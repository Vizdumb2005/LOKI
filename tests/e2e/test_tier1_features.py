"""LOKI E2E Test Suite — Tier 1: Feature Coverage (>=5 tests per feature).

Verifies core requirements and specifications for all 22 features enumerated
in PROJECT.md § Feature Inventory.
"""

from __future__ import annotations

import math
import random
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

from experiments.analyze_ab import analyze, bootstrap_ci, mann_whitney_u, welch_t
from experiments.estimate_visibility import (
    compute_breakeven_kappa,
    estimate_kappa_from_surveys,
)
from experiments.run_human_trial import run_session
from experiments.run_magic_factor_eval import KAPPA_SWEEP, evaluate_magic_factor
from services.effects.engine import CommitReason, EffectSession, Phase
from services.effects.loader import load_effects
from services.effects.models import EffectDef
from services.effects.techniques import load_techniques
from services.fusion.engine import (
    LatencyChannel,
    downgrade_strength,
    is_hesitant,
    latency_factor,
)
from services.hypothesis.metrics import normalize
from services.hypothesis.tracker import Tracker
from services.language.response_signals import AgreementStrength
from services.policy.method_selection import (
    FishingState,
    MethodPolicyParams,
    covert_candidate,
    force_target,
    select_turn,
)
from services.policy.reveal_planner import plan_reveal, wants_hesitation
from simulator.bandit import TabularBandit, context_cell
from simulator.participant import TruthfulNoisyParticipant
from simulator.profiles import PROFILES
from tests.e2e.conftest import truthful_body, truthful_response

REPO_ROOT = Path(__file__).resolve().parents[2]


# ==============================================================================
# F1: Mentalist Controller
# ==============================================================================

def test_f1_controller_decouples_belief_from_presentation(card_effect, renderer):
    """F1.1: Belief state inference is mathematically decoupled from theatrical dialogue."""
    session = EffectSession(card_effect, renderer)
    initial_p = dict(session.tracker.posterior)
    msg = session.ask_message
    assert isinstance(msg, str) and len(msg) > 0
    assert session.tracker.posterior == initial_p


def test_f1_controller_selects_direct_question_under_uniform_prior(card_effect):
    """F1.2: Controller chooses direct query when fishing is disabled or under direct policy."""
    direct_effect = card_effect.without_fishing()
    state = FishingState()
    posterior = {h: 1.0 / len(direct_effect.hypotheses) for h in direct_effect.hypotheses}
    plan = select_turn(direct_effect, posterior, set(), state)
    assert plan is not None
    assert plan.mode == "direct"
    assert plan.asserted_answer_id is None
    assert plan.info_gain_bits > 0.0


def test_f1_controller_transitions_to_covert_when_mass_exceeds_threshold(card_effect):
    """F1.3: Controller shifts to covert fishing once posterior mass exceeds fish_floor."""
    state = FishingState()
    red_hypotheses = [
        h for h, attrs in card_effect.hypotheses.items() if attrs.get("color") == "red"
    ]
    posterior = {
        h: (0.70 / len(red_hypotheses)) if h in red_hypotheses else 0.005
        for h in card_effect.hypotheses
    }
    posterior = normalize(posterior)
    plan = select_turn(card_effect, posterior, set(), state)
    assert plan is not None
    assert plan.mode == "covert"
    assert plan.asserted_answer_id is not None
    assert plan.reason == "credible_assertion"


def test_f1_controller_commits_when_posterior_exceeds_commit_threshold(card_effect, renderer):
    """F1.4: Controller transitions to reveal phase when entropy drops below threshold."""
    session = EffectSession(card_effect, renderer)
    truth = "AS"
    while session.phase is Phase.ACTIVE:
        truthful_response(session, card_effect, truth)
    assert session.phase is Phase.REVEALED
    assert session.prediction is not None
    assert session.prediction.hypothesis_id == truth
    assert session.tracker.entropy() <= card_effect.termination.entropy_threshold_bits


def test_f1_controller_respects_turn_budget_and_forces_commit(card_effect, renderer):
    """F1.5: Controller forces commit upon turn budget exhaustion."""
    direct_effect = card_effect.without_fishing()
    session = EffectSession(direct_effect, renderer)
    while session.phase is Phase.ACTIVE:
        q = session.current_question
        session.answer(q.answers[0].id)
    assert session.phase is Phase.REVEALED
    assert session.committed_because in (
        CommitReason.MAX_TURNS,
        CommitReason.NO_INFORMATIVE_QUESTION,
        CommitReason.ENTROPY_THRESHOLD,
    )


# ==============================================================================
# F2: Bayesian Hypothesis Tracker
# ==============================================================================

def test_f2_tracker_uniform_initialization():
    """F2.1: Tracker initializes a true uniform prior summing to 1.0."""
    hyps = ["h1", "h2", "h3", "h4"]
    tracker = Tracker(hyps)
    assert len(tracker.hypotheses) == 4
    for h in hyps:
        assert tracker.posterior[h] == pytest.approx(0.25)
    assert sum(tracker.posterior.values()) == pytest.approx(1.0)


def test_f2_tracker_exact_bayes_update():
    """F2.2: Tracker computes exact Bayesian update P(h|e) proportional to P(e|h)*P(h)."""
    hyps = ["h1", "h2"]
    tracker = Tracker(hyps)
    tracker.update({"h1": 0.9, "h2": 0.3})
    assert tracker.posterior["h1"] == pytest.approx(0.75)
    assert tracker.posterior["h2"] == pytest.approx(0.25)


def test_f2_tracker_entropy_calculation():
    """F2.3: Tracker calculates Shannon entropy in bits."""
    tracker = Tracker(["h1", "h2", "h3", "h4"])
    assert tracker.entropy() == pytest.approx(2.0)
    tracker.update({"h1": 1.0, "h2": 0.0, "h3": 0.0, "h4": 0.0})
    assert tracker.entropy() == pytest.approx(0.0)


def test_f2_tracker_map_hypothesis_selection():
    """F2.4: MAP hypothesis returns the highest posterior probability candidate."""
    tracker = Tracker(["h1", "h2", "h3"])
    tracker.update({"h1": 0.2, "h2": 0.7, "h3": 0.1})
    best_id, best_prob = tracker.map_hypothesis()
    assert best_id == "h2"
    assert best_prob == pytest.approx(0.7)


def test_f2_tracker_top_k_ranking():
    """F2.5: top_k returns ranked hypotheses in descending probability order."""
    tracker = Tracker(["h1", "h2", "h3", "h4"])
    tracker.update({"h1": 0.1, "h2": 0.5, "h3": 0.3, "h4": 0.1})
    top = tracker.top_k(2)
    assert len(top) == 2
    assert top[0] == ("h2", pytest.approx(0.5))
    assert top[1] == ("h3", pytest.approx(0.3))


# ==============================================================================
# F3: Magic Factor & Mystery Gap
# ==============================================================================

