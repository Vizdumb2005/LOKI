# AGENTS.md — LOKI Workspace Instructions

## What this project is

LOKI ("Digital Mentalist") is a multimodal AI magic/mentalism research prototype: it creates
convincing "mind reading" effects via camera/microphone sensing, dialogue, probabilistic
inference, and theatrical presentation — **not** literal telepathy. The authoritative project
plan is `C:\Users\viren\Downloads\idea.md` (outside this workspace). Read it before changing
architecture, effects, models, or privacy behavior.

**Current state:** Phase 0 (specifications), Phase 1 (Akinator-style engine + web UI + consent
ledger), and the Phase 2 perception slice (gaze dwell + voice answers, in-browser) are
implemented. Two text-only effects plus The Card with a `gaze_dwell` channel; FastAPI surface;
React frontend with in-browser MediaPipe gaze and Whisper ASR; seeded evaluation CLI including
a gaze-augmented mode. Remaining Phase 2 work and later phases per README's status table.
`services/capture|fusion` are still placeholder docstrings — perception lives client-side in
`apps/web/src/perception/`.

## Verified commands (repo root; Windows Git Bash uses `.venv/Scripts/`)

```bash
python -m venv .venv && pip install -e ".[dev]"
python -m pytest                                              # full suite
python -m experiments.run_baseline_eval --sessions 500 --seed 42
python -m experiments.run_baseline_eval --effect card_prediction --gaze-prob 0.7
python -m uvicorn services.api.main:app --port 8000           # backend on :8000
cd apps/web && npm install && npm run dev                     # frontend on :5173, proxies /api
npm run build                                                 # tsc strict + vite build
npm test                                                      # vitest (dwell + matcher)
python -m ruff check . && python -m ruff format .             # lint + format
```

Test suite: `tests/test_engine.py` resolves **every** hypothesis of both effects with truthful
answers — keep that invariant when touching tracker, policy, engine, or effect YAMLs. After any
effect change, run the eval CLI; a rising `forced_commit_rate` means the question set is too
weak (this metric has already caught two under-informative effects).

## Software engineering lifecycle (how to work here)

The project is implemented strictly by phases, each leaving the system measurable and runnable:

- **Phase 0 — Specification first.** Before feature code: effects schema, event schema, model
  registry, license registry, evaluation protocol. Specs live in `docs/` and `configs/`.
- **Phase 1 — Akinator-style engine** (explicit hypothesis space, Bayesian updates, question
  selection, basic web UI) before **Phase 2 — multimodal perception** (webcam/mic, ASR, gaze)
  and later fusion/policy/RL phases.
- **Do not** start by training one giant multimodal model. Research order is fixed:
  interpretable Bayesian baseline → task-specific perception → temporal fusion → learned
  evidence models → contextual bandit → constrained RL → integrated system.
- Organize tasks, tests, and resources systematically per phase; keep every improvement
  measurable (see Evaluation section of the plan: prediction ability and perceived magic are
  measured separately).

## Planned repository layout

```text
apps/web/          React + TypeScript frontend (browser camera/mic, WebRTC)
services/          capture, vision, audio, language, fusion, hypothesis, policy, effects, api
models/            loki-vision, loki-audio, loki-fusion, loki-hypothesis, loki-policy,
                   loki-language, loki-calibrator
datasets/          manifests/, schemas/, raw/, processed/, LICENSES.md
simulator/         participant simulator (required before any RL)
effects/           effect definitions (YAML state machines)
experiments/, configs/, tests/, docs/
```

## Architecture boundaries (non-negotiable)

- **LOKI-Fusion** outputs *structured session state* (JSON: observations, hypothesis
  distribution, uncertainty), never free-form prose.
- **LOKI-Language** only renders dialogue/theatrics from structured state. It must not perform
  truth estimation or decide predictions.
- **LOKI-Hypothesis** is the explicit probabilistic layer (Bayesian updates; keep competing
  hypotheses alive; premature commitment is a bug).
- **LOKI-Calibrator** is independent (ECE, Brier, reliability curves). The theatrical
  presentation layer must never convert weak evidence into unjustified certainty.
