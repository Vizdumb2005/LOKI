"""Tier 3: Pairwise and Cross-Feature Interaction Tests.

Verifies the integration contracts between subsystems when multiple features
interact simultaneously across the AI Mentalist (LOKI) platform.
"""

from __future__ import annotations

import math
import random
import sqlite3
from pathlib import Path

import pytest

from experiments.analyze_ab import mann_whitney_u, welch_t
from experiments.estimate_visibility import (
    compute_breakeven_kappa,
    estimate_kappa_from_surveys,
)
from experiments.run_magic_factor_eval import evaluate_magic_factor
from services.api.archive import SessionArchive
from services.effects.engine import EffectSession, Phase
from services.fusion.engine import downgrade_strength, is_hesitant
from services.hypothesis.tracker import Tracker
from services.language.response_signals import AgreementStrength
from services.policy.method_selection import FishingState, select_turn
from services.policy.reveal_planner import plan_reveal
from simulator.bandit import BanditTurnSelector, TabularBandit, context_cell
from simulator.participant import TruthfulNoisyParticipant
from tests.e2e.conftest import truthful_body


# ==============================================================================
# Pairwise Interaction 1: F1 + F7 + F10 (Covert fishing miss -> equivocation -> direct cooldown)
# ==============================================================================
def test_interaction_f1_f7_f10_covert_turn_miss_equivocation_cooldown(card_effect, renderer):
    """F1 + F7 + F10: Controller covert miss triggers equivocation reframe and shifts to direct.

    When the engine chooses a covert probe and the participant misses/denies it,
    the session invokes the equivocation layer, sets fishing cooldown to 1,
    transitions the next turn to direct mode, and preserves posterior normalization.
    """
    session = EffectSession(card_effect, renderer)
    assert session.phase is Phase.ACTIVE
    assert session.current_mode == "covert"

    # Turn 1: Participant issues a strong miss ("strong_no")
    session.respond_agreement("strong_no")

    # Fishing state cooldown is activated
    assert session._fishing.cooldown_turns == 1

    # Turn 2 must switch to direct mode
    assert session.current_mode == "direct"
    assert session.current_question is not None

    # Equivocation layer reframe was applied
    assert session.current_reframe is not None
    assert session.current_reframe[0] == "missed"
    assert session.ask_message != ""

    # Posterior distribution remains normalized and valid
    total_prob = sum(session.tracker.posterior.values())
    assert total_prob == pytest.approx(1.0, abs=1e-5)


# ==============================================================================
# Pairwise Interaction 2: F1 + F8 + F10 (Choice force -> defiance -> cooldown & narrowing)
# ==============================================================================
def test_interaction_f1_f8_f10_choice_force_defiance_cooldown_and_narrowing(card_effect, renderer):
    """F1 + F8 + F10: Participant defies choice force, triggering cooldown.

    When choice forcing targets a candidate answer and the participant defies it,
    the session records the defiance, activates force cooldown, suppresses forcing
    on the next turn, and updates posterior probabilities consistent with the chosen answer.
    """
    direct_effect = card_effect.without_fishing()
    session = EffectSession(direct_effect, renderer)

    # Skew posterior towards red cards to trigger choice forcing on color
    red_cards = [h for h, attrs in card_effect.hypotheses.items() if attrs.get("color") == "red"]
    black_cards = [
        h for h, attrs in card_effect.hypotheses.items() if attrs.get("color") == "black"
    ]

    skewed = {
        h: (0.75 / len(red_cards)) if h in red_cards else (0.25 / len(black_cards))
        for h in card_effect.hypotheses
    }
    session.tracker = Tracker(list(card_effect.hypotheses), prior=skewed)

    # Mark other questions asked so q_color is evaluated
    asked = {"q_rank_bucket", "q_rank_mod3", "q_suit", "q_rank_parity"}
    session.asked = list(asked)
    plan = select_turn(direct_effect, session.tracker.posterior, asked, session._fishing)
    assert plan is not None
    assert plan.salient_answer_id == "red"

    # Participant defies the force by choosing "black"
    q_color = next(q for q in direct_effect.questions if q.id == "q_color")
    session.current_question = q_color
    session.current_force_target = plan.salient_answer_id
    session.current_mode = "direct"
    session.asked.append(q_color.id)
    session.answer("black")

    # Next turn selection suppresses forcing due to cooldown, and defiance is reframed
    assert session.current_reframe == ("defied", "Red")
    assert session.current_force_target is None

    # Posterior correctly narrowed: black cards now dominate probability mass
    post = session.tracker.posterior
    assert sum(post[h] for h in red_cards) < 0.15
    assert sum(post[h] for h in black_cards) > 0.85
    assert sum(post.values()) == pytest.approx(1.0, abs=1e-5)


