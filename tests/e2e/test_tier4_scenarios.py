"""Tier 4: Real-World Application Scenarios (End-to-End Séance Flows).

Implements the 5 complete end-to-end lifecycle verification pipelines
defined in TEST_INFRA.md §6:
1. Scenario 1: Complete Séance Lifecycle Condition A (Unadorned Baseline)
2. Scenario 2: Complete Séance Lifecycle Condition B (Full Mentalist Engine)
3. Scenario 3: Complete GDPR Consent & Deletion Lifecycle
4. Scenario 4: Multi-Profile Population Simulation Pipeline
5. Scenario 5: Full A/B Human Trial Analysis Pipeline
"""

from __future__ import annotations

import math
import random
import sqlite3
from pathlib import Path
from typing import Any

from experiments.analyze_ab import analyze
from experiments.estimate_visibility import (
    compute_breakeven_kappa,
    estimate_kappa_from_surveys,
)
from services.api.archive import SessionArchive
from services.effects.engine import EffectSession, Phase
from services.language.renderer import LanguageRenderer
from simulator.participant import TruthfulNoisyParticipant
from simulator.profiles import PROFILES, Profile
from tests.e2e.conftest import truthful_answer, truthful_body


# ==============================================================================
# Scenario 1: Complete Séance Lifecycle Condition A (Unadorned Baseline)
# ==============================================================================
def test_scenario_1_complete_seance_lifecycle_condition_a_unadorned_baseline(
    client, card_effect, temp_db: Path
):
    """Scenario 1: Complete Séance Lifecycle Condition A (Unadorned Baseline).

    Verifies:
    - Session created with condition "a".
    - Zero covert turns and zero visual choice forcing across the entire session.
    - All questions answered truthfully until the reveal phase.
    - Unadorned direct reveal message and prediction.
    - Correct outcome report.
    - Rejection of survey submission before outcome phase (HTTP 409).
    - Valid 4-item Likert survey submission stored with condition "a".
    - Ledger records both the survey and the session summary in SQLite.
    """
    # 1. Create Condition A session
    create_resp = client.post(
        "/api/sessions", json={"effect_id": "card_prediction", "condition": "a"}
    )
    assert create_resp.status_code == 201
    view = create_resp.json()
    session_id = view["session_id"]
    assert view["condition"] == "a"
    assert view["phase"] == "active"

    # 2. Attempt survey submission before outcome phase -> verify rejection (HTTP 409)
    early_survey = {
        "impossibility": 3,
        "freedom": 6,
        "naturalness": 6,
        "surprise": 3,
        "willing_repeat": 0,
    }
    rejected_survey_1 = client.post(f"/api/sessions/{session_id}/survey", json=early_survey)
    assert rejected_survey_1.status_code == 409

    # 3. Step through turns: verify baseline constraints (zero covert, zero forcing)
    target_hypothesis = "AS"  # Ace of Spades
    turns_executed = 0

    while view["phase"] == "active":
        assert view["mode"] == "direct", (
            f"Condition A turn {turns_executed} must be direct; got '{view['mode']}'"
        )
        assert view["salient_option_id"] is None, (
            f"Condition A turn {turns_executed} must have zero choice forcing; "
            f"got '{view['salient_option_id']}'"
        )
        assert view["asserted_label"] is None, (
            f"Condition A turn {turns_executed} must not have asserted_label"
        )

        body = truthful_body(card_effect, view, target_hypothesis)
        ans_resp = client.post(f"/api/sessions/{session_id}/answer", json=body)
        assert ans_resp.status_code == 200
        view = ans_resp.json()
        turns_executed += 1

    # 4. Verify unadorned direct reveal message and prediction
    assert view["phase"] == "revealed"
    assert view["reveal_path"] == "plain"
    assert view["reveal_stages"] == []
    assert view["prediction"] is not None
    assert view["prediction"]["hypothesis_id"] == target_hypothesis
    assert view["message"] != ""

    # Verify survey is still rejected in revealed phase before outcome is reported
    rejected_survey_2 = client.post(f"/api/sessions/{session_id}/survey", json=early_survey)
    assert rejected_survey_2.status_code == 409

    # 5. Report outcome as correct
    outcome_resp = client.post(f"/api/sessions/{session_id}/outcome", json={"correct": True})
    assert outcome_resp.status_code == 200
    view = outcome_resp.json()
    assert view["phase"] == "outcome"

    # 6. Submit valid 4-item Likert survey -> verify stored with condition "a"
    survey_payload = {
        "impossibility": 3,
        "freedom": 6,
        "naturalness": 5,
        "surprise": 2,
        "willing_repeat": 0,
    }
    surv_resp = client.post(f"/api/sessions/{session_id}/survey", json=survey_payload)
    assert surv_resp.status_code == 201
    surv_data = surv_resp.json()
    assert surv_data["session_id"] == session_id
    assert surv_data["condition"] == "a"
    assert surv_data["impossibility"] == 3
    assert surv_data["freedom"] == 6
    assert surv_data["naturalness"] == 5
    assert surv_data["surprise"] == 2
    assert surv_data["willing_repeat"] == 0

    # 7. Explicit archive call
    arch_resp = client.post(f"/api/sessions/{session_id}/archive")
    assert arch_resp.status_code == 200
    assert arch_resp.json()["archived"] is True

    # 8. Confirm ledger records survey and session in SQLite
    list_resp = client.get("/api/archive")
    assert list_resp.status_code == 200
    assert any(s["session_id"] == session_id for s in list_resp.json())

    conn = sqlite3.connect(temp_db)
    cur = conn.cursor()
    cur.execute(
        "SELECT turns_used, correct, prediction_id FROM sessions WHERE session_id = ?",
        (session_id,),
    )
    sess_row = cur.fetchone()
    assert sess_row is not None
    assert sess_row[0] == turns_executed
    assert sess_row[1] == 1
    assert sess_row[2] == target_hypothesis

    cur.execute(
        "SELECT condition, impossibility, freedom, naturalness, surprise, willing_repeat "
        "FROM surveys WHERE session_id = ?",
        (session_id,),
    )
    surv_row = cur.fetchone()
    assert surv_row is not None
    assert surv_row[0] == "a"
    assert surv_row[1] == 3
    assert surv_row[2] == 6
    assert surv_row[3] == 5
    assert surv_row[4] == 2
    assert surv_row[5] == 0
    conn.close()


