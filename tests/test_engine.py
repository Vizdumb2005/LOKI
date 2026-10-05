"""Engine tests.

The parametrized exhaustive test is the correctness backbone: for EVERY
hypothesis of EVERY registered effect, deterministic truthful responses must
reach a reveal with the right prediction, within the turn budget, without
repeating a question — under the MIXED method policy (covert reads and
direct questions alike, ROADMAP Phase 2). Adding an effect YAML
automatically adds it to this invariant.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from services.effects.engine import CommitReason, EffectSession, InvalidStateError, Phase
from services.effects.loader import load_effects
from tests.conftest import direct_only, truthful_response

EFFECTS_DIR = Path(__file__).resolve().parents[1] / "configs" / "effects"
REGISTRY = load_effects(EFFECTS_DIR)
ALL_EFFECTS = list(REGISTRY.values())


def _play_truthfully(effect, renderer, hypothesis_id: str) -> EffectSession:
    session = EffectSession(effect, renderer)
    guard = 0
    while session.phase is Phase.ACTIVE:
        truthful_response(session, effect, hypothesis_id)
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


def test_first_card_turn_is_a_covert_read(card_effect, renderer):
    """The policy opens The Card with its most credible assertion (classic
    cold reading): the top-mass option of some question, at least fish_floor."""
    from services.policy.method_selection import answer_masses

    session = EffectSession(card_effect, renderer)
    assert session.current_mode == "covert"
    masses = answer_masses(card_effect, session.tracker.posterior, session.current_question)
    assert masses[session.asserted_answer_id] == max(masses.values())
    assert masses[session.asserted_answer_id] >= 0.40
    assert session.asserted_label == "Red"
    assert "Red" in session.ask_message


def test_entropy_decreases_under_truthful_answers(card_effect, renderer):
    session = EffectSession(card_effect, renderer)
    entropies = [session.initial_entropy]
    while session.phase is Phase.ACTIVE:
        truthful_response(session, card_effect, "7D")
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
        truthful_response(session, cramped, "AS")
    assert session.phase is Phase.REVEALED
    assert session.committed_because is CommitReason.MAX_TURNS
    assert session.turn == 2


def test_option_id_on_covert_turn_rejected(card_effect, renderer):
    session = EffectSession(card_effect, renderer)
    assert session.current_mode == "covert"
    with pytest.raises(ValueError, match="agreement strength"):
        session.answer("hearts")
    assert session.turn == 1 and session.phase is Phase.ACTIVE  # state unchanged


def test_agreement_on_direct_turn_rejected(card_effect, renderer):
    session = EffectSession(direct_only(card_effect), renderer)
    assert session.current_mode == "direct"
    with pytest.raises(InvalidStateError, match="direct question"):
        session.respond_agreement("strong_yes")


def test_invalid_option_on_direct_turn_rejected(card_effect, renderer):
    session = EffectSession(direct_only(card_effect), renderer)
    with pytest.raises(ValueError, match="not an option"):
        session.answer("definitely-not-an-option")
    assert session.phase is Phase.ACTIVE
    assert session.turn == 1  # state unchanged


def test_unknown_strength_rejected(card_effect, renderer):
    session = EffectSession(card_effect, renderer)
    with pytest.raises(ValueError, match="unknown agreement strength"):
        session.respond_agreement("purple")
    assert session.turn == 1


def test_unclear_response_advances_without_update(card_effect, renderer):
    session = EffectSession(card_effect, renderer)
    before = session.tracker.posterior
    session.respond_agreement("unclear")
    assert session.tracker.posterior == before  # uncertainty is not evidence
    assert session.turn == 2  # the turn still advanced
    assert session.current_question is not None


def test_response_after_reveal_rejected(card_effect, renderer):
    session = EffectSession(card_effect, renderer)
    while session.phase is Phase.ACTIVE:
        truthful_response(session, card_effect, "AS")
    with pytest.raises(InvalidStateError):
        session.respond_agreement("strong_yes")


def test_outcome_lifecycle_and_history(card_effect, renderer):
    session = EffectSession(card_effect, renderer)
    with pytest.raises(InvalidStateError):
        session.report_outcome(correct=True)  # rejected while ACTIVE
    while session.phase is Phase.ACTIVE:
        truthful_response(session, card_effect, "10C")
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


def test_covert_events_carry_v12_fields(card_effect, renderer):
    session = EffectSession(card_effect, renderer)
    assert session.current_mode == "covert"
    asserted = session.asserted_answer_id
    session.respond_agreement("lean_yes", latency_ms=900.0, utterance="sort of, yeah")

    decision = next(e for e in session.history if e.type.value == "policy.decision")
    assert decision.payload["mode"] == "covert"
    assert decision.payload["asserted_answer_id"] == asserted

    updated = next(e for e in session.history if e.type.value == "hypothesis.updated")
    assert updated.payload["mode"] == "covert"
    assert updated.payload["agreement_strength"] == "lean_yes"
    assert updated.payload["asserted_answer_id"] == asserted
    assert updated.payload["utterance"] == "sort of, yeah"
    assert updated.payload["answer_id"] is None


def test_direct_events_declare_mode(card_effect, renderer):
    from tests.conftest import truthful_answer

    session = EffectSession(direct_only(card_effect), renderer)
    question = session.current_question
    session.answer(truthful_answer(card_effect, question, "AS"), latency_ms=150.0)
    updated = next(e for e in session.history if e.type.value == "hypothesis.updated")
    assert updated.payload["mode"] == "direct"
    assert updated.payload["agreement_strength"] is None
    assert updated.payload["asserted_answer_id"] is None
    decision = next(e for e in session.history if e.type.value == "policy.decision")
    assert decision.payload["mode"] == "direct"
