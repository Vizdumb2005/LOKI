"""Effect Engine: the per-session state machine (plan §2.1, §5).

Deterministic and evidence-based: the theatrical surface is produced by
LOKI-Language, never by the engine. One EffectSession == one session loop:
intro -> ask/answer ... -> reveal -> outcome. All state changes are recorded
as append-only events (docs/spec/event-schema.md).

ROADMAP Phase 2: turns have a MODE. Direct turns ask a question and take an
option id; covert turns assert one option (chosen by the Method Selection
Policy, services/policy/method_selection.py) and take an agreement strength,
applied as a soft likelihood update (services/effects/agreement.py). The mode
changes only what is asked and how the reply is read — never the posterior's
integrity: updates stay soft, every hypothesis stays alive, and termination
rules are identical for both modes.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, replace
from enum import Enum
from uuid import uuid4

from services.brain.contract import BrainSelector
from services.brain.contract import validate as validate_brain
from services.effects.agreement import agreement_likelihoods
from services.effects.events import Event, EventType
from services.effects.models import EffectDef, Question
from services.fusion.engine import (
    downgrade_strength,
    is_hesitant,
    latency_factor,
    modulated_reliability,
)
from services.hypothesis.tracker import Tracker
from services.language.renderer import LanguageRenderer
from services.language.response_signals import AgreementStrength
from services.policy.method_selection import (
    DEFAULT_PARAMS,
    FishingState,
    TurnPlan,
    select_turn,
)
from services.policy.reveal_planner import RevealPlan, plan_reveal

TurnSelector = Callable[[EffectDef, dict[str, float], set[str], FishingState], TurnPlan | None]


def _default_turn_selector(
    effect: EffectDef,
    posterior: dict[str, float],
    asked: set[str],
    state: FishingState,
) -> TurnPlan | None:
    return select_turn(effect, posterior, asked, state, DEFAULT_PARAMS)


class InvalidStateError(RuntimeError):
    """Operation not valid in the session's current phase (maps to HTTP 409)."""


class Phase(str, Enum):
    ACTIVE = "active"
    REVEALED = "revealed"
    OUTCOME = "outcome"


class CommitReason(str, Enum):
    ENTROPY_THRESHOLD = "entropy_threshold"
    MAX_TURNS = "max_turns"
    NO_INFORMATIVE_QUESTION = "no_informative_question"


@dataclass
class Prediction:
    hypothesis_id: str
    label: str
    confidence: float


