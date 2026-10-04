"""Reveal Planner — path selection for the reveal moment (ROADMAP Phase 3).

The digital translation of "multiple outs" (digital-translation.md §2): the
reveal is routed through pre-staged pathways depending on posterior spread,
so several outcomes can converge into one convincing performance. The
commit itself never changes — the prediction stays the MAP hypothesis and
the reveal still ends in the confidence-banded identity line (plan §4.8).

Boundary: this module DECIDES the path from structured state (top-k
posterior, asked questions, hypothesis attributes). Rendering the chosen
plan into theatrical lines is `services/language/reveal_planner.py` —
LOKI-Language never makes this choice (docs/reveal-planning.md §1).
"""

from __future__ import annotations

from dataclasses import dataclass

from services.effects.models import EffectDef


@dataclass(frozen=True)
class RevealStage:
    """One structured beat before the identity line."""

    kind: str  # "attribute" | "category" | "deduction"
    attr: str | None  # the attribute the beat names, when one exists
    label: str  # display text source (answer label / shared value)


@dataclass(frozen=True)
class RevealPlan:
    path: str  # "progressive" | "category_cluster" | "dual_deduction" | "plain"
    candidates: tuple[str, ...]  # hypothesis ids the staging considered
    stages: tuple[RevealStage, ...]  # beats that precede the identity line


# Bands (docs/reveal-planning.md §2-3); the hesitation window is the
# digital-translation spec's 0.6 < P < 0.85.
STRONG_COMMIT = 0.80
CLUSTER_CEILING = 0.80
CLUSTER_FLOOR = 0.50
DEDUCTION_FLOOR_MASS = 0.70  # combined top-2 mass for a two-name deduction
HESITATION_LOW = 0.60
HESITATION_HIGH = 0.85
YES_NO_LABELS = {"yes", "no"}


def _answer_label_for(effect: EffectDef, question_id: str, hypothesis_id: str) -> str | None:
    """The label of the answer matching the hypothesis on that question."""
    question = next(q for q in effect.questions if q.id == question_id)
    attrs = effect.hypotheses[hypothesis_id]
    for answer in question.answers:
        if answer.predicate.matches(attrs):
            return answer.label
    return None  # pragma: no cover - partition rule guarantees a match


def _ladder(
    effect: EffectDef, asked: list[str], hypothesis_id: str, limit: int = 2
) -> tuple[RevealStage, ...]:
    """Attribute beats from the session's asked questions, in ask order.

    Bare Yes/No confirmations are not stage-worthy text; they fold into the
    identity line instead.
    """
    stages: list[RevealStage] = []
    for question_id in asked:
        if len(stages) >= limit:
            break
        question = next(q for q in effect.questions if q.id == question_id)
        if len(question.answers) == 2:
            labels = {a.label.strip().lower() for a in question.answers}
            if labels <= YES_NO_LABELS:
                continue  # "Yes" reads as nothing on a stage line
        label = _answer_label_for(effect, question_id, hypothesis_id)
        if label is None:
            continue
        attr = question.answers[0].predicate.attr
        stages.append(RevealStage(kind="attribute", attr=attr, label=label))
    return tuple(stages)


def _shared_category(effect: EffectDef, hid_a: str, hid_b: str) -> RevealStage | None:
    """The first attribute (in the effect's question order) where the two
    hypotheses agree — the family both candidates live in."""
    attrs_a = effect.hypotheses[hid_a]
    attrs_b = effect.hypotheses[hid_b]
    seen: set[str] = set()
    for question in effect.questions:
        attr = question.answers[0].predicate.attr
        if attr in seen or attr not in attrs_a or attr not in attrs_b:
            continue
        seen.add(attr)
        if attrs_a[attr] == attrs_b[attr]:
            value = attrs_a[attr]
            label = next(
                (a.label for a in question.answers if a.predicate.matches(attrs_a)),
                str(value),
            )
            return RevealStage(kind="category", attr=attr, label=label)
    return None


def plan_reveal(
    effect: EffectDef,
    candidates: list[tuple[str, float]],
    asked: list[str],
) -> RevealPlan:
    """Choose the reveal path and its beats from the top-k posterior.

    ``candidates`` is top-k as (hypothesis_id, probability), best first.
    Deterministic: first-in-order wins ties everywhere.
    """
    top_ids = [hid for hid, _ in candidates[:3]]
    p1 = candidates[0][1]
    p2 = candidates[1][1] if len(candidates) > 1 else 0.0
    top1 = top_ids[0]
    top2 = top_ids[1] if len(top_ids) > 1 else None

    stages: tuple[RevealStage, ...] = ()
    if p1 >= STRONG_COMMIT:
        path = "progressive"
        stages = _ladder(effect, asked, top1)
    elif p1 >= CLUSTER_FLOOR and top2 is not None:
        shared = _shared_category(effect, top1, top2)
        if shared is not None:
            path = "category_cluster"
            stages = (shared,)
        else:
            path = "plain"
    elif top2 is not None and p1 + p2 >= DEDUCTION_FLOOR_MASS:
        path = "dual_deduction"
        stages = (RevealStage(kind="deduction", attr=None, label=effect.hypothesis_label(top2)),)
    else:
        path = "plain"

    return RevealPlan(path=path, candidates=tuple(top_ids), stages=stages)


def wants_hesitation(confidence: float) -> bool:
    """One hesitation beat lands inside the calibrated doubt window."""
    return HESITATION_LOW <= confidence < HESITATION_HIGH