- **Effects are formal state machines** (hypothesis space, allowed observations, action space,
  termination criteria, reveal), not generic conversations.
- Backend: Python + FastAPI + WebSocket/WebRTC + structured event bus between components.
  Storage: SQLite locally, PostgreSQL for multi-user; raw media only with explicit retention.

## Privacy & safety rules (hard constraints)

- Camera/mic access: opt-in, session-scoped, visibly indicated, local-first where practical.
  Raw media is ephemeral by default; retention and deletion require explicit consent/controls.
- Never build inference of medical conditions, mental health, political beliefs, religion,
  sexual orientation, passwords/secrets, or financial credentials. Behavioral features are
  evidence for an explicit game/effect only — this is not a psychological profiling system.

## Licensing / provenance rules

- Prefer MIT / Apache-2.0 / BSD / compatible CC. Record repo ID, exact revision, license,
  provenance, restrictions in `datasets/LICENSES.md` / model registry.
- Hosting on Hugging Face does **not** mean a model/dataset is usable.
- Known-allowed initializations: `openai/whisper-small` (Apache-2.0),
  `openai/whisper-large-v3-turbo` (MIT), `ai4bharat/indic-conformer-600m-multilingual` (MIT,
  gated), `pyannote/speaker-diarization-3.1` (MIT, gated),
  `ehcalabres/wav2vec2-lg-xlsr-en-speech-emotion-recognition` (Apache-2.0).
- **Excluded** from the commercial-friendly base:
  `audeering/wav2vec2-large-robust-12-ft-emotion-msp-dim` (CC-BY-NC-SA-4.0).
- Re-verify license metadata before any release; hub terms can change.

## Known gotchas

- **YAML 1.1 booleans:** in effect YAMLs, unquoted `yes`/`no`/`on`/`off` parse as booleans.
  Quote answer ids/labels (`id: "yes"`). This bit us once — the loader rejects the result loudly,
  which is correct.
- **Effect partition rule:** for every (question, hypothesis) pair, exactly one answer predicate
  must match; the loader fails at startup otherwise. New effects need this verified across the
  whole hypothesis space — the parametrized exhaustive test does it automatically for every
  registered effect.
- **Consent-gated ledger (hard rule):** gameplay NEVER writes to disk. The only write path is
  `POST /api/sessions/{id}/archive` after explicit user consent, and `DELETE /api/archive/{id}`
  must keep working. The SQLite schema lives in `services/api/archive.py`, versioned via
  `PRAGMA user_version`; the db is `data/sessions.db` (git-ignored).
- **No raw media, ever (hard rule):** camera/microphone processing happens in the browser
  (`apps/web/src/perception/`); frames and audio never leave the machine and never enter events,
  the API, or the archive. Only derived observation events (`observation.recorded`) and
  consent-gated utterances cross the boundary. Observations are weak evidence: they never
  advance a question or trigger termination.
- **CDN pins are coupled:** `apps/web/src/perception/gazeTracker.ts` hardcodes the
  tasks-vision wasm URL at the exact installed npm version — bump it together with
  `apps/web/package.json` and the model registry entry. Whisper resolves its ONNX from the Hub
  at runtime; pin a revision before any redistribution.
- **vitest is pinned to v3** while the frontend uses vite 5 (vitest 4+/5 requires vite 6+).
  Upgrade both together.
- **The camera `<video>` element must always be mounted** (hidden via CSS, never conditionally
  rendered): `useSensing.start()` reads the ref before the permission prompt appears — a
  conditionally-rendered element makes the ref null and the click silently no-ops. This bug
  shipped once; don't reintroduce it.
- **Language renderer boundary:** templates receive structured state only. Never pass raw
  posteriors or hypotheses into user-facing phrasing decisions beyond the confidence band.
- **Sessions are memory-only by design** (privacy, plan §11) — do not "fix" persistence without
  a consent story.
- **Vite dev server binds `localhost` (IPv6 `::1`)** on this machine — curl
  `http://localhost:5173|4173`, not `127.0.0.1`.
