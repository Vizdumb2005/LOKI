"""Engine tests.

The parametrized exhaustive test is the correctness backbone: for EVERY
hypothesis of EVERY registered effect, deterministic truthful answers must
reach a reveal with the right prediction, within the turn budget, without
repeating a question. Adding an effect YAML automatically adds it to this
invariant.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from services.effects.engine import CommitReason, EffectSession, InvalidStateError, Phase
from services.effects.loader import load_effects
from tests.conftest import truthful_answer

EFFECTS_DIR = Path(__file__).resolve().parents[1] / "configs" / "effects"
REGISTRY = load_effects(EFFECTS_DIR)
ALL_EFFECTS = list(REGISTRY.values())


def _play_truthfully(effect, renderer, hypothesis_id: str) -> EffectSession:
    session = EffectSession(effect, renderer)
    guard = 0
    while session.phase is Phase.ACTIVE:
        assert session.current_question is not None
        session.answer(truthful_answer(effect, session.current_question, hypothesis_id))
        guard += 1
        assert guard <= effect.termination.max_turns + 2, "engine failed to terminate"
    return session


@pytest.mark.parametrize("effect", ALL_EFFECTS, ids=[e.id for e in ALL_EFFECTS])
def test_resolves_every_hypothesis(effect, renderer):
    for hypothesis_id in effect.hypotheses:
        session = _play_truthfully(effect, renderer, hypothesis_id)
        assert session.phase is Phase.REVEALED
        assert session.prediction is not None
        assert session.prediction.hypothesis_id == hypothesis_id
        assert session.turn <= effect.termination.max_turns
        assert len(session.asked) == len(set(session.asked)), "question repeated"


def test_entropy_decreases_under_truthful_answers(card_effect, renderer):
    session = EffectSession(card_effect, renderer)
    entropies = [session.initial_entropy]
    while session.phase is Phase.ACTIVE:
        session.answer(truthful_answer(card_effect, session.current_question, "7D"))
        entropies.append(session.tracker.entropy())
    assert entropies[-1] < entropies[0] / 2
    assert session.prediction is not None and session.prediction.hypothesis_id == "7D"


def test_max_turns_forces_commit(card_effect, renderer):
    from services.effects.models import Termination

    cramped = card_effect.model_copy(
        update={"termination": Termination(entropy_threshold_bits=0.05, max_turns=2)}
    )
    session = EffectSession(cramped, renderer)
    while session.phase is Phase.ACTIVE:
        session.answer(truthful_answer(cramped, session.current_question, "AS"))
    assert session.phase is Phase.REVEALED
    assert session.committed_because is CommitReason.MAX_TURNS
    assert session.turn == 2


def test_invalid_answer_rejected(card_effect, renderer):
    session = EffectSession(card_effect, renderer)
    with pytest.raises(ValueError, match="not an option"):
        session.answer("definitely-not-an-option")
    assert session.phase is Phase.ACTIVE
    assert session.turn == 1  # state unchanged


def test_answer_after_reveal_rejected(card_effect, renderer):
    session = EffectSession(card_effect, renderer)
    session.answer(truthful_answer(card_effect, session.current_question, "AS"))
    while session.phase is Phase.ACTIVE:
        session.answer(truthful_answer(card_effect, session.current_question, "AS"))
    with pytest.raises(InvalidStateError):
        current = session.current_question or card_effect.questions[0]
        session.answer(truthful_answer(card_effect, current, "AS"))


def test_outcome_lifecycle_and_history(card_effect, renderer):
    session = EffectSession(card_effect, renderer)
    with pytest.raises(InvalidStateError):
        session.report_outcome(correct=True)  # rejected while ACTIVE
    while session.phase is Phase.ACTIVE:
        session.answer(truthful_answer(card_effect, session.current_question, "10C"))
    session.report_outcome(correct=True)
    assert session.phase is Phase.OUTCOME
    with pytest.raises(InvalidStateError):
        session.report_outcome(correct=False)  # outcome is final

    types = [e.type.value for e in session.history]
    assert types[0] == "session.started"
    assert types.count("policy.decision") == session.turn
    assert types.count("hypothesis.updated") == session.turn
    assert "effect.revealed" in types
    assert types[-1] == "participant.outcome"
    assert all(e.session_id == session.session_id for e in session.history)
