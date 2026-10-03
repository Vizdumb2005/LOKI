// Pure dwell-accumulation logic for the gaze channel (Phase 2, slice B).
// No DOM, no MediaPipe — unit-testable. The caller feeds normalized viewport
// coordinates; the accumulator credits the option region nearest the gaze
// point and emits each option AT MOST ONCE per question once its cumulative
// dwell crosses the channel's min_dwell_ms.

export interface Point {
  x: number; // normalized 0..1 across the viewport
  y: number;
}

export interface OptionRegion {
  answerId: string;
  left: number;
  top: number;
  right: number;
  bottom: number;
}

export function nearestRegion(point: Point, regions: OptionRegion[]): OptionRegion | null {
  let best: OptionRegion | null = null;
  let bestDist = Number.POSITIVE_INFINITY;
  for (const region of regions) {
    const cx = Math.min(Math.max(point.x, region.left), region.right);
    const cy = Math.min(Math.max(point.y, region.top), region.bottom);
    const dist = (point.x - cx) ** 2 + (point.y - cy) ** 2;
    if (dist < bestDist) {
      bestDist = dist;
      best = region;
    }
  }
  return best;
}

export class DwellAccumulator {
  private totals = new Map<string, number>();
  private emitted = new Set<string>();
  private lastTs: number | null = null;

  constructor(
    private readonly minDwellMs: number,
    private readonly onEmit: (answerId: string, dwellMs: number) => void,
  ) {}

  /** Call when the question changes: nothing carries over. */
  reset(): void {
    this.totals.clear();
    this.emitted.clear();
    this.lastTs = null;
  }

  update(ts: number, point: Point | null, regions: OptionRegion[]): void {
    if (this.lastTs == null) {
      this.lastTs = ts;
      return;
    }
    const gap = ts - this.lastTs;
    this.lastTs = ts;
    // A gap longer than 1s is a discontinuity (tab switch, stall): credit nothing.
    if (point == null || gap <= 0 || gap > 1000 || regions.length === 0) return;
    const target = nearestRegion(point, regions);
    if (target == null) return;
    const total = (this.totals.get(target.answerId) ?? 0) + gap;
    this.totals.set(target.answerId, total);
    if (total >= this.minDwellMs && !this.emitted.has(target.answerId)) {
      this.emitted.add(target.answerId);
      this.onEmit(target.answerId, Math.round(total));
    }
  }
}
