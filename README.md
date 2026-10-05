# LOKI — Digital Mentalist

An AI mentalism research prototype: LOKI creates convincing "mind reading" illusions
through explicit hypothesis spaces, Bayesian inference, information-gain questioning, and
theatrical presentation. Sensing slices (in-browser gaze dwell and voice answers on *The Card*)
and passive signals (latency, typing rhythm) modulate evidence reliability and response interpretation
via pure reliability discounting (services/fusion/engine.py).
It is not telepathy — the full idea lives in the project plan (`../idea.md` in the workspace parent; specs in [`docs/spec/`](docs/spec/)).

> North star (plan §17): not *"I know what you are thinking"* but **"I know what to do next."**

## Status — phase tracker (ROADMAP.md Alignment)

| Phase | Scope | Status |
|---|---|---|
| 0 — Specification | effects/event schemas, evaluation protocol, model + license registries | ✅ done |
| 1 — Research & Foundations | taxonomy, digital translation, magic factor metric framework ($M(\kappa) = \frac{\text{Accuracy}}{1 + I_{\text{visible}}(\kappa)}$) | ✅ formal (κ calibrated in Phase 6) |
| 2 — Covert Fishing | cold reads, agreement-strength responses, soft Bayesian updates | ✅ done |
| 3 — Multi-Outs & Reveal | progressive attribute ladder, category cluster, hesitation, equivocation | ✅ done |
| 4 — Choice Architecture | visual saliency, default positioning, delayed emphasis onset | ✅ done |
| 5 — Passive Signal Fusion | response latency modulation, typing rhythm aggregates, gaze dwell | ✅ done |
| 6 — RL Policy & Human Trials | contextual bandit simulator built, double-blind A/B apparatus built (awaiting human trials) | 🔄 active |

## Project status — teamwork milestones (2026-10-05)

| Milestone | Scope | Status |
|---|---|---|
| M1 — Hygiene, Resilience & Core Engine | UTF-8 CLI guards, orphan-survey deletion fix, adversarial + concurrency suites | ✅ PASS (gate: 2 reviewers, 2 challengers, auditor CLEAN) |
| E2E track — Tiers 1–4 | 235 opaque-box tests (features, boundaries, interactions, séance scenarios) | ✅ CERTIFIED (235/235) |
| M2 — Metric Foundation & Visibility | breakeven κ\* inlined, 2,000-resample Likert estimator, κ sweep on every run | ✅ PASS (gate: 2 reviewers, 2 challengers, auditor CLEAN) |
| M3 — Research Questions Evidence Matrix | all 16 §13 RQs on canonical tiers; magic-factor/covert docs harmonized | ✅ PASS WITH NOTES (Q12 traceability + Q3 66% arithmetic logged as follow-ups) |
| M4 — Human Trial & Evaluation Pipeline | double-blind CLI + web séance runners, consent-gated ledger, A/B stats incl. replay willingness, web debrief disclosure | ✅ PASS WITH NOTES (485 tests green; 0 human rows — trials pending) |
| M5 — Final E2E & Adversarial Hardening | full suite green, Tier-5 challenger pass, `analyze()` junk-row hardening, Likert 0/8 test | ✅ PASS (485/485, 0 ruff; Tier-5: no pipeline-reachable holes) |

Run a human trial: `python -m experiments.run_human_trial --effect card_prediction`
(follow the consent prompts; debrief is shown to every participant), then
`python -m experiments.analyze_ab` for Mann-Whitney U, Welch's t, and 95% bootstrap CIs.
`python -m experiments.analyze_ab --simulated 60` exercises the pipeline on labeled placeholder data.

**ROADMAP phase 2 — Covert Fishing & Dialogue Strategy** (`ROADMAP.md`, the perceived-impact
prioritization): ✅ done — fishing assertions, agreement-strength responses with soft Bayesian
updates, and the Method Selection Policy ([`docs/covert-fishing.md`](docs/covert-fishing.md)).

**ROADMAP phase 3 — Multi-Outs & Reveal Planner**: ✅ done — the reveal is now staged through
pre-planned "outs" ([`docs/reveal-planning.md`](docs/reveal-planning.md)): a **progressive**
attribute ladder on decisive commits ("…a red card… six or seven… the Seven of Diamonds"), a
**category-cluster** beat when the top two share a family (a landed hit even if the identity
misses), a **dual-deduction** beat when two candidates dominate, and one **hesitation** beat
inside the calibrated doubt window (0.60–0.85 — it only ever adds doubt). Missed reads get an
**equivocation** reframe line instead of visible backtracking. The prediction and its
confidence-banded phrasing are untouched — staging moves the reveal moment, not the posterior.

**ROADMAP phase 4 — Choice Architecture & Forcing**: ✅ done — on direct turns with a credible
favorite (≥ 0.60 posterior mass), the UI applies three biasing primitives toward it
([`docs/choice-architecture.md`](docs/choice-architecture.md)): warm **saliency** that fades in
only after ~1.2 s (delayed emphasis onset — countdowns/disabled buttons are deliberately
rejected), **default positioning** (the salient option moves first), and nothing else: no
coercion, keyboard untouched. The click remains a plain Bayesian answer; a **defied** force is
folded into the performance (an equivocation reframe) and the primitives sit out a turn; the
curtain **discloses** the steering ("this turn: steering toward X"). Simulator gates: accuracy
within ±0.02 of the forcing-off arm on all effects but sigil (−0.022 at the boundary); force
success rates 0.77–0.90 in the mechanical noise-concentration model — real priming psychology
is a human-study question (ROADMAP Phase 6).

