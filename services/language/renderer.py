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
from typing import Any

from services.language.equivocation import REFRAME_DEFIED, REFRAME_MISS, REFRAME_UNCLEAR
from services.language.fishing import FISHING_OPENERS
from services.language.reveal_planner import (
    CATEGORY_BEATS,
    DEDUCTION_BEATS,
    FIRST_ATTRIBUTE_BEATS,
    HESITATION_BEATS,
    NEXT_ATTRIBUTE_BEATS,
    wants_hesitation,
)

ASK_OPENERS = (
    "The threads of fate pull tight. {question}",
    "Your mind flickers like candlelight — I can almost see it. {question}",
    "The ravens bring me whispers, but I prefer to ask. {question}",
    "Steady now, and answer true. I will know if it wavers. {question}",
    "Interesting… the mists part a little. {question}",
    "Hmm. The shape of it grows clearer. {question}",
)

COVERT_FISHING_OPENERS = (
    "I get a strong visual impression right now… {assertion}",
    "Do not speak yet — just focus. I sense that {assertion}",
    "There's an unmistakable resonance here… {assertion}",
    "A impression is taking form in my mind… {assertion}",
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

    def covert_fish(self, assertion_text: str, session_id: str, turn: int) -> str:
        template = self._pick(COVERT_FISHING_OPENERS, "covert_fish", session_id, str(turn))
        return template.format(assertion=assertion_text)

    def fishing(
        self,
        asserted_label: str,
        session_id: str,
        turn: int,
        openers: Sequence[str] | None = None,
    ) -> str:
        """Render a covert fishing assertion of one option (ROADMAP Phase 2).

        ``openers`` overrides the default bank (per-question YAML
        ``fishing_openers``). Deterministic like every other line: the same
        session and turn always see the same assertion.
        """
        bank = tuple(openers) if openers else FISHING_OPENERS
        return self._pick(bank, "fish", session_id, str(turn)).format(label=asserted_label)

    def stage_reveal(
        self,
        stages: Sequence[Any],
        winner_label: str,
        confidence: float,
        session_id: str,
    ) -> list[tuple[str, str]]:
        """Render the beats that precede the banded identity line (ROADMAP Phase 3).

        ``stages`` are the policy layer's structured RevealStage objects
        (duck-typed: kind/attr/label). Returns (kind, text) pairs; the
        identity line itself stays in :meth:`reveal` — staging adds beats,
        never certainty. Hesitation lands only inside the calibrated doubt
        window (docs/reveal-planning.md §3).
        """
        beats: list[tuple[str, str]] = []
        attribute_count = 0
        for index, stage in enumerate(stages):
            if stage.kind == "deduction":
                template = self._pick(DEDUCTION_BEATS, "stage", session_id, str(index))
                beats.append(("deduction", template.format(first=winner_label, second=stage.label)))
            elif stage.kind == "category":
                template = self._pick(CATEGORY_BEATS, "stage", session_id, str(index))
                beats.append(("category", template.format(label=stage.label)))
            else:
                bank = FIRST_ATTRIBUTE_BEATS if attribute_count == 0 else NEXT_ATTRIBUTE_BEATS
                template = self._pick(bank, "stage", session_id, str(index))
                beats.append(("attribute", template.format(label=stage.label)))
                attribute_count += 1
        if wants_hesitation(confidence):
            beats.append(("hesitation", self._pick(HESITATION_BEATS, "hesitate", session_id)))
        return beats

    def reframe(self, kind: str, missed_label: str, session_id: str, turn: int) -> str:
        """The equivocation line that opens the turn after a missed or unclear
        read, or a defied emphasis (docs/reveal-planning.md §4,
        docs/choice-architecture.md §4). Renders engine-recorded state only."""
        bank = {
            "missed": REFRAME_MISS,
            "unclear": REFRAME_UNCLEAR,
            "defied": REFRAME_DEFIED,
        }[kind]
        return self._pick(bank, "reframe", session_id, str(turn)).format(label=missed_label)

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
