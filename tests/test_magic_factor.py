"""Tests for the Magic Factor evaluation harness."""

from __future__ import annotations

import random
from pathlib import Path

from experiments.run_magic_factor_eval import evaluate_magic_factor
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
        covert_ratio=0.5,
    )

    assert res["effect_id"] == "sigil_forced_choice"
    assert res["top1_accuracy"] >= 0.90
    assert "magic_factor_score" in res
    assert res["avg_visible_bits_used"] > 0
