from __future__ import annotations

import pytest

from services.policy.info_gain import best_question, question_info_gain


def test_best_first_question_card_effect(card_effect):
    posterior = {hid: 1 / 52 for hid in card_effect.hypotheses}
    question, gain = best_question(card_effect, posterior, set())
    # rank bucket (7 near-uniform branches) beats suit and parity; the noise
    # model keeps the real gain below the ideal 2.72 bits
    assert question is not None and question.id == "q_rank_bucket"
    assert 2.0 < gain < 2.6
    suit_gain = question_info_gain(
        card_effect, posterior, next(q for q in card_effect.questions if q.id == "q_suit")
    )
    assert 1.5 < suit_gain < 2.1
    assert gain > suit_gain


def test_best_first_question_number_effect(number_effect):
    posterior = {hid: 1 / 100 for hid in number_effect.hypotheses}
    question, gain = best_question(number_effect, posterior, set())
    assert question is not None and question.id == "q_first_digit"
    assert 2.6 < gain < 3.1


def test_zero_gain_questions_are_skipped():
    from services.effects.models import AnswerOption, EffectDef, Predicate, Question, Termination

    effect = EffectDef(
        id="t",
        title="t",
        description="d",
        hypotheses={
            "a": {"tag": "x", "v": 1},
            "b": {"tag": "x", "v": 2},
            "c": {"tag": "x", "v": 3},
        },
        questions=[
            Question(
                id="useless",
                text="?",
                answers=[
                    # answer 1 matches every hypothesis; answer 2 matches none
                    AnswerOption(
                        id="all", label="all", predicate=Predicate(attr="tag", op="eq", value="x")
                    ),
                    AnswerOption(
                        id="none", label="none", predicate=Predicate(attr="tag", op="ne", value="x")
                    ),
                ],
            ),
            Question(
                id="useful",
                text="?",
                answers=[
                    AnswerOption(
                        id="lo", label="lo", predicate=Predicate(attr="v", op="lte", value=2)
                    ),
                    AnswerOption(
                        id="hi", label="hi", predicate=Predicate(attr="v", op="gte", value=3)
                    ),
                ],
            ),
        ],
        termination=Termination(entropy_threshold_bits=0.1, max_turns=5),
    )
    posterior = {"a": 1 / 3, "b": 1 / 3, "c": 1 / 3}
    # partition {a, b} vs {c} under the 0.9 default reliability: ~0.48 bits,
    # well below the 0.918-bit noiseless ideal — asserted with tolerance so the
    # test pins behavior, not the exact reliability constant
    assert question_info_gain(
        effect, posterior, next(q for q in effect.questions if q.id == "useful")
    ) == pytest.approx(0.479, abs=0.02)
    assert question_info_gain(
        effect, posterior, next(q for q in effect.questions if q.id == "useless")
    ) == pytest.approx(0.0, abs=1e-9)
    # zero-gain candidates are not selected: the engine treats None as a commit signal
    assert best_question(effect, posterior, {"useful"}) == (None, 0.0)


def test_asked_questions_excluded_and_exhaustion_signals_commit(card_effect):
    posterior = {hid: 1 / 52 for hid in card_effect.hypotheses}
    first, _ = best_question(card_effect, posterior, set())
    assert first is not None
    second, _ = best_question(card_effect, posterior, {first.id})
    assert second is not None and second.id != first.id
    all_asked = {q.id for q in card_effect.questions}
    assert best_question(card_effect, posterior, all_asked) == (None, 0.0)
