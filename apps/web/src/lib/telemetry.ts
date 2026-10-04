// Typing-rhythm telemetry (ROADMAP Phase 5, docs/passive-signals.md §2).
// Aggregates only: the tracker records WHEN keys happen, never which keys —
// key content never enters telemetry, and raw timing sequences never leave
// the browser. Three numbers ride the free-text reply's own event.

export interface TypingRhythm {
  first_key_ms: number;
  median_interval_ms: number;
  total_ms: number;
}

export interface RhythmTracker {
  /** Record a keystroke (character keys only — call sites filter). */
  key: () => void;
  /** The aggregate rhythm, or null if nothing was typed. */
  summary: () => TypingRhythm | null;
}

function median(values: number[]): number {
  if (values.length === 0) return 0;
  const sorted = [...values].sort((a, b) => a - b);
  const mid = Math.floor(sorted.length / 2);
  return sorted.length % 2 === 1 ? sorted[mid] : (sorted[mid - 1] + sorted[mid]) / 2;
}

export function createRhythmTracker(
  now: () => number = () => performance.now(),
): RhythmTracker {
  const shownAt = now();
  let firstKey: number | null = null;
  let lastKey: number | null = null;
  const intervals: number[] = [];

  return {
    key() {
      const t = now();
      if (firstKey === null) {
        firstKey = t;
      } else if (lastKey !== null) {
        intervals.push(t - lastKey);
      }
      lastKey = t;
    },
    summary() {
      if (firstKey === null || lastKey === null) return null;
      return {
        first_key_ms: Math.max(0, firstKey - shownAt),
        median_interval_ms: median(intervals),
        total_ms: Math.max(0, lastKey - firstKey),
      };
    },
  };
}
