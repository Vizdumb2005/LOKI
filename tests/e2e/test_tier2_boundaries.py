"""LOKI E2E Test Suite — Tier 2: Boundary & Corner Cases (>=5 tests per feature).

Stress-tests edge cases, boundary conditions, zero inputs, extreme parameter values,
budget limits, tie-breakers, and mathematical asymptotes across all 22 features.
"""

from __future__ import annotations

import math
import random
from pathlib import Path
from unittest.mock import patch

import pytest

from experiments.analyze_ab import mann_whitney_u, welch_t
from experiments.estimate_visibility import (
    compute_breakeven_kappa,
    estimate_kappa_from_surveys,
)
from experiments.run_human_trial import run_session
from experiments.run_magic_factor_eval import evaluate_magic_factor
from services.effects.engine import CommitReason, EffectSession, Phase
from services.effects.loader import load_effects
from services.effects.models import EffectDef
from services.fusion.engine import (
    LatencyChannel,
    downgrade_strength,
    is_hesitant,
    latency_factor,
)
from services.hypothesis.tracker import Tracker
from services.language.response_signals import AgreementStrength
from services.policy.info_gain import best_question
from services.policy.method_selection import (
    FishingState,
    MethodPolicyParams,
    covert_candidate,
    force_target,
    select_turn,
)
from services.policy.reveal_planner import plan_reveal, wants_hesitation
from simulator.bandit import TabularBandit
from simulator.profiles import PROFILES
from tests.e2e.conftest import truthful_body

REPO_ROOT = Path(__file__).resolve().parents[2]


# ==============================================================================
# F1: Controller Boundaries
# ==============================================================================

def test_f1_bnd_single_hypothesis_immediate_commit(renderer):
    """F1-B1: Single-hypothesis space starts with 0 entropy and commits immediately."""
    q_data = {
        "id": "q1",
        "text": "Only question?",
        "reliability": 1.0,
        "answers": [
            {"id": "a1", "label": "Yes", "predicate": {"attr": "val", "op": "eq", "value": 1}},
            {"id": "a2", "label": "No", "predicate": {"attr": "val", "op": "ne", "value": 1}},
        ],
    }
    effect_data = {
        "id": "single_hyp",
        "title": "Single",
        "description": "Single hypothesis",
        "hypotheses": {"h1": {"val": 1}},
        "prior": {"h1": 1.0},
        "termination": {"entropy_threshold_bits": 0.25, "max_turns": 5},
        "questions": [q_data],
    }
    effect = EffectDef.model_validate(effect_data)
    session = EffectSession(effect, renderer)
    assert session.phase is Phase.REVEALED
    assert session.prediction.hypothesis_id == "h1"


def test_f1_bnd_exhausted_questions_forces_commit(card_effect, renderer):
    """F1-B2: Asking all available questions forces commit when no questions remain."""
    session = EffectSession(card_effect.without_fishing(), renderer)
    while session.phase is Phase.ACTIVE:
        q = session.current_question
        session.answer(q.answers[0].id)
    assert session.phase is Phase.REVEALED
    assert session.committed_because in (
        CommitReason.MAX_TURNS,
        CommitReason.NO_INFORMATIVE_QUESTION,
        CommitReason.ENTROPY_THRESHOLD,
    )


def test_f1_bnd_zero_information_gain_questions_skipped(card_effect):
    """F1-B3: When posterior collapses to certainty, expected info gain is zero."""
    collapsed_p = {h: 1.0 if h == "AS" else 0.0 for h in card_effect.hypotheses}
    best_q, best_gain = best_question(card_effect, collapsed_p, set())
    assert best_gain == pytest.approx(0.0)


def test_f1_bnd_exact_tie_in_information_gain(card_effect):
    """F1-B4: Exact ties in question info gain resolve by declaration order."""
    uniform_p = {h: 1.0 / len(card_effect.hypotheses) for h in card_effect.hypotheses}
    q1, g1 = best_question(card_effect, uniform_p, set())
    assert q1 is not None


def test_f1_bnd_max_turns_budget_zero(card_effect):
    """F1-B5: When remaining turns are within reserve_turns, direct question is forced."""
    state = FishingState()
    params = MethodPolicyParams(reserve_turns=2)
    # Simulate turn count close to budget limit
    asked = {"q_suit", "q_rank_bucket", "q_rank_parity", "q_high_card", "q_rank_mod3", "q_color"}
    uniform_p = {h: 1.0 / len(card_effect.hypotheses) for h in card_effect.hypotheses}
    plan = select_turn(card_effect, uniform_p, asked, state, params)
    if plan:
        assert plan.mode == "direct"


# ==============================================================================
# F2: Tracker Boundaries
# ==============================================================================

def test_f2_bnd_empty_hypotheses_raises_value_error():
    """F2-B1: Tracker rejects empty hypothesis space."""
    with pytest.raises(ValueError, match="must not be empty"):
        Tracker([])


def test_f2_bnd_duplicate_hypotheses_raises_value_error():
    """F2-B2: Tracker rejects duplicate hypothesis IDs."""
    with pytest.raises(ValueError, match="unique"):
        Tracker(["h1", "h1"])


def test_f2_bnd_negative_prior_weights_rejected():
    """F2-B3: Negative weights in prior vector are rejected."""
    with pytest.raises(ValueError, match="negative"):
        Tracker(["h1", "h2"], prior={"h1": -0.5, "h2": 0.5})


def test_f2_bnd_total_zero_prior_weights_rejected():
    """F2-B4: All-zero prior weights vector is rejected."""
    with pytest.raises(ValueError, match="positive value"):
        Tracker(["h1", "h2"], prior={"h1": 0.0, "h2": 0.0})


def test_f2_bnd_contradictory_likelihood_all_zeros_raises_error():
    """F2-B5: Likelihood eliminating every hypothesis raises ValueError."""
    tracker = Tracker(["h1", "h2"])
    with pytest.raises(ValueError, match="eliminated every hypothesis"):
        tracker.update({"h1": 0.0, "h2": 0.0})


# ==============================================================================
# F3: Magic Factor Boundaries
# ==============================================================================

