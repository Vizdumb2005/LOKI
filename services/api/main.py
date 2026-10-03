"""FastAPI application factory for LOKI (Phase 1 surface).

Run: uvicorn services.api.main:app --reload --port 8000

Privacy model (plan §11): gameplay writes nothing anywhere. The only write
path is the explicit archive call, and every archived record can be deleted.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware

from services.api.archive import SessionArchive
from services.api.dto import (
    AnswerRequest,
    ArchivedSessionSummaryDTO,
    ArchiveResponseDTO,
    CreateSessionRequest,
    CurtainDTO,
    CurtainHypothesisDTO,
    EffectLedgerStatsDTO,
    EffectSummaryDTO,
    EntropyPointDTO,
    LastObservationDTO,
    ObservationChannelDTO,
    ObservationRequest,
    OptionDTO,
    OutcomeRequest,
    PredictionDTO,
    SessionViewDTO,
    TrajectoryDTO,
)
from services.api.store import SessionStore
from services.effects.engine import EffectSession, InvalidStateError, Phase
from services.effects.loader import load_effects
from services.language.renderer import LanguageRenderer

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_EFFECTS_DIR = REPO_ROOT / "configs" / "effects"
DEFAULT_DB_PATH = REPO_ROOT / "data" / "sessions.db"

# Vite dev server origins; the dev proxy makes these unnecessary, but the
# production build may be served from a different port during testing.
ALLOWED_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]


def create_app(effects_dir: Path | None = None, db_path: Path | None = None) -> FastAPI:
    registry = load_effects(effects_dir or DEFAULT_EFFECTS_DIR)
    renderer = LanguageRenderer()
    store = SessionStore()
    archive = SessionArchive(db_path or DEFAULT_DB_PATH)

    app = FastAPI(title="LOKI API", version="0.1.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=ALLOWED_ORIGINS,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    def _session_or_404(session_id: str) -> EffectSession:
        try:
            return store.get(session_id)
        except KeyError:
            raise HTTPException(status_code=404, detail="session not found") from None

    def _view(session: EffectSession) -> SessionViewDTO:
        entropy_bits = session.tracker.entropy()
        initial = session.initial_entropy
        top = [
            CurtainHypothesisDTO(
                hypothesis_id=hid,
                label=session.effect.hypothesis_label(hid),
                probability=p,
            )
            for hid, p in session.tracker.top_k(5)
        ]
        entropy_history = [
            EntropyPointDTO(turn=i + 1, entropy_bits=event.payload["entropy_after"])
            for i, event in enumerate(
                e for e in session.history if e.type.value == "hypothesis.updated"
            )
        ]
        last_observation = next(
            (e for e in reversed(session.history) if e.type.value == "observation.recorded"),
            None,
        )
        if session.phase is Phase.ACTIVE:
            message = session.ask_message
            options = [
                OptionDTO(id=a.id, label=a.label, voice=a.voice)
                for a in (session.current_question.answers if session.current_question else [])
            ]
        elif session.phase is Phase.REVEALED:
            message = session.reveal_message
            options = []
        else:
            message = session.outcome_message
            options = []
        return SessionViewDTO(
            session_id=session.session_id,
            effect_id=session.effect.id,
            effect_title=session.effect.title,
            phase=session.phase.value,
            turn=session.turn,
            max_turns=session.effect.termination.max_turns,
            question_id=session.current_question.id if session.current_question else None,
            message=message,
            options=options,
            uncertainty_bits=entropy_bits,
            certainty=(1.0 - entropy_bits / initial) if initial > 0 else 1.0,
            curtain=CurtainDTO(
                entropy_bits=entropy_bits,
                initial_entropy_bits=initial,
                last_info_gain_bits=session.last_info_gain,
                top=top,
                entropy_history=entropy_history,
                last_observation=(
                    LastObservationDTO(
                        channel=last_observation.payload["channel"],
                        answer_label=last_observation.payload["answer_label"],
                        dwell_ms=last_observation.payload["dwell_ms"],
                    )
                    if last_observation
                    else None
                ),
            ),
            prediction=(
                PredictionDTO(
                    hypothesis_id=session.prediction.hypothesis_id,
                    label=session.prediction.label,
                    confidence=session.prediction.confidence,
                )
                if session.prediction
                else None
            ),
        )

    @app.get("/api/health")
    def health() -> dict:
        return {"status": "ok", "effects": len(registry)}

    @app.get("/api/effects")
    def list_effects() -> list[EffectSummaryDTO]:
        return [
            EffectSummaryDTO(
                id=e.id,
                title=e.title,
                description=e.description.strip(),
                hypothesis_count=len(e.hypotheses),
                question_count=len(e.questions),
                observation_channels=[
                    ObservationChannelDTO(id=channel_id, min_dwell_ms=channel.min_dwell_ms)
                    for channel_id, channel in e.observations.items()
                ],
            )
            for e in registry.values()
        ]

    @app.post("/api/sessions", status_code=201)
    def create_session(request: CreateSessionRequest) -> SessionViewDTO:
        effect = registry.get(request.effect_id)
        if effect is None:
            raise HTTPException(status_code=404, detail=f"unknown effect '{request.effect_id}'")
        session = EffectSession(effect, renderer)
        store.add(session)
        return _view(session)

    @app.get("/api/sessions/{session_id}")
    def get_session(session_id: str) -> SessionViewDTO:
        return _view(_session_or_404(session_id))

    @app.get("/api/sessions/{session_id}/trajectory")
    def get_trajectory(session_id: str) -> TrajectoryDTO:
        session = _session_or_404(session_id)
        return TrajectoryDTO(
            session_id=session_id,
            events=[event.model_dump() for event in session.history],
        )

    @app.post("/api/sessions/{session_id}/answer")
    def answer(session_id: str, request: AnswerRequest) -> SessionViewDTO:
        session = _session_or_404(session_id)
        try:
            session.answer(
                request.answer_id,
                latency_ms=request.latency_ms,
                utterance=request.utterance,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from None
        except InvalidStateError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from None
        return _view(session)

    @app.post("/api/sessions/{session_id}/observations")
    def observe(session_id: str, request: ObservationRequest) -> SessionViewDTO:
        session = _session_or_404(session_id)
        try:
            session.observe(
                request.question_id,
                request.answer_id,
                request.channel,
                dwell_ms=request.dwell_ms,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from None
        except InvalidStateError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from None
        return _view(session)

    @app.post("/api/sessions/{session_id}/outcome")
    def report_outcome(session_id: str, request: OutcomeRequest) -> SessionViewDTO:
        session = _session_or_404(session_id)
        try:
            session.report_outcome(request.correct)
        except InvalidStateError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from None
        return _view(session)

    @app.post("/api/sessions/{session_id}/archive")
    def archive_session(session_id: str) -> ArchiveResponseDTO:
        session = _session_or_404(session_id)
        if session.phase is not Phase.OUTCOME:
            raise HTTPException(
                status_code=409,
                detail="a séance can only be archived after the outcome is reported",
            )
        summary = archive.save(session)
        return ArchiveResponseDTO(archived=True, summary=ArchivedSessionSummaryDTO(**summary))

    @app.get("/api/archive")
    def list_archive() -> list[ArchivedSessionSummaryDTO]:
        return [ArchivedSessionSummaryDTO(**s) for s in archive.list_summaries()]

    @app.delete("/api/archive/{session_id}", status_code=204)
    def delete_archived(session_id: str) -> Response:
        if not archive.delete(session_id):
            raise HTTPException(status_code=404, detail="no archived session with that id")
        return Response(status_code=204)

    @app.get("/api/stats")
    def ledger_stats() -> list[EffectLedgerStatsDTO]:
        rows = []
        for row in archive.stats():
            with_outcome = row["with_outcome"] or 0
            correct = row["correct"] or 0
            rows.append(
                EffectLedgerStatsDTO(
                    effect_id=row["effect_id"],
                    archived=row["archived"],
                    with_outcome=with_outcome,
                    correct=correct,
                    accuracy=(correct / with_outcome) if with_outcome else None,
                    avg_turns=row["avg_turns"],
                )
            )
        return rows

    return app


app = create_app()
