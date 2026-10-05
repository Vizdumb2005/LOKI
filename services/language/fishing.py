"""Covert fishing assertion templates (ROADMAP Phase 2; digital-translation.md §1).

Renders an entropy-reducing probe as an intuitive statement: instead of the
question "Is your card red, or black?" the participant reads an assertion of
one option — "There's a pull toward Red. Don't overthink it — does that
land?" — and replies in natural language.

Rules:
- an assertion names exactly ONE option (the one the Method Selection Policy
  chose) and never names the question's other options — no dimension leakage
  beyond the assertion itself. Enforced for YAML ``fishing_openers`` by a
  Question validator and for this default bank by the exhaustive renderer
  sweep test (tests/test_fishing.py);
- templates carry a ``{label}`` placeholder and nothing else to interpolate;
- the bank is shared across effects so every registered effect can fish
  without per-effect authoring; per-question ``fishing_openers`` overrides
  take precedence (docs/spec/effects-schema.md v1.2).
"""

from __future__ import annotations

FISHING_OPENERS: tuple[str, ...] = (
    "The threads hum around {label} — I keep circling back to it. That feels right, doesn't it?",
    "Wait. Something settles on {label}. Tell me honestly — am I close?",
    "I get a strong impression here, and it points at {label}. Isn't it?",
    "There's a pull toward {label}. Don't overthink it — does that land?",
    "The mists thin for a moment and show me {label}. Am I reading you true?",
)
