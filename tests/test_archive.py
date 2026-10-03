"""Archive flow: consent-gated writes, idempotence, deletion control, stats."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from services.api.main import create_app
from services.effects.loader import load_effects
from tests.conftest import truthful_answer

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
        question = next(q for q in effect.questions if q.id == view["question_id"])
        client.post(
            f"/api/sessions/{sid}/answer",
            json={"answer_id": truthful_answer(effect, question, truth)},
        )
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
        question = next(q for q in effect.questions if q.id == view["question_id"])
        client.post(
            f"/api/sessions/{sid}/answer",
            json={"answer_id": truthful_answer(effect, question, "AS")},
        )
    assert client.get(f"/api/sessions/{sid}").json()["phase"] == "revealed"
    assert client.post(f"/api/sessions/{sid}/archive").status_code == 409  # pre-outcome

    client.post(f"/api/sessions/{sid}/outcome", json={"correct": True})
    assert client.post(f"/api/sessions/{sid}/archive").status_code == 200


def test_archive_unknown_session_404(tmp_path):
    client = _client(tmp_path)
    assert client.post("/api/sessions/nope/archive").status_code == 404
    assert client.delete("/api/archive/nope").status_code == 404
