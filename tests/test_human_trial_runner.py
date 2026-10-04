"""Integration test for human trial runner and database archive pipeline (§18, Job e)."""

import io
from pathlib import Path

from experiments.analyze_ab import analyze
from experiments.run_human_trial import run_session
from services.api.archive import SessionArchive


def test_human_trial_runner_saves_consented_records(tmp_path, monkeypatch):
    test_db = tmp_path / "test_sessions.db"

    # Inputs sequence:
    # 1. Start session (Enter) -> ""
    # 2. Answers to turns: "1", "1", "1", "1", "1"
    # 3. Outcome correct? -> "y"
    # 4. Survey Likert ratings: "6", "5", "6", "7"
    # 5. Willing to repeat? -> "y"
    # 6. Consent to archive? -> "y"
    inputs = iter(["", "1", "1", "1", "1", "1", "1", "y", "6", "5", "6", "7", "y", "y"])
    monkeypatch.setattr("builtins.input", lambda prompt="": next(inputs))

    success = run_session(effect_id="card_prediction", condition="b", db_path=test_db)
    assert success is True

    # Verify database contents
    archive = SessionArchive(test_db)
    rows = archive.survey_rows()
    assert len(rows) == 1
    record = rows[0]
    assert record["condition"] == "b"
    assert record["impossibility"] == 6
    assert record["freedom"] == 5
    assert record["naturalness"] == 6
    assert record["surprise"] == 7
    assert record["willing_repeat"] == 1
    assert record["correct"] == 1

    # Verify analyze_ab pipeline processes this real record cleanly
    report = analyze(rows)
    assert report["n"]["b"] == 1
    assert report["impossibility"]["mean_b"] == 6.0


def test_human_trial_runner_respects_withheld_consent(tmp_path, monkeypatch):
    test_db = tmp_path / "test_sessions.db"

    # Consent answer is "n"
    inputs = iter(["", "1", "1", "1", "1", "1", "1", "y", "5", "5", "5", "5", "y", "n"])
    monkeypatch.setattr("builtins.input", lambda prompt="": next(inputs))

    success = run_session(effect_id="card_prediction", condition="a", db_path=test_db)
    assert success is True

    # Verify no records were saved
    archive = SessionArchive(test_db)
    assert len(archive.survey_rows()) == 0
    assert len(archive.list_summaries()) == 0