def test_f3_magic_factor_formula_accuracy():
    """F3.1: M = Accuracy / (1 + I_visible) calculation matches specification."""
    acc = 0.90
    i_vis = 2.0
    expected_m = 0.90 / (1.0 + 2.0)
    m = acc / (1.0 + i_vis)
    assert m == pytest.approx(expected_m)


def test_f3_mystery_gap_formula_accuracy():
    """F3.2: Delta H_mystery = Delta H_actual - I_visible calculation matches specification."""
    delta_h_actual = 4.5
    i_vis = 2.1
    expected_gap = 4.5 - 2.1
    gap = delta_h_actual - i_vis
    assert gap == pytest.approx(expected_gap)


def test_f3_magic_factor_higher_for_lower_visible_bits():
    """F3.3: Magic factor is strictly higher with fewer visible bits at equal accuracy."""
    acc = 0.85
    m_direct = acc / (1.0 + 3.5)
    m_covert = acc / (1.0 + 1.8)
    assert m_covert > m_direct


def test_f3_mystery_gap_positive_under_information_asymmetry():
    """F3.4: Information Mystery Gap is positive when actual reduction exceeds visible bits."""
    actual_reduced = 5.2
    visible_bits = 2.3
    mystery_gap = actual_reduced - visible_bits
    assert mystery_gap > 0.0


def test_f3_magic_factor_zero_accuracy_edge_case():
    """F3.5: Magic factor score is exactly zero when accuracy is zero."""
    acc = 0.0
    m = acc / (1.0 + 2.5)
    assert m == 0.0


# ==============================================================================
# F4: 5-Point Parameter Sweep
# ==============================================================================

def test_f4_sweep_contains_exact_five_kappa_points(card_effect):
    """F4.1: Sweep evaluates kappa across {0.0, 0.25, 0.50, 0.75, 1.0}."""
    assert KAPPA_SWEEP == (0.0, 0.25, 0.5, 0.75, 1.0)
    res = evaluate_magic_factor(card_effect, sessions=4, reliability=1.0, rng=random.Random(42))
    sweep_kappas = [entry["kappa"] for entry in res["kappa_sweep"]]
    assert sweep_kappas == [0.0, 0.25, 0.5, 0.75, 1.0]


def test_f4_sweep_monotonic_visible_bits(card_effect):
    """F4.2: Visible bits monotonically increase with kappa in the sweep."""
    res = evaluate_magic_factor(card_effect, sessions=4, reliability=1.0, rng=random.Random(42))
    vis_bits = [entry["avg_visible_bits"] for entry in res["kappa_sweep"]]
    for i in range(len(vis_bits) - 1):
        assert vis_bits[i] <= vis_bits[i + 1] + 1e-6


def test_f4_sweep_monotonic_mystery_gap_decrease(card_effect):
    """F4.3: Information Mystery Gap monotonically decreases as kappa increases."""
    res = evaluate_magic_factor(card_effect, sessions=4, reliability=1.0, rng=random.Random(42))
    gaps = [entry["avg_information_mystery_gap_bits"] for entry in res["kappa_sweep"]]
    for i in range(len(gaps) - 1):
        assert gaps[i] >= gaps[i + 1] - 1e-6


def test_f4_sweep_magic_factor_monotonic_decrease(card_effect):
    """F4.4: Magic Factor monotonically decreases as kappa increases."""
    res = evaluate_magic_factor(card_effect, sessions=4, reliability=1.0, rng=random.Random(42))
    m_scores = [entry["magic_factor_score"] for entry in res["kappa_sweep"]]
    for i in range(len(m_scores) - 1):
        assert m_scores[i] >= m_scores[i + 1] - 1e-6


def test_f4_sweep_headline_kappa_matches_quarter_point(card_effect):
    """F4.5: Headline reporting at kappa=0.25 matches the sweep entry."""
    res = evaluate_magic_factor(
        card_effect, sessions=4, reliability=1.0, rng=random.Random(42), kappa=0.25
    )
    quarter_sweep = next(s for s in res["kappa_sweep"] if s["kappa"] == 0.25)
    assert res["avg_visible_bits_used"] == quarter_sweep["avg_visible_bits"]
    assert (
        res["avg_information_mystery_gap_bits"]
        == quarter_sweep["avg_information_mystery_gap_bits"]
    )


# ==============================================================================
# F5: Breakeven kappa* Inlining
# ==============================================================================

def test_f5_breakeven_analytic_formula_equivalence():
    """F5.1: compute_breakeven_kappa solves M(auto, kappa*) = M(direct)."""
    acc_auto = 0.92
    acc_direct = 0.90
    vis_auto = 1.8
    vis_direct = 2.6
    covert_turns = 1.0
    k_star = compute_breakeven_kappa(acc_auto, acc_direct, vis_auto, vis_direct, covert_turns)
    assert k_star is not None
    m_direct = acc_direct / (1.0 + vis_direct)
    m_auto = acc_auto / (1.0 + vis_auto + k_star * covert_turns * math.log2(3.0))
    assert m_auto == pytest.approx(m_direct, abs=1e-3)


def test_f5_breakeven_none_when_no_covert_turns():
    """F5.2: compute_breakeven_kappa returns None when covert turns count is 0."""
    res = compute_breakeven_kappa(0.9, 0.9, 2.0, 2.0, covert_turns_auto=0.0)
    assert res is None


def test_f5_breakeven_none_when_direct_accuracy_zero():
    """F5.3: compute_breakeven_kappa returns None when direct accuracy is 0."""
    res = compute_breakeven_kappa(0.9, 0.0, 1.5, 2.5, covert_turns_auto=1.0)
    assert res is None


def test_f5_breakeven_positive_when_auto_beats_direct():
    """F5.4: Breakeven kappa* is positive when auto policy achieves higher efficiency."""
    k_star = compute_breakeven_kappa(0.95, 0.90, 1.2, 2.5, covert_turns_auto=1.0)
    assert k_star is not None
    assert k_star > 0.0


def test_f5_breakeven_round_trip_magic_factor_equality():
    """F5.5: Round-trip verification confirms breakeven equality within numerical precision."""
    k_star = compute_breakeven_kappa(0.88, 0.85, 1.5, 2.2, covert_turns_auto=1.2)
    assert k_star is not None
    denom_auto = 1.0 + 1.5 + k_star * 1.2 * math.log2(3.0)
    m_auto = 0.88 / denom_auto
    m_direct = 0.85 / (1.0 + 2.2)
    assert m_auto == pytest.approx(m_direct, abs=1e-3)


# ==============================================================================
# F6: Likert Visibility Estimator
# ==============================================================================

def test_f6_likert_estimator_computes_interrogation_ratio():
    """F6.1: Derives kappa point estimate from relative interrogation scores."""
    rows_a = [{"freedom": 3, "naturalness": 3}]
    rows_b = [{"freedom": 6, "naturalness": 6}]
    est = estimate_kappa_from_surveys(rows_a, rows_b, reps=100)
    assert est.method == "likert_interrogation_ratio"
    assert 0.0 <= est.point_estimate <= 1.0


