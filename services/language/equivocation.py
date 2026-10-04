"""Equivocation reframes (ROADMAP Phase 3) — the magician's graceful recovery.

After a covert read misses ("Not really") or lands unclear, the NEXT turn
opens with one reframe line: the miss is folded into the performance instead
of visibly backtracking (mentalism-techniques.md §2.1; architecture.md §4).

Boundary: the engine records WHAT happened (a miss, an unclear reply, and the
asserted option's label); these templates render it. They must not claim more
or less narrowing than the Bayesian update actually performed — no
probabilities, no hypothesis names beyond the missed label itself.
"""

from __future__ import annotations

REFRAME_MISS = (
    "Not {label}, then. Curious — a near-miss narrows the field more than you'd think.",
    "No matter. The threads re-weave: what remains is smaller than before.",
    "Ah — not {label}. That silence tells me plenty.",
)

REFRAME_UNCLEAR = (
    "The mists swallowed that one — I'll take a different angle.",
    "You gave me nothing there, which is itself a kind of answer.",
    "A ripple, not a reading. Let me approach from another side.",
)

# ROADMAP Phase 4: the participant defied the choice-architecture emphasis.
# The defiance is folded into the performance — never shown as an error, and
# never rewarded with a changed prediction (the update already spoke).
REFRAME_DEFIED = (
    "You reached past the obvious — good. The answer lives off the beaten path.",
    "Defiant. I like that; agreement teaches me nothing.",
    "So the obvious one was a lure, not a reading. Noted.",
)
