"""Response Signal Extractor.

Parses raw user utterances or option selections into structured agreement signals
("strong_yes", "weak_yes", "neutral", "weak_no", "strong_no") to calibrate soft Bayesian
likelihood updates during covert fishing reading loops.
"""

from __future__ import annotations

import re
from enum import Enum


class AgreementSignal(str, Enum):
    STRONG_YES = "strong_yes"
    WEAK_YES = "weak_yes"
    NEUTRAL = "neutral"
    WEAK_NO = "weak_no"
    STRONG_NO = "strong_no"


STRONG_YES_PATTERNS = [
    r"\b(exact|exactly|absolutely|definitely|spot on|correct|yes|indeed|100%|true)\b",
]

WEAK_YES_PATTERNS = [
    r"\b(kind of|sort of|a bit|maybe|somewhat|partly|in a way|close)\b",
]

WEAK_NO_PATTERNS = [
    r"\b(not really|not quite|hardly|doubtful|unlikely|barely)\b",
]

STRONG_NO_PATTERNS = [
    r"\b(no|never|false|incorrect|wrong|absolutely not|way off)\b",
]


def extract_agreement_signal(
    utterance: str | None, selected_answer_id: str | None = None
) -> AgreementSignal:
    """Extracts an AgreementSignal from raw spoken/typed text or selected answer ID."""
    if selected_answer_id in ("yes", "true", "correct"):
        if utterance:
            text = utterance.lower().strip()
            for pattern in WEAK_YES_PATTERNS:
                if re.search(pattern, text):
                    return AgreementSignal.WEAK_YES
        return AgreementSignal.STRONG_YES

    if selected_answer_id in ("no", "false", "incorrect"):
        if utterance:
            text = utterance.lower().strip()
            for pattern in WEAK_NO_PATTERNS:
                if re.search(pattern, text):
                    return AgreementSignal.WEAK_NO
        return AgreementSignal.STRONG_NO

    if not utterance:
        return AgreementSignal.NEUTRAL

    text = utterance.lower().strip()

    for pattern in STRONG_YES_PATTERNS:
        if re.search(pattern, text):
            return AgreementSignal.STRONG_YES

    for pattern in WEAK_YES_PATTERNS:
        if re.search(pattern, text):
            return AgreementSignal.WEAK_YES

    for pattern in WEAK_NO_PATTERNS:
        if re.search(pattern, text):
            return AgreementSignal.WEAK_NO

    for pattern in STRONG_NO_PATTERNS:
        if re.search(pattern, text):
            return AgreementSignal.STRONG_NO

    return AgreementSignal.NEUTRAL
