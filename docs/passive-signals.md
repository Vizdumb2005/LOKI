# Spec: Passive Signals — Latency & Typing Rhythm Fusion (ROADMAP Phase 5)

Status: **Active — ROADMAP Phase 5**

Translates `research/digital-translation.md` §7 (Observation-Based Inference: "dwell, latency,
typing pattern as likelihood evidence") and completes ROADMAP Phase 5's Multimodal Fusion
Engine: gaze dwell (Phase 2), response latency, and verbal/transcript evidence now combine
into one structured Bayesian update. `services/fusion` — a placeholder since Phase 0 — holds
the pure combination functions.

## 1. What latency can honestly mean here

A participant who answers instantly is telling you they are sure; one who hemms for eight
seconds may be guessing. The signal therefore does not point at any hypothesis — it
**modulates how much the verbal answer is worth**. This keeps the evidence model interpretable
(Stage A discipline): no learned P(latency | hypothesis) yet, just a calibrated discount.

Mechanics (pure functions in `services/fusion/engine.py`, applied by the engine only):

- the effect declares a latency channel (opt-in, per effect):
  ```yaml
  response_latency:
    fast_ms: 2000      # at or below: the answer keeps its full reliability
    slow_ms: 8000      # at or above: reliability scaled down to the floor
    floor: 0.6         # modulation floor — evidence is weakened, never inverted
  ```
- `factor = 1.0` for latency ≤ fast_ms, linear to `floor` at slow_ms, constant after;
- `answer()` applies `reliability_effective = question.reliability × factor` for that update
  only. Fast answers are untouched; hesitant ones move the posterior less. Nothing about the
  update is categorical, nothing advances the session by itself — the answer still advances
  exactly as before.

## 2. Typing rhythm on free-text replies

When the participant types a covert reply, the browser reports three aggregate numbers —
time to first keystroke, median inter-key interval, total typing time. Rules:

- **Aggregates only.** Key content never travels as telemetry (the words themselves are the
  consent-gated `utterance`/`free_text` path), and raw key-timing sequences never leave the
  browser. The three numbers ride the same event and the same consent semantics.
- A hesitant rhythm **downgrades the parsed agreement strength one step** —
  strong→lean, lean→unclear, strong_no→lean_no — via `fusion.downgrade_strength`.
  Hesitation thresholds: `first_key_ms > 3000` or `median_interval_ms > 700`.
- Button presses are not rhythm-modulated (their latency is recorded, not fused — v1 scope).

## 3. Boundaries

- `services/fusion` is pure: numbers in, numbers out; it never sees sessions, hypotheses, or
  prose, and it never emits text (the LOKI-Fusion boundary — structured output only).
- Only the engine applies fusion results to the tracker. The theatrical surface is unchanged:
  reveal bands, fishing phrasing, and equivocation read the posterior exactly as before.
- Telemetry is behavioral evidence for the explicit game/effect only (plan §11) — never a
  profiling input; nothing sensitive is ever an inference target.

## 4. Measurement (simulator gates)

The simulator gains latency behavior correlated with answer quality: truthful answers are
usually fast (85%), guesses usually slow (75% slow) — with enough crossover that fusion has
to earn its keep. Gates, fusion ON (channels declared) vs OFF (`--no-fusion` strips the
channels):

- top-1 accuracy: fusion ON must not lose, and is expected to gain a small margin (discounted
  guesses hurt less);
- mystery gap / forced-commit rate: not worse beyond noise;
- the harness reports the share of answers whose reliability was modulated.

Real participants need calibration of fast/slow/floor before any claimed effect — the knobs
are per-effect YAML precisely so a calibration study can fit them (ROADMAP Phase 6).

## 5. Event schema (v1.5, additive)

| event | new fields |
|---|---|
| `hypothesis.updated` | `reliability_effective` (the modulated reliability when latency fusion applied, else null), `agreement_strength_effective` (the downgraded strength when typing rhythm applied, else null), `typing_rhythm` (`{first_key_ms, median_interval_ms, total_ms}` or null — aggregates only) |

## 6. Out of scope (deferred)

Learned P(telemetry | hypothesis) evidence models (idea.md Stage D), keystroke-dynamics
identification (never — privacy rule), fusion of button-press latency, WebSocket streaming of
passive signals (idea.md Phase 3), per-participant calibration (Phase 6).
