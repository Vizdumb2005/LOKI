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
    sample_size_a: int = 0
    sample_size_b: int = 0
    breakeven_kappa: float | None = None


def bootstrap_ci(
    values: Sequence[float],
    statistic=statistics.mean,
    reps: int = 2000,
    seed: int = 0,
) -> tuple[float, float]:
    """Calculate 95% bootstrap confidence interval using empirical percentiles.

    Args:
        values: Sequence of numeric samples.
        statistic: Callable computing summary statistic from a sample list.
            Defaults to statistics.mean.
        reps: Number of bootstrap resamples (default 2,000 for standard 95% CI precision).
        seed: Random seed for deterministic reproducibility.

    Returns:
        tuple[float, float]: (ci_lower, ci_upper) representing 2.5th and 97.5th percentiles.
            Returns (nan, nan) if values is empty or reps <= 0.
            Returns (val, val) if values has only 1 element.
    """
    if not values or reps <= 0:
        return (float("nan"), float("nan"))
    clean_values = [float(v) for v in values if v is not None and not math.isnan(float(v))]
    if not clean_values:
        return (float("nan"), float("nan"))
    if len(clean_values) == 1:
        return (clean_values[0], clean_values[0])
    rng = random.Random(seed)
    n = len(clean_values)
    stats: list[float] = []
    for _ in range(reps):
        sample = [clean_values[rng.randrange(n)] for _ in range(n)]
        stats.append(statistic(sample))
    stats.sort()
    idx_low = max(0, min(reps - 1, int(0.025 * reps)))
    idx_high = max(idx_low, min(reps - 1, int(0.975 * reps) - 1))
    return (round(stats[idx_low], 4), round(stats[idx_high], 4))


def estimate_kappa_from_surveys(
    survey_rows_a: list[dict],
    survey_rows_b: list[dict],
    reps: int = 2000,
    seed: int = 42,
) -> VisibilityEstimate:
    """Estimate empirical visibility weight κ from Condition A (direct) and
    Condition B (mixed/covert) Likert survey responses.

    Perceived interrogation inversely correlates with perceived freedom and naturalness.
    We proxy perceived interrogation by I_score = (8 - freedom) + (8 - naturalness).
    κ models the relative interrogation weight of covert interaction vs direct questioning:
    κ = clamp(mean(I_score_B) / mean(I_score_A) * 0.35, 0.0, 1.0)

    Sample size documentation:
        Condition A (direct baseline) sample size: len(survey_rows_a)
        Condition B (mixed covert) sample size: len(survey_rows_b)
        Total sample size: len(survey_rows_a) + len(survey_rows_b)
        Bootstrap resamples: 2,000 iterations for 95% percentile confidence intervals.

    Args:
        survey_rows_a: List of survey response dicts for Condition A (direct questioning).
        survey_rows_b: List of survey response dicts for Condition B (mixed/covert).
        reps: Number of bootstrap iterations (default 2,000).
        seed: Random seed for bootstrap sampling (default 42).

    Returns:
        VisibilityEstimate containing point estimate, 95% CI bounds, method name,
        and documented sample sizes.
    """
    n_a = len(survey_rows_a) if survey_rows_a else 0
    n_b = len(survey_rows_b) if survey_rows_b else 0
    total_n = n_a + n_b

    if not survey_rows_a or not survey_rows_b:
        return VisibilityEstimate(
            point_estimate=0.25,
            ci_lower=float("nan"),
            ci_upper=float("nan"),
            method="uncalibrated_prior",
            sample_size=total_n,
            sample_size_a=n_a,
            sample_size_b=n_b,
        )

    def interrogation_score(row: dict) -> float:
        if not isinstance(row, dict):
            return 8.0
        try:
            f_val = row.get("freedom")
            freedom = float(f_val) if f_val is not None else 4.0
            if math.isnan(freedom):
                freedom = 4.0
        except (ValueError, TypeError):
            freedom = 4.0
        try:
            n_val = row.get("naturalness")
            naturalness = float(n_val) if n_val is not None else 4.0
            if math.isnan(naturalness):
                naturalness = 4.0
        except (ValueError, TypeError):
            naturalness = 4.0
        freedom = max(1.0, min(7.0, freedom))
        naturalness = max(1.0, min(7.0, naturalness))
        return (8.0 - freedom) + (8.0 - naturalness)

    scores_a = [interrogation_score(r) for r in survey_rows_a]
    scores_b = [interrogation_score(r) for r in survey_rows_b]

    mean_a = statistics.mean(scores_a)
    mean_b = statistics.mean(scores_b)
    # Ratio of perceived interrogation in mixed condition vs direct condition
    raw_ratio = (mean_b / mean_a) if mean_a > 0 else 0.5
    point_est = max(0.0, min(1.0, raw_ratio * 0.35))  # normalized by covert turn ratio

    # 2,000 bootstrap resamples for 95% CI
    n_reps = max(1, reps)
    rng = random.Random(seed)
    ratios: list[float] = []
    for _ in range(n_reps):
        s_a = statistics.mean([scores_a[rng.randrange(n_a)] for _ in range(n_a)])
        s_b = statistics.mean([scores_b[rng.randrange(n_b)] for _ in range(n_b)])
        r = (s_b / s_a) * 0.35 if s_a > 0 else 0.5
        ratios.append(max(0.0, min(1.0, r)))
    ratios.sort()
    idx_low = max(0, min(n_reps - 1, int(0.025 * n_reps)))
    idx_high = max(idx_low, min(n_reps - 1, int(0.975 * n_reps) - 1))
    ci_low = ratios[idx_low]
    ci_high = ratios[idx_high]

    return VisibilityEstimate(
        point_estimate=round(point_est, 4),
        ci_lower=round(ci_low, 4),
        ci_upper=round(ci_high, 4),
        method="likert_interrogation_ratio",
        sample_size=total_n,
        sample_size_a=n_a,
        sample_size_b=n_b,
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
    1 + direct_bits_auto + κ* * covert_turns_auto * log2(3)
        = (acc_auto / acc_direct) * (1 + direct_bits_direct)
    κ* = [ (acc_auto / acc_direct) * (1 + direct_bits_direct) - (1 + direct_bits_auto) ]
        / [ covert_turns_auto * log2(3) ]

    Args:
        acc_auto: Top-1 prediction accuracy under auto policy. Must be > 0.
        acc_direct: Top-1 prediction accuracy under direct baseline. Must be > 0.
        direct_bits_auto: Visible bits from explicit questions in auto policy.
        direct_bits_direct: Visible bits from explicit questions in direct baseline.
        covert_turns_auto: Mean number of covert turns per session in auto policy. Must be > 0.

    Returns:
        float | None: The analytic breakeven visibility weight κ* rounded to 4 decimals,
        or None if computation is invalid (e.g. non-positive auto or direct accuracy,
        zero covert turns, or NaN inputs).
    """
    for val in (acc_auto, acc_direct, direct_bits_auto, direct_bits_direct, covert_turns_auto):
        if not isinstance(val, (int, float)) or math.isnan(val) or math.isinf(val):
            return None

    if covert_turns_auto <= 0 or acc_direct <= 0 or acc_auto <= 0:
        return None

    denom = covert_turns_auto * math.log2(3.0)
    if denom <= 0:
        return None

    target_vis = (acc_auto / acc_direct) * (1.0 + direct_bits_direct) - 1.0
    diff = target_vis - direct_bits_auto
    kappa_star = diff / denom
    if math.isnan(kappa_star) or math.isinf(kappa_star):
        return None
    return round(kappa_star, 4)
