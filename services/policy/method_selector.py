"""Method Selection Policy for AI Mentalist Controller.

Selects the optimal performance method class (Direct Inference, Covert Fishing,
Progressive Narrowing, Choice Forcing) based on current hypothesis distribution,
entropy, confidence, turn count, and available channels.
"""

from __future__ import annotations

import math
from enum import Enum


class MentalistMethod(str, Enum):
    DIRECT_INFERENCE = "direct_inference"
    COVERT_FISHING = "covert_fishing"
    PROGRESSIVE_NARROWING = "progressive_narrowing"
    CHOICE_FORCING = "choice_forcing"


def select_method(
    entropy_bits: float,
    top_probability: float,
    hypothesis_count: int,
    turn: int,
    has_gaze_observation: bool = False,
    forcing_eligible: bool = False,
) -> MentalistMethod:
    """Selects the mentalist performance method for the current session step."""
    max_entropy = math.log2(hypothesis_count) if hypothesis_count > 1 else 1.0

    # High confidence or strong passive observation -> Commit via Direct Inference
    if top_probability >= 0.70 or (top_probability >= 0.55 and has_gaze_observation):
        return MentalistMethod.DIRECT_INFERENCE

    # Early in session with eligible choice architecture -> Choice Forcing
    if turn == 1 and forcing_eligible:
        return MentalistMethod.CHOICE_FORCING

    # Moderate uncertainty -> Covert Fishing / Cold Reading loop
    if entropy_bits > 0.4 * max_entropy:
        return MentalistMethod.COVERT_FISHING

    # Low uncertainty -> Progressive Narrowing
    return MentalistMethod.PROGRESSIVE_NARROWING
