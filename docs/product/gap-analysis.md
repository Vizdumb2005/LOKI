# LOKI Gap Analysis (Phase 0 audit, 2026-10-05)

Biggest gaps ordered by product impact, not by file count.

1. **No Stage / no Brain.** The Q&A questionnaire is the product's face and the heuristic
   policy's ceiling is the experience ceiling. `services/brain/` + `apps/web/src/stage/`
   are the transformation, everything else is incremental.
2. **No unified SessionContext.** Inference, participant, interaction, performance state
   live in separate heads. Required before Brain or replayable sessions.
3. **Dialogue is templates.** Repetition risk is the fastest magic-killer; learned
   generation behind the intent→validate→event pipeline comes after policy works.
4. **Fusion is modulation, not state.** Gaze/latency/typing enter as discounts;
   no temporal participant-state estimation yet.
5. **No learned policy serving traffic.** Bandit exists offline; heuristic decides live.
6. **No human-trial data.** Simulation ≠ magic; apparatus ready, records empty.
7. **No production shell.** Auth, rate-limit, monitoring, deployment all missing —
   intentionally deferred until flagship experience validates.

Non-gaps (do not rebuild): Bayesian tracker, effect state machines, event schemas,
covert/fishing/forcing/reveal stack, consent ledger, eval CLIs.