# ==============================================================================
# Scenario 2: Complete Séance Lifecycle Condition B (Full Mentalist Engine)
# ==============================================================================
def test_scenario_2_complete_seance_lifecycle_condition_b_full_mentalist_engine(
    client, card_effect, temp_db: Path
):
    """Scenario 2: Complete Séance Lifecycle Condition B (Full Mentalist Engine).

    Verifies:
    - Session created with condition "b" on card_prediction.
    - Interaction through covert cold reads, direct questions, and choice forcing.
    - Passive telemetry provided (latency, typing rhythm, gaze dwell observations).
    - Multi-stage reveal ladder beats and hesitation support.
    - Correct outcome reporting.
    - Research Disclosure Curtain exposing live entropy trajectory, top hypotheses,
      and observation telemetry.
    - Consented Likert survey stored with condition "b" and verified in persistent ledger.
    """
    # 1. Create Condition B session
    create_resp = client.post(
        "/api/sessions", json={"effect_id": "card_prediction", "condition": "b"}
    )
    assert create_resp.status_code == 201
    view = create_resp.json()
    session_id = view["session_id"]
    assert view["condition"] == "b"
    assert view["phase"] == "active"

    target_hypothesis = "AH"  # Ace of Hearts: red, ace, hearts
    target_attrs = card_effect.hypotheses[target_hypothesis]

    covert_turns = 0
    direct_turns = 0
    observations_applied = 0

    # 2. Step through turns with passive telemetry
    while view["phase"] == "active":
        if view["mode"] == "covert":
            covert_turns += 1
            assert view["asserted_label"] is not None
            # Evaluate whether the asserted reading holds for the target card
            q = next(q for q in card_effect.questions if q.id == view["question_id"])
            asserted_answer = next(a for a in q.answers if a.label == view["asserted_label"])
            holds = asserted_answer.predicate.matches(target_attrs)

            # Reply with natural language text and typing rhythm telemetry
            phrase = "that's right" if holds else "not really"
            ans_payload = {
                "free_text": phrase,
                "latency_ms": 1400.0,
                "typing_rhythm": {
                    "first_key_ms": 700.0,
                    "median_interval_ms": 115.0,
                    "total_ms": 1350.0,
                },
            }
            ans_resp = client.post(f"/api/sessions/{session_id}/answer", json=ans_payload)
            assert ans_resp.status_code == 200
            view = ans_resp.json()
        else:
            direct_turns += 1
            q = next(q for q in card_effect.questions if q.id == view["question_id"])
            truth_ans_id = truthful_answer(card_effect, q, target_hypothesis)

            # Supply passive non-verbal observation (gaze dwell)
            obs_payload = {
                "question_id": q.id,
                "answer_id": truth_ans_id,
                "channel": "gaze_dwell",
                "dwell_ms": 1150.0,
            }
            obs_resp = client.post(
                f"/api/sessions/{session_id}/observations", json=obs_payload
            )
            assert obs_resp.status_code == 200
            observations_applied += 1
            view = obs_resp.json()

            # Follow with verbal response and latency telemetry
            ans_payload = {
                "answer_id": truth_ans_id,
                "latency_ms": 1250.0,
            }
            ans_resp = client.post(f"/api/sessions/{session_id}/answer", json=ans_payload)
            assert ans_resp.status_code == 200
            view = ans_resp.json()

    # 3. Verify transition to reveal phase and structured multiple-outs staging
    assert view["phase"] == "revealed"
    assert view["prediction"] is not None
    assert view["prediction"]["hypothesis_id"] == target_hypothesis
    assert view["reveal_path"] in (
        "progressive",
        "category_cluster",
        "dual_deduction",
        "plain",
    )
    if view["reveal_stages"]:
        assert any(
            stage["kind"] in ("category", "attribute", "deduction")
            for stage in view["reveal_stages"]
        )
    assert covert_turns >= 1, "Condition B should execute at least one covert fishing turn"
    assert observations_applied >= 1, "Passive observations should have been applied"

    # 4. Report outcome as correct
    outcome_resp = client.post(f"/api/sessions/{session_id}/outcome", json={"correct": True})
    assert outcome_resp.status_code == 200
    view = outcome_resp.json()
    assert view["phase"] == "outcome"

    # 5. Inspect Research Disclosure Curtain
    curtain = view["curtain"]
    assert curtain["entropy_bits"] < curtain["initial_entropy_bits"]
    assert len(curtain["entropy_history"]) >= 2
    assert len(curtain["top"]) <= 5
    assert any(h["hypothesis_id"] == target_hypothesis for h in curtain["top"])
    assert curtain["last_observation"] is not None
    assert curtain["last_observation"]["channel"] == "gaze_dwell"
    assert curtain["last_observation"]["dwell_ms"] == 1150.0

    # 6. Submit survey and verify stored with condition "b"
    survey_payload = {
        "impossibility": 7,
        "freedom": 6,
        "naturalness": 7,
        "surprise": 7,
        "willing_repeat": 1,
    }
    surv_resp = client.post(f"/api/sessions/{session_id}/survey", json=survey_payload)
    assert surv_resp.status_code == 201
    surv_data = surv_resp.json()
    assert surv_data["session_id"] == session_id
    assert surv_data["condition"] == "b"
    assert surv_data["impossibility"] == 7
    assert surv_data["willing_repeat"] == 1

    # 7. Explicit archive call & database check
    arch_resp = client.post(f"/api/sessions/{session_id}/archive")
    assert arch_resp.status_code == 200

    conn = sqlite3.connect(temp_db)
    cur = conn.cursor()
    cur.execute("SELECT condition FROM surveys WHERE session_id = ?", (session_id,))
    assert cur.fetchone()[0] == "b"
    cur.execute("SELECT prediction_id, correct FROM sessions WHERE session_id = ?", (session_id,))
    sess_row = cur.fetchone()
    assert sess_row[0] == target_hypothesis
    assert sess_row[1] == 1
    conn.close()


