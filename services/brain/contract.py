"""Brain action contract: what LOKI may do next, and what it may not.

Actions map 1:1 onto what the engine can already perform — OBSERVE, WAIT,
REFRAME and friends arrive with the engine support they need. ``validate``
is the hard mask: it runs outside the deciding policy, learned or otherwise.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from enum import Enum

from services.effects.models import EffectDef
from services.policy.method_selection import FishingState, TurnPlan


class Action(str, Enum):
    DIRECT = "direct"
    COVERT_PROBE = "covert_probe"
    FORCE = "force"
    REVEAL = "reveal"


class InvalidBrainAction(ValueError):
    """A Brain decision that violates hard constraints (never served, always raised)."""


@dataclass(frozen=True)
class BrainDecision:
    action: Action
    question_id: str | None  # None for REVEAL (commit now)
    confidence: float
    reason: str
    asserted_answer_id: str | None = None  # COVERT_PROBE only
    salient_answer_id: str | None = None  # FORCE only
    info_gain_bits: float = 0.0

    def to_turn_plan(self) -> TurnPlan | None:
        """Lower the decision to the engine's interaction plan. REVEAL → None,
        which the engine reads as 'nothing informative left' and commits."""
        if self.action is Action.REVEAL:
            return None
        mode = "covert" if self.action is Action.COVERT_PROBE else "direct"
        assert self.question_id is not None
        return TurnPlan(
            question_id=self.question_id,
            mode=mode,
            asserted_answer_id=self.asserted_answer_id,
            info_gain_bits=self.info_gain_bits,
            reason=self.reason,
            salient_answer_id=self.salient_answer_id,
        )


#: decide(effect, posterior, asked, fishing_state) -> BrainDecision.
#: Same inputs as the engine's TurnSelector, so any Brain plugs into the hook.
BrainSelector = Callable[[EffectDef, Mapping[str, float], set[str], FishingState], BrainDecision]


def validate(decision: BrainDecision, effect: EffectDef, asked: set[str]) -> BrainDecision:
    """Hard constraints. Raises InvalidBrainAction; returns the decision unchanged."""
    if decision.action is Action.REVEAL:
        if decision.question_id is not None:
            raise InvalidBrainAction("REVEAL commits — it takes no question")
        return decision
    question = next((q for q in effect.questions if q.id == decision.question_id), None)
    if question is None:
        raise InvalidBrainAction(f"unknown question '{decision.question_id}'")
    if question.id in asked:
        raise InvalidBrainAction(f"question '{question.id}' was already asked")
    options = {a.id for a in question.answers}
    if decision.action is Action.COVERT_PROBE:
        if not question.fishing:
            raise InvalidBrainAction(f"question '{question.id}' disallows fishing")
        if decision.asserted_answer_id not in options:
            raise InvalidBrainAction(
                f"'{decision.asserted_answer_id}' is not an option of '{question.id}'"
            )
    if decision.action is Action.FORCE and decision.salient_answer_id not in options:
        raise InvalidBrainAction(
            f"'{decision.salient_answer_id}' is not an option of '{question.id}'"
        )
    return decision
