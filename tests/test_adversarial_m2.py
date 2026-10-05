"""Adversarial stress and boundary tests for Milestone 2 changes.

Empirically challenges:
1. `compute_breakeven_kappa`:
   - Extreme inputs: zero covert turns, negative/zero accuracy, infinity/NaN,
     massive/tiny visible bits.
   - Mathematical identity assertion: M(auto, κ*) == M(direct).
   - Rejection of non-positive auto prediction accuracy (acc_auto <= 0).
2. `estimate_kappa_from_surveys`:
   - Empty lists, partial empty lists, and sample size accounting.
   - Asymmetric/unequal cohort lengths.
   - Malformed Likert inputs: strings, non-numeric, out-of-range clamping,
     None, missing keys, non-dict rows, NaN/Inf.
   - Bootstrap confidence interval bounds (ci_lower <= point_estimate <= ci_upper or NaN fallback).
3. CLI invocation of `experiments/run_magic_factor_eval.py`:
   - Custom flags, seeds, policies (auto vs direct), baseline inlining, and error handling.
"""

from __future__ import annotations

import math
import random
import subprocess
import sys
from pathlib import Path

import pytest

from experiments.estimate_visibility import (
    compute_breakeven_kappa,
    estimate_kappa_from_surveys,
)

REPO_ROOT = Path(__file__).resolve().parents[1]


# ==============================================================================
# 1. compute_breakeven_kappa Stress Tests & Mathematical Identity
# ==============================================================================


def test_compute_breakeven_kappa_rejects_nonpositive_acc_direct():
    """Direct accuracy <= 0 must be rejected as an invalid baseline."""
    assert compute_breakeven_kappa(0.9, 0.0, 10.0, 10.0, 1.0) is None
    assert compute_breakeven_kappa(0.9, -0.5, 10.0, 10.0, 1.0) is None


def test_compute_breakeven_kappa_rejects_nonpositive_covert_turns():
    """Covert turns <= 0 must be rejected (no covert turns to adjust)."""
    assert compute_breakeven_kappa(0.9, 0.9, 10.0, 10.0, 0.0) is None
    assert compute_breakeven_kappa(0.9, 0.9, 10.0, 10.0, -1.0) is None


def test_compute_breakeven_kappa_rejects_nan_and_inf():
    """Any NaN or Inf argument must return None."""
    for bad in (float("nan"), float("inf"), float("-inf")):
        assert compute_breakeven_kappa(bad, 0.9, 10.0, 10.0, 1.0) is None
        assert compute_breakeven_kappa(0.9, bad, 10.0, 10.0, 1.0) is None
        assert compute_breakeven_kappa(0.9, 0.9, bad, 10.0, 1.0) is None
        assert compute_breakeven_kappa(0.9, 0.9, 10.0, bad, 1.0) is None
        assert compute_breakeven_kappa(0.9, 0.9, 10.0, 10.0, bad) is None


def test_compute_breakeven_kappa_rejects_non_numeric():
    """Non-numeric arguments must return None safely."""
    for bad in (None, "0.9", [1.0], {"val": 1.0}):
        assert compute_breakeven_kappa(bad, 0.9, 10.0, 10.0, 1.0) is None
        assert compute_breakeven_kappa(0.9, bad, 10.0, 10.0, 1.0) is None
        assert compute_breakeven_kappa(0.9, 0.9, bad, 10.0, 1.0) is None
        assert compute_breakeven_kappa(0.9, 0.9, 10.0, bad, 1.0) is None
        assert compute_breakeven_kappa(0.9, 0.9, 10.0, 10.0, bad) is None


def test_compute_breakeven_kappa_massive_and_tiny_visible_bits():
    """Verify extreme magnitudes for visible bits do not cause overflow or corrupt identity."""
    cases = [
        (0.9, 0.9, 1e-9, 1e-9, 1.0),
        (0.9, 0.9, 0.0, 0.0, 1.0),
        (0.9, 0.9, 1e6, 1e6, 1.0),
        (0.9, 0.9, 1e9, 1e9, 1.0),
        (0.95, 0.90, 1e6, 1e3, 2.0),
    ]
    for acc_auto, acc_dir, vis_auto, vis_dir, covert_t in cases:
        k_star = compute_breakeven_kappa(acc_auto, acc_dir, vis_auto, vis_dir, covert_t)
        assert k_star is not None
        m_dir = acc_dir / (1.0 + vis_dir)
        denom_auto = 1.0 + vis_auto + k_star * covert_t * math.log2(3.0)
        assert denom_auto > 0
        m_auto = acc_auto / denom_auto
        assert abs(m_auto - m_dir) < 1e-4


