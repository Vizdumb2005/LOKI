"""LOKI-Language: dialogue rendering (plan §4.7).

Phase 1 implementation: deterministic template renderer with the Loki persona.
Boundary rules (AGENTS.md / plan §4.7):
- receives *structured state only* (labels, confidence, turn counts);
- never estimates truth and never changes a prediction;
- phrasing confidence is driven by the posterior confidence bands below —
  the theatrical surface must not convert weak evidence into certainty
  (the Phase 1 stand-in for the full LOKI-Calibrator, plan §4.8).
Phase 5 replaces the templates with the in-house dialogue model behind the
same interface.
"""

from __future__ import annotations

import hashlib
from collections.abc import Sequence

ASK_OPENERS = (
    "The threads of fate pull tight. {question}",
    "Your mind flickers like candlelight — I can almost see it. {question}",
    "The ravens bring me whispers, but I prefer to ask. {question}",
    "Steady now, and answer true. I will know if it wavers. {question}",
    "Interesting… the mists part a little. {question}",
    "Hmm. The shape of it grows clearer. {question}",
)

INTRO_LINES = (
    "Very well. Fix the {title}'s secret in your mind and hold it there. "
    "Answer truly — trickery is my domain, not yours.",
    "So it begins. Picture it clearly and keep it fixed. I will do the rest.",
    "A worthy opponent? We shall see. Hold the {title} in your thoughts and do not let go.",
)

# Confidence bands: phrasing must reflect the actual posterior (plan §4.8).
REVEAL_HIGH = (  # p >= 0.90
    "It was the {label}. It was always the {label}.",
    "The {label}. Don't look so surprised — your mind broadcast it the whole time.",
)
REVEAL_MEASURED = (  # 0.60 <= p < 0.90
    "Then let me speak it plainly: the {label}. I would wager a great deal on that.",
    "I commit — the {label}. The signs were hard to argue with.",
)
REVEAL_HEDGED = (  # 0.40 <= p < 0.60
    "The mists are thick tonight, but I sense… the {label}. Am I close?",
    "My sight wavers. Still, I trust my instinct: the {label}.",
)
REVEAL_FORCED = (  # p < 0.40 — openly uncertain
    "The threads are tangled and time is spent. If forced to choose: the {label}. "
    "The fates owe me one.",
    "Enough questions. I will say the {label} — and if I am wrong, I was never here.",
)

OUTCOME_CORRECT = (
    "{turns} questions. Your mind was an open book — I merely read it.",
    "As foretold. {turns} questions was all it took.",
)
OUTCOME_WRONG = (
    "Impossible… enjoy this moment. It will not repeat.",
    "A flaw in the threads, not in the weaver. Rematch?",
)


class LanguageRenderer:
    """Deterministic, seeded line selection — same session always sees the same lines."""

    def __init__(self, seed: str = "loki") -> None:
        self._seed = seed

    def _pick(self, options: Sequence[str], *salt: str) -> str:
        digest = hashlib.blake2b(":".join((self._seed, *salt)).encode(), digest_size=8).digest()
        return options[int.from_bytes(digest, "big") % len(options)]

    def intro(self, effect_title: str, session_id: str) -> str:
        return self._pick(INTRO_LINES, "intro", session_id).format(title=effect_title)

    def ask(self, question_text: str, session_id: str, turn: int) -> str:
        template = self._pick(ASK_OPENERS, "ask", session_id, str(turn))
        return template.format(question=question_text)

    def reveal(self, label: str, confidence: float, session_id: str) -> str:
        if confidence >= 0.90:
            band = REVEAL_HIGH
        elif confidence >= 0.60:
            band = REVEAL_MEASURED
        elif confidence >= 0.40:
            band = REVEAL_HEDGED
        else:
            band = REVEAL_FORCED
        return self._pick(band, "reveal", session_id).format(label=label)

    def outcome(self, correct: bool, turns: int, session_id: str) -> str:
        options = OUTCOME_CORRECT if correct else OUTCOME_WRONG
        return self._pick(options, "outcome", session_id).format(turns=turns)