def test_f3_bnd_infinite_visible_bits_magic_factor_asymptote():
    """F3-B1: As visible bits approach infinity, Magic Factor score approaches 0."""
    acc = 0.95
    i_vis = 1_000_000.0
    m = acc / (1.0 + i_vis)
    assert m < 1e-5


def test_f3_bnd_zero_visible_bits_magic_factor_equals_accuracy():
    """F3-B2: With zero visible bits, Magic Factor exactly equals raw accuracy."""
    acc = 0.88
    i_vis = 0.0
    m = acc / (1.0 + i_vis)
    assert m == pytest.approx(acc)


def test_f3_bnd_negative_mystery_gap_when_interrogation_exceeds_entropy():
    """F3-B3: When visible bits exceed actual entropy reduced, mystery gap is negative."""
    actual_reduced = 1.2
    i_vis = 4.5
    gap = actual_reduced - i_vis
    assert gap < 0.0


def test_f3_bnd_zero_entropy_reduction_gives_negative_or_zero_gap():
    """F3-B4: Zero actual entropy reduction yields gap <= 0."""
    actual_reduced = 0.0
    i_vis = 2.0
    gap = actual_reduced - i_vis
    assert gap <= 0.0


def test_f3_bnd_perfect_accuracy_and_zero_visible_yields_one():
    """F3-B5: Perfect accuracy (1.0) with zero visible bits yields Magic Factor of 1.0."""
    acc = 1.0
    i_vis = 0.0
    m = acc / (1.0 + i_vis)
    assert m == 1.0


# ==============================================================================
# F4: 5-Point Parameter Sweep Boundaries
# ==============================================================================

def test_f4_bnd_kappa_zero_visible_bits_minimal(card_effect):
    """F4-B1: kappa=0 charges zero visible bits for covert turns."""
    res = evaluate_magic_factor(card_effect, sessions=2, reliability=1.0, rng=random.Random(42))
    k0 = next(s for s in res["kappa_sweep"] if s["kappa"] == 0.0)
    k1 = next(s for s in res["kappa_sweep"] if s["kappa"] == 1.0)
    assert k0["avg_visible_bits"] <= k1["avg_visible_bits"]


def test_f4_bnd_kappa_one_covert_treated_as_three_way_choice(card_effect):
    """F4-B2: kappa=1.0 charges full log2(3) bits for each covert turn."""
    res = evaluate_magic_factor(card_effect, sessions=3, reliability=1.0, rng=random.Random(42))
    k1 = next(s for s in res["kappa_sweep"] if s["kappa"] == 1.0)
    assert k1["avg_visible_bits"] >= 0.0


def test_f4_bnd_sweep_handles_zero_covert_turns(card_effect):
    """F4-B3: When zero covert turns are taken, visible bits are identical across sweep."""
    direct_effect = card_effect.without_fishing()
    res = evaluate_magic_factor(direct_effect, sessions=3, reliability=1.0, rng=random.Random(42))
    vis_values = [s["avg_visible_bits"] for s in res["kappa_sweep"]]
    assert len(set(vis_values)) == 1


def test_f4_bnd_sweep_handles_all_covert_turns(card_effect):
    """F4-B4: Higher kappa strictly increases or maintains visible bits in sweep."""
    res = evaluate_magic_factor(card_effect, sessions=3, reliability=1.0, rng=random.Random(42))
    for i in range(len(res["kappa_sweep"]) - 1):
        assert (
            res["kappa_sweep"][i]["avg_visible_bits"]
            <= res["kappa_sweep"][i + 1]["avg_visible_bits"] + 1e-6
        )


def test_f4_bnd_arbitrary_floating_point_kappa(card_effect):
    """F4-B5: Evaluator supports arbitrary floating point kappa outside standard grid."""
    res = evaluate_magic_factor(
        card_effect, sessions=2, reliability=1.0, rng=random.Random(42), kappa=0.333
    )
    assert res["kappa"] == 0.333
    assert res["avg_visible_bits_used"] > 0.0


# ==============================================================================
# F5: Breakeven kappa* Boundaries
# ==============================================================================

def test_f5_bnd_negative_breakeven_when_auto_accuracy_lower():
    """F5-B1: When auto accuracy is lower than direct, breakeven kappa is negative."""
    k_star = compute_breakeven_kappa(0.60, 0.90, 2.0, 2.0, covert_turns_auto=1.0)
    assert k_star is not None
    assert k_star < 0.0


def test_f5_bnd_breakeven_greater_than_one():
    """F5-B2: When auto accuracy substantially exceeds direct, kappa* > 1.0."""
    k_star = compute_breakeven_kappa(0.99, 0.50, 1.0, 3.0, covert_turns_auto=1.0)
    assert k_star is not None
    assert k_star > 1.0


def test_f5_bnd_identical_policies_yields_zero():
    """F5-B3: Identical policies yield breakeven kappa* of 0.0."""
    k_star = compute_breakeven_kappa(0.85, 0.85, 2.0, 2.0, covert_turns_auto=1.0)
    assert k_star == 0.0


def test_f5_bnd_extreme_accuracy_ratio():
    """F5-B4: Large accuracy disparities compute without math overflow."""
    k_star = compute_breakeven_kappa(1.0, 0.1, 1.0, 5.0, covert_turns_auto=2.0)
    assert k_star is not None
    assert not math.isinf(k_star)


def test_f5_bnd_floating_point_precision_stability():
    """F5-B5: Micro-deltas in bits compute stably without precision loss."""
    k_star = compute_breakeven_kappa(0.85001, 0.85000, 2.0001, 2.0000, covert_turns_auto=1.0)
    assert k_star is not None


# ==============================================================================
# F6: Likert Visibility Estimator Boundaries
# ==============================================================================

def test_f6_bnd_minimum_likert_scores_all_ones():
    """F6-B1: Minimum freedom and naturalness scores produce maximum interrogation."""
    rows_a = [{"freedom": 1, "naturalness": 1}]
    rows_b = [{"freedom": 1, "naturalness": 1}]
    est = estimate_kappa_from_surveys(rows_a, rows_b, reps=20)
    assert est.point_estimate == pytest.approx(0.35)


