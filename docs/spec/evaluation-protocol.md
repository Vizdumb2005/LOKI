# Spec: Evaluation Protocol (v1)

Status: **Active — Phase 0/1**

Prediction ability and perceived magic are measured **separately** (plan §12). A high magic
score never compensates for fabricated certainty. Phase 1 measures only the classical baseline;
the human-study protocol arrives with a real product surface (Phase 7).

## Phase 1 metric set (classical Bayesian baseline)

Measured by `experiments/run_baseline_eval.py` over N simulated sessions per effect
(synthetic truthful-noisy participants, seeded RNG):

| metric | definition | why |
|---|---|---|
| `top1_accuracy` | fraction of sessions where the revealed MAP hypothesis equals ground truth | core prediction ability |
| `avg_turns_to_reveal` | mean questions asked per session | question efficiency (plan §12: average turns to reveal) |
| `avg_entropy_at_commit` | mean posterior entropy (bits) at the moment of reveal | how justified the reveal was |
| `forced_commit_rate` | fraction of commits caused by `max_turns` rather than `entropy_threshold` | detects under-informative question sets |
| `avg_info_gain_per_question` | mean expected information gain of chosen questions (bits) | quality of the policy |

## Protocol rules

1. **Seeds are mandatory.** Every run takes `--seed`; results must reproduce bit-for-bit.
2. **Every effect must be evaluated before it ships.** A new `configs/effects/*.yaml` PR
   includes eval output for that effect in the description.
3. **Accuracy is reported with the noise model it was measured under** (participant
   reliability). Accuracy under truthful answering alone is meaningless for a noisy world.
4. **A reveal is a commitment.** Metrics are computed at commit time, not "if we had asked one
   more question". This keeps calibration honest.
5. Simulation is a floor, not a ceiling: Phase 4 replaces the truthful-noisy participant with
   the full Participant Simulator (hesitation, deception, adversarial behavior — plan §8);
   Phase 5+ replaces it with consented human data.

## Deferred metrics (documented, not yet implemented)

- Posterior log loss, Brier, ECE, reliability curves → with LOKI-Calibrator (Stage F)
- Policy regret, bandit baselines → Phase 4
- Latency/FPS/WER → Phase 2+ (perception), measured per-model
- Human-study metrics (surprise, naturalness, replay intent…) → Phase 7
