"""Synthetic participant profiles (ROADMAP Phase 6; idea.md §8).

The simulator precondition for RL is a POPULATION, not a single calibration:
heterogeneous profiles with different noise, latency, suggestibility,
evasiveness, and adversarial behavior, so a learned policy must generalize
rather than overfit one participant model.

A profile is a plain parameter bundle for ``TruthfulNoisyParticipant`` —
nothing here invents behavior the participant model cannot express.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Profile:
    """One synthetic participant archetype."""

    name: str
    description: str
    reliability: float | None = None  # answer-noise override (None = per-question YAML)
    gaze_prob: float = 0.0
    gaze_accuracy: float = 0.8
    force_susceptibility: float = 0.0
    # latency behavior: fast answers when sure, slow when guessing
    p_fast_truthful: float = 0.85
    p_fast_guess: float = 0.25
    # covert replies: probability a sampled reaction is softened one step
    # toward uncertainty (the "evasive" failure mode, digital-translation.md)
    fishing_evasiveness: float = 0.0
    tags: tuple[str, ...] = field(default_factory=tuple)


PROFILES: dict[str, Profile] = {
    "balanced": Profile(
        name="balanced",
        description="the calibration defaults across every channel",
        gaze_prob=0.5,
    ),
    "impulsive": Profile(
        name="impulsive",
        description="answers fast and noisily, rarely looks anywhere useful",
        reliability=0.75,
        gaze_prob=0.2,
        gaze_accuracy=0.6,
        p_fast_truthful=0.95,
        p_fast_guess=0.7,
        tags=("noisy", "fast"),
    ),
    "cautious": Profile(
        name="cautious",
        description="deliberate and precise; slow even when sure",
        reliability=0.98,
        gaze_prob=0.4,
        gaze_accuracy=0.9,
        p_fast_truthful=0.5,
        p_fast_guess=0.1,
        tags=("slow", "precise"),
    ),
    "suggestible": Profile(
        name="suggestible",
        description="follows the obvious option and affirms reads",
        reliability=0.85,
        gaze_prob=0.5,
        force_susceptibility=0.5,
        tags=("suggestible",),
    ),
    "evasive": Profile(
        name="evasive",
        description="hedges, stalls, and softens every reaction",
        reliability=0.88,
        gaze_prob=0.3,
        p_fast_truthful=0.4,
        p_fast_guess=0.1,
        fishing_evasiveness=0.45,
        tags=("evasive", "slow"),
    ),
    "adversarial": Profile(
        name="adversarial",
        description="actively misleading answers and decoy gaze",
        reliability=0.15,
        gaze_prob=0.5,
        gaze_accuracy=0.3,
        tags=("adversarial",),
    ),
}


def sample_profile(rng: random.Random) -> Profile:
    """A profile from the uniform mixture — the training/evaluation
    population (docs/rl-policy.md §3)."""
    return rng.choice(list(PROFILES.values()))
