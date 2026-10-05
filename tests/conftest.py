"""Shared fixtures: validated effect registry, engine, API client."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from services.api.main import create_app
from services.effects.loader import load_effects
from services.language.renderer import LanguageRenderer

EFFECTS_DIR = Path(__file__).resolve().parents[1] / "configs" / "effects"


@pytest.fixture(scope="session")
def registry():
    return load_effects(EFFECTS_DIR)


@pytest.fixture(scope="session")
def card_effect(registry):
    return registry["card_prediction"]


@pytest.fixture(scope="session")
def number_effect(registry):
    return registry["number_prediction"]


@pytest.fixture(scope="session")
def renderer():
    return LanguageRenderer()


@pytest.fixture()
def client():
    return TestClient(create_app(EFFECTS_DIR))


def truthful_answer(effect, question, hypothesis_id: str) -> str:
    """The deterministic truthful answer to `question` for a hidden hypothesis."""
    attrs = effect.hypotheses[hypothesis_id]
    matches = [a.id for a in question.answers if a.predicate.matches(attrs)]
    assert len(matches) == 1, f"expected exactly one match for {hypothesis_id}: {matches}"
    return matches[0]


def direct_only(effect):
    """A copy of `effect` with covert fishing disabled on every question."""
    return effect.model_copy(
        update={"questions": [q.model_copy(update={"fishing": False}) for q in effect.questions]}
    )


def truthful_response(session, effect, hypothesis_id: str, **kwargs) -> None:
    """Deterministic truthful response to the session's current turn, whatever
    its mode (docs/covert-fishing.md): the truthful option id on direct turns;
    strong_yes / strong_no on covert turns according to whether the assertion
    holds for the hidden hypothesis."""
    question = session.current_question
    assert question is not None
    if session.current_mode == "covert":
        asserted = next(a for a in question.answers if a.id == session.asserted_answer_id)
        holds = asserted.predicate.matches(effect.hypotheses[hypothesis_id])
        session.respond_agreement("strong_yes" if holds else "strong_no", **kwargs)
    else:
        session.answer(truthful_answer(effect, question, hypothesis_id), **kwargs)


def truthful_body(effect, view, hypothesis_id: str) -> dict:
    """Request body for a deterministic truthful response to the current turn
    of an API session view, whatever its mode."""
    question = next(q for q in effect.questions if q.id == view["question_id"])
    if view.get("mode") == "covert":
        asserted = next(a for a in question.answers if a.label == view["asserted_label"])
        holds = asserted.predicate.matches(effect.hypotheses[hypothesis_id])
        return {"answer_id": "strong_yes" if holds else "strong_no"}
    return {"answer_id": truthful_answer(effect, question, hypothesis_id)}
