import { useEffect, useRef, useState, type FormEvent } from "react";
import type { ObservationChannel, SessionView, TypingRhythm } from "../types";
import { useSensing } from "../hooks/useSensing";
import { MicRecorder } from "../perception/mic";
import { matchTranscript, targetsFromOptions } from "../perception/matcher";
import { orderWithSalient, salientOf } from "../lib/forcing";
import { createRhythmTracker, type RhythmTracker } from "../lib/telemetry";
import type { SurveyAnswers } from "../types";

interface SessionProps {
  session: SessionView;
  busy: boolean;
  archived: boolean;
  observationChannels: ObservationChannel[];
  onAnswer: (optionId: string, latencyMs?: number, utterance?: string) => void;
  onFreeText: (text: string, latencyMs?: number, rhythm?: TypingRhythm | null) => void;
  onSurvey: (answers: SurveyAnswers) => void;
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
  onFreeText,
  onSurvey,
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
  const [freeText, setFreeText] = useState("");
  const [stagesShown, setStagesShown] = useState(0);
  const [survey, setSurvey] = useState<SurveyAnswers | null>(null);
  const [surveySent, setSurveySent] = useState(false);
  const recorderRef = useRef<MicRecorder | null>(null);
  const rhythmRef = useRef<RhythmTracker | null>(null);
  const recordStartRef = useRef(0);
  const transcriberReady = useRef(false);

