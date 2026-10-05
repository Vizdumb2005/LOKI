"""Agreement-response model for covert fishing turns (docs/covert-fishing.md).

One response matrix, two consumers:
- the ENGINE inverts rows into likelihood vectors over hypotheses — a soft
  Bayesian update that never eliminates a hypothesis (every entry > 0, the
  keep-competing-hypotheses-alive invariant);
- the SIMULATOR samples participant reactions from the same rows (the
  well-calibrated case; calibrating against real participants is later-phase
  work — idea.md Stage D / LOKI-Calibrator).

Rows are P(observed response | the assertion holds for the true target);
columns sum to 1. An ``unclear`` response is deliberately excluded from
updates: extractor uncertainty is not evidence (docs/covert-fishing.md).
"""

from __future__ import annotations

from services.effects.models import EffectDef, Question
from services.language.response_signals import AgreementStrength

RESPONSE_MODEL: dict[AgreementStrength, dict[bool, float]] = {
    AgreementStrength.STRONG_YES: {True: 0.70, False: 0.05},
    AgreementStrength.LEAN_YES: {True: 0.20, False: 0.12},
    AgreementStrength.UNCLEAR: {True: 0.02, False: 0.10},
    AgreementStrength.LEAN_NO: {True: 0.06, False: 0.43},
    AgreementStrength.STRONG_NO: {True: 0.02, False: 0.30},
}


def agreement_likelihoods(
    effect: EffectDef,
    question: Question,
    asserted_answer_id: str,
    strength: AgreementStrength,
) -> dict[str, float]:
    """P(observed agreement response | h) for every hypothesis h.

    The vector only shifts mass between the asserted option's partition and
    everything else — relative order inside a partition is untouched, which
    is exactly what "not really" tells us: not *this*, nothing more specific.
    """
    if strength is AgreementStrength.UNCLEAR:
        return {hid: 1.0 for hid in effect.hypotheses}
    try:
        asserted = next(a for a in question.answers if a.id == asserted_answer_id)
    except StopIteration:
        raise ValueError(
            f"answer '{asserted_answer_id}' is not an option of question '{question.id}'"
        ) from None
    model = RESPONSE_MODEL[strength]
    return {
        hid: model[asserted.predicate.matches(attrs)] for hid, attrs in effect.hypotheses.items()
    }
