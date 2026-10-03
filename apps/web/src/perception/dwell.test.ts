import { describe, expect, it, vi } from "vitest";
import { DwellAccumulator, nearestRegion, type OptionRegion } from "./dwell";

const REGIONS: OptionRegion[] = [
  { answerId: "left", left: 0.0, top: 0.4, right: 0.45, bottom: 0.6 },
  { answerId: "right", left: 0.55, top: 0.4, right: 1.0, bottom: 0.6 },
];

describe("nearestRegion", () => {
  it("returns the region containing the point", () => {
    expect(nearestRegion({ x: 0.2, y: 0.5 }, REGIONS)?.answerId).toBe("left");
    expect(nearestRegion({ x: 0.8, y: 0.5 }, REGIONS)?.answerId).toBe("right");
  });

  it("returns the closest region when the point is outside all of them", () => {
    expect(nearestRegion({ x: 0.47, y: 0.5 }, REGIONS)?.answerId).toBe("left");
    expect(nearestRegion({ x: 0.53, y: 0.5 }, REGIONS)?.answerId).toBe("right");
  });

  it("returns null only when there are no regions", () => {
    expect(nearestRegion({ x: 0.5, y: 0.5 }, [])).toBeNull();
  });
});

describe("DwellAccumulator", () => {
  it("emits once per option when cumulative dwell crosses the threshold", () => {
    const onEmit = vi.fn();
    const acc = new DwellAccumulator(400, onEmit);
    acc.reset();
    // establish a first timestamp without accumulating
    acc.update(1000, { x: 0.2, y: 0.5 }, REGIONS);
    acc.update(1350, { x: 0.2, y: 0.5 }, REGIONS); // 350 ms
    expect(onEmit).not.toHaveBeenCalled();
    acc.update(1500, { x: 0.2, y: 0.5 }, REGIONS); // 500 ms cumulative
    expect(onEmit).toHaveBeenCalledTimes(1);
    expect(onEmit).toHaveBeenCalledWith("left", 500);
    acc.update(1900, { x: 0.2, y: 0.5 }, REGIONS); // more dwell, already emitted
    expect(onEmit).toHaveBeenCalledTimes(1);
  });

  it("splits credit between options as the gaze moves", () => {
    const onEmit = vi.fn();
    const acc = new DwellAccumulator(400, onEmit);
    acc.update(0, { x: 0.2, y: 0.5 }, REGIONS);
    acc.update(300, { x: 0.2, y: 0.5 }, REGIONS); // left: 300
    // intervals are credited to the region seen at their end
    acc.update(600, { x: 0.8, y: 0.5 }, REGIONS); // right: 300
    acc.update(1200, { x: 0.8, y: 0.5 }, REGIONS); // right: 900
    expect(onEmit).toHaveBeenCalledTimes(1);
    expect(onEmit).toHaveBeenCalledWith("right", 900);
  });

  it("ignores frames without a face and treats >1s gaps as discontinuities", () => {
    const onEmit = vi.fn();
    const acc = new DwellAccumulator(400, onEmit);
    acc.update(0, { x: 0.2, y: 0.5 }, REGIONS);
    acc.update(500, null, REGIONS); // no face: no credit, clock still advances
    acc.update(10_000, { x: 0.2, y: 0.5 }, REGIONS); // gap clamped to 200 ms
    acc.update(10_400, { x: 0.2, y: 0.5 }, REGIONS);
    expect(onEmit).toHaveBeenCalledTimes(1);
    expect(onEmit).toHaveBeenCalledWith("left", 400);
  });

  it("reset clears everything on question change", () => {
    const onEmit = vi.fn();
    const acc = new DwellAccumulator(400, onEmit);
    acc.update(0, { x: 0.2, y: 0.5 }, REGIONS);
    acc.update(300, { x: 0.2, y: 0.5 }, REGIONS);
    acc.reset();
    acc.update(1000, { x: 0.2, y: 0.5 }, REGIONS);
    acc.update(1450, { x: 0.2, y: 0.5 }, REGIONS); // only 450 ms since reset
    expect(onEmit).toHaveBeenCalledTimes(1);
    expect(onEmit).toHaveBeenCalledWith("left", 450);
  });
});
