# Spec: Covert Fishing & Dialogue Strategy (ROADMAP Phase 2)

Status: **Active — Phase 2 of `ROADMAP.md`**

This document specifies the digital translation of cold reading ("fishing") defined in
`research/digital-translation.md` §1 and the Method Selection Layer of `docs/architecture.md`
§3.3. It turns entropy-reducing probes into intuitive statements answered in natural language,
and mixes them with explicit questions through a per-turn method-selection policy.

## 1. Interaction protocol

A session's turns now carry a **mode**:

| mode | surface | response |
|---|---|---|
| `direct` | a question + its option buttons (as before) | an option id — full Bayesian update at the question's reliability |
| `covert` | an assertion of ONE option ("There's a pull toward Red. Don't overthink it — does that land?") | an agreement strength — soft likelihood update per §3 |

The mode changes only what is asked and how the reply is read. It never changes the hypothesis
space, the question set, the partition rule, the posterior's integrity, or the termination
rules. A cold reader who falsifies the books is a bug, not a feature (digital-translation.md,
verification rule 2: the Performance Engine must not alter the Bayesian state).

Response modalities on a covert turn:

- the fixed three-button scale (see §2) — ids are `AgreementStrength` values;
- free text (`free_text`, ≤200 chars), parsed server-side by the Response Signal Extractor —
  the verbatim text is recorded as `utterance` with the same consent semantics as voice;
- voice (in-browser Whisper) — the transcript takes the free-text path.

## 2. Agreement scale

