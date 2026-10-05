# LOKI Current State (Phase 0 audit, 2026-10-05)

Verified by inspection, not by README claims. Evidence paths inline.

## Capability matrix

| Capability | Exists | Partial | Placeholder | Missing | Evidence |
|---|:--:|:--:|:--:|:--:|--|
| Bayesian inference | x | | | | `services/hypothesis/tracker.py` (`Tracker.update/top_k/entropy`), `metrics.py` |
| Effect engine | x | | | | `services/effects/engine.py` (`EffectSession`, 192 exhaustive sessions pass) |
| Effect library | | x | | | 4 YAMLs in `configs/effects/` (card, number, animal, sigil); flagship Card only polished one |
| Session state | | x | | | Memory-only `EffectSession.history: list[Event]`; no unified `SessionContext`/reducer/replay |
| Brain / action contract | | x | | | `policy/method_selection.py` (`TurnPlan`: direct/covert/forced) + `policy/reveal_planner.py` path choice; no `services/brain/` or OBSERVE/WAIT/REFRAME actions |
| Learned policy | | x | | | `simulator/bandit.py` tabular ε-greedy + `run_bandit_eval.py`; heuristic still serves traffic |
| Participant model | | x | | | `simulator/profiles.py` + noisy participant params; no learned estimator |
| Dialogue model | | | | x | `language/renderer.py` banded templates + `fishing.py`/`equivocation.py`; no learned generator |
| Stage UI | | | | x | Q&A flow (`Session.tsx` conditionals, `Phase="active\|revealed\|outcome"`); no `stage/` state machine |
| Perception (browser) | | x | | | `apps/web/src/perception/` gaze dwell + whisper-tiny ASR + matcher; server `capture/vision/audio` are docstring-only placeholders |
| Passive fusion | | x | | | `services/fusion/engine.py` pure modulations (latency discount, typing downgrade); full temporal fusion still future |
| Covert fishing | x | | | | `language/fishing.py` + `response_signals.py` + agreement soft-updates (κ sweep, κ\*≈0.33–0.40) |
| Forcing / choice arch | x | | | | `apps/web/src/lib/forcing.ts`, salient-option glow, disclosed curtain |
| Reveal planning | x | | | | Path (`policy/reveal_planner.py`) vs staging (`language/reveal_planner.py`) split + equivocation reframes |
| Human evaluation | | x | | | `run_human_trial.py` + `human-trials.md` apparatus; no recorded trials |
| Production | | | | x | No auth, rate-limit, model serving/versioning, monitoring, deployment |

## Notes

- ROADMAP Phases 1–5 checkboxes are plausible except Phase 5, which is weak-signal
  modulation labeled as full fusion (`models.yaml` itself still says `loki-fusion: planned`).
- `docs/registries/model-registry.md` is stale vs `configs/registries/models.yaml`
  (vision/audio/asr `planned` vs `prototyped`). Machine-readable YAML wins.
- `docs/architecture/` (this dir) was empty; real arch doc is `docs/architecture.md`.
- Privacy invariants hold: browser-only raw media, consent-gated archive, memory-only sessions.
