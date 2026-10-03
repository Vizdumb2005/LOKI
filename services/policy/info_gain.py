"""Maximum expected information gain question selection (Phase 1 policy).

For each unasked question we compute the expected posterior entropy after the
answer update, weighting each possible answer by its probability under the
current posterior. The question with the largest expected entropy reduction
wins; questions with no positive gain are treated as exhausted (commit instead
of asking nothing useful).
"""

from __future__ import annotations

from services.effects.models import EffectDef, Question
from services.hypothesis.metrics import entropy


def expected_entropy(
    effect: EffectDef,
    posterior: dict[str, float],
    question: Question,
) -> float:
    """E[H(posterior after observing an answer to ``question``)], in bits."""
    h_after = 0.0
    for answer_id, p_answer in effect.predict_answer_distribution(posterior, question).items():
        if p_answer <= 0:
            continue
        likelihoods = effect.likelihoods(question, answer_id)
        weighted = {h: posterior[h] * likelihoods[h] for h in posterior}
        total = sum(weighted.values())
        if total <= 0:
            continue
        h_after += p_answer * entropy({h: w / total for h, w in weighted.items()})
    return h_after


def question_info_gain(
    effect: EffectDef,
    posterior: dict[str, float],
    question: Question,
) -> float:
    """Expected information gain of ``question`` under ``posterior`` (bits)."""
    return entropy(posterior) - expected_entropy(effect, posterior, question)


def best_question(
    effect: EffectDef,
    posterior: dict[str, float],
    asked: set[str],
) -> tuple[Question | None, float]:
    """Pick the unasked question with maximum expected information gain.

    Returns ``(None, 0.0)`` when no unasked question carries positive gain —
    the engine treats that as a commit signal.
    """
    candidates = [q for q in effect.questions if q.id not in asked]
    best: Question | None = None
    best_gain = 0.0
    for question in candidates:
        gain = question_info_gain(effect, posterior, question)
        if gain > best_gain + 1e-12:
            best, best_gain = question, gain
    return best, best_gain
