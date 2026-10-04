import { useCallback, useEffect, useState } from "react";
import { api } from "./api";
import type {
  ArchivedSummary,
  EffectSummary,
  LedgerStats,
  SessionView,
  SurveyAnswers,
  TypingRhythm,
} from "./types";
import { Landing } from "./components/Landing";
import { Session } from "./components/Session";

export default function App() {
  const [effects, setEffects] = useState<EffectSummary[] | null>(null);
  const [session, setSession] = useState<SessionView | null>(null);
  const [archived, setArchived] = useState(false);
  const [ledgerStats, setLedgerStats] = useState<LedgerStats[]>([]);
  const [ledgerEntries, setLedgerEntries] = useState<ArchivedSummary[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const loadLedger = useCallback(() => {
    api.stats().then(setLedgerStats).catch(() => setLedgerStats([]));
    api.ledger().then(setLedgerEntries).catch(() => setLedgerEntries([]));
  }, []);

  useEffect(() => {
    api
      .effects()
      .then(setEffects)
      .catch((e: Error) => setError(e.message));
    loadLedger();
  }, [loadLedger]);

  const start = useCallback(async (effectId: string) => {
    setBusy(true);
    setError(null);
    setArchived(false);
    try {
      setSession(await api.createSession(effectId));
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }, []);

  const answer = useCallback(
    async (optionId: string, latencyMs?: number, utterance?: string) => {
      if (!session) return;
      setBusy(true);
      setError(null);
      try {
        setSession(await api.answer(session.session_id, optionId, latencyMs, utterance));
      } catch (e) {
        setError((e as Error).message);
      } finally {
        setBusy(false);
      }
    },
    [session],
  );

  const answerFreeText = useCallback(
    async (text: string, latencyMs?: number, rhythm?: TypingRhythm | null) => {
      if (!session) return;
      setBusy(true);
      setError(null);
      try {
        setSession(await api.answerFreeText(session.session_id, text, latencyMs, rhythm));
      } catch (e) {
        setError((e as Error).message);
      } finally {
        setBusy(false);
      }
    },
    [session],
  );

  const observe = useCallback(
    async (observation: {
      channel: string;
      question_id: string;
      answer_id: string;
      dwell_ms?: number;
    }) => {
      if (!session) return;
      try {
        // Sensing errors are non-fatal: the parlor continues word-only.
        setSession(await api.observe(session.session_id, observation));
      } catch {
        // ignore — e.g. the question advanced between dwell and send
      }
    },
    [session],
  );

  const reportOutcome = useCallback(
    async (correct: boolean) => {
      if (!session) return;
      setBusy(true);
      setError(null);
      try {
        setSession(await api.outcome(session.session_id, correct));
      } catch (e) {
        setError((e as Error).message);
      } finally {
        setBusy(false);
      }
    },
    [session],
  );

  const submitSurvey = useCallback(
    async (answers: SurveyAnswers) => {
      if (!session) return;
      try {
        await api.survey(session.session_id, answers);
      } catch (e) {
        setError((e as Error).message);
      }
    },
    [session],
  );

  const archive = useCallback(async () => {
    if (!session) return;
    setBusy(true);
    setError(null);
    try {
      await api.archive(session.session_id);
      setArchived(true);
      loadLedger();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }, [session, loadLedger]);

  const removeArchived = useCallback(
    async (sessionId: string) => {
      try {
        await api.removeArchived(sessionId);
        loadLedger();
      } catch (e) {
        setError((e as Error).message);
      }
    },
    [loadLedger],
  );

  const restart = useCallback(() => {
    setSession(null);
    setArchived(false);
    setError(null);
  }, []);

  return (
    <div className="app">
      <header className="app-header">
        <h1 className="wordmark">L O K I</h1>
        <p className="tagline">digital mentalist — every trick is inference in disguise</p>
      </header>

      <main>
        {error && (
          <div className="error" role="alert">
            {error} — is the API running?{" "}
            <code>uvicorn services.api.main:app --port 8000</code>
          </div>
        )}
        {session ? (
          <Session
            session={session}
            busy={busy}
            archived={archived}
            observationChannels={
              effects?.find((e) => e.id === session.effect_id)?.observation_channels ?? []
            }
            onAnswer={answer}
            onFreeText={answerFreeText}
            onSurvey={submitSurvey}
            onOutcome={reportOutcome}
            onArchive={archive}
            onRestart={restart}
            onObserve={observe}
          />
        ) : (
          <Landing
            effects={effects}
            ledgerStats={ledgerStats}
            ledgerEntries={ledgerEntries}
            busy={busy}
            onStart={start}
            onDeleteArchived={removeArchived}
          />
        )}
      </main>

      <footer className="app-footer">
        <p>
          Camera and microphone are opt-in, session-scoped, and processed entirely in
          your browser — frames and audio never leave this machine. Gameplay writes
          nothing anywhere: a séance is only kept in the ledger if you say so, and you
          can delete it whenever you like.
        </p>
      </footer>
    </div>
  );
}