  const gazeChannel = observationChannels.find((c) => c.id === "gaze_dwell");
  // Choice-architecture primitives (ROADMAP Phase 4): default positioning
  // and saliency on the posterior-favored option. The click remains a plain
  // answer; the curtain discloses the steering.
  const orderedOptions = orderWithSalient(session.options, session.salient_option_id);
  const salientOption = salientOf(session.options, session.salient_option_id);
  const sensing = useSensing({
    enabled: sensingEnabled,
    minDwellMs: gazeChannel?.min_dwell_ms ?? 400,
    questionId: session.question_id,
    onDwell: (answerId, dwellMs) => {
      // Gaze applies to direct turns only: a covert turn shows agreement
      // reactions, not answer options to dwell on.
      if (session.mode === "direct" && session.question_id) {
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
    setFreeText("");
  }, [session.session_id]);

  useEffect(() => {
    setFreeText("");
    // fresh typing-rhythm tracker per turn (ROADMAP Phase 5)
    rhythmRef.current = createRhythmTracker();
  }, [session.question_id, session.turn]);

  // Theatrical pacing (ROADMAP Phase 3): reveal beats land one at a time;
  // the banded identity line and the prediction panel follow the last beat.
  const revealStages = session.reveal_stages;
  useEffect(() => {
    if (session.phase !== "revealed") {
      setStagesShown(0);
      return;
    }
    setStagesShown(0);
    if (revealStages.length === 0) return;
    const timer = window.setInterval(() => {
      setStagesShown((shown) => {
        if (shown >= revealStages.length) {
          window.clearInterval(timer);
          return shown;
        }
        return shown + 1;
      });
    }, 900);
    return () => window.clearInterval(timer);
  }, [session.phase, session.session_id, revealStages.length]);
  const stagesComplete = stagesShown >= revealStages.length;

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
      // Skip keys while typing a free-text reply.
      if (event.target instanceof HTMLInputElement) return;
      const index = Number.parseInt(event.key, 10) - 1;
      if (Number.isInteger(index) && index >= 0 && index < orderedOptions.length) {
        onAnswer(orderedOptions[index].id, performance.now() - questionShownAt.current);
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [session.phase, orderedOptions, busy, onAnswer]);

  function submitFreeText(event: FormEvent): void {
    event.preventDefault();
    const text = freeText.trim();
    if (!text || busy) return;
    setFreeText("");
    const rhythm = rhythmRef.current?.summary() ?? null;
    onFreeText(text, performance.now() - questionShownAt.current, rhythm);
  }

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
      if (session.mode === "covert") {
        // Voice on a covert turn is just words in the air: send the verbatim
        // transcript down the free-text path for server-side parsing.
        setVoiceState("idle");
        if (!transcript.trim()) {
          setVoiceFeedback("The spirits heard nothing — say it again.");
          return;
        }
        onFreeText(transcript, performance.now() - recordStartRef.current);
        return;
      }
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

  function submitSurvey(event: FormEvent): void {
    event.preventDefault();
    if (!survey || busy) return;
    onSurvey(survey);
    setSurveySent(true);
  }

  const LIKERT_ITEMS: { key: keyof SurveyAnswers; label: string }[] = [
    { key: "impossibility", label: "There is no way it could have known from what I said." },
    { key: "freedom", label: "I felt completely free — not steered." },
    { key: "naturalness", label: "It felt like a performance, not a survey." },
    { key: "surprise", label: "The reveal was unexpected and dramatic." },
  ];

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

      {!(session.phase === "revealed" && !stagesComplete) && (
        <blockquote className="message" aria-live="polite">
          {session.message}
        </blockquote>
      )}

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
            {orderedOptions.map((option, index) => (
              <button
                key={option.id}
                className={`option-btn${
                  option.id === session.salient_option_id ? " option-salient" : ""
                }`}
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

          {session.mode === "covert" && (
            <form className="freetext-row" onSubmit={submitFreeText}>
              <input
                type="text"
                value={freeText}
                maxLength={200}
                disabled={busy}
                onChange={(e) => setFreeText(e.target.value)}
                onKeyDown={(e) => {
                  // Rhythm aggregates only: character keystrokes, never key
                  // identity (docs/passive-signals.md §2).
                  if (e.key.length === 1) rhythmRef.current?.key();
                }}
                placeholder="…or answer in your own words"
                aria-label="Answer in your own words"
              />
              <button type="submit" className="option-btn subtle" disabled={busy || !freeText.trim()}>
                Send
              </button>
            </form>
          )}
        </>
      )}

      {session.phase === "revealed" && session.prediction && (
        <div className="reveal">
          {revealStages.slice(0, stagesShown).map((stage, index) => (
            <p key={index} className={`reveal-stage reveal-stage-${stage.kind}`}>
              {stage.text}
            </p>
          ))}
          {stagesComplete && (
            <>
              <p className="reveal-label">LOKI commits to</p>
              <p className="prediction">{session.prediction.label}</p>
              <p className="confidence">
                posterior confidence {(session.prediction.confidence * 100).toFixed(1)}%
                {session.reveal_path && session.reveal_path !== "plain" && (
                  <> · reveal path: {session.reveal_path.replace(/_/g, " ")}</>
                )}
              </p>
              <div className="outcome-buttons">
                <button className="option-btn correct" disabled={busy} onClick={() => onOutcome(true)}>
                  The trickster saw true
                </button>
                <button className="option-btn wrong" disabled={busy} onClick={() => onOutcome(false)}>
                  LOKI was wrong
                </button>
              </div>
            </>
          )}
        </div>
      )}

      {session.phase === "outcome" && (
        <div className="again">
          <p className="curtain-note">
            Debrief — LOKI is a research prototype investigating the digitalization of
            mentalism. It uses exact Bayesian inference, information-gain queries, and
            structured theatrical timing. It possesses no telepathic or supernatural
            capabilities.
          </p>
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

          {!surveySent ? (
            <form className="survey" onSubmit={submitSurvey}>
              <p className="survey-invite">
                Optional research question — press <strong>Send answers</strong> only if you
                consent to keeping these four numbers (nothing else, deletable anytime).
              </p>
              {LIKERT_ITEMS.map((item) => (
                <label key={item.key} className="survey-item">
                  <span>“{item.label}” — 1 (no) … 7 (completely)</span>
                  <input
                    type="range"
                    min={1}
                    max={7}
                    step={1}
                    value={(survey?.[item.key] as number | undefined) ?? 4}
                    onChange={(e) =>
                      setSurvey((s) => ({
                        impossibility: s?.impossibility ?? 4,
                        freedom: s?.freedom ?? 4,
                        naturalness: s?.naturalness ?? 4,
                        surprise: s?.surprise ?? 4,
                        willing_repeat: s?.willing_repeat ?? null,
                        [item.key]: Number(e.target.value),
                      }))
                    }
                  />
                </label>
              ))}
              <label className="survey-item">
                <input
                  type="checkbox"
                  checked={survey?.willing_repeat === true}
                  onChange={(e) =>
                    setSurvey((s) => ({
                      impossibility: s?.impossibility ?? 4,
                      freedom: s?.freedom ?? 4,
                      naturalness: s?.naturalness ?? 4,
                      surprise: s?.surprise ?? 4,
                      willing_repeat: e.target.checked,
                    }))
                  }
                />
                <span>I would try this again / show it to someone.</span>
              </label>
              <button type="submit" className="option-btn" disabled={busy}>
                Send answers
              </button>
            </form>
          ) : (
            <span className="archived-note">Answers kept — thank you. They can be deleted anytime.</span>
          )}
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
            <span>this turn: {session.mode === "covert" ? "covert read" : "direct question"}</span>
            {salientOption && session.phase === "active" && (
              <span>this turn: steering toward {salientOption.label}</span>
            )}
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
