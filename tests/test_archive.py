"""Archive flow: consent-gated writes, idempotence, deletion control, stats."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from services.api.archive import SessionArchive
from services.api.main import create_app
from services.effects.loader import load_effects
from tests.conftest import truthful_body

EFFECTS_DIR = Path(__file__).resolve().parents[1] / "configs" / "effects"
REGISTRY = load_effects(EFFECTS_DIR)


def _client(tmp_path) -> TestClient:
    return TestClient(create_app(EFFECTS_DIR, db_path=tmp_path / "data" / "sessions.db"))


def _play_to_outcome(client: TestClient, effect_id: str, truth: str, correct: bool = True) -> str:
    effect = REGISTRY[effect_id]
    sid = client.post("/api/sessions", json={"effect_id": effect_id}).json()["session_id"]
    for _ in range(effect.termination.max_turns + 1):
        view = client.get(f"/api/sessions/{sid}").json()
        if view["phase"] != "active":
            break
        client.post(f"/api/sessions/{sid}/answer", json=truthful_body(effect, view, truth))
    client.post(f"/api/sessions/{sid}/outcome", json={"correct": correct})
    return sid


def test_no_db_file_without_consent(tmp_path):
    db = tmp_path / "data" / "sessions.db"
    client = _client(tmp_path)
    _play_to_outcome(client, "card_prediction", "AS")
    assert not db.exists(), "gameplay must never create or write the archive"
    assert client.get("/api/archive").json() == []
    assert client.get("/api/stats").json() == []


def test_archive_list_stats_delete_flow(tmp_path):
    client = _client(tmp_path)
    sid = _play_to_outcome(client, "card_prediction", "AS", correct=True)

    archived = client.post(f"/api/sessions/{sid}/archive")
    assert archived.status_code == 200
    summary = archived.json()["summary"]
    assert summary["session_id"] == sid
    assert summary["effect_id"] == "card_prediction"
    assert summary["prediction_label"] == "Ace of Spades"
    assert summary["correct"] is True
    assert summary["committed_because"] in (
        "entropy_threshold",
        "max_turns",
        "no_informative_question",
    )

    client.post(f"/api/sessions/{sid}/archive")  # idempotent
    assert len(client.get("/api/archive").json()) == 1

    stats = client.get("/api/stats").json()
    assert len(stats) == 1
    row = stats[0]
    assert row["effect_id"] == "card_prediction"
    assert row["archived"] == 1
    assert row["with_outcome"] == 1
    assert row["accuracy"] == 1.0
    assert row["avg_turns"] is not None

    sid2 = _play_to_outcome(client, "card_prediction", "KH", correct=False)
    client.post(f"/api/sessions/{sid2}/archive")
    stats = client.get("/api/stats").json()
    assert stats[0]["archived"] == 2
    assert stats[0]["with_outcome"] == 2
    assert stats[0]["accuracy"] == pytest.approx(0.5)
    assert stats[0]["correct"] == 1

    assert client.delete(f"/api/archive/{sid}").status_code == 204
    remaining = client.get("/api/archive").json()
    assert [s["session_id"] for s in remaining] == [sid2]
    assert client.delete(f"/api/archive/{sid}").status_code == 404
    assert client.get("/api/stats").json()[0]["archived"] == 1


def test_archive_requires_outcome_phase(tmp_path):
    client = _client(tmp_path)
    effect = REGISTRY["card_prediction"]
    sid = client.post("/api/sessions", json={"effect_id": "card_prediction"}).json()["session_id"]
    assert client.post(f"/api/sessions/{sid}/archive").status_code == 409  # active

    for _ in range(effect.termination.max_turns + 1):
        view = client.get(f"/api/sessions/{sid}").json()
        if view["phase"] != "active":
            break
        client.post(f"/api/sessions/{sid}/answer", json=truthful_body(effect, view, "AS"))
    assert client.get(f"/api/sessions/{sid}").json()["phase"] == "revealed"
    assert client.post(f"/api/sessions/{sid}/archive").status_code == 409  # pre-outcome

    client.post(f"/api/sessions/{sid}/outcome", json={"correct": True})
    assert client.post(f"/api/sessions/{sid}/archive").status_code == 200


def test_archive_unknown_session_404(tmp_path):
    client = _client(tmp_path)
    assert client.post("/api/sessions/nope/archive").status_code == 404
    assert client.delete("/api/archive/nope").status_code == 404


def test_delete_orphan_survey_without_archived_session(tmp_path):
    """Directive §19 deletion control: deleting a session that submitted a survey
    without archiving the gameplay trajectory must delete the survey and return 204."""
    db_path = tmp_path / "data" / "sessions.db"
    client = _client(tmp_path)
    sid = _play_to_outcome(client, "card_prediction", "AS", correct=True)

    # Participant submits survey but does NOT archive trajectory
    survey_payload = {
        "impossibility": 6,
        "freedom": 5,
        "naturalness": 7,
        "surprise": 4,
        "willing_repeat": True,
    }
    resp = client.post(f"/api/sessions/{sid}/survey", json=survey_payload)
    assert resp.status_code == 201

    # Verify session trajectory is not in /api/archive, but survey exists in db
    assert client.get("/api/archive").json() == []
    archive = SessionArchive(db_path)
    surveys_before = archive.survey_rows()
    assert len(surveys_before) == 1
    assert surveys_before[0]["session_id"] == sid

    # Deletion control must succeed with 204 No Content
    del_resp = client.delete(f"/api/archive/{sid}")
    assert del_resp.status_code == 204

    # Verify survey is completely purged from ledger
    assert archive.survey_rows() == []

    # Subsequent deletion must return 404 (already deleted)
    assert client.delete(f"/api/archive/{sid}").status_code == 404


def test_session_archive_delete_orphan_survey_direct(tmp_path):
    """Direct SessionArchive unit test for orphan survey deletion."""
    db_path = tmp_path / "data" / "sessions.db"
    archive = SessionArchive(db_path)
    answers = {
        "impossibility": 5,
        "freedom": 4,
        "naturalness": 6,
        "surprise": 5,
        "willing_repeat": True,
    }
    archive.save_survey("orphan_sid", "b", answers, created_at="2026-10-04T00:00:00Z")
    assert len(archive.survey_rows()) == 1

    # First delete returns True and purges survey
    assert archive.delete("orphan_sid") is True
    assert len(archive.survey_rows()) == 0

    # Second delete returns False
    assert archive.delete("orphan_sid") is False