# ==============================================================================
# Scenario 3: Complete GDPR Consent & Deletion Lifecycle
# ==============================================================================
def test_scenario_3_complete_gdpr_consent_and_deletion_lifecycle(
    client, number_effect, temp_db: Path
):
    """Scenario 3: Complete GDPR Consent & Deletion Lifecycle.

    Verifies:
    - Execution of a full interactive séance and survey submission.
    - Verified existence of persistent records across both sessions and surveys tables.
    - Invocations of DELETE /api/archive/{session_id} returning HTTP 204 No Content.
    - Confirmed immediate hard purge from both SQLite tables with 0 residual records.
    - GET /api/archive confirms zero remaining traces of the session.
    - Subsequent deletion attempts return HTTP 404.
    """
    # 1. Execute a full interactive séance on number_prediction
    create_resp = client.post(
        "/api/sessions", json={"effect_id": "number_prediction", "condition": "b"}
    )
    assert create_resp.status_code == 201
    session_id = create_resp.json()["session_id"]
    target_num = "7"

    while True:
        curr = client.get(f"/api/sessions/{session_id}").json()
        if curr["phase"] != "active":
            break
        body = truthful_body(number_effect, curr, target_num)
        ans_resp = client.post(f"/api/sessions/{session_id}/answer", json=body)
        assert ans_resp.status_code == 200

    # Report outcome
    client.post(f"/api/sessions/{session_id}/outcome", json={"correct": True})

    # Submit consent-gated survey
    surv_payload = {
        "impossibility": 6,
        "freedom": 5,
        "naturalness": 5,
        "surprise": 6,
        "willing_repeat": 1,
    }
    surv_resp = client.post(f"/api/sessions/{session_id}/survey", json=surv_payload)
    assert surv_resp.status_code == 201

    # Archive session
    arch_resp = client.post(f"/api/sessions/{session_id}/archive")
    assert arch_resp.status_code == 200

    # 2. Verify records exist in SQLite ledger
    conn = sqlite3.connect(temp_db)
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM sessions WHERE session_id = ?", (session_id,))
    assert cur.fetchone()[0] == 1
    cur.execute("SELECT COUNT(*) FROM surveys WHERE session_id = ?", (session_id,))
    assert cur.fetchone()[0] == 1
    conn.close()

    # 3. Send DELETE /api/archive/{session_id}
    del_resp = client.delete(f"/api/archive/{session_id}")
    assert del_resp.status_code == 204

    # 4. Confirm immediate hard purge from both tables
    conn = sqlite3.connect(temp_db)
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM sessions WHERE session_id = ?", (session_id,))
    assert cur.fetchone()[0] == 0
    cur.execute("SELECT COUNT(*) FROM surveys WHERE session_id = ?", (session_id,))
    assert cur.fetchone()[0] == 0
    conn.close()

    # 5. Query GET /api/archive and confirm zero traces remain
    list_resp = client.get("/api/archive")
    assert list_resp.status_code == 200
    assert not any(s["session_id"] == session_id for s in list_resp.json())

    # 6. Subsequent deletion attempt returns HTTP 404
    del_resp_retry = client.delete(f"/api/archive/{session_id}")
    assert del_resp_retry.status_code == 404