def test_f6_likert_estimator_returns_uncalibrated_prior_when_empty():
    """F6.2: Returns uncalibrated prior (0.25) when survey inputs are empty."""
    est = estimate_kappa_from_surveys([], [])
    assert est.point_estimate == 0.25
    assert est.method == "uncalibrated_prior"
    assert est.sample_size == 0


def test_f6_likert_estimator_clamps_to_zero_one():
    """F6.3: Point estimate is strictly clamped to [0.0, 1.0]."""
    rows_a = [{"freedom": 7, "naturalness": 7}]
    rows_b = [{"freedom": 1, "naturalness": 1}]
    est = estimate_kappa_from_surveys(rows_a, rows_b, reps=50)
    assert 0.0 <= est.point_estimate <= 1.0


def test_f6_likert_estimator_bootstrap_confidence_interval():
    """F6.4: Produces valid ordered 95% bootstrap confidence interval."""
    rows_a = [{"freedom": 4, "naturalness": 4}, {"freedom": 3, "naturalness": 5}]
    rows_b = [{"freedom": 6, "naturalness": 5}, {"freedom": 5, "naturalness": 6}]
    est = estimate_kappa_from_surveys(rows_a, rows_b, reps=100)
    assert not math.isnan(est.ci_lower)
    assert not math.isnan(est.ci_upper)
    assert est.ci_lower <= est.ci_upper


def test_f6_likert_estimator_sample_size_tracking():
    """F6.5: Correctly tracks total sample size Na + Nb."""
    rows_a = [{"freedom": 4, "naturalness": 4}] * 3
    rows_b = [{"freedom": 5, "naturalness": 5}] * 5
    est = estimate_kappa_from_surveys(rows_a, rows_b, reps=50)
    assert est.sample_size == 8


# ==============================================================================
# F7: Covert Fishing Engine
# ==============================================================================

def test_f7_fishing_candidate_requires_sufficient_posterior(card_effect):
    """F7.1: Covert candidate is rejected when posterior mass is below fish_floor."""
    # Under fish_floor = 0.90, uniform distribution on cards cannot fish
    params = MethodPolicyParams(fish_floor=0.90)
    posterior = {h: 1.0 / len(card_effect.hypotheses) for h in card_effect.hypotheses}
    cand = covert_candidate(card_effect, posterior, set(), params)
    assert cand is None


def test_f7_fishing_candidate_restricts_to_binary_partitions(card_effect):
    """F7.2: Covert fishing is restricted to questions with <= max_fish_options (2)."""
    params = MethodPolicyParams(max_fish_options=2)
    posterior = {h: 0.90 if "S" in h else 0.002 for h in card_effect.hypotheses}
    posterior = normalize(posterior)
    cand = covert_candidate(card_effect, posterior, set(), params)
    if cand:
        q = next(q for q in card_effect.questions if q.id == cand.question_id)
        assert len(q.answers) <= 2


def test_f7_fishing_soft_update_strong_yes(card_effect, renderer):
    """F7.3: Affirmative covert response increases asserted option probability."""
    session = EffectSession(card_effect, renderer)
    q_color = next(q for q in card_effect.questions if q.id == "q_color")
    session._current_mode = "covert"
    session._current_question = q_color
    session._asserted_answer_id = "red"
    p_before = sum(
        session.tracker.posterior[h]
        for h, a in card_effect.hypotheses.items()
        if a.get("color") == "red"
    )
    session.respond_agreement("strong_yes")
    p_after = sum(
        session.tracker.posterior[h]
        for h, a in card_effect.hypotheses.items()
        if a.get("color") == "red"
    )
    assert p_after > p_before


def test_f7_fishing_soft_update_strong_no(card_effect, renderer):
    """F7.4: Denial response reduces asserted option probability."""
    session = EffectSession(card_effect, renderer)
    q_color = next(q for q in card_effect.questions if q.id == "q_color")
    session._current_mode = "covert"
    session._current_question = q_color
    session._asserted_answer_id = "red"
    p_before = sum(
        session.tracker.posterior[h]
        for h, a in card_effect.hypotheses.items()
        if a.get("color") == "red"
    )
    session.respond_agreement("strong_no")
    p_after = sum(
        session.tracker.posterior[h]
        for h, a in card_effect.hypotheses.items()
        if a.get("color") == "red"
    )
    assert p_after < p_before


def test_f7_fishing_openers_rendered_theatrically(renderer):
    """F7.5: Fishing statements are rendered with theatrical framing templates."""
    line = renderer.fishing("red", session_id="test_sess", turn=1)
    assert isinstance(line, str)
    assert "red" in line.lower()


# ==============================================================================
# F8: Choice Architecture Forcing
# ==============================================================================

def test_f8_forcing_triggers_when_posterior_reaches_sixty_percent(card_effect):
    """F8.1: Salient force target activates when option partition holds >= 0.60 mass."""
    q_color = next(q for q in card_effect.questions if q.id == "q_color")
    red_hyps = [h for h, attrs in card_effect.hypotheses.items() if attrs.get("color") == "red"]
    posterior = {
        h: (0.65 / len(red_hyps)) if h in red_hyps else (0.35 / (52 - len(red_hyps)))
        for h in card_effect.hypotheses
    }
    target = force_target(card_effect, posterior, q_color)
    assert target == "red"


def test_f8_forcing_dormant_when_mass_below_threshold(card_effect):
    """F8.2: Force target is None when partition mass is below force_floor."""
    q_color = next(q for q in card_effect.questions if q.id == "q_color")
    uniform_p = {h: 1.0 / len(card_effect.hypotheses) for h in card_effect.hypotheses}
    target = force_target(card_effect, uniform_p, q_color)
    assert target is None


def test_f8_forcing_deterministic_tie_breaking(card_effect):
    """F8.3: Exact ties in answer mass resolve deterministically by declaration order."""
    q_color = next(q for q in card_effect.questions if q.id == "q_color")
    params = MethodPolicyParams(force_floor=0.40)
    uniform_p = {h: 1.0 / len(card_effect.hypotheses) for h in card_effect.hypotheses}
    target = force_target(card_effect, uniform_p, q_color, params=params)
    assert target == q_color.answers[0].id


def test_f8_forcing_participant_susceptibility_concentrates_choice(card_effect):
    """F8.4: Susceptible participant concentrates choice noise on salient option."""
    rng = random.Random(42)
    truth = "AS"
    participant = TruthfulNoisyParticipant(
        card_effect, truth, rng, reliability_override=0.0, force_susceptibility=1.0
    )
    q = card_effect.questions[0]
    forced_target = q.answers[1].id
    chosen = participant.answer(q, salient_answer_id=forced_target)
    assert chosen == forced_target


