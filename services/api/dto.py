"""API request/response DTOs. The view model exposes posterior internals through
the "curtain" — transparency as a product feature (plan §12: perceived
fairness/transparency)."""

from __future__ import annotations

from typing import Literal

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
    # A/B condition (docs/human-trials.md): "a" (Akinator baseline) or "b"
    # (performance engine). None → the server assigns uniformly at random;
    # the condition travels as data and the frontend never displays it.
    condition: Literal["a", "b"] | None = None


class SurveyRequest(BaseModel):
    """The §4 Likert instrument (1–7) — submitting is the consent act
    (docs/human-trials.md §3)."""

    impossibility: int = Field(ge=1, le=7)
    freedom: int = Field(ge=1, le=7)
    naturalness: int = Field(ge=1, le=7)
    surprise: int = Field(ge=1, le=7)
    willing_repeat: bool | None = None


class TypingRhythmDTO(BaseModel):
    """Aggregate typing-telemetry numbers (ROADMAP Phase 5,
    docs/passive-signals.md §2) — never key content, never raw timing
    sequences; rides the free_text event under its consent semantics."""

    first_key_ms: float = Field(ge=0)
    median_interval_ms: float = Field(ge=0)
    total_ms: float = Field(ge=0)


class AnswerRequest(BaseModel):
    """A turn response. Direct turns carry ``answer_id`` (option id); covert
    turns carry either an agreement strength as ``answer_id`` or verbatim
    participant text as ``free_text`` (parsed server-side, consent-gated
    recording like ``utterance``) — docs/covert-fishing.md."""

    answer_id: str | None = None
    latency_ms: float | None = Field(default=None, ge=0)
    utterance: str | None = Field(default=None, max_length=500)
    free_text: str | None = Field(default=None, max_length=200)
    typing_rhythm: TypingRhythmDTO | None = None


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


class RevealStageDTO(BaseModel):
    """One staged beat before the banded reveal message (ROADMAP Phase 3)."""

    kind: str  # "attribute" | "category" | "deduction" | "hesitation"
    text: str


class SessionViewDTO(BaseModel):
    session_id: str
    effect_id: str
    effect_title: str
    phase: str
    turn: int
    max_turns: int
    question_id: str | None
    # Schema v1.2: "direct" (question + options) or "covert" (assertion +
    # agreement scale); asserted_label names the asserted option on covert turns.
    mode: str = "direct"
    asserted_label: str | None = None
    # Schema v1.4: choice-architecture emphasis on direct turns — the option
    # the UI should make salient (docs/choice-architecture.md). Disclosure
    # lives in the curtain; the click remains a plain Bayesian answer.
    salient_option_id: str | None = None
    # Schema v1.3: the multiple-outs reveal staging (empty on plain reveals).
    reveal_path: str | None = None
    reveal_stages: list[RevealStageDTO] = Field(default_factory=list)
    # ROADMAP Phase 6: the A/B condition ("a" | "b") — data for the analysis,
    # never displayed by the frontend.
    condition: str | None = None
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