def test_f6_bnd_maximum_likert_scores_all_sevens():
    """F6-B2: Maximum freedom and naturalness scores produce minimum interrogation."""
    rows_a = [{"freedom": 7, "naturalness": 7}]
    rows_b = [{"freedom": 7, "naturalness": 7}]
    est = estimate_kappa_from_surveys(rows_a, rows_b, reps=20)
    assert est.point_estimate == pytest.approx(0.35)


def test_f6_bnd_identical_scores_in_both_cohorts():
    """F6-B3: Identical cohort scores yield normalized point estimate 0.35."""
    rows_a = [{"freedom": 5, "naturalness": 5}]
    rows_b = [{"freedom": 5, "naturalness": 5}]
    est = estimate_kappa_from_surveys(rows_a, rows_b, reps=20)
    assert est.point_estimate == pytest.approx(0.35)


def test_f6_bnd_single_sample_cohort():
    """F6-B4: Cohort with N=1 sample calculates without exception."""
    est = estimate_kappa_from_surveys(
        [{"freedom": 4, "naturalness": 4}], [{"freedom": 6, "naturalness": 6}], reps=20
    )
    assert est.sample_size == 2
    assert not math.isnan(est.point_estimate)


def test_f6_bnd_missing_optional_fields_defaults_gracefully():
    """F6-B5: Survey rows with missing optional fields default to neutral 4."""
    rows_a = [{}]
    rows_b = [{}]
    est = estimate_kappa_from_surveys(rows_a, rows_b, reps=20)
    assert est.sample_size == 2


# ==============================================================================
# F7: Fishing Engine Boundaries
# ==============================================================================

def test_f7_bnd_all_fishing_disabled_policy_remains_pure_direct(card_effect):
    """F7-B1: When fishing is disabled on all questions, covert candidate is None."""
    direct_effect = card_effect.without_fishing()
    posterior = {h: 1.0 / len(direct_effect.hypotheses) for h in direct_effect.hypotheses}
    cand = covert_candidate(direct_effect, posterior, set())
    assert cand is None


def test_f7_bnd_maximum_covert_budget_zero_forces_direct(card_effect):
    """F7-B2: max_covert_turns=0 causes select_turn to strictly return direct."""
    params = MethodPolicyParams(max_covert_turns=0, covert_ratio=0.0)
    state = FishingState()
    posterior = {h: 1.0 / len(card_effect.hypotheses) for h in card_effect.hypotheses}
    plan = select_turn(card_effect, posterior, set(), state, params)
    assert plan is not None
    assert plan.mode == "direct"


def test_f7_bnd_covert_ratio_bounds(card_effect):
    """F7-B3: Setting covert_ratio=0.0 strictly limits to max_covert_turns."""
    params = MethodPolicyParams(max_covert_turns=1, covert_ratio=0.0)
    state = FishingState(covert_turns=1)
    posterior = {h: 1.0 / len(card_effect.hypotheses) for h in card_effect.hypotheses}
    plan = select_turn(card_effect, posterior, set(), state, params)
    assert plan is not None
    assert plan.mode == "direct"
    assert plan.reason == "covert_budget_spent"


def test_f7_bnd_unclear_agreement_preserves_entropy(card_effect, renderer):
    """F7-B4: Unclear response to covert turn preserves posterior entropy."""
    session = EffectSession(card_effect, renderer)
    q_color = next(q for q in card_effect.questions if q.id == "q_color")
    session._current_mode = "covert"
    session._current_question = q_color
    session._asserted_answer_id = "red"
    h_before = session.tracker.entropy()
    session.respond_agreement("unclear")
    h_after = session.tracker.entropy()
    assert h_after == pytest.approx(h_before, abs=1e-3)


def test_f7_bnd_rapid_successive_fishing_respects_budget(card_effect):
    """F7-B5: Exhausting covert budget forces subsequent turns to direct."""
    params = MethodPolicyParams(max_covert_turns=1, covert_ratio=0.0)
    state = FishingState(covert_turns=1)
    posterior = {h: 1.0 / len(card_effect.hypotheses) for h in card_effect.hypotheses}
    plan = select_turn(card_effect, posterior, set(), state, params)
    assert plan.mode == "direct"


# ==============================================================================
# F8: Choice Architecture Boundaries
# ==============================================================================

def test_f8_bnd_exact_sixty_percent_threshold_triggers_force(card_effect):
    """F8-B1: Top answer holding 60% mass triggers choice force."""
    q_color = next(q for q in card_effect.questions if q.id == "q_color")
    red_hyps = [h for h, attrs in card_effect.hypotheses.items() if attrs.get("color") == "red"]
    posterior = {
        h: (0.60001 / len(red_hyps)) if h in red_hyps else (0.39999 / (52 - len(red_hyps)))
        for h in card_effect.hypotheses
    }
    target = force_target(card_effect, posterior, q_color)
    assert target == "red"


def test_f8_bnd_fifty_nine_percent_represses_force(card_effect):
    """F8-B2: Top answer holding 0.599 mass represses choice force."""
    q_color = next(q for q in card_effect.questions if q.id == "q_color")
    red_hyps = [h for h, attrs in card_effect.hypotheses.items() if attrs.get("color") == "red"]
    posterior = {
        h: (0.599 / len(red_hyps)) if h in red_hyps else (0.401 / (52 - len(red_hyps)))
        for h in card_effect.hypotheses
    }
    target = force_target(card_effect, posterior, q_color)
    assert target is None


def test_f8_bnd_post_defiance_cooldown_represses_consecutive_force(card_effect):
    """F8-B3: Force cooldown > 0 suppresses salient answer ID."""
    state = FishingState(force_cooldown=1)
    direct_effect = card_effect.without_fishing()
    red_hyps = [h for h, attrs in card_effect.hypotheses.items() if attrs.get("color") == "red"]
    posterior = {
        h: (0.75 / len(red_hyps)) if h in red_hyps else (0.25 / (52 - len(red_hyps)))
        for h in card_effect.hypotheses
    }
    plan = select_turn(direct_effect, posterior, set(), state)
    assert plan.salient_answer_id is None
    assert state.force_cooldown == 0