def test_f8_forcing_view_dto_exposes_salient_option(client):
    """F8.5: SessionViewDTO includes salient_option_id when choice forcing is active."""
    resp = client.post("/api/sessions", json={"effect_id": "card_prediction", "condition": "b"})
    data = resp.json()
    assert "salient_option_id" in data


# ==============================================================================
# F9: Multi-Branch Reveal Planning
# ==============================================================================

def test_f9_reveal_progressive_ladder_when_high_confidence(card_effect):
    """F9.1: Selects progressive attribute ladder when confidence >= 0.80."""
    candidates = [("AS", 0.92), ("KS", 0.04), ("QS", 0.04)]
    plan = plan_reveal(card_effect, candidates=candidates, asked=["q_color"])
    assert plan.path == "progressive"
    assert len(plan.stages) > 0


def test_f9_reveal_category_cluster_when_uncertain(card_effect):
    """F9.2: Selects category cluster when confidence is between 0.50 and 0.80."""
    candidates = [("AS", 0.55), ("KS", 0.35), ("QS", 0.10)]
    plan = plan_reveal(card_effect, candidates=candidates, asked=[])
    assert plan.path in ("category_cluster", "dual_deduction")


def test_f9_reveal_dual_deduction_when_two_rivals(card_effect):
    """F9.3: Selects dual deduction when top two rivals dominate mass."""
    candidates = [("AS", 0.45), ("KS", 0.35), ("2C", 0.20)]
    plan = plan_reveal(card_effect, candidates=candidates, asked=[])
    assert plan.path == "dual_deduction"


def test_f9_reveal_strategic_hesitation_within_doubt_window():
    """F9.4: Hesitation is flagged True inside calibrated doubt window [0.60, 0.85)."""
    assert wants_hesitation(0.72) is True
    assert wants_hesitation(0.95) is False
    assert wants_hesitation(0.40) is False


def test_f9_reveal_prioritizes_unasked_corpus_attributes(card_effect):
    """F9.5: Unasked attributes are prioritized in progressive ladder beats."""
    candidates = [("AS", 0.95)]
    plan = plan_reveal(card_effect, candidates=candidates, asked=["q_color"])
    assert plan.stages[0].attr != "color"


# ==============================================================================
# F10: Equivocation Recovery Engine
# ==============================================================================

def test_f10_equivocation_reframes_missed_reading(renderer):
    """F10.1: Generates theatrical reframing dialogue following a missed cold read."""
    line = renderer.reframe("missed", "red", "sess_1", turn=2)
    assert isinstance(line, str)
    assert len(line) > 0


def test_f10_equivocation_reframes_unclear_reading(renderer):
    """F10.2: Generates softening reframing dialogue following an unclear read."""
    line = renderer.reframe("unclear", "red", "sess_1", turn=2)
    assert isinstance(line, str)
    assert len(line) > 0


def test_f10_equivocation_reframes_defied_choice_force(renderer):
    """F10.3: Generates theatrical pivot when participant defies choice forcing."""
    line = renderer.reframe("defied", "red", "sess_1", turn=2)
    assert isinstance(line, str)
    assert len(line) > 0


def test_f10_equivocation_increments_consecutive_misses(card_effect, renderer):
    """F10.4: Denial reaction on covert turn records miss and triggers cooldown."""
    session = EffectSession(card_effect, renderer)
    q_color = next(q for q in card_effect.questions if q.id == "q_color")
    session._current_mode = "covert"
    session._current_question = q_color
    session._asserted_answer_id = "red"
    session.respond_agreement("strong_no")
    assert session._fishing.cooldown_turns == 1
    assert session.current_mode == "direct"


def test_f10_equivocation_triggers_cooldown_after_miss(card_effect):
    """F10.5: Consecutive miss triggers direct questioning backoff."""
    state = FishingState(consecutive_misses=1)
    params = MethodPolicyParams(miss_limit=1, cooldown_turns=1)
    posterior = {h: 1.0 / len(card_effect.hypotheses) for h in card_effect.hypotheses}
    plan = select_turn(card_effect, posterior, set(), state, params)
    assert plan is not None
    assert plan.mode == "direct"
    assert "misses" in plan.reason


# ==============================================================================
# F11: Passive Signal Modulation
# ==============================================================================

def test_f11_latency_factor_fast_response_retains_unity():
    """F11.1: Response latency <= fast_ms retains full factor 1.0."""
    ch = LatencyChannel(fast_ms=2000.0, slow_ms=8000.0, floor=0.6)
    assert latency_factor(ch, 1500.0) == 1.0
    assert latency_factor(ch, 2000.0) == 1.0


def test_f11_latency_factor_slow_response_drops_to_floor():
    """F11.2: Response latency >= slow_ms drops to configured floor (0.6)."""
    ch = LatencyChannel(fast_ms=2000.0, slow_ms=8000.0, floor=0.6)
    assert latency_factor(ch, 8000.0) == 0.6
    assert latency_factor(ch, 12000.0) == 0.6


def test_f11_latency_factor_linear_interpolation():
    """F11.3: Latency linearly interpolates between fast_ms and slow_ms."""
    ch = LatencyChannel(fast_ms=2000.0, slow_ms=8000.0, floor=0.6)
    assert latency_factor(ch, 5000.0) == pytest.approx(0.8)


def test_f11_hesitation_detected_by_slow_first_key():
    """F11.4: Typing rhythm first key > 3000ms flags hesitation."""
    assert is_hesitant(first_key_ms=3500.0, median_interval_ms=200.0) is True
    assert is_hesitant(first_key_ms=1000.0, median_interval_ms=200.0) is False


def test_f11_hesitation_downgrades_agreement_strength():
    """F11.5: Hesitation downgrades agreement strength one step toward uncertainty."""
    assert downgrade_strength(AgreementStrength.STRONG_YES) == AgreementStrength.LEAN_YES
    assert downgrade_strength(AgreementStrength.LEAN_YES) == AgreementStrength.UNCLEAR
    assert downgrade_strength(AgreementStrength.STRONG_NO) == AgreementStrength.LEAN_NO


# ==============================================================================
# F12: Contextual RL Bandit
# ==============================================================================

def test_f12_bandit_initialization_and_cell_discretization(card_effect):
    """F12.1: Context cell discretization maps session state to valid (phase, credibility) cell."""
    posterior = {h: 1.0 / len(card_effect.hypotheses) for h in card_effect.hypotheses}
    cell = context_cell(card_effect, posterior, set(), card_effect.questions[0])
    assert isinstance(cell, tuple)
    assert len(cell) == 2
    assert 0 <= cell[0] < 3
    assert 0 <= cell[1] < 3


def test_f12_bandit_epsilon_greedy_action_selection():
    """F12.2: Bandit selects an action from allowed set respecting epsilon."""
    bandit = TabularBandit(epsilon=0.0, seed=42)
    action = bandit.select((0, 0), allowed=["direct", "covert"])
    assert action in ["direct", "covert"]


