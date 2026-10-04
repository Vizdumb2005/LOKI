"""A/B human-trial analysis (ROADMAP Phase 6, docs/human-trials.md §4).

Reads the consented survey records from the archive database and compares
conditions on the §4 Likert instrument (perceived impossibility, freedom,
naturalness, surprise) with bootstrap CIs and rank/parametric tests, plus the
objective protocol as manipulation checks.

    python -m experiments.analyze_ab                        # real records
    python -m experiments.analyze_ab --simulated 60         # labeled placeholder pilot

The simulated pilot validates the PIPELINE end-to-end; its "scores" are
placeholder distributions and say NOTHING about human perception.
"""

from __future__ import annotations

import argparse
import math
import random
import statistics
import sys
from pathlib import Path

from services.api.archive import SessionArchive

ITEMS = ("impossibility", "freedom", "naturalness", "surprise")


def bootstrap_ci(
    values: list[float], statistic=statistics.mean, reps: int = 2000
) -> tuple[float, float]:
    """95% bootstrap confidence interval for the statistic."""
    if not values:
        return (float("nan"), float("nan"))
    rng = random.Random(0)
    stats = []
    n = len(values)
    for _ in range(reps):
        sample = [values[rng.randrange(n)] for _ in range(n)]
        stats.append(statistic(sample))
    stats.sort()
    return (stats[int(0.025 * reps)], stats[int(0.975 * reps) - 1])


def mann_whitney_u(a: list[float], b: list[float]) -> tuple[float, float]:
    """U statistic and a normal-approximation two-sided p-value (large-n; no
    tie correction — the instrument's ties make exact tables pointless)."""
    n_a, n_b = len(a), len(b)
    if n_a == 0 or n_b == 0:
        return (float("nan"), float("nan"))
    pooled = [(v, 0) for v in a] + [(v, 1) for v in b]
    pooled.sort()
    ranks = [0.0] * len(pooled)
    i = 0
    while i < len(pooled):
        j = i
        while j < len(pooled) and pooled[j][0] == pooled[i][0]:
            j += 1
        average_rank = (i + j - 1) / 2 + 1
        for k in range(i, j):
            ranks[k] = average_rank
        i = j
    rank_sum_a = sum(rank for rank, (v, side) in zip(ranks, pooled, strict=True) if side == 0)
    u_a = rank_sum_a - n_a * (n_a + 1) / 2
    mu = n_a * n_b / 2
    sigma = (n_a * n_b * (n_a + n_b + 1) / 12) ** 0.5
    if sigma == 0:
        return (u_a, float("nan"))
    z = (u_a - mu) / sigma
    p = 2.0 * (1.0 - 0.5 * (1.0 + math.erf(abs(z) / math.sqrt(2))))
    return (u_a, p)


def welch_t(a: list[float], b: list[float]) -> float:
    """Welch's t statistic (df-aware p-values are left to the writeup)."""
    if len(a) < 2 or len(b) < 2:
        return float("nan")
    var_a = statistics.variance(a)
    var_b = statistics.variance(b)
    denom = (var_a / len(a) + var_b / len(b)) ** 0.5
    if denom == 0:
        return 0.0
    return (statistics.mean(a) - statistics.mean(b)) / denom


def analyze(rows: list[dict]) -> dict:
    by_condition: dict[str, dict[str, list[float]]] = {"a": {}, "b": {}}
    for row in rows:
        condition = row.get("condition")
        if condition not in by_condition:
            continue
        for item in ITEMS:
            by_condition[condition].setdefault(item, []).append(row[item])
    report: dict = {"n": {c: len(by_condition[c].get(ITEMS[0], [])) for c in by_condition}}
    for item in ITEMS:
        a = by_condition["a"].get(item, [])
        b = by_condition["b"].get(item, [])
        u, p_u = mann_whitney_u(a, b)
        report[item] = {
            "mean_a": round(statistics.mean(a), 3) if a else None,
            "mean_b": round(statistics.mean(b), 3) if b else None,
            "ci_a": tuple(round(x, 3) for x in bootstrap_ci(a)) if a else None,
            "ci_b": tuple(round(x, 3) for x in bootstrap_ci(b)) if b else None,
            "welch_t": round(welch_t(a, b), 3),
            "mann_whitney_u": round(u, 1),
            "p_normal_approx": round(p_u, 4),
        }
    # manipulation checks (objective protocol)
    for condition in ("a", "b"):
        rows_c = [
            r for r in rows if r.get("condition") == condition and r.get("correct") is not None
        ]
        report[f"accuracy_{condition}"] = (
            round(sum(r["correct"] for r in rows_c) / len(rows_c), 3) if rows_c else None
        )
    return report


def _simulated_rows(n: int, rng: random.Random) -> list[dict]:
    """PLACEHOLDER pilot data — clearly labeled, says nothing about humans."""
    rows = []
    for i in range(n):
        condition = "a" if i % 2 == 0 else "b"
        # synthetic gap: condition B rates ~0.8 higher on impossibility only
        lift = 0.8 if condition == "b" else 0.0
        base = {
            item: rng.uniform(3.2, 5.2) + (lift if item == "impossibility" else 0.0)
            for item in ITEMS
        }
        rows.append(
            {
                "session_id": f"sim-{i}",
                "condition": condition,
                **{item: max(1, min(7, round(base[item]))) for item in ITEMS},
                "willing_repeat": rng.random() < (0.7 if condition == "b" else 0.5),
                "effect_id": "card_prediction",
                "correct": rng.random() < 0.9,
                "turns_used": rng.randint(3, 9),
            }
        )
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description="LOKI A/B analysis")
    parser.add_argument("--db", type=Path, default=Path("data/sessions.db"))
    parser.add_argument(
        "--simulated",
        type=int,
        default=0,
        help="run the pipeline on N synthetic records (labeled placeholder pilot)",
    )
    args = parser.parse_args()

    if args.simulated:
        rows = _simulated_rows(args.simulated, random.Random(0))
        print(f"SIMULATED pilot ({args.simulated} placeholder records) — not human data")
    else:
        archive = SessionArchive(args.db)
        rows = archive.survey_rows()
        print(f"consented survey records: {len(rows)}")
    if not rows:
        print("nothing to analyze yet")
        return 0

    report = analyze(rows)
    print(f"\nn per condition: {report.pop('n')}")
    header = (
        f"{'item':<15}{'mean A':>8}{'mean B':>8}{'CI A':>16}{'CI B':>16}{'t':>7}{'U':>9}{'p≈':>7}"
    )
    print(header)
    print("-" * len(header))
    for item in ITEMS:
        r = report[item]
        if r["mean_a"] is None:
            continue
        print(
            f"{item:<15}{r['mean_a']:>8.2f}{r['mean_b']:>8.2f}"
            f"{str(r['ci_a']):>16}{str(r['ci_b']):>16}"
            f"{r['welch_t']:>7.2f}{r['mann_whitney_u']:>9.1f}{r['p_normal_approx']:>7.3f}"
        )
    print(f"\nmanipulation checks: accuracy A={report['accuracy_a']}, B={report['accuracy_b']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
