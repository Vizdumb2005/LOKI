"""Method Selection Layer tests (ROADMAP Phase 2).

The policy chooses the interaction only — these tests pin its heuristics:
credible assertions, miss backoff, turn-budget reserve, and opt-outs.
"""

from __future__ import annotations

import pytest

from services.effects.models import Termination
from services.policy.method_selection import (
    FishingState,
    MethodPolicyParams,
    answer_masses,
    select_turn,
)


def _uniform(effect) -> dict[str, float]:
    n = len(effect.hypotheses)
    return {h: 1.0 / n for h in effect.hypotheses}


def test_first_card_plan_is_a_covert_read(card_effect):
    plan = select_turn(card_effect, _uniform(card_effect), set(), FishingState())
    assert plan is not None
    assert plan.mode == "covert"
    assert plan.reason == "credible_assertion"
    # Credible AND most informative: among questions whose top answer carries
    # at least fish_floor mass, color splits the deck cleanest (1 bit) at the
    # uniform prior. The assertion names its top-mass option.
    assert plan.question_id == "q_color"
    assert plan.asserted_answer_id == "red"
    assert plan.info_gain_bits > 0.75


def test_answer_masses_partition_the_posterior(card_effect):
    posterior = _uniform(card_effect)
    color = answer_masses(card_effect, posterior, card_effect.questions[-1])
    assert color["red"] == pytest.approx(0.5)
    high = answer_masses(card_effect, posterior, card_effect.questions[3])
    assert high["low"] == pytest.approx(44 / 52)


def test_no_informative_question_returns_none(card_effect):
    asked = {q.id for q in card_effect.questions}
    plan = select_turn(card_effect, _uniform(card_effect), asked, FishingState())
    assert plan is None


def test_backoff_after_misses_then_cooldown(card_effect):
    posterior = _uniform(card_effect)
    state = FishingState(consecutive_misses=2)
    plan = select_turn(card_effect, posterior, set(), state)
    assert plan.mode == "direct" and plan.reason == "backoff_after_misses"
    assert state.cooldown_turns == 1
    assert state.consecutive_misses == 0  # the backoff clears the miss streak
    cooled = select_turn(card_effect, posterior, set(), state)
    assert cooled.mode == "direct" and cooled.reason == "cooldown_after_misses"
    assert state.cooldown_turns == 0
    recovered = select_turn(card_effect, posterior, set(), state)
    assert recovered.mode == "covert"  # cleared state, credible reads remain


def test_budget_reserve_forces_direct(number_effect):
    params = MethodPolicyParams()
    cramped = number_effect.model_copy(
        update={
            "termination": Termination(
                entropy_threshold_bits=0.25, max_turns=len(number_effect.questions)
            )
        }
    )
    asked = {q.id for q in cramped.questions[:-2]}
    assert cramped.termination.max_turns - len(asked) <= params.reserve_turns
    plan = select_turn(cramped, _uniform(number_effect), asked, FishingState(), params)
    assert plan is not None
    assert plan.mode == "direct" and plan.reason == "budget_reserve"


def test_fishing_opt_out_respected(card_effect):
    effect = card_effect.model_copy(
        update={
            "questions": [
                q.model_copy(update={"fishing": False}) if q.id == "q_high_card" else q
                for q in card_effect.questions
            ]
        }
    )
    plan = select_turn(effect, _uniform(card_effect), set(), FishingState())
    assert plan.mode == "covert"
    assert plan.question_id != "q_high_card"  # next-most-credible assertion


def test_direct_only_effect_never_fishes(card_effect):
    from tests.conftest import direct_only

    effect = direct_only(card_effect)
    plan = select_turn(effect, _uniform(card_effect), set(), FishingState())
    assert plan.mode == "direct"
    assert plan.reason == "max_expected_information_gain"


def test_select_turn_never_repeats_a_question(card_effect):
    posterior = _uniform(card_effect)
    state = FishingState()
    asked: set[str] = set()
    for _ in range(len(card_effect.questions)):
        plan = select_turn(card_effect, posterior, asked, state)
        assert plan is not None
        assert plan.question_id not in asked
        asked.add(plan.question_id)
    assert select_turn(card_effect, posterior, asked, state) is None