def test_compute_breakeven_kappa_mathematical_identity_grid():
    """Assert mathematical identity M(auto, κ*) == M(direct) across a parameter grid."""
    acc_autos = [0.2, 0.6, 0.85, 0.95, 1.0]
    acc_dirs = [0.2, 0.6, 0.85, 0.95, 1.0]
    vis_autos = [2.0, 5.0, 10.0]
    vis_dirs = [2.0, 5.0, 10.0]
    covert_ts = [0.5, 1.0, 2.5]

    for acc_auto in acc_autos:
        for acc_dir in acc_dirs:
            for vis_auto in vis_autos:
                for vis_dir in vis_dirs:
                    for covert_t in covert_ts:
                        k_star = compute_breakeven_kappa(
                            acc_auto, acc_dir, vis_auto, vis_dir, covert_t
                        )
                        assert k_star is not None
                        m_dir = acc_dir / (1.0 + vis_dir)
                        denom_auto = 1.0 + vis_auto + k_star * covert_t * math.log2(3.0)
                        assert denom_auto > 0
                        m_auto = acc_auto / denom_auto
                        assert abs(m_auto - m_dir) < 1e-4


def test_compute_breakeven_kappa_mathematical_identity_fails_at_zero_acc():
    """When acc_auto == 0, M(auto) = 0.0 cannot break even with M(direct) > 0.
    compute_breakeven_kappa must return None to avoid mathematical identity violation.
    """
    assert compute_breakeven_kappa(0.0, 0.9, 10.0, 10.0, 1.0) is None


def test_compute_breakeven_kappa_should_reject_nonpositive_acc_auto():
    """Verify compute_breakeven_kappa rejects non-positive acc_auto.
    At acc_auto <= 0, M(auto) is 0 or negative and cannot break even with M(direct) > 0.
    """
    assert compute_breakeven_kappa(0.0, 0.9, 10.0, 10.0, 1.0) is None
    assert compute_breakeven_kappa(-0.5, 0.9, 10.0, 10.0, 1.0) is None


# ==============================================================================
# 2. estimate_kappa_from_surveys Stress Tests
# ==============================================================================


def test_estimate_kappa_from_surveys_empty_and_partial_cohorts():
    """Verify empty and partial cohorts return documented sample sizes and uncalibrated prior."""
    # Both empty
    e_empty = estimate_kappa_from_surveys([], [])
    assert e_empty.point_estimate == 0.25
    assert math.isnan(e_empty.ci_lower) and math.isnan(e_empty.ci_upper)
    assert e_empty.method == "uncalibrated_prior"
    assert e_empty.sample_size == 0
    assert e_empty.sample_size_a == 0
    assert e_empty.sample_size_b == 0

    # A non-empty, B empty
    e_a_only = estimate_kappa_from_surveys([{"freedom": 5, "naturalness": 5}], [])
    assert e_a_only.point_estimate == 0.25
    assert math.isnan(e_a_only.ci_lower)
    assert e_a_only.sample_size == 1
    assert e_a_only.sample_size_a == 1
    assert e_a_only.sample_size_b == 0

    # A empty, B non-empty
    e_b_only = estimate_kappa_from_surveys([], [{"freedom": 5, "naturalness": 5}] * 3)
    assert e_b_only.point_estimate == 0.25
    assert math.isnan(e_b_only.ci_lower)
    assert e_b_only.sample_size == 3
    assert e_b_only.sample_size_a == 0
    assert e_b_only.sample_size_b == 3


def test_estimate_kappa_from_surveys_unequal_cohort_lengths():
    """Verify stability under highly unbalanced cohort lengths (e.g. 1 vs 50)."""
    # 1 in A vs 50 in B
    e_1_50 = estimate_kappa_from_surveys(
        [{"freedom": 2, "naturalness": 3}],
        [{"freedom": 6, "naturalness": 6}] * 50,
        reps=500,
    )
    assert 0.0 <= e_1_50.point_estimate <= 1.0
    assert e_1_50.ci_lower <= e_1_50.point_estimate <= e_1_50.ci_upper
    assert e_1_50.sample_size_a == 1
    assert e_1_50.sample_size_b == 50
    assert e_1_50.sample_size == 51

    # 50 in A vs 1 in B
    e_50_1 = estimate_kappa_from_surveys(
        [{"freedom": 2, "naturalness": 3}] * 50,
        [{"freedom": 6, "naturalness": 6}],
        reps=500,
    )
    assert 0.0 <= e_50_1.point_estimate <= 1.0
    assert e_50_1.ci_lower <= e_50_1.point_estimate <= e_50_1.ci_upper
    assert e_50_1.sample_size_a == 50
    assert e_50_1.sample_size_b == 1
    assert e_50_1.sample_size == 51


def test_estimate_kappa_from_surveys_malformed_hostile_inputs():
    """Verify defensive handling of strings, None, out-of-range, NaN/Inf, and non-dict rows."""
    hostile_rows_a = [
        {"freedom": "5", "naturalness": "6"},  # numeric strings
        {"freedom": "high", "naturalness": "bad"},  # non-numeric strings
        {"freedom": 0, "naturalness": 10},  # out of [1, 7] range
        {"freedom": -999, "naturalness": 999},  # extreme out of range
        {"freedom": None, "naturalness": None},  # None values
        {"impossibility": 7},  # missing keys
        {},  # empty dict
        None,  # non-dict (None)
        "not_a_dict",  # non-dict (string)
        12345,  # non-dict (int)
        {"freedom": [1, 2], "naturalness": {"k": "v"}},  # nested unparseable
        {"freedom": float("nan"), "naturalness": float("inf")},  # NaN / Inf
        {"freedom": float("-inf"), "naturalness": 4.0},  # -Inf
    ]
    rows_b = [
        {"freedom": 6, "naturalness": 6},
        {"freedom": 5, "naturalness": 5},
    ]

    est = estimate_kappa_from_surveys(hostile_rows_a, rows_b, reps=500)
    assert 0.0 <= est.point_estimate <= 1.0
    assert est.ci_lower <= est.ci_upper
    assert est.sample_size == len(hostile_rows_a) + len(rows_b)
    assert est.sample_size_a == len(hostile_rows_a)
    assert est.sample_size_b == len(rows_b)
    assert est.method == "likert_interrogation_ratio"


