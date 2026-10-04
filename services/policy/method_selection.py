"""Method Selection Layer (docs/architecture.md §3.3; ROADMAP Phase 2).

Chooses HOW the next turn interacts: a direct question (progressive
narrowing) or a covert fishing statement that asserts the option the
posterior currently favors. Hand-designed heuristics, v1 — the contextual
bandit comparison is ROADMAP Phase 6, and the third method of the
architecture doc (direct inference from passive signals) already exists via
observation channels plus the commit path.

Boundary: this layer selects the interaction only. It never touches the
posterior, never invents evidence, and never commits — a cold reader who
falsifies the books is a bug, not a feature (digital-translation.md,
verification rule 2).
"""

from __future__ import annotations

from dataclasses import dataclass, replace

from services.effects.models import EffectDef
from services.policy import info_gain


@dataclass(frozen=True)
class TurnPlan:
    """The interaction the engine should present next."""

    question_id: str
    mode: str  # "direct" | "covert"
    asserted_answer_id: str | None
    info_gain_bits: float
    reason: str
    # ROADMAP Phase 4: choice-architecture emphasis for direct turns — the
    # option the UI should make salient (None = no steering this turn). The
    # participant's click is still a plain Bayesian answer.
    salient_answer_id: str | None = None


@dataclass
class FishingState:
    """Per-session record of how the fishing and forcing have been landing.

    Mutated by :func:`select_turn` (cooldown accounting) and by the engine
    (miss counting, covert-turn counting, defiance cooldown).
    """

    consecutive_misses: int = 0
    cooldown_turns: int = 0
    covert_turns: int = 0
    force_cooldown: int = 0


@dataclass(frozen=True)
class MethodPolicyParams:
    """Tuning knobs (docs/covert-fishing.md). Shared by all effects in v1."""

    # Minimum posterior mass on the asserted option — asserting a 1-in-52
    # shot is bad cold reading.
    fish_floor: float = 0.40
    # Only fish questions with at most this many options. A denial ("not
    # really") eliminates ONLY the asserted reading, so on a k-option
    # question a miss leaves k-1 rivals unresolved; on a binary question it
    # resolves the whole complement. Multi-option dimensions go direct.
    max_fish_options: int = 2
    # Consecutive non-affirming responses before backing off to direct
    # narrowing for ``cooldown_turns`` turns. 1 = any miss sends the policy
    # back to plain questions; only landing reads keep the fishing going —
    # the adaptive mix that keeps question-limited effects resolvable.
    miss_limit: int = 1
    cooldown_turns: int = 1
    # Stop fishing this close to the turn budget so precision narrowing
    # always has room to land.
    reserve_turns: int = 2
    # Hard ration of covert turns per session. Graded reactions carry less
    # information than option clicks (the documented SNR failure mode), and
    # the measured gates (accuracy, forced-commit rate, mystery gap at
    # kappa <= 0.25 — see docs/covert-fishing.md) hold at ONE read per
    # session by default; a ratio parameter allows adaptive multi-read sessions.
    max_covert_turns: int = 1
    # Target covert read-to-question ratio (e.g. 0.20 = 1 read per 5 max turns).
    covert_ratio: float = 0.20
    # ROADMAP Phase 4: minimum posterior mass on the emphasized option —
    # biasing a near-coin-flip is meaningless (and unfelt).
    force_floor: float = 0.60


DEFAULT_PARAMS = MethodPolicyParams()


def force_target(
    effect: EffectDef,
    posterior: dict[str, float],
    question,  # Question — duck-typed to avoid an import cycle
    params: MethodPolicyParams = DEFAULT_PARAMS,
) -> str | None:
    """The option the choice-architecture primitives should emphasize, or None.

    The maximum-mass answer option of the question, when its partition holds
    at least ``force_floor`` of the posterior. Deterministic: first in
    declaration order wins ties.
    """
    masses = answer_masses(effect, posterior, question)
    top_id, top_mass = max(masses.items(), key=lambda kv: kv[1])
    if top_mass < params.force_floor:
        return None
    return top_id


