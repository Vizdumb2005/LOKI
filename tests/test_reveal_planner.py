"""Reveal planner + staging tests (ROADMAP Phase 3).

The planner chooses the multiple-outs path from structured state; the
language layer stages it. The prediction itself and its banded phrasing are
untouched — staging adds beats, never certainty.
"""

from __future__ import annotations

from services.effects.engine import EffectSession, Phase
from services.language.renderer import LanguageRenderer
from services.policy.reveal_planner import (
    RevealPlan,
    RevealStage,
    plan_reveal,
    wants_hesitation,
)
from tests.conftest import truthful_response

RENDERER = LanguageRenderer()


def _rest(total: float, effect) -> list[tuple[str, float]]:
    """Spread the remaining mass over a few other hypotheses (deterministically)."""
    others = list(effect.hypotheses)[:3]
    share = total / max(1, len(others))
    return [(h, share) for h in others]


def test_high_confidence_takes_the_progressive_ladder(card_effect):
    asked = ["q_color", "q_rank_bucket"]
    candidates = [("7D", 0.90), ("7C", 0.02), ("7H", 0.02)] + _rest(0.06, card_effect)
    plan = plan_reveal(card_effect, candidates, asked)
    assert plan.path == "progressive"
    assert plan.candidates[0] == "7D"
    kinds = [s.kind for s in plan.stages]
    assert kinds.count("attribute") == 2
    labels = [s.label for s in plan.stages]
    # Prioritizes un-interviewed corpus attributes (suit: Diamonds, rank: Odd)
    assert "Diamonds" in labels or "Odd" in labels


def test_ladder_prioritizes_uninterviewed_corpus_attributes(card_effect):
    candidates = [("7D", 0.90), ("7C", 0.02), ("7H", 0.02)] + _rest(0.06, card_effect)
    plan = plan_reveal(card_effect, candidates, ["q_color"])
    attrs = [s.attr for s in plan.stages]
    # Draw from unasked questions first rather than restating asked color
    assert "color" not in attrs or len(attrs) > 1
    assert any(a in ("suit", "rank_value", "parity", "rank_bucket") for a in attrs)


def test_shared_category_takes_the_cluster_out(card_effect):
    # Two hearts at mid confidence: the suit is the family both live in.
    candidates = [("7H", 0.60), ("KH", 0.15), ("7D", 0.05)] + _rest(0.20, card_effect)
    plan = plan_reveal(card_effect, candidates, ["q_color"])
    assert plan.path == "category_cluster"
    stage = plan.stages[0]
    assert stage.kind == "category"
    assert stage.attr == "suit"
    assert stage.label == "Hearts"


def test_mid_confidence_without_a_shared_family_stays_plain(card_effect):
    candidates = [("7H", 0.60), ("KC", 0.15), ("7D", 0.05)] + _rest(0.20, card_effect)
    plan = plan_reveal(card_effect, candidates, [])
    assert plan.path == "plain"
    assert plan.stages == ()


def test_tight_top_two_takes_the_deduction_out(card_effect):
    candidates = [("7D", 0.40), ("8D", 0.35), ("7H", 0.10)] + _rest(0.15, card_effect)
    plan = plan_reveal(card_effect, candidates, [])
    assert plan.path == "dual_deduction"
    stage = plan.stages[0]
    assert stage.kind == "deduction"
    assert stage.label == "Eight of Diamonds"  # display name, not the id


def test_plain_fallback_when_the_top_is_soft_and_spread(card_effect):
    candidates = [("7D", 0.30), ("KC", 0.20), ("7H", 0.10)] + _rest(0.40, card_effect)
    plan = plan_reveal(card_effect, candidates, [])
    assert plan.path == "plain"
    assert plan.stages == ()


def test_plan_is_deterministic(card_effect):
    candidates = [("7H", 0.60), ("KH", 0.15), ("7D", 0.05)] + _rest(0.20, card_effect)
    assert plan_reveal(card_effect, candidates, ["q_color"]) == plan_reveal(
        card_effect, candidates, ["q_color"]
    )


