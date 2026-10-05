"""Adversarial stress tests for Milestone 1 changes.

Verifies:
1. CLI entrypoint resilience under hostile terminal encodings:
   - cp1252
   - cp437:strict
   - ascii:replace
   Covering:
   - run_bandit_eval.py
   - run_baseline_eval.py
   - run_human_trial.py (both Condition A and Condition B)

2. SessionArchive.delete and HTTP DELETE /api/archive/{id} edge cases:
   - Non-existent session IDs (DB absent, DB empty, DB populated)
   - Injection / malformed session IDs ("", "' OR 1=1 --")
   - Double deletion / idempotence
   - Session with both trajectory and survey (both purged, returns True / 204)
   - Survey-only session without trajectory (survey purged, returns True / 204)
   - Trajectory-only session without survey (trajectory purged, returns True / 204)
   - Multi-session isolation (no collateral deletion)
   - Concurrent deletion race conditions
"""

from __future__ import annotations

import os
import subprocess
import sys
import threading
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from services.api.archive import SessionArchive
from services.api.main import create_app
from services.effects.engine import EffectSession
from services.effects.loader import load_effects
from services.language.renderer import LanguageRenderer

REPO_ROOT = Path(__file__).resolve().parents[1]
EFFECTS_DIR = REPO_ROOT / "configs" / "effects"


# ==============================================================================
# 1. Hostile Terminal Encoding Verification
# ==============================================================================


@pytest.mark.parametrize("encoding", ["cp1252", "cp437:strict", "ascii:replace"])
def test_run_bandit_eval_hostile_encoding(encoding: str):
    """Verify run_bandit_eval executes cleanly under hostile terminal encoding."""
    env = {**os.environ, "PYTHONIOENCODING": encoding}
    cmd = [
        sys.executable,
        "-m",
        "experiments.run_bandit_eval",
        "--episodes",
        "1",
        "--eval-sessions",
        "1",
        "--seed",
        "42",
    ]
    res = subprocess.run(
        cmd,
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=False,
        timeout=30,
    )
    err = res.stderr.decode("utf-8", errors="replace")
    assert res.returncode == 0, f"Failed under {encoding}:\n{err}"
    # Verify stdout was produced and epsilon symbol didn't trigger crash
    assert len(res.stdout) > 0


@pytest.mark.parametrize("encoding", ["cp1252", "cp437:strict", "ascii:replace"])
def test_run_baseline_eval_hostile_encoding(encoding: str):
    """Verify run_baseline_eval executes cleanly under hostile terminal encoding."""
    env = {**os.environ, "PYTHONIOENCODING": encoding}
    cmd = [
        sys.executable,
        "-m",
        "experiments.run_baseline_eval",
        "--sessions",
        "1",
        "--seed",
        "0",
    ]
    res = subprocess.run(
        cmd,
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=False,
        timeout=30,
    )
    err = res.stderr.decode("utf-8", errors="replace")
    assert res.returncode == 0, f"Failed under {encoding}:\n{err}"
    assert len(res.stdout) > 0


@pytest.mark.parametrize("encoding", ["cp1252", "cp437:strict", "ascii:replace"])
@pytest.mark.parametrize("condition", ["a", "b"])
def test_run_human_trial_hostile_encoding(tmp_path: Path, encoding: str, condition: str):
    """Verify run_human_trial handles hostile encoding across Condition A and B."""
    db_path = tmp_path / "trial_test.db"
    env = {**os.environ, "PYTHONIOENCODING": encoding}
    # Simulated keystrokes:
    # Enter to start, 6 answers ('1') for questions, 'y' for outcome match,
    # '7', '7', '7', '7' for Likert survey, 'y' for repeat, 'y' for consent.
    inputs = [""] + ["1"] * 6 + ["y", "7", "7", "7", "7", "y", "y"]
    simulated_input = ("\n".join(inputs) + "\n").encode("ascii")

    cmd = [
        sys.executable,
        "-m",
        "experiments.run_human_trial",
        "--effect",
        "card_prediction",
        "--condition",
        condition,
        "--db",
        str(db_path),
    ]
    res = subprocess.run(
        cmd,
        cwd=REPO_ROOT,
        env=env,
        input=simulated_input,
        capture_output=True,
        text=False,
        timeout=30,
    )
    err = res.stderr.decode("utf-8", errors="replace")
    assert res.returncode == 0, f"Failed condition {condition} under {encoding}:\n{err}"
    assert len(res.stdout) > 0

    # Verify session and survey were properly persisted in db
    archive = SessionArchive(db_path)
    assert len(archive.list_summaries()) == 1
    assert len(archive.survey_rows()) == 1


# ==============================================================================
# 2. SessionArchive.delete Edge Cases & Stress Tests
# ==============================================================================


