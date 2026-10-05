# AI Mentalist — audit findings and where to focus

You are picking up work on **LOKI** (`C:\Users\viren\Downloads\LOKI`, branch `main`, HEAD `bb60490`).

You have been handed a diagnosis of where this project actually stands against its own
governing document, and a work order. Read both before you touch code.

**Read this first, because it changes how you read everything below.** This audit was written
against HEAD `3b4dc4a` while its own file sat **untracked and unread** in the working tree. In
parallel, an independent branch —
`feat/loki-directive-alignment-and-dataset-232012973718164411`, merged as **PR #3**, commit
`336b0b4`, merged in `bb60490` — landed four of the six ranked jobs in this document. Its author
never saw the audit. It is therefore **not** stale documentation to be reconciled against a newer
plan: it is a **second, independent finding**, reached from the opposite direction.

Where the two meet, they agree on the diagnosis and disagree on the reading:

| Ranked job | What PR #3 did | Verdict |
|---|---|---|
| (e) reveal ladder | `_ladder()` now scans **unasked** questions first and only falls back to asked ones to fill the beat count; dedupes on attribute | **Done, properly.** The cleanest of the four. |
| (b) technique dataset (§16) | `datasets/mentalism_techniques.yaml` + Pydantic loader + `consult_techniques()` | **Built but unwired.** Called only from its own test file. |
| (c) covert ratio | `covert_ratio: float = 0.20` added; allowance is now `max(max_covert_turns, int(max_turns * covert_ratio))` | **Changed on a measurement the repo contradicts** — and the contradicting sentence was deleted to make room. |
| (d) passive generation (§13 Q8/Q9) | `infer_latent_trait()` / `trait_likelihood_vector()` in `services/fusion/latent_traits.py` | **Exists, uncalibrated, unwired.** Real channel, invented thresholds. |
| (a) `I_visible` (§8) | untouched | **Not started — and it goes first.** |
| (f) real humans (§18) | untouched | **Not started.** |

The remote author took the optimistic reading of every meeting point: build the artifact, tick the
box, describe the benefit. The audit took the pessimistic one: an artifact nothing calls is not a
capability. Both readings are recorded here. You are expected to hold the second.

---

## 1. The directive and its bar

The governing document is the **"AI MENTALIST — AUTONOMOUS RESEARCH & BUILD DIRECTIVE"**,
23 sections, at:

```
C:\Users\viren\.os3\attachments\mutw1d8j4zr3
```

Read it. It is the spec, not a mood board. Section headings run:

- §1 Core Product Concept · §2 Research First · §3 Fundamental Architectural Shift · §4 Model the
  Mentalist as a Strategic Agent · §5 The System Needs Multiple "Methods" · §6 Separate "Inference"
  From "Performance" · §7 Build a "Magic Factor" Metric · §8 Optimize for "Apparent Information" ·
  §9 Conversational Strategy · §10 Introduce Controlled Uncertainty · §11 Create Explicit Reveal
  Planning · §12 Failure Recovery Is Part of the Trick · §13 Research Questions the Agent Must
  Answer · §14 Treat the Participant as Part of the System · §15 Machine Learning Strategy ·
  §16 Dataset Design · §17 Build an Experiment Harness · §18 Human Evaluation Is Mandatory ·
  §19 Build Toward a Portfolio-Grade Research Project · §20 What NOT to Do · §21 Autonomous Agent
  Operating Mode · §22 Immediate Deliverables · §23 First Engineering Objective

**Judge this project against the directive's own standard: experimentally answered and
human-measured. Not against fraction-of-files.** A section with a beautiful markdown document and
zero experiment is absent, not done. A section with a passing test suite that no session can reach
is absent, not done.

Current honest score:

