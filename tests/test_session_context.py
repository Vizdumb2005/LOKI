"""Phase 2 gate: a complete session replays from structured events alone."""

from __future__ import annotations

import pytest

from services.effects.engine import EffectSession
from services.session.context import (
    REPLAY_PARITY_FIELDS,
    SessionSnapshot,
    replay,
    snapshot_from_session,
)
from tests.conftest import truthful_response


def _run_session(effect, renderer, hypothesis_id: str) -> EffectSession:
    session = EffectSession(effect, renderer)
    while session.phase.value == "active":
        truthful_response(session, effect, hypothesis_id)
    session.report_outcome(True)
    return session


def test_replay_reproduces_final_snapshot(card_effect, renderer):
    hypothesis_id = next(iter(card_effect.hypotheses))
    session = _run_session(card_effect, renderer, hypothesis_id)
    trail = replay(session.history, max_turns=session.effect.termination.max_turns)
    assert len(trail) == len(session.history)
    final, live = trail[-1], snapshot_from_session(session)
    for field in REPLAY_PARITY_FIELDS:
        assert getattr(final, field) == getattr(live, field), field
    assert final.entropy_bits == pytest.approx(live.entropy_bits)
    assert final.confidence == pytest.approx(live.confidence)
    assert final.to_dict()["performance"]["phase"] == "outcome"


def test_replay_needs_only_events(card_effect, renderer):
    """Replay input is history + budget; the live session object is never touched."""
    hypothesis_id = next(iter(card_effect.hypotheses))
    session = _run_session(card_effect, renderer, hypothesis_id)
    events = list(session.history)
    del session
    trail = replay(events, max_turns=card_effect.termination.max_turns)
    assert isinstance(trail[-1], SessionSnapshot)
    assert trail[-1].responses > 0
    assert trail[-1].mystery < 1.0
