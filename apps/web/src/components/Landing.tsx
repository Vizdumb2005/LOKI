import type { ArchivedSummary, EffectSummary, LedgerStats } from "../types";
import { Ledger } from "./Ledger";

interface LandingProps {
  effects: EffectSummary[] | null;
  ledgerStats: LedgerStats[];
  ledgerEntries: ArchivedSummary[];
  busy: boolean;
  onStart: (effectId: string) => void;
  onDeleteArchived: (sessionId: string) => void;
}

export function Landing({
  effects,
  ledgerStats,
  ledgerEntries,
  busy,
  onStart,
  onDeleteArchived,
}: LandingProps) {
  if (!effects) {
    return <p className="loading">Consulting the ravens…</p>;
  }
  return (
    <section>
      <p className="landing-lede">
        Choose an effect. Keep your secret firmly in mind — <em>answer truly</em>,
        and LOKI will name what you hide. Every question narrows the possible;
        the trick is knowing what to ask next.
      </p>
      <div className="effect-grid">
        {effects.map((effect) => (
          <button
            key={effect.id}
            className="effect-card"
            disabled={busy}
            onClick={() => onStart(effect.id)}
          >
            <h2>{effect.title}</h2>
            <p>{effect.description}</p>
            <span className="counts">
              {effect.hypothesis_count} possibilities · {effect.question_count} questions
              {effect.observation_channels.length > 0 ? " · 👁 camera-ready" : ""}
            </span>
            <span className="begin">Begin the séance →</span>
          </button>
        ))}
      </div>
      <Ledger
        stats={ledgerStats}
        entries={ledgerEntries}
        effects={effects}
        onDelete={onDeleteArchived}
      />
    </section>
  );
}
