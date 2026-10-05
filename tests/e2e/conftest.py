"""Shared fixtures and utilities for the LOKI E2E test suite (Tiers 1-4)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from services.api.archive import SessionArchive
from services.api.main import create_app
from services.effects.loader import load_effects
from services.language.renderer import LanguageRenderer

REPO_ROOT = Path(__file__).resolve().parents[2]
EFFECTS_DIR = REPO_ROOT / "configs" / "effects"


@pytest.fixture(scope="session")
def registry():
    """Loaded effect definitions across all 4 configured domains."""
    return load_effects(EFFECTS_DIR)


@pytest.fixture(scope="session")
def card_effect(registry):
    return registry["card_prediction"]


@pytest.fixture(scope="session")
def number_effect(registry):
    return registry["number_prediction"]


@pytest.fixture(scope="session")
def animal_effect(registry):
    return registry["animal_guess"]


@pytest.fixture(scope="session")
def sigil_effect(registry):
    return registry["sigil_forced_choice"]


@pytest.fixture()
def renderer():
    return LanguageRenderer("test-e2e-seed")


@pytest.fixture()
def temp_db(tmp_path: Path) -> Path:
    """Isolated temporary SQLite database file for testing consent-gated persistence."""
    return tmp_path / "test_sessions.db"


@pytest.fixture()
def archive(temp_db: Path) -> SessionArchive:
    """Hermetic SessionArchive instance pointed at a temporary DB."""
    return SessionArchive(temp_db)


@pytest.fixture()
def app(temp_db: Path):
    """FastAPI application configured with the temporary database path."""
    return create_app(EFFECTS_DIR, db_path=temp_db)


@pytest.fixture()
def client(app) -> TestClient:
    """FastAPI TestClient backed by an isolated database."""
    return TestClient(app)


def truthful_answer(effect, question, hypothesis_id: str) -> str:
    """Deterministic truthful option ID for a hidden hypothesis on a direct question."""
    attrs = effect.hypotheses[hypothesis_id]
    matches = [a.id for a in question.answers if a.predicate.matches(attrs)]
    assert len(matches) == 1, f"Expected exactly one match for {hypothesis_id}: {matches}"
    return matches[0]


def truthful_response(session, effect, hypothesis_id: str, **kwargs) -> None:
    """Deterministic truthful reply to the active turn of an EffectSession."""
    question = session.current_question
    assert question is not None, "Cannot respond when no question is active"
    if session.current_mode == "covert":
        asserted = next(a for a in question.answers if a.id == session.asserted_answer_id)
        holds = asserted.predicate.matches(effect.hypotheses[hypothesis_id])
        session.respond_agreement("strong_yes" if holds else "strong_no", **kwargs)
    else:
        ans_id = truthful_answer(effect, question, hypothesis_id)
        session.answer(ans_id, **kwargs)


def truthful_body(effect, view: dict[str, Any], hypothesis_id: str) -> dict[str, Any]:
    """Deterministic truthful payload for POST /api/sessions/{id}/answer."""
    question = next(q for q in effect.questions if q.id == view["question_id"])
    if view.get("mode") == "covert":
        asserted = next(a for a in question.answers if a.label == view["asserted_label"])
        holds = asserted.predicate.matches(effect.hypotheses[hypothesis_id])
        return {"answer_id": "strong_yes" if holds else "strong_no"}
    return {"answer_id": truthful_answer(effect, question, hypothesis_id)}
