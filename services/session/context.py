"""SessionSnapshot: one coherent read-view folded from structured events.

``reduce(snapshot, event)`` is pure; ``replay(events)`` folds a full session.
``snapshot_from_session`` builds the same view live for cross-checking.
Full-posterior replay is NOT claimed: events carry top-k/entropy, not likelihood
vectors (ponytail: enrich the schema only when a consumer needs it).
"""

from __future__ import annotations

from dataclasses import dataclass, replace

from services.effects.events import Event, EventType

# Hesitation is read off discounts the engine already recorded: a direct answer
# whose reliability was discounted, or a covert reply downgraded toward unclear.
HESITANT_STYLE_RATE = 0.30


@dataclass(frozen=True)
class SessionSnapshot:
    phase: str = "active"
    turn: int = 0
    entropy_bits: float = 0.0
    initial_entropy_bits: float = 0.0
    confidence: float = 0.0
    top: tuple[tuple[str, float], ...] = ()
    hypothesis_count: int = 0
    responses: int = 0
    hesitations: int = 0
    latencies_ms: tuple[float, ...] = ()
    covert_yes: int = 0
    covert_total: int = 0
    modes: tuple[str, ...] = ()
    max_turns: int = 0
    committed_because: str | None = None
    prediction_id: str | None = None

    @property
    def mystery(self) -> float:
        """Remaining uncertainty share: 1 at session start → ~0 at commit."""
        if self.initial_entropy_bits <= 0:
            return 0.0
        return max(0.0, self.entropy_bits / self.initial_entropy_bits)

    @property
    def interrogation_cost(self) -> float:
        """Turn-budget share consumed."""
        if self.max_turns <= 0:
            return 0.0
        return min(1.0, self.turn / self.max_turns)

    @property
    def tension(self) -> float:
        """Dramatic pressure: spent budget × earned confidence."""
        return self.interrogation_cost * self.confidence

    @property
    def response_style(self) -> str:
        if self.responses == 0:
            return "unknown"
        rate = self.hesitations / self.responses
        if rate == 0:
            return "decisive"
        return "steady" if rate <= HESITANT_STYLE_RATE else "hesitant"

    @property
    def median_latency_ms(self) -> float | None:
        if not self.latencies_ms:
            return None
        ordered = sorted(self.latencies_ms)
        mid = len(ordered) // 2
        return ordered[mid] if len(ordered) % 2 else (ordered[mid - 1] + ordered[mid]) / 2

    def to_dict(self) -> dict:
        return {
            "inference": {
                "entropy": round(self.entropy_bits, 4),
                "confidence": round(self.confidence, 4),
                "top_candidates": [[h, round(p, 4)] for h, p in self.top],
            },
            "participant": {
                "hesitation": (
                    round(self.hesitations / self.responses, 4) if self.responses else 0.0
                ),
                "response_style": self.response_style,
                "median_latency_ms": self.median_latency_ms,
            },
            "interaction": {
                "turn": self.turn,
                "interrogation_cost": round(self.interrogation_cost, 4),
                "modes": list(self.modes),
            },
            "performance": {
                "tension": round(self.tension, 4),
                "mystery": round(self.mystery, 4),
                "reveal_readiness": round(self.confidence, 4),
                "phase": self.phase,
            },
        }


