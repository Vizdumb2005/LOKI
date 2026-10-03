# Model Registry

The machine-readable registry is [`configs/registries/models.yaml`](../../configs/registries/models.yaml).
This document explains the registry's purpose and rules; the YAML is the source of truth.

## Purpose

Every intelligence component of LOKI is either built in-house or initialized from a vetted
third-party model (plan §4, §15). The registry tracks the status of each component so any agent
or contributor can see what exists, what is planned, and which external models are cleared for
use — before touching `models/` or `datasets/`.

## Rules for adding or changing entries

1. A third-party model may only be **downloaded or fine-tuned** after its registry entry has a
   pinned `revision` and re-verified license metadata. `revision: null` means "not cleared".
2. Gated models (requiring Hub approval) are recorded with `gated: true`; access acceptance
   must be noted in the entry before use.
3. License re-verification is required before any release — Hub terms can change (plan §15).
4. Every entry states its intended use. Behavioral features are evidence for explicit effects
   only, never general-purpose psychological profiling (plan §11).
5. The excluded list in [`datasets/LICENSES.md`](../../datasets/LICENSES.md) is authoritative:
   models listed there must not be added as dependencies or baselines.

## Current component status (2026-10)

| component | status | where |
|---|---|---|
| loki-hypothesis | implemented (Stage A classical baseline) | `services/hypothesis/` |
| loki-policy | implemented (information-gain policy) | `services/policy/` |
| loki-language | implemented (template renderer, no LM) | `services/language/` |
| loki-vision / loki-audio / loki-asr | planned — Phase 2 | — |
| loki-fusion | planned — Phase 3 | — |
| loki-calibrator | planned — Phase 5 (Phase 1 uses confidence-band phrasing) | — |

No third-party model weights are vendored in Phase 0/1.
