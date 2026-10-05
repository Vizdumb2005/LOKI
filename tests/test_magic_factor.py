"""Tests for the Magic Factor evaluation harness (ROADMAP Phase 2 protocol)."""

from __future__ import annotations

import json
import random
from pathlib import Path

from experiments.estimate_visibility import compute_breakeven_kappa
from experiments.run_magic_factor_eval import KAPPA_SWEEP, evaluate_magic_factor
from services.effects.loader import load_effects

REPO_ROOT = Path(__file__).resolve().parents[1]
EFFECTS_DIR = REPO_ROOT / "configs" / "effects"


def test_magic_factor_eval_basic():
    registry = load_effects(EFFECTS_DIR)
    effect = registry["sigil_forced_choice"]
    rng = random.Random(42)

    res = evaluate_magic_factor(
        effect,
        sessions=20,
        reliability=1.0,
        rng=rng,
        gaze_prob=0.5,
    )

    assert res["effect_id"] == "sigil_forced_choice"
    assert res["top1_accuracy"] >= 0.90
    assert "magic_factor_score" in res
    assert res["avg_visible_bits_used"] > 0
    assert [a["kappa"] for a in res["kappa_sweep"]] == list(KAPPA_SWEEP)


def test_kappa_sweep_monotone_in_visible_bits():
    """Raising the visibility weight must raise visible bits and shrink the
    mystery gap — the accounting is recomputed, not re-simulated."""
    registry = load_effects(EFFECTS_DIR)
    effect = registry["card_prediction"]
    rng = random.Random(7)

    res = evaluate_magic_factor(effect, sessions=20, reliability=1.0, rng=rng)
    sweep = res["kappa_sweep"]
    visibles = [a["avg_visible_bits"] for a in sweep]
    gaps = [a["avg_information_mystery_gap_bits"] for a in sweep]
    assert visibles == sorted(visibles)
    assert gaps == sorted(gaps, reverse=True)
    # kappa=0 attributes nothing visible to covert turns, so with any covert
    # traffic the gap must beat the fully-visible bound.
    assert gaps[0] > gaps[-1]


def test_direct_policy_uses_no_covert_turns():
    registry = load_effects(EFFECTS_DIR)
    effect = registry["card_prediction"].without_fishing()
    rng = random.Random(42)

    res = evaluate_magic_factor(effect, sessions=10, reliability=1.0, rng=rng)

    assert res["avg_covert_turns"] == 0.0
    assert res["fishing_affirmation_rate"] == 0.0


def test_evaluate_magic_factor_breakeven_inlining():
    registry = load_effects(EFFECTS_DIR)
    effect = registry["card_prediction"]
    rng_auto = random.Random(42)
    rng_direct = random.Random(42)

    # Direct baseline run
    res_direct = evaluate_magic_factor(
        effect.without_fishing(),
        sessions=20,
        reliability=1.0,
        rng=rng_direct,
    )
    assert res_direct["breakeven_kappa"] is None

    # Auto run with baseline_direct provided
    res_auto = evaluate_magic_factor(
        effect,
        sessions=20,
        reliability=1.0,
        rng=rng_auto,
        baseline_direct=res_direct,
    )
    assert "breakeven_kappa" in res_auto
    assert isinstance(res_auto["breakeven_kappa"], float)
    assert -1.0 <= res_auto["breakeven_kappa"] <= 1.5


def test_magic_factor_eval_cli_runs_and_inlines_breakeven(monkeypatch, capsys):
    from experiments.run_magic_factor_eval import main

    monkeypatch.setattr(
        "sys.argv",
        [
            "run_magic_factor_eval",
            "--sessions",
            "5",
            "--seed",
            "42",
            "--effect",
            "sigil_forced_choice",
        ],
    )
    exit_code = main()
    assert exit_code == 0
    captured = capsys.readouterr().out
    assert "LOKI Magic Factor Evaluation" in captured
    assert "Empirical breakeven κ* (auto policy vs direct baseline):" in captured
    assert "sigil_forced_choice" in captured
    assert "κ sensitivity — visible-bit accounting for covert turns:" in captured


def test_reproducible_precomputed_mf_1000_sweep_and_breakeven():
    auto_file = REPO_ROOT / "experiments" / "outputs" / "mf_auto_1000.json"
    direct_file = REPO_ROOT / "experiments" / "outputs" / "mf_direct_1000.json"
    assert auto_file.is_file() and direct_file.is_file()

    auto_data = json.loads(auto_file.read_text(encoding="utf-8"))
    direct_data = json.loads(direct_file.read_text(encoding="utf-8"))

    expected_effects = {
        "animal_guess",
        "card_prediction",
        "number_prediction",
        "sigil_forced_choice",
    }
    assert {e["effect_id"] for e in auto_data} == expected_effects
    assert {e["effect_id"] for e in direct_data} == expected_effects

    direct_by_id = {e["effect_id"]: e for e in direct_data}

    for a in auto_data:
        eid = a["effect_id"]
        d = direct_by_id[eid]
        assert a["sessions"] == 1000
        assert d["sessions"] == 1000
        assert d["avg_covert_turns"] == 0.0

        # Verify 5-point parameter sweep
        sweep_kappas = [s["kappa"] for s in a["kappa_sweep"]]
        assert sweep_kappas == [0.0, 0.25, 0.5, 0.75, 1.0]

        # Calculate breakeven kappa*
        vis_auto_dir = next(s["avg_visible_bits"] for s in a["kappa_sweep"] if s["kappa"] == 0.0)
        vis_dir_direct = d["avg_visible_bits_used"]
        k_star = compute_breakeven_kappa(
            a["top1_accuracy"],
            d["top1_accuracy"],
            vis_auto_dir,
            vis_dir_direct,
            a["avg_covert_turns"],
        )
        assert k_star is not None
        # Must fall within the measured breakeven range [0.30, 0.45] per Directive §8 / Finding 3
        assert 0.30 <= k_star <= 0.45, f"{eid} kappa*={k_star} out of expected [0.30, 0.45]"

