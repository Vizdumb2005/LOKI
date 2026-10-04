"""LOKI-Fusion: Generative Passive Signal Inference (Directive §5G, §13 Q8/Q9).

Infers latent behavioral traits (e.g., intuitive vs deliberate processing) from
passive telemetry (response latency, typing rhythm, gaze dwell) and generates
bounded, soft Bayesian evidence updates over target hypotheses.

Rules:
- Positive, falsifiable inference with stated reliability (bounded confidence <= 0.35);
- Soft Bayesian updates only: never zeroes out hypotheses;
- Pure functions: telemetry in, structured LatentTraitInference / likelihood vector out;
- Fully auditable: evidence triggers are preserved in the inference record.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from services.effects.models import EffectDef


@dataclass(frozen=True)
class LatenterTraitInference:
    trait_id: str  # "fast_intuitive" | "deliberate_analytical" | "hesitant_uncertain"
    confidence: float  # In (0.0, 0.35] — bounded weak evidence
    evidence: dict[str, Any] = field(default_factory=dict)
    description: str = ""


def infer_latent_trait(
    latency_ms: float | None = None,
    typing_rhythm: dict[str, float] | None = None,
    gaze_dwell_ms: float | None = None,
) -> LatenterTraitInference | None:
    """Infer a latent behavioral trait from passive telemetry signals.

    Returns None if telemetry is insufficient or ambiguous.
    """
    if latency_ms is None and typing_rhythm is None and gaze_dwell_ms is None:
        return None

    # Fast response latency (< 1800 ms) indicates fast intuitive processing
    if latency_ms is not None and latency_ms < 1800.0:
        return LatenterTraitInference(
            trait_id="fast_intuitive",
            confidence=0.25,
            evidence={"latency_ms": latency_ms},
            description="Rapid decision speed indicating intuitive / high-prior selection.",
        )

    # Slow latency (> 7000 ms) or slow typing start (> 3500 ms) indicates deliberate analysis
    first_key = typing_rhythm.get("first_key_ms") if typing_rhythm else None
    if (latency_ms is not None and latency_ms > 7000.0) or (
        first_key is not None and first_key > 3500.0
    ):
        return LatenterTraitInference(
            trait_id="deliberate_analytical",
            confidence=0.20,
            evidence={
                "latency_ms": latency_ms,
                "first_key_ms": first_key,
            },
            description="Extended latency or typing pause indicating deliberate / complex retrieval.",  # noqa: E501
        )

    # Sustained gaze dwell (> 800 ms) indicates active visual focus
    if gaze_dwell_ms is not None and gaze_dwell_ms > 800.0:
        return LatenterTraitInference(
            trait_id="focused_visual",
            confidence=0.30,
            evidence={"gaze_dwell_ms": gaze_dwell_ms},
            description="Sustained gaze dwell duration indicating strong visual focus.",
        )

    return None


def trait_likelihood_vector(
    effect: EffectDef,
    inference: LatenterTraitInference,
) -> dict[str, float]:
    """Compute soft Bayesian likelihoods P(latent_trait | h) across the hypothesis space.

    Hypotheses whose attributes align with the latent trait receive a minor likelihood
    boost proportional to inference.confidence, keeping all likelihoods strictly positive.
    """
    likelihoods: dict[str, float] = {}
    conf = min(0.35, max(0.05, inference.confidence))

    for hid, attrs in effect.hypotheses.items():
        # Trait alignment heuristics based on hypothesis metadata
        aligned = False
        if inference.trait_id == "fast_intuitive":
            # Fast intuitive choices favor common/archetypal/popular targets
            if attrs.get("common", False) or attrs.get("popular", False) or attrs.get("big", False):
                aligned = True
        elif inference.trait_id == "deliberate_analytical":
            # Deliberate analytical choices favor rare/complex targets
            if attrs.get("rare", False) or attrs.get("complex", False) or attrs.get("water", False):
                aligned = True
        elif inference.trait_id == "focused_visual":
            # Visual focus favors visually salient / color / symbol hypotheses
            if "color" in attrs or "symbol" in attrs or "suit" in attrs:
                aligned = True

        if aligned:
            likelihoods[hid] = 1.0 + conf
        else:
            likelihoods[hid] = 1.0 - conf

    return likelihoods
