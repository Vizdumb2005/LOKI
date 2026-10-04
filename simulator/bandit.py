"""Contextual bandit over turn-level interaction strategies (ROADMAP Phase 6,
docs/rl-policy.md).

A tabular ε-greedy bandit: context = (phase, credibility) cells × three
actions {direct, covert, forced}. Deliberately simple and fully auditable —
the point of the phase is the EXPERIMENT (can a bandit beat the tuned
heuristics?), not the learner's sophistication. Hard constraints (no repeated
questions, the covert ration, credibility floors) are action masks applied by
the selector, never learned.
"""

from __future__ import annotations

import json
import random
from collections.abc import Sequence

from services.effects.models import EffectDef
from services.policy import info_gain
from services.policy.method_selection import (
    DEFAULT_PARAMS,
    FishingState,
    MethodPolicyParams,
    TurnPlan,
    answer_masses,
    covert_candidate,
    force_target,
)

ACTIONS = ("direct", "covert", "forced")

# Context discretization: phase of the session × credibility of the favorite.
PHASES, CREDIBILITY = 3, 3


def context_cell(
    effect: EffectDef,
    posterior: dict[str, float],
    asked: set[str],
    direct_question,  # Question
) -> tuple[int, int]:
    """(phase, credibility) cell for the current decision."""
    phase = min(PHASES - 1, len(asked) * PHASES // max(1, effect.termination.max_turns))
    top_mass = max(answer_masses(effect, posterior, direct_question).items(), key=lambda kv: kv[1])[
        1
    ]
    credibility = 0 if top_mass < 0.5 else 1 if top_mass < 0.75 else 2
    return (phase, credibility)


class TabularBandit:
    def __init__(
        self,
        epsilon: float = 0.3,
        epsilon_min: float = 0.05,
        epsilon_decay: float = 0.995,
        optimistic_init: float = 0.05,
        seed: int | None = None,
    ) -> None:
        self.epsilon = epsilon
        self._epsilon_min = epsilon_min
        self._epsilon_decay = epsilon_decay
        self._optimistic_init = optimistic_init
        self._rng = random.Random(seed)
        self._values: dict[tuple[int, int], dict[str, float]] = {}
        self._counts: dict[tuple[int, int], dict[str, int]] = {}

    def _value(self, cell: tuple[int, int], action: str) -> float:
        return self._values.get(cell, {}).get(action, self._optimistic_init)

    def select(self, cell: tuple[int, int], allowed: Sequence[str]) -> str:
        """Choose an action among the ALLOWED ones (masked bandit)."""
        if not allowed:
            raise ValueError("no actions allowed — the caller must leave one")
        if self._rng.random() < self.epsilon:
            return self._rng.choice(list(allowed))
        return max(allowed, key=lambda a: self._value(cell, a))

    def update(self, cell: tuple[int, int], action: str, reward: float) -> None:
        counts_cell = self._counts.setdefault(cell, {})
        values_cell = self._values.setdefault(cell, {})
        n = counts_cell.get(action, 0)
        values_cell[action] = (values_cell.get(action, self._optimistic_init) * n + reward) / (
            n + 1
        )
        counts_cell[action] = n + 1
        self.epsilon = max(self._epsilon_min, self.epsilon * self._epsilon_decay)

    def greedy_action(self, cell: tuple[int, int]) -> str:
        return max(ACTIONS, key=lambda a: self._value(cell, a))

    def to_dict(self) -> dict:
        return {
            "epsilon": self.epsilon,
            "values": {str(cell): dict(v) for cell, v in self._values.items()},
            "counts": {str(cell): dict(c) for cell, c in self._counts.items()},
        }

    @classmethod
    def from_dict(cls, data: dict) -> "TabularBandit":
        bandit = cls(epsilon=data.get("epsilon", 0.3))
        for cell, values in data.get("values", {}).items():
            key = tuple(int(p) for p in cell.strip("()").split(","))
            bandit._values[key] = dict(values)
        for cell, counts in data.get("counts", {}).items():
            key = tuple(int(p) for p in cell.strip("()").split(","))
            bandit._counts[key] = dict(counts)
        return bandit


class BanditTurnSelector:
    """A turn selector for ``EffectSession`` driven by the bandit.

    Same contract as ``services.policy.method_selection.select_turn``; the
    hard constraints are masks (credibility floor, covert ration, defiance
    cooldown), the learned part is only WHICH masked strategy runs. Reasons
    are recorded as ``bandit:<action>`` so trajectories stay auditable.
    """

    def __init__(
        self,
        agent: TabularBandit,
        params: MethodPolicyParams = DEFAULT_PARAMS,
        explore: bool = True,
    ) -> None:
        self.agent = agent
        self.params = params
        self.explore = explore  # False = greedy (evaluation)
        # (cell, action) of the most recent decision — the training loop reads
        # it to apply the per-turn reward (docs/rl-policy.md §2).
        self.last_decision: tuple[tuple[int, int], str] | None = None

    def __call__(
        self,
        effect: EffectDef,
        posterior: dict[str, float],
        asked: set[str],
        state: FishingState,
    ) -> TurnPlan | None:
        direct_question, gain = info_gain.best_question(effect, posterior, asked)
        if direct_question is None:
            return None

        allowed: list[str] = ["direct"]
        covert = None
        if state.covert_turns < self.params.max_covert_turns:
            covert = covert_candidate(effect, posterior, asked, self.params)
            if covert is not None:
                allowed.append("covert")
        salient = None
        if state.force_cooldown == 0:
            salient = force_target(effect, posterior, direct_question, self.params)
            if salient is not None:
                allowed.append("forced")

        cell = context_cell(effect, posterior, asked, direct_question)
        action = (
            self.agent.select(cell, allowed) if self.explore else self.agent.greedy_action(cell)
        )
        self.last_decision = (cell, action)

        if action == "covert" and covert is not None:
            return TurnPlan(
                covert.question_id,
                "covert",
                covert.asserted_answer_id,
                covert.info_gain_bits,
                "bandit:covert",
            )
        if action == "forced" and salient is not None:
            return TurnPlan(
                direct_question.id,
                "direct",
                None,
                gain,
                "bandit:forced",
                salient_answer_id=salient,
            )
        return TurnPlan(direct_question.id, "direct", None, gain, "bandit:direct")


def serialize(bandit: TabularBandit, path) -> None:
    path.write_text(json.dumps(bandit.to_dict(), indent=2), encoding="utf-8")


def load(path) -> TabularBandit:
    return TabularBandit.from_dict(json.loads(path.read_text(encoding="utf-8")))
