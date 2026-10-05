"""Choice architecture / psychological forcing tests (ROADMAP Phase 4).

The emphasis is presentation only: the click stays a plain Bayesian answer,
defiance is folded into the performance, and the simulator models the
mechanical choice shift without claiming real priming psychology
(docs/choice-architecture.md).
"""

from __future__ import annotations

import random

import pytest

from services.effects.engine import EffectSession, Phase
from services.policy.method_selection import FishingState, MethodPolicyParams, select_turn
from simulator.participant import TruthfulNoisyParticipant
from tests.conftest import truthful_response


def _hearts_posterior(card_effect) -> dict[str, float]:
    """A posterior heavily concentrated on hearts (0.95) — every heart-card
    equally likely, everything else sharing the rest."""
    hearts = [h for h, a in card_effect.hypotheses.items() if a["suit"] == "hearts"]
    others = [h for h in card_effect.hypotheses if h not in hearts]
    posterior = {h: 0.95 / len(hearts) for h in hearts}
    posterior.update({h: 0.05 / len(others) for h in others})
    return posterior


def _biased_effect():
    """A tiny effect with a strong prior (0.7 on 'a') whose best question is
    'a' vs the rest — a credible favorite by construction."""
    from services.effects.models import (
        AnswerOption,
        EffectDef,
        Predicate,
        Question,
        Termination,
    )

    hyps = {h: {"name": h.upper(), "v": v} for v, h in enumerate(["a", "b", "c", "d"], 1)}
    return EffectDef(
        id="t",
        title="t",
        description="d",
        hypotheses=hyps,
        prior={"a": 0.7, "b": 0.1, "c": 0.1, "d": 0.1},
        questions=[
            Question(
                id="q_a",
                text="?",
                answers=[
                    AnswerOption(
                        id="a", label="Alpha", predicate=Predicate(attr="v", op="eq", value=1)
                    ),
                    AnswerOption(
                        id="rest", label="Rest", predicate=Predicate(attr="v", op="ne", value=1)
                    ),
                ],
            ),
            Question(
                id="q_pair",
                text="?",
                answers=[
                    AnswerOption(
                        id="lo", label="Low", predicate=Predicate(attr="v", op="lte", value=2)
                    ),
                    AnswerOption(
                        id="hi", label="High", predicate=Predicate(attr="v", op="gte", value=3)
                    ),
                ],
            ),
            # a spare dimension so a defiance on q_pair has a next turn to open
            Question(
                id="q_mod",
                text="?",
                answers=[
                    AnswerOption(
                        id="rem1",
                        label="Remainder one",
                        predicate=Predicate(attr="v", op="mod_eq", mod=3, value=1),
                    ),
                    AnswerOption(
                        id="rem2",
                        label="Remainder two",
                        predicate=Predicate(attr="v", op="mod_eq", mod=3, value=2),
                    ),
                    AnswerOption(
                        id="rem0",
                        label="Divisible by three",
                        predicate=Predicate(attr="v", op="mod_eq", mod=3, value=0),
                    ),
                ],
            ),
        ],
        termination=Termination(entropy_threshold_bits=0.1, max_turns=5),
    )


def test_force_target_requires_a_credible_favorite(card_effect):
    from services.policy.method_selection import answer_masses, force_target

    uniform = {h: 1.0 / 52 for h in card_effect.hypotheses}
    color = next(q for q in card_effect.questions if q.id == "q_color")
    assert force_target(card_effect, uniform, color) is None  # 0.5 < force_floor

    posterior = _hearts_posterior(card_effect)
    suit = next(q for q in card_effect.questions if q.id == "q_suit")
    assert force_target(card_effect, posterior, suit) == "hearts"
    # sanity: the target really holds >= floor
    masses = answer_masses(card_effect, posterior, suit)
    assert masses["hearts"] >= 0.60


def test_direct_plan_carries_the_salient_option():
    effect = _biased_effect()
    # max_covert_turns=0 isolates the direct path: q_a would otherwise be
    # fished (its favorite is credible), and forcing rides on DIRECT turns.
    params = MethodPolicyParams(max_covert_turns=0)
    plan = select_turn(effect, dict(effect.prior), set(), FishingState(), params)
    assert plan.mode == "direct"
    assert plan.question_id == "q_mod"  # the max-information-gain question
    assert plan.salient_answer_id == "rem1"  # {a, d} holds 0.8 of the prior


def test_force_cooldown_sits_out_one_turn():
    effect = _biased_effect()
    params = MethodPolicyParams(max_covert_turns=0)
    state = FishingState(force_cooldown=1)
    plan = select_turn(effect, dict(effect.prior), set(), state, params)
    assert plan.mode == "direct"
    assert plan.salient_answer_id is None  # the turn after a defiance
    assert state.force_cooldown == 0
    resumed = select_turn(effect, dict(effect.prior), set(), state, params)
    # forcing resumes on the next direct turn with a credible favorite
    assert resumed.salient_answer_id is not None


