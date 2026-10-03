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

from services.effects.models import EffectDef, Question


class TruthfulNoisyParticipant:
    def __init__(
        self,
        effect: EffectDef,
        true_hypothesis_id: str,
        rng: random.Random,
        reliability_override: float | None = None,
        gaze_prob: float = 0.0,
        gaze_accuracy: float = 0.8,
    ) -> None:
        if true_hypothesis_id not in effect.hypotheses:
            raise ValueError(f"unknown hypothesis '{true_hypothesis_id}'")
        self._effect = effect
        self._truth = effect.hypotheses[true_hypothesis_id]
        self._rng = rng
        self._override = reliability_override
        self._gaze_prob = gaze_prob
        self._gaze_accuracy = gaze_accuracy

    def answer(self, question: Question) -> str:
        reliability = self._override if self._override is not None else question.reliability
        weights = [
            reliability
            if a.predicate.matches(self._truth)
            else (1.0 - reliability) / (len(question.answers) - 1)
            for a in question.answers
        ]
        return self._rng.choices([a.id for a in question.answers], weights=weights, k=1)[0]

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