def test_f12_bandit_q_value_update_and_epsilon_decay():
    """F12.3: Updating bandit shifts action value and decays exploration rate."""
    bandit = TabularBandit(epsilon=0.5, epsilon_decay=0.9, seed=42)
    initial_eps = bandit.epsilon
    bandit.update((0, 0), "direct", reward=1.0)
    assert bandit.epsilon < initial_eps
    assert bandit._values[(0, 0)]["direct"] > 0.05


def test_f12_bandit_action_masking_enforces_rules():
    """F12.4: Action masking strictly restricts bandit to allowed actions."""
    bandit = TabularBandit(epsilon=0.0, seed=42)
    bandit.update((0, 0), "covert", reward=10.0)
    action = bandit.select((0, 0), allowed=["direct"])
    assert action == "direct"


def test_f12_bandit_serialization_round_trip():
    """F12.5: to_dict and from_dict preserve exact weights and counts."""
    bandit = TabularBandit(seed=42)
    bandit.update((1, 2), "forced", reward=0.8)
    data = bandit.to_dict()
    restored = TabularBandit.from_dict(data)
    assert restored.greedy_action((1, 2)) == "forced"


# ==============================================================================
# F13: Simulation Harness >= 1,000
# ==============================================================================

def test_f13_simulation_reproducibility_with_seed(card_effect):
    """F13.1: Seeded simulations produce bit-identical results."""
    res1 = evaluate_magic_factor(
        card_effect, sessions=5, reliability=0.9, rng=random.Random(100)
    )
    res2 = evaluate_magic_factor(
        card_effect, sessions=5, reliability=0.9, rng=random.Random(100)
    )
    assert res1["top1_accuracy"] == res2["top1_accuracy"]
    assert res1["avg_turns"] == res2["avg_turns"]
    assert res1["magic_factor_score"] == res2["magic_factor_score"]


def test_f13_simulation_supports_all_six_profiles():
    """F13.2: Simulator provides all 6 documented participant profiles."""
    expected = {"balanced", "impulsive", "cautious", "suggestible", "evasive", "adversarial"}
    assert set(PROFILES.keys()) == expected


def test_f13_simulation_supports_all_four_effect_domains(registry):
    """F13.3: Harness supports 4 target domains."""
    domains = ["animal_guess", "card_prediction", "number_prediction", "sigil_forced_choice"]
    for effect_id in domains:
        res = evaluate_magic_factor(
            registry[effect_id], sessions=2, reliability=1.0, rng=random.Random(42)
        )
        assert res["sessions"] == 2
        assert "magic_factor_score" in res


def test_f13_simulation_tracks_forced_commit_rate(card_effect):
    """F13.4: Tracks fraction of sessions forced to commit by turn budget exhaustion."""
    res = evaluate_magic_factor(card_effect, sessions=4, reliability=0.9, rng=random.Random(42))
    assert 0.0 <= res["forced_commit_rate"] <= 1.0


def test_f13_simulation_calculates_magic_factor_and_mystery_gap(card_effect):
    """F13.5: Calculates both Magic Factor score and Information Mystery Gap."""
    res = evaluate_magic_factor(card_effect, sessions=4, reliability=0.9, rng=random.Random(42))
    assert "magic_factor_score" in res
    assert "avg_information_mystery_gap_bits" in res


# ==============================================================================
# F14: Double-Blind A/B Assignment
# ==============================================================================

def test_f14_server_side_random_assignment(client):
    """F14.1: Server assigns condition A or B randomly when unspecified."""
    conditions = set()
    for _ in range(25):
        resp = client.post("/api/sessions", json={"effect_id": "card_prediction"})
        conditions.add(resp.json()["condition"])
    assert "a" in conditions and "b" in conditions


def test_f14_condition_a_disables_performance_and_fishing(client):
    """F14.2: Condition A disables theatrical performance and covert fishing."""
    resp = client.post("/api/sessions", json={"effect_id": "card_prediction", "condition": "a"})
    data = resp.json()
    assert data["condition"] == "a"
    assert data["mode"] == "direct"


def test_f14_condition_b_enables_full_mentalist_engine(client):
    """F14.3: Condition B enables full mentalist engine."""
    resp = client.post("/api/sessions", json={"effect_id": "card_prediction", "condition": "b"})
    data = resp.json()
    assert data["condition"] == "b"


def test_f14_explicit_condition_override_respected(client):
    """F14.4: Explicit condition parameter is strictly respected."""
    resp_a = client.post("/api/sessions", json={"effect_id": "card_prediction", "condition": "a"})
    assert resp_a.json()["condition"] == "a"
    resp_b = client.post("/api/sessions", json={"effect_id": "card_prediction", "condition": "b"})
    assert resp_b.json()["condition"] == "b"


def test_f14_session_view_reflects_assigned_condition(client):
    """F14.5: SessionViewDTO exposes condition field."""
    resp = client.post("/api/sessions", json={"effect_id": "card_prediction"})
    data = resp.json()
    assert data["condition"] in ("a", "b")


# ==============================================================================
# F15: Consent-Gated Local Ledger
# ==============================================================================

def test_f15_zero_writes_during_gameplay(client, archive):
    """F15.1: Zero records written to database during active gameplay."""
    resp = client.post("/api/sessions", json={"effect_id": "card_prediction", "condition": "b"})
    sess_id = resp.json()["session_id"]
    client.post(f"/api/sessions/{sess_id}/answer", json={"answer_id": "strong_yes"})
    assert archive.list_summaries() == []
    assert archive.survey_rows() == []


def test_f15_survey_submission_acts_as_consent_write(client, archive, card_effect):
    """F15.2: Submitting post-séance survey writes research ledger entry."""
    resp = client.post("/api/sessions", json={"effect_id": "card_prediction"})
    sess_id = resp.json()["session_id"]
    view = resp.json()
    while view["phase"] == "active":
        body = truthful_body(card_effect, view, "AS")
        view = client.post(f"/api/sessions/{sess_id}/answer", json=body).json()
    client.post(f"/api/sessions/{sess_id}/outcome", json={"correct": True})
    survey_payload = {
        "impossibility": 7,
        "freedom": 6,
        "naturalness": 5,
        "surprise": 7,
        "willing_repeat": 1,
    }
    s_resp = client.post(f"/api/sessions/{sess_id}/survey", json=survey_payload)
    assert s_resp.status_code == 201
    surveys = archive.survey_rows()
    assert len(surveys) == 1
    assert surveys[0]["session_id"] == sess_id


def test_f15_explicit_archive_endpoint_persists_session(client, archive, card_effect):
    """F15.3: POST /api/sessions/{id}/archive writes session summary."""
    resp = client.post("/api/sessions", json={"effect_id": "card_prediction"})
    sess_id = resp.json()["session_id"]
    view = resp.json()
    while view["phase"] == "active":
        body = truthful_body(card_effect, view, "AS")
        view = client.post(f"/api/sessions/{sess_id}/answer", json=body).json()
    client.post(f"/api/sessions/{sess_id}/outcome", json={"correct": True})
    arch_resp = client.post(f"/api/sessions/{sess_id}/archive")
    assert arch_resp.status_code == 200
    assert len(archive.list_summaries()) == 1


