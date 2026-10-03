"""Magic Factor Evaluation Experiment Harness.

Evaluates AI Mentalist performance using the Magic Factor framework (docs/magic-factor.md).
Compares baseline explicit questioning against mentalist strategies (covert observation,
gaze/passive signal fusion, and information mystery gap optimization).

Usage:
    python -m experiments.run_magic_factor_eval --sessions 200 --seed 42
"""

from __future__ import annotations

import argparse
import json
import math
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


def evaluate_magic_factor(
    effect,
    sessions: int,
    reliability: float | None,
    rng: random.Random,
    gaze_prob: float = 0.0,
    covert_ratio: float = 0.0,  # proportion of questions styled as covert fishing
):
    renderer = LanguageRenderer()
    correct = 0
    turns: list[int] = []
    actual_entropy_reduced: list[float] = []
    visible_bits_list: list[float] = []
    mystery_gaps: list[float] = []
    magic_factors: list[float] = []
    forced = 0

    for _ in range(sessions):
        truth = rng.choice(list(effect.hypotheses))
        participant = TruthfulNoisyParticipant(effect, truth, rng, reliability, gaze_prob=gaze_prob)
        session = EffectSession(effect, renderer)
        initial_entropy = session.initial_entropy

        visible_bits_session = 0.0

        while session.phase is Phase.ACTIVE:
            q = session.current_question
            assert q is not None

            # Calculate visible bits for this question.
            # If covert_ratio applies, questions are framed covertly.
            num_answers = len(q.answers)
            question_visible_bits = math.log2(num_answers) if num_answers > 0 else 1.0

            # Apply covert reduction factor if applicable
            is_covert = rng.random() < covert_ratio
            if is_covert:
                # covert fishing statement carries low apparent interrogation
                question_visible_bits *= 0.25

            visible_bits_session += question_visible_bits

            # Check for non-verbal gaze observation
            look = participant.look(q)
            if look is not None and "gaze_dwell" in effect.observations:
                session.observe(q.id, look[0], "gaze_dwell", dwell_ms=look[1])

            # Submit answer
            ans_id = participant.answer(q)
            session.answer(ans_id)

        assert session.prediction is not None
        is_correct = session.prediction.hypothesis_id == truth
        if is_correct:
            correct += 1

        final_entropy = session.tracker.entropy()
        delta_h_actual = max(0.0, initial_entropy - final_entropy)
        mystery_gap = delta_h_actual - visible_bits_session
        magic_factor = (1.0 if is_correct else 0.0) / (1.0 + visible_bits_session)

        turns.append(session.turn)
        actual_entropy_reduced.append(delta_h_actual)
        visible_bits_list.append(visible_bits_session)
        mystery_gaps.append(mystery_gap)
        magic_factors.append(magic_factor)

        if session.committed_because in (
            CommitReason.MAX_TURNS,
            CommitReason.NO_INFORMATIVE_QUESTION,
        ):
            forced += 1

    accuracy = correct / sessions
    avg_visible_bits = statistics.mean(visible_bits_list)
    magic_factor_score = accuracy / (1.0 + avg_visible_bits)

    return {
        "effect_id": effect.id,
        "sessions": sessions,
        "gaze_prob": gaze_prob,
        "covert_ratio": covert_ratio,
        "top1_accuracy": round(accuracy, 4),
        "avg_turns": round(statistics.mean(turns), 2),
        "avg_actual_entropy_reduced_bits": round(statistics.mean(actual_entropy_reduced), 4),
        "avg_visible_bits_used": round(avg_visible_bits, 4),
        "avg_information_mystery_gap_bits": round(statistics.mean(mystery_gaps), 4),
        "magic_factor_score": round(magic_factor_score, 4),
        "forced_commit_rate": round(forced / sessions, 4),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="LOKI Magic Factor Evaluation")
    parser.add_argument("--effect", action="append", help="effect id (default: all)")
    parser.add_argument("--sessions", type=int, default=200)
    parser.add_argument("--reliability", type=float, default=None)
    parser.add_argument("--gaze-prob", type=float, default=0.5)
    parser.add_argument(
        "--covert-ratio",
        type=float,
        default=0.3,
        help="ratio of questions framed as covert cold reading / fishing",
    )
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--json", type=Path, default=None)
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
            evaluate_magic_factor(
                registry[effect_id],
                args.sessions,
                args.reliability,
                rng,
                gaze_prob=args.gaze_prob,
                covert_ratio=args.covert_ratio,
            )
        )

    print(
        f"LOKI Magic Factor Evaluation — sessions={args.sessions}, seed={args.seed}, "
        f"gaze_prob={args.gaze_prob}, covert_ratio={args.covert_ratio}"
    )
    header = (
        f"{'effect':<20}{'accuracy':>9}{'turns':>8}{'ΔH_actual':>11}"
        f"{'Vis_bits':>10}{'MysteryGap':>12}{'MagicFactor':>13}"
    )
    print(header)
    print("-" * len(header))
    for r in results:
        print(
            f"{r['effect_id']:<20}{r['top1_accuracy']:>9.3f}"
            f"{r['avg_turns']:>8.2f}{r['avg_actual_entropy_reduced_bits']:>11.3f}"
            f"{r['avg_visible_bits_used']:>10.3f}{r['avg_information_mystery_gap_bits']:>12.3f}"
            f"{r['magic_factor_score']:>13.4f}"
        )

    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(results, indent=2), encoding="utf-8")
        print(f"\nresults written to {args.json}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
