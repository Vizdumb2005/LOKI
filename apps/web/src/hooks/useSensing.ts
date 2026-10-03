// Camera → gaze → dwell → observation pipeline (Phase 2, slice B).
// Privacy rules encoded here: the camera runs ONLY while the participant is
// answering (auto-stopped the moment the phase leaves "active"), the preview
// is what they see of themselves, and stop() is absolute. No frame ever
// leaves the browser; only the derived dwell events are handed to onDwell.

import { useCallback, useEffect, useRef, useState } from "react";
import { openCamera } from "../perception/camera";
import { DwellAccumulator, type OptionRegion } from "../perception/dwell";

export type SensingState =
  | "off" // not started
  | "requesting" // permission prompt / loading the model
  | "active" // camera on, tracker running
  | "denied" // permission refused or no camera
  | "failed" // camera ok but the tracker/model could not load
  | "stopped"; // user pressed Stop this session

interface UseSensingArgs {
  /** True once the participant explicitly opted in for this session. */
  enabled: boolean;
  minDwellMs: number;
  /** Current question id — the accumulator resets whenever it changes. */
  questionId: string | null;
  onDwell: (answerId: string, dwellMs: number) => void;
}

function readOptionRegions(): OptionRegion[] {
  const vw = window.innerWidth;
  const vh = window.innerHeight;
  const regions: OptionRegion[] = [];
  document.querySelectorAll<HTMLElement>("[data-answer-id]").forEach((el) => {
    const answerId = el.dataset.answerId;
    if (!answerId) return;
    const rect = el.getBoundingClientRect();
    regions.push({
      answerId,
      left: rect.left / vw,
      top: rect.top / vh,
      right: rect.right / vw,
      bottom: rect.bottom / vh,
    });
  });
  return regions;
}

export function useSensing({ enabled, minDwellMs, questionId, onDwell }: UseSensingArgs) {
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const [state, setState] = useState<SensingState>("off");
  const [faceFound, setFaceFound] = useState(false);
  const cleanupRef = useRef<(() => void) | null>(null);
  const accumulatorRef = useRef<DwellAccumulator | null>(null);
  const onDwellRef = useRef(onDwell);
  onDwellRef.current = onDwell;
  const questionRef = useRef(questionId);
  questionRef.current = questionId;

  const start = useCallback(async () => {
    if (cleanupRef.current || !videoRef.current) return;
    setState("requesting");
    let camera: { stop(): void } | null = null;
    try {
      camera = await openCamera(videoRef.current);
      // MediaPipe (+ its WASM runtime) is heavy: load it only when sensing starts.
      const { createGazeTracker } = await import("../perception/gazeTracker");
      const accumulator = new DwellAccumulator(minDwellMs, (answerId, dwellMs) => {
        if (questionRef.current) onDwellRef.current(answerId, dwellMs);
      });
      accumulatorRef.current = accumulator;
      const tracker = await createGazeTracker(videoRef.current, (sample) => {
        setFaceFound(sample.faceFound);
        accumulator.update(sample.t, sample.point, readOptionRegions());
      });
      cleanupRef.current = () => {
        tracker.stop();
        camera?.stop();
        accumulator.reset();
        accumulatorRef.current = null;
        setFaceFound(false);
      };
      setState("active");
    } catch (e) {
      // Never leak the stream when the tracker fails to load.
      camera?.stop();
      accumulatorRef.current = null;
      const name = (e as Error)?.name ?? "";
      setState(
        name === "NotAllowedError" || name === "NotFoundError" || name === "NotReadableError"
          ? "denied"
          : "failed",
      );
    }
  }, [minDwellMs]);

  const stop = useCallback(() => {
    cleanupRef.current?.();
    cleanupRef.current = null;
    setState("stopped");
  }, []);

  // New question: dwell credit never carries over.
  useEffect(() => {
    accumulatorRef.current?.reset();
  }, [questionId]);

  // Sensing only exists during the questioning phase.
  useEffect(() => {
    if (!enabled && cleanupRef.current) stop();
  }, [enabled, stop]);

  // Leaving the session (unmount): camera off, always.
  useEffect(() => () => cleanupRef.current?.(), []);

  return { videoRef, state, faceFound, start, stop };
}
