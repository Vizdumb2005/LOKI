import type { ArchivedSummary, EffectSummary, LedgerStats } from "../types";

interface LedgerProps {
  stats: LedgerStats[];
  entries: ArchivedSummary[];
  effects: EffectSummary[] | null;
  onDelete: (sessionId: string) => void;
}

function titleOf(effects: EffectSummary[] | null, effectId: string): string {
  return effects?.find((e) => e.id === effectId)?.title ?? effectId;
}

export function Ledger({ stats, entries, effects, onDelete }: LedgerProps) {
  const total = stats.reduce((acc, s) => acc + s.archived, 0);
  const withOutcome = stats.reduce((acc, s) => acc + s.with_outcome, 0);
  const correct = stats.reduce((acc, s) => acc + s.correct, 0);
  const truthPct = withOutcome > 0 ? Math.round((correct / withOutcome) * 100) : null;

  return (
    <details className="ledger">
      <summary>
        The parlor's ledger — {total} séance{total === 1 ? "" : "s"} kept
        {truthPct != null ? ` · ${truthPct}% true` : ""}
      </summary>
      {entries.length === 0 ? (
        <p className="ledger-empty">
          Nothing kept yet. Finish a séance and choose to keep it — only then is
          anything written down.
        </p>
      ) : (
        <table className="ledger-table">
          <thead>
            <tr>
              <th>Effect</th>
              <th>Prediction</th>
              <th>Turns</th>
              <th>Truth</th>
              <th aria-label="delete" />
            </tr>
          </thead>
          <tbody>
            {entries.map((entry) => (
              <tr key={entry.session_id}>
                <td>{titleOf(effects, entry.effect_id)}</td>
                <td>{entry.prediction_label}</td>
                <td>{entry.turns_used}</td>
                <td className={entry.correct == null ? "" : entry.correct ? "truth-yes" : "truth-no"}>
                  {entry.correct == null ? "unreported" : entry.correct ? "true" : "false"}
                </td>
                <td>
                  <button
                    className="delete-btn"
                    aria-label={`Delete the record of ${entry.prediction_label}`}
                    onClick={() => onDelete(entry.session_id)}
                  >
                    ✕
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      <p className="ledger-note">
        Kept only with your explicit consent, in a local file on this machine ·
        delete anything, anytime.
      </p>
    </details>
  );
}
