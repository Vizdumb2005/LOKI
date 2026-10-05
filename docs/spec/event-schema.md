# Spec: Event Schema (v1.5)

Status: **Active — Phase 0–5**

Every state change in a LOKI session is recorded as a structured event. This is the seed of the
"structured event bus between components" (plan §9 Backend) and of the end-to-end replay harness
(plan §9 Experimentation, Phase 3 "replayable sessions").

## v1.1 additions (Phase 2 — multimodal observations)

| type | emitted by | payload |
|---|---|---|
| `observation.recorded` | engine via `observe()` | `{channel, question_id, answer_id, answer_label, dwell_ms, reliability, entropy_before, entropy_after, top_hypothesis_id, top_probability}` |

- `hypothesis.updated` gains an optional `utterance` (verbatim transcript when the answer was
  spoken; `null` otherwise). Utterances are consent-gated: they live in the in-memory session
  and reach disk only through the explicit archive flow.
- Raw media is still forbidden in every payload — the observation event carries the *derived*
  signal only (which answer button, how long), never the frames/audio it came from.

## v1.2 additions (ROADMAP Phase 2 — interaction modes)

Additive payload fields; no new event types. Normative behavior: docs/covert-fishing.md.

| event | new fields |
|---|---|
| `policy.decision` | `mode` ("direct" \| "covert"), `asserted_answer_id` (null on direct turns); `reason` may additionally be `credible_assertion`, `backoff_after_misses`, `cooldown_after_misses`, `budget_reserve`, `covert_budget_spent` |
| `hypothesis.updated` | `mode`, `agreement_strength` (null on direct turns; one of `strong_yes`, `lean_yes`, `unclear`, `lean_no`, `strong_no`), `asserted_answer_id` (null on direct turns); `utterance` now records any verbatim participant text — spoken transcript OR typed `free_text` reply — under the same consent semantics as before |
| `observation.recorded` | unchanged; observations apply to direct turns only (a covert turn shows agreement reactions, not options to dwell on) |

## v1.3 additions (ROADMAP Phase 3 — reveal planning)

Additive payload fields; no new event types. Normative behavior: docs/reveal-planning.md.

| event | new fields |
|---|---|
| `policy.decision` | `reframe` (`"missed"` \| `"unclear"` \| `null`) — the equivocation beat that opens this turn after a missed/unclear covert read |
| `effect.revealed` | `reveal_path` (`progressive` \| `category_cluster` \| `dual_deduction` \| `plain`), `reveal_candidates` (top-k hypothesis ids the staging considered), `stages` (structured descriptors `{kind, attr, label}` — attribute/category/deduction beats; no prose in events) |

## v1.4 additions (ROADMAP Phase 4 — choice architecture)

Additive payload fields; no new event types. Normative behavior: docs/choice-architecture.md.

| event | new fields |
|---|---|
| `policy.decision` | `force_target` (option id the UI emphasizes on direct turns, or `null`) — the click remains a plain Bayesian answer; `SessionView` exposes it as `salient_option_id` and the curtain discloses it |

## v1.5 additions (ROADMAP Phase 5 — passive-signal fusion)

Additive payload fields; no new event types. Normative behavior: docs/passive-signals.md.

| event | new fields |
|---|---|
| `hypothesis.updated` | `reliability_effective` (the latency-modulated reliability of the verbal answer when the effect declares a `response_latency` channel and a latency was measured, else `null` — a slow answer is discounted toward the channel floor, a fast one keeps its base), `agreement_strength_effective` (the typing-rhythm-downgraded strength when a hesitant free-text reply was softened one step, else `null`), `typing_rhythm` (`{first_key_ms, median_interval_ms, total_ms}` — aggregate numbers only, never key content or raw timing sequences; rides the free_text consent semantics) |

## Normative implementation

`services/effects/events.py` (Pydantic models). In Phase 1 events are appended to the in-memory
session history; a persistent/bus transport arrives with the capture services (Phase 2+). The
module is deliberately dependency-free so any component can emit events without importing the
engine.

## Envelope

Every event has:

| field | type | notes |
|---|---|---|
| `event_id` | UUID4 string | unique per event |
| `session_id` | string | the session this belongs to |
| `ts` | ISO-8601 UTC timestamp | `datetime.now(timezone.utc)` |
| `type` | enum string | see registry below |
| `payload` | object | type-specific; validated by the matching payload model |
| `schema_version` | integer | currently `1` |

## Event registry (v1)

| type | emitted by | payload |
|---|---|---|
| `session.started` | engine on session creation | `{effect_id, initial_entropy_bits, hypothesis_count}` |
| `policy.decision` | policy | `{action, question_id?, info_gain_bits?, alternatives_considered, reason}` |
| `hypothesis.updated` | engine after each answer | `{question_id, answer_id, latency_ms?, entropy_before, entropy_after, top_hypothesis_id, top_probability}` |
| `effect.revealed` | engine on commit | `{prediction_id, prediction_label, confidence, turns_used, committed_because}` where `committed_because ∈ {entropy_threshold, max_turns, no_informative_question}` |
| `participant.outcome` | engine on outcome report | `{correct, turns_used}` |

## Rules

1. Events are **append-only**. Nothing mutates history; corrections are new events.
2. Events carry **no raw media and no free-form prose** — structured payloads only. Raw media
   is ephemeral by default and never enters the event stream (plan §11).
3. The posterior trajectory used by evaluation/replay is derived from `hypothesis.updated`
   events, not stored separately.
4. `participant.outcome` is the only event carrying ground truth; it exists so evaluation
   (plan §12) and the future LOKI Interaction Dataset (plan §6) can be derived from the same
   records. In Phase 1 it is held in memory for the lifetime of the session only.
