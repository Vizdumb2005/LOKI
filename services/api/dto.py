"""API request/response DTOs. The view model exposes posterior internals through
the "curtain" — transparency as a product feature (plan §12: perceived
fairness/transparency)."""

from __future__ import annotations

from pydantic import BaseModel, Field


class ObservationChannelDTO(BaseModel):
    id: str
    min_dwell_ms: int


class EffectSummaryDTO(BaseModel):
    id: str
    title: str
    description: str
    hypothesis_count: int
    question_count: int
    observation_channels: list[ObservationChannelDTO] = Field(default_factory=list)


class CreateSessionRequest(BaseModel):
    effect_id: str


class AnswerRequest(BaseModel):
    answer_id: str
    latency_ms: float | None = Field(default=None, ge=0)
    utterance: str | None = Field(default=None, max_length=500)


class ObservationRequest(BaseModel):
    """Weak non-verbal evidence for the CURRENT question (schema v1.1)."""

    channel: str
    question_id: str
    answer_id: str
    dwell_ms: float | None = Field(default=None, ge=0)


class OutcomeRequest(BaseModel):
    correct: bool


class OptionDTO(BaseModel):
    id: str
    label: str
    voice: list[str] = Field(default_factory=list)


class CurtainHypothesisDTO(BaseModel):
    hypothesis_id: str
    label: str
    probability: float


class EntropyPointDTO(BaseModel):
    turn: int
    entropy_bits: float


class LastObservationDTO(BaseModel):
    channel: str
    answer_label: str
    dwell_ms: float | None


class CurtainDTO(BaseModel):
    entropy_bits: float
    initial_entropy_bits: float
    last_info_gain_bits: float | None
    top: list[CurtainHypothesisDTO]
    entropy_history: list[EntropyPointDTO] = Field(default_factory=list)
    last_observation: LastObservationDTO | None = None


class PredictionDTO(BaseModel):
    hypothesis_id: str
    label: str
    confidence: float


class SessionViewDTO(BaseModel):
    session_id: str
    effect_id: str
    effect_title: str
    phase: str
    turn: int
    max_turns: int
    question_id: str | None
    message: str
    options: list[OptionDTO]
    uncertainty_bits: float
    certainty: float
    curtain: CurtainDTO
    prediction: PredictionDTO | None


class TrajectoryDTO(BaseModel):
    session_id: str
    events: list[dict]


class ArchivedSessionSummaryDTO(BaseModel):
    session_id: str
    effect_id: str
    created_at: str
    turns_used: int
    prediction_label: str
    confidence: float
    correct: bool | None
    committed_because: str | None


class ArchiveResponseDTO(BaseModel):
    archived: bool
    summary: ArchivedSessionSummaryDTO


class EffectLedgerStatsDTO(BaseModel):
    effect_id: str
    archived: int
    with_outcome: int
    correct: int
    accuracy: float | None
    avg_turns: float | None