def test_staging_renders_beats_and_respects_the_hesitation_band():
    stages = (
        RevealStage(kind="attribute", attr="color", label="Red"),
        RevealStage(kind="attribute", attr="rank_bucket", label="Six or Seven"),
    )
    decisive = RENDERER.stage_reveal(stages, "Seven of Diamonds", 0.90, "s1")
    assert [k for k, _ in decisive] == ["attribute", "attribute"]  # no hesitation beat
    assert any("Red" in t for _, t in decisive)
    assert any("Six or Seven" in t for _, t in decisive)

    warm = RENDERER.stage_reveal(stages, "Seven of Diamonds", 0.70, "s1")
    assert [k for k, _ in warm][-1] == "hesitation"
    hedged = RENDERER.stage_reveal(stages, "Seven of Diamonds", 0.50, "s1")
    assert all(k != "hesitation" for k, _ in hedged)  # already-hedged band: no pile-on


def test_deduction_beat_names_both_candidates():
    plan = RevealPlan(
        path="dual_deduction",
        candidates=("7D", "8D"),
        stages=(RevealStage(kind="deduction", attr=None, label="Eight of Diamonds"),),
    )
    beats = RENDERER.stage_reveal(plan.stages, "Seven of Diamonds", 0.45, "s2")
    text = beats[0][1]
    assert "Seven of Diamonds" in text and "Eight of Diamonds" in text


def test_wants_hesitation_window():
    assert not wants_hesitation(0.59)
    assert wants_hesitation(0.60)
    assert wants_hesitation(0.84)
    assert not wants_hesitation(0.85)


def test_engine_builds_a_reveal_plan_and_stages(card_effect, renderer):
    session = EffectSession(card_effect, renderer)
    while session.phase is not Phase.REVEALED:
        truthful_response(session, card_effect, "7D")
    assert session.reveal_plan is not None
    assert session.reveal_plan.candidates[0] == "7D"
    # decisive truthful play ends above the strong-commit band
    assert session.prediction is not None and session.prediction.confidence >= 0.80
    revealed = next(e for e in session.history if e.type.value == "effect.revealed")
    assert revealed.payload["reveal_path"] == session.reveal_plan.path
    assert revealed.payload["reveal_candidates"][0] == "7D"
    assert isinstance(revealed.payload["stages"], list)
    # the banded identity line stays the message; every beat is non-empty prose
    assert session.reveal_message
    assert all(text for _, text in session.reveal_stage_messages)


def test_reframe_after_missed_and_unclear_reads(card_effect, renderer):
    session = EffectSession(card_effect, renderer)
    assert session.current_mode == "covert"
    session.respond_agreement("lean_no")
    assert session.current_reframe == ("missed", "Red")  # turn 1 asserts Red
    message = session.ask_message
    assert "\n\n" in message  # reframe opens the next turn's message
    decision = [e for e in session.history if e.type.value == "policy.decision"][-1]
    assert decision.payload["reframe"] == "missed"

    session2 = EffectSession(card_effect, renderer)
    session2.respond_agreement("unclear")
    assert session2.current_reframe == ("unclear", "Red")


def test_reframe_clears_after_one_turn(card_effect, renderer):
    session = EffectSession(card_effect, renderer)
    session.respond_agreement("lean_no")
    assert session.current_reframe is not None
    truthful_response(session, card_effect, "7D")  # the backoff turn (direct)
    assert session.current_reframe is None  # cleared at the next selection
    assert "\n\n" not in session.ask_message


def test_reframe_renders_from_state_only(renderer):
    line_miss = renderer.reframe("missed", "Red", "s", 3)
    line_unclear = renderer.reframe("unclear", "Red", "s", 3)
    assert line_miss != line_unclear
    assert renderer.reframe("missed", "Red", "s", 3) == line_miss  # deterministic
