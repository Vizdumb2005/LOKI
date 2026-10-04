# Spec: Effect Schema (v1.5)

Status: **Active — Phase 0–5** (versioned; additive changes bump the version below)

An **effect** is a formal policy environment — not a conversation. LOKI is built around effects
(plan §5). This document defines the declarative schema; the normative implementation is the
Pydantic model in `services/effects/models.py` and the loader in `services/effects/loader.py`.
The loader is strict: a malformed effect must fail at startup, never mid-session.

## v1.1 additions (Phase 2 — multimodal observations)

Two additive blocks, fully optional per effect:

```yaml
observations:                    # non-verbal evidence channels
  gaze_dwell:
    reliability: 0.55            # WEAK by definition: strictly below 1.0
    min_dwell_ms: 400            # client-side dwell threshold before emitting
```

- `reliability` is the likelihood weight `P(dwell on X | true answer X)` — a hint about the
  answer the participant is about to give, **not** a statement. Observations never advance a
  session, never count as turns, and never trigger termination; they only move probability
  mass (`EffectSession.observe`). The info-gain policy reads the updated posterior, so
  gaze-informed question ordering falls out for free.
- Per-answer `voice: [synonyms]` — spoken tokens the in-browser matcher accepts for that
  answer (e.g. `voice: ["hearts", "heart"]`). Matching is conservative: ambiguous or unmatched
  transcripts submit nothing.

## v1.2 additions (ROADMAP Phase 2 — covert fishing presentation)

Two additive, fully optional per-question fields. They change how a question is PRESENTED and
answered, never the hypothesis space, the partition rule, or the likelihood model:

```yaml
questions:
  - id: q_color
    fishing: true                # optional, default true — set false to opt out of assertion turns
    fishing_openers:             # optional, overrides the default assertion bank (services/language/fishing.py)
      - "There's a warmth to this… {label}, isn't it?"
```

- `fishing: false` removes the question from the Method Selection Policy's covert candidates;
  it can then only be asked directly.
- `fishing_openers` templates MUST contain a `{label}` placeholder (the asserted option's label
  is interpolated) and MUST NOT name any other option of the question — an assertion may leak
  only the option it asserts. The loader fails at startup otherwise (YAML 1.1 warning: quote
  any bare `yes`/`no` strings).
- Normative behavior of covert turns (agreement scale, soft-update matrix, method-selection
  policy, measured gates): **docs/covert-fishing.md**.

## v1.5 additions (ROADMAP Phase 5 — latency modulation channel)

An optional top-level `response_latency:` key declares the passive-signal modulation channel
(docs/passive-signals.md). Unlike the categorical `observations:` channels, latency modulates
how much the verbal answer itself is worth:

```yaml
response_latency:
  fast_ms: 2000        # at or below: the answer keeps its full reliability
  slow_ms: 8000        # at or above: reliability scaled down to the floor
  floor: 0.6           # weakened, never inverted
```

The loader parses this into `EffectDef.latency_channel` (not into the categorical
`observations` map), validation requires `0 < fast_ms < slow_ms` and `floor ∈ (0, 1]`, and a
malformed channel fails at startup like any other effect error.

## Location

Effect definitions live in `configs/effects/*.yaml`. One file per effect. The file stem is
informational; the effect identity is the `id` field.

## Schema

```yaml
id: card_prediction              # required, unique, kebab/snake case
title: The Card                  # required, human-readable
description: "..."               # required, shown on the landing screen
hypothesis_space:                # required
  type: deck_52                  # builtin | range | enumerated
prior: uniform                   # optional: "uniform" | mapping of hypothesis id -> weight
termination:                     # required
  entropy_threshold_bits: 0.25   # commit when posterior entropy <= this
  max_turns: 8                   # forced best-guess commit after this many questions
questions:                       # required, >= 1, unique ids
  - id: q_color                  # required, unique within effect
    text: "Is your card red, or black?"   # asked to the participant (rendered theatrically by LOKI-Language)
    reliability: 0.95            # optional, in (0, 1]; P(truthful answer). Default 0.9
    answers:                     # required, >= 2, unique ids
      - id: red                  # required
        label: Red               # required, shown on the answer buttons
        predicate:               # required — which hypotheses this answer matches
          attr: color            # attribute present on EVERY hypothesis (validated at load)
          op: eq                 # eq | ne | gt | gte | lt | lte | in | between | mod_eq
          value: red             # for `in`/`between`: list [lo, hi]; for `mod_eq`: remainder, plus `mod: k`
```

## Hypothesis space builtins

| type | expands to |
|---|---|
| `deck_52` | 52 cards; attrs: `name`, `suit`, `color`, `rank`, `rank_value` (A=14), `rank_class` (`ace`/`number`/`face`) |
| `range` | `{min: a, max: b}` integers; attrs: `value`, `first_digit` (0 for single digits), `digit_sum` |
| `enumerated` | `items:` list of `{id: ..., <attrs>}` — every key except `id` becomes an attribute |

Hypothesis attributes are immutable facts about the hidden target. Behavioral/observational
signals (gaze, latency, prosody) are **not** hypothesis attributes and never enter this schema;
they arrive as evidence via the event schema in later phases.

## Likelihood model (Stage A — classical baseline)

For question `q` with answer set `A` and reliability `r`:

- `P(answer=a | true hypothesis h) = r` if `a.predicate` matches `h`'s attributes
- `= (1 - r) / (|A| - 1)` otherwise (uniform spread over non-matching answers)

This is deliberately interpretable and non-neural: the Bayesian baseline must be understandable
before any learned evidence model (plan §7 Stage A, §16).

## Policy interface

The policy (Phase 1: information gain; ROADMAP Phase 2: information gain + method selection;
later: bandit/RL) selects the next action from:

- `ask(question_id, mode)` — never repeats a question already asked in the session; `mode` is
  `direct` (question + options) or `covert` (assertion of one option + agreement scale)
- `commit()` — reveal the MAP hypothesis

Termination: commit when posterior entropy ≤ `entropy_threshold_bits`, or when `max_turns`
questions have been asked, or when no unasked question carries positive information gain.
A forced commit under high entropy is allowed but MUST be phrased with hedged confidence by
LOKI-Language (calibration rule, plan §4.8 — no fabricated certainty).

## Out of scope for v1 (planned, do not hack in)

- Multi-participant effects, physical props, AR (plan §5 longer-term)
- Observation types beyond `verbal_response` (gaze/head pose/latency arrive with Phase 2+;
  `latency_ms` is recorded in events from day one so the schema does not change later)
- Decoy/misdirection actions (`show_decoy`) — action space is versioned; Phase 1 is ask/commit
