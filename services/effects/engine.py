"""Effect Engine: the per-session state machine (plan §2.1, §5).

Deterministic and evidence-based: the theatrical surface is produced by
LOKI-Language, never by the engine. One EffectSession == one session loop:
intro -> ask/answer ... -> reveal -> outcome. All state changes are recorded
as append-only events (docs/spec/event-schema.md).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from uuid import uuid4

from services.effects.events import Event, EventType
from services.effects.models import EffectDef, Question
from services.hypothesis.tracker import Tracker
from services.language.renderer import LanguageRenderer
from services.policy import info_gain


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
    ) -> None:
        self.session_id = session_id or uuid4().hex[:12]
        self.effect = effect
        self.renderer = renderer
        self.tracker = Tracker(list(effect.hypotheses), effect.prior)
        self.phase = Phase.ACTIVE
        self.asked: list[str] = []
        self.turn = 0
        self.current_question: Question | None = None
        self.last_info_gain: float | None = None
        self.prediction: Prediction | None = None
        self.committed_because: CommitReason | None = None
        self.last_outcome_correct: bool | None = None
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
        self._select_next_question()

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
        verbal answer remains the only committing action.
        """
        if self.phase is not Phase.ACTIVE:
            raise InvalidStateError(f"cannot observe in phase '{self.phase.value}'")
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
        """Apply the participant's answer to the current question and advance.

        ``utterance`` records the verbatim spoken transcript when the answer was
        given by voice (event schema v1.1) — consent-gated by the archive, never
        persisted during gameplay.
        """
        if self.phase is not Phase.ACTIVE:
            raise InvalidStateError(f"cannot answer in phase '{self.phase.value}'")
        question = self.current_question
        if question is None:  # pragma: no cover - impossible while ACTIVE
            raise InvalidStateError("no question is pending")
        if answer_id not in {a.id for a in question.answers}:
            raise ValueError(f"answer '{answer_id}' is not an option of question '{question.id}'")

        entropy_before = self.tracker.entropy()
        self.tracker.update(self.effect.likelihoods(question, answer_id))
        entropy_after = self.tracker.entropy()
        top_id, top_p = self.tracker.map_hypothesis()
        self._record(
            EventType.HYPOTHESIS_UPDATED,
            {
                "question_id": question.id,
                "answer_id": answer_id,
                "latency_ms": latency_ms,
                "utterance": utterance,
                "entropy_before": entropy_before,
                "entropy_after": entropy_after,
                "top_hypothesis_id": top_id,
                "top_probability": top_p,
            },
        )

        if entropy_after <= self.effect.termination.entropy_threshold_bits:
            self._commit(CommitReason.ENTROPY_THRESHOLD)
        elif self.turn >= self.effect.termination.max_turns:
            self._commit(CommitReason.MAX_TURNS)
        else:
            self.current_question = None
            self._select_next_question()

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

    def _select_next_question(self) -> None:
        question, gain = info_gain.best_question(
            self.effect, self.tracker.posterior, set(self.asked)
        )
        if question is None:
            self._commit(CommitReason.NO_INFORMATIVE_QUESTION)
            return
        self.current_question = question
        self.turn += 1
        self.asked.append(question.id)
        self.last_info_gain = gain
        self._record(
            EventType.POLICY_DECISION,
            {
                "action": "ask",
                "question_id": question.id,
                "info_gain_bits": gain,
                "alternatives_considered": [
                    q.id
                    for q in self.effect.questions
                    if q.id not in self.asked and q.id != question.id
                ],
                "reason": "max_expected_information_gain",
            },
        )

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
        self._record(
            EventType.EFFECT_REVEALED,
            {
                "prediction_id": hypothesis_id,
                "prediction_label": self.prediction.label,
                "confidence": confidence,
                "turns_used": self.turn,
                "committed_because": reason.value,
            },
        )

    def _record(self, event_type: EventType, payload: dict) -> None:
        self.history.append(Event(session_id=self.session_id, type=event_type, payload=payload))

    # -- rendered messages (delegated to LOKI-Language) --------------------------

    @property
    def intro_message(self) -> str:
        return self.renderer.intro(self.effect.title, self.session_id)

    @property
    def ask_message(self) -> str:
        assert self.current_question is not None
        return self.renderer.ask(self.current_question.text, self.session_id, self.turn)

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
