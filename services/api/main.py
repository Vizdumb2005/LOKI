"""FastAPI application factory for LOKI (Phase 1 surface).

Run: uvicorn services.api.main:app --reload --port 8000

Privacy model (plan §11): gameplay writes nothing anywhere. The only write
path is the explicit archive call, and every archived record can be deleted.
"""

from __future__ import annotations

import random
from datetime import datetime, timezone
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
    RevealStageDTO,
    SessionViewDTO,
    SurveyRequest,
    TrajectoryDTO,
)
from services.api.store import SessionStore
from services.effects.engine import EffectSession, InvalidStateError, Phase
from services.effects.loader import load_effects
from services.language.renderer import LanguageRenderer
from services.language.response_signals import parse_agreement

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_EFFECTS_DIR = REPO_ROOT / "configs" / "effects"
DEFAULT_DB_PATH = REPO_ROOT / "data" / "sessions.db"

# Vite dev server origins; the dev proxy makes these unnecessary, but the
# production build may be served from a different port during testing.
ALLOWED_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]

# The fixed covert-turn response scale (docs/covert-fishing.md). Sent as the
# option list of a covert turn so the frontend renders it like any other
# turn; ids are AgreementStrength values.
AGREEMENT_OPTIONS = [
    OptionDTO(id="strong_yes", label="Yes, exactly", voice=[]),
    OptionDTO(id="lean_yes", label="Sort of…", voice=[]),
    OptionDTO(id="lean_no", label="Not really", voice=[]),
]


def _session_or_404(store: SessionStore, session_id: str) -> EffectSession:
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
        if session.current_mode == "covert":
            options = AGREEMENT_OPTIONS
        else:
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
    reveal_stages = (
        [RevealStageDTO(kind=kind, text=text) for kind, text in session.reveal_stage_messages]
        if session.phase is Phase.REVEALED
        else []
    )
    return SessionViewDTO(
        session_id=session.session_id,
        effect_id=session.effect.id,
        effect_title=session.effect.title,
        phase=session.phase.value,
        turn=session.turn,
        max_turns=session.effect.termination.max_turns,
        question_id=session.current_question.id if session.current_question else None,
        mode=session.current_mode,
        asserted_label=session.asserted_label,
        condition=session.condition,
        salient_option_id=(session.current_force_target if session.phase is Phase.ACTIVE else None),
        reveal_path=session.reveal_plan.path if session.reveal_plan else None,
        reveal_stages=reveal_stages,
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
        # A/B assignment (docs/human-trials.md §1): condition A is the same
        # engine with the performance layer off; B is the default.
        condition = request.condition or ("a" if random.random() < 0.5 else "b")
        if condition == "a":
            session = EffectSession(
                effect.without_fishing(), renderer, performance=False, condition="a"
            )
        else:
            session = EffectSession(effect, renderer, condition="b")
        store.add(session)
        return _view(session)

    @app.post("/api/sessions/{session_id}/survey", status_code=201)
    def submit_survey(session_id: str, request: SurveyRequest) -> dict:
        session = _session_or_404(store, session_id)
        if session.phase is not Phase.OUTCOME:
            raise HTTPException(
                status_code=409, detail="the survey opens after the outcome is reported"
            )
        # Submitting is the consent act — the only write path for survey data
        # (docs/human-trials.md §3).
        return archive.save_survey(
            session_id,
            session.condition,
            {
                "impossibility": request.impossibility,
                "freedom": request.freedom,
                "naturalness": request.naturalness,
                "surprise": request.surprise,
                "willing_repeat": request.willing_repeat,
            },
            created_at=datetime.now(timezone.utc).isoformat(),
        )

    @app.get("/api/sessions/{session_id}")
    def get_session(session_id: str) -> SessionViewDTO:
        return _view(_session_or_404(store, session_id))

    @app.get("/api/sessions/{session_id}/trajectory")
    def get_trajectory(session_id: str) -> TrajectoryDTO:
        session = _session_or_404(store, session_id)
        return TrajectoryDTO(
            session_id=session_id,
            events=[event.model_dump() for event in session.history],
        )

    @app.post("/api/sessions/{session_id}/answer")
    def answer(session_id: str, request: AnswerRequest) -> SessionViewDTO:
        session = _session_or_404(store, session_id)
        try:
            if request.free_text is not None:
                if session.phase is not Phase.ACTIVE or session.current_mode != "covert":
                    raise HTTPException(
                        status_code=400,
                        detail="free_text responses apply only to an active covert turn",
                    )
                signal = parse_agreement(request.free_text)
                session.respond_agreement(
                    signal.strength.value,
                    latency_ms=request.latency_ms,
                    utterance=request.free_text,
                    typing_rhythm=(
                        request.typing_rhythm.model_dump()
                        if request.typing_rhythm is not None
                        else None
                    ),
                )
            else:
                if request.typing_rhythm is not None:
                    raise HTTPException(
                        status_code=400,
                        detail="typing_rhythm applies only to free_text replies",
                    )
                if request.answer_id is None:
                    raise HTTPException(status_code=400, detail="provide answer_id or free_text")
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
        session = _session_or_404(store, session_id)
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
        session = _session_or_404(store, session_id)
        try:
            session.report_outcome(request.correct)
        except InvalidStateError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from None
        return _view(session)

    @app.post("/api/sessions/{session_id}/archive")
    def archive_session(session_id: str) -> ArchiveResponseDTO:
        session = _session_or_404(store, session_id)
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
