"""Normative effect schema (docs/spec/effects-schema.md).

Every effect loaded into LOKI is validated against these models. Malformed
effects must fail at load time, never mid-session.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator


class Predicate(BaseModel):
    """A test over a hypothesis's attributes.

    The predicate is what makes an answer meaningful: it selects the subset of
    hypotheses that the answer claims to match. Attributes are immutable facts
    about the hidden target — never behavioral observations.
    """

    attr: str
    op: Literal["eq", "ne", "gt", "gte", "lt", "lte", "in", "not_in", "between", "mod_eq"] = "eq"
    value: Any = None
    mod: int | None = None

    @model_validator(mode="after")
    def _validate_op_args(self) -> "Predicate":
        if self.op in ("in", "not_in") and not isinstance(self.value, list):
            raise ValueError(f"op '{self.op}' requires a list value")
        if self.op == "between":
            if (
                not isinstance(self.value, (list, tuple))
                or len(self.value) != 2
                or self.value[0] > self.value[1]
            ):
                raise ValueError("op 'between' requires [lo, hi] with lo <= hi")
        if self.op == "mod_eq" and (self.mod is None or self.mod < 1):
            raise ValueError("op 'mod_eq' requires a positive integer `mod`")
        if self.value is None:
            raise ValueError(f"op '{self.op}' requires a value")
        return self

    def matches(self, attrs: Mapping[str, Any]) -> bool:
        if self.attr not in attrs:
            raise KeyError(f"predicate references unknown attribute '{self.attr}'")
        v = attrs[self.attr]
        match self.op:
            case "eq":
                return v == self.value
            case "ne":
                return v != self.value
            case "gt":
                return v > self.value
            case "gte":
                return v >= self.value
            case "lt":
                return v < self.value
            case "lte":
                return v <= self.value
            case "in":
                return v in self.value
            case "not_in":
                return v not in self.value
            case "between":
                return self.value[0] <= v <= self.value[1]
            case "mod_eq":
                return v % self.mod == self.value
        raise ValueError(f"unsupported op '{self.op}'")  # pragma: no cover


class AnswerOption(BaseModel):
    id: str
    label: str
    predicate: Predicate
    # Optional spoken synonyms (schema v1.1): transcript tokens that resolve to
    # this answer, used by the in-browser voice matcher.
    voice: list[str] = Field(default_factory=list)


class Question(BaseModel):
    id: str
    text: str
    answers: list[AnswerOption] = Field(min_length=2)
    reliability: float = Field(default=0.9, gt=0.0, le=1.0)
    # Schema v1.2: covert-fishing presentation (docs/covert-fishing.md).
    # `fishing: false` opts a question out of assertion-style turns;
    # `fishing_openers` overrides the default assertion bank. An opener must
    # carry a {label} placeholder and must not name any OTHER option of this
    # question — an assertion may leak only the option it asserts.
    fishing: bool = True
    fishing_openers: list[str] = Field(default_factory=list)

    @field_validator("answers")
    @classmethod
    def _unique_answer_ids(cls, answers: list[AnswerOption]) -> list[AnswerOption]:
        ids = [a.id for a in answers]
        if len(set(ids)) != len(ids):
            raise ValueError(f"answer ids must be unique within a question: {ids}")
        return answers

    @model_validator(mode="after")
    def _validate_fishing_openers(self) -> "Question":
        if not self.fishing and self.fishing_openers:
            raise ValueError(f"question '{self.id}': fishing_openers set but fishing is false")
        for template in self.fishing_openers:
            if "{label}" not in template:
                raise ValueError(
                    f"question '{self.id}': fishing opener must contain a '{{label}}' placeholder"
                )
            try:
                template.format(label="x")
            except (KeyError, IndexError, ValueError) as exc:
                raise ValueError(
                    f"question '{self.id}': fishing opener {template!r} does not interpolate: {exc}"
                ) from exc
            static = template.replace("{label}", " ").lower()
            for answer in self.answers:
                if re.search(rf"\b{re.escape(answer.label.lower())}\b", static):
                    raise ValueError(
                        f"question '{self.id}': fishing opener names another answer label "
                        f"'{answer.label}' — an assertion must not leak the option set"
                    )
        return self


class Termination(BaseModel):
    entropy_threshold_bits: float = Field(ge=0.0)
    max_turns: int = Field(ge=1)


class ObservationChannel(BaseModel):
    """A non-verbal evidence channel (schema v1.1): gaze dwell, prosody, ...

    Reliability is deliberately WEAK (strictly below answer reliability): a
    dwelled gaze is a hint about the answer the participant is about to give,
    not a statement. Observations never advance a session and never trigger
    termination — they only move probability mass (docs/spec/effects-schema.md).
    """

    reliability: float = Field(gt=0.0, lt=1.0)
    min_dwell_ms: int = Field(default=400, ge=0)


class LatencyChannel(BaseModel):
    """Response-latency modulation channel (schema v1.5, docs/passive-signals.md).

    Unlike categorical observation channels, latency modulates how much the
    verbal answer itself is worth: fast answers keep their full reliability,
    hesitant ones are discounted toward the floor. Declared per effect under
    the ``response_latency:`` YAML key and parsed by the loader.
    """

    fast_ms: float = Field(gt=0.0)
    slow_ms: float = Field(gt=0.0)
    floor: float = Field(gt=0.0, le=1.0)

    @model_validator(mode="after")
    def _validate_bounds(self) -> "LatencyChannel":
        if self.fast_ms >= self.slow_ms:
            raise ValueError("latency channel requires fast_ms < slow_ms")
        return self


class EffectDef(BaseModel):
    id: str
    title: str
    description: str
    hypotheses: dict[str, dict[str, Any]]
    prior: dict[str, float] | None = None
    questions: list[Question] = Field(min_length=1)
    observations: dict[str, ObservationChannel] = Field(default_factory=dict)
    # Schema v1.5: latency modulation (docs/passive-signals.md). Parsed from
    # the `response_latency:` YAML key by the loader — a different shape than
    # the categorical observation channels, hence its own field.
    latency_channel: LatencyChannel | None = None
    termination: Termination

    @field_validator("questions")
    @classmethod
    def _unique_question_ids(cls, questions: list[Question]) -> list[Question]:
        ids = [q.id for q in questions]
        if len(set(ids)) != len(ids):
            raise ValueError(f"question ids must be unique within an effect: {ids}")
        return questions

    @model_validator(mode="after")
    def _validate_prior(self) -> "EffectDef":
        if self.prior is not None:
            unknown = set(self.prior) - set(self.hypotheses)
            if unknown:
                raise ValueError(f"prior references unknown hypotheses: {sorted(unknown)[:5]}")
        return self

    # -- likelihood model (Stage A: interpretable, non-neural) -----------------

    def without_fishing(self) -> "EffectDef":
        """A copy with covert fishing disabled on every question — used by
        direct-only comparison runs (docs/covert-fishing.md)."""
        return self.model_copy(
            update={"questions": [q.model_copy(update={"fishing": False}) for q in self.questions]}
        )

    def likelihoods(
        self,
        question: Question,
        answer_id: str,
        reliability: float | None = None,
    ) -> dict[str, float]:
        """P(observing ``answer_id`` | h) for every hypothesis h.

        r for the matching answer, (1 - r) / (k - 1) spread over the rest
        (docs/spec/effects-schema.md). The loader guarantees exactly one answer
        matches each hypothesis, so these sum to 1 across answers.
        ``reliability`` overrides the question's own — used by the weak
        observation channels (schema v1.1).
        """
        try:
            answer = next(a for a in question.answers if a.id == answer_id)
        except StopIteration:
            raise ValueError(
                f"answer '{answer_id}' is not an option of question '{question.id}'"
            ) from None
        r = reliability if reliability is not None else question.reliability
        k = len(question.answers)
        alternative = (1.0 - r) / (k - 1) if k > 1 else 0.0
        return {
            hid: r if answer.predicate.matches(attrs) else alternative
            for hid, attrs in self.hypotheses.items()
        }

    def predict_answer_distribution(
        self,
        posterior: Mapping[str, float],
        question: Question,
    ) -> dict[str, float]:
        """P(observing each answer) under the current posterior."""
        dist = {a.id: 0.0 for a in question.answers}
        for a in question.answers:
            lik = self.likelihoods(question, a.id)
            dist[a.id] = sum(posterior[h] * lik[h] for h in posterior)
        return dist

    def hypothesis_label(self, hypothesis_id: str) -> str:
        return str(self.hypotheses[hypothesis_id].get("name", hypothesis_id))
