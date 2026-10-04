"""Passive-signal fusion tests (ROADMAP Phase 5, docs/passive-signals.md).

Latency and typing rhythm are WEAK modulations: they discount evidence,
never invent or invert it, and never move a session forward by themselves.
"""

from __future__ import annotations

import pytest

from services.effects.engine import EffectSession, Phase
from services.fusion.engine import (
    LatencyChannel,
    downgrade_strength,
    is_hesitant,
    latency_factor,
    modulated_reliability,
)
from services.language.response_signals import AgreementStrength as S
from tests.conftest import direct_only, truthful_answer

CHANNEL = LatencyChannel(fast_ms=2000.0, slow_ms=8000.0, floor=0.6)


def test_latency_factor_curve():
    assert latency_factor(CHANNEL, 500.0) == 1.0  # fast: full weight
    assert latency_factor(CHANNEL, 2000.0) == 1.0
    assert latency_factor(CHANNEL, 8000.0) == 0.6  # the floor
    assert latency_factor(CHANNEL, 20000.0) == 0.6  # constant after slow_ms
    mid = latency_factor(CHANNEL, 5000.0)
    assert 0.6 < mid < 1.0  # linear between the bounds
    assert latency_factor(CHANNEL, 3000.0) > mid > latency_factor(CHANNEL, 7000.0)


def test_latency_channel_validation():
    with pytest.raises(ValueError, match="fast_ms"):
        LatencyChannel(fast_ms=9000.0, slow_ms=2000.0, floor=0.6)
    with pytest.raises(ValueError, match="floor"):
        LatencyChannel(fast_ms=1000.0, slow_ms=2000.0, floor=1.5)


def test_modulated_reliability_never_strengthens():
    assert modulated_reliability(0.95, 1.0) == 0.95
    assert modulated_reliability(0.95, 0.6) == pytest.approx(0.57)
    # a factor above 1 must not lift the answer above its base
    assert modulated_reliability(0.95, 1.4) == 0.95
    with pytest.raises(ValueError):
        modulated_reliability(0.0, 1.0)


def test_hesitation_thresholds():
    assert not is_hesitant(None, None)
    assert not is_hesitant(1000.0, 300.0)
    assert is_hesitant(4000.0, None)  # slow to start
    assert is_hesitant(None, 900.0)  # slow keystrokes
    assert is_hesitant(4000.0, 900.0)


def test_downgrade_steps_toward_uncertainty():
    assert downgrade_strength(S.STRONG_YES) is S.LEAN_YES
    assert downgrade_strength(S.LEAN_YES) is S.UNCLEAR
    assert downgrade_strength(S.UNCLEAR) is S.UNCLEAR  # already the floor
    assert downgrade_strength(S.STRONG_NO) is S.LEAN_NO
    assert downgrade_strength(S.LEAN_NO) is S.UNCLEAR


def test_loader_parses_the_latency_channel(registry):
    for effect in registry.values():
        assert effect.latency_channel is not None
        assert effect.latency_channel.floor == pytest.approx(0.6)
        # the modulation channel is redirected out of the categorical map
        assert "response_latency" not in effect.observations


def test_loader_rejects_an_invalid_latency_channel(tmp_path):
    from services.effects.loader import load_effect

    yaml_text = """
id: t
title: t
description: d
hypothesis_space:
  type: enumerated
  items:
    - {id: a, v: 1}
    - {id: b, v: 2}
    - {id: c, v: 3}
observations:
  response_latency:
    fast_ms: 9000
    slow_ms: 2000
    floor: 0.6
questions:
  - id: q1
    text: "?"
    answers:
      - {id: lo, label: lo, predicate: {attr: v, op: lte, value: 2}}
      - {id: hi, label: hi, predicate: {attr: v, op: gte, value: 3}}
termination: {entropy_threshold_bits: 0.1, max_turns: 5}
"""
    path = tmp_path / "t.yaml"
    path.write_text(yaml_text, encoding="utf-8")
    with pytest.raises(ValueError, match="fast_ms"):
        load_effect(path)