# ==============================================================================
# Scenario 4: Multi-Profile Population Simulation Pipeline
# ==============================================================================
def _simulate_single_session(
    effect,
    profile: Profile,
    truth_id: str,
    rng: random.Random,
    renderer: LanguageRenderer,
) -> dict[str, Any]:
    """Helper to simulate an entire session for a specific participant profile."""
    participant = TruthfulNoisyParticipant(
        effect,
        truth_id,
        rng,
        reliability_override=profile.reliability,
        gaze_prob=profile.gaze_prob,
        gaze_accuracy=profile.gaze_accuracy,
        force_susceptibility=profile.force_susceptibility,
        p_fast_truthful=profile.p_fast_truthful,
        p_fast_guess=profile.p_fast_guess,
        fishing_evasiveness=profile.fishing_evasiveness,
    )
    session = EffectSession(effect, renderer)
    force_presented = 0
    force_followed = 0

    while session.phase is Phase.ACTIVE:
        question = session.current_question
        if session.current_mode == "covert":
            strength, latency = participant.respond_to_fishing(
                question, session.asserted_answer_id
            )
            session.respond_agreement(strength, latency_ms=latency)
        else:
            look = participant.look(question)
            if look is not None and "gaze_dwell" in effect.observations:
                session.observe(question.id, look[0], "gaze_dwell", dwell_ms=look[1])
            salient = session.current_force_target
            if salient is not None:
                force_presented += 1
            ans_id, latency = participant.answer_with_latency(question, salient)
            if salient is not None and ans_id == salient:
                force_followed += 1
            session.answer(ans_id, latency_ms=latency)

    assert session.prediction is not None
    is_correct = session.prediction.hypothesis_id == truth_id
    return {
        "correct": is_correct,
        "turns": session.turn,
        "prediction_id": session.prediction.hypothesis_id,
        "force_presented": force_presented,
        "force_followed": force_followed,
    }