def answer_masses(
    effect: EffectDef,
    posterior: dict[str, float],
    question,  # Question — kept untyped to avoid an import cycle
) -> dict[str, float]:
    """Posterior mass under each answer option's partition."""
    masses = {a.id: 0.0 for a in question.answers}
    for hid, attrs in effect.hypotheses.items():
        p = posterior.get(hid, 0.0)
        if p <= 0.0:
            continue
        for a in question.answers:
            if a.predicate.matches(attrs):
                masses[a.id] += p
                break  # partition rule: exactly one answer matches
    return masses


def covert_candidate(
    effect: EffectDef,
    posterior: dict[str, float],
    asked: set[str],
    params: MethodPolicyParams = DEFAULT_PARAMS,
) -> TurnPlan | None:
    """The most informative credible fishing assertion, or ``None``.

    The unasked, fishing-enabled question whose top answer carries credible
    mass (>= ``fish_floor``); among those, maximum expected information gain
    (first in declaration order breaks ties — deterministic). Also the
    masking helper for the bandit policy (docs/rl-policy.md §1).
    """
    best: tuple[str, str, float] | None = None  # (question_id, asserted_id, gain)
    best_gain = 0.0
    for question in effect.questions:
        if question.id in asked or not question.fishing:
            continue
        if len(question.answers) > params.max_fish_options:
            continue  # a denial can't resolve the complement of a wide option set
        top_id, top_mass = max(
            answer_masses(effect, posterior, question).items(), key=lambda kv: kv[1]
        )
        if top_mass < params.fish_floor:
            continue  # not a credible assertion — a 1-in-52 read is bad theater
        gain = info_gain.question_info_gain(effect, posterior, question)
        if gain > best_gain + 1e-12:
            best = (question.id, top_id, gain)
            best_gain = gain
    if best is not None:
        return TurnPlan(best[0], "covert", best[1], best[2], "credible_assertion")
    return None


def select_turn(
    effect: EffectDef,
    posterior: dict[str, float],
    asked: set[str],
    state: FishingState,
    params: MethodPolicyParams = DEFAULT_PARAMS,
) -> TurnPlan | None:
    """Plan the next turn, or ``None`` when no informative interaction remains.

    The direct candidate always comes from the information-gain policy. The
    covert candidate is the unasked, fishing-enabled question whose top answer
    carries credible mass (>= ``fish_floor``); among those, the one with the
    maximum expected information gain wins (first in declaration order breaks
    ties — deterministic). ``None`` means commit.
    """
    direct_question, direct_gain = info_gain.best_question(effect, posterior, asked)
    if direct_question is None:
        return None

    def _direct(reason: str) -> TurnPlan:
        """A direct turn, with choice-architecture emphasis unless the
        post-defiance cooldown says to sit a turn out (docs/choice-architecture.md §3)."""
        plan = TurnPlan(direct_question.id, "direct", None, direct_gain, reason)
        if state.force_cooldown > 0:
            state.force_cooldown -= 1
            return plan
        salient = force_target(effect, posterior, direct_question, params)
        if salient is not None:
            return replace(plan, salient_answer_id=salient)
        return plan

    if state.cooldown_turns > 0:
        state.cooldown_turns -= 1
        return _direct("cooldown_after_misses")
    if state.consecutive_misses >= params.miss_limit:
        # Back off to direct narrowing; the miss counter resets with the
        # cooldown so fishing can resume once the direct turn has landed.
        state.cooldown_turns = params.cooldown_turns
        state.consecutive_misses = 0
        return _direct("backoff_after_misses")
    if effect.termination.max_turns - len(asked) <= params.reserve_turns:
        return _direct("budget_reserve")

    # Dynamic covert turn allowance based on session max turns and ratio
    if params.max_covert_turns == 0:
        effective_max_covert = 0
    else:
        effective_max_covert = (
            max(
                params.max_covert_turns,
                int(effect.termination.max_turns * params.covert_ratio),
            )
            if params.covert_ratio > 0
            else params.max_covert_turns
        )

    if state.covert_turns >= effective_max_covert:
        return _direct("covert_budget_spent")

    covert = covert_candidate(effect, posterior, asked, params)
    if covert is not None:
        return TurnPlan(
            covert.question_id,
            "covert",
            covert.asserted_answer_id,
            covert.info_gain_bits,
            covert.reason,
        )
    return _direct("max_expected_information_gain")
