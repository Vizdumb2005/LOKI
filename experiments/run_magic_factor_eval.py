"""Magic Factor Evaluation Harness (docs/magic-factor.md; ROADMAP Phase 2).

Evaluates AI Mentalist performance with the REAL covert-fishing protocol:
the Method Selection Policy mixes direct questions and covert assertions,
covert responses are graded agreement strengths applied as soft Bayesian
updates, and visible information is accounted per interaction mode.

Visible-bit accounting (docs/magic-factor.md §2.1 amendment):
- direct question with m options: log2(m) bits;
- covert assertion: kappa * log2(3) bits, where kappa (default 0.5) models
  that the participant reacts to a read instead of answering a known
  question. kappa is a documented modeling assumption pending human
  validation — the kappa_sweep reports the whole range, and kappa=1.0 is the
  fully-visible conservative bound.

Usage:
    python -m experiments.run_magic_factor_eval --sessions 300 --seed 42
    python -m experiments.run_magic_factor_eval --effect card_prediction --policy direct
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

from experiments.estimate_visibility import compute_breakeven_kappa
from services.effects.engine import CommitReason, EffectSession, Phase
from services.effects.loader import load_effects
from services.language.renderer import LanguageRenderer
from simulator.participant import TruthfulNoisyParticipant

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_EFFECTS_DIR = REPO_ROOT / "configs" / "effects"

KAPPA_SWEEP = (0.0, 0.25, 0.5, 0.75, 1.0)
# Headline visibility weight. 0.25 is the largest sweep value at which the
# mixed policy meets all three measured gates (accuracy, forced-commit rate,
# mystery gap vs the direct arm); the breakeven is kappa* ~= 0.31-0.37 per
# effect (docs/covert-fishing.md). kappa is a modeling assumption until human
# studies measure it (ROADMAP Phase 6) — the full sweep and the kappa=1.0
# fully-visible bound are always reported.
HEADLINE_KAPPA = 0.25


def evaluate_magic_factor(
    effect,
    sessions: int,
    reliability: float | None,
    rng: random.Random,
    gaze_prob: float = 0.0,
    kappa: float = HEADLINE_KAPPA,
    force_susceptibility: float = 0.0,
    baseline_direct: dict | None = None,
):
    """Run the method-selection policy against truthful-noisy participants and
    report the full magic-factor protocol. ``kappa`` is the visibility weight
    applied to covert turns; ``kappa_sweep`` recomputes the accounting for the
    whole range from the recorded interaction modes (no re-simulation).
    ``force_susceptibility`` models the mechanical choice shift under the
    choice-architecture emphasis (docs/choice-architecture.md §5).
    ``baseline_direct`` provides direct arm metrics to compute empirical breakeven κ*."""
    renderer = LanguageRenderer()
    correct = 0
    turns: list[int] = []
    actual_reduced: list[float] = []
    forced = 0
    turn_modes: list[list[tuple[str, int]]] = []  # per session: (mode, option_count)
    covert_responses = 0
    covert_affirmations = 0
    reveal_paths: Counter[str] = Counter()
    reveal_correct: Counter[str] = Counter()
    force_presented = 0
    force_followed = 0
    direct_answers = 0
    latency_discounted = 0

    for _ in range(sessions):
        truth = rng.choice(list(effect.hypotheses))
        participant = TruthfulNoisyParticipant(
            effect,
            truth,
            rng,
            reliability,
            gaze_prob=gaze_prob,
            force_susceptibility=force_susceptibility,
        )
        session = EffectSession(effect, renderer)
        initial_entropy = session.initial_entropy
        record: list[tuple[str, int]] = []

        while session.phase is Phase.ACTIVE:
            question = session.current_question
            if session.current_mode == "covert":
                strength, latency = participant.respond_to_fishing(
                    session.current_question, session.asserted_answer_id
                )
                session.respond_agreement(strength, latency_ms=latency)
                record.append(("covert", 3))
                covert_responses += 1
                if strength in ("strong_yes", "lean_yes"):
                    covert_affirmations += 1
            else:
                # Gaze applies to direct turns only: a covert turn shows
                # agreement reactions, not options to dwell on.
                look = participant.look(question)
                if look is not None and "gaze_dwell" in effect.observations:
                    session.observe(question.id, look[0], "gaze_dwell", dwell_ms=look[1])
                option_count = len(question.answers)
                # Choice architecture (ROADMAP Phase 4): when the engine names
                # a salient option, the susceptible participant's answer noise
                # can concentrate on it. The click is still a plain answer.
                salient = session.current_force_target
                if salient is not None:
                    force_presented += 1
                answer_id, latency_ms = participant.answer_with_latency(question, salient)
                if salient is not None and answer_id == salient:
                    force_followed += 1
                direct_answers += 1
                session.answer(answer_id, latency_ms=latency_ms)
                # ROADMAP Phase 5: was this answer's reliability actually
                # reduced by latency fusion? (fast answers keep their base.)
                updated = next(
                    e for e in reversed(session.history) if e.type.value == "hypothesis.updated"
                )
                effective = updated.payload.get("reliability_effective")
                if effective is not None and effective < question.reliability:
                    latency_discounted += 1
                record.append(("direct", option_count))

        turn_modes.append(record)
        assert session.prediction is not None  # revealed by construction
        is_correct = session.prediction.hypothesis_id == truth
        if is_correct:
            correct += 1
        # Reveal-path distribution (ROADMAP Phase 3): which out fired, and
        # whether it landed. Staging cannot change the posterior, so these
        # ride along with the inference metrics.
        path = session.reveal_plan.path if session.reveal_plan else "plain"
        reveal_paths[path] += 1
        reveal_correct[path] += 1 if is_correct else 0
        turns.append(session.turn)
        actual_reduced.append(max(0.0, initial_entropy - session.tracker.entropy()))
        if session.committed_because in (
            CommitReason.MAX_TURNS,
            CommitReason.NO_INFORMATIVE_QUESTION,
        ):
            forced += 1

    accuracy = correct / sessions
    avg_turns = statistics.mean(turns)
    avg_actual = statistics.mean(actual_reduced)

    def account(kappa_value: float) -> dict:
        visible = statistics.mean(
            sum(
                math.log2(count) if mode == "direct" else kappa_value * math.log2(3)
                for mode, count in session_record
            )
            for session_record in turn_modes
        )
        return {
            "kappa": kappa_value,
            "avg_visible_bits": round(visible, 4),
            "avg_information_mystery_gap_bits": round(avg_actual - visible, 4),
            "magic_factor_score": round(accuracy / (1.0 + visible), 4),
        }

    headline = account(kappa)
    sweep_accounts = [account(k) for k in KAPPA_SWEEP]

    kappa_star = None
    if baseline_direct is not None:
        direct_bits_auto = next(
            (s["avg_visible_bits"] for s in sweep_accounts if s["kappa"] == 0.0),
            0.0,
        )
        acc_direct = baseline_direct.get("top1_accuracy", 0.0)
        direct_bits_direct = baseline_direct.get(
            "avg_visible_bits_used",
            baseline_direct.get("avg_visible_bits", 0.0),
        )
        covert_turns = covert_responses / sessions
        kappa_star = compute_breakeven_kappa(
            accuracy,
            acc_direct,
            direct_bits_auto,
            direct_bits_direct,
            covert_turns,
        )

    return {
        "effect_id": effect.id,
        "sessions": sessions,
        "gaze_prob": gaze_prob,
        "top1_accuracy": round(accuracy, 4),
        "avg_turns": round(avg_turns, 2),
        "avg_actual_entropy_reduced_bits": round(avg_actual, 4),
        "forced_commit_rate": round(forced / sessions, 4),
        "avg_covert_turns": round(covert_responses / sessions, 2),
        "fishing_affirmation_rate": (
            round(covert_affirmations / covert_responses, 4) if covert_responses else 0.0
        ),
        "reveal_paths": {
            path: round(count / sessions, 4) for path, count in sorted(reveal_paths.items())
        },
        "accuracy_by_reveal_path": {
            path: round(reveal_correct[path] / count, 4)
            for path, count in sorted(reveal_paths.items())
            if count
        },
        "force_presented_per_session": round(force_presented / sessions, 2),
        "force_success_rate": (
            round(force_followed / force_presented, 4) if force_presented else 0.0
        ),
        "latency_discounted_rate": (
            round(latency_discounted / direct_answers, 4) if direct_answers else 0.0
        ),
        # headline accounting at the configured visibility weight
        "kappa": kappa,
        "avg_visible_bits_used": headline["avg_visible_bits"],
        "avg_information_mystery_gap_bits": headline["avg_information_mystery_gap_bits"],
        "magic_factor_score": headline["magic_factor_score"],
        "breakeven_kappa": kappa_star,
        "kappa_sweep": sweep_accounts,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="LOKI Magic Factor Evaluation")
    parser.add_argument("--effect", action="append", help="effect id (default: all)")
    parser.add_argument("--sessions", type=int, default=200)
    parser.add_argument("--reliability", type=float, default=None)
    parser.add_argument("--gaze-prob", type=float, default=0.5)
    parser.add_argument(
        "--policy",
        choices=("auto", "direct"),
        default="auto",
        help="auto mixes covert reads and direct questions (Method Selection "
        "Policy); direct keeps every turn an explicit question",
    )
    parser.add_argument(
        "--kappa",
        type=float,
        default=HEADLINE_KAPPA,
        help="visibility weight for covert turns (headline accounting; the "
        "full sweep is always reported)",
    )
    parser.add_argument(
        "--force-susceptibility",
        type=float,
        default=0.0,
        help="probability the simulated participant's answer noise "
        "concentrates on the choice-architecture salient option "
        "(docs/choice-architecture.md §5)",
    )
    parser.add_argument(
        "--no-fusion",
        action="store_true",
        help="strip the latency-modulation channels: measure the passive-signal "
        "fusion OFF arm (docs/passive-signals.md §4)",
    )
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument(
        "--baseline",
        type=Path,
        default=None,
        help="path to direct baseline JSON metrics (e.g. "
        "experiments/outputs/mf_direct_1000.json). If omitted, runs direct baseline "
        "alongside auto or reads precomputed baseline for 1000 sessions.",
    )
    parser.add_argument("--json", type=Path, default=None)
    args = parser.parse_args()

    registry = load_effects(DEFAULT_EFFECTS_DIR)
    effect_ids = args.effect or list(registry)
    unknown = [e for e in effect_ids if e not in registry]
    if unknown:
        parser.error(f"unknown effect(s): {unknown}; available: {list(registry)}")

    baseline_by_effect: dict[str, dict] = {}
    if args.policy == "auto":
        if args.baseline and args.baseline.is_file():
            try:
                raw_baseline = json.loads(args.baseline.read_text(encoding="utf-8"))
                for entry in raw_baseline:
                    if isinstance(entry, dict) and "effect_id" in entry:
                        baseline_by_effect[entry["effect_id"]] = entry
            except Exception as err:
                print(
                    f"Warning: Failed to load baseline from {args.baseline}: {err}",
                    file=sys.stderr,
                )
        elif args.sessions == 1000:
            std_base = REPO_ROOT / "experiments" / "outputs" / "mf_direct_1000.json"
            if std_base.is_file():
                try:
                    raw_baseline = json.loads(std_base.read_text(encoding="utf-8"))
                    for entry in raw_baseline:
                        if isinstance(entry, dict) and "effect_id" in entry:
                            baseline_by_effect[entry["effect_id"]] = entry
                except Exception:
                    pass

        missing_baselines = [eid for eid in effect_ids if eid not in baseline_by_effect]
        if missing_baselines:
            rng_direct = random.Random(args.seed)
            for eid in effect_ids:
                eff_direct = registry[eid].without_fishing()
                if args.no_fusion:
                    eff_direct = eff_direct.model_copy(update={"latency_channel": None})
                base_eval = evaluate_magic_factor(
                    eff_direct,
                    args.sessions,
                    args.reliability,
                    rng_direct,
                    gaze_prob=args.gaze_prob,
                    kappa=args.kappa,
                    force_susceptibility=args.force_susceptibility,
                )
                if eid in missing_baselines:
                    baseline_by_effect[eid] = base_eval

    rng = random.Random(args.seed)
    results = []
    for effect_id in effect_ids:
        effect = registry[effect_id]
        if args.policy == "direct":
            effect = effect.without_fishing()
        if args.no_fusion:
            effect = effect.model_copy(update={"latency_channel": None})
        base_match = baseline_by_effect.get(effect_id) if args.policy == "auto" else None
        results.append(
            evaluate_magic_factor(
                effect,
                args.sessions,
                args.reliability,
                rng,
                gaze_prob=args.gaze_prob,
                kappa=args.kappa,
                force_susceptibility=args.force_susceptibility,
                baseline_direct=base_match,
            )
        )

    print(
        f"LOKI Magic Factor Evaluation — sessions={args.sessions}, seed={args.seed}, "
        f"gaze_prob={args.gaze_prob}, policy={args.policy}, headline κ={args.kappa}, "
        f"force_susceptibility={args.force_susceptibility}"
    )
    header = (
        f"{'effect':<22}{'accuracy':>9}{'turns':>7}{'ΔH':>7}{'Vis_bits':>9}"
        f"{'Mystery':>8}{'MagicF':>8}{'forced':>8}{'covert':>7}{'affirm':>7}"
    )
    print(header)
    print("-" * len(header))
    for r in results:
        print(
            f"{r['effect_id']:<22}{r['top1_accuracy']:>9.3f}{r['avg_turns']:>7.2f}"
            f"{r['avg_actual_entropy_reduced_bits']:>7.3f}{r['avg_visible_bits_used']:>9.3f}"
            f"{r['avg_information_mystery_gap_bits']:>8.3f}{r['magic_factor_score']:>8.4f}"
            f"{r['forced_commit_rate']:>8.3f}{r['avg_covert_turns']:>7.2f}"
            f"{r['fishing_affirmation_rate']:>7.2f}"
        )
    print("\nκ sensitivity — visible-bit accounting for covert turns:")
    for r in results:
        cells = "  ".join(
            f"κ={a['kappa']:<5}V={a['avg_visible_bits']:>6.2f} "
            f"ΔHm={a['avg_information_mystery_gap_bits']:>6.2f} "
            f"M={a['magic_factor_score']:.3f}"
            for a in r["kappa_sweep"]
        )
        print(f"  {r['effect_id']:<22}{cells}")

    if args.policy == "auto":
        print("\nEmpirical breakeven κ* (auto policy vs direct baseline):")
        header_p1 = (
            f"  {'effect':<22}  {'acc(auto)':>9}  {'acc(dir)':>9}  "
            f"{'vis_dir(auto)':>13}  {'vis(dir)':>9}  {'covert_T':>8}"
        )
        headline_label = f"verdict @ headline κ={args.kappa}"
        header_p2 = f"  {'κ* breakeven':>12}    {headline_label:<28}"
        be_header = f"{header_p1}{header_p2}"
        print(be_header)
        print("  " + "-" * (len(be_header) - 2))
        for r in results:
            eid = r["effect_id"]
            base = baseline_by_effect.get(eid)
            k_star = r.get("breakeven_kappa")
            acc_dir_str = f"{base['top1_accuracy']:>9.3f}" if base else f"{'N/A':>9}"
            vis_dir_auto = next(
                (s["avg_visible_bits"] for s in r["kappa_sweep"] if s["kappa"] == 0.0),
                0.0,
            )
            vis_dir_base = (
                base.get("avg_visible_bits_used", base.get("avg_visible_bits", 0.0))
                if base
                else 0.0
            )
            vis_base_str = f"{vis_dir_base:>9.3f}" if base else f"{'N/A':>9}"
            k_star_str = f"{k_star:>12.4f}" if k_star is not None else f"{'N/A':>12}"

            if k_star is None:
                verdict = "N/A"
            elif args.kappa <= k_star:
                verdict = f"auto wins ({args.kappa:.2f} <= {k_star:.4f})"
            else:
                verdict = f"direct wins ({args.kappa:.2f} > {k_star:.4f})"

            row_p1 = (
                f"  {eid:<22}  {r['top1_accuracy']:>9.3f}  {acc_dir_str}  "
                f"{vis_dir_auto:>13.3f}  {vis_base_str}  {r['avg_covert_turns']:>8.2f}"
            )
            row_p2 = f"  {k_star_str}    {verdict:<28}"
            print(f"{row_p1}{row_p2}")
    else:
        print(
            "\nEmpirical breakeven κ*: N/A "
            "(direct policy evaluated; breakeven compares auto vs direct)"
        )

    print("\nreveal paths (share of sessions | accuracy within path):")
    for r in results:
        cells = "  ".join(
            f"{path}={share:.2f}@{r['accuracy_by_reveal_path'][path]:.2f}"
            for path, share in r["reveal_paths"].items()
            if share > 0
        )
        print(f"  {r['effect_id']:<22}{cells}")

    print("\nchoice architecture (presentations/session | picked salient | presented):")
    for r in results:
        print(
            f"  {r['effect_id']:<22}{r['force_presented_per_session']:>7.2f}"
            f"{r['force_success_rate']:>12.2f}"
        )

    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(results, indent=2), encoding="utf-8")
        print(f"\nresults written to {args.json}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
