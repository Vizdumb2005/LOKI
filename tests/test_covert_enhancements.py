"""Tests for enhanced covert fishing policy and multi-covert allowance."""

from pathlib import Path

from services.effects.loader import load_effects
from services.policy.method_selection import (
    FishingState,
    MethodPolicyParams,
    covert_candidate,
    select_turn,
)


def test_multi_covert_turns_allowance():
    effects = load_effects(Path("configs/effects"))
    effect = effects["animal_guess"]

    # Posterior with a credible candidate on a fishing-enabled question
    posterior = {h: 0.01 for h in effect.hypotheses}
    # Raise dog and cat to create credible candidate mass for mammals/pets
    posterior["dog"] = 0.50
    posterior["cat"] = 0.40

    # Total mass sum normalization
    total = sum(posterior.values())
    posterior = {h: p / total for h, p in posterior.items()}

    state = FishingState(covert_turns=1)  # 1 turn already spent
    # With max_covert_turns=3 and covert_ratio=0.3, effective max covert turns is >= 3
    params = MethodPolicyParams(max_covert_turns=3, covert_ratio=0.3)

    plan = select_turn(effect, posterior, set(), state, params)
    assert plan is not None
    assert plan.mode == "covert"
    assert plan.asserted_answer_id is not None


def test_uninterviewed_covert_candidate_selection():
    effects = load_effects(Path("configs/effects"))
    effect = effects["card_prediction"]

    posterior = {h: 1.0 / len(effect.hypotheses) for h in effect.hypotheses}
    # Concentrate mass on red cards
    for h in effect.hypotheses:
        if h.endswith("H") or h.endswith("D"):
            posterior[h] = 0.03

    total = sum(posterior.values())
    posterior = {h: p / total for h, p in posterior.items()}

    asked = set()  # No questions asked yet (un-interviewed)
    candidate = covert_candidate(effect, posterior, asked)
    assert candidate is not None
    assert candidate.question_id not in asked
    assert candidate.asserted_answer_id is not None