class EffectSession:
    def __init__(
        self,
        effect: EffectDef,
        renderer: LanguageRenderer,
        session_id: str | None = None,
        selector: TurnSelector | None = None,
        performance: bool = True,
        condition: str | None = None,
        decide: BrainSelector | None = None,
    ) -> None:
        self.session_id = session_id or uuid4().hex[:12]
        self.effect = effect
        self.renderer = renderer
        # ROADMAP Phase 6: the turn selector is injectable (RL policies,
        # A/B conditions); the default is the hand-designed method policy.
        self._selector = selector or _default_turn_selector
        # Mission Phase 3: optional Brain. Same inputs as the selector, but
        # the choice passes through the hard action contract and is logged.
        # None = legacy path, byte-identical behavior.
        self._decide = decide
        # Condition A of the A/B suite: the performance layer (emphasis,
        # staged reveals, reframes) switches off; the Bayesian engine is
        # identical (docs/human-trials.md §2).
        self.performance = performance
        self.condition = condition
        self.tracker = Tracker(list(effect.hypotheses), effect.prior)
        self.phase = Phase.ACTIVE
        self.asked: list[str] = []
        self.turn = 0
        self.current_question: Question | None = None
        self.current_mode: str = "direct"
        self.asserted_answer_id: str | None = None
        self.current_force_target: str | None = None
        self._fishing = FishingState()
        self.last_info_gain: float | None = None
        self.prediction: Prediction | None = None
        self.reveal_plan: RevealPlan | None = None
        self.committed_because: CommitReason | None = None
        self.last_outcome_correct: bool | None = None
        # Equivocation state (ROADMAP Phase 3): a miss/unclear read queues a
        # reframe that opens the NEXT turn's message, then moves to
        # current_reframe for rendering until the turn is answered.
        self._reframe: tuple[str, str] | None = None
        self.current_reframe: tuple[str, str] | None = None
        self.history: list[Event] = []
        self.initial_entropy = self.tracker.entropy()
        self._record(
            EventType.SESSION_STARTED,
            {
                "effect_id": effect.id,
                "initial_entropy_bits": self.initial_entropy,
                "hypothesis_count": len(effect.hypotheses),
            },
        )
        self._select_next_turn()

    # -- session loop ----------------------------------------------------------

    def observe(
        self,
        question_id: str,
        answer_id: str,
        channel: str,
        dwell_ms: float | None = None,
    ) -> None:
        """Apply weak non-verbal evidence (schema v1.1) without advancing the session.

        Observations move probability mass only: the question stays current, the
        turn count is untouched, and termination is never evaluated here — the
        verbal response remains the only committing action. They apply to
        direct turns only: on a covert turn the screen shows agreement
        reactions, not answer options, so there is nothing to dwell on.
        """
        if self.phase is not Phase.ACTIVE:
            raise InvalidStateError(f"cannot observe in phase '{self.phase.value}'")
        if self.current_mode == "covert":
            raise InvalidStateError(
                "observations apply to direct question turns, not covert assertions"
            )
        question = self.current_question
        if question is None:  # pragma: no cover - impossible while ACTIVE
            raise InvalidStateError("no question is pending")
        if question.id != question_id:
            raise ValueError(
                f"observation targets question '{question_id}' but '{question.id}' is current"
            )
        channel_cfg = self.effect.observations.get(channel)
        if channel_cfg is None:
            raise ValueError(f"effect '{self.effect.id}' has no observation channel '{channel}'")
        if answer_id not in {a.id for a in question.answers}:
            raise ValueError(f"answer '{answer_id}' is not an option of question '{question.id}'")

        entropy_before = self.tracker.entropy()
        self.tracker.update(
            self.effect.likelihoods(question, answer_id, reliability=channel_cfg.reliability)
        )
        entropy_after = self.tracker.entropy()
        top_id, top_p = self.tracker.map_hypothesis()
        answer_label = next(a.label for a in question.answers if a.id == answer_id)
        self._record(
            EventType.OBSERVATION_RECORDED,
            {
                "channel": channel,
                "question_id": question.id,
                "answer_id": answer_id,
                "answer_label": answer_label,
                "dwell_ms": dwell_ms,
                "reliability": channel_cfg.reliability,
                "entropy_before": entropy_before,
                "entropy_after": entropy_after,
                "top_hypothesis_id": top_id,
                "top_probability": top_p,
            },
        )

    def answer(
        self,
        answer_id: str,
        latency_ms: float | None = None,
        utterance: str | None = None,
    ) -> None:
        """Apply the participant's response to the current turn and advance.

        Direct turns take an option id. Covert turns take an agreement
        strength (the UI's fixed Yes / Sort of / Not really scale) —
        dispatched to :meth:`respond_agreement`.

        ``utterance`` records the verbatim spoken transcript when the answer
        was given by voice (event schema v1.1) — consent-gated by the archive,
        never persisted during gameplay.
        """
        if self.current_mode == "covert":
            self.respond_agreement(answer_id, latency_ms=latency_ms, utterance=utterance)
            return
        if self.phase is not Phase.ACTIVE:
            raise InvalidStateError(f"cannot answer in phase '{self.phase.value}'")
        question = self.current_question
        if question is None:  # pragma: no cover - impossible while ACTIVE
            raise InvalidStateError("no question is pending")
        if answer_id not in {a.id for a in question.answers}:
            raise ValueError(f"answer '{answer_id}' is not an option of question '{question.id}'")
        if self.current_force_target is not None and answer_id != self.current_force_target:
            # ROADMAP Phase 4: the participant defied the force. The update
            # below proceeds unchanged; the defiance is folded into the
            # performance (an equivocation reframe opens the next turn) and
            # the primitives take a one-turn rest (docs/choice-architecture.md §4).
            force_label = next(
                a.label for a in question.answers if a.id == self.current_force_target
            )
            self._reframe = ("defied", force_label)
            self._fishing.force_cooldown = 1

        entropy_before = self.tracker.entropy()
        # ROADMAP Phase 5: latency fusion — a hesitant answer is discounted
        # toward the channel floor; a fast one keeps its full weight.
        reliability_effective = None
        if self.effect.latency_channel is not None and latency_ms is not None:
            factor = latency_factor(self.effect.latency_channel, latency_ms)
            reliability_effective = modulated_reliability(question.reliability, factor)
        self.tracker.update(
            self.effect.likelihoods(question, answer_id, reliability=reliability_effective)
        )
        self._advance(
            question,
            {
                "question_id": question.id,
                "answer_id": answer_id,
                "mode": "direct",
                "agreement_strength": None,
                "asserted_answer_id": None,
                "reliability_effective": reliability_effective,
                "typing_rhythm": None,
                "latency_ms": latency_ms,
                "utterance": utterance,
            },
            entropy_before,
        )

    def respond_agreement(
        self,
        strength: str,
        latency_ms: float | None = None,
        utterance: str | None = None,
        typing_rhythm: dict | None = None,
    ) -> None:
        """Apply a graded response to the current covert assertion and advance.

        ``strength`` is an :class:`AgreementStrength` value. Unclear responses
        advance the turn without touching the posterior — extractor
        uncertainty is not evidence (docs/covert-fishing.md). ``utterance``
        records the verbatim participant text (spoken transcript or typed
        reply) under the same consent semantics as direct turns. When the
        reply was typed hesitantly (``typing_rhythm`` aggregates, ROADMAP
        Phase 5), the strength is downgraded one step toward uncertainty —
        hesitant words are worth less (docs/passive-signals.md §2).
        """
        if self.phase is not Phase.ACTIVE:
            raise InvalidStateError(f"cannot respond in phase '{self.phase.value}'")
        if self.current_mode != "covert":
            raise InvalidStateError(
                "the current turn is a direct question — respond with an option id"
            )
        question = self.current_question
        if question is None or self.asserted_answer_id is None:  # pragma: no cover
            raise InvalidStateError("no covert assertion is pending")
        try:
            strength = AgreementStrength(strength)
        except ValueError:
            raise ValueError(
                f"unknown agreement strength '{strength}' (expected one of "
                f"{[s.value for s in AgreementStrength]})"
            ) from None

        strength_effective = strength
        if typing_rhythm is not None and is_hesitant(
            typing_rhythm.get("first_key_ms"), typing_rhythm.get("median_interval_ms")
        ):
            strength_effective = downgrade_strength(strength)

        entropy_before = self.tracker.entropy()
        if strength_effective is not AgreementStrength.UNCLEAR:
            self.tracker.update(
                agreement_likelihoods(
                    self.effect, question, self.asserted_answer_id, strength_effective
                )
            )
        if strength_effective in (AgreementStrength.STRONG_YES, AgreementStrength.LEAN_YES):
            self._fishing.consecutive_misses = 0
            self._reframe = None
        else:
            self._fishing.consecutive_misses += 1
            kind = "unclear" if strength_effective is AgreementStrength.UNCLEAR else "missed"
            self._reframe = (kind, self.asserted_label or "")
        self._advance(
            question,
            {
                "question_id": question.id,
                "answer_id": None,
                "mode": "covert",
                "agreement_strength": strength.value,
                "agreement_strength_effective": (
                    strength_effective.value if strength_effective is not strength else None
                ),
                "asserted_answer_id": self.asserted_answer_id,
                "typing_rhythm": typing_rhythm,
                "reliability_effective": None,
                "latency_ms": latency_ms,
                "utterance": utterance,
            },
            entropy_before,
        )

    def report_outcome(self, correct: bool) -> None:
        if self.phase is not Phase.REVEALED:
            raise InvalidStateError(f"cannot report outcome in phase '{self.phase.value}'")
        self.phase = Phase.OUTCOME
        self.last_outcome_correct = correct
        self._record(
            EventType.PARTICIPANT_OUTCOME,
            {"correct": correct, "turns_used": self.turn},
        )

    # -- internals ---------------------------------------------------------------

    def _select_next_turn(self) -> None:
        brain_action: str | None = None
        if self._decide is not None:
            decision = validate_brain(
                self._decide(self.effect, self.tracker.posterior, set(self.asked), self._fishing),
                self.effect,
                set(self.asked),
            )
            brain_action = decision.action.value
            plan = decision.to_turn_plan()
        else:
            plan = self._selector(
                self.effect, self.tracker.posterior, set(self.asked), self._fishing
            )
        if plan is None:
            self._commit(CommitReason.NO_INFORMATIVE_QUESTION)
            return
        if not self.performance and plan.salient_answer_id is not None:
            plan = replace(plan, salient_answer_id=None)
        self.current_question = next(q for q in self.effect.questions if q.id == plan.question_id)
        self.current_mode = plan.mode
        self.asserted_answer_id = plan.asserted_answer_id
        self.current_force_target = plan.salient_answer_id
        if plan.mode == "covert":
            self._fishing.covert_turns += 1
        self.turn += 1
        self.asked.append(plan.question_id)
        self.last_info_gain = plan.info_gain_bits
        # The reframe queued by a missed/unclear read opens THIS turn's
        # message; the decision event records it for the trajectory.
        self.current_reframe = self._reframe
        self._reframe = None
        self._record(
            EventType.POLICY_DECISION,
            {
                "action": "ask",
                "brain_action": brain_action,
                "mode": plan.mode,
                "question_id": plan.question_id,
                "asserted_answer_id": plan.asserted_answer_id,
                "force_target": plan.salient_answer_id,
                "info_gain_bits": plan.info_gain_bits,
                "reframe": self.current_reframe[0] if self.current_reframe else None,
                "alternatives_considered": [
                    q.id
                    for q in self.effect.questions
                    if q.id not in self.asked and q.id != plan.question_id
                ],
                "reason": plan.reason,
            },
        )

    def _advance(
        self,
        question: Question,
        payload: dict,
        entropy_before: float,
    ) -> None:
        """Shared tail of both response paths: record, evaluate termination,
        select the next turn."""
        entropy_after = self.tracker.entropy()
        top_id, top_p = self.tracker.map_hypothesis()
        payload.update(
            {
                "entropy_before": entropy_before,
                "entropy_after": entropy_after,
                "top_hypothesis_id": top_id,
                "top_probability": top_p,
            }
        )
        self._record(EventType.HYPOTHESIS_UPDATED, payload)

        if entropy_after <= self.effect.termination.entropy_threshold_bits:
            self._commit(CommitReason.ENTROPY_THRESHOLD)
        elif self.turn >= self.effect.termination.max_turns:
            self._commit(CommitReason.MAX_TURNS)
        else:
            self.current_question = None
            self.asserted_answer_id = None
            self.current_force_target = None
            self.current_mode = "direct"
            self._select_next_turn()

    def _commit(self, reason: CommitReason) -> None:
        hypothesis_id, confidence = self.tracker.map_hypothesis()
        self.prediction = Prediction(
            hypothesis_id=hypothesis_id,
            label=self.effect.hypothesis_label(hypothesis_id),
            confidence=confidence,
        )
        self.committed_because = reason
        self.phase = Phase.REVEALED
        self.current_question = None
        self.asserted_answer_id = None
        self.current_force_target = None
        self.current_reframe = None
        self._reframe = None
        # ROADMAP Phase 3: route the reveal through the multiple-outs planner.
        # The prediction and its banded phrasing are unchanged; only the
        # staging around them is chosen here. Condition A (performance off)
        # collapses every path to the plain single-line reveal.
        self.reveal_plan = plan_reveal(self.effect, self.tracker.top_k(3), list(self.asked))
        if not self.performance:
            self.reveal_plan = RevealPlan(
                path="plain",
                candidates=self.reveal_plan.candidates,
                stages=(),
            )
        self._record(
            EventType.EFFECT_REVEALED,
            {
                "prediction_id": hypothesis_id,
                "prediction_label": self.prediction.label,
                "confidence": confidence,
                "turns_used": self.turn,
                "committed_because": reason.value,
                "reveal_path": self.reveal_plan.path,
                "reveal_candidates": list(self.reveal_plan.candidates),
                "stages": [
                    {"kind": s.kind, "attr": s.attr, "label": s.label}
                    for s in self.reveal_plan.stages
                ],
            },
        )

    def _record(self, event_type: EventType, payload: dict) -> None:
        self.history.append(Event(session_id=self.session_id, type=event_type, payload=payload))

    # -- rendered messages (delegated to LOKI-Language) --------------------------

    @property
    def intro_message(self) -> str:
        return self.renderer.intro(self.effect.title, self.session_id)

    @property
    def asserted_label(self) -> str | None:
        """The option the current covert turn asserts (None on direct turns)."""
        if (
            self.current_mode != "covert"
            or self.asserted_answer_id is None
            or self.current_question is None
        ):
            return None
        return next(
            a.label for a in self.current_question.answers if a.id == self.asserted_answer_id
        )

    @property
    def ask_message(self) -> str:
        assert self.current_question is not None
        if self.current_mode == "covert":
            line = self.renderer.fishing(
                self.asserted_label or "",
                self.session_id,
                self.turn,
                openers=self.current_question.fishing_openers,
            )
        else:
            line = self.renderer.ask(self.current_question.text, self.session_id, self.turn)
        if self.current_reframe is not None and self.performance:
            kind, label = self.current_reframe
            reframe = self.renderer.reframe(kind, label, self.session_id, self.turn)
            line = f"{reframe}\n\n{line}"
        return line

    @property
    def reveal_stage_messages(self) -> list[tuple[str, str]]:
        """The staged beats before the banded identity line (ROADMAP Phase 3).

        Empty for plain reveals; (kind, text) pairs otherwise — the identity
        line itself remains :attr:`reveal_message`.
        """
        if self.reveal_plan is None or self.prediction is None:
            return []
        return self.renderer.stage_reveal(
            self.reveal_plan.stages,
            self.prediction.label,
            self.prediction.confidence,
            self.session_id,
        )

    @property
    def reveal_message(self) -> str:
        assert self.prediction is not None
        return self.renderer.reveal(
            self.prediction.label, self.prediction.confidence, self.session_id
        )

    @property
    def outcome_message(self) -> str:
        assert self.last_outcome_correct is not None
        return self.renderer.outcome(self.last_outcome_correct, self.turn, self.session_id)
