# Spec: Reveal Planning — Multiple Outs, Progressive Staging, Equivocation (ROADMAP Phase 3)

Status: **Active — ROADMAP Phase 3**

Translates `research/digital-translation.md` §2 (Multi-Branch Reveal Resolver), §2.9 (strategic
hesitation), and `research/mentalism-techniques.md` §2.1/§2.2/§4.1 (equivocation, multiple outs,
reveal escalation) into the reveal moment. The commit mathematics do not change: the prediction
is still the MAP hypothesis, still governed by the same entropy/turn termination, and the
reveal still ends in the same confidence-banded line (plan §4.8 — the surface never converts
weak evidence into certainty). What changes is **how the reveal is staged**.

## 1. Boundary split (why two modules)

Choosing a reveal PATH depends on posterior spread — that is a decision, so it lives in the
policy layer: `services/policy/reveal_planner.py` produces a structured `RevealPlan`. Staging
that plan into theatrical lines is rendering: `services/language/reveal_planner.py` turns the
plan plus confidence into the beat sequence. (ROADMAP named one module in `services/language/`;
the split keeps the AGENTS.md boundary — LOKI-Language never decides — intact. The equivocation
reframes likewise render engine-recorded state, never re-interpret probabilities.)

## 2. Reveal paths (the multiple outs)

Given candidates = top-3 posterior hypotheses with probabilities p1 ≥ p2 ≥ p3:

| path | condition | staging |
|---|---|---|
| `progressive` | p1 ≥ 0.80 | attribute ladder from the session's asked questions (up to 2 beats: e.g. "a red card…" → "six or seven…"), then the banded identity line. Classic Category → Attribute → Identity escalation. |
| `category_cluster` | 0.50 ≤ p1 < 0.80 and top-2 share an attribute value | one beat naming the shared family ("Everything here beats in the same family — a heart."), then the banded identity. Even a missed identity leaves a landed "hit". |
| `dual_deduction` | p1 < 0.50 and p1 + p2 ≥ 0.70 | one beat presenting both candidates as a deduction ("Two threads cross here — the Salmon, or the Trout. My instinct settles on one."), then the banded identity (top-1). Combined top-2 mass makes the deduction a strong apparent hit even when the final pick misses. |
| `plain` | anything else | the banded identity line alone (the pre-Phase-3 reveal). |

Ladder beats derive from the asked questions only, in ask order: for each question whose
matching answer label is not a bare "Yes"/"No", the winner's answer label becomes a beat
(boolean confirmations fold into the identity line — "Yes" is not stage-worthy text).
Ties and determinism: first in declaration order wins; the same session always sees the same
staging (seeded selection, as everywhere in LOKI-Language).

## 3. Strategic hesitation

When 0.60 ≤ p1 < 0.85 the staging inserts ONE hesitation beat before the identity line
("Wait — no. It's clearer now."), per digital-translation.md's calibrated window. Rules:

- p1 ≥ 0.85: no hesitation — a decisive kill is the better theater.
- p1 < 0.60: no hesitation beat — the banded line is already hedged; piling doubt on doubt
  reads as incompetence, not mystery.
- Hesitation only ever ADDS doubt. Faked certainty remains forbidden in every band.

## 4. Equivocation (failure recovery as performance)

After a covert read misses (`lean_no`/`strong_no`) or lands `unclear`, the NEXT turn's message
opens with one reframe line — the magician's "Ah — not the craft itself, then…" — rendered by
`services/language/equivocation.py` from the engine-recorded state (`reframe` kind + the
missed option's label). Constraints:

- The Bayesian update has already handled the miss; the reframe is pure theater around it and
  must not claim more (or less) narrowing than happened — no probabilities, no hypothesis
  names beyond the missed label itself.
- `unclear` replies get a gentler beat (the mists swallowed that one).
- The next `policy.decision` event carries `reframe: "missed" | "unclear" | null` so the
  trajectory shows the recovery (event schema v1.3).

## 5. Event schema (v1.3, additive) and view

- `effect.revealed` gains `reveal_path`, `reveal_candidates` (hypothesis ids), and `stages`
  (structured descriptors `{kind, attr, label}` — no prose in events).
- `policy.decision` gains `reframe`.
- `SessionView` gains `reveal_path: str | null` and `reveal_stages: [{kind, text}]` — the
  rendered beats that precede `message` (which remains the final banded line). The frontend
  staggers the beats (~0.9 s apart) before showing the prediction — reveal timing becomes a
  first-class experimental lever (research question 10; perceived-impact measurement itself
  waits for human studies, ROADMAP Phase 6).

## 6. Measurement

`run_magic_factor_eval` reports the reveal-path distribution and accuracy per path. The
inference-affecting metrics (accuracy, turns, mystery gap, forced-commit rate) are unchanged
by construction — Phase 3 moves the reveal moment, not the posterior. Deferred: interactive
multi-branch reveals (revealing candidate B when the participant visibly balks at A) need a
post-reveal reaction channel — ROADMAP Phase 4/6 territory.
