# LOKI CORE V1 (frozen 2026-10-05)

Reference inference implementation. Future Brain/policy/language work must reproduce
or beat these numbers, never silently change semantics underneath them.

## Frozen semantics

- `Tracker.update()` takes strictly-positive likelihood vectors only; an update that
  zeroes a hypothesis raises (soft-agreement invariant, covert-fishing rule a).
- One (question, hypothesis) → exactly one matching answer predicate (`loader`
  partition rule); `unclear` advances the turn without touching the posterior.
- Observations apply to direct turns only; they modulate reliability, never decide.
- Posterior is owned by `services/hypothesis` + `services/effects` only. Brain,
  language, frontend may read it; nothing outside may write it.

## Baseline (direct mode, 500 sessions, seed 42)

| effect | accuracy | turns | H@commit | forced |
|---|--:|--:|--:|--:|
| animal_guess | 0.886 | 9.26 | 0.507 | 0.628 |
| card_prediction | 0.898 | 5.38 | 0.514 | 0.188 |
| number_prediction | 0.868 | 6.68 | 0.636 | 0.614 |
| sigil_forced_choice | 0.974 | 3.40 | 0.140 | 0.032 |

Reproduce: `python -m experiments.run_baseline_eval --sessions 500 --seed 42`
Regression: `python -m pytest` — 488 passed in 54s on 2026-10-05.