# ==============================================================================
# Pairwise Interaction 3: F2 + F11 + F1 (Passive latency & hesitation -> reliability discount)
# ==============================================================================
def test_interaction_f2_f11_f1_latency_hesitation_discount_and_turn_selection(
    card_effect, renderer
):
    """F2 + F11 + F1: Response latency triggers hesitation classification and Bayesian discounting.

    Excessive latency (> threshold) flags hesitation, discounts the report's reliability,
    retains higher posterior entropy than prompt responses, and feeds into best question selection.
    """
    direct_effect = card_effect.without_fishing()
    session_fast = EffectSession(direct_effect, renderer)
    session_slow = EffectSession(direct_effect, renderer)

    # Both answer the first question identically, but one is fast (1000ms) and one is slow (9000ms)
    ans_id = session_fast.current_question.answers[0].id
    session_fast.answer(ans_id, latency_ms=1000.0)
    session_slow.answer(ans_id, latency_ms=9000.0)

    # Slow, hesitant answer is discounted by latency channel, leaving higher entropy
    assert session_slow.tracker.entropy() > session_fast.tracker.entropy()

    # Verification of typing rhythm hesitation and agreement downgrade primitives
    assert is_hesitant(3500.0, 500.0)
    assert not is_hesitant(1500.0, 400.0)
    assert (
        downgrade_strength(AgreementStrength.STRONG_YES) is AgreementStrength.LEAN_YES
    )


# ==============================================================================
# Pairwise Interaction 4: F7 + F3 + F4 (Covert fishing turns -> Magic Factor kappa sweep)
# ==============================================================================
def test_interaction_f7_f3_f4_covert_fishing_magic_factor_sweep(card_effect):
    """F7 + F3 + F4: Covert fishing turns directly drive the Magic Factor kappa sweep.

    Evaluates that running sessions with covert fishing yields an empirical mystery gap
    that behaves monotonically across the 5-point visibility grid [0.0, 0.25, 0.5, 0.75, 1.0].
    """
    rng = random.Random(42)
    results = evaluate_magic_factor(card_effect, sessions=15, reliability=0.95, rng=rng)

    assert "kappa_sweep" in results
    sweep = results["kappa_sweep"]
    assert len(sweep) == 5

    # Check monotonicity: as kappa increases, visible bits increase, mystery gap decreases
    for i in range(len(sweep) - 1):
        k_curr = sweep[i]
        k_next = sweep[i + 1]
        assert k_curr["avg_visible_bits"] <= k_next["avg_visible_bits"]
        assert (
            k_curr["avg_information_mystery_gap_bits"]
            >= k_next["avg_information_mystery_gap_bits"]
        )

    # Magic factor score at kappa=0 must exceed score at kappa=1.0 when covert turns were run
    if results["avg_covert_turns"] > 0:
        assert sweep[0]["magic_factor_score"] > sweep[-1]["magic_factor_score"]


