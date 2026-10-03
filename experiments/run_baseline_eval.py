"""Baseline evaluation CLI (docs/spec/evaluation-protocol.md).

Runs N simulated sessions per effect against truthful-noisy participants and
reports the Phase 1 metric set. Seeded and reproducible. Gaze-augmented runs
(``--gaze-prob``) measure what the weak observation channel adds on top of
verbal answers — Phase 2 slice A.

Usage:
    python -m experiments.run_baseline_eval --effect card_prediction --sessions 200
    python -m experiments.run_baseline_eval --sessions 500 --reliability 0.85 --seed 7
    python -m experiments.run_baseline_eval --effect card_prediction --gaze-prob 0.7
"""

from __future__ import annotations

import argparse
import json
import random
import statistics
import sys
from pathlib import Path

from services.effects.engine import CommitReason, EffectSession, Phase
from services.effects.loader import load_effects
from services.language.renderer import LanguageRenderer
from simulator.participant import TruthfulNoisyParticipant

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_EFFECTS_DIR = REPO_ROOT / "configs" / "effects"


def evaluate_effect(
    effect,
    sessions: int,
    reliability: float | None,
    rng: random.Random,
    gaze_prob: float = 0.0,
    gaze_reliability: float | None = None,
):
    if gaze_reliability is not None and "gaze_dwell" in effect.observations:
        channel = effect.observations["gaze_dwell"].model_copy(
            update={"reliability": gaze_reliability}
        )
        effect = effect.model_copy(update={"observations": {"gaze_dwell": channel}})

    renderer = LanguageRenderer()
    correct = 0
    turns: list[int] = []
    entropy_at_commit: list[float] = []
    forced = 0
    observations = 0
    info_gains: list[float] = []

    for _ in range(sessions):
        truth = rng.choice(list(effect.hypotheses))
        participant = TruthfulNoisyParticipant(effect, truth, rng, reliability, gaze_prob=gaze_prob)
        session = EffectSession(effect, renderer)
        while session.phase is Phase.ACTIVE:
            look = participant.look(session.current_question)
            if look is not None:
                session.observe(
                    session.current_question.id, look[0], "gaze_dwell", dwell_ms=look[1]
                )
            session.answer(participant.answer(session.current_question))
        assert session.prediction is not None  # revealed by construction
        if session.prediction.hypothesis_id == truth:
            correct += 1
        turns.append(session.turn)
        entropy_at_commit.append(session.tracker.entropy())
        if session.committed_because in (
            CommitReason.MAX_TURNS,
            CommitReason.NO_INFORMATIVE_QUESTION,
        ):
            forced += 1
        observations += sum(
            1 for event in session.history if event.type.value == "observation.recorded"
        )
        info_gains.extend(
            event.payload["info_gain_bits"]
            for event in session.history
            if event.type.value == "policy.decision"
        )

    return {
        "effect_id": effect.id,
        "sessions": sessions,
        "reliability": reliability if reliability is not None else "per-question YAML",
        "gaze_prob": gaze_prob,
        "top1_accuracy": correct / sessions,
        "avg_turns_to_reveal": round(statistics.mean(turns), 3),
        "avg_entropy_at_commit_bits": round(statistics.mean(entropy_at_commit), 4),
        "forced_commit_rate": forced / sessions,
        "avg_observations_per_session": round(observations / sessions, 2),
        "avg_info_gain_per_question_bits": round(statistics.mean(info_gains), 4),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="LOKI baseline evaluation")
    parser.add_argument("--effect", action="append", help="effect id (repeatable; default: all)")
    parser.add_argument("--sessions", type=int, default=200)
    parser.add_argument(
        "--reliability",
        type=float,
        default=None,
        help="override per-question reliability for a noise sweep",
    )
    parser.add_argument(
        "--gaze-prob",
        type=float,
        default=0.0,
        help="probability the simulated participant lingers on an answer before "
        "giving it (Phase 2 gaze channel; only affects effects that declare it)",
    )
    parser.add_argument(
        "--gaze-reliability",
        type=float,
        default=None,
        help="override the gaze channel reliability for a sweep",
    )
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--json", type=Path, default=None, help="also write results as JSON")
    args = parser.parse_args()

    registry = load_effects(DEFAULT_EFFECTS_DIR)
    effect_ids = args.effect or list(registry)
    unknown = [e for e in effect_ids if e not in registry]
    if unknown:
        parser.error(f"unknown effect(s): {unknown}; available: {list(registry)}")

    rng = random.Random(args.seed)
    results = []
    for effect_id in effect_ids:
        results.append(
            evaluate_effect(
                registry[effect_id],
                args.sessions,
                args.reliability,
                rng,
                gaze_prob=args.gaze_prob,
                gaze_reliability=args.gaze_reliability,
            )
        )

    print(
        f"LOKI baseline evaluation — sessions={args.sessions}, seed={args.seed}, "
        f"gaze_prob={args.gaze_prob}"
    )
    header = (
        f"{'effect':<20}{'accuracy':>9}{'turns':>8}{'H@commit':>10}{'forced':>8}"
        f"{'obs/sess':>9}{'IG/question':>13}"
    )
    print(header)
    print("-" * len(header))
    for r in results:
        print(
            f"{r['effect_id']:<20}{r['top1_accuracy']:>9.3f}"
            f"{r['avg_turns_to_reveal']:>8.2f}{r['avg_entropy_at_commit_bits']:>10.3f}"
            f"{r['forced_commit_rate']:>8.3f}{r['avg_observations_per_session']:>9.2f}"
            f"{r['avg_info_gain_per_question_bits']:>13.3f}"
        )
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(results, indent=2), encoding="utf-8")
        print(f"\nresults written to {args.json}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
