"""Phase 3: the Brain action contract and deterministic baseline brain.

RED slice: BrainDecision validates hard constraints; the baseline brain runs a
full Card session through the engine hook with default behavior unchanged.
"""

from __future__ import annotations

import pytest

from services.brain.baseline import baseline_decide
from services.brain.contract import Action, BrainDecision, InvalidBrainAction, validate
from services.effects.engine import EffectSession
from tests.conftest import truthful_response


def _direct(question_id: str) -> BrainDecision:
    return BrainDecision(
        action=Action.DIRECT, question_id=question_id, confidence=0.5, reason="test"
    )


def test_validate_accepts_well_formed_direct(card_effect):
    q = card_effect.questions[0]
    decision = validate(_direct(q.id), card_effect, asked=set())
    assert decision.question_id == q.id


def test_validate_rejects_unknown_and_reasked_questions(card_effect):
    q = card_effect.questions[0]
    with pytest.raises(InvalidBrainAction):
        validate(_direct("nope"), card_effect, asked=set())
    with pytest.raises(InvalidBrainAction):
        validate(_direct(q.id), card_effect, asked={q.id})


def test_validate_rejects_covert_without_fishing(card_effect):
    from tests.conftest import direct_only

    effect = direct_only(card_effect)  # fishing disabled: covert is illegal here
    q = effect.questions[0]
    option = q.answers[0].id
    with pytest.raises(InvalidBrainAction):
        validate(
            BrainDecision(
                action=Action.COVERT_PROBE,
                question_id=q.id,
                asserted_answer_id=option,
                confidence=0.5,
                reason="test",
            ),
            effect,
            asked=set(),
        )


def test_validate_rejects_reveal_with_target(card_effect):
    with pytest.raises(InvalidBrainAction):
        validate(
            BrainDecision(action=Action.REVEAL, question_id="q_x", confidence=0.9, reason="t"),
            card_effect,
            asked=set(),
        )


def test_baseline_brain_runs_card_to_completion(card_effect, renderer):
    """Brain-driven session resolves with truthful answers; every decision valid."""
    hypothesis_id = next(iter(card_effect.hypotheses))
    session = EffectSession(card_effect, renderer, decide=baseline_decide)
    decisions = 0
    while session.phase.value == "active":
        decisions += 1
        assert decisions < 100, "brain failed to drive the session to commit"
        truthful_response(session, card_effect, hypothesis_id)
    session.report_outcome(True)
    assert session.prediction is not None
    assert session.prediction.hypothesis_id == hypothesis_id
    actions = [
        e.payload.get("brain_action") for e in session.history if e.type.value == "policy.decision"
    ]
    assert actions and all(a in ("direct", "covert_probe", "force") for a in actions)