**ROADMAP phase 5 — Passive Signals & Multimodal Fusion**: ✅ done — `services/fusion` (a
placeholder since Phase 0) now fuses the three weak channels into one Bayesian update
([`docs/passive-signals.md`](docs/passive-signals.md)): **response latency** modulates how much
a verbal answer is worth (fast ≤ 2 s keeps full reliability; hesitant ≥ 8 s is discounted to
60% — a guess counts less), and **typing rhythm** on free-text replies (three aggregates:
time-to-first-key, median inter-key interval, total — never key content, never raw sequences)
downgrades a hesitant reply's agreement strength one step. Gaze dwell (Phase 2) completes the
trio. Measured (500 sessions, seed 42, fusion on vs `--no-fusion`):

| effect | accuracy OFF → ON | forced-commit OFF → ON |
|---|---|---|
| animal_guess | 0.884 → **0.912** | 0.68 → 0.72 |
| card_prediction | 0.910 → **0.940** | 0.43 → 0.64 |
| number_prediction | 0.882 → **0.890** | 0.65 → 0.73 |
| sigil_forced_choice | 0.962 → **0.986** | 0.04 → 0.12 |

The honest trade: discounted guesses make the MAP land on the truth more often (+0.8 to
+3.0 points on every effect — the first fusion mechanism with a measurable simulated win), but
weakened evidence gathers fewer bits per turn, so forced commits rise and the mystery gap
narrows slightly. The hedged reveal band phrases those commits honestly. Calibration of the
fast/slow/floor knobs on real participants is ROADMAP Phase 6.

```bash
python -m experiments.run_magic_factor_eval --sessions 500 --seed 42               # fusion on
python -m experiments.run_magic_factor_eval --sessions 500 --seed 42 --no-fusion   # off arm
```

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

## Phase R2 — covert fishing & the dialogue strategy engine

Instead of only asking explicit questions ("Is your card red, or black?"), LOKI can now make a
**cold read** ("I get a strong impression here, and it points at Red. Isn't it?") and parse the
reply in natural language — typed, spoken, or via three agreement buttons ("Yes, exactly" /
"Sort of…" / "Not really"). A Method Selection Policy mixes the two modes per turn; see
[`docs/covert-fishing.md`](docs/covert-fishing.md) for the normative spec.

Design constraints kept intact: effects remain formal state machines; agreement updates are
soft (every hypothesis stays alive — a denial eliminates only the asserted reading); unclear
replies touch nothing; the reveal never borrows confidence the posterior doesn't have. The
policy only fishes binary, credible, high-information dimensions, backs off after any miss,
and rations itself to one read per session — all measured choices, not taste.

**Measured** (1000 simulated sessions, seed 42, gaze_prob 0.5; direct arm = every question
explicit; visible-bit accounting per [`docs/magic-factor.md`](docs/magic-factor.md) §2.1 —
covert turns weigh κ·log₂(3), headline κ = 0.25):

| effect | accuracy auto / direct | forced auto / direct | M auto / direct @ κ=0.25 |
|---|---|---|---|
| animal_guess | **0.891** / 0.889 | 0.658 / 0.635 | **0.0747** / 0.0734 |
| card_prediction | **0.911** / 0.905 | 0.409 / 0.255 | **0.1000** / 0.0968 |
| number_prediction | **0.884** / 0.876 | 0.638 / 0.581 | **0.0748** / 0.0729 |
| sigil_forced_choice | 0.973 / **0.982** | 0.035 / 0.021 | **0.2318** / 0.2245 |

Honest reading: at κ = 0.25 the mixed policy wins accuracy and the magic factor on three of
four effects and never loses meaningfully; the price is a higher forced-commit rate on
question-limited effects (trading direct questions for covert reads spends turns on graded reactions;
with `covert_ratio: 0.20`, effects with max_turns >= 10 permit 2 reads, raising forced commits
from 0.658 to 0.751 on animal_guess). The **breakeven is κ\* ≈ 0.33–0.40**: fishing improves the
magic factor exactly when participants perceive a statement-reaction as less than ~⅓ as interrogating
as an explicit question — a human-study question (ROADMAP phase 6), not an assumption. The harness reports
the full κ sweep on every run; κ = 1.0 (fully visible) is the conservative bound under which
fishing loses everywhere. Reads land 53–68% of the time in simulation (`fishing_affirmation_rate`).

```bash
python -m experiments.run_magic_factor_eval --sessions 1000 --seed 42   # auto policy + κ sweep
python -m experiments.run_magic_factor_eval --sessions 1000 --seed 42 --policy direct
python -m experiments.run_baseline_eval --sessions 400 --seed 42        # direct-mode baseline
```

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

## Recorded baseline (direct mode, 400 sessions, seed 42, per-question YAML reliability ≈ 0.92–0.98)

| effect | top-1 accuracy | avg turns | entropy at commit | forced-commit rate |
|---|---|---|---|---|
| card_prediction | 0.922 | 5.30 | 0.46 bits | 0.15 |
| number_prediction | 0.902 | 6.53 | 0.55 bits | 0.58 |
| animal_guess | 0.885 | 9.25 | 0.51 bits | 0.63 |
| sigil_forced_choice | 0.975 | 3.36 | 0.13 bits | 0.03 |

(run `python -m experiments.run_baseline_eval --sessions 400 --seed 42` — `--mode direct` is
the default so numbers stay comparable across revisions.)

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
