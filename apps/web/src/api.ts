import type {
  ArchivedSummary,
  EffectSummary,
  LedgerStats,
  SessionView,
  SurveyAnswers,
  TypingRhythm,
} from "./types";

async function handle<T>(res: Response): Promise<T> {
  if (!res.ok) {
    let detail = `${res.status} ${res.statusText}`;
    try {
      const body = (await res.json()) as { detail?: unknown };
      if (body?.detail) detail = String(body.detail);
    } catch {
      // non-JSON error body — keep the status-line detail
    }
    throw new Error(detail);
  }
  return (await res.json()) as T;
}

function post<T>(path: string, body: unknown): Promise<T> {
  return fetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  }).then((r) => handle<T>(r));
}

export const api = {
  effects: () => fetch("/api/effects").then((r) => handle<EffectSummary[]>(r)),
  createSession: (effectId: string) =>
    post<SessionView>("/api/sessions", { effect_id: effectId }),
  answer: (sessionId: string, answerId: string, latencyMs?: number, utterance?: string) =>
    post<SessionView>(`/api/sessions/${sessionId}/answer`, {
      answer_id: answerId,
      latency_ms: latencyMs,
      utterance: utterance,
    }),
  // Covert turns accept verbatim participant text; the server parses it into
  // an agreement strength. The text is recorded consent-gated like utterance.
  // Typing rhythm aggregates (never key content) ride along for fusion.
  answerFreeText: (
    sessionId: string,
    text: string,
    latencyMs?: number,
    rhythm?: TypingRhythm | null,
  ) =>
    post<SessionView>(`/api/sessions/${sessionId}/answer`, {
      answer_id: null,
      free_text: text,
      latency_ms: latencyMs,
      typing_rhythm: rhythm ?? null,
    }),
  observe: (
    sessionId: string,
    observation: { channel: string; question_id: string; answer_id: string; dwell_ms?: number },
  ) => post<SessionView>(`/api/sessions/${sessionId}/observations`, observation),
  outcome: (sessionId: string, correct: boolean) =>
    post<SessionView>(`/api/sessions/${sessionId}/outcome`, { correct }),
  // Submitting the survey is the consent act (docs/human-trials.md §3).
  survey: (sessionId: string, answers: SurveyAnswers) =>
    post<Record<string, unknown>>(`/api/sessions/${sessionId}/survey`, answers),
  archive: (sessionId: string) =>
    post<{ archived: boolean; summary: ArchivedSummary }>(
      `/api/sessions/${sessionId}/archive`,
      {},
    ),
  ledger: () => fetch("/api/archive").then((r) => handle<ArchivedSummary[]>(r)),
  stats: () => fetch("/api/stats").then((r) => handle<LedgerStats[]>(r)),
  removeArchived: (sessionId: string) =>
    fetch(`/api/archive/${sessionId}`, { method: "DELETE" }).then((r) => {
      if (!r.ok) throw new Error(`${r.status} ${r.statusText}`);
    }),
};
