// Camera lifecycle (Phase 2, slice B). Privacy rule: the stream stays in the
// element given to us; stop() is absolute — tracks end, the element detaches,
// and no frame is retained anywhere.

export interface CameraHandle {
  stop(): void;
}

export async function openCamera(video: HTMLVideoElement): Promise<CameraHandle> {
  const stream = await navigator.mediaDevices.getUserMedia({
    video: { width: { ideal: 640 }, height: { ideal: 480 }, facingMode: "user" },
    audio: false,
  });
  video.srcObject = stream;
  video.muted = true;
  try {
    await video.play();
  } catch {
    // autoplay policies: the muted element will play once visible
  }
  return {
    stop(): void {
      stream.getTracks().forEach((track) => track.stop());
      video.srcObject = null;
    },
  };
}