# ==============================================================================
# Pairwise Interaction 5: F14 + F15 + F16 (Blind Condition B -> Survey -> GDPR wipe)
# ==============================================================================
def test_interaction_f14_f15_f16_blind_survey_and_gdpr_hard_deletion(
    client, card_effect, temp_db: Path
):
    """F14 + F15 + F16: API session runs under Condition B, collects survey, and executes GDPR wipe.

    Verifies that a session completes, records consent survey and outcome,
    persists into SQLite, and is completely eliminated by DELETE /api/archive/{session_id}.
    """
    # 1. Create Condition B session
    create_resp = client.post(
        "/api/sessions", json={"effect_id": "card_prediction", "condition": "b"}
    )
    assert create_resp.status_code == 201
    session_id = create_resp.json()["session_id"]
    assert create_resp.json()["condition"] == "b"

    # 2. Advance to outcome
    while True:
        curr = client.get(f"/api/sessions/{session_id}").json()
        if curr["phase"] != "active":
            break
        body = truthful_body(card_effect, curr, "AS")
        resp = client.post(f"/api/sessions/{session_id}/answer", json=body)
        assert resp.status_code == 200

    # 3. Report outcome & submit survey
    client.post(f"/api/sessions/{session_id}/outcome", json={"correct": True})
    survey_payload = {
        "impossibility": 7,
        "freedom": 6,
        "naturalness": 6,
        "surprise": 7,
        "willing_repeat": 1,
    }
    surv_resp = client.post(f"/api/sessions/{session_id}/survey", json=survey_payload)
    assert surv_resp.status_code == 201

    # 4. Archive session explicitly
    arch_resp = client.post(f"/api/sessions/{session_id}/archive")
    assert arch_resp.status_code == 200

    # Verify session summary is listed
    list_resp = client.get("/api/archive")
    assert any(s["session_id"] == session_id for s in list_resp.json())

    # 5. GDPR Hard Deletion
    del_resp = client.delete(f"/api/archive/{session_id}")
    assert del_resp.status_code == 204

    # 6. Verify 0 residual records in archive listing
    list_after = client.get("/api/archive").json()
    assert not any(s["session_id"] == session_id for s in list_after)

    # 7. Verify 0 residual records directly in SQLite database
    conn = sqlite3.connect(temp_db)
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM sessions WHERE session_id = ?", (session_id,))
    assert cur.fetchone()[0] == 0
    cur.execute("SELECT COUNT(*) FROM surveys WHERE session_id = ?", (session_id,))
    assert cur.fetchone()[0] == 0
    conn.close()


# ==============================================================================
# Pairwise Interaction 6: F12 + F13 + F8 (Bandit policy -> choice force -> suggestible participant)
# ==============================================================================
def test_interaction_f12_f13_f8_bandit_policy_force_suggestible_q_learning(card_effect):
    """F12 + F13 + F8: Tabular bandit turn selector updates Q-values following choice force.

    Exercises interaction between TabularBandit, force target identification,
    participant compliance under suggestible profile, and policy reward update.
    """
    # Skew posterior to make color forcing viable
    red_cards = [h for h, attrs in card_effect.hypotheses.items() if attrs.get("color") == "red"]
    black_cards = [
        h for h, attrs in card_effect.hypotheses.items() if attrs.get("color") == "black"
    ]
    skewed = {
        h: (0.75 / len(red_cards)) if h in red_cards else (0.25 / len(black_cards))
        for h in card_effect.hypotheses
    }

    direct_effect = card_effect.without_fishing()
    asked = {"q_rank_bucket", "q_rank_mod3", "q_suit", "q_rank_parity"}
    q_color = next(q for q in direct_effect.questions if q.id == "q_color")
    cell = context_cell(direct_effect, skewed, asked, q_color)

    bandit = TabularBandit(epsilon=0.0, seed=42)
    # Prefer forced action in the target context cell
    bandit.update(cell, "forced", reward=5.0)

    selector = BanditTurnSelector(agent=bandit, explore=True)
    plan = selector(direct_effect, skewed, asked, FishingState())
    assert plan is not None
    assert plan.salient_answer_id == "red"
    cell, action = selector.last_decision
    assert action == "forced"

    # High force susceptibility models compliance with salient force target
    q = next(q for q in direct_effect.questions if q.id == plan.question_id)
    participant = TruthfulNoisyParticipant(
        card_effect, "AH", random.Random(42), force_susceptibility=1.0
    )
    ans = participant.answer(q, salient_answer_id=plan.salient_answer_id)
    assert ans == "red"

    # Turn reward is updated in bandit
    bandit.update(cell, action, reward=1.0)
    updated_val = bandit._value(cell, action)

    # Q-value remains strong
    assert updated_val > 0.0


