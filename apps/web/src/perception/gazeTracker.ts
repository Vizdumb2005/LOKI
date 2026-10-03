// In-browser face tracking and coarse gaze estimation (Phase 2, slice B).
// MediaPipe FaceLandmarker runs entirely on-device (WASM/GPU); nothing but the
// derived gaze point ever leaves this module. Honest limitation: this is a
// parlor-grade head+eye direction proxy good enough to tell WHICH answer
// button someone is nearest — not precision eye tracking. The dwell
// accumulator's nearest-option credit absorbs the noise.

import {
  FaceLandmarker,
  FilesetResolver,
  type FaceLandmarkerResult,
} from "@mediapipe/tasks-vision";
import type { Point } from "./dwell";

// Pinned to the installed package version — bump here and in the model
// registry (configs/registries/models.yaml) together with package.json.
const WASM_URL = "https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@1.0.1/wasm";
const MODEL_URL =
  "https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/1/face_landmarker.task";

export interface GazeSample {
  t: number;
  point: Point | null; // normalized viewport coords; null when no face
  faceFound: boolean;
}

export interface GazeTrackerHandle {
  stop(): void;
}

// Landmark indices (MediaPipe canonical face mesh)
const NOSE_TIP = 1;
const CHIN = 152;
const FOREHEAD = 10;
const LEFT_CHEEK = 234;
const RIGHT_CHEEK = 454;
const LEFT_EYE_OUTER = 33;
const LEFT_EYE_INNER = 133;
const RIGHT_EYE_INNER = 362;
const RIGHT_EYE_OUTER = 263;
const LEFT_IRIS = 468;
const RIGHT_IRIS = 473;
const LEFT_EYE_TOP = 159;
const LEFT_EYE_BOTTOM = 145;
const RIGHT_EYE_TOP = 386;
const RIGHT_EYE_BOTTOM = 374;

// Parlor-grade mapping weights (tuned by hand; see docs curtain note)
const YAW_WEIGHT = 0.6;
const EYE_WEIGHT = 0.35;
const PITCH_WEIGHT = 0.6;
const EYE_Y_WEIGHT = 0.3;

function clamp01(v: number): number {
  return Math.min(1, Math.max(0, v));
}

export function gazePointFrom(result: FaceLandmarkerResult): Point | null {
  const lm = result.faceLandmarks[0];
  if (!lm || lm.length < RIGHT_EYE_BOTTOM + 1) return null;

  const faceCenterX = (lm[LEFT_CHEEK].x + lm[RIGHT_CHEEK].x) / 2;
  const faceWidth = Math.abs(lm[RIGHT_CHEEK].x - lm[LEFT_CHEEK].x) || 1e-6;
  const yawProxy = ((lm[NOSE_TIP].x - faceCenterX) / faceWidth) * 2;

  const eyeRatio = (iris: number, outer: number, inner: number): number => {
    const span = lm[inner].x - lm[outer].x || 1e-6;
    return ((lm[iris].x - lm[outer].x) / span - 0.5) * 2;
  };
  const gazeX = (eyeRatio(LEFT_IRIS, LEFT_EYE_OUTER, LEFT_EYE_INNER) +
    eyeRatio(RIGHT_IRIS, RIGHT_EYE_OUTER, RIGHT_EYE_INNER)) / 2;

  const faceMidY = (lm[FOREHEAD].y + lm[CHIN].y) / 2;
  const faceHeight = Math.abs(lm[CHIN].y - lm[FOREHEAD].y) || 1e-6;
  const pitchProxy = ((lm[NOSE_TIP].y - faceMidY) / faceHeight) * 2;

  const eyeRatioY = (iris: number, top: number, bottom: number): number => {
    const span = lm[bottom].y - lm[top].y || 1e-6;
    return ((lm[iris].y - lm[top].y) / span - 0.5) * 2;
  };
  const gazeY = (eyeRatioY(LEFT_IRIS, LEFT_EYE_TOP, LEFT_EYE_BOTTOM) +
    eyeRatioY(RIGHT_IRIS, RIGHT_EYE_TOP, RIGHT_EYE_BOTTOM)) / 2;

  // The preview is mirrored (scaleX(-1)); mirror the x axis to match what the
  // participant sees. Turning toward an option on the screen's right must move
  // the point right on screen.
  const x = clamp01(0.5 - (YAW_WEIGHT * yawProxy + EYE_WEIGHT * gazeX) / 2);
  const y = clamp01(0.5 + (PITCH_WEIGHT * pitchProxy + EYE_Y_WEIGHT * gazeY) / 2);
  return { x, y };
}

export async function createGazeTracker(
  video: HTMLVideoElement,
  onSample: (sample: GazeSample) => void,
): Promise<GazeTrackerHandle> {
  const fileset = await FilesetResolver.forVisionTasks(WASM_URL);
  let landmarker: FaceLandmarker;
  try {
    landmarker = await FaceLandmarker.createFromOptions(fileset, {
      baseOptions: { modelAssetPath: MODEL_URL, delegate: "GPU" },
      runningMode: "VIDEO",
      outputFaceBlendshapes: true,
      outputFacialTransformationMatrixes: true,
      numFaces: 1,
    });
  } catch {
    // GPU delegate unavailable (driver/codec quirks) — fall back to CPU
    landmarker = await FaceLandmarker.createFromOptions(fileset, {
      baseOptions: { modelAssetPath: MODEL_URL, delegate: "CPU" },
      runningMode: "VIDEO",
      outputFaceBlendshapes: true,
      outputFacialTransformationMatrixes: true,
      numFaces: 1,
    });
  }

  let running = true;
  let lastVideoTime = -1;

  const loop = (): void => {
    if (!running) return;
    if (video.readyState >= 2 && video.currentTime !== lastVideoTime) {
      lastVideoTime = video.currentTime;
      const t = performance.now();
      try {
        const result = landmarker.detectForVideo(video, t);
        const point = gazePointFrom(result);
        onSample({ t, point, faceFound: point != null });
      } catch {
        // A per-frame failure (GPU hiccup, context loss) must not kill the loop.
      }
    }
    requestAnimationFrame(loop);
  };
  requestAnimationFrame(loop);

  return {
    stop(): void {
      running = false;
      landmarker.close();
    },
  };
}
