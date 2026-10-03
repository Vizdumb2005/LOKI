import { useEffect, useRef, useState } from "react";
import type { ObservationChannel, SessionView } from "../types";
import { useSensing } from "../hooks/useSensing";
import { MicRecorder } from "../perception/mic";
import { matchTranscript, targetsFromOptions } from "../perception/matcher";

interface SessionProps {
  session: SessionView;
  busy: boolean;
  archived: boolean;
  observationChannels: ObservationChannel[];
  onAnswer: (optionId: string, latencyMs?: number, utterance?: string) => void;
  onOutcome: (correct: boolean) => void;
  onArchive: () => void;
  onRestart: () => void;
  onObserve: (observation: {
    channel: string;
    question_id: string;
    answer_id: string;
    dwell_ms?: number;
  }) => void;
}

type VoiceState = "idle" | "loading" | "recording" | "transcribing";

export function Session({
  session,
  busy,
  archived,
  observationChannels,
  onAnswer,
  onOutcome,
  onArchive,
  onRestart,
  onObserve,
}: SessionProps) {
  const questionShownAt = useRef<number>(performance.now());
  const [sensingChoice, setSensingChoice] = useState<"undecided" | "declined">("undecided");
  const [sensingEnabled, setSensingEnabled] = useState(false);
  const [voiceState, setVoiceState] = useState<VoiceState>("idle");
  const [voiceProgress, setVoiceProgress] = useState(0);
  const [voiceFeedback, setVoiceFeedback] = useState<string | null>(null);
  const recorderRef = useRef<MicRecorder | null>(null);
  const recordStartRef = useRef(0);
  const transcriberReady = useRef(false);

  const gazeChannel = observationChannels.find((c) => c.id === "gaze_dwell");
  const sensing = useSensing({
    enabled: sensingEnabled,
    minDwellMs: gazeChannel?.min_dwell_ms ?? 400,
    questionId: session.question_id,
    onDwell: (answerId, dwellMs) => {
      if (session.question_id) {
        onObserve({
          channel: "gaze_dwell",
          question_id: session.question_id,
          answer_id: answerId,
          dwell_ms: dwellMs,
        });
      }
    },
  });

  // Reset per-session choices and camera when a new séance starts.
  useEffect(() => {
    setSensingChoice("undecided");
    setSensingEnabled(false);
    setVoiceState("idle");
    setVoiceFeedback(null);
  }, [session.session_id]);

  // The camera only exists while questions are on the table.
  useEffect(() => {
    if (session.phase !== "active" && sensing.state === "active") {
      sensing.stop();
    }
  }, [session.phase, sensing]);

  useEffect(() => {
    questionShownAt.current = performance.now();
  }, [session.question_id, session.phase]);

  useEffect(() => {
    if (session.phase !== "active" || busy) return;
    const handler = (event: KeyboardEvent) => {
      const index = Number.parseInt(event.key, 10) - 1;
      if (Number.isInteger(index) && index >= 0 && index < session.options.length) {
        onAnswer(session.options[index].id, performance.now() - questionShownAt.current);
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [session.phase, session.options, busy, onAnswer]);

  async function toggleVoice(): Promise<void> {
    if (voiceState === "loading" || voiceState === "transcribing") return;
    if (voiceState === "idle") {
      setVoiceFeedback(null);
      try {
        if (!transcriberReady.current) {
          setVoiceState("loading");
          // Whisper (+ Transformers.js) is heavy: lazy-load on first use.
          const asr = await import("../perception/asr");
          await asr.loadTranscriber((percent) => setVoiceProgress(percent));
          transcriberReady.current = true;
        }
        recorderRef.current = new MicRecorder();
        await recorderRef.current.start();
        recordStartRef.current = performance.now();
        setVoiceState("recording");
      } catch {
        setVoiceState("idle");
        setVoiceFeedback("The microphone stayed silent — permission was denied.");
      }
      return;
    }
    // recording → transcribe → match
    setVoiceState("transcribing");
    const pcm = await recorderRef.current!.stop();
    recorderRef.current = null;
    try {
      const asr = await import("../perception/asr");
      const transcript = await asr.transcribe(pcm);
      const result = matchTranscript(transcript, targetsFromOptions(session.options));
      if (result.status === "matched") {
        setVoiceState("idle");
        onAnswer(result.answerId, performance.now() - recordStartRef.current, transcript);
      } else {
        setVoiceState("idle");
        setVoiceFeedback(
          result.status === "ambiguous"
            ? `“${transcript}” — the spirits heard several answers at once. Name just one.`
            : `“${transcript}” — nothing clear in that. Say it again.`,
        );
      }
    } catch (e) {
      setVoiceState("idle");
      setVoiceFeedback(`The whispering failed — ${(e as Error).message}`);
    }
  }

  const { curtain } = session;
  const certaintyPct = Math.max(0, Math.min(1, session.certainty)) * 100;
  const showSensingOffer = gazeChannel != null && session.phase === "active" && sensing.state === "off";

  const history = curtain.entropy_history;
  const sparkPoints =
    history.length > 1
      ? history
          .map((point, i) => {
            const x = (i / (history.length - 1)) * 100;
            const y =
              40 -
              (point.entropy_bits / Math.max(curtain.initial_entropy_bits, 0.001)) * 40;
            return `${x.toFixed(2)},${Math.max(0, Math.min(40, y)).toFixed(2)}`;
          })
          .join(" ")
      : null;

  return (
    <section className="session">
      {/* Always mounted: start() needs this element to exist BEFORE the
          permission prompt appears, so it cannot be conditionally rendered. */}
      <div
        className={`sensing-live ${
          sensing.state === "requesting" || sensing.state === "active" ? "" : "sensing-hidden"
        }`}
      >
        <video ref={sensing.videoRef} className="sensing-video" playsInline muted />
        {sensing.state === "requesting" && (
          <span className="sensing-chip">awaiting the camera…</span>
        )}
        {sensing.state === "active" && (
          <>
            <span className="sensing-chip">
              <span className="pulse" aria-hidden="true" />
              {sensing.faceFound ? "eyes sensed — in your browser only" : "searching for a face…"}
            </span>
            <button className="sensing-stop" onClick={sensing.stop}>
              Stop
            </button>
          </>
        )}
      </div>

      <div className="session-meta">
        <span className="effect-name">{session.effect_title}</span>
        <span className="turn-counter">
          Question {session.turn} of {session.max_turns}
        </span>
      </div>

      <div className="meters">
        <div className="meter-row">
          <label>Certainty</label>
          <div className="meter">
            <div className="meter-fill" style={{ width: `${certaintyPct}%` }} />
          </div>
          <span className="meter-value">{certaintyPct.toFixed(0)}%</span>
        </div>
      </div>

      <blockquote className="message" aria-live="polite">
        {session.message}
      </blockquote>

      {session.phase === "active" && (
        <>
          {showSensingOffer && sensingChoice === "undecided" && (
            <div className="sensing-banner" role="note">
              <p>
                LOKI may watch your eyes while you choose — <strong>in your browser only</strong>.
                Frames never leave this machine; only “you lingered on an answer” events reach
                the server.
              </p>
              <div className="sensing-banner-actions">
                <button
                  className="option-btn"
                  disabled={busy}
                  onClick={() => {
                    setSensingEnabled(true);
                    void sensing.start();
                  }}
                >
                  Allow the spirits to see
                </button>
                <button className="option-btn subtle" onClick={() => setSensingChoice("declined")}>
                  Not now
                </button>
              </div>
            </div>
          )}
          {showSensingOffer && sensingChoice === "declined" && sensing.state === "off" && (
            <button
              className="sensing-reoffer"
              onClick={() => {
                setSensingEnabled(true);
                void sensing.start();
              }}
            >
              👁 enable eye sensing
            </button>
          )}
          {sensing.state === "denied" && (
            <p className="sensing-denied">
              The camera stayed dark — the séance continues word-only.{" "}
              <button className="sensing-reoffer" onClick={() => void sensing.start()}>
                Try again
              </button>
            </p>
          )}
          {sensing.state === "failed" && (
            <p className="sensing-denied">
              The seeing-stone failed to load (model or network) — the séance continues
              word-only.{" "}
              <button className="sensing-reoffer" onClick={() => void sensing.start()}>
                Try again
              </button>
            </p>
          )}

          <div className="options" data-options-container>
            {session.options.map((option, index) => (
              <button
                key={option.id}
                className="option-btn"
                data-answer-id={option.id}
                disabled={busy}
                onClick={() => onAnswer(option.id, performance.now() - questionShownAt.current)}
              >
                <span className="key-hint" aria-hidden="true">
                  {index + 1}
                </span>
                {option.label}
              </button>
            ))}
            {session.phase === "active" && (
              <button
                className="option-btn mic-btn"
                disabled={busy}
                onClick={() => void toggleVoice()}
              >
                {voiceState === "idle" && <span className="key-hint">🎙</span>}
                {voiceState === "idle" && "Speak your answer"}
                {voiceState === "loading" && `Summoning the whisperer… ${voiceProgress.toFixed(0)}%`}
                {voiceState === "recording" && "● Listening — click when done"}
                {voiceState === "transcribing" && "✨ Listening to the spirits…"}
              </button>
            )}
          </div>
          {voiceFeedback && <p className="voice-feedback">{voiceFeedback}</p>}
        </>
      )}

      {session.phase === "revealed" && session.prediction && (
        <div className="reveal">
          <p className="reveal-label">LOKI commits to</p>
          <p className="prediction">{session.prediction.label}</p>
          <p className="confidence">
            posterior confidence {(session.prediction.confidence * 100).toFixed(1)}%
          </p>
          <div className="outcome-buttons">
            <button className="option-btn correct" disabled={busy} onClick={() => onOutcome(true)}>
              The trickster saw true
            </button>
            <button className="option-btn wrong" disabled={busy} onClick={() => onOutcome(false)}>
              LOKI was wrong
            </button>
          </div>
        </div>
      )}

      {session.phase === "outcome" && (
        <div className="again">
          {archived ? (
            <span className="archived-note">Kept in the ledger — the fates remember.</span>
          ) : (
            <button className="option-btn subtle" disabled={busy} onClick={onArchive}>
              Keep this séance in the ledger
            </button>
          )}
          <button className="option-btn" disabled={busy} onClick={onRestart}>
            Return to the parlor
          </button>
        </div>
      )}

      <details className="curtain">
        <summary>Peek behind the curtain (research diagnostics)</summary>
        <div className="curtain-body">
          {sparkPoints && (
            <div className="sparkline-wrap">
              <span className="sparkline-label">the narrowing</span>
              <svg
                className="sparkline"
                viewBox="0 0 100 40"
                preserveAspectRatio="none"
                role="img"
                aria-label="Posterior entropy falling as questions are answered"
              >
                <polyline points={sparkPoints} fill="none" stroke="currentColor" strokeWidth="1.5" />
              </svg>
            </div>
          )}
          <div className="curtain-stats">
            <span>entropy: {curtain.entropy_bits.toFixed(3)} bits</span>
            <span>initial: {curtain.initial_entropy_bits.toFixed(3)} bits</span>
            <span>
              last question info gain:{" "}
              {curtain.last_info_gain_bits == null
                ? "—"
                : `${curtain.last_info_gain_bits.toFixed(3)} bits`}
            </span>
            {curtain.last_observation && (
              <span>
                last gaze: {curtain.last_observation.answer_label}{" "}
                {curtain.last_observation.dwell_ms != null
                  ? `for ${(curtain.last_observation.dwell_ms / 1000).toFixed(1)} s`
                  : ""}
              </span>
            )}
          </div>
          <table className="curtain-table">
            <thead>
              <tr>
                <th>leading hypotheses</th>
                <th>posterior</th>
              </tr>
            </thead>
            <tbody>
              {curtain.top.map((h) => (
                <tr key={h.hypothesis_id}>
                  <td>{h.label}</td>
                  <td className="prob-cell">
                    <div className="prob-bar">
                      <div
                        className="prob-fill"
                        style={{ width: `${(h.probability * 100).toFixed(1)}%` }}
                      />
                    </div>
                    <span>{(h.probability * 100).toFixed(1)}%</span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          <p className="curtain-note">
            LOKI's "magic" is a Bayesian posterior narrowing over an explicit
            hypothesis space. It keeps every rival hypothesis alive until the
            evidence — your answers, your gaze, your pauses — collapses the
            possibilities. Gaze is parlor-grade here: it credits the answer
            button nearest where your head and eyes point, not precision
            eye-tracking.
          </p>
        </div>
      </details>
    </section>
  );
}