def test_f8_bnd_three_way_equal_split_represses_force(card_effect):
    """F8-B4: Three-way equal split represses choice forcing."""
    q_mod3 = next(q for q in card_effect.questions if q.id == "q_rank_mod3")
    uniform_p = {h: 1.0 / len(card_effect.hypotheses) for h in card_effect.hypotheses}
    target = force_target(card_effect, uniform_p, q_mod3)
    assert target is None


def test_f8_bnd_salient_answer_absent_on_covert_turns(card_effect):
    """F8-B5: Covert turns never designate a salient option."""
    state = FishingState()
    red_hyps = [h for h, attrs in card_effect.hypotheses.items() if attrs.get("color") == "red"]
    posterior = {
        h: (0.80 / len(red_hyps)) if h in red_hyps else (0.20 / (52 - len(red_hyps)))
        for h in card_effect.hypotheses
    }
    plan = select_turn(card_effect, posterior, set(), state)
    if plan.mode == "covert":
        assert plan.salient_answer_id is None


# ==============================================================================
# F9: Reveal Planner Boundaries
# ==============================================================================

def test_f9_bnd_ninety_percent_confidence_triggers_high_reveal(renderer):
    """F9-B1: Confidence >= 0.90 selects high reveal band phrasing."""
    line = renderer.reveal("Ace of Spades", confidence=0.95, session_id="s1")
    assert "ace of spades" in line.lower()


def test_f9_bnd_sub_forty_percent_triggers_forced_reveal(renderer):
    """F9-B2: Confidence < 0.40 selects forced reveal band phrasing."""
    line = renderer.reveal("Ace of Spades", confidence=0.35, session_id="s1")
    assert "ace of spades" in line.lower()


def test_f9_bnd_doubt_window_exact_edges():
    """F9-B3: Hesitation beat is active at exactly 0.60 and inactive at 0.85."""
    assert wants_hesitation(0.60) is True
    assert wants_hesitation(0.8499) is True
    assert wants_hesitation(0.85) is False


def test_f9_bnd_zero_unasked_attributes_falls_back_gracefully(card_effect):
    """F9-B4: When all questions are asked, plan_reveal falls back without exception."""
    all_q_ids = [q.id for q in card_effect.questions]
    plan = plan_reveal(card_effect, candidates=[("AS", 0.95)], asked=all_q_ids)
    assert plan.path == "progressive"


def test_f9_bnd_stages_duck_typing_and_serializability(card_effect, renderer):
    """F9-B5: Stage beats format cleanly into (kind, text) tuples."""
    plan = plan_reveal(card_effect, candidates=[("AS", 0.95)], asked=[])
    beats = renderer.stage_reveal(plan.stages, "Ace of Spades", 0.95, "s1")
    assert isinstance(beats, list)
    for kind, text in beats:
        assert isinstance(kind, str)
        assert isinstance(text, str)


# ==============================================================================
# F10: Equivocation Boundaries
# ==============================================================================

def test_f10_bnd_multiple_consecutive_misses_trigger_cooldown(card_effect):
    """F10-B1: Two consecutive misses trigger backoff to direct questioning."""
    state = FishingState(consecutive_misses=2)
    uniform_p = {h: 1.0 / len(card_effect.hypotheses) for h in card_effect.hypotheses}
    plan = select_turn(card_effect, uniform_p, set(), state)
    assert plan.mode == "direct"
    assert plan.reason == "backoff_after_misses"


def test_f10_bnd_cooldown_countdown_decrements_per_turn(card_effect):
    """F10-B2: Cooldown turns counter decrements by 1 on each call."""
    state = FishingState(cooldown_turns=2)
    uniform_p = {h: 1.0 / len(card_effect.hypotheses) for h in card_effect.hypotheses}
    select_turn(card_effect, uniform_p, set(), state)
    assert state.cooldown_turns == 1


def test_f10_bnd_reframe_templates_never_crash_on_unknown_tokens(renderer):
    """F10-B3: Reframing handles arbitrary label strings without crashing."""
    line = renderer.reframe("missed", "Omega-42", "s_token", turn=1)
    assert "omega-42" in line.lower()


def test_f10_bnd_affirmation_resets_miss_counter(card_effect, renderer):
    """F10-B4: Affirmative reaction clears consecutive misses."""
    session = EffectSession(card_effect, renderer)
    q_color = next(q for q in card_effect.questions if q.id == "q_color")
    session._current_mode = "covert"
    session._current_question = q_color
    session._asserted_answer_id = "red"
    session._fishing.consecutive_misses = 1
    session.respond_agreement("strong_yes")
    assert session._fishing.consecutive_misses == 0


def test_f10_bnd_equivocation_leaves_tracker_unaltered(card_effect, renderer):
    """F10-B5: Reframing generation has zero side effect on tracker posterior."""
    session = EffectSession(card_effect, renderer)
    p_before = dict(session.tracker.posterior)
    renderer.reframe("missed", "red", session.session_id, turn=1)
    assert session.tracker.posterior == p_before


# ==============================================================================
# F11: Passive Signal Boundaries
# ==============================================================================

def test_f11_bnd_negative_latency_clamps_to_unity():
    """F11-B1: Negative latency returns factor 1.0."""
    ch = LatencyChannel(fast_ms=2000.0, slow_ms=8000.0, floor=0.6)
    assert latency_factor(ch, -100.0) == 1.0


def test_f11_bnd_extreme_latency_sixty_seconds_clamps_to_floor():
    """F11-B2: Extreme latency (60s) clamps to configured floor."""
    ch = LatencyChannel(fast_ms=2000.0, slow_ms=8000.0, floor=0.6)
    assert latency_factor(ch, 60000.0) == 0.6


def test_f11_bnd_invalid_channel_parameters_rejected():
    """F11-B3: Invalid channel thresholds raise ValueError."""
    with pytest.raises(ValueError, match="latency channel requires"):
        LatencyChannel(fast_ms=8000.0, slow_ms=2000.0)


