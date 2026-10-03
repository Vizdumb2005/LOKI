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