def _create_finished_session(effect_id: str = "card_prediction") -> EffectSession:
    registry = load_effects(EFFECTS_DIR)
    effect = registry[effect_id]
    renderer = LanguageRenderer()
    session = EffectSession(effect, renderer, condition="b")
    while session.phase.value == "active":
        if session.current_mode == "covert":
            session.respond_agreement("strong_yes")
        else:
            session.answer(session.current_question.answers[0].id)
    session.report_outcome(True)
    return session


def test_delete_nonexistent_session_db_absent(tmp_path: Path):
    """Edge Case 1a: Database does not exist yet -> must return False."""
    db_path = tmp_path / "data" / "does_not_exist.db"
    archive = SessionArchive(db_path)
    assert archive.delete("nonexistent_session_id") is False


def test_delete_nonexistent_session_db_empty(tmp_path: Path):
    """Edge Case 1b: Database exists but has no sessions -> must return False."""
    db_path = tmp_path / "data" / "sessions.db"
    archive = SessionArchive(db_path)
    # Trigger DB creation
    archive.list_summaries()  # Non-existent DB path check returns [] without creating table
    # Save a temporary session and delete it to instantiate schema
    s = _create_finished_session()
    archive.save(s)
    assert archive.delete(s.session_id) is True

    # Now DB exists and is empty
    assert archive.delete("unknown_session") is False
    assert archive.delete("") is False
    assert archive.delete("' OR '1'='1") is False


def test_delete_idempotence_and_double_deletion(tmp_path: Path):
    """Edge Case 2: Deleting an existing session twice must return True first, then False."""
    db_path = tmp_path / "data" / "sessions.db"
    archive = SessionArchive(db_path)
    s = _create_finished_session()
    archive.save(s)

    # 1st delete -> True
    assert archive.delete(s.session_id) is True
    # 2nd delete -> False (idempotence)
    assert archive.delete(s.session_id) is False
    # 3rd delete -> False
    assert archive.delete(s.session_id) is False


def test_delete_session_with_both_trajectory_and_survey(tmp_path: Path):
    """Edge Case 3: Session with both trajectory and survey -> both purged, returns True."""
    db_path = tmp_path / "data" / "sessions.db"
    archive = SessionArchive(db_path)
    s = _create_finished_session()
    archive.save(s)
    archive.save_survey(
        s.session_id,
        s.condition,
        {"impossibility": 7, "freedom": 6, "naturalness": 5, "surprise": 7, "willing_repeat": 1},
        created_at="2026-10-04T00:00:00Z",
    )

    # Pre-condition: both records present
    assert len(archive.list_summaries()) == 1
    assert len(archive.survey_rows()) == 1

    # Action: delete
    result = archive.delete(s.session_id)
    assert result is True

    # Post-condition: both purged
    assert len(archive.list_summaries()) == 0
    assert len(archive.survey_rows()) == 0

    # Re-deletion returns False
    assert archive.delete(s.session_id) is False


def test_delete_survey_only_session_without_trajectory(tmp_path: Path):
    """Edge Case 4: Survey-only session without trajectory -> survey purged, returns True."""
    db_path = tmp_path / "data" / "sessions.db"
    archive = SessionArchive(db_path)
    orphan_sid = "sid_orphan_survey"
    archive.save_survey(
        orphan_sid,
        "a",
        {"impossibility": 4, "freedom": 4, "naturalness": 4, "surprise": 4, "willing_repeat": 0},
        created_at="2026-10-04T00:00:00Z",
    )

    # Pre-condition: only survey present
    assert len(archive.list_summaries()) == 0
    assert len(archive.survey_rows()) == 1

    # Action: delete
    result = archive.delete(orphan_sid)
    assert result is True

    # Post-condition: survey purged
    assert len(archive.survey_rows()) == 0

    # Re-deletion returns False
    assert archive.delete(orphan_sid) is False


def test_delete_trajectory_only_session_without_survey(tmp_path: Path):
    """Edge Case 5: Trajectory-only session without survey -> trajectory purged, returns True."""
    db_path = tmp_path / "data" / "sessions.db"
    archive = SessionArchive(db_path)
    s = _create_finished_session()
    archive.save(s)

    # Pre-condition: only trajectory present
    assert len(archive.list_summaries()) == 1
    assert len(archive.survey_rows()) == 0

    # Action: delete
    result = archive.delete(s.session_id)
    assert result is True

    # Post-condition: trajectory purged
    assert len(archive.list_summaries()) == 0
    assert len(archive.survey_rows()) == 0

    # Re-deletion returns False
    assert archive.delete(s.session_id) is False


