"""Tests for empirical visibility estimator (Job a)."""

import math

from experiments.estimate_visibility import (
    bootstrap_ci,
    compute_breakeven_kappa,
    estimate_kappa_from_surveys,
)


def test_bootstrap_ci():
    values = [4.0, 5.0, 6.0, 5.0, 4.5]
    low, high = bootstrap_ci(values, reps=500, seed=42)
    assert 4.0 <= low <= high <= 6.0


def test_estimate_kappa_from_surveys_empty():
    est = estimate_kappa_from_surveys([], [])
    assert est.point_estimate == 0.25
    assert est.method == "uncalibrated_prior"
    assert est.sample_size == 0


def test_estimate_kappa_from_surveys_with_data():
    # Direct condition: lower perceived freedom, higher interrogation
    rows_a = [
        {"impossibility": 4, "freedom": 3, "naturalness": 3, "surprise": 4},
        {"impossibility": 3, "freedom": 2, "naturalness": 4, "surprise": 3},
    ]
    # Mixed condition: higher perceived freedom, lower interrogation
    rows_b = [
        {"impossibility": 6, "freedom": 6, "naturalness": 6, "surprise": 6},
        {"impossibility": 5, "freedom": 5, "naturalness": 5, "surprise": 5},
    ]
    est = estimate_kappa_from_surveys(rows_a, rows_b, reps=500)
    assert 0.0 <= est.point_estimate <= 1.0
    assert est.ci_lower <= est.ci_upper
    assert est.sample_size == 4
    assert est.method == "likert_interrogation_ratio"


def test_compute_breakeven_kappa():
    # Example values from animal_guess:
    # auto: acc=0.891, direct=0.889, direct_bits_auto=9.89,
    # direct_bits_direct=11.10, covert_turns=1.0
    kappa_star = compute_breakeven_kappa(
        acc_auto=0.891,
        acc_direct=0.889,
        direct_bits_auto=9.89,
        direct_bits_direct=11.10,
        covert_turns_auto=1.0,
    )
    assert kappa_star is not None
    assert 0.20 <= kappa_star <= 0.80


def test_bootstrap_ci_edge_cases():
    # Empty list
    low, high = bootstrap_ci([])
    assert math.isnan(low) and math.isnan(high)

    # Reps <= 0
    low, high = bootstrap_ci([1.0, 2.0], reps=0)
    assert math.isnan(low) and math.isnan(high)

    # Single value
    low, high = bootstrap_ci([5.0])
    assert low == 5.0 and high == 5.0

    # Values with None / NaN filtered out
    low, high = bootstrap_ci([4.0, float("nan"), 6.0], reps=500, seed=42)
    assert 4.0 <= low <= high <= 6.0


def test_estimate_kappa_from_surveys_partial_empty_and_docs():
    # A non-empty, B empty
    est_a = estimate_kappa_from_surveys([{"freedom": 4}], [])
    assert est_a.point_estimate == 0.25
    assert est_a.method == "uncalibrated_prior"
    assert est_a.sample_size == 1
    assert est_a.sample_size_a == 1
    assert est_a.sample_size_b == 0
    assert math.isnan(est_a.ci_lower)

    # A empty, B non-empty
    est_b = estimate_kappa_from_surveys([], [{"freedom": 4}, {"freedom": 5}])
    assert est_b.sample_size == 2
    assert est_b.sample_size_a == 0
    assert est_b.sample_size_b == 2


def test_estimate_kappa_from_surveys_malformed_and_defaults():
    # Rows with missing, None, string, and out-of-range items
    rows_a = [
        {},
        {"freedom": None, "naturalness": "not_a_number"},
        {"freedom": -10, "naturalness": 100},  # clamped to [1, 7]
    ]
    rows_b = [
        {"freedom": 6, "naturalness": 6},
        "not_a_dict",  # handled safely
    ]
    est = estimate_kappa_from_surveys(rows_a, rows_b, reps=500)
    assert 0.0 <= est.point_estimate <= 1.0
    assert est.ci_lower <= est.ci_upper
    assert est.sample_size == 5


def test_compute_breakeven_kappa_edge_cases():
    # Zero covert turns: cannot break even through covert visibility weight
    assert compute_breakeven_kappa(0.9, 0.9, 10.0, 10.0, 0.0) is None
    assert compute_breakeven_kappa(0.9, 0.9, 10.0, 10.0, -1.0) is None

    # Zero or negative direct accuracy: invalid baseline
    assert compute_breakeven_kappa(0.9, 0.0, 10.0, 10.0, 1.0) is None
    assert compute_breakeven_kappa(0.9, -0.5, 10.0, 10.0, 1.0) is None

    # Zero or negative auto accuracy: cannot break even with positive direct accuracy
    assert compute_breakeven_kappa(0.0, 0.9, 10.0, 10.0, 1.0) is None
    assert compute_breakeven_kappa(-0.5, 0.9, 10.0, 10.0, 1.0) is None

    # NaN / Inf inputs
    assert compute_breakeven_kappa(float("nan"), 0.9, 10.0, 10.0, 1.0) is None
    assert compute_breakeven_kappa(0.9, float("inf"), 10.0, 10.0, 1.0) is None


def test_compute_breakeven_kappa_mathematical_identity():
    # At kappa = kappa*, M(auto) must equal M(direct) exactly
    cases = [
        (0.891, 0.889, 10.5355, 11.1134, 1.0),
        (0.911, 0.905, 7.7170, 8.3492, 1.0),
        (0.884, 0.876, 10.4229, 11.0108, 1.0),
        (0.973, 0.982, 2.8020, 3.3740, 1.0),
    ]
    for acc_auto, acc_dir, vis_auto, vis_dir, covert_turns in cases:
        k_star = compute_breakeven_kappa(acc_auto, acc_dir, vis_auto, vis_dir, covert_turns)
        assert k_star is not None
        m_direct = acc_dir / (1.0 + vis_dir)
        m_auto = acc_auto / (1.0 + vis_auto + k_star * covert_turns * math.log2(3.0))
        assert abs(m_auto - m_direct) < 1e-4
