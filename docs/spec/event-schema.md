# Spec: Event Schema (v1.1)

Status: **Active — Phase 0–2**

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
