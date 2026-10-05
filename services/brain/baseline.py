"""Deterministic baseline Brain: the hand-designed method policy behind the
BrainDecision contract. Behavior-identical to the engine default; the contract
(and its logged action) is the only thing new. The heuristic stays as the
reference the learned policy must beat (mission Phase 8)."""

from __future__ import annotations

from collections.abc import Mapping

from services.brain.contract import Action, BrainDecision
from services.effects.models import EffectDef
from services.policy.method_selection import (
    DEFAULT_PARAMS,
    FishingState,
    select_turn,
)


def baseline_decide(
    effect: EffectDef,
    posterior: Mapping[str, float],
    asked: set[str],
    state: FishingState,
) -> BrainDecision:
    plan = select_turn(effect, dict(posterior), asked, state, DEFAULT_PARAMS)
    if plan is None:
        confidence = max(posterior.values()) if posterior else 0.0
        return BrainDecision(
            action=Action.REVEAL,
            question_id=None,
            confidence=confidence,
            reason="no_informative_question",
        )
    if plan.mode == "covert":
        action, asserted, salient = Action.COVERT_PROBE, plan.asserted_answer_id, None
    elif plan.salient_answer_id is not None:
        action, asserted, salient = Action.FORCE, None, plan.salient_answer_id
    else:
        action, asserted, salient = Action.DIRECT, None, None
    return BrainDecision(
        action=action,
        question_id=plan.question_id,
        confidence=max(posterior.values()) if posterior else 0.0,
        reason=plan.reason,
        asserted_answer_id=asserted,
        salient_answer_id=salient,
        info_gain_bits=plan.info_gain_bits,
    )
