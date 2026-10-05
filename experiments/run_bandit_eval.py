"""Contextual-bandit dialogue policy: training + evaluation (ROADMAP Phase 6,
docs/rl-policy.md).

Trains a tabular ε-greedy bandit over turn-level strategies {direct, covert,
forced} against synthetic participant profiles (simulator/profiles.py), with a
Magic-Factor-aligned reward:

    r = ΔH_actual(turn) − λ · visible_bits(turn)   (λ = 0.25)
    terminal (committing turn): +0.5 correct / −0.5 wrong

then evaluates greedy-bandit vs the hand-designed method policy across the
profile mixture with the full magic-factor protocol. The comparison answers
idea.md §13 Q6 honestly in whichever direction it falls.

Usage:
    python -m experiments.run_bandit_eval --episodes 600 --eval-sessions 120 --seed 42
"""

from __future__ import annotations

import argparse
import json
import math
import random
import statistics
import sys
from collections import Counter
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
if hasattr(sys.stderr, "reconfigure"):
    try:
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

from services.effects.engine import EffectSession, Phase
from services.effects.loader import load_effects
from services.language.renderer import LanguageRenderer
from simulator.bandit import BanditTurnSelector, TabularBandit, serialize
from simulator.participant import TruthfulNoisyParticipant
from simulator.profiles import Profile, sample_profile

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_EFFECTS_DIR = REPO_ROOT / "configs" / "effects"

LAMBDA_VISIBLE = 0.25  # reward weight of perceived interrogation (docs/rl-policy.md §2)
TERMINAL_CORRECT = 0.5
TERMINAL_WRONG = -0.5


def _visible_bits(mode: str, option_count: int, kappa: float = 0.25) -> float:
    if mode == "covert":
        return kappa * math.log2(3)
    return math.log2(option_count) if option_count > 1 else 0.0


def play_episode(
    effect,
    renderer: LanguageRenderer,
    rng: random.Random,
    profile: Profile,
    agent: TabularBandit | None = None,
) -> dict:
    """One simulated séance; updates the agent in place when given.

    Returns the session's objective metrics plus the action distribution.
    """
    truth = rng.choice(list(effect.hypotheses))
    participant = TruthfulNoisyParticipant(
        effect,
        truth,
        rng,
        reliability_override=profile.reliability,
        gaze_prob=profile.gaze_prob,
        gaze_accuracy=profile.gaze_accuracy,
        force_susceptibility=profile.force_susceptibility,
        p_fast_truthful=profile.p_fast_truthful,
        p_fast_guess=profile.p_fast_guess,
        fishing_evasiveness=profile.fishing_evasiveness,
    )
    selector = BanditTurnSelector(agent, explore=True) if agent is not None else None
    session = EffectSession(effect, renderer, selector=selector)
    actions: Counter[str] = Counter()
    decisions: list[tuple[tuple[int, int], str, float]] = []

    while session.phase is Phase.ACTIVE:
        question = session.current_question
        if session.current_mode == "covert":
            strength, latency = participant.respond_to_fishing(
                session.current_question, session.asserted_answer_id
            )
            session.respond_agreement(strength, latency_ms=latency)
            mode, option_count = "covert", 3
        else:
            # gaze applies to direct turns only
            look = participant.look(question)
            if look is not None and "gaze_dwell" in effect.observations:
                session.observe(question.id, look[0], "gaze_dwell", dwell_ms=look[1])
            salient = session.current_force_target
            answer_id, latency_ms = participant.answer_with_latency(question, salient)
            session.answer(answer_id, latency_ms=latency_ms)
            mode, option_count = "direct", len(question.answers)

        updated = next(e for e in reversed(session.history) if e.type.value == "hypothesis.updated")
        delta_h = max(0.0, updated.payload["entropy_before"] - updated.payload["entropy_after"])
        reward = delta_h - LAMBDA_VISIBLE * _visible_bits(mode, option_count)
        if selector is not None and selector.last_decision is not None:
            cell, action = selector.last_decision
            actions[action] += 1
            decisions.append((cell, action, reward))
            agent.update(cell, action, reward)

    if agent is not None and decisions and session.prediction is not None:
        # terminal bonus on the committing turn (docs/rl-policy.md §2)
        cell, action, reward = decisions[-1]
        bonus = TERMINAL_CORRECT if session.prediction.hypothesis_id == truth else TERMINAL_WRONG
        agent.update(cell, action, reward + bonus)

    return {
        "correct": session.prediction is not None and session.prediction.hypothesis_id == truth,
        "turns": session.turn,
        "forced": session.committed_because is not None
        and session.committed_because.value != "entropy_threshold",
        "actions": dict(actions),
    }


