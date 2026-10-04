"""Agreement-response model tests (ROADMAP Phase 2).

Contract: soft updates only — every hypothesis stays alive; affirmations
lift the asserted partition, negations shift mass off it without picking a
replacement, and unclear touches nothing.
"""

from __future__ import annotations

import pytest

from services.effects.agreement import RESPONSE_MODEL, agreement_likelihoods
from services.language.response_signals import AgreementStrength as S


def _mass(lik: dict[str, float], effect, predicate_key: str, value) -> float:
    return sum(p for h, p in lik.items() if effect.hypotheses[h][predicate_key] == value)


def test_response_model_columns_sum_to_one():
    """Columns are P(strength | holds?) — each must be a proper distribution
    (the simulator samples them directly)."""
    for holds in (True, False):
        assert sum(row[holds] for row in RESPONSE_MODEL.values()) == pytest.approx(1.0), holds


@pytest.mark.parametrize("strength", list(S))
def test_every_strength_keeps_every_hypothesis_alive(card_effect, strength):
    lik = agreement_likelihoods(card_effect, card_effect.questions[0], "hearts", strength)
    assert len(lik) == 52
    assert all(v > 0.0 for v in lik.values())


def test_strong_yes_lifts_asserted_partition(card_effect):
    lik = agreement_likelihoods(card_effect, card_effect.questions[-1], "red", S.STRONG_YES)
    assert _mass(lik, card_effect, "color", "red") > _mass(lik, card_effect, "color", "black")


def test_affirmation_strength_is_monotonic(card_effect):
    def ratio(strength):
        lik = agreement_likelihoods(card_effect, card_effect.questions[-1], "red", strength)
        return lik["2H"] / lik["2C"]  # red card vs black card

    assert ratio(S.STRONG_YES) > ratio(S.LEAN_YES) > 1.0


def test_negation_shifts_off_asserted_without_picking_a_winner(card_effect):
    lik = agreement_likelihoods(card_effect, card_effect.questions[-1], "red", S.LEAN_NO)
    red = _mass(lik, card_effect, "color", "red")
    black = _mass(lik, card_effect, "color", "black")
    assert black > red
    # "not really" says nothing about WHICH alternative: every black-suit
    # hypothesis gets the same likelihood.
    black_lik = {
        lik[h] for h in card_effect.hypotheses if card_effect.hypotheses[h]["color"] == "black"
    }
    assert len(black_lik) == 1


def test_unclear_is_flat(card_effect):
    lik = agreement_likelihoods(card_effect, card_effect.questions[0], "hearts", S.UNCLEAR)
    assert all(v == 1.0 for v in lik.values())


def test_unknown_asserted_answer_rejected(card_effect):
    with pytest.raises(ValueError, match="not an option"):
        agreement_likelihoods(card_effect, card_effect.questions[0], "not-a-suit", S.STRONG_YES)


def test_decisive_words_match_direct_answer_strength(card_effect):
    """A flat denial/affirmation is semantically the participant answering the
    complementary option — its likelihood ratio must rival a direct answer's.
    The softness lives in the HEDGES ("sort of", "not really"), not here."""
    question = card_effect.questions[3]  # q_high_card
    direct = card_effect.likelihoods(question, "low")
    assert direct["2H"] / direct["KC"] == pytest.approx(0.95 / 0.05)

    covert_yes = agreement_likelihoods(card_effect, question, "low", S.STRONG_YES)
    assert covert_yes["2H"] / covert_yes["KC"] == pytest.approx(0.70 / 0.05)
    covert_no = agreement_likelihoods(card_effect, question, "high", S.STRONG_NO)
    assert covert_no["2H"] / covert_no["KC"] == pytest.approx(0.30 / 0.02)

    # And the hedge ratios are much weaker than either.
    lean = agreement_likelihoods(card_effect, question, "low", S.LEAN_YES)
    assert lean["2H"] / lean["KC"] < covert_yes["2H"] / covert_yes["KC"]