def _run_population_sweep(registry, seed: int, reps_per_pair: int = 2) -> dict:
    """Execute the simulation matrix across all 6 profiles and 4 effects."""
    rng = random.Random(seed)
    renderer = LanguageRenderer("repro-test-renderer")
    effects = [
        "animal_guess",
        "card_prediction",
        "number_prediction",
        "sigil_forced_choice",
    ]
    results = {}
    for profile_name in (
        "balanced",
        "impulsive",
        "cautious",
        "suggestible",
        "evasive",
        "adversarial",
    ):
        profile = PROFILES[profile_name]
        for effect_id in effects:
            eff = registry[effect_id]
            hyps = list(eff.hypotheses)
            trials = []
            for _ in range(reps_per_pair):
                truth_id = rng.choice(hyps)
                res = _simulate_single_session(eff, profile, truth_id, rng, renderer)
                trials.append(res)
            results[(profile_name, effect_id)] = trials
    return results


def test_scenario_4_multi_profile_population_simulation_pipeline(registry, card_effect, renderer):
    """Scenario 4: Multi-Profile Population Simulation Pipeline.

    Verifies:
    - Seeded simulation across all 6 synthetic participant profiles on all 4 effect domains.
    - Deterministic bit-identical reproducibility between independent runs with the same seed.
    - Expected behavioral stratification:
        * Cautious profile (high reliability) yields significantly higher accuracy than Adversarial.
        * Adversarial profile (0.15 reliability) yields low top-1 accuracy.
        * Suggestible profile complies with choice-forcing salient targets.
    """
    # 1. Verify all 6 profiles exist with documented parameters
    profile_names = {"balanced", "impulsive", "cautious", "suggestible", "evasive", "adversarial"}
    assert set(PROFILES.keys()) == profile_names

    # 2. Run population simulation twice with identical seed -> verify bit-identical reproducibility
    run_a = _run_population_sweep(registry, seed=42, reps_per_pair=2)
    run_b = _run_population_sweep(registry, seed=42, reps_per_pair=2)
    assert run_a == run_b, "Seeded simulation must be bit-identical across runs"

    # 3. Behavioral stratification verification: Cautious vs Adversarial
    # Cautious profile (0.98 reliability) vs Adversarial profile (0.15 reliability)
    # evaluated on card_prediction
    cautious_rng = random.Random(777)
    cautious_trials = [
        _simulate_single_session(
            card_effect,
            PROFILES["cautious"],
            cautious_rng.choice(list(card_effect.hypotheses)),
            cautious_rng,
            renderer,
        )
        for _ in range(12)
    ]
    cautious_accuracy = sum(1 for t in cautious_trials if t["correct"]) / len(cautious_trials)

    adversarial_rng = random.Random(777)
    adversarial_trials = [
        _simulate_single_session(
            card_effect,
            PROFILES["adversarial"],
            adversarial_rng.choice(list(card_effect.hypotheses)),
            adversarial_rng,
            renderer,
        )
        for _ in range(12)
    ]
    adversarial_accuracy = sum(
        1 for t in adversarial_trials if t["correct"]
    ) / len(adversarial_trials)

    assert cautious_accuracy >= 0.80, (
        f"Cautious accuracy {cautious_accuracy} should be >= 0.80"
    )
    assert adversarial_accuracy <= 0.35, (
        f"Adversarial accuracy {adversarial_accuracy} should be <= 0.35"
    )
    assert cautious_accuracy > adversarial_accuracy

    # 4. Behavioral stratification: Suggestible profile choice-forcing compliance
    assert PROFILES["suggestible"].force_susceptibility == 0.50
    sugg_rng = random.Random(888)
    q = card_effect.questions[0]
    sugg_participant = TruthfulNoisyParticipant(
        card_effect,
        "AH",
        sugg_rng,
        reliability_override=PROFILES["suggestible"].reliability,
        force_susceptibility=PROFILES["suggestible"].force_susceptibility,
    )
    salient_id = [
        a.id for a in q.answers if not a.predicate.matches(card_effect.hypotheses["AH"])
    ][0]
    forced_selections = sum(
        1
        for _ in range(25)
        if sugg_participant.answer(q, salient_answer_id=salient_id) == salient_id
    )
    assert forced_selections > 0, "Suggestible participant should follow salient force target"


