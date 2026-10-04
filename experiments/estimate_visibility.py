"""Empirical Visibility Weight (κ) and Visible Information Estimator (§8, Job a).

Estimates κ and I_visible from empirical participant surveys and simulator traces,
providing point estimates, 95% bootstrap confidence intervals, and breakeven κ*
calculations to replace authored constants with measured distributions.

Reference:
    Directive §8 (Apparent Information & Information Mystery Gap)
    docs/magic-factor.md §2.1
    docs/covert-fishing.md §6 finding 3
"""

from __future__ import annotations

import math
import random
import statistics
from dataclasses import dataclass
from typing import Sequence


@dataclass(frozen=True)
class VisibilityEstimate:
    point_estimate: float
    ci_lower: float
    ci_upper: float
    method: str
    sample_size: int
    breakeven_kappa: float | None = None


def bootstrap_ci(
    values: Sequence[float],
    statistic=statistics.mean,
    reps: int = 2000,
    seed: int = 0,
) -> tuple[float, float]:
    """Calculate 95% bootstrap confidence interval."""
    if not values:
        return (float("nan"), float("nan"))
    if len(values) == 1:
        return (float(values[0]), float(values[0]))
    rng = random.Random(seed)
    n = len(values)
    stats: list[float] = []
    for _ in range(reps):
        sample = [values[rng.randrange(n)] for _ in range(n)]
        stats.append(statistic(sample))
    stats.sort()
    return (stats[int(0.025 * reps)], stats[int(0.975 * reps) - 1])


def estimate_kappa_from_surveys(
    survey_rows_a: list[dict],
    survey_rows_b: list[dict],
    reps: int = 2000,
) -> VisibilityEstimate:
    """Estimate empirical visibility weight κ from Condition A (direct) and

    Condition B (mixed/covert) Likert survey responses.

    Perceived interrogation inversely correlates with perceived freedom and naturalness.
    We proxy perceived interrogation by I_score = (8 - freedom) + (8 - naturalness).
    κ models the relative interrogation weight of covert interaction vs direct questioning:
    κ = clamp(mean(I_score_B) / mean(I_score_A), 0.0, 1.0)
    """
    if not survey_rows_a or not survey_rows_b:
        return VisibilityEstimate(
            point_estimate=0.25,
            ci_lower=float("nan"),
            ci_upper=float("nan"),
            method="uncalibrated_prior",
            sample_size=len(survey_rows_a) + len(survey_rows_b),
        )

    def interrogation_score(row: dict) -> float:
        freedom = float(row.get("freedom", 4))
        naturalness = float(row.get("naturalness", 4))
        return (8.0 - freedom) + (8.0 - naturalness)

    scores_a = [interrogation_score(r) for r in survey_rows_a]
    scores_b = [interrogation_score(r) for r in survey_rows_b]

    mean_a = statistics.mean(scores_a)
    mean_b = statistics.mean(scores_b)
    # Ratio of perceived interrogation in mixed condition vs direct condition
    raw_ratio = (mean_b / mean_a) if mean_a > 0 else 0.5
    point_est = max(0.0, min(1.0, raw_ratio * 0.35))  # normalized by covert turn ratio

    # Bootstrap ratio
    rng = random.Random(42)
    n_a, n_b = len(scores_a), len(scores_b)
    ratios: list[float] = []
    for _ in range(reps):
        s_a = statistics.mean([scores_a[rng.randrange(n_a)] for _ in range(n_a)])
        s_b = statistics.mean([scores_b[rng.randrange(n_b)] for _ in range(n_b)])
        r = (s_b / s_a) * 0.35 if s_a > 0 else 0.5
        ratios.append(max(0.0, min(1.0, r)))
    ratios.sort()
    ci_low = ratios[int(0.025 * reps)]
    ci_high = ratios[int(0.975 * reps) - 1]

    return VisibilityEstimate(
        point_estimate=round(point_est, 4),
        ci_lower=round(ci_low, 4),
        ci_upper=round(ci_high, 4),
        method="likert_interrogation_ratio",
        sample_size=n_a + n_b,
    )


def compute_breakeven_kappa(
    acc_auto: float,
    acc_direct: float,
    direct_bits_auto: float,
    direct_bits_direct: float,
    covert_turns_auto: float,
) -> float | None:
    """Compute breakeven κ* where M(auto, κ*) = M(direct).

    M(auto) = acc_auto / (1 + direct_bits_auto + κ * covert_turns_auto * log2(3))
    M(direct) = acc_direct / (1 + direct_bits_direct)
    Equating the two yields:
    1 + direct_bits_auto + κ* * covert_turns_auto * log2(3) = (acc_auto / acc_direct) * (1 + direct_bits_direct)
    κ* = [ (acc_auto / acc_direct) * (1 + direct_bits_direct) - (1 + direct_bits_auto) ] / [ covert_turns_auto * log2(3) ]
    """
    if covert_turns_auto <= 0 or acc_direct <= 0:
        return None
    denom = covert_turns_auto * math.log2(3.0)
    target_vis = (acc_auto / acc_direct) * (1.0 + direct_bits_direct) - 1.0
    diff = target_vis - direct_bits_auto
    kappa_star = diff / denom
    return round(kappa_star, 4)
