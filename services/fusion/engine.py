"""LOKI-Fusion: passive-signal fusion primitives (ROADMAP Phase 5).

Pure combination functions for the weak behavioral channels — response
latency and typing rhythm — expressed as modulations on the evidence the
engine already has (docs/passive-signals.md). Rules:

- numbers in, numbers out: this module never sees sessions, hypotheses, or
  prose, and never emits text (the LOKI-Fusion boundary — structured output
  only, plan §4.4);
- only the engine applies the results to the tracker; a modulation weakens
  evidence, it never invents or inverts it;
- gaze dwell (Phase 2) already fuses through the observation channels; these
  functions complete the trio (gaze + latency + verbal/transcript).
"""

from __future__ import annotations

from dataclasses import dataclass

from services.language.response_signals import AgreementStrength


@dataclass(frozen=True)
class LatencyChannel:
    """Calibration knobs for response-latency modulation (per-effect YAML)."""

    fast_ms: float = 2000.0  # at or below: full answer reliability
    slow_ms: float = 8000.0  # at or above: reliability scaled to the floor
    floor: float = 0.6  # modulation floor — weakened, never inverted

    def __post_init__(self) -> None:
        if not 0.0 < self.fast_ms < self.slow_ms:
            raise ValueError("latency channel requires 0 < fast_ms < slow_ms")
        if not 0.0 < self.floor <= 1.0:
            raise ValueError("latency channel floor must be in (0, 1]")


# Hesitation thresholds for typing rhythm (docs/passive-signals.md §2).
HESITANT_FIRST_KEY_MS = 3000.0
HESITANT_MEDIAN_INTERVAL_MS = 700.0


def latency_factor(channel: LatencyChannel, latency_ms: float) -> float:
    """The modulation factor for a response latency: 1.0 when fast, falling
    linearly to ``floor`` at slow_ms, constant after."""
    if latency_ms <= channel.fast_ms:
        return 1.0
    if latency_ms >= channel.slow_ms:
        return channel.floor
    span = channel.slow_ms - channel.fast_ms
    progress = (latency_ms - channel.fast_ms) / span
    return 1.0 - (1.0 - channel.floor) * progress


def modulated_reliability(base_reliability: float, factor: float) -> float:
    """Effective answer reliability after latency modulation.

    The result stays a proper reliability: in (0, 1], never above the base —
    a signal can discount an answer, never strengthen it beyond what the
    question already grants.
    """
    if not 0.0 < base_reliability <= 1.0:
        raise ValueError("base reliability must be in (0, 1]")
    return min(base_reliability, base_reliability * factor)


def is_hesitant(first_key_ms: float | None, median_interval_ms: float | None) -> bool:
    """Whether a typing rhythm reads as hesitation (either signal suffices)."""
    if first_key_ms is None and median_interval_ms is None:
        return False
    slow_start = first_key_ms is not None and first_key_ms > HESITANT_FIRST_KEY_MS
    slow_typing = (
        median_interval_ms is not None and median_interval_ms > HESITANT_MEDIAN_INTERVAL_MS
    )
    return bool(slow_start or slow_typing)


_DOWNGRADE = {
    AgreementStrength.STRONG_YES: AgreementStrength.LEAN_YES,
    AgreementStrength.LEAN_YES: AgreementStrength.UNCLEAR,
    AgreementStrength.UNCLEAR: AgreementStrength.UNCLEAR,
    AgreementStrength.LEAN_NO: AgreementStrength.UNCLEAR,
    AgreementStrength.STRONG_NO: AgreementStrength.LEAN_NO,
}


def downgrade_strength(strength: AgreementStrength) -> AgreementStrength:
    """One step toward uncertainty — hesitant words are worth less.

    Symmetric across affirmation and denial; `unclear` is already the floor.
    """
    return _DOWNGRADE[strength]
