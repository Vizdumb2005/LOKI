"""Consent-gated session archive (plan §6, §11) — the Phase 1 seed of the
LOKI Interaction Dataset.

Hard rules:
- Nothing is written while a séance is being played. The ONLY write path is
  ``save()``, invoked by ``POST /api/sessions/{id}/archive`` after the
  participant explicitly opts in on the outcome screen.
- ``delete()`` implements the required deletion control; it removes every
  trace of the session, including its event history.
- Only structured events are stored — there is no raw media in Phase 1, and
  the event schema forbids it regardless (docs/spec/event-schema.md).

Schema lives in code and is versioned via ``PRAGMA user_version``; future
migrations read that and apply incremental changes. This module intentionally
depends on nothing but the stdlib — it returns plain dicts and lets the API
layer wrap them in DTOs.
"""

from __future__ import annotations

import contextlib
import json
import sqlite3
import threading
from pathlib import Path
from typing import Any

from services.effects.engine import EffectSession

SCHEMA_VERSION = 1

_SCHEMA = """
CREATE TABLE IF NOT EXISTS sessions (
    session_id        TEXT PRIMARY KEY,
    effect_id         TEXT NOT NULL,
    created_at        TEXT NOT NULL,
    turns_used        INTEGER NOT NULL,
    prediction_id     TEXT NOT NULL,
    prediction_label  TEXT NOT NULL,
    confidence        REAL NOT NULL,
    correct           INTEGER,
    committed_because TEXT,
    events_json       TEXT NOT NULL
);
"""


class SessionArchive:
    def __init__(self, db_path: Path) -> None:
        self._db_path = Path(db_path)
        self._lock = threading.Lock()

    # -- write path (consent required upstream) ---------------------------------

    def save(self, session: EffectSession) -> dict[str, Any]:
        """Archive a completed session. Idempotent: re-saving returns the
        stored record unchanged."""
        assert session.prediction is not None, "only revealed sessions can be archived"
        events = [event.model_dump() for event in session.history]
        record = {
            "session_id": session.session_id,
            "effect_id": session.effect.id,
            "created_at": events[0]["ts"] if events else "",
            "turns_used": session.turn,
            "prediction_id": session.prediction.hypothesis_id,
            "prediction_label": session.prediction.label,
            "confidence": session.prediction.confidence,
            "correct": session.last_outcome_correct,
            "committed_because": (
                session.committed_because.value if session.committed_because else None
            ),
            "events_json": json.dumps(events),
        }
        with self._lock:
            self._db_path.parent.mkdir(parents=True, exist_ok=True)
            with contextlib.closing(self._connect()) as conn:
                with conn:  # transaction
                    conn.executescript(_SCHEMA)
                    conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
                    conn.execute(
                        """
                        INSERT OR IGNORE INTO sessions
                        (session_id, effect_id, created_at, turns_used, prediction_id,
                         prediction_label, confidence, correct, committed_because, events_json)
                        VALUES (:session_id, :effect_id, :created_at, :turns_used, :prediction_id,
                                :prediction_label, :confidence, :correct, :committed_because,
                                :events_json)
                        """,
                        record,
                    )
                    row = conn.execute(
                        "SELECT * FROM sessions WHERE session_id = ?",
                        (session.session_id,),
                    ).fetchone()
        return self._summary_from_row(row)

    def delete(self, session_id: str) -> bool:
        with self._lock:
            if not self._db_path.exists():
                return False
            with contextlib.closing(self._connect()) as conn:
                with conn:  # transaction
                    cursor = conn.execute(
                        "DELETE FROM sessions WHERE session_id = ?", (session_id,)
                    )
                deleted = cursor.rowcount > 0
        return deleted

    # -- read paths -------------------------------------------------------------

    def list_summaries(self) -> list[dict[str, Any]]:
        if not self._db_path.exists():
            return []
        with contextlib.closing(self._connect()) as conn:
            rows = conn.execute("SELECT * FROM sessions ORDER BY created_at DESC").fetchall()
        return [self._summary_from_row(row) for row in rows]

    def stats(self) -> list[dict[str, Any]]:
        """Per-effect aggregates over archived sessions only."""
        if not self._db_path.exists():
            return []
        with contextlib.closing(self._connect()) as conn:
            rows = conn.execute(
                """
                SELECT effect_id,
                       COUNT(*)                          AS archived,
                       SUM(correct IS NOT NULL)          AS with_outcome,
                       SUM(COALESCE(correct, 0))         AS correct,
                       AVG(CASE WHEN correct IS NOT NULL
                                THEN turns_used END)     AS avg_turns
                FROM sessions
                GROUP BY effect_id
                """
            ).fetchall()
        return [dict(row) for row in rows]

    # -- internals ----------------------------------------------------------------

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        return conn

    @staticmethod
    def _summary_from_row(row: sqlite3.Row) -> dict[str, Any]:
        summary = dict(row)
        summary.pop("events_json", None)  # history is retrievable per-session later
        return summary