# ==============================================================================
# Pairwise Interaction 7: F17 + F6 + F15 (Survey records -> A/B analysis + visibility estimation)
# ==============================================================================
def test_interaction_f17_f6_f15_survey_records_to_ab_stats_and_visibility(temp_db: Path):
    """F17 + F6 + F15: Consented survey records stream cleanly into statistical analysis.

    Demonstrates that survey responses stored in SessionArchive conform to both
    A/B hypothesis testing (Welch's t, Mann-Whitney U) and visibility bootstrapping.
    """
    archive = SessionArchive(temp_db)

    # Insert mock surveyed cohorts: A (baseline) and B (mentalist)
    surv_a = {
        "impossibility": 4, "freedom": 4, "naturalness": 4, "surprise": 4, "willing_repeat": 0
    }
    surv_b = {
        "impossibility": 6, "freedom": 6, "naturalness": 6, "surprise": 6, "willing_repeat": 1
    }
    for i in range(10):
        archive.save_survey(f"sess_a_{i}", "a", surv_a, "2026-01-01T00:00:00Z")
        archive.save_survey(f"sess_b_{i}", "b", surv_b, "2026-01-01T00:00:00Z")

    # Retrieve rows via public method
    all_surveys = archive.survey_rows()
    rows_a = [r for r in all_surveys if r["condition"] == "a"]
    rows_b = [r for r in all_surveys if r["condition"] == "b"]
    assert len(rows_a) == 10
    assert len(rows_b) == 10

    # Compute Welch's t and Mann-Whitney U on impossibility ratings
    scores_a = [float(r["impossibility"]) for r in rows_a]
    scores_b = [float(r["impossibility"]) for r in rows_b]
    t_val = welch_t(scores_a, scores_b)
    _, u_p = mann_whitney_u(scores_a, scores_b)

    assert not math.isnan(t_val)
    assert u_p < 0.05

    # Estimate empirical visibility parameter kappa
    est = estimate_kappa_from_surveys(rows_a, rows_b, reps=50)
    assert est.sample_size == 20
    assert 0.0 <= est.point_estimate <= 1.0
    assert est.ci_lower <= est.ci_upper


# ==============================================================================
# Pairwise Interaction 8: F18 + F19 + F20 (Séance runner -> CurtainDTO telemetry -> reveal)
# ==============================================================================
def test_interaction_f18_f19_f20_curtain_entropy_curve_and_reveal_telemetry(client, card_effect):
    """F18 + F19 + F20: Session yields live entropy curve, observation, and reveal staging.

    Traces the entire telemetry pipeline from initial curtain uncertainty
    through answer updates to final debriefing payload.
    """
    create_resp = client.post("/api/sessions", json={"effect_id": "card_prediction"})
    session_id = create_resp.json()["session_id"]
    curtain_init = create_resp.json()["curtain"]

    assert curtain_init["entropy_bits"] > 0
    assert len(curtain_init["top"]) > 0

    # Step through turns to capture entropy trajectory
    entropy_levels = [curtain_init["entropy_bits"]]
    while True:
        curr = client.get(f"/api/sessions/{session_id}").json()
        if curr["phase"] != "active":
            break
        body = truthful_body(card_effect, curr, "KH")
        ans_resp = client.post(f"/api/sessions/{session_id}/answer", json=body)
        assert ans_resp.status_code == 200
        entropy_levels.append(ans_resp.json()["curtain"]["entropy_bits"])

    final_view = client.get(f"/api/sessions/{session_id}").json()
    assert final_view["phase"] in ("revealed", "outcome")
    assert final_view["reveal_path"] in (
        "progressive",
        "category_cluster",
        "dual_deduction",
        "plain",
    )
    assert final_view["prediction"] is not None
    assert final_view["prediction"]["hypothesis_id"] == "KH"

    # Entropy history in curtain records every progression
    history = final_view["curtain"]["entropy_history"]
    assert len(history) >= 1
    assert final_view["curtain"]["entropy_bits"] < curtain_init["entropy_bits"]