def test_estimate_kappa_from_surveys_bootstrap_ci_coverage():
    """Monte Carlo stress test: verify ci_lower <= point_estimate <= ci_upper across 100 cohorts."""
    rng = random.Random(1337)
    for trial in range(100):
        na = rng.randint(2, 20)
        nb = rng.randint(2, 20)
        rows_a = [
            {"freedom": rng.uniform(1.0, 7.0), "naturalness": rng.uniform(1.0, 7.0)}
            for _ in range(na)
        ]
        rows_b = [
            {"freedom": rng.uniform(1.0, 7.0), "naturalness": rng.uniform(1.0, 7.0)}
            for _ in range(nb)
        ]
        est = estimate_kappa_from_surveys(rows_a, rows_b, reps=500, seed=trial)
        assert est.ci_lower <= est.point_estimate <= est.ci_upper, (
            f"Trial {trial} failed: ci_lower={est.ci_lower}, pt={est.point_estimate}, "
            f"ci_upper={est.ci_upper}"
        )


# ==============================================================================
# 3. CLI Invocation Stress Tests for run_magic_factor_eval.py
# ==============================================================================


@pytest.mark.parametrize("seed", [42, 1337, 9999])
def test_cli_invocation_custom_seeds_and_effects(seed: int):
    """Verify CLI runs cleanly with various seeds and single effect."""
    cmd = [
        sys.executable,
        "-m",
        "experiments.run_magic_factor_eval",
        "--sessions",
        "5",
        "--seed",
        str(seed),
        "--effect",
        "card_prediction",
    ]
    res = subprocess.run(
        cmd,
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=30,
    )
    assert res.returncode == 0, f"CLI failed with seed {seed}:\n{res.stderr}"
    assert "LOKI Magic Factor Evaluation" in res.stdout
    assert "Empirical breakeven κ* (auto policy vs direct baseline):" in res.stdout
    assert "card_prediction" in res.stdout


def test_cli_invocation_direct_policy():
    """Verify CLI runs cleanly under --policy direct and reports breakeven as N/A."""
    cmd = [
        sys.executable,
        "-m",
        "experiments.run_magic_factor_eval",
        "--sessions",
        "5",
        "--seed",
        "42",
        "--policy",
        "direct",
    ]
    res = subprocess.run(
        cmd,
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=30,
    )
    assert res.returncode == 0, f"CLI direct policy failed:\n{res.stderr}"
    assert "Empirical breakeven κ*: N/A" in res.stdout


def test_cli_invocation_with_baseline_json_and_output(tmp_path: Path):
    """Verify CLI accepts --baseline and writes results to --json."""
    baseline_path = REPO_ROOT / "experiments" / "outputs" / "mf_direct_1000.json"
    out_json = tmp_path / "cli_results.json"

    cmd = [
        sys.executable,
        "-m",
        "experiments.run_magic_factor_eval",
        "--sessions",
        "5",
        "--seed",
        "42",
        "--effect",
        "sigil_forced_choice",
        "--baseline",
        str(baseline_path),
        "--json",
        str(out_json),
    ]
    res = subprocess.run(
        cmd,
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=30,
    )
    assert res.returncode == 0, f"CLI failed:\n{res.stderr}"
    assert out_json.is_file()
    assert "sigil_forced_choice" in out_json.read_text(encoding="utf-8")


def test_cli_invocation_flags_combination():
    """Verify CLI handles complex flags (--no-fusion, --force-susceptibility, --kappa)."""
    cmd = [
        sys.executable,
        "-m",
        "experiments.run_magic_factor_eval",
        "--sessions",
        "5",
        "--seed",
        "42",
        "--effect",
        "animal_guess",
        "--no-fusion",
        "--force-susceptibility",
        "0.4",
        "--kappa",
        "0.5",
        "--gaze-prob",
        "0.8",
    ]
    res = subprocess.run(
        cmd,
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=30,
    )
    assert res.returncode == 0, f"CLI flag combination failed:\n{res.stderr}"
    assert "animal_guess" in res.stdout


def test_cli_invocation_invalid_effect_exits_nonzero():
    """Verify CLI exits with non-zero status when given an unknown effect id."""
    cmd = [
        sys.executable,
        "-m",
        "experiments.run_magic_factor_eval",
        "--effect",
        "completely_bogus_effect",
    ]
    res = subprocess.run(
        cmd,
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=30,
    )
    assert res.returncode != 0
    assert "unknown effect" in res.stderr
