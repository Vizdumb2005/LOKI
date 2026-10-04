"""Effect loader: YAML -> validated EffectDef (docs/spec/effects-schema.md).

Strict by design: every question's predicates must reference attributes that
exist on *every* hypothesis, and for each (question, hypothesis) pair exactly
one answer may match — that is what makes the likelihood model a proper pmf.
A malformed effect fails at startup, never mid-session.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from services.effects.models import EffectDef

RANK_NAMES = {
    2: "Two",
    3: "Three",
    4: "Four",
    5: "Five",
    6: "Six",
    7: "Seven",
    8: "Eight",
    9: "Nine",
    10: "Ten",
    11: "Jack",
    12: "Queen",
    13: "King",
    14: "Ace",
}
SUITS = [
    ("hearts", "red", "Hearts", "H"),
    ("diamonds", "red", "Diamonds", "D"),
    ("clubs", "black", "Clubs", "C"),
    ("spades", "black", "Spades", "S"),
]


def _deck_52() -> dict[str, dict[str, Any]]:
    hypotheses: dict[str, dict[str, Any]] = {}
    for suit_id, color, suit_name, letter in SUITS:
        for value, rank_name in RANK_NAMES.items():
            if value == 14:
                rank, rank_class = "A", "ace"
            elif value == 11:
                rank, rank_class = "J", "face"
            elif value == 12:
                rank, rank_class = "Q", "face"
            elif value == 13:
                rank, rank_class = "K", "face"
            else:
                rank, rank_class = str(value), "number"
            hypotheses[f"{rank}{letter}"] = {
                "name": f"{rank_name} of {suit_name}",
                "suit": suit_id,
                "color": color,
                "rank": rank,
                "rank_value": value,
                "rank_class": rank_class,
            }
    return hypotheses


def _range_space(spec: dict[str, Any]) -> dict[str, dict[str, Any]]:
    lo, hi = int(spec["min"]), int(spec["max"])
    if lo > hi:
        raise ValueError(f"range hypothesis space requires min <= max, got [{lo}, {hi}]")
    hypotheses: dict[str, dict[str, Any]] = {}
    for v in range(lo, hi + 1):
        hypotheses[str(v)] = {
            "name": str(v),
            "value": v,
            # 0 encodes "single digit"; 100 correctly leads with digit 1
            "first_digit": int(str(v)[0]) if v >= 10 else 0,
            "digit_sum": sum(int(c) for c in str(v)),
        }
    return hypotheses


def _enumerated_space(spec: dict[str, Any]) -> dict[str, dict[str, Any]]:
    items = spec.get("items")
    if not isinstance(items, list) or not items:
        raise ValueError("'enumerated' hypothesis space requires a non-empty `items` list")
    hypotheses: dict[str, dict[str, Any]] = {}
    for item in items:
        if not isinstance(item, dict) or "id" not in item:
            raise ValueError(f"each enumerated hypothesis needs an 'id': got {item!r}")
        hid = str(item["id"])
        if hid in hypotheses:
            raise ValueError(f"duplicate hypothesis id '{hid}' in enumerated space")
        hypotheses[hid] = {k: v for k, v in item.items() if k != "id"}
    return hypotheses


_SPACE_BUILDERS = {
    "deck_52": lambda spec: _deck_52(),
    "range": _range_space,
    "enumerated": _enumerated_space,
}


def _expand_hypothesis_space(raw: dict[str, Any]) -> dict[str, dict[str, Any]]:
    space_type = raw.get("type")
    builder = _SPACE_BUILDERS.get(space_type)
    if builder is None:
        raise ValueError(
            f"unknown hypothesis space type '{space_type}' "
            f"(expected one of {sorted(_SPACE_BUILDERS)})"
        )
    return builder(raw)


def _validate_semantics(effect: EffectDef) -> None:
    for question in effect.questions:
        for answer in question.answers:
            attr = answer.predicate.attr
            missing = [hid for hid, attrs in effect.hypotheses.items() if attr not in attrs]
            if missing:
                raise ValueError(
                    f"effect '{effect.id}': question '{question.id}' answer "
                    f"'{answer.id}' references attribute '{attr}' that is missing "
                    f"on hypothesis '{missing[0]}' (and {len(missing) - 1} others)"
                )
        for hid, attrs in effect.hypotheses.items():
            matches = [a.id for a in question.answers if a.predicate.matches(attrs)]
            if len(matches) != 1:
                raise ValueError(
                    f"effect '{effect.id}': question '{question.id}' matches "
                    f"{len(matches)} answers ({matches}) on hypothesis '{hid}' — "
                    f"exactly one answer must match every hypothesis"
                )


def _build_effect(raw: dict[str, Any]) -> EffectDef:
    raw = dict(raw)
    space_raw = raw.pop("hypothesis_space", None)
    if not isinstance(space_raw, dict):
        raise ValueError("effect requires a 'hypothesis_space' mapping")
    raw["hypotheses"] = _expand_hypothesis_space(space_raw)
    if raw.get("prior") == "uniform":
        raw["prior"] = None
    # Schema v1.5: the latency channel is a modulation channel, not a
    # categorical one — parsed into its own field (docs/passive-signals.md).
    observations = raw.get("observations")
    if isinstance(observations, dict) and "response_latency" in observations:
        latency = observations["response_latency"]
        if not isinstance(latency, dict):
            raise ValueError("'response_latency' must be a mapping of fast_ms/slow_ms/floor")
        raw["latency_channel"] = latency
        raw["observations"] = {k: v for k, v in observations.items() if k != "response_latency"}
    effect = EffectDef.model_validate(raw)
    _validate_semantics(effect)
    return effect


def load_effect(path: Path) -> EffectDef:
    with open(path, encoding="utf-8") as fh:
        raw = yaml.safe_load(fh)
    if not isinstance(raw, dict):
        raise ValueError(f"{path}: expected a YAML mapping")
    try:
        return _build_effect(raw)
    except Exception as exc:
        raise ValueError(f"{path}: invalid effect definition — {exc}") from exc


def load_effects(directory: Path) -> dict[str, EffectDef]:
    """Load every ``*.yaml`` in ``directory``; duplicate effect ids are an error."""
    registry: dict[str, EffectDef] = {}
    seen: dict[str, Path] = {}
    for path in sorted(directory.glob("*.yaml")):
        effect = load_effect(path)
        if effect.id in registry:
            raise ValueError(f"duplicate effect id '{effect.id}' in {path} and {seen[effect.id]}")
        seen[effect.id] = path
        registry[effect.id] = effect
    if not registry:
        raise ValueError(f"no effect definitions found in {directory}")
    return registry
