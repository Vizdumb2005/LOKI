import { describe, expect, it } from "vitest";
import { createRhythmTracker } from "./telemetry";

function steppedClock(start = 0, step = 100) {
  let t = start;
  return () => {
    t += step;
    return t;
  };
}

describe("createRhythmTracker", () => {
  it("returns null when nothing was typed", () => {
    const tracker = createRhythmTracker(steppedClock());
    expect(tracker.summary()).toBeNull();
  });

  it("measures time to first keystroke from when the tracker was created", () => {
    let t = 0;
    const tracker = createRhythmTracker(() => t);
    t = 3200; // the participant stared at the box for a while
    tracker.key();
    t = 3350;
    tracker.key();
    const summary = tracker.summary()!;
    expect(summary.first_key_ms).toBe(3200);
    expect(summary.total_ms).toBe(150);
    expect(summary.median_interval_ms).toBe(150);
  });

  it("computes the median inter-key interval (even count averages the middle two)", () => {
    let t = 0;
    const tracker = createRhythmTracker(() => t);
    t = 100;
    tracker.key(); // first keystroke
    t = 300;
    tracker.key(); // interval 200
    t = 800;
    tracker.key(); // interval 500
    t = 900;
    tracker.key(); // interval 100
    const summary = tracker.summary()!;
    expect(summary.median_interval_ms).toBe(200);
    expect(summary.total_ms).toBe(800);
  });

  it("clamps negatives and tolerates a single keystroke", () => {
    let t = 0;
    const tracker = createRhythmTracker(() => t);
    t = 500;
    tracker.key();
    const summary = tracker.summary()!;
    expect(summary.first_key_ms).toBe(500);
    expect(summary.total_ms).toBe(0);
    expect(summary.median_interval_ms).toBe(0);
  });
});