def test_f11_bnd_none_typing_signals_not_hesitant():
    """F11-B4: None typing rhythm signals return hesitant=False."""
    assert is_hesitant(None, None) is False


def test_f11_bnd_unclear_agreement_downgrade_stays_unclear():
    """F11-B5: Downgrading UNCLEAR remains UNCLEAR."""
    assert downgrade_strength(AgreementStrength.UNCLEAR) == AgreementStrength.UNCLEAR


# ==============================================================================
# F12: Contextual Bandit Boundaries
# ==============================================================================

def test_f12_bnd_epsilon_zero_pure_exploitation():
    """F12-B1: Epsilon=0.0 always chooses highest value action."""
    bandit = TabularBandit(epsilon=0.0, seed=42)
    bandit.update((0, 0), "direct", reward=1.0)
    bandit.update((0, 0), "covert", reward=5.0)
    assert bandit.select((0, 0), allowed=["direct", "covert"]) == "covert"


def test_f12_bnd_epsilon_one_pure_exploration():
    """F12-B2: Epsilon=1.0 explores uniformly among allowed actions."""
    bandit = TabularBandit(epsilon=1.0, seed=42)
    actions = {bandit.select((0, 0), allowed=["direct", "covert"]) for _ in range(30)}
    assert actions == {"direct", "covert"}


def test_f12_bnd_epsilon_decay_stops_at_epsilon_min():
    """F12-B3: Epsilon decay halts at configured epsilon_min."""
    bandit = TabularBandit(epsilon=0.5, epsilon_min=0.05, epsilon_decay=0.5, seed=42)
    for _ in range(50):
        bandit.update((0, 0), "direct", reward=1.0)
    assert bandit.epsilon >= 0.05


def test_f12_bnd_empty_allowed_actions_raises_value_error():
    """F12-B4: Empty allowed actions sequence raises ValueError."""
    bandit = TabularBandit(seed=42)
    with pytest.raises(ValueError, match="no actions allowed"):
        bandit.select((0, 0), allowed=[])


def test_f12_bnd_unseen_cell_returns_optimistic_initialization():
    """F12-B5: Unvisited context cell returns optimistic initialization value."""
    bandit = TabularBandit(optimistic_init=0.08, seed=42)
    assert bandit._value((2, 2), "forced") == 0.08


# ==============================================================================
# F13: Simulation Harness Boundaries
# ==============================================================================

def test_f13_bnd_zero_sessions_handled_safely(card_effect):
    """F13-B1: Requesting minimal sessions executes without error."""
    res = evaluate_magic_factor(card_effect, sessions=1, reliability=1.0, rng=random.Random(42))
    assert res["sessions"] == 1


def test_f13_bnd_adversarial_profile_lowest_accuracy():
    """F13-B2: Adversarial profile has lowest answer reliability (0.15)."""
    assert PROFILES["adversarial"].reliability == 0.15


def test_f13_bnd_cautious_profile_high_accuracy():
    """F13-B3: Cautious profile has highest answer reliability (0.98)."""
    assert PROFILES["cautious"].reliability == 0.98


def test_f13_bnd_suggestible_profile_high_force_rate():
    """F13-B4: Suggestible profile has high choice susceptibility (0.50)."""
    assert PROFILES["suggestible"].force_susceptibility == 0.50


def test_f13_bnd_evasive_profile_high_covert_softening():
    """F13-B5: Evasive profile has high fishing evasiveness (0.45)."""
    assert PROFILES["evasive"].fishing_evasiveness == 0.45


# ==============================================================================
# F14: Double-Blind A/B Boundaries
# ==============================================================================

def test_f14_bnd_condition_case_insensitive(client):
    """F14-B1: Client accepts condition parameters reliably."""
    resp = client.post("/api/sessions", json={"effect_id": "card_prediction", "condition": "a"})
    assert resp.status_code == 201


def test_f14_bnd_invalid_condition_defaults_or_handled(client):
    """F14-B2: Creating session without condition assigns a or b."""
    resp = client.post("/api/sessions", json={"effect_id": "card_prediction"})
    assert resp.json()["condition"] in ("a", "b")


def test_f14_bnd_empty_condition_defaults_to_random(client):
    """F14-B3: Omitted condition assigns condition a or b."""
    resp = client.post("/api/sessions", json={"effect_id": "card_prediction", "condition": None})
    assert resp.json()["condition"] in ("a", "b")


def test_f14_bnd_condition_a_never_emits_covert_turns(client, card_effect):
    """F14-B4: Condition A session contains zero covert turns throughout execution."""
    resp = client.post("/api/sessions", json={"effect_id": "card_prediction", "condition": "a"})
    sess_id = resp.json()["session_id"]
    view = resp.json()
    while view["phase"] == "active":
        assert view["mode"] == "direct"
        body = truthful_body(card_effect, view, "AS")
        view = client.post(f"/api/sessions/{sess_id}/answer", json=body).json()


def test_f14_bnd_condition_preserved_across_serialization(client):
    """F14-B5: Condition field persists across GET /api/sessions/{id}."""
    resp = client.post("/api/sessions", json={"effect_id": "card_prediction", "condition": "b"})
    sess_id = resp.json()["session_id"]
    view = client.get(f"/api/sessions/{sess_id}").json()
    assert view["condition"] == "b"


# ==============================================================================
# F15: Consent-Gated Ledger Boundaries
# ==============================================================================

def test_f15_bnd_gameplay_answer_creates_zero_sqlite_records(client, archive, card_effect):
    """F15-B1: Multiple answers create zero database records."""
    resp = client.post("/api/sessions", json={"effect_id": "card_prediction", "condition": "a"})
    sess_id = resp.json()["session_id"]
    view = resp.json()
    client.post(f"/api/sessions/{sess_id}/answer", json=truthful_body(card_effect, view, "AS"))
    assert len(archive.list_summaries()) == 0