def evaluate_policy(
    effect,
    renderer: LanguageRenderer,
    sessions: int,
    rng: random.Random,
    profile: Profile,
    agent: TabularBandit | None,
) -> dict:
    """Greedy evaluation of a policy (agent=None → the hand-designed heuristic)."""
    correct = 0
    turns: list[int] = []
    forced = 0
    actions: Counter[str] = Counter()
    for _ in range(sessions):
        selector = BanditTurnSelector(agent, explore=False) if agent is not None else None
        truth = rng.choice(list(effect.hypotheses))
        participant = TruthfulNoisyParticipant(
            effect,
            truth,
            rng,
            reliability_override=profile.reliability,
            gaze_prob=profile.gaze_prob,
            gaze_accuracy=profile.gaze_accuracy,
            force_susceptibility=profile.force_susceptibility,
            p_fast_truthful=profile.p_fast_truthful,
            p_fast_guess=profile.p_fast_guess,
            fishing_evasiveness=profile.fishing_evasiveness,
        )
        session = EffectSession(effect, renderer, selector=selector)
        while session.phase is Phase.ACTIVE:
            question = session.current_question
            if session.current_mode == "covert":
                strength, latency = participant.respond_to_fishing(
                    session.current_question, session.asserted_answer_id
                )
                session.respond_agreement(strength, latency_ms=latency)
            else:
                look = participant.look(question)
                if look is not None and "gaze_dwell" in effect.observations:
                    session.observe(question.id, look[0], "gaze_dwell", dwell_ms=look[1])
                salient = session.current_force_target
                answer_id, latency_ms = participant.answer_with_latency(question, salient)
                session.answer(answer_id, latency_ms=latency_ms)
        if session.prediction is not None and session.prediction.hypothesis_id == truth:
            correct += 1
        turns.append(session.turn)
        if session.committed_because is not None and session.committed_because.value != (
            "entropy_threshold"
        ):
            forced += 1
        for event in session.history:
            if event.type.value == "policy.decision":
                reason = event.payload["reason"]
                if reason.startswith("bandit:"):
                    actions[reason.removeprefix("bandit:")] += 1
                else:
                    actions[("covert" if event.payload["mode"] == "covert" else "direct")] += 1
    return {
        "top1_accuracy": round(correct / sessions, 4),
        "avg_turns": round(statistics.mean(turns), 2),
        "forced_commit_rate": round(forced / sessions, 4),
        "action_distribution": {
            action: round(count / max(1, sum(actions.values())), 3)
            for action, count in sorted(actions.items())
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="LOKI contextual-bandit dialogue policy")
    parser.add_argument("--episodes", type=int, default=600)
    parser.add_argument("--eval-sessions", type=int, default=100)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument(
        "--effect",
        action="append",
        help="restrict training/eval to these effect ids (default: all)",
    )
    parser.add_argument("--json", type=Path, default=None)
    args = parser.parse_args()

    registry = load_effects(DEFAULT_EFFECTS_DIR)
    effects = [registry[eid] for eid in args.effect] if args.effect else list(registry.values())
    renderer = LanguageRenderer()

    # -- training --------------------------------------------------------------
    rng = random.Random(args.seed)
    agent = TabularBandit(seed=args.seed)
    train_correct = 0
    for _ in range(args.episodes):
        profile = sample_profile(rng)
        effect = rng.choice(effects)
        result = play_episode(effect, renderer, rng, profile, agent=agent)
        train_correct += 1 if result["correct"] else 0
    print(
        f"trained {args.episodes} episodes over {len(effects)} effects across the "
        f"profile mixture (ε now {agent.epsilon:.3f}); "
        f"training accuracy {train_correct / args.episodes:.3f}"
    )

    # -- evaluation: greedy bandit vs the hand-designed heuristic ---------------
    from simulator.profiles import PROFILES

    eval_rng = random.Random(args.seed + 1)
    eval_results: list[dict] = []
    for profile_name, profile in sorted(PROFILES.items()):
        for effect in effects:
            heuristic = evaluate_policy(
                effect, renderer, args.eval_sessions, eval_rng, profile, None
            )
            bandit = evaluate_policy(effect, renderer, args.eval_sessions, eval_rng, profile, agent)
            eval_results.append(
                {
                    "profile": profile_name,
                    "effect": effect.id,
                    "heuristic": heuristic,
                    "bandit": bandit,
                }
            )

    header = (
        f"{'profile':<13}{'effect':<22}{'acc H':>7}{'acc B':>7}"
        f"{'turns H':>8}{'turns B':>8}{'forced H':>9}{'forced B':>9}"
    )
    print(header)
    print("-" * len(header))
    for row in eval_results:
        print(
            f"{row['profile']:<13}{row['effect']:<22}"
            f"{row['heuristic']['top1_accuracy']:>7.3f}{row['bandit']['top1_accuracy']:>7.3f}"
            f"{row['heuristic']['avg_turns']:>8.2f}{row['bandit']['avg_turns']:>8.2f}"
            f"{row['heuristic']['forced_commit_rate']:>9.3f}{row['bandit']['forced_commit_rate']:>9.3f}"
        )
    # aggregate
    h_acc = statistics.mean(r["heuristic"]["top1_accuracy"] for r in eval_results)
    b_acc = statistics.mean(r["bandit"]["top1_accuracy"] for r in eval_results)
    h_turns = statistics.mean(r["heuristic"]["avg_turns"] for r in eval_results)
    b_turns = statistics.mean(r["bandit"]["avg_turns"] for r in eval_results)
    print(
        f"\naggregate over {len(eval_results)} cells: "
        f"accuracy {h_acc:.3f} (heuristic) vs {b_acc:.3f} (bandit); "
        f"turns {h_turns:.2f} vs {b_turns:.2f}"
    )

    artifact = REPO_ROOT / "experiments" / "outputs" / "bandit_policy.json"
    serialize(agent, artifact)
    print(f"\nbandit policy written to {artifact}")
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(eval_results, indent=2), encoding="utf-8")
        print(f"evaluation written to {args.json}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