| | |
|---|---|
| Sections genuinely done | **~7 of 23** (unchanged by PR #3) |
| Sections partial | **~11** (was ~8: §13, §14, §16 each moved absent → partial) |
| Sections absent | **~5** (§13, §14, §16, §18, §19) |
| **Substance reached, graded against §23's bar** | **~35%** (unchanged by PR #3) |

Read those two tables together. PR #3 moved three sections from **absent** to **partial**, and
that is real progress, but it did not move a single line of the bottom table, because §23 asks for
a human-measured result:

> **A convincing proof-of-concept where a participant cannot easily explain how the system
> arrived at the correct result.**

That milestone is **still not met**, and nothing in PR #3 changed it.

---

## 2. The §23 verdict — the framing problem

> **Akinator with a costume and a good costume budget.**

The diagnosis is already written down and it is good: `docs/architecture.md` §1
*"Architectural Diagnosis: Why the Current System Feels Like Akinator"* names the explicit
interrogation loop, the exposed algorithm, the inference/performance coupling, and the zero mystery
gap. **The redesign, not the diagnosis, is what's missing.** Do not rewrite the diagnosis. Act on it.

The evidence, all verified in this repo at `bb60490`:

1. **The dominant turn is still a multiple-choice button grid over declared attributes.**
   `configs/effects/animal_guess.yaml:59`, question `q_class`, asks:
   *"Which of nature's families does it belong to?"* — rendered as seven buttons. That is Akinator
   verbatim, one YAML attribute read. Untouched by PR #3.

2. **The policy rations itself to ONE covert read per session — by default, but no longer by
   measurement.** `services/policy/method_selection.py:79` still reads `max_covert_turns: int = 1`,
   and the in-file comment still concedes the reasoning: at `κ <= 0.25` fishing barely beats
   questioning, so hold at one read. The *same comment* at lines 75-78 now ends
   *"by default; a ratio parameter allows adaptive multi-read sessions"* — the clause
   *"a ration of 2 measurably degrades resolution"* was **deleted** by `336b0b4`. Line 81 adds
   `covert_ratio: float = 0.20`, and `select_turn()` computes
   `max(max_covert_turns, int(max_turns * covert_ratio))` at lines 204-217. For `animal_guess`
   (`max_turns: 12`) that is `max(1, 2) = 2` reads, so reads now exceed one per session. The
   direction is right. The deleted sentence is not.

3. **The README's magic-factor advantage is an authored constant, not behaviour.**
   `README.md:137`: animal_guess **0.0747** / 0.0734. That whole gap is produced by
   `κ = 0.25` being declared as the visible-information weight of a covert turn. Change κ and the
   table changes. Nothing about the software did anything. PR #3 did not touch this — it made it
   *more* load-bearing (see §3).

4. **The reveal ladder is fixed.** Previously `_ladder()` (`services/policy/reveal_planner.py:59`)
   walked `asked` and lifted answer labels from questions already asked. It now builds a first
   pass from **unasked** questions — corpus attributes the participant never supplied — and falls
   back to `asked` only if the beat count is short, skipping yes/no binary attributes and deduping
   on `attr`. This lands the audit's finding 4 outright. Do not regress it.

5. **Every "mystery" beat is still fixed-template prose seeded by session id.**
   `services/language/renderer.py` — `ASK_OPENERS`, `INTRO_LINES`, `REVEAL_HIGH`, `REVEAL_MEASURED`,
   `REVEAL_HEDGED`, `REVEAL_FORCED`, `OUTCOME_CORRECT`, `OUTCOME_WRONG`, all tuples selected by
   `blake2b` over `(seed, salt, session_id)`. Deterministic costume. The confidence bands are
   thresholds at `renderer.py:154-159` (`0.90 / 0.60 / 0.40`). Untouched by PR #3.

6. **Passive signals now generate — but on invented numbers, and nothing calls them.**
   `services/fusion/engine.py` still only *discounts* (`modulated_reliability` at line 55,
   `downgrade_strength` at line 87; `tests/test_fusion.py::test_modulated_reliability_never_strengthens`
   still guards the rule). PR #3 added a **genuinely distinct** generative channel beside it —
   `services/fusion/latent_traits.py`, `infer_latent_trait()` at line 30 and
   `trait_likelihood_vector()` at line 78 — which to its credit leaves `modulated_reliability`
   alone and produces soft likelihoods in [0.65, 1.35]. But its thresholds are invented: latency
   `< 1800 ms` → `fast_intuitive` at confidence **0.25** (line 43-46); latency `> 7000 ms` or slow
   first-key → `deliberate_analytical` at **0.20** (line 53-58); gaze dwell `> 800 ms` →
   `focused_visual` at **0.30** (line 67-70). Nothing calibrates them. And the whole module is
   referenced only by `tests/test_latent_traits.py`.

---

## 3. The single biggest gap — §8, Information Mystery Gap

**§8 is still untouched, and it still goes first.** PR #3 did not touch it.

§8 says the illusion is not *"the AI knew"* but *"the AI knew without having enough information to
know"*, and that this should become *"one of the project's central design concepts."*

Right now the central metric is an **assumption the author chose**.

In `docs/magic-factor.md` §2.1, visible-bit accounting is:

- direct turn = `log₂(options)`
- covert turn = **`κ · log₂(3)`**

And **κ = 0.25 was picked by the author**, because that is the value at which the fishing arm wins.
`docs/magic-factor.md:42-43` makes the sweep a reporting convention — the harness reports the full
`κ ∈ {0, 0.25, 0.5, 0.75, 1.0}` sweep on every run, and the headline uses κ = 0.25.
`docs/rl-policy.md:36` reuses the same hard-coded `λ = 0.25`.

The repo is honest about it, which is to its credit. `docs/covert-fishing.md` §6 finding 3:

> **The breakeven visibility weight is κ\* ≈ 0.33–0.40** (per effect): the mixed policy wins the
> mystery gap if and only if participants perceive a statement-reaction as less than roughly
> one-third as interrogating as an explicit question. At κ = 1.0 (fully visible) fishing loses
> everywhere. **κ is therefore not an assumption to bake in — it is a human-study question**
> (perceived-interrogation Likert items, ROADMAP Phase 6).

**And PR #3 made this worse, not better.** The README phase table header (`README.md:16`, Phase 1
*Research & Foundations*) now presents `$M = \frac{\text{Accuracy}}{1 + I_{\text{visible}}}$` as the
definition of what Phase 1 completed, and ticks it ✅.