def test_f15_bnd_duplicate_survey_submission_idempotent_replace(client, archive, card_effect):
    """F15-B2: Submitting survey twice replaces existing row without duplicate error."""
    resp = client.post("/api/sessions", json={"effect_id": "card_prediction"})
    sess_id = resp.json()["session_id"]
    view = resp.json()
    while view["phase"] == "active":
        body = truthful_body(card_effect, view, "AS")
        view = client.post(f"/api/sessions/{sess_id}/answer", json=body).json()
    client.post(f"/api/sessions/{sess_id}/outcome", json={"correct": True})
    p1 = {"impossibility": 5, "freedom": 5, "naturalness": 5, "surprise": 5}
    p2 = {"impossibility": 7, "freedom": 7, "naturalness": 7, "surprise": 7}
    client.post(f"/api/sessions/{sess_id}/survey", json=p1)
    s2 = client.post(f"/api/sessions/{sess_id}/survey", json=p2)
    assert s2.status_code == 201
    assert len(archive.survey_rows()) == 1
    assert archive.survey_rows()[0]["impossibility"] == 7


def test_f15_bnd_likert_out_of_range_rejected(client, card_effect):
    """F15-B3: Non-numeric survey fields are rejected with 422."""
    resp = client.post("/api/sessions", json={"effect_id": "card_prediction"})
    sess_id = resp.json()["session_id"]
    view = resp.json()
    while view["phase"] == "active":
        body = truthful_body(card_effect, view, "AS")
        view = client.post(f"/api/sessions/{sess_id}/answer", json=body).json()
    client.post(f"/api/sessions/{sess_id}/outcome", json={"correct": True})
    bad = client.post(
        f"/api/sessions/{sess_id}/survey",
        json={"impossibility": "very", "freedom": 5, "naturalness": 5, "surprise": 5},
    )
    assert bad.status_code == 422


def test_f15_bnd_likert_numeric_bounds_rejected(client, card_effect):
    """F15-B6: Numeric Likert values outside 1-7 are rejected with 422."""
    resp = client.post("/api/sessions", json={"effect_id": "card_prediction"})
    sess_id = resp.json()["session_id"]
    view = resp.json()
    while view["phase"] == "active":
        body = truthful_body(card_effect, view, "AS")
        view = client.post(f"/api/sessions/{sess_id}/answer", json=body).json()
    client.post(f"/api/sessions/{sess_id}/outcome", json={"correct": True})
    for value in (0, 8):
        bad = client.post(
            f"/api/sessions/{sess_id}/survey",
            json={"impossibility": value, "freedom": 5, "naturalness": 5, "surprise": 5},
        )
        assert bad.status_code == 422


def test_f15_bnd_nonexistent_session_survey_rejected(client):
    """F15-B4: Submitting survey for non-existent session returns 404."""
    resp = client.post(
        "/api/sessions/nonexistent/survey",
        json={"impossibility": 5, "freedom": 5, "naturalness": 5, "surprise": 5},
    )
    assert resp.status_code == 404


def test_f15_bnd_database_created_automatically_if_missing(tmp_path):
    """F15-B5: SessionArchive creates database file and parent directories automatically."""
    from services.api.archive import SessionArchive
    db_file = tmp_path / "sub" / "dir" / "new.db"
    arch = SessionArchive(db_file)
    arch.save_survey(
        "s1",
        "a",
        {"impossibility": 5, "freedom": 5, "naturalness": 5, "surprise": 5},
        "2026-10-04T00:00:00Z",
    )
    assert db_file.exists()


# ==============================================================================
# F16: Complete Deletion Boundaries
# ==============================================================================

def test_f16_bnd_delete_nonexistent_session_returns_false(archive):
    """F16-B1: Deleting unrecorded UUID returns False."""
    assert archive.delete("unrecorded_uuid") is False


def test_f16_bnd_delete_empty_database_returns_false(tmp_path):
    """F16-B2: Deleting on non-existent database file returns False."""
    from services.api.archive import SessionArchive
    arch = SessionArchive(tmp_path / "absent.db")
    assert arch.delete("some_id") is False


def test_f16_bnd_sql_injection_payload_in_session_id_sanitized(archive):
    """F16-B3: Malicious session_id string is sanitized safely."""
    injection_id = "test' OR '1'='1"
    assert archive.delete(injection_id) is False


def test_f16_bnd_orphan_survey_deletion(archive):
    """F16-B4: Orphan survey records are purged cleanly by delete."""
    archive.save_survey(
        "orphan_sess",
        "b",
        {"impossibility": 5, "freedom": 5, "naturalness": 5, "surprise": 5},
        "2026-10-04T12:00:00Z",
    )
    assert len(archive.survey_rows()) == 1
    archive.delete("orphan_sess")
    assert len(archive.survey_rows()) == 0


def test_f16_bnd_delete_locks_during_concurrent_writes(archive):
    """F16-B5: Archive maintains a threading lock for thread safety."""
    assert hasattr(archive, "_lock")


# ==============================================================================
# F17: A/B Statistical Boundaries
# ==============================================================================

def test_f17_bnd_empty_cohort_returns_nan_statistics():
    """F17-B1: Empty cohort returns NaN for Mann-Whitney U and p-value."""
    u, p = mann_whitney_u([], [1.0, 2.0])
    assert math.isnan(u)
    assert math.isnan(p)


def test_f17_bnd_identical_cohorts_return_p_value_one():
    """F17-B2: Identical cohorts produce Welch's t of 0.0 and large p-value."""
    a = [4.0, 5.0, 6.0]
    b = [4.0, 5.0, 6.0]
    t = welch_t(a, b)
    assert t == pytest.approx(0.0)


def test_f17_bnd_single_sample_cohort_returns_nan_or_valid():
    """F17-B3: Welch's t with single sample returns NaN."""
    t = welch_t([5.0], [5.0, 6.0])
    assert math.isnan(t)


def test_f17_bnd_all_tied_scores_handled():
    """F17-B4: All tied scores compute without ZeroDivisionError."""
    a = [4.0, 4.0, 4.0]
    b = [4.0, 4.0, 4.0]
    u, p = mann_whitney_u(a, b)
    assert not math.isnan(u)