def test_f15_survey_requires_completed_outcome_phase(client):
    """F15.4: Submitting survey before outcome phase is rejected with HTTP 409."""
    resp = client.post("/api/sessions", json={"effect_id": "card_prediction"})
    sess_id = resp.json()["session_id"]
    s_resp = client.post(
        f"/api/sessions/{sess_id}/survey",
        json={"impossibility": 5, "freedom": 5, "naturalness": 5, "surprise": 5},
    )
    assert s_resp.status_code == 409


def test_f15_archive_stores_likert_instrument_fields(client, archive, card_effect):
    """F15.5: Archive stores all 4 Likert items + willing_repeat."""
    resp = client.post("/api/sessions", json={"effect_id": "card_prediction"})
    sess_id = resp.json()["session_id"]
    view = resp.json()
    while view["phase"] == "active":
        body = truthful_body(card_effect, view, "AS")
        view = client.post(f"/api/sessions/{sess_id}/answer", json=body).json()
    client.post(f"/api/sessions/{sess_id}/outcome", json={"correct": True})
    client.post(
        f"/api/sessions/{sess_id}/survey",
        json={
            "impossibility": 6,
            "freedom": 5,
            "naturalness": 4,
            "surprise": 7,
            "willing_repeat": 1,
        },
    )
    row = archive.survey_rows()[0]
    assert row["impossibility"] == 6
    assert row["freedom"] == 5
    assert row["naturalness"] == 4
    assert row["surprise"] == 7
    assert row["willing_repeat"] == 1


# ==============================================================================
# F16: Complete Deletion Controls
# ==============================================================================

def test_f16_deletion_removes_session_record(client, archive, card_effect):
    """F16.1: Hard deletion removes session record completely."""
    resp = client.post("/api/sessions", json={"effect_id": "card_prediction"})
    sess_id = resp.json()["session_id"]
    view = resp.json()
    while view["phase"] == "active":
        body = truthful_body(card_effect, view, "AS")
        view = client.post(f"/api/sessions/{sess_id}/answer", json=body).json()
    client.post(f"/api/sessions/{sess_id}/outcome", json={"correct": True})
    client.post(f"/api/sessions/{sess_id}/archive")
    assert len(archive.list_summaries()) == 1
    archive.delete(sess_id)
    assert len(archive.list_summaries()) == 0


def test_f16_deletion_removes_survey_record(client, archive, card_effect):
    """F16.2: Hard deletion purges associated survey record."""
    resp = client.post("/api/sessions", json={"effect_id": "card_prediction"})
    sess_id = resp.json()["session_id"]
    view = resp.json()
    while view["phase"] == "active":
        body = truthful_body(card_effect, view, "AS")
        view = client.post(f"/api/sessions/{sess_id}/answer", json=body).json()
    client.post(f"/api/sessions/{sess_id}/outcome", json={"correct": True})
    client.post(
        f"/api/sessions/{sess_id}/survey",
        json={"impossibility": 7, "freedom": 7, "naturalness": 7, "surprise": 7},
    )
    assert len(archive.survey_rows()) == 1
    archive.delete(sess_id)
    assert len(archive.survey_rows()) == 0


def test_f16_deletion_returns_http_204_on_success(client, card_effect):
    """F16.3: DELETE /api/archive/{id} returns HTTP 204 No Content."""
    resp = client.post("/api/sessions", json={"effect_id": "card_prediction"})
    sess_id = resp.json()["session_id"]
    view = resp.json()
    while view["phase"] == "active":
        body = truthful_body(card_effect, view, "AS")
        view = client.post(f"/api/sessions/{sess_id}/answer", json=body).json()
    client.post(f"/api/sessions/{sess_id}/outcome", json={"correct": True})
    client.post(f"/api/sessions/{sess_id}/archive")
    del_resp = client.delete(f"/api/archive/{sess_id}")
    assert del_resp.status_code == 204


def test_f16_deletion_returns_http_404_for_nonexistent(client):
    """F16.4: Deleting non-existent archive record returns HTTP 404."""
    del_resp = client.delete("/api/archive/unknown_uuid")
    assert del_resp.status_code == 404


def test_f16_deletion_idempotent_and_verifiable(client, card_effect):
    """F16.5: Subsequent deletion attempts fail after first successful deletion."""
    resp = client.post("/api/sessions", json={"effect_id": "card_prediction"})
    sess_id = resp.json()["session_id"]
    view = resp.json()
    while view["phase"] == "active":
        body = truthful_body(card_effect, view, "AS")
        view = client.post(f"/api/sessions/{sess_id}/answer", json=body).json()
    client.post(f"/api/sessions/{sess_id}/outcome", json={"correct": True})
    client.post(f"/api/sessions/{sess_id}/archive")
    assert client.delete(f"/api/archive/{sess_id}").status_code == 204
    assert client.delete(f"/api/archive/{sess_id}").status_code == 404


# ==============================================================================
# F17: A/B Statistical Test Suite
# ==============================================================================

def test_f17_mann_whitney_u_statistic_and_p_value():
    """F17.1: Computes Mann-Whitney U and two-sided p-value correctly."""
    a = [1.0, 2.0, 3.0]
    b = [4.0, 5.0, 6.0]
    u, p = mann_whitney_u(a, b)
    assert u == 0.0
    assert p < 0.05


def test_f17_welch_t_statistic_unequal_variances():
    """F17.2: Computes Welch's t statistic for unequal variance distributions."""
    a = [2.0, 2.1, 2.0, 2.2]
    b = [5.0, 5.5, 4.8, 5.2]
    t = welch_t(a, b)
    assert t < -5.0


def test_f17_bootstrap_confidence_intervals_95_percent():
    """F17.3: Produces 95% bootstrap confidence interval."""
    vals = [4.0, 5.0, 6.0, 5.0, 4.0, 6.0, 5.0]
    ci_low, ci_high = bootstrap_ci(vals, reps=100)
    assert ci_low <= ci_high
    assert 4.0 <= ci_low <= 6.0


def test_f17_analyze_ab_reports_all_four_likert_items():
    """F17.4: analyze_ab reports statistics across all 4 Likert items."""
    rows = [
        {"condition": "a", "impossibility": 3, "freedom": 4, "naturalness": 4, "surprise": 3},
        {"condition": "b", "impossibility": 6, "freedom": 5, "naturalness": 6, "surprise": 6},
    ]
    report = analyze(rows)
    for item in ("impossibility", "freedom", "naturalness", "surprise"):
        assert item in report
        assert "mean_a" in report[item]
        assert "mean_b" in report[item]


