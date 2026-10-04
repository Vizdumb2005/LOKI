"""ROADMAP Phase 6 tests: profiles, bandit, selector injection, A/B conditions,
survey storage (docs/rl-policy.md, docs/human-trials.md)."""

from __future__ import annotations

import random

import pytest

from services.effects.engine import EffectSession, Phase
from services.policy.method_selection import FishingState, TurnPlan
from simulator.bandit import BanditTurnSelector, TabularBandit
from simulator.profiles import PROFILES, sample_profile
from tests.conftest import truthful_response

# -- profiles ------------------------------------------------------------------


def test_profile_registry_covers_the_archetypes():
    assert {"balanced", "impulsive", "cautious", "suggestible", "evasive", "adversarial"} == set(
        PROFILES
    )
    for profile in PROFILES.values():
        if profile.reliability is not None:
            assert 0.05 <= profile.reliability <= 1.0
        assert 0.0 <= profile.force_susceptibility <= 1.0
        assert 0.0 <= profile.fishing_evasiveness <= 1.0


def test_sample_profile_draws_from_the_registry():
    rng = random.Random(0)
    drawn = {sample_profile(rng).name for _ in range(200)}
    assert drawn == set(PROFILES)


# -- bandit --------------------------------------------------------------------


def test_bandit_select_respects_the_action_mask():
    bandit = TabularBandit(seed=1)
    for _ in range(50):
        assert bandit.select((0, 2), ["direct", "forced"]) in ("direct", "forced")
    with pytest.raises(ValueError):
        bandit.select((0, 2), [])


def test_bandit_learning_shifts_greedy_choice():
    bandit = TabularBandit(seed=2, epsilon=0.0)
    # reward "covert" handsomely in one cell, punish it in another
    for _ in range(30):
        bandit.update((0, 2), "covert", 0.9)
        bandit.update((2, 0), "covert", -0.9)
    assert bandit.greedy_action((0, 2)) == "covert"
    assert bandit.greedy_action((2, 0)) != "covert"


def test_bandit_serialization_round_trip():
    bandit = TabularBandit(seed=3, epsilon=0.2)
    bandit.update((1, 1), "forced", 0.4)
    clone = TabularBandit.from_dict(bandit.to_dict())
    assert clone.to_dict() == bandit.to_dict()
    assert clone.epsilon == bandit.epsilon


def test_bandit_selector_produces_valid_plans(card_effect):
    agent = TabularBandit(seed=4, epsilon=0.5)
    selector = BanditTurnSelector(agent)
    state = FishingState()
    asked: set[str] = set()
    posterior = {h: 1.0 / 52 for h in card_effect.hypotheses}
    for _ in range(len(card_effect.questions)):
        plan = selector(card_effect, posterior, asked, state)
        assert plan is not None
        assert plan.mode in ("direct", "covert")
        assert plan.question_id not in asked
        assert plan.reason.startswith("bandit:")
        asked.add(plan.question_id)
        if plan.mode == "covert":
            state.covert_turns += 1  # the engine would do this


def test_bandit_selector_masks_the_covert_ration(card_effect):
    from tests.conftest import direct_only

    agent = TabularBandit(seed=6, epsilon=0.0)
    # optimistic init makes "covert" attractive — the mask must hold anyway
    agent._values[(0, 1)] = {"covert": 99.0}
    selector = BanditTurnSelector(agent)
    state = FishingState(covert_turns=1)  # ration spent
    effect = direct_only(card_effect)
    plan = selector(effect, {h: 1.0 / 52 for h in effect.hypotheses}, set(), state)
    assert plan is not None and plan.mode == "direct"


def test_engine_uses_the_injected_selector(card_effect, renderer):
    def stubborn_selector(effect, posterior, asked, state) -> TurnPlan | None:
        question = next(q for q in effect.questions if q.id == "q_color" and q.id not in asked)
        if question is None:
            return None
        return TurnPlan("q_color", "direct", None, 0.5, "stubborn")

    session = EffectSession(card_effect, renderer, selector=stubborn_selector)
    assert session.current_question.id == "q_color"
    assert session.current_mode == "direct"
    decision = next(e for e in session.history if e.type.value == "policy.decision")
    assert decision.payload["reason"] == "stubborn"


# -- A/B conditions -------------------------------------------------------------


def test_condition_a_suppresses_the_performance_layer(card_effect, renderer):
    session = EffectSession(card_effect, renderer, performance=False, condition="a")
    assert session.condition == "a"
    # no choice-architecture emphasis, ever
    assert session.current_force_target is None
    # drive to the reveal: the path is always plain
    while session.phase is Phase.ACTIVE:
        truthful_response(session, card_effect, "7D")
    assert session.reveal_plan is not None
    assert session.reveal_plan.path == "plain"
    assert session.reveal_plan.stages == ()
    assert session.reveal_stage_messages == []


def test_condition_b_keeps_the_performance_layer(card_effect, renderer):
    session = EffectSession(card_effect, renderer, condition="b")
    assert session.condition == "b"
    # the default engine: the first card turn is a covert read
    assert session.current_mode == "covert"


# -- survey storage --------------------------------------------------------------


def test_survey_round_trip_and_cascade(tmp_path, card_effect, renderer):
    from services.api.archive import SessionArchive

    archive = SessionArchive(tmp_path / "s" / "sessions.db")
    session = EffectSession(card_effect, renderer)
    while session.phase is Phase.ACTIVE:
        truthful_response(session, card_effect, "7D")
    session.report_outcome(correct=True)
    archive.save(session)

    answers = {
        "impossibility": 6,
        "freedom": 5,
        "naturalness": 7,
        "surprise": 4,
        "willing_repeat": True,
    }
    stored = archive.save_survey(
        session.session_id, "b", answers, created_at="2026-10-04T00:00:00Z"
    )
    assert stored["condition"] == "b"
    rows = archive.survey_rows()
    assert len(rows) == 1
    assert rows[0]["impossibility"] == 6
    assert rows[0]["effect_id"] == "card_prediction"  # joined with the outcome

    # the deletion control removes the survey with the session
    assert archive.delete(session.session_id) is True
    assert archive.survey_rows() == []