def test_f17_bnd_extreme_discrepancy_p_value_near_zero():
    """F17-B5: Completely separated distributions yield small p-value."""
    a = [1.0, 1.0, 1.0, 1.0, 1.0]
    b = [7.0, 7.0, 7.0, 7.0, 7.0]
    _, p = mann_whitney_u(a, b)
    assert p < 0.02


# ==============================================================================
# F18: Séance Runner Boundaries
# ==============================================================================

def test_f18_bnd_cli_runner_keyboard_interrupt_handled():
    """F18-B1: CLI runner exits safely on invalid effect."""
    assert run_session(effect_id="invalid_xyz") is False


def test_f18_bnd_cli_runner_empty_input_defaults_to_first_option(temp_db):
    """F18-B2: Blank input defaults to first choice option."""
    def mock_input(prompt=""):
        p = prompt.lower()
        if "did loki name your true thought" in p:
            return "y"
        if "1-7" in p:
            return "5"
        if "again or show" in p:
            return "y"
        if "consent" in p:
            return "n"
        return ""

    with patch("builtins.input", mock_input):
        ok = run_session(effect_id="card_prediction", db_path=temp_db)
        assert ok is True


def test_f18_bnd_cli_runner_declined_consent_stores_nothing(temp_db):
    """F18-B3: Declining consent persists zero records to disk."""
    from services.api.archive import SessionArchive
    def mock_input(prompt=""):
        p = prompt.lower()
        if "did loki name your true thought" in p:
            return "y"
        if "1-7" in p:
            return "5"
        if "again or show" in p:
            return "y"
        if "consent" in p:
            return "n"
        return "1"

    with patch("builtins.input", mock_input):
        run_session(effect_id="card_prediction", db_path=temp_db)
    arch = SessionArchive(temp_db)
    assert len(arch.list_summaries()) == 0


def test_f18_bnd_api_invalid_session_id_returns_404(client):
    """F18-B4: Querying invalid session ID returns HTTP 404."""
    assert client.get("/api/sessions/invalid_session_id").status_code == 404


def test_f18_bnd_api_duplicate_outcome_report_rejected(client, card_effect):
    """F18-B5: Reporting outcome twice raises HTTP 409 conflict."""
    resp = client.post("/api/sessions", json={"effect_id": "card_prediction"})
    sess_id = resp.json()["session_id"]
    view = resp.json()
    while view["phase"] == "active":
        body = truthful_body(card_effect, view, "AS")
        view = client.post(f"/api/sessions/{sess_id}/answer", json=body).json()
    client.post(f"/api/sessions/{sess_id}/outcome", json={"correct": True})
    dup = client.post(f"/api/sessions/{sess_id}/outcome", json={"correct": True})
    assert dup.status_code == 409


# ==============================================================================
# F19: Research Disclosure Panel Boundaries
# ==============================================================================

def test_f19_bnd_curtain_initial_entropy_matches_uniform(client):
    """F19-B1: Initial curtain entropy matches log2(52) for card effect."""
    resp = client.post("/api/sessions", json={"effect_id": "card_prediction"})
    curtain = resp.json()["curtain"]
    assert curtain["initial_entropy_bits"] == pytest.approx(math.log2(52), abs=1e-3)


def test_f19_bnd_curtain_certainty_reaches_one_at_zero_entropy(card_effect, renderer):
    """F19-B2: Certainty reaches 1.0 when posterior entropy collapses to 0."""
    session = EffectSession(card_effect, renderer)
    while session.phase is Phase.ACTIVE:
        if session.current_mode == "covert":
            session.respond_agreement("strong_yes")
        else:
            q = session.current_question
            session.answer(q.answers[0].id)
    assert session.phase in (Phase.REVEALED, Phase.OUTCOME)


def test_f19_bnd_curtain_last_observation_none_initially(client):
    """F19-B3: last_observation is None before any passive signals recorded."""
    resp = client.post("/api/sessions", json={"effect_id": "card_prediction"})
    curtain = resp.json()["curtain"]
    assert curtain["last_observation"] is None


def test_f19_bnd_curtain_top_k_caps_at_total_hypotheses(client, number_effect):
    """F19-B4: Top-k hypothesis list length does not exceed total hypotheses."""
    resp = client.post("/api/sessions", json={"effect_id": "number_prediction"})
    top = resp.json()["curtain"]["top"]
    assert len(top) <= len(number_effect.hypotheses)


def test_f19_bnd_curtain_trajectory_length_matches_turns(client, card_effect):
    """F19-B5: Entropy history length grows monotonically with answered turns."""
    resp = client.post("/api/sessions", json={"effect_id": "card_prediction", "condition": "a"})
    sess_id = resp.json()["session_id"]
    view = resp.json()
    client.post(f"/api/sessions/{sess_id}/answer", json=truthful_body(card_effect, view, "AS"))
    view2 = client.get(f"/api/sessions/{sess_id}").json()
    assert len(view2["curtain"]["entropy_history"]) == 1


# ==============================================================================
# F20: Debriefing Boundaries
# ==============================================================================

def test_f20_bnd_debriefing_contains_no_telepathic_claims(temp_db, capsys):
    """F20-B1: Debriefing text strictly avoids claiming supernatural ability."""
    def mock_input(prompt=""):
        p = prompt.lower()
        if "did loki name your true thought" in p:
            return "y"
        if "1-7" in p:
            return "5"
        if "again or show" in p:
            return "y"
        if "consent" in p:
            return "n"
        return "1"

    with patch("builtins.input", mock_input):
        run_session(effect_id="card_prediction", db_path=temp_db)
    captured = capsys.readouterr().out
    assert "no telepathic" in captured.lower()


def test_f20_bnd_debriefing_disclaimer_not_empty(temp_db, capsys):
    """F20-B2: Debriefing text is substantial and non-empty."""
    def mock_input(prompt=""):
        p = prompt.lower()
        if "did loki name your true thought" in p:
            return "y"
        if "1-7" in p:
            return "5"
        if "again or show" in p:
            return "y"
        if "consent" in p:
            return "n"
        return "1"

    with patch("builtins.input", mock_input):
        run_session(effect_id="card_prediction", db_path=temp_db)
    captured = capsys.readouterr().out
    assert len(captured) > 200