`services/language/response_signals.py` maps participant words to a five-level, deterministic
scale: `strong_yes` (yes / exactly / that's right), `lean_yes` (sort of / maybe / i guess),
`unclear` (hmm / not sure / unrecognized — the conservative default), `lean_no` (not really /
probably not / nope), `strong_no` (no / definitely not). The UI buttons show three of the five
("Yes, exactly" / "Sort of…" / "Not really"); free text can yield all five.

The parser produces STRUCTURE only — no truth estimation, no probability. Mixed signals
("yes, but not really") resolve to the conservative hedge. The documented failure mode
"participant calls out 'that's a question, not a read!'" is mitigated by template phrasing
(assertion + tag question), never by hiding the response scale.

## 3. Soft agreement updates

`services/effects/agreement.py` holds the one response matrix, `P(response | assertion holds?)`,
used by the engine (inverted into likelihood vectors) and by the simulator (sampled directly —
the well-calibrated case; calibration against real participants is later-phase work):

| strength | holds = True | holds = False | likelihood ratio |
|---|---|---|---|
| `strong_yes` | 0.70 | 0.05 | 14× for the assertion |
| `lean_yes` | 0.12 | 0.10 | 1.2× (nearly worthless — by design) |
| `unclear` | 0.02 | 0.15 | **not used**: extractor uncertainty is not evidence |
| `lean_no` | 0.06 | 0.43 | 7× against the assertion |
| `strong_no` | 0.02 | 0.30 | 15× against the assertion |

Contract (enforced by tests):

- every likelihood vector is strictly positive — **no hard elimination**; the
  keep-competing-hypotheses-alive invariant holds for every strength;
- a denial eliminates only the asserted option's partition — it says nothing about which
  alternative is right (relative order inside the complement is untouched);
- hedges are soft, decisive words are strong — a flat "no" is semantically the participant
  answering the complement, so its strength rivals a direct answer's;
- `unclear` advances the turn without touching the posterior (a real cost: the turn is spent).

## 4. Method Selection Policy

`services/policy/method_selection.py`, hand-designed v1 (the contextual bandit comparison is
ROADMAP Phase 6). Per turn it plans either the information-gain question (direct) or the most
informative credible assertion (covert). Parameters (one frozen dataclass, measured — see §6):

| param | value | rationale |
|---|---|---|
| `fish_floor` | 0.40 | never assert below even-ish odds — a 1-in-52 read is bad theater |
| `max_fish_options` | 2 | a denial eliminates only the asserted reading; on binary questions it resolves the whole complement, on k-option questions it leaves k−1 rivals unresolved (this was measured: multi-option fishing left rival pairs exactly tied and broke resolution) |
| `miss_limit` | 1 | any miss sends the policy back to plain narrowing; only landing reads keep fishing going |
| `cooldown_turns` | 1 | one direct turn after a backoff |
| `reserve_turns` | 2 | the turn budget's tail is reserved for precision narrowing |
| `max_covert_turns` | 1 | a hard ration: one read per session (measured — see §6) |

The policy selects the interaction only; it never touches the posterior and never commits.

## 5. Event schema (v1.2, additive)

- `policy.decision` gains `mode` ("direct" | "covert") and `asserted_answer_id` (null on
  direct turns); `reason` distinguishes `credible_assertion`, `backoff_after_misses`,
  `cooldown_after_misses`, `budget_reserve`, `covert_budget_spent`,
  `max_expected_information_gain`.
- `hypothesis.updated` gains `mode`, `agreement_strength` (null on direct turns) and
  `asserted_answer_id`; `utterance` now records any verbatim participant text (spoken
  transcript or typed reply), consent-gated as before.
- No new event types; raw media remains forbidden in every payload.

## 6. Measured results (simulator, 1000 sessions, seed 42, gaze_prob 0.5)

Direct arm = all questions explicit; auto arm = the policy above. Visible-bit accounting per
`docs/magic-factor.md` §2.1: direct turn = log2(options); covert turn = κ·log2(3).

| effect | accuracy auto / direct | forced auto / direct | ΔH_mystery(auto) − ΔH_mystery(direct) @ κ=0.25 | M auto / direct @ κ=0.25 |
|---|---|---|---|---|
| animal_guess | 0.891 / 0.889 | 0.658 / 0.635 | **+0.18 bits** | 0.0747 / 0.0734 |
| card_prediction | 0.911 / 0.905 | 0.409 / 0.255 | **+0.24 bits** | 0.1000 / 0.0968 |
| number_prediction | 0.884 / 0.876 | 0.638 / 0.581 | **+0.15 bits** | 0.0748 / 0.0729 |
| sigil_forced_choice | 0.973 / 0.982 | 0.035 / 0.021 | **+0.13 bits** | 0.2318 / 0.2245 |

Honest findings:

1. **At κ = 0.25 the mixed policy meets every gate**: accuracy equal-or-better on all four
   effects, mystery gap strictly better on all four, Magic Factor better on all four.
2. **The cost is the forced-commit rate on question-limited effects** (card 0.409 vs 0.255,
   number 0.638 vs 0.581): trading one direct answer for a read leaves borderline sessions
   committing at slightly higher entropy. The hedged reveal band phrases those honestly.
3. **The breakeven visibility weight is κ\* ≈ 0.33–0.40** (per effect): the mixed policy wins
   the mystery gap if and only if participants perceive a statement-reaction as less than
   roughly one-third as interrogating as an explicit question. At κ = 1.0 (fully visible)
   fishing loses everywhere. κ is therefore not an assumption to bake in — it is a human-study
   question (perceived-interrogation Likert items, ROADMAP Phase 6). The harness reports the
   full sweep {0, 0.25, 0.5, 0.75, 1.0} on every run.
4. Covert turns also suppress the passive gaze channel (observations apply to direct turns
   only), which is part of why more fishing is not better. Latency recorded on covert turns is
   deliberately not fused into updates (ROADMAP Phase 5).

## 7. Out of scope (deferred)

Latency/keystroke fusion (ROADMAP Phase 5), multi-outs and the reveal planner (Phase 3),
choice-architecture forcing (Phase 4), learned method selection (Phase 6), multilingual
response parsing (idea.md Phase 5), WebSocket transport (idea.md Phase 3).