# ==============================================================================
# Scenario 5: Full A/B Human Trial Analysis Pipeline
# ==============================================================================
def test_scenario_5_full_ab_human_trial_analysis_pipeline(temp_db: Path):
    """Scenario 5: Full A/B Human Trial Analysis Pipeline.

    Verifies:
    - Balanced ledger population with Condition A and Condition B survey records.
    - Execution of statistical hypothesis testing via analyze_ab
      (Welch's t, Mann-Whitney U, bootstrap CIs).
    - Execution of empirical visibility estimation via estimate_visibility
      (point estimate, bootstrap CI).
    - Verified extraction of manipulation checks and breakeven kappa* computation.
    """
    archive = SessionArchive(temp_db)
    rng = random.Random(12345)
    sample_size = 25

    # 1. Populate ledger with balanced Condition A (baseline) and Condition B (mentalist) records
    for i in range(sample_size):
        surv_a = {
            "impossibility": rng.randint(2, 4),
            "freedom": rng.randint(5, 7),
            "naturalness": rng.randint(5, 7),
            "surprise": rng.randint(2, 4),
            "willing_repeat": 1 if rng.random() < 0.35 else 0,
        }
        archive.save_survey(
            f"sess_trial_a_{i}", "a", surv_a, f"2026-10-01T10:{i:02d}:00Z"
        )

        surv_b = {
            "impossibility": rng.randint(5, 7),
            "freedom": rng.randint(3, 5),
            "naturalness": rng.randint(4, 6),
            "surprise": rng.randint(5, 7),
            "willing_repeat": 1 if rng.random() < 0.85 else 0,
        }
        archive.save_survey(
            f"sess_trial_b_{i}", "b", surv_b, f"2026-10-01T11:{i:02d}:00Z"
        )

    # Populate matching sessions table records for manipulation check joins
    conn = sqlite3.connect(temp_db)
    cur = conn.cursor()
    for i in range(sample_size):
        cur.execute(
            """
            INSERT INTO sessions
            (session_id, effect_id, created_at, turns_used, prediction_id,
             prediction_label, confidence, correct, committed_because, events_json)
            VALUES (?, 'card_prediction', '2026-10-01T10:00:00Z', 5, 'AS',
                    'Ace of Spades', 0.95, 1, 'entropy_threshold', '[]')
            """,
            (f"sess_trial_a_{i}",),
        )
        cur.execute(
            """
            INSERT INTO sessions
            (session_id, effect_id, created_at, turns_used, prediction_id,
             prediction_label, confidence, correct, committed_because, events_json)
            VALUES (?, 'card_prediction', '2026-10-01T11:00:00Z', 4, 'AH',
                    'Ace of Hearts', 0.98, 1, 'entropy_threshold', '[]')
            """,
            (f"sess_trial_b_{i}",),
        )
    conn.commit()
    conn.close()

    # 2. Retrieve survey rows joined with session outcomes
    rows = archive.survey_rows()
    rows_a = [r for r in rows if r["condition"] == "a"]
    rows_b = [r for r in rows if r["condition"] == "b"]
    assert len(rows_a) == sample_size
    assert len(rows_b) == sample_size

    # 3. Execute A/B statistical test suite
    report = analyze(rows)
    assert report["n"]["a"] == sample_size
    assert report["n"]["b"] == sample_size

    # Impossibility rating: condition B must demonstrate statistically significant lift
    imp = report["impossibility"]
    assert imp["mean_b"] > imp["mean_a"]
    assert imp["p_normal_approx"] < 0.001
    assert imp["mann_whitney_u"] >= 0
    assert imp["ci_a"][0] <= imp["ci_a"][1]
    assert imp["ci_b"][0] <= imp["ci_b"][1]
    assert not math.isnan(imp["welch_t"])

    # Surprise rating: condition B exceeds condition A
    surp = report["surprise"]
    assert surp["mean_b"] > surp["mean_a"]

    # Manipulation checks: both arms achieved 100% objective accuracy
    assert report["accuracy_a"] == 1.0
    assert report["accuracy_b"] == 1.0

    # 4. Execute empirical visibility estimator
    est = estimate_kappa_from_surveys(rows_a, rows_b, reps=1000)
    assert est.sample_size == sample_size * 2
    assert 0.0 <= est.point_estimate <= 1.0
    assert est.ci_lower <= est.ci_upper
    assert est.method == "likert_interrogation_ratio"

    # 5. Breakeven kappa* calculation
    kappa_star = compute_breakeven_kappa(
        acc_auto=report["accuracy_b"],
        acc_direct=report["accuracy_a"],
        direct_bits_auto=3.2,
        direct_bits_direct=3.9,
        covert_turns_auto=1.2,
    )
    assert kappa_star is not None
    assert not math.isnan(kappa_star)
