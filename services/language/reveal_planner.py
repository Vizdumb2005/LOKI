"""Reveal staging banks (ROADMAP Phase 3) — the beats BEFORE the identity line.

`services/policy/reveal_planner.py` chooses the reveal path and its structured
stages; this module and :meth:`LanguageRenderer.stage_reveal` render them.
Rules (docs/reveal-planning.md):

- the identity line is ALWAYS the existing confidence-banded reveal — staging
  adds beats, never certainty;
- hesitation exists only inside the calibrated doubt window (0.60 ≤ p < 0.85,
  digital-translation.md §2.9) and only ever adds doubt;
- deterministic seeded selection, like every LOKI-Language line.
"""

from __future__ import annotations

# Bands for the hesitation beat (language-owned: it is presentation logic).
HESITATION_LOW = 0.60
HESITATION_HIGH = 0.85

FIRST_ATTRIBUTE_BEATS = (
    "Let me build this slowly. {label} — that much I will stake.",
    "The first thread shows itself: {label}.",
    "Before the name, the shape: {label}.",
)

NEXT_ATTRIBUTE_BEATS = (
    "Closer now — {label}.",
    "And with it, {label}. Feel it narrowing?",
    "One layer deeper: {label}.",
)

CATEGORY_BEATS = (
    "Everything here beats in the same family: {label}.",
    "One family holds them both — {label}.",
    "Strip away the details and one kind remains: {label}.",
)

DEDUCTION_BEATS = (
    "Two names keep surfacing — {first}, or {second}. Give me a breath.",
    "It comes down to two, doesn't it. {first}… or {second}.",
    "I see {first} and {second} crossed by the same thread. One of them is yours.",
)

HESITATION_BEATS = (
    "Wait. No — it's clearer now.",
    "Hold on… the mists shift. There.",
    "Hmm — not so fast. Yes. I have it.",
)


def wants_hesitation(confidence: float) -> bool:
    """One hesitation beat lands inside the calibrated doubt window."""
    return HESITATION_LOW <= confidence < HESITATION_HIGH
