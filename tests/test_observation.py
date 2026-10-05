"""Phase 2 slice A: weak observation evidence (effect schema v1.1).

Observations move probability mass only — they never advance the session,
never commit, and never count as turns. They apply to direct turns only:
a covert turn shows agreement reactions, not answer options to dwell on
(ROADMAP Phase 2).
"""

from __future__ import annotations

import pytest

from services.effects.engine import EffectSession, InvalidStateError, Phase
from tests.conftest import direct_only, truthful_answer, truthful_response


def test_observation_moves_posterior_without_advancing(card_effect, renderer):
    session = EffectSession(direct_only(card_effect), renderer)
    question = session.current_question
    assert question.id == "q_rank_bucket"  # policy's first pick
    before = session.tracker.posterior

    session.observe(question.id, "r10", "gaze_dwell", dwell_ms=900.0)

    after = session.tracker.posterior
    tens = [h for h, attrs in card_effect.hypotheses.items() if attrs["rank_value"] == 10]
    others = [h for h in card_effect.hypotheses if h not in tens]
    assert sum(after[h] for h in tens) > sum(before[h] for h in tens)
    assert sum(after[h] for h in tens) > sum(after[h] for h in others) / 12
    assert session.phase is Phase.ACTIVE
    assert session.current_question is question  # same question, unchanged
    assert session.turn == 1

    events = [e for e in session.history if e.type.value == "observation.recorded"]
    assert len(events) == 1
    payload = events[0].payload
    assert payload["channel"] == "gaze_dwell"
    assert payload["answer_id"] == "r10"
    assert payload["answer_label"] == "Ten"
    assert payload["dwell_ms"] == 900.0
    assert payload["reliability"] == pytest.approx(0.55)
    assert payload["entropy_after"] < payload["entropy_before"]


def test_gaze_evidence_strengthen_the_same_answer(card_effect, renderer):
    """Fusing gaze + verbal answer should land further toward the truth than the
    verbal answer alone."""

    def tens_mass_after(observe_first: bool) -> float:
        session = EffectSession(direct_only(card_effect), renderer)
        question = session.current_question
        if observe_first:
            session.observe(question.id, "r10", "gaze_dwell", dwell_ms=800.0)
            question = session.current_question
        session.answer(truthful_answer(card_effect, question, "10D"))
        return sum(
            p
            for h, p in session.tracker.posterior.items()
            if card_effect.hypotheses[h]["rank_value"] == 10
        )

    assert tens_mass_after(True) > tens_mass_after(False)


def test_observation_validation(card_effect, renderer):
    session = EffectSession(direct_only(card_effect), renderer)
    question = session.current_question
    with pytest.raises(ValueError, match="no observation channel"):
        session.observe(question.id, "red", "telepathy")
    with pytest.raises(ValueError, match="is current"):
        session.observe("q_color", "red", "gaze_dwell")  # not the current question
    with pytest.raises(ValueError, match="not an option"):
        session.observe(question.id, "purple", "gaze_dwell")
    assert session.turn == 1 and session.phase is Phase.ACTIVE  # state untouched


def test_observation_rejected_on_covert_turn(card_effect, renderer):
    session = EffectSession(card_effect, renderer)
    assert session.current_mode == "covert"
    with pytest.raises(InvalidStateError, match="covert"):
        session.observe(session.current_question.id, session.asserted_answer_id, "gaze_dwell")
    assert session.turn == 1 and session.phase is Phase.ACTIVE  # state untouched


def test_observation_rejected_outside_active_phase(card_effect, renderer):
    session = EffectSession(card_effect, renderer)
    while session.phase is Phase.ACTIVE:
        truthful_response(session, card_effect, "AS")
    with pytest.raises(InvalidStateError):
        session.observe("q_color", "red", "gaze_dwell")


def test_answer_records_utterance(card_effect, renderer):
    session = EffectSession(direct_only(card_effect), renderer)
    question = session.current_question
    session.answer(
        truthful_answer(card_effect, question, "AS"),
        latency_ms=150.0,
        utterance="the ace of spades",
    )
    event = next(e for e in session.history if e.type.value == "hypothesis.updated")
    assert event.payload["utterance"] == "the ace of spades"


def _drive_to_direct_turn(client, session_id: str, max_turns: int) -> dict:
    """Reach a guaranteed direct turn: two non-affirming responses trigger the
    policy's backoff (or a direct turn arrives on its own)."""
    view = client.get(f"/api/sessions/{session_id}").json()
    for _ in range(3):
        if view["phase"] != "active":
            break
        if view["mode"] == "direct":
            return view
        view = client.post(
            f"/api/sessions/{session_id}/answer", json={"answer_id": "lean_no"}
        ).json()
    assert view["phase"] == "active" and view["mode"] == "direct"
    return view


def test_observe_endpoint_moves_certainty(client, card_effect):
    created = client.post("/api/sessions", json={"effect_id": "card_prediction", "condition": "b"})
    assert created.status_code == 201
    view = created.json()
    sid = view["session_id"]

    view = _drive_to_direct_turn(client, sid, card_effect.termination.max_turns)
    question = next(q for q in card_effect.questions if q.id == view["question_id"])
    answer_id = truthful_answer(card_effect, question, "10D")
    answer_label = next(a.label for a in question.answers if a.id == answer_id)

    response = client.post(
        f"/api/sessions/{sid}/observations",
        json={
            "channel": "gaze_dwell",
            "question_id": view["question_id"],
            "answer_id": answer_id,
            "dwell_ms": 700.0,
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["certainty"] > 0
    assert body["curtain"]["last_observation"]["dwell_ms"] == 700.0
    assert body["curtain"]["last_observation"]["answer_label"] == answer_label

    # wrong channel -> 400
    bad_channel = client.post(
        f"/api/sessions/{sid}/observations",
        json={"channel": "auras", "question_id": view["question_id"], "answer_id": answer_id},
    )
    assert bad_channel.status_code == 400
    # wrong question -> 400
    other = next(q.id for q in card_effect.questions if q.id != view["question_id"])
    bad_question = client.post(
        f"/api/sessions/{sid}/observations",
        json={"channel": "gaze_dwell", "question_id": other, "answer_id": answer_id},
    )
    assert bad_question.status_code == 400
    # covert turns take no observations -> 409
    covert_view = client.post(
        "/api/sessions", json={"effect_id": "card_prediction", "condition": "b"}
    ).json()
    if covert_view["mode"] == "covert":
        rejected = client.post(
            f"/api/sessions/{covert_view['session_id']}/observations",
            json={
                "channel": "gaze_dwell",
                "question_id": covert_view["question_id"],
                "answer_id": "r10",
            },
        )
        assert rejected.status_code == 409

    # effects expose their channels
    effects = {e["id"]: e for e in client.get("/api/effects").json()}
    assert effects["card_prediction"]["observation_channels"] == [
        {"id": "gaze_dwell", "min_dwell_ms": 400}
    ]
    assert effects["number_prediction"]["observation_channels"] == []
