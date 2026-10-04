from __future__ import annotations

import pytest

from tests.conftest import truthful_body as _truthful_body


def test_health(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "effects": 4}


def test_list_effects(client):
    response = client.get("/api/effects")
    assert response.status_code == 200
    effects = response.json()
    assert {e["id"] for e in effects} == {
        "card_prediction",
        "number_prediction",
        "animal_guess",
        "sigil_forced_choice",
    }
    assert all(
        set(e)
        == {
            "id",
            "title",
            "description",
            "hypothesis_count",
            "question_count",
            "observation_channels",
        }
        for e in effects
    )
    card = next(e for e in effects if e["id"] == "card_prediction")
    assert card["hypothesis_count"] == 52
    assert card["question_count"] == 6
    assert card["observation_channels"] == [{"id": "gaze_dwell", "min_dwell_ms": 400}]


def test_create_session(client, card_effect):
    response = client.post("/api/sessions", json={"effect_id": "card_prediction"})
    assert response.status_code == 201
    view = response.json()
    assert view["phase"] == "active"
    assert view["turn"] == 1
    assert view["max_turns"] == card_effect.termination.max_turns
    assert view["question_id"] is not None
    assert len(view["options"]) >= 2
    assert view["certainty"] == pytest.approx(0.0, abs=1e-9)
    assert len(view["curtain"]["top"]) == 5
    assert all(h["probability"] == pytest.approx(1 / 52, rel=1e-6) for h in view["curtain"]["top"])
    assert view["message"]


def test_create_session_unknown_effect(client):
    response = client.post("/api/sessions", json={"effect_id": "levitation"})
    assert response.status_code == 404


def test_full_truthful_lifecycle(client, card_effect):
    created = client.post("/api/sessions", json={"effect_id": "card_prediction"})
    assert created.status_code == 201
    session_id = created.json()["session_id"]

    latency_sent = False
    for _ in range(card_effect.termination.max_turns + 1):
        view = client.get(f"/api/sessions/{session_id}").json()
        if view["phase"] != "active":
            break
        payload = _truthful_body(card_effect, view, "7D")
        if not latency_sent:
            payload["latency_ms"] = 412.0
            latency_sent = True
        answered = client.post(f"/api/sessions/{session_id}/answer", json=payload)
        assert answered.status_code == 200

    view = client.get(f"/api/sessions/{session_id}").json()
    assert view["phase"] == "revealed"
    assert view["prediction"]["hypothesis_id"] == "7D"
    assert view["prediction"]["label"] == "Seven of Diamonds"
    # Covert agreement updates are deliberately softer than direct answers, so
    # mixed-policy commits sit a little lower than the direct-only ~0.95.
    assert view["prediction"]["confidence"] > 0.75

    trajectory = client.get(f"/api/sessions/{session_id}/trajectory").json()
    event_types = [e["type"] for e in trajectory["events"]]
    assert event_types[0] == "session.started"
    assert "hypothesis.updated" in event_types
    assert "effect.revealed" in event_types
    latency_events = [
        e
        for e in trajectory["events"]
        if e["type"] == "hypothesis.updated" and e["payload"]["latency_ms"] == 412.0
    ]
    assert len(latency_events) == 1
    assert all(e["schema_version"] == 1 and e["event_id"] and e["ts"] for e in trajectory["events"])

    outcome = client.post(f"/api/sessions/{session_id}/outcome", json={"correct": True})
    assert outcome.status_code == 200
    assert outcome.json()["phase"] == "outcome"


def test_answer_validation_errors(client, card_effect):
    session_id = client.post(
        "/api/sessions", json={"effect_id": "card_prediction", "condition": "b"}
    ).json()["session_id"]
    # Covert first turn: option ids are not agreement strengths.
    bad_answer = client.post(f"/api/sessions/{session_id}/answer", json={"answer_id": "purple"})
    assert bad_answer.status_code == 400

    # drive to reveal, then answering again must conflict
    for _ in range(card_effect.termination.max_turns + 1):
        view = client.get(f"/api/sessions/{session_id}").json()
        if view["phase"] != "active":
            break
        client.post(
            f"/api/sessions/{session_id}/answer", json=_truthful_body(card_effect, view, "AS")
        )
    conflict = client.post(f"/api/sessions/{session_id}/answer", json={"answer_id": "hearts"})
    assert conflict.status_code == 409