def test_slow_answers_count_less_than_fast_ones(card_effect, renderer):
    """The whole point of latency fusion: a hesitant answer moves the
    posterior less than a confident one — same option, same question."""
    effect = direct_only(card_effect)
    question_id = "q_high_card"

    def posterior_after(latency_ms: float) -> float:
        session = EffectSession(
            effect.model_copy(
                update={"questions": [q for q in effect.questions if q.id == question_id]}
            ),
            renderer,
        )
        session.answer("low", latency_ms=latency_ms)
        return sum(
            p
            for h, p in session.tracker.posterior.items()
            if effect.hypotheses[h]["rank_value"] < 13
        )

    fast = posterior_after(1000.0)
    slow = posterior_after(9000.0)
    assert fast > slow  # the slow answer was discounted toward the floor
    assert fast > 0 and slow > 0  # nothing is ever eliminated


def test_event_records_the_effective_reliability(card_effect, renderer):
    from tests.conftest import truthful_answer

    session = EffectSession(direct_only(card_effect), renderer)
    question = session.current_question
    session.answer(truthful_answer(card_effect, question, "AS"), latency_ms=9000.0)
    payload = next(e for e in session.history if e.type.value == "hypothesis.updated").payload
    expected = question.reliability * latency_factor(card_effect.latency_channel, 9000.0)
    assert payload["reliability_effective"] == pytest.approx(expected)


def test_typing_rhythm_downgrades_the_strength(card_effect, renderer):
    session = EffectSession(card_effect, renderer)
    assert session.current_mode == "covert"

    # a hesitant "yes" counts as a lean yes
    session.respond_agreement(
        "strong_yes",
        utterance="yes",
        typing_rhythm={"first_key_ms": 4200.0, "median_interval_ms": 800.0, "total_ms": 900.0},
    )
    payload = [e for e in session.history if e.type.value == "hypothesis.updated"][-1].payload
    assert payload["agreement_strength"] == "strong_yes"
    assert payload["agreement_strength_effective"] == "lean_yes"
    assert payload["typing_rhythm"]["first_key_ms"] == 4200.0

    # the softer update moves the asserted (red) partition less than a firm one
    def red_mass(hesitant: bool) -> float:
        s2 = EffectSession(card_effect, renderer)
        rhythm = (
            {"first_key_ms": 4200.0, "median_interval_ms": 800.0, "total_ms": 900.0}
            if hesitant
            else {"first_key_ms": 400.0, "median_interval_ms": 150.0, "total_ms": 500.0}
        )
        s2.respond_agreement("strong_yes", typing_rhythm=rhythm)
        return sum(
            p
            for h, p in s2.tracker.posterior.items()
            if card_effect.hypotheses[h]["color"] == "red"
        )

    assert red_mass(False) > red_mass(True)


def test_api_typing_rhythm_paths(client):
    sid = client.post(
        "/api/sessions", json={"effect_id": "card_prediction", "condition": "b"}
    ).json()["session_id"]
    # typing_rhythm without free_text is rejected
    bad = client.post(
        f"/api/sessions/{sid}/answer",
        json={
            "answer_id": "strong_yes",
            "typing_rhythm": {"first_key_ms": 100, "median_interval_ms": 100, "total_ms": 100},
        },
    )
    assert bad.status_code == 400
    # rhythm rides the free-text reply
    ok = client.post(
        f"/api/sessions/{sid}/answer",
        json={
            "free_text": "yes exactly",
            "latency_ms": 5000.0,
            "typing_rhythm": {
                "first_key_ms": 4200.0,
                "median_interval_ms": 800.0,
                "total_ms": 900.0,
            },
        },
    )
    assert ok.status_code == 200
    trajectory = client.get(f"/api/sessions/{sid}/trajectory").json()
    payload = [e for e in trajectory["events"] if e["type"] == "hypothesis.updated"][-1]["payload"]
    assert payload["agreement_strength_effective"] == "lean_yes"
    assert payload["typing_rhythm"]["median_interval_ms"] == 800.0


def test_exhaustive_resolution_survives_fast_latency(card_effect, renderer):
    """The AGENTS.md backbone under fusion: decisive truthful play with fast
    answers still resolves the hypothesis exactly."""
    session = EffectSession(direct_only(card_effect), renderer)
    while session.phase is Phase.ACTIVE:
        question = session.current_question
        session.answer(truthful_answer(card_effect, question, "7D"), latency_ms=800.0)
    assert session.prediction is not None
    assert session.prediction.hypothesis_id == "7D"