def test_covert_turns_never_carry_a_force(card_effect):
    uniform = {h: 1.0 / 52 for h in card_effect.hypotheses}
    plan = select_turn(card_effect, uniform, set(), FishingState())
    assert plan.mode == "covert"
    assert plan.salient_answer_id is None


def test_engine_records_force_and_defiance(renderer):
    from tests.test_forcing import _biased_effect

    effect = _biased_effect()
    session = EffectSession(effect, renderer)
    # turn 1 is the covert read on q_a (asserting "a"); a decisive "yes"
    # spends the ration, so turn 2 is a direct turn with a salient option.
    session.respond_agreement("strong_yes")
    assert session.current_mode == "direct"
    salient = session.current_force_target
    assert salient is not None  # ~0.97 posterior mass sits on one option
    decision = [e for e in session.history if e.type.value == "policy.decision"][-1]
    assert decision.payload["force_target"] == salient
    salient_label = next(a.label for a in session.current_question.answers if a.id == salient)

    # defy the force with a different valid option
    other = next(a.id for a in session.current_question.answers if a.id != salient)
    session.answer(other)
    assert session.current_reframe == ("defied", salient_label)
    assert "\n\n" in session.ask_message  # the defiance opens the next turn
    # the defiance cooldown sat the next turn out: no emphasis on it
    assert session.current_force_target is None


def test_matching_the_force_raises_no_reframe(renderer):
    from tests.test_forcing import _biased_effect

    effect = _biased_effect()
    session = EffectSession(effect, renderer)
    session.respond_agreement("strong_yes")
    salient = session.current_force_target
    assert salient is not None
    session.answer(salient)
    assert session.current_reframe is None
    if session.phase is Phase.ACTIVE:
        assert "\n\n" not in session.ask_message


def test_invariant_holds_with_forcing_active(card_effect, renderer):
    """The AGENTS.md backbone under the Phase 4 machinery: decisive truthful
    play still resolves the hypothesis exactly."""
    session = EffectSession(card_effect, renderer)
    while session.phase is Phase.ACTIVE:
        truthful_response(session, card_effect, "7D")
    assert session.prediction is not None
    assert session.prediction.hypothesis_id == "7D"


def test_simulator_concentrates_noise_on_the_salient_option(card_effect):
    """With susceptibility 1.0 all scattered-noise mass lands on the salient
    option; with 0.0 the distribution is the classic uniform noise."""
    question = next(q for q in card_effect.questions if q.id == "q_suit")
    rng = random.Random(7)

    p = TruthfulNoisyParticipant(
        card_effect, "7D", rng, reliability_override=0.5, force_susceptibility=1.0
    )
    picks = {p.answer(question, "spades") for _ in range(100)}
    # truth=diamonds plus the captured noise; hearts/clubs never surface
    assert picks == {"diamonds", "spades"}

    p0 = TruthfulNoisyParticipant(
        card_effect, "7D", rng, reliability_override=0.5, force_susceptibility=0.0
    )
    salient_picks = sum(1 for _ in range(3000) if p0.answer(question, "spades") == "spades")
    expected = 3000 * 0.5 / 3  # (1 - r) / (k - 1) with r = 0.5, k = 4
    assert abs(salient_picks - expected) < 150


def test_binary_questions_are_unaffected_by_susceptibility(card_effect):
    """On a binary question the noise has nowhere else to go, so the salient
    option's pick rate equals the plain noise rate."""
    question = next(q for q in card_effect.questions if q.id == "q_color")
    rng = random.Random(11)
    p = TruthfulNoisyParticipant(
        card_effect, "7D", rng, reliability_override=0.5, force_susceptibility=0.9
    )
    # truth = red; salient = black. P(black) = (1 - r) regardless of s.
    black = sum(1 for _ in range(2000) if p.answer(question, "black") == "black")
    assert black == pytest.approx(1000, abs=120)


def test_view_exposes_salient_option(client, card_effect):
    sid = client.post(
        "/api/sessions", json={"effect_id": "card_prediction", "condition": "b"}
    ).json()["session_id"]
    view = client.get(f"/api/sessions/{sid}").json()
    assert view["mode"] == "covert"
    assert view["salient_option_id"] is None  # covert turns never steer twice

    client.post(f"/api/sessions/{sid}/answer", json={"answer_id": "strong_yes"})
    view = client.get(f"/api/sessions/{sid}").json()
    assert view["phase"] == "active" and view["mode"] == "direct"
    if view["salient_option_id"] is not None:
        assert view["salient_option_id"] in {o["id"] for o in view["options"]}
