# Spec: Choice Architecture & Psychological Forcing (ROADMAP Phase 4)

Status: **Active — ROADMAP Phase 4**

Translates `research/digital-translation.md` §3 (Choice Architecture & Forcing Engine) and
`docs/architecture.md` §3.3 item 4 into the interaction surface: UI primitives that bias the
participant's selection toward the option the posterior currently favors, with the failure
recovery the same document mandates. Evidence status per `research/mentalism-techniques.md`:
semantic priming is moderately supported (§1.2), forcing success rates are context-dependent
(20–65%, §2.6), and "perceived freedom" is an explicit human metric of the evaluation protocol
(`docs/magic-factor.md` §4) — bias must never be *perceived* as steering.

## 1. What forcing means in a fixed-target game (scope honesty)

Classic forcing shapes a choice the participant has not firmly made. LOKI's effects ask the
participant to FIX a target first, so a "successful" force cannot manufacture truth — it can
only (a) concentrate the participant's natural answer noise onto the system's current best
guess, keeping the performance coherent, and (b) raise perceived impossibility when the
salient option is also the eventual reveal. The engine therefore treats every click exactly
as before — a plain Bayesian answer at the question's reliability. Forcing changes ONLY the
presentation. If it silently changed likelihoods, it would violate the architecture boundary
(`docs/architecture.md` §3.2: the performance layer must not falsify the Bayesian state).

## 2. The primitives (frontend, `apps/web`)

On a direct turn where the engine names a salient option:

1. **Visual saliency** — the salient button gains a warm emphasis (border glow) that fades in
   after a delay (see 3).
2. **Default positioning** — the options list reorders so the salient option is first
   (the visual default position).
3. **Timing window** — implemented as *delayed emphasis onset* (~1.2 s): the participant sees
   the plain option set first; the emphasis then appears. Hard timing limits (countdowns,
   disabled buttons) are deliberately rejected: they coerce instead of prime, harm
   accessibility, and directly damage the "perceived freedom" metric.

Non-negotiables: nothing is ever disabled; contrast/keyboard access is preserved; the
"Peek behind the curtain" panel DISCLOSES the steering ("this turn: steering toward X") —
transparency is a product feature (plan §12), and the disclosure is what keeps a psychological
influence experiment honest.

## 3. Force-target policy (`services/policy/method_selection.py`)

`force_target(effect, posterior, question)` returns the maximum-mass answer option when its
mass ≥ `force_floor` (0.60 — forcing on a near-coin-flip is meaningless), else `None`.
Direct turns only (a covert assertion already leads the witness). After a defied force the
policy sits out for one turn (`force_cooldown`) — repeating a failed force reads as pushy and
burns perceived freedom. The selection rides on the existing `TurnPlan`
(`salient_answer_id`), so the Method Selection Layer owns it and the engine merely carries it.

## 4. Failure recovery (the second ROADMAP item)

When the participant defies the force (their answer ≠ the salient option):

- the Bayesian update proceeds unchanged — their click is their evidence;
- the NEXT turn's message opens with a **defied** equivocation reframe
  (`services/language/equivocation.py`, `REFRAME_DEFIED`): the defiance is folded into the
  performance ("You reached past the obvious — good.") instead of visibly backtracking;
- the policy takes the one-turn force cooldown (§3);
- the trajectory records it: `policy.decision.force_target` (v1.4) plus the answer event lets
  the harness compute defiance rates.

## 5. Simulator model and its honesty limits

`TruthfulNoisyParticipant` gains `force_susceptibility` (default 0). When a salient option is
presented and differs from the truthful one, the answer-noise mass (1 − r) concentrates on the
salient option with probability s (otherwise it spreads as before):
`P(pick salient | salient ≠ truth) = s·(1−r) + (1−s)·(1−r)/(k−1)`.

This models ONLY the mechanical choice shift. It cannot capture real priming psychology
(uncertainty-amplified saliency effects, §1.2) — a simulator participant's target is fixed,
so in-simulation forcing is expected to be roughly metric-neutral: P(correct) stays at the
question reliability by construction. The gates therefore assert non-regression, and the
perceptual upside (perceived impossibility of "guessing" the salient option) is a human-study
question (ROADMAP Phase 6), not a simulated one. Do not tune s to manufacture a win.

## 6. Measurement

`run_magic_factor_eval --force-susceptibility S` reports per effect:
force_presented_rate, force_success_rate (picked salient | presented), defiance rate, and the
standard protocol. Gates vs the forcing-off arm: top-1 accuracy within ±0.02, mystery gap and
forced-commit rate not worse beyond noise. UI primitives are verified in the frontend build
plus a unit-tested pure helper (ordering + emphasis selection); perceived effects need human
studies (Phase 6).

## 7. Out of scope (deferred)

Interactive multi-branch reveals that re-route on a balked reveal (needs a post-reveal
reaction channel), empirical choice-favorite priors (e.g. number favorites like 37/73 — the
project invents no psychology data it does not have; `prior:` stays a documented, sourced
input), countdown/timing-limit forcing (rejected, see §2), RL-learned forcing policy
(ROADMAP Phase 6).
