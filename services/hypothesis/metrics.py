"""Probability metrics over finite hypothesis spaces (Phase 1: entropy in bits)."""

from __future__ import annotations

import math
from collections.abc import Mapping


def normalize(weights: Mapping[str, float]) -> dict[str, float]:
    """Return a copy of ``weights`` summing to 1. Negative weights are rejected."""
    negative = [key for key, value in weights.items() if value < 0]
    if negative:
        raise ValueError(f"negative weights are not probabilities: {negative[:5]}")
    total = sum(weights.values())
    if total <= 0:
        raise ValueError(f"weights must sum to a positive value, got {total}")
    return {key: value / total for key, value in weights.items()}


def entropy(pmf: Mapping[str, float]) -> float:
    """Shannon entropy of a pmf, in bits. Zero-probability entries are skipped."""
    return -sum(p * math.log2(p) for p in pmf.values() if p > 0)
