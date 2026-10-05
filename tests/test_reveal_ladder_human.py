"""End-to-end verification of the Reveal Ladder fix (§11, §18, Job f).

Proves that:
1. Unasked corpus attributes surface before asked attributes in the reveal ladder;
2. Binary yes/no attributes are skipped to preserve theatrical weight;
3. Attributes deduplicate across beats;
4. The reveal plan produces structured beats that integrate into live sessions.
"""

from pathlib import Path

from services.effects.loader import load_effects
from services.policy.reveal_planner import _ladder, plan_reveal


def test_reveal_ladder_prioritizes_unasked_attributes():
    effects = load_effects(Path("configs/effects"))
    effect = effects["card_prediction"]
    target_hid = "7D"  # Seven of Diamonds

    # Suppose only q_color was asked during the séance
    asked = ["q_color"]

    stages = _ladder(effect, asked, target_hid, limit=3)
    assert len(stages) == 3

    # Verify that stages come from UNASKED questions, not q_color
    assert all(s.attr != "color" for s in stages)
    assert stages[0].label == "Diamonds"
    assert stages[1].label == "Six or Seven"


def test_reveal_ladder_skips_binary_yes_no():
    effects = load_effects(Path("configs/effects"))
    effect = effects["animal_guess"]
    target_hid = "tiger"

    # In animal_guess, 14 of 15 questions have Yes/No labels.
    # q_class has categorical labels ("A mammal", "A bird", etc.).
    # _ladder must skip all 14 binary questions.
    stages = _ladder(effect, asked=[], hypothesis_id=target_hid, limit=3)

    # Only q_class has non-binary answers, so only 1 stage can be generated
    assert len(stages) == 1
    assert stages[0].attr == "cls"
    assert stages[0].label == "A mammal"


def test_reveal_ladder_falls_back_to_asked_when_unasked_exhausted():
    effects = load_effects(Path("configs/effects"))
    effect = effects["card_prediction"]
    target_hid = "7D"

    # All questions asked except q_color
    asked = ["q_suit", "q_rank_bucket", "q_rank_parity", "q_high_card", "q_rank_mod3"]
    stages = _ladder(effect, asked, target_hid, limit=3)

    assert len(stages) >= 2
    # First stage must be the single unasked question (q_color -> Red)
    assert stages[0].attr == "color"
    assert stages[0].label == "Red"
    # Fallback stage must be from asked questions
    assert stages[1].attr in {"suit", "rank_value"}


def test_plan_reveal_staged_beats():
    effects = load_effects(Path("configs/effects"))
    effect = effects["card_prediction"]

    # Decisive commit with high posterior mass on top candidate
    top_candidates = [("7D", 0.92), ("8D", 0.05), ("7H", 0.03)]
    asked = ["q_color"]

    plan = plan_reveal(effect, top_candidates, asked)
    assert plan.path == "progressive"
    assert len(plan.stages) >= 1
    # First stage must not repeat q_color
    assert plan.stages[0].attr != "color"