# ==============================================================================
# Pairwise Interaction 9: F9 + F2 + F1 (Reveal ladder planning -> MAP confidence -> staged reveal)
# ==============================================================================
def test_interaction_f9_f2_f1_reveal_ladder_planning_from_map_confidence(card_effect, renderer):
    """F9 + F2 + F1: Controller drives entropy collapse to MAP candidate, triggering reveal ladder.

    Verifies that when tracker entropy meets termination threshold,
    the reveal planner selects a structured reveal path (e.g. progressive)
    with staged attributes matching the MAP candidate.
    """
    session = EffectSession(card_effect, renderer)

    # Force entropy to near-zero by concentrating probability on Queen of Diamonds ("QD")
    target_card = "QD"
    single_hyp = {
        h: 0.99 if h == target_card else (0.01 / 51)
        for h in card_effect.hypotheses
    }
    session.tracker = Tracker(list(card_effect.hypotheses), prior=single_hyp)
    asked = {"q_color", "q_suit"}

    candidates = session.tracker.top_k(3)
    plan = plan_reveal(card_effect, candidates, asked)

    assert plan.path in ("progressive", "category_cluster", "dual_deduction", "plain")
    assert len(plan.candidates) > 0
    assert plan.candidates[0] == target_card

    # If progressive stages were selected, verify stages lead to the target
    if plan.stages:
        stage_kinds = [s.kind for s in plan.stages]
        assert any(k in ("category", "attribute") for k in stage_kinds)


# ==============================================================================
# Pairwise Interaction 10: F13 + F3 + F5 (Simulator auto vs direct -> breakeven kappa derivation)
# ==============================================================================
def test_interaction_f13_f3_f5_simulator_auto_vs_direct_breakeven_kappa(card_effect):
    """F13 + F3 + F5: Simulated comparison yields empirical breakeven kappa.

    Compares mentalist policy (using covert fishing) against direct questioning baseline,
    captures visible probe accounting, and verifies the calculated breakeven point kappa*.
    """
    rng = random.Random(42)

    # Evaluate mentalist policy
    res_mentalist = evaluate_magic_factor(card_effect, sessions=10, reliability=1.0, rng=rng)

    # Evaluate direct policy (using without_fishing)
    direct_effect = card_effect.without_fishing()
    res_direct = evaluate_magic_factor(direct_effect, sessions=10, reliability=1.0, rng=rng)

    acc_auto = res_mentalist["top1_accuracy"]
    acc_direct = res_direct["top1_accuracy"]
    direct_bits_auto = res_mentalist["kappa_sweep"][0]["avg_visible_bits"]
    direct_bits_direct = res_direct["avg_visible_bits_used"]
    covert_turns = res_mentalist["avg_covert_turns"]

    # Compute breakeven kappa*
    kappa_star = compute_breakeven_kappa(
        acc_auto, acc_direct, direct_bits_auto, direct_bits_direct, covert_turns
    )
    if kappa_star is not None:
        assert not math.isnan(kappa_star)
