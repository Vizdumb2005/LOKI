"""In-memory session store. Sessions die with the process by design (privacy,
plan §11): nothing about a participant outlives the server."""

from __future__ import annotations

import threading

from services.effects.engine import EffectSession


class SessionStore:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._sessions: dict[str, EffectSession] = {}

    def add(self, session: EffectSession) -> None:
        with self._lock:
            self._sessions[session.session_id] = session

    def get(self, session_id: str) -> EffectSession:
        with self._lock:
            try:
                return self._sessions[session_id]
            except KeyError:
                raise KeyError(session_id) from None
