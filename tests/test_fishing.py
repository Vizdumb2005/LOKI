"""Covert fishing template tests (ROADMAP Phase 2).

The assertion bank must work for EVERY (effect, question, option) without
naming any option other than the asserted one — an assertion may leak only
the option it asserts (docs/covert-fishing.md).
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from pydantic import ValidationError

from services.effects.models import AnswerOption, Predicate, Question
from services.language.fishing import FISHING_OPENERS
from services.language.renderer import LanguageRenderer

RENDERER = LanguageRenderer()

EFFECTS_DIR = Path(__file__).resolve().parents[1] / "configs" / "effects"


def test_fishing_renders_asserted_label_deterministically():
    first = RENDERER.fishing("Queen or lower", "session-1", 1)
    again = RENDERER.fishing("Queen or lower", "session-1", 1)
    assert first == again
    assert "Queen or lower" in first


def test_different_turns_vary_or_stay_valid():
    for turn in range(1, 6):
        line = RENDERER.fishing("Red", "s", turn)
        assert "Red" in line


def test_default_bank_leak_free_for_every_registered_effect():
    """Exhaustive sweep: no opener may name another option of the question —
    the whole option set must not leak through an assertion of one option."""
    from services.effects.loader import load_effects

    registry = load_effects(EFFECTS_DIR)
    for effect in registry.values():
        for question in effect.questions:
            for answer in question.answers:
                line = RENDERER.fishing(answer.label, "sweep", 1).lower()
                for other in question.answers:
                    if other.id == answer.id:
                        continue
                    assert not re.search(
                        rf"\b{re.escape(other.label.lower())}\b",
                        line,
                    ), (
                        f"{effect.id}/{question.id}: opener leaked option "
                        f"'{other.label}' while asserting '{answer.label}': {line}"
                    )


def test_default_bank_interpolates_cleanly():
    for template in FISHING_OPENERS:
        assert "{label}" in template
        rendered = template.format(label="x")
        assert "x" in rendered


def test_yaml_openers_override_the_bank():
    question = Question(
        id="q",
        text="?",
        answers=[
            AnswerOption(id="a", label="Alpha", predicate=Predicate(attr="v", op="eq", value=1)),
            AnswerOption(id="b", label="Beta", predicate=Predicate(attr="v", op="eq", value=2)),
        ],
        fishing_openers=["Behold — {label}, no?"],
    )
    line = RENDERER.fishing("Alpha", "s", 1, openers=question.fishing_openers)
    assert line == "Behold — Alpha, no?"


def _question_with_openers(openers: list[str]) -> dict:
    return {
        "id": "q",
        "text": "?",
        "answers": [
            {"id": "a", "label": "Alpha", "predicate": {"attr": "v", "op": "eq", "value": 1}},
            {"id": "b", "label": "Beta", "predicate": {"attr": "v", "op": "eq", "value": 2}},
        ],
        "fishing_openers": openers,
    }


def test_openers_must_carry_label_placeholder():
    with pytest.raises(ValidationError, match="label"):
        Question(**_question_with_openers(["Behold — destiny, no?"]))


def test_openers_must_not_leak_other_labels():
    with pytest.raises(ValidationError, match="leak"):
        Question(**_question_with_openers(["Behold — {label} or Beta, no?"]))


def test_openers_must_interpolate():
    with pytest.raises(ValidationError, match="interpolate"):
        Question(**_question_with_openers(["{label} {bogus}!"]))


def test_openers_require_fishing_enabled():
    raw = _question_with_openers(["Behold — {label}, no?"])
    raw["fishing"] = False
    with pytest.raises(ValidationError, match="fishing is false"):
        Question(**raw)


def test_registered_effects_load_with_fishing_defaults():
    from services.effects.loader import load_effects

    registry = load_effects(EFFECTS_DIR)
    assert all(q.fishing for effect in registry.values() for q in effect.questions)
    assert all(not q.fishing_openers for effect in registry.values() for q in effect.questions)
