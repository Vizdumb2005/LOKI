# Spec: Effect Schema (v1.1)

Status: **Active — Phase 0–2** (versioned; additive changes bump the version below)

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

The policy (Phase 1: information gain; later: bandit/RL) selects the next action from:

- `ask(question_id)` — never repeats a question already asked in the session
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
