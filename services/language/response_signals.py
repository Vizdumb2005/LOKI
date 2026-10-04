"""Response Signal Extractor (ROADMAP Phase 2): participant text -> agreement signal.

Covert fishing statements are answered in natural language ("yes, exactly",
"sort of", "not really") instead of by clicking hypothesis-partition options.
This module normalizes that free text onto a small agreement scale.

Boundary rules (AGENTS.md; docs/architecture.md §3):
- produces STRUCTURE only — a strength label plus the matched phrase;
- performs no truth estimation and touches no probability (the engine owns
  all Bayesian state);
- conservative by default: empty, ambiguous, or unrecognized text maps to
  ``unclear``, never to a decisive strength (docs/covert-fishing.md).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum


class AgreementStrength(str, Enum):
    """How strongly the participant's words affirmed the assertion."""

    STRONG_YES = "strong_yes"
    LEAN_YES = "lean_yes"
    UNCLEAR = "unclear"
    LEAN_NO = "lean_no"
    STRONG_NO = "strong_no"


@dataclass(frozen=True)
class AgreementSignal:
    strength: AgreementStrength
    matched_phrase: str | None


# Multi-word phrase tiers, checked strongest-first. Negated hedges
# ("not really") are tiered above bare tokens so they are never read as
# flat refusals, and mixed-signal text resolves to the first decisive tier.
_PHRASES: tuple[tuple[AgreementStrength, tuple[str, ...]], ...] = (
    (
        AgreementStrength.STRONG_NO,
        ("definitely not", "absolutely not", "certainly not", "no way"),
    ),
    (
        AgreementStrength.STRONG_YES,
        ("exactly", "that's right", "thats right", "spot on", "definitely", "absolutely"),
    ),
    (
        AgreementStrength.LEAN_NO,
        (
            "not really",
            "probably not",
            "don't think so",
            "dont think so",
            "nope",
            "nah",
        ),
    ),
    (
        AgreementStrength.LEAN_YES,
        (
            "sort of",
            "sorta",
            "kind of",
            "kinda",
            "i guess",
            "maybe",
            "perhaps",
            "possibly",
            "could be",
        ),
    ),
    (
        AgreementStrength.UNCLEAR,
        ("not sure", "don't know", "dont know", "dunno", "unsure", "hmm", "hmmm"),
    ),
)

_BARE_YES = ("yes", "yeah", "yep", "yup", "sure")
_BARE_NO = ("no", "nay")

_WORD = re.compile(r"[a-z0-9']+")


def _normalize(text: str) -> str:
    return " ".join(_WORD.findall(text.lower().replace("’", "'")))


def parse_agreement(text: str | None) -> AgreementSignal:
    """Normalize free participant text into an agreement strength.

    Deterministic and keyword-tiered by design: no model, no randomness, and
    an ``unclear`` default for anything the tiers cannot place.
    """
    if text is None:
        return AgreementSignal(AgreementStrength.UNCLEAR, None)
    normalized = _normalize(text)
    if not normalized:
        return AgreementSignal(AgreementStrength.UNCLEAR, None)
    for strength, phrases in _PHRASES:
        for phrase in phrases:
            if re.search(rf"(?:^| ){re.escape(phrase)}(?: |$)", normalized):
                return AgreementSignal(strength, phrase)
    tokens = set(normalized.split())
    if tokens & set(_BARE_YES):
        return AgreementSignal(AgreementStrength.STRONG_YES, "yes")
    if tokens & set(_BARE_NO):
        return AgreementSignal(AgreementStrength.STRONG_NO, "no")
    return AgreementSignal(AgreementStrength.UNCLEAR, None)
