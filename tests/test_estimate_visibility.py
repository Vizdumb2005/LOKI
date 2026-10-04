"""Tests for empirical visibility estimator (Job a)."""

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
    # auto: acc=0.891, direct=0.889, direct_bits_auto=9.89, direct_bits_direct=11.10, covert_turns=1.0
    kappa_star = compute_breakeven_kappa(
        acc_auto=0.891,
        acc_direct=0.889,
        direct_bits_auto=9.89,
        direct_bits_direct=11.10,
        covert_turns_auto=1.0,
    )
    assert kappa_star is not None
    assert 0.20 <= kappa_star <= 0.80
