"""LOKI-Brain: the strategic decision layer (mission Phase 3).

The Brain decides WHAT to do next; it never touches the posterior. Hard
constraints in ``contract.validate`` apply outside any learned decision-making,
so a future learned policy inherits the same guardrails as the baseline.
"""