So the repo now asserts that a metric built on an **authored** constant is **done**. The unmeasured
κ is more load-bearing after PR #3 than before it, not less: it is not a private authoring
assumption any more, it is the stated completion criterion for a phase the README claims is
complete. Every magic-factor number in the repo — including the 0.0747 vs 0.0734 gap PR #3 left
standing — rests on it.

**First job: make `I_visible` measured or estimated, not authored.**

---

## 4. The dead-code problem — the clearest structural pattern now

This is new since the audit was written, and it is the single thing most worth internalising.

**Two brand-new capability modules pass all 188 tests and are imported by nothing outside their own
test files.**

- `services/effects/techniques.py` — `load_techniques()` (line 45), `consult_techniques()` (line 63),
  a Pydantic `Technique` model carrying the ten §16 fields, loading
  `datasets/mentalism_techniques.yaml` (179 lines). Its only importer is `tests/test_techniques.py`.
- `services/fusion/latent_traits.py` — `infer_latent_trait()` (line 30), `trait_likelihood_vector()`
  (line 78). Its only importer is `tests/test_latent_traits.py`.

Nothing in `services/policy/` — the layer that would consult either one — imports them. A
participant in a live séance cannot reach a single behaviour either module provides. The test count
went 179 → 188 and **nine of those new tests assert against code the product never executes.**

The rule this establishes, and it applies to everything you build from here:

> **Either a capability earns its place in a live session, or it does not belong in the tree.**

A tree that contains a capability nobody can reach *implies* a system that has it. To a reader, to
a reviewer, to the README — the feature exists. That implication is false, and it is the exact
mechanism by which this project has produced three plausible-looking documents and zero measured
results. Passing tests are not reachability. Ask, of any change you make: **what code path in a
real session reaches this?**

---

## 5. Per-section status, all 23