def test_delete_isolation_no_collateral_damage(tmp_path: Path):
    """Edge Case 6: Deleting session A does NOT purge session B or orphan survey C."""
    db_path = tmp_path / "data" / "sessions.db"
    archive = SessionArchive(db_path)

    # Session A: trajectory + survey
    sa = _create_finished_session()
    archive.save(sa)
    archive.save_survey(
        sa.session_id,
        "b",
        {"impossibility": 6, "freedom": 6, "naturalness": 6, "surprise": 6, "willing_repeat": 1},
        created_at="2026-10-04T00:00:00Z",
    )

    # Session B: trajectory only
    sb = _create_finished_session()
    archive.save(sb)

    # Session C: survey only
    archive.save_survey(
        "sc_survey_only",
        "a",
        {"impossibility": 3, "freedom": 3, "naturalness": 3, "surprise": 3, "willing_repeat": 0},
        created_at="2026-10-04T00:00:00Z",
    )

    assert len(archive.list_summaries()) == 2
    assert len(archive.survey_rows()) == 2

    # Delete session A
    assert archive.delete(sa.session_id) is True

    # Session B trajectory and Session C survey must remain intact
    summaries = archive.list_summaries()
    assert len(summaries) == 1
    assert summaries[0]["session_id"] == sb.session_id

    surveys = archive.survey_rows()
    assert len(surveys) == 1
    assert surveys[0]["session_id"] == "sc_survey_only"

    # Delete session C (survey only)
    assert archive.delete("sc_survey_only") is True
    assert len(archive.survey_rows()) == 0
    assert len(archive.list_summaries()) == 1

    # Delete session B (trajectory only)
    assert archive.delete(sb.session_id) is True
    assert len(archive.list_summaries()) == 0
    assert len(archive.survey_rows()) == 0


def test_api_delete_endpoints_and_status_codes(tmp_path: Path):
    """Verify HTTP DELETE /api/archive/{id} status codes across edge cases:
    - 404 for unknown session
    - 204 for trajectory+survey session
    - 404 on subsequent call (idempotence)
    - 204 for survey-only session
    - 404 on subsequent call
    - 204 for trajectory-only session
    - 404 on subsequent call
    """
    db_path = tmp_path / "data" / "sessions.db"
    app = create_app(db_path=db_path)
    client = TestClient(app)

    # 1. Unknown session -> 404
    assert client.delete("/api/archive/unknown_id").status_code == 404

    # 2. Both trajectory and survey
    archive = SessionArchive(db_path)
    s = _create_finished_session()
    archive.save(s)
    archive.save_survey(
        s.session_id,
        "b",
        {"impossibility": 7, "freedom": 7, "naturalness": 7, "surprise": 7, "willing_repeat": 1},
        created_at="2026-10-04T00:00:00Z",
    )
    assert client.delete(f"/api/archive/{s.session_id}").status_code == 204
    assert client.delete(f"/api/archive/{s.session_id}").status_code == 404

    # 3. Survey-only session
    archive.save_survey(
        "orphan_survey_api",
        "a",
        {"impossibility": 5, "freedom": 5, "naturalness": 5, "surprise": 5, "willing_repeat": 0},
        created_at="2026-10-04T00:00:00Z",
    )
    assert client.delete("/api/archive/orphan_survey_api").status_code == 204
    assert client.delete("/api/archive/orphan_survey_api").status_code == 404

    # 4. Trajectory-only session
    s_traj = _create_finished_session()
    archive.save(s_traj)
    assert client.delete(f"/api/archive/{s_traj.session_id}").status_code == 204
    assert client.delete(f"/api/archive/{s_traj.session_id}").status_code == 404


def test_concurrent_deletion_race_condition(tmp_path: Path):
    """Stress test: 10 concurrent threads deleting the same session.
    Exactly 1 thread must return True, exactly 9 threads must return False.
    """
    db_path = tmp_path / "data" / "sessions.db"
    archive = SessionArchive(db_path)
    s = _create_finished_session()
    archive.save(s)
    archive.save_survey(
        s.session_id,
        "b",
        {"impossibility": 6, "freedom": 6, "naturalness": 6, "surprise": 6, "willing_repeat": 1},
        created_at="2026-10-04T00:00:00Z",
    )

    results: list[bool] = []
    lock = threading.Lock()

    def worker():
        res = archive.delete(s.session_id)
        with lock:
            results.append(res)

    threads = [threading.Thread(target=worker) for _ in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len(results) == 10
    assert results.count(True) == 1, f"Expected exactly 1 True, got {results.count(True)}"
    assert results.count(False) == 9, f"Expected exactly 9 False, got {results.count(False)}"
    assert len(archive.list_summaries()) == 0
    assert len(archive.survey_rows()) == 0
