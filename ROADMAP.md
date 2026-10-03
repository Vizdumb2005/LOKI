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
- [ ] **Covert Fishing Dialogue Templates**: Create phrase collections in `services/language/` that disguise entropy-reducing questions as intuitive statements.
- [ ] **Response Signal Extractor**: Parse user responses for agreement strength ("Yes", "Sort of", "Not really") to apply soft Bayesian likelihood updates.
- [ ] **Method Selection Policy**: Implement the policy selector in `services/policy/` to choose dynamically between direct inference, covert fishing, and progressive narrowing.

---

## Phase 3 — Multi-Outs & Reveal Planner (High Impact)
- [ ] **Multi-Branch State Machine**: Build state machine support in `services/effects/` to track multiple plausible candidate branches ($H_{\text{top}}$).
- [ ] **Reveal Planner**: Create `services/language/reveal_planner.py` to stage progressive reveals (Category $\to$ Attribute $\to$ Identity) and inject strategic hesitation/faked uncertainty.
- [ ] **Equivocation Engine**: Add support for dynamic choice re-framing when choices are ambiguous or unexpected.

---

## Phase 4 — Psychological Forcing & Interactive Choice Architecture (Medium/High Impact)
- [ ] **Choice Biasing UI Primitives**: Build React frontend components in `apps/web/` that apply visual saliency, default positioning, and timing limits to bias choices toward high-prior targets.
- [ ] **Forcing Failure Recovery**: Implement automatic fallback paths when participants defy a force.

---

## Phase 5 — Multimodal Fusion & Passive Signal Integration (Medium Impact)
- [ ] **Latency & Keystroke Telemetry**: Capture response delay and typing rhythm in `apps/web/` as additional weak observation evidence.
- [ ] **Multimodal Fusion Engine**: Integrate gaze dwell, response latency, and verbal transcripts into structured Bayesian likelihood updates.

---

## Phase 6 — Continuous Reinforcement Learning & Human Trials
- [ ] **RL Dialogue Policy**: Train a contextual bandit / RL agent in `simulator/` to optimize the Magic Factor score against synthetic participant profiles.
- [ ] **A/B Human Evaluation Suite**: Run double-blind human trials comparing baseline Akinator dialogue against the AI Mentalist performance engine.
