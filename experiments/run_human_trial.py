"""Interactive Human Trial Runner (§18, Job e).

Runs an interactive double-blind séance session with a human participant,
records true response latencies and choices, presents the outcome and reveal ladder,
and collects consent-gated Likert survey records into data/sessions.db.

Usage:
    python -m experiments.run_human_trial
    python -m experiments.run_human_trial --effect card_prediction
    python -m experiments.run_human_trial --condition b
"""

from __future__ import annotations

import argparse
import random
import sys
import time
from datetime import datetime, timezone
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

from services.api.archive import SessionArchive
from services.effects.engine import EffectSession, Phase
from services.effects.loader import load_effects
from services.language.renderer import LanguageRenderer

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_EFFECTS_DIR = REPO_ROOT / "configs" / "effects"
DEFAULT_DB_PATH = REPO_ROOT / "data" / "sessions.db"

AGREEMENT_MAP = {
    "1": ("strong_yes", "Yes, exactly"),
    "2": ("lean_yes", "Sort of…"),
    "3": ("lean_no", "Not really"),
}


def run_session(
    effect_id: str = "card_prediction",
    condition: str | None = None,
    db_path: Path = DEFAULT_DB_PATH,
) -> bool:
    effects = load_effects(DEFAULT_EFFECTS_DIR)
    if effect_id not in effects:
        print(f"Unknown effect '{effect_id}'. Available: {list(effects.keys())}")
        return False

    effect = effects[effect_id]
    renderer = LanguageRenderer()
    assigned_condition = condition or ("a" if random.random() < 0.5 else "b")

    if assigned_condition == "a":
        session = EffectSession(
            effect.without_fishing(), renderer, performance=False, condition="a"
        )
    else:
        session = EffectSession(effect, renderer, condition="b")

    print("\n" + "=" * 60)
    print("           LOKI — DIGITAL SÉANCE EXPERIMENT")
    print("=" * 60)
    print(f"\nEffect: {effect.title}")
    print(f"{effect.description}\n")
    print("Focus your mind on your target...")
    print("When ready, press Enter to begin the interaction.")
    input(">>> ")

    while session.phase is Phase.ACTIVE:
        print("\n" + "-" * 50)
        if session.current_mode == "covert":
            print(f"LOKI senses: \"{session.ask_message}\"")
            print("\nHow does this feel to you?")
            print("  [1] Yes, exactly")
            print("  [2] Sort of…")
            print("  [3] Not really")
            t0 = time.perf_counter()
            choice = input("Your reaction (1-3): ").strip()
            latency_ms = (time.perf_counter() - t0) * 1000.0
            strength_val = AGREEMENT_MAP.get(choice, ("lean_yes", "Sort of…"))[0]
            session.respond_agreement(strength_val, latency_ms=latency_ms)
        else:
            q = session.current_question
            print(f"LOKI asks: \"{session.ask_message}\"")
            for idx, ans in enumerate(q.answers, start=1):
                print(f"  [{idx}] {ans.label}")
            t0 = time.perf_counter()
            choice = input(f"Choose an option (1-{len(q.answers)}): ").strip()
            latency_ms = (time.perf_counter() - t0) * 1000.0
            try:
                selected_idx = int(choice) - 1
                if 0 <= selected_idx < len(q.answers):
                    ans_id = q.answers[selected_idx].id
                else:
                    ans_id = q.answers[0].id
            except ValueError:
                ans_id = q.answers[0].id
            session.answer(ans_id, latency_ms=latency_ms)

    print("\n" + "=" * 60)
    print("                    THE REVEAL")
    print("=" * 60)
    if session.reveal_plan and session.reveal_plan.stages:
        for stage in session.reveal_plan.stages:
            print(f"… {stage.label} …")
            time.sleep(0.5)

    print(f"\n{session.reveal_message}")
    print(f"\nLOKI's Final Prediction: {session.prediction.label.upper()}")
    print(f"(Confidence: {session.prediction.confidence * 100:.1f}%)")

    correct_in = input("\nDid LOKI name your true thought? (y/n): ").strip().lower()
    is_correct = correct_in.startswith("y")
    session.report_outcome(is_correct)

    print("\n" + "=" * 60)
    print("       OPTIONAL RESEARCH SURVEY (CONSENT-GATED)")
    print("=" * 60)
    print("Please rate your experience on a 1 (not at all) to 7 (completely) scale.")
    print("Your answers help measure the Information Mystery Gap experimentally.\n")

    def get_likert(prompt: str) -> int:
        while True:
            val = input(f"{prompt} (1-7): ").strip()
            if val.isdigit() and 1 <= int(val) <= 7:
                return int(val)
            print("Please enter a whole number between 1 and 7.")

    impossibility = get_likert(
        "1. IMPOSSIBILITY: How impossible was it for an algorithm to deduce your choice?"
    )
    freedom = get_likert(
        "2. FREEDOM: Did you feel completely unconstrained in your thinking and choices?"
    )
    naturalness = get_likert(
        "3. NATURALNESS: How natural and conversational did the séance feel?"
    )
    surprise = get_likert(
        "4. SURPRISE: How surprised were you by the reveal?"
    )
    repeat_in = input(
        "\nWould you try this again or show it to someone else? (y/n): "
    ).strip().lower()
    willing_repeat = 1 if repeat_in.startswith("y") else 0

    consent = input(
        "\nDo you consent to saving these research metrics to data/sessions.db? (y/n): "
    ).strip().lower()

    if consent.startswith("y"):
        archive = SessionArchive(db_path)
        archive.save(session)
        archive.save_survey(
            session.session_id,
            session.condition,
            {
                "impossibility": impossibility,
                "freedom": freedom,
                "naturalness": naturalness,
                "surprise": surprise,
                "willing_repeat": willing_repeat,
            },
            created_at=datetime.now(timezone.utc).isoformat(),
        )
        print("\nSession and survey successfully recorded in the research ledger.")
    else:
        print("\nRecord discarded per consent policy. No data stored.")

    # Debrief per Directive §18 & §20
    print("\n" + "=" * 60)
    print("                   PARTICIPANT DEBRIEF")
    print("=" * 60)
    print(
        "LOKI is a research prototype investigating the digitalization of mentalism.\n"
        "It uses exact Bayesian inference, information-gain queries, and structured\n"
        "theatrical timing. It possesses no telepathic or supernatural capabilities.\n"
        "Thank you for participating!"
    )
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description="LOKI Interactive Human Trial Runner")
    parser.add_argument("--effect", type=str, default="card_prediction")
    parser.add_argument("--condition", type=str, choices=["a", "b"], default=None)
    parser.add_argument("--db", type=Path, default=DEFAULT_DB_PATH)
    args = parser.parse_args()

    success = run_session(effect_id=args.effect, condition=args.condition, db_path=args.db)
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
