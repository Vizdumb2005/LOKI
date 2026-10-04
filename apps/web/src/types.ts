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

export type TurnMode = "direct" | "covert";

export interface RevealStage {
  kind: "attribute" | "category" | "deduction" | "hesitation";
  text: string;
}

// Aggregate typing telemetry (ROADMAP Phase 5) — never key content.
export interface TypingRhythm {
  first_key_ms: number;
  median_interval_ms: number;
  total_ms: number;
}

export interface SessionView {
  session_id: string;
  effect_id: string;
  effect_title: string;
  phase: Phase;
  turn: number;
  max_turns: number;
  question_id: string | null;
  // Schema v1.2: "direct" renders question + options; "covert" renders an
  // assertion of asserted_label + the agreement scale (in options).
  mode: TurnMode;
  asserted_label: string | null;
  // Schema v1.4: choice-architecture emphasis on direct turns — the option
  // the UI renders salient. Presentation only; disclosed in the curtain.
  salient_option_id: string | null;
  // Schema v1.3: the multiple-outs reveal staging — beats delivered before
  // the final banded line (message).
  reveal_path: string | null;
  reveal_stages: RevealStage[];
  // ROADMAP Phase 6: the A/B condition ("a" | "b") — data for the analysis,
  // never displayed by the frontend.
  condition: string | null;
  message: string;
  options: Option[];
  uncertainty_bits: number;
  certainty: number;
  curtain: Curtain;
  prediction: Prediction | null;
}

// The §4 Likert instrument (docs/human-trials.md §3) — submitting is consent.
export interface SurveyAnswers {
  impossibility: number;
  freedom: number;
  naturalness: number;
  surprise: number;
  willing_repeat: boolean | null;
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