def reduce(snapshot: SessionSnapshot, event: Event, *, max_turns: int = 0) -> SessionSnapshot:
    """Pure fold of one event into the snapshot."""
    p = event.payload
    if event.type is EventType.SESSION_STARTED:
        return replace(
            snapshot,
            initial_entropy_bits=p.get("initial_entropy_bits", 0.0),
            entropy_bits=p.get("initial_entropy_bits", 0.0),
            hypothesis_count=p.get("hypothesis_count", 0),
            max_turns=max_turns or snapshot.max_turns,
        )
    if event.type is EventType.POLICY_DECISION:
        mode = p.get("mode", "direct")
        modes = snapshot.modes if mode in snapshot.modes else (*snapshot.modes, mode)
        return replace(snapshot, turn=snapshot.turn + 1, modes=modes)
    if event.type is EventType.HYPOTHESIS_UPDATED:
        latencies = snapshot.latencies_ms
        if p.get("latency_ms") is not None:
            latencies = (*latencies, float(p["latency_ms"]))
        hesitant = p.get("reliability_effective") is not None or (
            p.get("agreement_strength_effective") is not None
        )
        covert = p.get("mode") == "covert"
        yes = p.get("agreement_strength") in ("strong_yes", "lean_yes")
        if "top_hypothesis_id" in p:
            top: tuple[tuple[str, float], ...] = ((p["top_hypothesis_id"], p["top_probability"]),)
        else:
            top = snapshot.top
        return replace(
            snapshot,
            entropy_bits=p.get("entropy_after", snapshot.entropy_bits),
            confidence=p.get("top_probability", snapshot.confidence),
            top=top,
            responses=snapshot.responses + 1,
            hesitations=snapshot.hesitations + (1 if hesitant else 0),
            latencies_ms=latencies,
            covert_yes=snapshot.covert_yes + (1 if covert and yes else 0),
            covert_total=snapshot.covert_total + (1 if covert else 0),
        )
    if event.type is EventType.OBSERVATION_RECORDED:
        return replace(
            snapshot,
            entropy_bits=p.get("entropy_after", snapshot.entropy_bits),
            confidence=p.get("top_probability", snapshot.confidence),
        )
    if event.type is EventType.EFFECT_REVEALED:
        return replace(
            snapshot,
            phase="revealed",
            confidence=p.get("confidence", snapshot.confidence),
            committed_because=p.get("committed_because"),
            prediction_id=p.get("prediction_id"),
        )
    if event.type is EventType.PARTICIPANT_OUTCOME:
        return replace(snapshot, phase="outcome")
    return snapshot  # pragma: no cover - unknown future event types pass through


def replay(events: list[Event], *, max_turns: int = 0) -> list[SessionSnapshot]:
    """Fold a full event history into per-event snapshots. Events only."""
    snapshots: list[SessionSnapshot] = []
    current = SessionSnapshot(max_turns=max_turns)
    for event in events:
        current = reduce(current, event)
        snapshots.append(current)
    return snapshots


def snapshot_from_session(session) -> SessionSnapshot:
    """Live view of an EffectSession — same shape as the replayed final state."""
    top_id, top_p = session.tracker.map_hypothesis()
    latencies = [
        e.payload["latency_ms"]
        for e in session.history
        if e.type is EventType.HYPOTHESIS_UPDATED and e.payload.get("latency_ms") is not None
    ]
    updates = [e for e in session.history if e.type is EventType.HYPOTHESIS_UPDATED]
    hesitant = sum(
        1
        for e in updates
        if e.payload.get("reliability_effective") is not None
        or e.payload.get("agreement_strength_effective") is not None
    )
    covert = [e for e in updates if e.payload.get("mode") == "covert"]
    return SessionSnapshot(
        phase=session.phase.value,
        turn=session.turn,
        entropy_bits=session.tracker.entropy(),
        initial_entropy_bits=session.initial_entropy,
        confidence=top_p,
        top=((top_id, top_p),),
        hypothesis_count=len(session.effect.hypotheses),
        responses=len(updates),
        hesitations=hesitant,
        latencies_ms=tuple(float(v) for v in latencies),
        covert_yes=sum(
            1 for e in covert if e.payload.get("agreement_strength") in ("strong_yes", "lean_yes")
        ),
        covert_total=len(covert),
        modes=tuple(
            dict.fromkeys(
                e.payload.get("mode", "direct")
                for e in session.history
                if e.type is EventType.POLICY_DECISION
            )
        ),
        max_turns=session.effect.termination.max_turns,
        committed_because=session.committed_because.value if session.committed_because else None,
        prediction_id=session.prediction.hypothesis_id if session.prediction else None,
    )


#: Fields the event-fold reproduces exactly (``top`` keeps only the winner; the
#: live view's full top-k is intentionally richer than the replayed trail).
REPLAY_PARITY_FIELDS = (
    "phase",
    "turn",
    "responses",
    "hesitations",
    "covert_total",
    "committed_because",
    "prediction_id",
)