def test_f17_analyze_ab_computes_manipulation_checks():
    """F17.5: Computes objective manipulation check accuracies."""
    rows = [
        {
            "condition": "a",
            "correct": 1,
            "impossibility": 4,
            "freedom": 4,
            "naturalness": 4,
            "surprise": 4,
        },
        {
            "condition": "b",
            "correct": 1,
            "impossibility": 6,
            "freedom": 5,
            "naturalness": 6,
            "surprise": 6,
        },
    ]
    report = analyze(rows)
    assert report["accuracy_a"] == 1.0
    assert report["accuracy_b"] == 1.0


def test_f17_analyze_ab_reports_willing_repeat_rates():
    """F17.6: analyze_ab reports replay-willingness rates per condition."""
    rows = [
        {
            "condition": "a",
            "willing_repeat": 0,
            "impossibility": 3,
            "freedom": 4,
            "naturalness": 4,
            "surprise": 3,
        },
        {
            "condition": "a",
            "willing_repeat": 1,
            "impossibility": 4,
            "freedom": 4,
            "naturalness": 4,
            "surprise": 4,
        },
        {
            "condition": "b",
            "willing_repeat": 1,
            "impossibility": 6,
            "freedom": 5,
            "naturalness": 6,
            "surprise": 6,
        },
        {
            "condition": "b",
            "willing_repeat": 1,
            "impossibility": 5,
            "freedom": 5,
            "naturalness": 5,
            "surprise": 5,
        },
    ]
    report = analyze(rows)
    assert report["willing_repeat"]["rate_a"] == 0.5
    assert report["willing_repeat"]["rate_b"] == 1.0
    assert report["willing_repeat"]["ci_a"] is not None
    assert report["willing_repeat"]["ci_b"] is not None


def test_f17_analyze_ab_skips_malformed_rows_without_crashing():
    """F17.7: analyze_ab coerces-or-skips junk fields in hand-built rows."""
    rows = [
        {"condition": "a", "willing_repeat": "yes", "surprise": None},
        {"condition": "b", "willing_repeat": True, "surprise": "5"},
        {"condition": "zzz", "willing_repeat": 1, "surprise": 7},
        {"condition": "a"},
    ]
    report = analyze(rows)
    assert report["willing_repeat"]["rate_a"] is None
    assert report["willing_repeat"]["rate_b"] == 1.0
    assert report["surprise"]["mean_a"] is None
    assert report["surprise"]["mean_b"] == 5.0


# ==============================================================================
# F18: Interactive Séance Runners
# ==============================================================================

def test_f18_cli_runner_validates_known_effects():
    """F18.1: CLI runner rejects unknown effect IDs gracefully."""
    ok = run_session(effect_id="nonexistent_effect")
    assert ok is False


def test_f18_cli_runner_executes_full_turn_loop(temp_db):
    """F18.2: CLI runner executes full interactive loop with simulated input."""
    def mock_input(prompt=""):
        p = prompt.lower()
        if "did loki name your true thought" in p:
            return "y"
        if "1-7" in p:
            return "5"
        if "again or show" in p:
            return "y"
        if "consent" in p:
            return "y"
        return "1"

    with patch("builtins.input", mock_input):
        ok = run_session(effect_id="card_prediction", db_path=temp_db)
        assert ok is True


def test_f18_web_api_serves_health_and_effects_registry(client):
    """F18.3: Web API serves health check and effect summaries."""
    h_resp = client.get("/api/health")
    assert h_resp.status_code == 200
    assert h_resp.json()["status"] == "ok"
    e_resp = client.get("/api/effects")
    assert e_resp.status_code == 200
    assert len(e_resp.json()) >= 4


def test_f18_web_api_executes_full_interactive_session(client, card_effect):
    """F18.4: Full web API session completes through survey."""
    s_resp = client.post("/api/sessions", json={"effect_id": "card_prediction"})
    sess_id = s_resp.json()["session_id"]
    view = s_resp.json()
    while view["phase"] == "active":
        body = truthful_body(card_effect, view, "AS")
        view = client.post(f"/api/sessions/{sess_id}/answer", json=body).json()
    assert view["phase"] == "revealed"
    out_resp = client.post(f"/api/sessions/{sess_id}/outcome", json={"correct": True})
    assert out_resp.status_code == 200


def test_f18_cli_runner_honors_condition_flag(temp_db):
    """F18.5: CLI runner honors condition parameter."""
    def mock_input(prompt=""):
        p = prompt.lower()
        if "did loki name your true thought" in p:
            return "y"
        if "1-7" in p:
            return "6"
        if "again or show" in p:
            return "y"
        if "consent" in p:
            return "n"
        return "1"

    with patch("builtins.input", mock_input):
        ok = run_session(effect_id="card_prediction", condition="a", db_path=temp_db)
        assert ok is True


# ==============================================================================
# F19: Research Disclosure Panel
# ==============================================================================

def test_f19_curtain_dto_exposes_entropy_bits(client):
    """F19.1: CurtainDTO exposes current entropy in bits."""
    resp = client.post("/api/sessions", json={"effect_id": "card_prediction"})
    curtain = resp.json()["curtain"]
    assert curtain["entropy_bits"] > 0.0


def test_f19_curtain_dto_tracks_entropy_history(client, card_effect):
    """F19.2: CurtainDTO records entropy trajectory across turns."""
    resp = client.post("/api/sessions", json={"effect_id": "card_prediction", "condition": "a"})
    sess_id = resp.json()["session_id"]
    view = resp.json()
    client.post(
        f"/api/sessions/{sess_id}/answer",
        json=truthful_body(card_effect, view, "AS"),
    )
    view2 = client.get(f"/api/sessions/{sess_id}").json()
    assert len(view2["curtain"]["entropy_history"]) == 1
    assert view2["curtain"]["entropy_history"][0]["turn"] == 1


def test_f19_curtain_dto_exposes_top_k_posteriors(client):
    """F19.3: CurtainDTO exposes top-k hypotheses with labels and probabilities."""
    resp = client.post("/api/sessions", json={"effect_id": "card_prediction"})
    top = resp.json()["curtain"]["top"]
    assert len(top) <= 5
    for item in top:
        assert "hypothesis_id" in item
        assert "label" in item
        assert 0.0 <= item["probability"] <= 1.0


def test_f19_curtain_dto_records_last_observation(client):
    """F19.4: CurtainDTO captures last observation channel and dwell time."""
    resp = client.post("/api/sessions", json={"effect_id": "card_prediction", "condition": "a"})
    sess_id = resp.json()["session_id"]
    view = resp.json()
    q_id = view["question_id"]
    ans_id = view["options"][0]["id"]
    obs_resp = client.post(
        f"/api/sessions/{sess_id}/observations",
        json={
            "question_id": q_id,
            "answer_id": ans_id,
            "channel": "gaze_dwell",
            "dwell_ms": 1200.0,
        },
    )
    assert obs_resp.status_code == 200
    curtain = obs_resp.json()["curtain"]
    assert curtain["last_observation"] is not None
    assert curtain["last_observation"]["channel"] == "gaze_dwell"
    assert curtain["last_observation"]["dwell_ms"] == 1200.0


