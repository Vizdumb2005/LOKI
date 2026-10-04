"""Response Signal Extractor tests (ROADMAP Phase 2).

The parser is the conservative boundary between participant words and the
Bayesian engine: anything it cannot place is `unclear`, never a guess.
"""

from __future__ import annotations

import pytest

from services.language.response_signals import AgreementStrength, parse_agreement

S = AgreementStrength


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        # strong affirmation
        ("yes", S.STRONG_YES),
        ("Yes!", S.STRONG_YES),
        ("yeah exactly", S.STRONG_YES),
        ("that's right", S.STRONG_YES),
        ("spot on", S.STRONG_YES),
        # strong denial
        ("definitely not", S.STRONG_NO),
        ("No way", S.STRONG_NO),
        ("no", S.STRONG_NO),
        ("absolutely not!", S.STRONG_NO),
        # hedges read as soft rejections, never flat ones
        ("not really", S.LEAN_NO),
        ("Not really…", S.LEAN_NO),
        ("probably not", S.LEAN_NO),
        ("nope", S.LEAN_NO),
        # soft affirmation
        ("sort of", S.LEAN_YES),
        ("kinda", S.LEAN_YES),
        ("maybe?", S.LEAN_YES),
        ("i guess", S.LEAN_YES),
        # uncertain
        ("hmm", S.UNCLEAR),
        ("not sure", S.UNCLEAR),
        ("i don't know", S.UNCLEAR),
        # conservative defaults
        ("purple elephant", S.UNCLEAR),
        ("", S.UNCLEAR),
        ("   ", S.UNCLEAR),
        (None, S.UNCLEAR),
        # tier precedence: hedges beat fillers; negated forms beat bare ones;
        # mixed signals resolve to the conservative hedge
        ("hmm, not really", S.LEAN_NO),
        ("yes, but not really", S.LEAN_NO),
    ],
)
def test_parse_map(text, expected):
    assert parse_agreement(text).strength is expected


def test_matched_phrase_is_reported():
    signal = parse_agreement("Hmm… not really, I think")
    assert signal.strength is S.LEAN_NO
    assert signal.matched_phrase == "not really"


def test_deterministic():
    assert parse_agreement("sort of") == parse_agreement("Sort of!")


def test_typography_and_punctuation_tolerated():
    assert parse_agreement("Thats right — exactly!").strength is S.STRONG_YES
    assert parse_agreement("that’s right").strength is S.STRONG_YES


def test_signal_is_structure_only():
    """The extractor produces labels, never probabilities or hypotheses."""
    signal = parse_agreement("absolutely")
    assert signal.strength is S.STRONG_YES
    assert not hasattr(signal, "probability")
    assert not hasattr(signal, "hypothesis_id")
