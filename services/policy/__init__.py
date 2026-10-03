"""LOKI-Policy: the active decision engine (plan §4.6).

Phase 1 ships method 1 (hand-designed information-gain policy) as the measurable
baseline. Contextual bandits / constrained RL (methods 2–4) must beat this
policy offline in the Phase 4 harness before replacing it.
"""

from __future__ import annotations
