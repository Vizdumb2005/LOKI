# AI Mentalist Implementation Roadmap

This roadmap outlines the prioritized phases to transform LOKI from an Akinator-style decision engine into a portfolio-grade AI Mentalist. Development is prioritized by **perceived mind-reading impact** and **Information Mystery Gap ($\Delta H_{\text{mystery}}$)** rather than implementation convenience.

---

## Phase 1 — Research & Architectural Foundations (Completed)
- [x] **Mentalism Technique Research & Taxonomy**: Complete `research/mentalism-techniques.md` documenting cold reading, forcing, equivocation, multiple outs, and psychological effects with empirical rigor.
- [x] **Digital Translation Specifications**: Complete `research/digital-translation.md` mapping human techniques to software primitives, ML models, data structures, and failure modes.
- [x] **Decoupled Architecture & Diagnosis**: Produce `docs/architecture.md` detailing the separation of Inference Engine, Mentalist Controller, Method Selection Layer, and Performance Engine.
- [x] **Magic Factor Framework**: Formulate `docs/magic-factor.md` establishing the quantitative metric $M = \frac{\text{Accuracy}}{1 + I_{\text{visible}}}$ and Information Mystery Gap ($\Delta H_{\text{mystery}}$).
- [x] **Magic Factor Evaluation Harness**: Implement `experiments/run_magic_factor_eval.py` and test suite `tests/test_magic_factor.py`.

---

## Phase 2 — Covert Fishing & Dialogue Strategy Engine (High Impact)
- [x] **Covert Fishing Dialogue Templates**: Create phrase collections in `services/language/` that disguise entropy-reducing questions as intuitive statements. (`services/language/fishing.py`; per-question YAML overrides; leak-checked assertions)
- [x] **Response Signal Extractor**: Parse user responses for agreement strength ("Yes", "Sort of", "Not really") to apply soft Bayesian likelihood updates. (`services/language/response_signals.py` + `services/effects/agreement.py`; five-level scale, never hard-eliminates)
- [x] **Method Selection Policy**: Implement the policy selector in `services/policy/` to choose dynamically between direct inference, covert fishing, and progressive narrowing. (`services/policy/method_selection.py`; measured gates in `docs/covert-fishing.md` §6 — breakeven κ\* ≈ 0.33–0.40)

---

## Phase 3 — Multi-Outs & Reveal Planner (High Impact)
- [x] **Multi-Branch State Machine**: Build state machine support in `services/effects/` to track multiple plausible candidate branches ($H_{\text{top}}$). (top-k candidates carried through the commit: `RevealPlan.candidates`, `effect.revealed.reveal_candidates`, deduction staging over top-2)
- [x] **Reveal Planner**: Create `services/language/reveal_planner.py` to stage progressive reveals (Category $\to$ Attribute $\to$ Identity) and inject strategic hesitation/faked uncertainty. (staging lives in `services/language/reveal_planner.py`; the path CHOICE lives in `services/policy/reveal_planner.py` to keep the LOKI-Language boundary — see `docs/reveal-planning.md` §1)
- [x] **Equivocation Engine**: Add support for dynamic choice re-framing when choices are ambiguous or unexpected. (`services/language/equivocation.py`; engine queues a reframe after missed/unclear reads, event schema v1.3 records it)

---

## Phase 4 — Psychological Forcing & Interactive Choice Architecture (Medium/High Impact)
- [x] **Choice Biasing UI Primitives**: Build React frontend components in `apps/web/` that apply visual saliency, default positioning, and timing limits to bias choices toward high-prior targets. (`apps/web/src/lib/forcing.ts` + Session rendering: saliency glow with 1.2 s delayed onset, salient option moved first; hard timing limits rejected as coercive — see `docs/choice-architecture.md` §2)
- [x] **Forcing Failure Recovery**: Implement automatic fallback paths when participants defy a force. (defiance → equivocation reframe + one-turn emphasis cooldown, `policy.decision.force_target` in event schema v1.4; the Bayesian update never changes)

---

## Phase 5 — Multimodal Fusion & Passive Signal Integration (Medium Impact)
- [x] **Latency & Keystroke Telemetry**: Capture response delay and typing rhythm in `apps/web/` as additional weak observation evidence. (typing rhythm = three aggregates — time-to-first-key, median inter-key interval, total — never key content, never raw sequences; `apps/web/src/lib/telemetry.ts` + `AnswerRequest.typing_rhythm`)
- [x] **Multimodal Fusion Engine**: Integrate gaze dwell, response latency, and verbal transcripts into structured Bayesian likelihood updates. (`services/fusion/engine.py` — pure modulation functions; latency discounts a hesitant answer's reliability, typing rhythm downgrades a hesitant reply's agreement strength one step; measured gains in `docs/passive-signals.md` §4 — accuracy up on all four effects, forced-commit rate the honest cost)

---

## Phase 6 — Continuous Reinforcement Learning & Human Trials
- [ ] **RL Dialogue Policy**: Train a contextual bandit / RL agent in `simulator/` to optimize the Magic Factor score against synthetic participant profiles. (Simulator and training harness built: `simulator/bandit.py`, `experiments/run_bandit_eval.py` — active)
- [ ] **A/B Human Evaluation Suite**: Run double-blind human trials comparing baseline Akinator dialogue against the AI Mentalist performance engine. (Double-blind apparatus built: `services/api/main.py`, `experiments/run_human_trial.py`, `experiments/analyze_ab.py` — awaiting human participant records)
