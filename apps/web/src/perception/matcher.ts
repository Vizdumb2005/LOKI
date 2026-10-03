// Pure transcript→answer resolution for voice answers (Phase 2, slice C).
// The effect YAML declares `voice` synonyms per answer; the matcher is
// deliberately conservative: ambiguous or unheard transcripts never submit.

export interface VoiceTarget {
  answerId: string;
  words: string[];
}

export type MatchResult =
  | { status: "matched"; answerId: string }
  | { status: "ambiguous"; candidates: string[] }
  | { status: "no_match" };

export function tokenize(transcript: string): string[] {
  return transcript
    .toLowerCase()
    .replace(/[^a-z0-9\s]/g, " ")
    .split(/\s+/)
    .filter(Boolean);
}

// Label filler words that would otherwise collide with spoken filler
// ("red or black" must not match "Jack, Queen **or** King").
const STOP_WORDS = new Set(["or", "and", "the", "a", "an", "of", "to", "is", "it", "in"]);

export function targetsFromOptions(options: { id: string; label: string; voice: string[] }[]): VoiceTarget[] {
  return options.map((option) => ({
    answerId: option.id,
    words: [
      ...tokenize(option.label),
      ...option.voice.flatMap((phrase) => tokenize(phrase)),
    ].filter((w) => w.length > 0 && !STOP_WORDS.has(w)),
  }));
}

export function matchTranscript(transcript: string, targets: VoiceTarget[]): MatchResult {
  const tokens = tokenize(transcript);
  const hits = new Map<string, number>();
  for (const target of targets) {
    for (const token of tokens) {
      if (target.words.includes(token)) {
        hits.set(target.answerId, (hits.get(target.answerId) ?? 0) + 1);
      }
    }
  }
  const matched = [...hits.keys()];
  if (matched.length === 1) return { status: "matched", answerId: matched[0] };
  if (matched.length > 1) return { status: "ambiguous", candidates: matched.sort() };
  return { status: "no_match" };
}
