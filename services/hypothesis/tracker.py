"""Bayesian hypothesis tracker: P(h | e) ∝ P(e | h) · P(h) over a finite space.

The tracker is deliberately dumb about *what* hypotheses mean — it only moves
probability mass. Meaning (attributes, predicates, likelihoods) lives in the
effect layer. Keep that boundary: it is what makes the Stage A baseline
interpretable and swappable (plan §4.5, §16).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from services.hypothesis.metrics import entropy, normalize

HypothesisId = str


class Tracker:
    def __init__(
        self,
        hypotheses: Sequence[HypothesisId],
        prior: Mapping[HypothesisId, float] | None = None,
    ) -> None:
        if not hypotheses:
            raise ValueError("hypothesis space must not be empty")
        if len(set(hypotheses)) != len(hypotheses):
            raise ValueError("hypothesis ids must be unique")
        if prior is None:
            weights = {h: 1.0 for h in hypotheses}
        else:
            unknown = [h for h in prior if h not in set(hypotheses)]
            if unknown:
                raise ValueError(f"prior references unknown hypotheses: {unknown[:5]}")
            missing = [h for h in hypotheses if h not in prior]
            if missing:
                raise ValueError(f"prior is missing hypotheses: {missing[:5]}")
            weights = {h: float(prior[h]) for h in hypotheses}
        self._hypotheses: tuple[HypothesisId, ...] = tuple(hypotheses)
        self._posterior: dict[HypothesisId, float] = normalize(weights)

    @property
    def hypotheses(self) -> tuple[HypothesisId, ...]:
        return self._hypotheses

    @property
    def posterior(self) -> dict[HypothesisId, float]:
        return dict(self._posterior)

    def update(self, likelihoods: Mapping[HypothesisId, float]) -> None:
        """Bayesian update with a full likelihood vector P(e | h) for every hypothesis."""
        missing = [h for h in self._hypotheses if h not in likelihoods]
        if missing:
            raise ValueError(f"likelihood vector is missing hypotheses: {missing[:5]}")
        if any(value < 0 for value in likelihoods.values()):
            raise ValueError("likelihoods must be non-negative")
        weighted = {h: self._posterior[h] * likelihoods[h] for h in self._hypotheses}
        total = sum(weighted.values())
        if total <= 0:
            raise ValueError(
                "evidence eliminated every hypothesis; the likelihood model is "
                "inconsistent with the hypothesis space"
            )
        self._posterior = {h: value / total for h, value in weighted.items()}

    def entropy(self) -> float:
        """Posterior entropy in bits."""
        return entropy(self._posterior)

    def map_hypothesis(self) -> tuple[HypothesisId, float]:
        """(hypothesis, probability) with the highest posterior; ties break by id."""
        best = max(sorted(self._posterior), key=lambda h: self._posterior[h])
        return best, self._posterior[best]

    def top_k(self, k: int) -> list[tuple[HypothesisId, float]]:
        ranked = sorted(self._posterior.items(), key=lambda kv: (-kv[1], kv[0]))
        return ranked[: max(0, k)]