def test_covert_turn_view_scale(client):
    view = client.post(
        "/api/sessions", json={"effect_id": "card_prediction", "condition": "b"}
    ).json()
    assert view["phase"] == "active"
    assert view["mode"] == "covert"
    assert view["asserted_label"]
    assert [o["id"] for o in view["options"]] == ["strong_yes", "lean_yes", "lean_no"]


def test_free_text_response_parsed_server_side(client):
    session_id = client.post(
        "/api/sessions", json={"effect_id": "card_prediction", "condition": "b"}
    ).json()["session_id"]
    answered = client.post(
        f"/api/sessions/{session_id}/answer",
        json={"free_text": "hmm, not really", "latency_ms": 1700.0},
    )
    assert answered.status_code == 200
    trajectory = client.get(f"/api/sessions/{session_id}/trajectory").json()
    updated = [e for e in trajectory["events"] if e["type"] == "hypothesis.updated"]
    payload = updated[-1]["payload"]
    assert payload["mode"] == "covert"
    assert payload["agreement_strength"] == "lean_no"
    assert payload["asserted_answer_id"]
    assert payload["utterance"] == "hmm, not really"  # verbatim text, consent-gated


def test_free_text_requires_active_covert_turn(client, card_effect):
    session_id = client.post(
        "/api/sessions", json={"effect_id": "card_prediction", "condition": "b"}
    ).json()["session_id"]
    for _ in range(card_effect.termination.max_turns + 1):
        view = client.get(f"/api/sessions/{session_id}").json()
        if view["phase"] != "active":
            break
        client.post(
            f"/api/sessions/{session_id}/answer", json=_truthful_body(card_effect, view, "AS")
        )
    late = client.post(f"/api/sessions/{session_id}/answer", json={"free_text": "yes"})
    assert late.status_code == 400


def test_answer_requires_id_or_free_text(client):
    session_id = client.post(
        "/api/sessions", json={"effect_id": "card_prediction", "condition": "b"}
    ).json()["session_id"]
    empty = client.post(f"/api/sessions/{session_id}/answer", json={})
    assert empty.status_code == 400


def test_revealed_view_carries_reveal_staging(client, card_effect):
    session_id = client.post(
        "/api/sessions", json={"effect_id": "card_prediction", "condition": "b"}
    ).json()["session_id"]
    for _ in range(card_effect.termination.max_turns + 1):
        view = client.get(f"/api/sessions/{session_id}").json()
        if view["phase"] != "active":
            break
        client.post(
            f"/api/sessions/{session_id}/answer",
            json=_truthful_body(card_effect, view, "7D"),
        )
    view = client.get(f"/api/sessions/{session_id}").json()
    assert view["phase"] == "revealed"
    assert view["reveal_path"] in (
        "progressive",
        "category_cluster",
        "dual_deduction",
        "plain",
    )
    for stage in view["reveal_stages"]:
        assert stage["kind"] in ("attribute", "category", "deduction", "hesitation")
        assert stage["text"]
    assert view["message"]  # the banded identity line always remains


def test_unknown_session_404(client):
    assert client.get("/api/sessions/nope").status_code == 404
    assert client.post("/api/sessions/nope/answer", json={"answer_id": "x"}).status_code == 404
    assert client.post("/api/sessions/nope/outcome", json={"correct": True}).status_code == 404


def test_session_or_404_helper(card_effect):
    from fastapi import HTTPException

    from services.api.main import _session_or_404
    from services.api.store import SessionStore
    from services.effects.engine import EffectSession
    from services.language.renderer import LanguageRenderer

    store = SessionStore()
    session = EffectSession(card_effect, LanguageRenderer())
    store.add(session)

    # Found session
    retrieved = _session_or_404(store, session.session_id)
    assert retrieved is session

    # Missing session raises 404
    with pytest.raises(HTTPException) as exc_info:
        _session_or_404(store, "non_existent_id")
    assert exc_info.value.status_code == 404
    assert exc_info.value.detail == "session not found"
