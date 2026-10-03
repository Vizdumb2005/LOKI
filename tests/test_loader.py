from __future__ import annotations

import pytest
from pydantic import ValidationError

from services.effects.loader import load_effect, load_effects

VALID = """
id: t
title: t
description: d
hypothesis_space:
  type: enumerated
  items:
    - {id: a, tag: x, v: 1}
    - {id: b, tag: x, v: 2}
questions:
  - id: q1
    text: "?"
    answers:
      - {id: lo, label: lo, predicate: {attr: v, op: lte, value: 1}}
      - {id: hi, label: hi, predicate: {attr: v, op: gte, value: 2}}
termination: {entropy_threshold_bits: 0.1, max_turns: 5}
"""

MISSING_ATTRIBUTE = """
id: t
title: t
description: d
hypothesis_space:
  type: enumerated
  items:
    - {id: a, tag: x, v: 1}
    - {id: b, v: 2}
questions:
  - id: q1
    text: "?"
    answers:
      - {id: x, label: x, predicate: {attr: tag, op: eq, value: x}}
      - {id: hi, label: hi, predicate: {attr: v, op: gte, value: 2}}
termination: {entropy_threshold_bits: 0.1, max_turns: 5}
"""

NON_PARTITION = """
id: t
title: t
description: d
hypothesis_space:
  type: enumerated
  items:
    - {id: a, v: 1}
    - {id: b, v: 2}
questions:
  - id: q1
    text: "?"
    answers:
      - {id: lo, label: lo, predicate: {attr: v, op: lte, value: 2}}
      - {id: hi, label: hi, predicate: {attr: v, op: gte, value: 1}}
termination: {entropy_threshold_bits: 0.1, max_turns: 5}
"""


def _write(tmp_path, name: str, text: str):
    path = tmp_path / name
    path.write_text(text, encoding="utf-8")
    return path


def test_deck_52_builtin(card_effect):
    assert len(card_effect.hypotheses) == 52
    assert card_effect.hypotheses["AS"] == {
        "name": "Ace of Spades",
        "suit": "spades",
        "color": "black",
        "rank": "A",
        "rank_value": 14,
        "rank_class": "ace",
    }
    assert card_effect.hypotheses["2H"]["color"] == "red"
    assert card_effect.hypotheses["10D"]["rank_class"] == "number"
    assert card_effect.hypotheses["KC"]["rank_class"] == "face"


def test_range_builtin(number_effect):
    assert len(number_effect.hypotheses) == 100
    assert number_effect.hypotheses["7"]["first_digit"] == 0
    assert number_effect.hypotheses["100"]["first_digit"] == 1
    assert number_effect.hypotheses["99"]["digit_sum"] == 18


def test_registry_contains_all_effects(registry):
    assert set(registry) == {
        "card_prediction",
        "number_prediction",
        "animal_guess",
        "sigil_forced_choice",
    }


def test_valid_enumerated_effect_loads(tmp_path):
    effect = load_effect(_write(tmp_path, "t.yaml", VALID))
    assert set(effect.hypotheses) == {"a", "b"}


def test_missing_attribute_fails_at_load(tmp_path):
    with pytest.raises(ValueError, match="missing on hypothesis 'b'"):
        load_effect(_write(tmp_path, "t.yaml", MISSING_ATTRIBUTE))


def test_non_partition_question_fails_at_load(tmp_path):
    with pytest.raises(ValueError, match="exactly one answer must match"):
        load_effect(_write(tmp_path, "t.yaml", NON_PARTITION))


def test_unknown_space_type_fails(tmp_path):
    with pytest.raises(ValueError, match="unknown hypothesis space type"):
        load_effect(_write(tmp_path, "t.yaml", VALID.replace("type: enumerated", "type: bogus")))


def test_duplicate_effect_ids_fail(tmp_path):
    _write(tmp_path, "one.yaml", VALID)
    _write(tmp_path, "two.yaml", VALID)
    with pytest.raises(ValueError, match="duplicate effect id 't'"):
        load_effects(tmp_path)


def test_empty_effects_dir_fails(tmp_path):
    with pytest.raises(ValueError, match="no effect definitions"):
        load_effects(tmp_path)


def test_predicate_requires_mod_for_mod_eq():
    from services.effects.models import Predicate

    with pytest.raises(ValidationError, match="mod_eq"):
        Predicate(attr="v", op="mod_eq", value=0)
    with pytest.raises(ValidationError):
        Predicate(attr="v", op="eq")  # value required


def test_predicate_between_and_mod_eq_semantics():
    from services.effects.models import Predicate

    attrs = {"v": 7}
    assert Predicate(attr="v", op="between", value=[5, 10]).matches(attrs)
    assert not Predicate(attr="v", op="between", value=[8, 10]).matches(attrs)
    assert Predicate(attr="v", op="mod_eq", mod=3, value=1).matches(attrs)
    assert not Predicate(attr="v", op="mod_eq", mod=3, value=2).matches(attrs)
