# Spec: A/B Human Evaluation Suite (ROADMAP Phase 6, item 2)

Status: **Built — awaiting participants** (the trials themselves require humans; everything
needed to run them is in place and piloted in simulation)

Implements docs/magic-factor.md §4's experiential protocol: a double-blind comparison of

- **Condition A — baseline**: the Akinator-style engine (explicit questions only, single-line
  reveal, no emphasis, no fishing, no reframes);
- **Condition B — performance engine**: covert fishing, staged multi-out reveals, choice
  architecture, passive-signal fusion, equivocation recovery.

on the four Likert items of §4 (1–7): **perceived impossibility**, **perceived freedom**,
**conversational naturalness**, **surprise** — plus optional replay willingness.

## 1. Double-blind protocol

- **Assignment**: the server assigns `a`/`b` uniformly at random at session creation
  (`POST /api/sessions` with no condition, or an explicit condition for research runs). The
  condition is stored with the session and returned in the API view as data only — the
  frontend never displays it.
- **Participant blinding**: the two conditions present identically branded interfaces; the
  only differences are the treatment itself. Nobody tells the participant which engine they
  met.
- **Moderator blinding**: moderators interact through the same app; no condition hint exists
  in the interface.
- **Experimenter honesty**: analysis code reads conditions from the consented records only,
  and every session's curtain panel still discloses the mechanism on demand (plan §12 — the
  disclosure is a feature, and curious participants may opt out of blinding themselves).

## 2. Condition construction (server-side, no forked code)

Condition A is the SAME engine with the performance layer switched off:
`effect.without_fishing()` plus `EffectSession(performance=False)` — which suppresses the
choice-architecture emphasis, the reveal staging (path becomes `plain`), and the equivocation
reframes. Condition B is the default. Both record identical event schemas, so trajectories
are directly comparable (turns, ΔH, visible bits, paths).

## 3. The survey

After the outcome screen, the participant is offered — entirely optionally — four 1–7 sliders
plus a replay-willingness checkbox. Submitting is the **act of consent**: the answers are
stored only when the participant presses submit, under the same consent architecture as the
ledger (gameplay never writes; `POST /api/sessions/{id}/survey` is the only write path; the
record is deletable). The archive schema bumps to `user_version` 2 with a `surveys` table;
`DELETE /api/archive/{id}` (and survey deletion) keeps working.

## 4. Analysis

`experiments/analyze_ab.py` reads the consented records and reports per condition: n, survey
means with 95% CIs (bootstrap), Mann-Whitney U and Welch t for each item, and the objective
protocol (accuracy, turns, visible bits) as manipulation checks. A simulated pilot runs the
same pipeline end-to-end without humans (`--simulated N`), which validates the suite but
says nothing about human perception — simulator "survey" scores are placeholder
distributions, clearly labeled.

## 5. Ethics rules (hard)

No sensitive-attribute inference (plan §11); telemetry and survey data are game evidence
only; every stored record is deletable; the debrief after the session explains that LOKI is
probabilistic inference and performance, never telepathy — the research documentation stays
honest even when the performance is deceptive (plan §20).

## 6. Running the trials (operator playbook)

1. Deploy with both conditions live (`POST /api/sessions` randomizes).
2. Recruit ≥ 40 participants per condition for 80% power on a medium effect (d = 0.5).
3. Collect consented surveys; monitor n per condition via `/api/stats`.
4. `python -m experiments.analyze_ab` — report means, CIs, significance.
5. Debrief every participant; publish the analysis with the mechanism disclosure.
