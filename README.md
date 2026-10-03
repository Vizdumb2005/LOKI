# LOKI — Digital Mentalist

A multimodal AI mentalism research prototype: LOKI creates convincing "mind reading" effects
through explicit hypothesis spaces, Bayesian inference, information-gain questioning, and
theatrical presentation. It is not telepathy — the full idea lives in the project plan
(`../idea.md` in the workspace parent; specs in [`docs/spec/`](docs/spec/)).

> North star (plan §17): not *"I know what you are thinking"* but **"I know what to do next."**

## Status — phase tracker

| Phase | Scope | Status |
|---|---|---|
| 0 — Specification | effects/event schemas, evaluation protocol, model + license registries | ✅ done |
| 1 — Akinator-style engine | Bayesian tracker, info-gain policy, effect engine, web UI (text-only) | ✅ done |
| 2 — Multimodal perception | webcam + gaze dwell, voice answers — in-browser, privacy-first | ✅ slice shipped (The Card) |
| 3 — Fusion | structured multimodal state, replayable sessions | not started |
| 4 — Policy | participant simulator, bandit, offline evaluation | simulator seed only |
| 5–7 | in-house models, performance, product | not started |

## What Phase 1 contains

- **Four effects** (`configs/effects/*.yaml`): *The Card* (52 hypotheses), *The Number* (1–100),
  *The Beast* (34 animals — the Akinator flagship), and *The Sigil* (6 symbols, quickworking).
  Effects are declarative state machines — hypothesis space, questions with predicates,
  reliability (answer noise), termination criteria.
- **LOKI-Hypothesis** (`services/hypothesis/`): Bayesian posterior tracking, entropy in bits.
- **LOKI-Policy** (`services/policy/`): maximum expected information gain question selection,
  with no-repeat and commit-when-exhausted rules.
- **Effect Engine** (`services/effects/`): per-session state machine, append-only event history
  (see [`docs/spec/event-schema.md`](docs/spec/event-schema.md)).
- **LOKI-Language** (`services/language/`): deterministic Loki-persona templates. Reveal phrasing
  is driven by posterior confidence bands — the surface never fabricates certainty (plan §4.8).
- **API** (`services/api/`): FastAPI. Gameplay stays in memory; the **parlor's ledger**
  (`services/api/archive.py`) is a consent-gated SQLite record — a séance is only written when
  the participant explicitly opts in on the outcome screen, and every record can be deleted
  (plan §6, §11).
- **Web app** (`apps/web/`): React + TypeScript + Vite; a "peek behind the curtain" panel with
  the live posterior and an entropy sparkline ("the narrowing"), keyboard answering (1–9), and
  the ledger with deletion controls — transparency as a product feature (plan §12).
- **Simulator seed** (`simulator/`) + **evaluation CLI** (`experiments/`), now with a gaze
  behavior model (`--gaze-prob`) for measuring what weak observations add.

## Phase 2 — perception, privacy-first (slice shipped)

*The Card* offers two sensing channels; every other effect stays word-only:

- **Gaze dwell** — MediaPipe FaceLandmarker runs entirely in your browser (WebGL/GPU with WASM
  fallback). Head pose + iris direction produce a coarse screen point; lingering on an answer
  button ≥ 400 ms emits a `gaze_dwell` observation — *weak* evidence (reliability 0.55) that
  moves the posterior without advancing the session. Parlor-grade, not precision eye-tracking;
  the curtain says so.
- **Voice answers** — push-to-talk via whisper-tiny.en running in-browser (Transformers.js,
  WebGPU when available, WASM otherwise; ~50 MB model downloaded once, then cached). The
  transcript resolves against per-answer synonyms; ambiguous or unmatched speech submits
  nothing. The verbatim utterance is recorded on the answer event (consent-gated via the ledger).

**Hard privacy rules** (plan §11, enforced in code): raw frames and audio never leave the
browser and are never stored; the camera runs only while questions are on the table, behind an
explicit opt-in with a visible indicator and a one-click Stop; permission denied means a fully
functional word-only séance; every observation is a structured event visible in the curtain.

## Quickstart

Backend (Python ≥ 3.11):

```bash
python -m venv .venv
.venv/Scripts/pip install -e ".[dev]"        # Windows; Linux/mac: .venv/bin/pip
.venv/Scripts/python -m pytest               # test suite
.venv/Scripts/python -m uvicorn services.api.main:app --port 8000
```

Frontend (Node ≥ 20):

```bash
cd apps/web
npm install
npm run dev                                  # http://localhost:5173 (proxies /api → :8000)
npm run build                                # tsc strict + production bundle
```

Evaluation (reproducible, seeded — protocol in [`docs/spec/evaluation-protocol.md`](docs/spec/evaluation-protocol.md)):

```bash
python -m experiments.run_baseline_eval --sessions 500 --seed 42
python -m experiments.run_baseline_eval --effect card_prediction --reliability 0.8   # noise sweep
```

## Recorded baseline (400 sessions, seed 42, per-question YAML reliability ≈ 0.92–0.98)

| effect | top-1 accuracy | avg turns | entropy at commit | forced-commit rate |
|---|---|---|---|---|
| card_prediction | 0.900 | 5.38 | 0.44 bits | 0.15 |
| number_prediction | 0.897 | 6.42 | 0.56 bits | 0.54 |
| animal_guess | 0.885 | 9.25 | 0.51 bits | 0.63 |
| sigil_forced_choice | 0.983 | 3.31 | 0.13 bits | 0.02 |

Under fully truthful answers all four effects resolve every hypothesis correctly (enforced by
tests — 192 exhaustive sessions). The remaining forced commits under noise are inherent: the
engine can't distinguish a noisy answer from a lie, so it keeps rivals alive — that is the
calibrated behavior we want. `animal_guess`'s higher forced rate marks it as the next effect to
get more orthogonal questions (the metric is doing its job).

**Gaze-augmented** (same seed, `--gaze-prob 0.7` — simulated participants linger on the answer
they intend 70% of the time; only `card_prediction` declares the channel):

| effect | top-1 accuracy | avg turns | forced-commit rate | obs/session |
|---|---|---|---|---|
| card_prediction | **0.917** | **4.71** | 0.20 | 3.30 |

vs 0.900 / 5.38 verbal-only — weak evidence, measured like any other component (Stage E
philosophy: the simulator validates fusion before any human data).

## Repository layout

```text
apps/web/            React + TypeScript frontend
services/            api (incl. consent-gated ledger), effects, hypothesis, policy, language
                     (+ capture/vision/audio/fusion placeholders)
configs/effects/     effect definitions (YAML state machines)
configs/registries/  model registry (machine-readable)
datasets/            manifests, schemas, LICENSES.md (raw media is git-ignored)
data/                consent-gated session ledger (sessions.db) — git-ignored
simulator/           participant simulator (Phase 1: truthful-noisy answerer)
experiments/         evaluation CLI + recorded outputs
tests/               pytest suite (engine, policy, loader, archive, API, language)
docs/spec/           normative schemas: effects, events, evaluation protocol
```

## Ground rules for contributors (and agents)

See [`AGENTS.md`](AGENTS.md) for the full working agreement. Non-negotiables:

- Phases in order; specs before features; every effect evaluated before it ships.
- LOKI-Language renders; it never estimates truth. Fusion emits structured state, never prose.
- Camera/mic is opt-in and session-scoped; raw media is ephemeral by default; nothing sensitive
  (health, beliefs, credentials…) is ever an inference target.
- No third-party model without a pinned revision and re-verified license.

## License

MIT — see [LICENSE](LICENSE).
