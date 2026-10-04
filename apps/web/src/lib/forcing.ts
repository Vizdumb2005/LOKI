// Choice-architecture primitives (ROADMAP Phase 4, docs/choice-architecture.md).
// Pure helpers, unit-tested: the emphasis is presentation only — the click is
// still a plain Bayesian answer, nothing is ever disabled, and the curtain
// discloses the steering.

export interface OptionLike {
  id: string;
}

/**
 * Default-positioning primitive: move the salient option to the first
 * position, preserving the relative order of everything else. Non-salient
 * (or unknown) ids leave the list untouched.
 */
export function orderWithSalient<T extends OptionLike>(
  options: T[],
  salientId: string | null,
): T[] {
  if (!salientId) return options;
  const salient = options.find((o) => o.id === salientId);
  if (!salient) return options;
  return [salient, ...options.filter((o) => o.id !== salientId)];
}

/** Which option (if any) the current turn emphasizes. */
export function salientOf<T extends OptionLike>(
  options: T[],
  salientId: string | null,
): T | null {
  if (!salientId) return null;
  return options.find((o) => o.id === salientId) ?? null;
}
