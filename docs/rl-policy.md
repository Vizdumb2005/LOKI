# Spec: RL Dialogue Policy — Contextual Bandit (ROADMAP Phase 6, item 1)

Status: **Active — ROADMAP Phase 6 (Bandit simulator & training harness built)**

Answers idea.md §13 Q6 experimentally: *can a contextual bandit produce better interactions
than the manually designed information-gain heuristics?* The agent trains in the participant
simulator (idea.md §8 — the precondition is met: answer, gaze, fishing-response, latency, and
forcing models all exist) against **synthetic participant profiles**, optimizing a
Magic-Factor-aligned reward (docs/magic-factor.md).

## 1. Decision point and action space

Each turn, the agent observes a context and chooses one interaction:

| action | meaning |
|---|---|
| `direct` | the information-gain question, no emphasis |
| `covert` | a covert fishing assertion (only when a credible candidate exists and the ration allows) |
| `forced` | the direct question with choice-architecture emphasis (only when a credible favorite exists) |

Hard constraints are **action masks**, not learned: never repeat a question; the covert
ration and budget reserve still bind; invalid actions are masked out of the choice set. The
bandit chooses the STRATEGY; the state machine stays sovereign.

## 2. Context and reward

Context is discretized into interpretable cells: `phase` (turn fraction: early/mid/late) ×
`credibility` (top-mass of the best action's favorite: < 0.5 / 0.5–0.75 / ≥ 0.75) — 9 cells ×
3 actions. A tabular ε-greedy bandit (optimistic init 0.05, ε decaying 0.3 → 0.05) — no
linear algebra, fully auditable; a linear/UCB upgrade is future work.

Per-turn reward, Magic-Factor-aligned:

```
r = ΔH_actual(turn) − λ · visible_bits(turn) + terminal
λ = 0.25 (documented weight of perceived interrogation)
terminal (last turn only): +0.5 correct prediction / −0.5 wrong
```

Credit assignment is deliberately simple: turns update their own (cell, action) value with
the immediate reward; the terminal bonus lands on the committing turn. This is a bandit with
shaping, not full sequence RL (idea.md Stage E's constrained RL remains future work) — the
simplification is stated because it bounds what the agent can learn: turn-level strategy
selection, not multi-turn plans.

## 3. Synthetic participant profiles (`simulator/profiles.py`)

Heterogeneous populations so the policy must generalize (idea.md §8: noise, hesitation,
strategy changes, adversarial behavior):

| profile | parameters |
|---|---|
| `balanced` | the calibration defaults |
| `impulsive` | fast latencies, low answer reliability (0.75) |
| `cautious` | slow latencies, high reliability (0.98) |
| `suggestible` | high forcing susceptibility (0.5), affirming fishing responses |
| `evasive` | frequent unclear/hedged replies (fishing noise up), slow typing |
| `adversarial` | actively misleading answers (reliability 0.15), decoy gaze |

`sample_profile(rng)` draws from a uniform mixture; training and evaluation both run over the
mixture, and the evaluation reports per-profile breakdowns.

## 4. Engine integration

`EffectSession` gains an injectable turn selector (same signature as
`services.policy.method_selection.select_turn`, default unchanged — every existing invariant
and test holds) plus a `performance` flag (condition A, below). The bandit's selector
materializes its action into a `TurnPlan` through the same helpers the heuristics use, and
`policy.decision.reason` records `bandit:<action>` so trajectories stay auditable.

## 5. Measurement

`experiments/run_bandit_eval.py`: trains N episodes over the profile mixture, then evaluates
**bandit (greedy) vs the hand-designed heuristic** on fresh sessions per profile, reporting
the full magic-factor protocol (accuracy, turns, ΔH, visible bits, mystery gap, M,
forced-commit rate) and the learned action distribution. The result is reported honestly in
both directions — a tie against a tuned heuristic is a finding (§13 Q6), not a failure.
The trained table is serialized to `experiments/outputs/bandit_policy.json`.

## 6. Out of scope (deferred)

Linear/UCB function approximation, full sequence RL with discounting (idea.md §4.6 candidate
methods 3–4), online learning from consented human sessions (needs the A/B suite's data,
docs/human-trials.md), reward learning from human preferences.
