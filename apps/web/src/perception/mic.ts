// Push-to-talk microphone capture (Phase 2, slice C). Privacy rule: the PCM
// buffer lives only in this class until stop() hands it to the in-browser
// transcriber; the MediaStream ends the moment recording stops.

const WORKLET_SOURCE = `
class PCMCapture extends AudioWorkletProcessor {
  process(inputs) {
    const channel = inputs[0] && inputs[0][0];
    if (channel) this.port.postMessage(channel.slice(0));
    return true;
  }
}
registerProcessor("pcm-capture", PCMCapture);
`;

export class MicRecorder {
  private ctx: AudioContext | null = null;
  private stream: MediaStream | null = null;
  private node: AudioWorkletNode | null = null;
  private chunks: Float32Array[] = [];

  async start(): Promise<void> {
    this.stream = await navigator.mediaDevices.getUserMedia({
      audio: { echoCancellation: true, noiseSuppression: true },
    });
    // 16 kHz mono is exactly what the whisper frontend expects
    this.ctx = new AudioContext({ sampleRate: 16000 });
    const url = URL.createObjectURL(
      new Blob([WORKLET_SOURCE], { type: "application/javascript" }),
    );
    await this.ctx.audioWorklet.addModule(url);
    URL.revokeObjectURL(url);
    this.node = new AudioWorkletNode(this.ctx, "pcm-capture");
    this.node.port.onmessage = (event: MessageEvent<Float32Array>) => {
      this.chunks.push(new Float32Array(event.data));
    };
    this.ctx.createMediaStreamSource(this.stream).connect(this.node);
    this.chunks = [];
  }

  /** Ends capture and returns the mono 16 kHz PCM buffer. */
  async stop(): Promise<Float32Array> {
    const total = this.chunks.reduce((acc, chunk) => acc + chunk.length, 0);
    const out = new Float32Array(total);
    let offset = 0;
    for (const chunk of this.chunks) {
      out.set(chunk, offset);
      offset += chunk.length;
    }
    this.chunks = [];
    this.node?.disconnect();
    this.node = null;
    this.stream?.getTracks().forEach((track) => track.stop());
    this.stream = null;
    await this.ctx?.close();
    this.ctx = null;
    return out;
  }
}