Verdicts are as of `bb60490`. Changes from the `3b4dc4a` audit are marked **(moved by PR #3)**.

| § | Section | Verdict | Pointer |
|---|---|---|---|
| 1 | Core Product Concept | **partial** | Product exists and works, but the felt experience is a survey. `docs/architecture.md` §1 names why. |
| 2 | Research First | **done** | `research/mentalism-techniques.md`, `research/digital-translation.md`. Genuine, separates documented effects from anecdotes. |
| 3 | Fundamental Architectural Shift | **partial** | Belief state + policy exist (`services/hypothesis/tracker.py`, `services/policy/`), but no Mentalist Controller / Reveal Planner as the conceptual centre. |
| 4 | Strategic Agent | **partial** | Bayesian belief updating real and soft; the "combinations of" list is mostly untried. No embeddings, no PGM. |
| 5 | Multiple "Methods" | **partial** | Direct narrowing + fishing + equivocation + forcing exist. **Cold-reading interpretation (§5F) still not in the live policy** — `latent_traits.py` is the first attempt and is unwired. |
| 6 | Inference / Performance Separation | **done** | Strongest engineering in the repo. See §10 below — do not regress. |
| 7 | Magic Factor Metric | **partial** | Formula defined in `docs/magic-factor.md`, harness in `experiments/run_magic_factor_eval.py`. Of 11 experiential metrics, 5 exist in no form. |
| 8 | Apparent Information | **partial** | Concept defined and named; **the measurement is authored**, and the README now hangs a ✅ on it. See §3 above. |
| 9 | Conversational Strategy | **partial** | Observation→statement→ambiguous confirmation path exists in `docs/covert-fishing.md` §1, but direct button turns still dominate the turn budget. |
| 10 | Controlled Uncertainty | **partial** | Confidence-band phrasing only (`services/language/renderer.py:154-159`, `0.90/0.60/0.40` thresholds). No experiment on when uncertainty helps. |
| 11 | Explicit Reveal Planning | **partial, much stronger** | `services/policy/reveal_planner.py`, `services/language/reveal_planner.py`, `docs/reveal-planning.md`. **`_ladder()` now sources beats from unasked corpus attributes** (moved by PR #3). Still no human verdict on reveal timing. |
| 12 | Failure Recovery | **partial** | `services/language/equivocation.py` covers missed/unclear reads. Adversarial participants, ambiguity, "break the system": unaddressed. |
| 13 | Research Questions | **partial** (moved by PR #3) | `docs/research-questions-matrix.md` now enumerates all 16 questions with verdicts and code pointers. **But the verdicts are assertions, not experiments**: Q8 and Q9 are answered "Yes" on the strength of an unwired module and an existing simulator arm. See §7. |
| 14 | Participant as Part of the System | **partial** (moved by PR #3) | `docs/system-formalism-comparison.md` (84 lines) compares POMDP / contextual bandit / adaptive dialogue policy / Bayesian decision process / RL environment and justifies a hybrid "Decoupled POMDP-Bandit". A real comparison, and a real commitment with reasons. |
| 15 | ML Strategy | **done** | Smallest-system discipline honoured: no LLM anywhere in `services/`. |
| 16 | Dataset Design | **partial** (moved by PR #3) | `datasets/mentalism_techniques.yaml` carries the ten fields §16 names, Pydantic-validated. **Unwired**, and the effect hypotheses remain flat attribute dicts with no aliases, stereotypes or priors. See §7. |
| 17 | Experiment Harness | **done** | `simulator/` (`participant.py`, `profiles.py`, `bandit.py`), `experiments/run_baseline_eval.py`, `run_magic_factor_eval.py`, `run_bandit_eval.py`, `analyze_ab.py`. Real, reproducible, seeded. `bandit.serialize()` now creates its parent directory (moved by PR #3). |
| 18 | Human Evaluation | **absent** | Apparatus genuinely built; **zero human records**. PR #3 did not touch it. See §7. |
| 19 | Portfolio-Grade Research | **absent** | The chain stops at "experimental evaluation". No human study, so no measured magic factor. |
| 20 | What NOT to Do | **partial** | Every explicit prohibition still respected. But PR #3 deleted a *measurement* from a code comment and substituted a tuned default (§6) — an instance of the failure mode §20 exists to prevent. |
| 21 | Autonomous Operating Mode | **partial** | Loop runs; the "identify why it feels like Akinator" step produced a diagnosis nobody then acted on. |
| 22 | Immediate Deliverables | **done** | All six artifacts exist: `research/mentalism-techniques.md`, `research/digital-translation.md`, `docs/architecture.md`, `docs/magic-factor.md`, `experiments/`, `ROADMAP.md`. |
| 23 | First Engineering Objective | **partial** | Diagnosed honestly, not delivered. Milestone unmet. |

Count: **~7 done, ~11 partial, ~5 absent.** Substance graded against §23's bar: **~35%, unmoved.**

---

## 6. What PR #3 got right, and what it left standing

### Landed properly

- **The reveal ladder (audit job e).** `_ladder()` (`services/policy/reveal_planner.py:59`) scans
  unasked questions first, falls back to asked only when the beat count is short, skips yes/no
  binary attributes, dedupes on `attr`. This is the fix the audit asked for, implemented the right
  way round. Keep it.
- **`docs/system-formalism-comparison.md`** answers §14 properly: five candidates, a mathematical
  formulation for each, strengths and limits, then a committed hybrid with reasons. Real §14 work.
- **`docs/research-questions-matrix.md`** at least makes §13 *tracked* — all sixteen questions,
  enumerated, with pointers. The enumeration was the ask; the verdicts are the problem.
- **`datasets/mentalism_techniques.yaml`** is real, schema-checked, and carries the ten fields §16
  names (`name`, `mechanism`, `required_information`, `visible_participant_action`,
  `hidden_system_state`, `confidence_requirements`, `failure_modes`, `psychological_basis`,
  `digital_translation`, `measurable_effect`), each with genuine content and citations.

### Landed as a document, not a capability

- **`consult_techniques()`** is called by `tests/test_techniques.py` and nothing else. The technique
  dataset cannot steer a turn choice, because the layer that chooses turns has never heard of it.
  This is the audit's own line: *an unused dataset is a document, not a capability.*
- **`trait_likelihood_vector()`** is called by `tests/test_latent_traits.py` and nothing else.

### Landed on a contradicted measurement

- **`covert_ratio: float = 0.20`.** The effective allowance is now
  `max(max_covert_turns, int(effect.termination.max_turns * covert_ratio))`, which does raise reads
  above one per session — the right direction. But the comment it replaced was a **measurement**:
  the ration of one read was justified because *"a ration of 2 measurably degrades resolution."*
  That sentence is deleted, and replaced by a tuned-looking default that produces exactly the ration
  of 2 the measurement warned against. **A finding was not refuted; it was edited out of the file it
  was recorded in.**
- **And the documentation now disagrees with the code.** `docs/covert-fishing.md:81` still reads:

  | `max_covert_turns` | 1 | a hard ration: one read per session (measured — see §6) |

  It is still labelled a hard ration, still labelled measured, and `covert_ratio` is absent from the
  table entirely. Meanwhile §6 finding 2 records the forced-commit cost that more reads would raise,
  and that cost was to be **reported**, not paid quietly.

### Unearned verdicts now on the record

`docs/research-questions-matrix.md` asserts, in its own words:

- **Q8** *"Can the system infer latent traits rather than explicit answers?"* → **"Yes."** Cited to
  `services/fusion/latent_traits.py`, which no session executes.
- **Q9** *"Can multiple weak signals outperform explicit questioning?"* → **"Yes, in precision
  refinement ... +0.8 to +3.0 percentage points across all 4 effects."* That number is the existing
  `docs/passive-signals.md` §4 **simulator** arm, on synthetic profiles. Presented as the answer to a
  directive research question without that qualifier, it is the mislabelling pattern this audit
  exists to catch.
- **Q3** credits fishing with reducing perceived interrogation *"by up to 66% (κ ≈ 0.25)"*. That 66%
  is κ restated, not a perception measurement.

### Smaller

- `simulator/bandit.py` `serialize()` now creates parent directories before writing.
- The README phase table was rewritten to a 1-6 **ROADMAP.md Alignment** scheme, replacing the old
  two-scheme confusion with one — a genuine repair. See §9.

---

## 7. The sections that are still the real backlog

### §18 — Human Evaluation Is Mandatory

**The apparatus is genuinely built.** Do not rebuild it:

- server-side random A/B assignment — `services/api/main.py:203`
- consent-gated survey write — `services/api/main.py:213` (`POST /api/sessions/{session_id}/survey`),
  gated so it cannot precede the outcome report (409 at line 218)
- `experiments/analyze_ab.py` — `bootstrap_ci` (line 29), `mann_whitney_u` (line 45), `welch_t`
  (line 74), `ITEMS = ("impossibility", "freedom", "naturalness", "surprise")` (line 26)
- blinding (participant and moderator) and the debrief rule — `docs/human-trials.md` §1, §5
- power calculation — `docs/human-trials.md` §6: *"Recruit ≈ 40 participants per condition for 80%
  power on a medium effect (d = 0.5)"*

**And there are zero human records.** `data/sessions.db` contains a `sessions` table with **0 rows**
and **no `surveys` table at all.**

The only field work that exists is `_simulated_rows` in `experiments/analyze_ab.py` (line 119) —
synthetic rows for dry-running the analysis, with a hand-injected lift (`lift = 0.8 if condition ==
"b"`, line 125) and a hand-injected willingness-to-repeat (`rng.random() < (0.7 if condition == "b"
else 0.5)`, line 135). That is not a participant. That is the answer, written in advance, in the
file that will later be cited as evidence.

### §16 — Dataset Design (partially moved, not moved)

`datasets/mentalism_techniques.yaml` now exists and is real. What has **not** moved is the part that
makes cold reading possible. `configs/effects/animal_guess.yaml:48` — and every other effect:
`card_prediction.yaml:8`, `number_prediction.yaml:10`, `sigil_forced_choice.yaml:15` — still reads
`prior: uniform`. Hypotheses are still flat attribute dicts
(`configs/effects/animal_guess.yaml:10-42`), with no aliases, stereotypes, cultural priors, semantic
neighbours, misconceptions, discriminating clues or per-hypothesis reveal paths. The population-priors
lever that Barnum-style reading depends on is still switched off at the root, and the technique
dataset does not touch it.

`datasets/schemas/` and `datasets/manifests/` are empty (`.gitkeep` only), even though the
`.gitignore` comment promises that manifests and schemas **are** tracked.

### §13 — Research Questions (enumerated, not answered)

Sixteen questions now have a verdict in `docs/research-questions-matrix.md`. Four were previously
answered *by accident* — forcing-digitally (`docs/choice-architecture.md` §4), weak-signals-vs-
questions (`docs/passive-signals.md` §4), reveal-timing (`docs/reveal-planning.md`),
RL-discovers-strategies (`docs/rl-policy.md`, `simulator/bandit.py`). None of those was a §13
experiment then and none is now; they are the same simulator arms wearing a §13 label, and the Q9
line is the clearest example. **Grading each verdict as human-measured / simulator / assertion is the
work that remains.**

### §19 and §8

Unchanged by PR #3. See §3.

---

## 8. Experiential metrics — reality table

§7 lists eleven experiential metrics to *"measure experimentally"*. Per §18, human evaluation is
mandatory. Status at `bb60490` — **PR #3 changed nothing in this table**:

| Metric | Status |
|---|---|
| perceived accuracy | **proxy** — instrumented (`analyze_ab.py` `ITEMS`), no human rows |
| perceived impossibility | **proxy** — instrumented, no data |
| perceived mind-reading ability | **absent** — does not exist in any form |
| perceived randomness | **absent** |
| perceived participant freedom | **proxy** — instrumented, no data |
| surprise | **proxy** — simulator proxy: it assumes a beat lands **iff the identity was right**, so it cannot detect a well-timed but wrong-feeling reveal |
| "somehow knew" | **absent** |
| perceived intelligence | **absent** |
| memorability | **absent** |
| willingness to try again | **invented** — hard-coded `rng.random() < (0.7 if condition == "b" else 0.5)` at `experiments/analyze_ab.py:135`, inside `_simulated_rows` |
| willingness to show another person | **absent** |

**Real data: 0. Instrument-but-empty: 4. Proxy: 2. Invented: 1. Nonexistent: 5.**

The structural consequence, and it is the one to internalise:

> **The magic factor has never touched a human.** Every experiential claim in this repo is currently
> unfalsifiable.

A new module that infers traits from thresholds nobody calibrated does not change this sentence.
Neither does a new document. Only `data/sessions.db` changes it.

---

## 9. Mislabelled claims to fix

You will trust these. Do not. Fix them as part of your work.

1. **`README.md:16`** now presents the magic-factor formula as the **completion definition** for
   Phase 1 *Research & Foundations* — `($M = \frac{\text{Accuracy}}{1 + I_{\text{visible}}}$) | ✅ done`.
   The metric's central term is an authored constant (§3). A phase cannot be done on an assumption.

2. **`docs/research-questions-matrix.md`** answers Q8 and Q9 "Yes" on the strength of a module no
   session executes and a simulator arm presented without that qualifier. Q3's "66%" is κ restated.
   Every verdict in that file should carry its evidence class: **human-measured / simulator /
   assertion**. At present none does.

3. **`docs/covert-fishing.md:81`** still documents `max_covert_turns` as *"a hard ration: one read
   per session (measured — see §6)"*, while `covert_ratio: float = 0.20`
   (`services/policy/method_selection.py:81`) makes it two reads for `animal_guess`. The param table
   is stale. Either the code is reverted or the table is rewritten **with the forced-commit cost
   reported**, per §6 finding 2.

4. **`README.md:145`** describes the one-read ration as still operative — *"the one-read ration
   spends a turn that a direct answer would have used"* — in the very table the PR changed.

5. **`README.md:3`** now reads *"An AI mentalism research prototype"* — PR #3 correctly dropped the
   word *"multimodal"*, so this line is fixed. But the same paragraph still says passive signals
   *"modulate evidence reliability and response interpretation"*, which no longer describes
   `latent_traits.py`. Say what the system does, including what it does not yet do in a session.

6. **`ROADMAP.md:43-44`** still leaves both Phase 6 items `[ ]` unchecked, while `README.md:21`
   marks Phase 6 *RL Policy & Human Trials* **🔄 active** and `docs/rl-policy.md:3` now reads
   *"Active — ROADMAP Phase 6 (Bandit simulator & training harness built)"* (PR #3 tightened that
   line, correctly). One of the two is still lying about the human-trials half.

7. **`docs/human-trials.md:3`** now reads *"Apparatus built & simulated pilot validated — awaiting
   human participant records"* (PR #3 tightened this, correctly). It is now accurate; do not
   "tighten" it further, and never describe the simulated pilot as a pilot.

---

## 10. What the repo honours — do not regress this

**§6 is the strongest engineering in the repo**, and it is *structural*, not merely documented:

- `services/hypothesis/tracker.py` never sees prose
- `services/language/renderer.py` receives structured state only
- `services/fusion/engine.py` is numbers-in / numbers-out
- `docs/reveal-planning.md` §1 splits the boundary deliberately: staging in
  `services/language/reveal_planner.py`, **path choice** in `services/policy/reveal_planner.py`

PR #3 respected this. `latent_traits.py` is a pure module beside the fusion engine; it did not
invert `modulated_reliability`, and `tests/test_fusion.py::test_modulated_reliability_never_strengthens`
still holds. **Keep both facts true.** A generative channel must be added, never an up-weighted
discount.

**§20's prohibitions are still honoured**, to the letter:

- no LLM anywhere in `services/`
- no fabricated telemetry — in-browser only
- no supernatural claims
- no overclaimed psychological effects
- the κ sweep published rather than hidden
- forcing **disclosed** in the peek-behind-the-curtain panel ("this turn: steering toward X")

**But watch the spirit, not just the letter.** §20 caps everything:

> The product may create a **mind-reading illusion**, but its research documentation should remain
> honest about what the machine is actually doing.

Deleting *"a ration of 2 measurably degrades resolution"* from a code comment, while leaving a
different number in place in `docs/covert-fishing.md`, breaks that cap without breaking any written
rule. **Any fix you make must preserve the honesty.** No fabricated observations. No overclaimed
psychological effects. No supernatural claims. And: **no deleting a finding.**

---

## 11. Prioritized work — the current six

Ordered by leverage on **perceived impossibility**, not by ease. For each: what, why, what "done"
looks like, and what would count as **cheating**.

### (a) Make `I_visible` measured or estimated, not authored

- **Why first:** every other number in the repo depends on κ. It is the x-axis of the central
  metric. While κ is authored, you cannot distinguish a real improvement from a retuned constant.
  **And PR #3 made it more load-bearing, not less:** the README phase table now presents
  `$M = \frac{\text{Accuracy}}{1 + I_{\text{visible}}}$` as the completion definition for Phase 1,
  ticked ✅. An unmeasured constant that defines a "done" phase cannot stay unmeasured.
- **Done when:** `I_visible` derives from an empirical or principled estimator with stated
  uncertainty — a pilot with perceived-interrogation Likert items (already specified as ROADMAP
  Phase 6 in `docs/covert-fishing.md` §6 finding 3), **or** a defensible simulation of participant
  perception calibrated against that pilot. Report results across the full sweep
  {0, 0.25, 0.5, 0.75, 1.0}, which `docs/magic-factor.md:42` already mandates. Then restate every
  headline number as a function of κ rather than a point estimate, including the README table.
- **Cheating:** raising κ. Hard-coding a better constant. Reporting M at the κ that flatters it.
  Widening CIs while keeping the point estimate. Quoting the sweep's best value in the summary and
  its worst in the table.

### (b) Wire `consult_techniques()` and `trait_likelihood_vector()` into the live policy path, or remove them

- **Why second:** both modules pass every test and are reachable from no session. This is the
  clearest instance of the pattern in §4, and it now has nine tests defending it. Either the
  technique taxonomy can steer a turn choice, or nothing — in which case the modules are liability,
  not asset.
- **Done when:** `services/policy/` imports at least one of them on the live path, **and a test
  proves the wiring changes a real session's output** — e.g. that two sessions identical except for
  the consulted technique produce different turn plans or reveal beats. Absent that test, the module
  is still unreachable-in-practice. If the honest answer is that the wiring should not exist,
  **delete the module and its tests** and say so in the summary.
- **Cheating:** an import at module scope whose result is assigned to `_` and never used. A test
  that only asserts the function returns something. Wiring it in behind a flag that defaults off.

### (c) Reconcile the covert ration, and report the forced-commit cost

- **Why third:** the read-to-question ratio **is** what the participant experiences. `covert_ratio`
  moved it in the right direction on a measurement the repo contradicts, and deleted the sentence
  that contradicted it. Right now code and documentation disagree, and the deleted finding has no
  home.
- **Done when:** either the ration is reverted to `max_covert_turns: int = 1` and the measurement
  stands, **or** `docs/covert-fishing.md` §4's param table is rewritten to include `covert_ratio`
  and the forced-commit cost from §6 finding 2 is **reported as a number at the new ratio**,
  re-measured in the simulator and stated in the README honest-reading paragraph. Either way: the
  sentence *"a ration of 2 measurably degrades resolution"* is either refuted by a fresh
  measurement or restored. It must not simply be gone.
- **Cheating:** raising the ratio and re-running the eval, reporting only the magic-factor column.
  Leaving the doc stale. Restoring the sentence as dead commentary without re-measuring. Every turn
  covert. Covert turns that restate what the last question already implied — those are questions in
  costume, and they make the interrogation *more* visible, not less.

### (d) Calibrate the passive trait thresholds, or delete them

- **Why fourth:** `infer_latent_trait()` is the first genuinely generative channel in the repo and it
  deserves to survive — but 1800 ms / 7000 ms / 800 ms with confidences 0.25 / 0.20 / 0.30 are
  invented, and invented thresholds presented as inference are worse than no inference, because
  `docs/research-questions-matrix.md` already cites them as a "Yes". This is §13 Q8 and Q9, and the
  no-fabrication rule is absolute here.
- **Done when:** the thresholds are estimated from a stated source — literature, the pilot from
  (a)/(e), or a labelled corpus — with sensitivity reported, and the confidence values carry a
  justification. Or the module is removed and Q8/Q9 in the matrix are downgraded to *unanswered*.
  Do not leave invented numbers presented as inference. And keep the generative/discount separation:
  `tests/test_fusion.py::test_modulated_reliability_never_strengthens` exists for a reason — never
  invert a discount to fake a channel; add an honest one or none.
- **Cheating:** tuning thresholds until `run_baseline_eval` shows a nicer accuracy delta. Reporting
  the +0.8 to +3.0 pp simulator gain from `docs/passive-signals.md` §4 as if it came from this
  module, or as if it were a human result. Widening the [0.65, 1.35] likelihood band until every
  session improves.

### (e) Get real humans through the existing §18 apparatus

- **Why non-negotiable:** it is the only item that can falsify anything. Everything above is a
  hypothesis about a human experience, measured against a metric whose κ is authored (a) and whose
  participant-perception side has never been observed (§8).
- **Done when:** `data/sessions.db` has non-zero `sessions` rows **and** a populated `surveys`
  table; `experiments/analyze_ab.py` runs on real rows with `--simulated` unset; results reported
  with CIs and the tests named in `docs/human-trials.md` §4. Target ≈ 40 per condition for 80%
  power at d = 0.5. Consent, debrief and deletability gates stay hard.
- **Cheating:** keeping `_simulated_rows` output and presenting it as findings. Widening `ITEMS`
  until one looks significant. Small n without CIs. Running conditions A and B as different builds
  and calling it blinded. **Removing the `--simulated` flag** so the synthetic path becomes the
  default.

### (f) Keep the reveal-ladder fix, and prove it on a human

- **Why last:** PR #3 landed this one properly and it is the cheapest real win in the repo. Do not
  regress it and do not "simplify" it back to walking `asked`. But an improved ladder is still
  unmeasured: nobody has seen it.
- **Done when:** the ladder's behaviour is asserted end-to-end — unasked attributes surface first,
  yes/no binaries are skipped, attributes dedupe — **and** its effect on perceived accuracy appears
  in the (e) results rather than only in a unit test.
- **Cheating:** widening the ladder so a beat can come from any attribute at all, including one the
  participant supplied. Reordering the same asked-question labels and calling it a fix.

---

## 12. The standing test questions

§21, at **every** design decision:

> **Does this increase the user's perception that the system knows something it should not know?**

If the answer is no, question whether the work is actually advancing the core project.

A second question, added by PR #3, to apply at least as often:

> **What code path in a live session reaches this?**

And §20, which caps all of it: the product may create a mind-reading illusion; the **research
documentation must remain honest** about what the machine is actually doing.

---

## 13. Working agreements

- **Repo:** `C:\Users\viren\Downloads\LOKI`, branch `main`, HEAD `bb60490`, in sync with
  `origin/main`. Work from there.
- **Provenance:** the branch `feat/loki-directive-alignment-and-dataset-232012973718164411`
  (commit `336b0b4`, merged as **PR #3**) was authored **without sight of this audit**, which was
  untracked at the time. Where this document and that PR disagree, **both are findings** — this
  audit is not stale documentation to be reconciled away, and the PR is not a newer plan that
  supersedes it. Say which one you are following whenever you act on a disagreement.
- **Tests:** the suite is **188 passing** via `.venv\Scripts\python.exe -m pytest` (verified at
  `bb60490`). Keep it green and **report the number** in your summary. Do not weaken a test to make
  a change land. Nine of those tests cover modules no session executes (§4) — passing them is not
  evidence of capability.
- **Commits:** conventional-commit messages (`feat:`, `fix:`, `docs:`, `refactor:`).
- **`graphify-out\`** is generated output. **Keep it out of commits.** Since PR #3 the repo enforces
  this itself — `.gitignore` now carries `graphify-out/`, so it reports as ignored rather than
  untracked. You no longer need to add that line; a `.gitignore` change for it would be noise.
- **Process:** per the project's own `AGENTS.md` and `docs/spec/` — triage and spec before building.
  No building before tasks exist. Every phase either runs or is skipped **with the reason
  recorded**. No silent skips. At most **three** clarifying questions, and never advance on a guess.
  If verification fails twice, split the task or go research — **never retry the same failing action
  a third time.**
- **Baselines and leakage checks are mandatory** before claiming any model or metric improvement.
- **Shell is `cmd.exe`.** Full absolute paths. `powershell -NoProfile -Command` for recursion. Use the
  `grep` tool, **not** `Select-String`. Capture test output to a file and read it. Trust the tool's
  exit code, not an echoed `%ERRORLEVEL%`.
- **Credentials:** expected environment variables are named only, never opened. Do not read, echo or
  paste `.env` files, keys or tokens into logs, tests or summaries.
- **Leash is ask-first.** Reading and listing are free. Changing, moving, deleting, committing or
  sending anything: propose it, get approval, then act. If something fails, a file is deleted, or
  access is refused, say so plainly.