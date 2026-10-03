"""Session event envelope (docs/spec/event-schema.md).

Events are append-only records of everything that happens in a session. They
carry structured payloads only — no raw media, no free-form prose. Phase 1
appends them to the in-memory session history; the transport/bus arrives with
the Phase 2+ capture services. Kept dependency-free so any component can emit.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


class EventType(str, Enum):
    SESSION_STARTED = "session.started"
    POLICY_DECISION = "policy.decision"
    HYPOTHESIS_UPDATED = "hypothesis.updated"
    OBSERVATION_RECORDED = "observation.recorded"
    EFFECT_REVEALED = "effect.revealed"
    PARTICIPANT_OUTCOME = "participant.outcome"


class Event(BaseModel):
    event_id: str = Field(default_factory=lambda: str(uuid4()))
    session_id: str
    ts: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    type: EventType
    payload: dict[str, Any]
    schema_version: int = 1
