// Mirrors services/api/dto.py — keep in sync when the API view model changes.

export interface ObservationChannel {
  id: string;
  min_dwell_ms: number;
}

export interface EffectSummary {
  id: string;
  title: string;
  description: string;
  hypothesis_count: number;
  question_count: number;
  observation_channels: ObservationChannel[];
}

export interface Option {
  id: string;
  label: string;
  voice: string[];
}

export interface CurtainHypothesis {
  hypothesis_id: string;
  label: string;
  probability: number;
}

export interface EntropyPoint {
  turn: number;
  entropy_bits: number;
}

export interface LastObservation {
  channel: string;
  answer_label: string;
  dwell_ms: number | null;
}

export interface Curtain {
  entropy_bits: number;
  initial_entropy_bits: number;
  last_info_gain_bits: number | null;
  top: CurtainHypothesis[];
  entropy_history: EntropyPoint[];
  last_observation: LastObservation | null;
}

export interface Prediction {
  hypothesis_id: string;
  label: string;
  confidence: number;
}

export type Phase = "active" | "revealed" | "outcome";

export interface SessionView {
  session_id: string;
  effect_id: string;
  effect_title: string;
  phase: Phase;
  turn: number;
  max_turns: number;
  question_id: string | null;
  message: string;
  options: Option[];
  uncertainty_bits: number;
  certainty: number;
  curtain: Curtain;
  prediction: Prediction | null;
}

export interface ArchivedSummary {
  session_id: string;
  effect_id: string;
  created_at: string;
  turns_used: number;
  prediction_label: string;
  confidence: number;
  correct: boolean | null;
  committed_because: string | null;
}

export interface LedgerStats {
  effect_id: string;
  archived: number;
  with_outcome: number;
  correct: number;
  accuracy: number | null;
  avg_turns: number | null;
}