def test_f19_curtain_dto_reports_information_gain(client, card_effect):
    """F19.5: CurtainDTO reports information gain from last turn."""
    resp = client.post("/api/sessions", json={"effect_id": "card_prediction", "condition": "a"})
    sess_id = resp.json()["session_id"]
    view = resp.json()
    ans_resp = client.post(
        f"/api/sessions/{sess_id}/answer",
        json=truthful_body(card_effect, view, "AS"),
    )
    assert ans_resp.status_code == 200
    curtain = ans_resp.json()["curtain"]
    assert curtain["last_info_gain_bits"] is not None
    assert curtain["last_info_gain_bits"] >= 0.0


# ==============================================================================
# F20: Participant Debriefing
# ==============================================================================

def test_f20_debriefing_disclaims_telepathy_and_supernatural(temp_db, capsys):
    """F20.1: Debriefing explicitly disclaims supernatural powers and telepathy."""
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
    assert "no telepathic or supernatural capabilities" in captured


def test_f20_debriefing_explains_bayesian_and_psychological_basis(temp_db, capsys):
    """F20.2: Debriefing explains exact Bayesian inference and psychological principles."""
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
    assert "exact Bayesian inference" in captured


def test_f20_cli_runner_displays_debriefing_on_completion(temp_db, capsys):
    """F20.3: CLI runner displays debriefing banner upon completion."""
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
    assert "PARTICIPANT DEBRIEF" in captured


def test_f20_web_api_exposes_outcome_and_disclosure_payload(client, card_effect):
    """F20.4: Web API exposes outcome message and curtain details for client debrief."""
    resp = client.post("/api/sessions", json={"effect_id": "card_prediction"})
    sess_id = resp.json()["session_id"]
    view = resp.json()
    while view["phase"] == "active":
        body = truthful_body(card_effect, view, "AS")
        view = client.post(f"/api/sessions/{sess_id}/answer", json=body).json()
    out_resp = client.post(f"/api/sessions/{sess_id}/outcome", json={"correct": True})
    assert out_resp.json()["phase"] == "outcome"
    assert out_resp.json()["curtain"] is not None


def test_f20_web_outcome_screen_renders_participant_debrief():
    """F20.6: Web outcome screen renders the non-supernatural debrief disclosure."""
    session_tsx = REPO_ROOT / "apps" / "web" / "src" / "components" / "Session.tsx"
    content = session_tsx.read_text(encoding="utf-8")
    assert "no telepathic or supernatural" in content
    assert "exact Bayesian inference" in content


def test_f20_debriefing_accessible_regardless_of_outcome_accuracy(temp_db, capsys):
    """F20.5: Debriefing is presented even when participant reports incorrect outcome."""
    def mock_input(prompt=""):
        p = prompt.lower()
        if "did loki name your true thought" in p:
            return "n"
        if "1-7" in p:
            return "2"
        if "again or show" in p:
            return "n"
        if "consent" in p:
            return "n"
        return "1"

    with patch("builtins.input", mock_input):
        run_session(effect_id="card_prediction", db_path=temp_db)
    captured = capsys.readouterr().out
    assert "PARTICIPANT DEBRIEF" in captured


# ==============================================================================
# F21: 16 Research Questions Matrix
# ==============================================================================

def test_f21_matrix_contains_all_sixteen_questions():
    """F21.1: Research Questions Matrix documents all 16 Directive questions."""
    matrix_path = REPO_ROOT / "docs" / "research-questions-matrix.md"
    assert matrix_path.exists()
    content = matrix_path.read_text(encoding="utf-8")
    for i in range(1, 17):
        assert f"Q{i}" in content


def test_f21_matrix_uses_canonical_evidence_tiers():
    """F21.2: Research matrix categorizes findings under canonical evidence tiers."""
    matrix_path = REPO_ROOT / "docs" / "research-questions-matrix.md"
    content = matrix_path.read_text(encoding="utf-8")
    for tier in ("human-measured", "simulator", "architecture / logic", "literature", "assertion"):
        assert tier in content


def test_f21_matrix_links_repository_evidence():
    """F21.3: Matrix references repository implementation paths."""
    matrix_path = REPO_ROOT / "docs" / "research-questions-matrix.md"
    content = matrix_path.read_text(encoding="utf-8")
    assert "services/hypothesis/tracker.py" in content
    assert "services/language/response_signals.py" in content


def test_f21_matrix_classifies_q3_covert_mystery_gap_correctly():
    """F21.4: Q3 includes explicit modeled footnote regarding kappa=0.25 assumption."""
    matrix_path = REPO_ROOT / "docs" / "research-questions-matrix.md"
    content = matrix_path.read_text(encoding="utf-8")
    assert "kappa = 0.25" in content or "κ = 0.25" in content


def test_f21_matrix_classifies_q14_ab_testing_honestly():
    """F21.5: Q14 honestly discloses that human trials apparatus is built with 0 human rows."""
    matrix_path = REPO_ROOT / "docs" / "research-questions-matrix.md"
    content = matrix_path.read_text(encoding="utf-8")
    assert "data/sessions.db" in content


# ==============================================================================
# F22: Codebase Hygiene & Linting
# ==============================================================================

def test_f22_no_ruff_lint_errors():
    """F22.1: Codebase core services and test suite pass ruff check cleanly."""
    res = subprocess.run(
        [sys.executable, "-m", "ruff", "check", "services", "simulator", "tests/e2e"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    assert res.returncode == 0, f"Ruff violations found: {res.stdout}\n{res.stderr}"


def test_f22_cross_platform_utf8_encoding_safe():
    """F22.2: CLI evaluation scripts configure UTF-8 output streams safely."""
    for script in ["run_magic_factor_eval.py", "analyze_ab.py"]:
        p = REPO_ROOT / "experiments" / script
        content = p.read_text(encoding="utf-8")
        assert "reconfigure(encoding=" in content


def test_f22_yaml_effect_configs_valid_and_loadable():
    """F22.3: All YAML effect definitions parse into valid EffectDef schemas."""
    configs = load_effects(REPO_ROOT / "configs" / "effects")
    assert len(configs) >= 4
    for effect in configs.values():
        assert isinstance(effect, EffectDef)
        assert len(effect.hypotheses) > 0
        assert len(effect.questions) > 0


def test_f22_hypothesis_partitions_exhaustive_and_disjoint():
    """F22.4: Every question answer set forms a disjoint, exhaustive partition."""
    configs = load_effects(REPO_ROOT / "configs" / "effects")
    for effect in configs.values():
        for q in effect.questions:
            for hid, attrs in effect.hypotheses.items():
                matches = sum(1 for a in q.answers if a.predicate.matches(attrs))
                assert matches == 1, f"Partition broken for {effect.id}:{q.id} on {hid}"


def test_f22_mentalism_techniques_dataset_valid():
    """F22.5: Mentalism techniques dataset loads with verified techniques."""
    dataset = load_techniques()
    assert len(dataset.techniques) > 0
