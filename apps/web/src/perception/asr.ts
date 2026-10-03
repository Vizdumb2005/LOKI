// In-browser speech-to-text (Phase 2, slice C): whisper-tiny.en via
// Transformers.js, WebGPU when available, WASM otherwise. The model
// (~50 MB, q8) downloads once and is served from the browser cache after.
// Audio never leaves the machine — only the final transcript is used, and
// only locally, to resolve an answer.

import {
  env,
  pipeline,
  type AutomaticSpeechRecognitionPipeline,
} from "@huggingface/transformers";

// Don't try to resolve local model paths; we always fetch from the Hub.
env.allowLocalModels = false;

let pipelinePromise: Promise<AutomaticSpeechRecognitionPipeline> | null = null;

export function loadTranscriber(
  onProgress?: (percent: number) => void,
): Promise<AutomaticSpeechRecognitionPipeline> {
  if (!pipelinePromise) {
    const device = "gpu" in navigator ? "webgpu" : "wasm";
    pipelinePromise = pipeline(
      "automatic-speech-recognition",
      "onnx-community/whisper-tiny.en",
      {
        dtype: { encoder_model: "q8", decoder_model_merged: "q8" },
        device,
        progress_callback: (progress: { status: string; progress?: number }) => {
          if (progress.status === "progress" && typeof progress.progress === "number") {
            onProgress?.(progress.progress);
          }
        },
      },
    );
  }
  return pipelinePromise;
}

export async function transcribe(pcm: Float32Array): Promise<string> {
  const transcriber = await pipelinePromise;
  if (!transcriber) throw new Error("transcriber not loaded — call loadTranscriber() first");
  const output = await transcriber(pcm);
  const text = Array.isArray(output) ? output[0]?.text : output.text;
  return (text ?? "").trim();
}