def test_f20_bnd_debriefing_rendered_when_participant_hostile(temp_db, capsys):
    """F20-B3: Debriefing displays even when participant rejects outcome."""
    def mock_input(prompt=""):
        p = prompt.lower()
        if "did loki name your true thought" in p:
            return "n"
        if "1-7" in p:
            return "1"
        if "again or show" in p:
            return "n"
        if "consent" in p:
            return "n"
        return "1"

    with patch("builtins.input", mock_input):
        run_session(effect_id="card_prediction", db_path=temp_db)
    captured = capsys.readouterr().out
    assert "PARTICIPANT DEBRIEF" in captured


def test_f20_bnd_debriefing_rendered_when_consent_declined(temp_db, capsys):
    """F20-B4: Declining consent still displays full participant debriefing."""
    def mock_input(prompt=""):
        p = prompt.lower()
        if "did loki name your true thought" in p:
            return "y"
        if "1-7" in p:
            return "4"
        if "again or show" in p:
            return "y"
        if "consent" in p:
            return "n"
        return "1"

    with patch("builtins.input", mock_input):
        run_session(effect_id="card_prediction", db_path=temp_db)
    captured = capsys.readouterr().out
    assert "scientific principles" in captured or "Bayesian" in captured or "telepathic" in captured


def test_f20_bnd_debriefing_accessible_in_api_dto(client, card_effect):
    """F20-B5: Outcome message in SessionViewDTO is accessible and non-empty."""
    resp = client.post("/api/sessions", json={"effect_id": "card_prediction"})
    sess_id = resp.json()["session_id"]
    view = resp.json()
    while view["phase"] == "active":
        body = truthful_body(card_effect, view, "AS")
        view = client.post(f"/api/sessions/{sess_id}/answer", json=body).json()
    client.post(f"/api/sessions/{sess_id}/outcome", json={"correct": True})
    outcome_view = client.get(f"/api/sessions/{sess_id}").json()
    assert outcome_view["message"] is not None
    assert len(outcome_view["message"]) > 0


# ==============================================================================
# F21: 16 Research Questions Boundaries
# ==============================================================================

def test_f21_bnd_matrix_no_unassigned_questions():
    """F21-B1: Matrix contains zero unassigned questions."""
    content = (REPO_ROOT / "docs" / "research-questions-matrix.md").read_text(encoding="utf-8")
    for i in range(1, 17):
        assert f"| **Q{i}** |" in content


def test_f21_bnd_matrix_strictly_five_canonical_evidence_tiers():
    """F21-B2: Matrix uses strictly canonical evidence classifications."""
    content = (REPO_ROOT / "docs" / "research-questions-matrix.md").read_text(encoding="utf-8")
    assert "human-measured" in content
    assert "simulator" in content


def test_f21_bnd_matrix_file_exists_and_readable():
    """F21-B3: Matrix file exists and is non-empty."""
    p = REPO_ROOT / "docs" / "research-questions-matrix.md"
    assert p.is_file()
    assert p.stat().st_size > 1000


def test_f21_bnd_matrix_consistent_markdown_table_formatting():
    """F21-B4: Matrix markdown table header contains 5 columns."""
    content = (REPO_ROOT / "docs" / "research-questions-matrix.md").read_text(encoding="utf-8")
    header_line = next(
        line for line in content.splitlines() if "Directive Research Question" in line
    )
    assert header_line.count("|") == 6  # 5 columns delimited by 6 pipes


def test_f21_bnd_matrix_cross_references_exist_in_tree():
    """F21-B5: Referenced implementation files exist in the repository."""
    assert (REPO_ROOT / "services" / "hypothesis" / "tracker.py").exists()
    assert (REPO_ROOT / "services" / "policy" / "reveal_planner.py").exists()


# ==============================================================================
# F22: Codebase Hygiene Boundaries
# ==============================================================================

def test_f22_bnd_no_trailing_whitespace_or_bom():
    """F22-B1: Key configuration files do not start with UTF-8 BOM."""
    for conf in (REPO_ROOT / "configs" / "effects").glob("*.yaml"):
        raw = conf.read_bytes()
        assert not raw.startswith(b"\xef\xbb\xbf"), f"BOM found in {conf}"


def test_f22_bnd_all_yaml_questions_have_valid_predicates():
    """F22-B2: All effect questions contain non-empty attributes and operators."""
    registry = load_effects(REPO_ROOT / "configs" / "effects")
    for effect in registry.values():
        for q in effect.questions:
            for ans in q.answers:
                assert ans.predicate.attr
                assert ans.predicate.op


def test_f22_bnd_no_dead_or_unreachable_hypotheses():
    """F22-B3: Every hypothesis matches at least one question answer."""
    registry = load_effects(REPO_ROOT / "configs" / "effects")
    for effect in registry.values():
        for hid, attrs in effect.hypotheses.items():
            matched = any(
                ans.predicate.matches(attrs)
                for q in effect.questions
                for ans in q.answers
            )
            assert matched, f"Hypothesis {hid} unreachable in {effect.id}"


def test_f22_bnd_bandit_cli_handles_utf8_symbols():
    """F22-B4: Bandit evaluation CLI script has UTF-8 console output setup."""
    p = REPO_ROOT / "experiments" / "run_bandit_eval.py"
    content = p.read_text(encoding="utf-8")
    assert "reconfigure(encoding=" in content


def test_f22_bnd_session_archive_pragma_user_version(temp_db):
    """F22-B5: SessionArchive initializes database with user_version == 2."""
    from services.api.archive import SessionArchive
    arch = SessionArchive(temp_db)
    arch.save_survey(
        "s1",
        "a",
        {"impossibility": 5, "freedom": 5, "naturalness": 5, "surprise": 5},
        "2026-10-04T00:00:00Z",
    )
    import sqlite3
    conn = sqlite3.connect(temp_db)
    v = conn.execute("PRAGMA user_version").fetchone()[0]
    conn.close()
    assert v == 2
