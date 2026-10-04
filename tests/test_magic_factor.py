"""Tests for the Magic Factor evaluation harness (ROADMAP Phase 2 protocol)."""

from __future__ import annotations

import random
from pathlib import Path

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
