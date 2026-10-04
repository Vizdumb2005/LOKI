"""Tests for generative passive signal inference and latent trait likelihood vector computation."""

from pathlib import Path

from services.effects.loader import load_effects
from services.fusion.latent_traits import (
    LatenterTraitInference,
    infer_latent_trait,
    trait_likelihood_vector,
)


def test_infer_latent_trait_fast_intuitive():
    inf = infer_latent_trait(latency_ms=1200.0)
    assert inf is not None
    assert inf.trait_id == "fast_intuitive"
    assert inf.confidence <= 0.35
    assert inf.evidence["latency_ms"] == 1200.0


def test_infer_latent_trait_deliberate_analytical():
    inf = infer_latent_trait(latency_ms=8500.0)
    assert inf is not None
    assert inf.trait_id == "deliberate_analytical"
    assert inf.confidence <= 0.35

    inf_typing = infer_latent_trait(typing_rhythm={"first_key_ms": 4000.0})
    assert inf_typing is not None
    assert inf_typing.trait_id == "deliberate_analytical"


def test_infer_latent_trait_gaze_dwell():
    inf = infer_latent_trait(gaze_dwell_ms=950.0)
    assert inf is not None
    assert inf.trait_id == "focused_visual"


def test_trait_likelihood_vector_soft_and_positive():
    effects = load_effects(Path("configs/effects"))
    effect = effects["animal_guess"]

    inference = LatenterTraitInference(
        trait_id="fast_intuitive",
        confidence=0.25,
        description="Fast intuitive response",
    )

    likelihoods = trait_likelihood_vector(effect, inference)
    assert len(likelihoods) == len(effect.hypotheses)
    # Every likelihood must be strictly positive and bounded
    for _hid, p in likelihoods.items():
        assert p > 0.0
        assert 0.65 <= p <= 1.35
