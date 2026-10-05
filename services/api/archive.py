"""Consent-gated session archive (plan §6, §11) — the Phase 1 seed of the
LOKI Interaction Dataset.

Hard rules:
- Nothing is written while a séance is being played. The ONLY write paths are
  ``save()`` (invoked by ``POST /api/sessions/{id}/archive`` after the
  participant explicitly opts in on the outcome screen) and ``save_survey()``
  (invoked by ``POST /api/sessions/{id}/survey`` — submitting the survey IS
  the consent act, docs/human-trials.md §3).
- ``delete()`` implements the required deletion control; it removes every
  trace of the session, including its event history and any survey answers.
- Only structured events and survey numbers are stored — no raw media (the
  event schema forbids it regardless, docs/spec/event-schema.md).

Schema lives in code and is versioned via ``PRAGMA user_version``; migrations
are incremental. v2 (ROADMAP Phase 6) adds the A/B survey table. This module
intentionally depends on nothing but the stdlib — it returns plain dicts and
lets the API layer wrap them in DTOs.
"""

from __future__ import annotations

import contextlib
import json
import sqlite3
import threading
from pathlib import Path
from typing import Any

from services.effects.engine import EffectSession

SCHEMA_VERSION = 2

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
CREATE TABLE IF NOT EXISTS surveys (
    session_id        TEXT PRIMARY KEY,
    condition         TEXT,
    impossibility     INTEGER NOT NULL,
    freedom           INTEGER NOT NULL,
    naturalness       INTEGER NOT NULL,
    surprise          INTEGER NOT NULL,
    willing_repeat    INTEGER,
    created_at        TEXT NOT NULL
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
            with contextlib.closing(self._connect()) as conn:
                with conn:  # transaction
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

    def save_survey(
        self,
        session_id: str,
        condition: str | None,
        answers: dict[str, Any],
        created_at: str,
    ) -> dict[str, Any]:
        """Store A/B survey answers. Submitting is the consent act
        (docs/human-trials.md §3). Re-submitting replaces the answers."""
        record = {
            "session_id": session_id,
            "condition": condition,
            "impossibility": answers["impossibility"],
            "freedom": answers["freedom"],
            "naturalness": answers["naturalness"],
            "surprise": answers["surprise"],
            "willing_repeat": answers.get("willing_repeat"),
            "created_at": created_at,
        }
        with self._lock:
            with contextlib.closing(self._connect()) as conn:
                with conn:  # transaction
                    conn.execute(
                        """
                        INSERT OR REPLACE INTO surveys
                        (session_id, condition, impossibility, freedom, naturalness,
                         surprise, willing_repeat, created_at)
                        VALUES (:session_id, :condition, :impossibility, :freedom,
                                 :naturalness, :surprise, :willing_repeat, :created_at)
                        """,
                        record,
                    )
                    row = conn.execute(
                        "SELECT * FROM surveys WHERE session_id = ?", (session_id,)
                    ).fetchone()
        return dict(row)

    def delete(self, session_id: str) -> bool:
        with self._lock:
            if not self._db_path.exists():
                return False
            with contextlib.closing(self._connect()) as conn:
                with conn:  # transaction
                    cursor_sess = conn.execute(
                        "DELETE FROM sessions WHERE session_id = ?", (session_id,)
                    )
                    # deletion control covers every trace, surveys included
                    cursor_surv = conn.execute(
                        "DELETE FROM surveys WHERE session_id = ?", (session_id,)
                    )
                deleted = (cursor_sess.rowcount > 0) or (cursor_surv.rowcount > 0)
        return deleted

    # -- read paths -------------------------------------------------------------

    def list_summaries(self) -> list[dict[str, Any]]:
        if not self._db_path.exists():
            return []
        with contextlib.closing(self._connect()) as conn:
            rows = conn.execute("SELECT * FROM sessions ORDER BY created_at DESC").fetchall()
        return [self._summary_from_row(row) for row in rows]

    def survey_rows(self) -> list[dict[str, Any]]:
        """Survey answers joined with their session outcome (consented records
        only) — the A/B analysis input (docs/human-trials.md §4)."""
        if not self._db_path.exists():
            return []
        with contextlib.closing(self._connect()) as conn:
            rows = conn.execute(
                """
                SELECT sv.session_id, sv.condition, sv.impossibility, sv.freedom,
                       sv.naturalness, sv.surprise, sv.willing_repeat, sv.created_at,
                       ses.effect_id, ses.correct, ses.turns_used
                FROM surveys sv
                LEFT JOIN sessions ses ON ses.session_id = sv.session_id
                ORDER BY sv.created_at DESC
                """
            ).fetchall()
        return [dict(row) for row in rows]

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
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        self._ensure_schema(conn)
        return conn

    def _ensure_schema(self, conn: sqlite3.Connection) -> None:
        """Idempotent migration to the current schema version. v1 dbs (and
        fresh files) gain the v2 survey table."""
        version = conn.execute("PRAGMA user_version").fetchone()[0]
        if version < SCHEMA_VERSION:
            with conn:  # transaction
                conn.executescript(_SCHEMA)
                conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")

    @staticmethod
    def _summary_from_row(row: sqlite3.Row) -> dict[str, Any]:
        summary = dict(row)
        summary.pop("events_json", None)  # history is retrievable per-session later
        return summary
