"""Truthful-noisy participant: samples answers from the effect's likelihood model.

Given a hidden target, the participant answers each question by drawing from
P(answer | truth) exactly as the engine's likelihood model defines it — reliable
but imperfect, per-question reliability optionally overridden for noise sweeps.

The optional gaze behavior (plan §8 behavior model, Phase 2): with probability
``gaze_prob`` the participant's eyes linger on an answer before giving it —
usually the one they intend (``gaze_accuracy``), sometimes a decoy.
"""

from __future__ import annotations

import random

from services.effects.agreement import RESPONSE_MODEL
from services.effects.models import EffectDef, Question
from services.fusion.engine import downgrade_strength
from services.language.response_signals import AgreementStrength


class TruthfulNoisyParticipant:
    def __init__(
        self,
        effect: EffectDef,
        true_hypothesis_id: str,
        rng: random.Random,
        reliability_override: float | None = None,
        gaze_prob: float = 0.0,
        gaze_accuracy: float = 0.8,
        force_susceptibility: float = 0.0,
        p_fast_truthful: float = 0.85,
        p_fast_guess: float = 0.25,
        fishing_evasiveness: float = 0.0,
    ) -> None:
        if true_hypothesis_id not in effect.hypotheses:
            raise ValueError(f"unknown hypothesis '{true_hypothesis_id}'")
        self._effect = effect
        self._truth = effect.hypotheses[true_hypothesis_id]
        self._rng = rng
        self._override = reliability_override
        self._gaze_prob = gaze_prob
        self._gaze_accuracy = gaze_accuracy
        self._force_susceptibility = force_susceptibility
        self._p_fast_truthful = p_fast_truthful
        self._p_fast_guess = p_fast_guess
        self._fishing_evasiveness = fishing_evasiveness

    def answer(self, question: Question, salient_answer_id: str | None = None) -> str:
        """Sample an answer, optionally under choice-architecture emphasis.

        With probability ``force_susceptibility`` the answer-noise mass
        (1 − reliability) concentrates on the salient option instead of
        spreading uniformly — the mechanical choice shift only
        (docs/choice-architecture.md §5: real priming psychology is not
        modeled; the target here is fixed). P(correct) is unchanged by
        construction.
        """
        reliability = self._override if self._override is not None else question.reliability
        noise = 1.0 - reliability
        options = question.answers
        truth_id = next(a.id for a in options if a.predicate.matches(self._truth))
        concentrated = (
            salient_answer_id is not None
            and salient_answer_id != truth_id
            and self._force_susceptibility > 0.0
            and self._rng.random() < self._force_susceptibility
        )
        weights = [
            reliability
            if a.id == truth_id
            else noise
            if concentrated and a.id == salient_answer_id
            else 0.0
            if concentrated
            else noise / (len(options) - 1)
            for a in options
        ]
        return self._rng.choices([a.id for a in options], weights=weights, k=1)[0]

    def answer_with_latency(
        self, question: Question, salient_answer_id: str | None = None
    ) -> tuple[str, float]:
        """Sample an answer plus a latency correlated with its quality
        (ROADMAP Phase 5 behavior model): the answer the participant is sure
        of usually comes fast; a guess usually takes longer — with enough
        crossover that fusion has to earn its keep
        (docs/passive-signals.md §4).

        Returns ``(answer_id, latency_ms)``. The extra ``rng.random()`` draw
        happens only when latency modeling is on (``p_fast`` bounds), keeping
        ``answer()``-only runs stream-compatible.
        """
        answer_id = self.answer(question, salient_answer_id)
        truth_id = next(a.id for a in question.answers if a.predicate.matches(self._truth))
        p_fast = self._p_fast_truthful if answer_id == truth_id else self._p_fast_guess
        if self._rng.random() < p_fast:
            latency = self._rng.uniform(600.0, 2500.0)
        else:
            latency = self._rng.uniform(3000.0, 9000.0)
        return answer_id, latency

    def look(self, question: Question) -> tuple[str, float] | None:
        """An observation for the current question, or None (didn't linger).

        Returns ``(answer_id, dwell_ms)``. Only fires when the effect declares
        a gaze channel and the gaze-probability roll passes.
        """
        if "gaze_dwell" not in self._effect.observations:
            return None
        if self._rng.random() >= self._gaze_prob:
            return None
        truthful = next(a.id for a in question.answers if a.predicate.matches(self._truth))
        if self._rng.random() < self._gaze_accuracy:
            target = truthful
        else:
            others = [a.id for a in question.answers if a.id != truthful]
            target = self._rng.choice(others)
        return target, self._rng.uniform(400.0, 1500.0)

    def respond_to_fishing(self, question: Question, asserted_answer_id: str) -> tuple[str, float]:
        """Graded reaction to a covert assertion, sampled from the shared
        response model (services/effects/agreement.py) — the well-calibrated
        case; calibrating against real participants is later-phase work.

        Returns ``(strength, latency_ms)``. Latency models hesitation: reads
        that miss take longer to answer. It is recorded in events but never
        fused into updates (latency fusion is ROADMAP Phase 5).
        """
        asserted = next(a for a in question.answers if a.id == asserted_answer_id)
        holds = asserted.predicate.matches(self._truth)
        strengths = list(RESPONSE_MODEL)
        weights = [RESPONSE_MODEL[s][holds] for s in strengths]
        strength = self._rng.choices(strengths, weights=weights, k=1)[0]
        if self._fishing_evasiveness > 0.0 and self._rng.random() < self._fishing_evasiveness:
            # the evasive failure mode: reactions soften one step toward
            # uncertainty (docs/rl-policy.md §3)
            strength = downgrade_strength(strength)
        latency = self._rng.uniform(500.0, 2000.0) if holds else self._rng.uniform(1200.0, 4000.0)
        return AgreementStrength(strength).value, latency
