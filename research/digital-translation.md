# Digital Translation: Mapping Mentalism to Software Primitives

This document translates physical mentalism techniques and psychological mechanisms into formal software architectures, data structures, probabilistic models, and failure modes.

---

## Technical Mapping Matrix

| Mentalism Technique | Informational Mechanism | Software Equivalent / Component | ML / Data Requirements | Primary Failure Modes |
| :--- | :--- | :--- | :--- | :--- |
| **Cold Reading / Fishing** | Broad probabilistic statements disguised as assertions; observing micro-confirmations. | **Covert Information Gathering Policy**: Semantic query masking + bayesian update on answer/hesitation. | Semantic association graphs, phrase-level entropy models. | Participant calls out "That's a question, not a read!"; low signal-to-noise ratio in participant responses. |
| **Barnum / Forer Effect** | High-acceptance generalized trait statements. | **Template Generator with Variable Injection**: Dynamic persona synthesis based on latent cluster priors. | Latent trait distributions, semantic embeddings. | Statements feel generic or horoscope-like if lacking specific anchor tokens. |
| **Psychological Forcing** | Biasing choice probability $P(X)$ while maintaining perceived free choice. | **Constrained Choice UI / Context Priming**: Visual positioning, timing delays, semantic priming prompts. | Empirical choice distributions under specific UI configurations. | Participant defies the force (~30–50% failure rate depending on force strength). Requires backup plan. |
| **Multiple Outs** | Diverting $N$ potential outcomes to $N$ pre-staged reveal branches. | **Multi-Branch State Machine + Conditional Reveal Resolver**: Dynamic routing to distinct reveal templates. | Pre-configured branching targets mapped to top posterior candidates. | Over-complexity in state tracking; revealing wrong branch due to stale state. |
| **Equivocation (Magician's Choice)** | Semantic re-interpretation of binary selections. | **Dynamic Semantic Interpreter**: Re-framing option selection based on current posterior distribution. | Flexible dialogue generator / re-framing template engine. | Participant notices inconsistent logic if re-framing is sloppy or exposed in UI. |
| **One-Ahead Principle** | Gathering info for target $N$ while revealing $N-1$. | **Asynchronous Background Pipeline**: Latent feature extraction / search query during theatrical delay. | Non-blocking async event bus, background hypothesis evaluation. | System latency causes noticeable lag or out-of-order execution. |
| **Observation-Based Inference** | Non-verbal signals (dwell, latency, typing pattern) as likelihood evidence. | **Telemetry Sensor & Fusion Layer**: WebGL gaze dwell tracker, keystroke/click timing analyzer. | Calibrated observation likelihood function $P(\text{Telemetry} \mid H_i)$. | Sensor noise, false positives, participant distraction or abnormal device usage. |
| **Reveal Escalation & Pacing** | Progressive revelation of target attributes in increasing specificity. | **Multi-Stage Reveal Planner**: Attribute decomposition and staged delivery controller. | Knowledge graph of targets with decomposed attributes (e.g., Category $\to$ Color $\to$ Name). | Revealing high-specificity detail before validating low-specificity attribute. |
| **Strategic Hesitation / Uncertainty** | Simulating cognitive effort / doubt before commitment. | **Performance Delay & Framing Injector**: Calibrated pause duration + doubt-phrasing templates. | Posterior confidence thresholding ($0.6 < P(\text{Top}) < 0.85$). | Artificial delays feel slow or frustrating if overused or misplaced. |

---

## Detailed Software Primitive Specifications

### 1. Covert Information Gathering (Fishing Engine)
* **Goal**: Maximize Information Gain $\text{IG}(Q)$ without revealing that an interrogation is taking place.
* **Primitive**: Instead of rendering binary questions ("Is the person an actor? [Yes/No]"), the Performance Engine renders an intuitive assertion:
  $$\text{Rendered Prompt}: \text{"I get a strong visual impression... this person is connected to performing or the arts, isn't that right?"}$$
* **State Logic**:
  - Internal state tracks: `question_type: "covert_fishing"`
  - High agreement ("Yes") $\implies$ full Bayesian update on positive likelihood.
  - Hesitation / Rejection ("Not really") $\implies$ fallback interpretation: "Ah, it's not their primary profession, but there's a dramatic presence about them..." (soft likelihood update).

### 2. Multi-Branch Reveal Resolver (Multiple Outs System)
* **Goal**: Achieve perceived 100% accuracy across a top candidate set $H_{\text{top}} = \{h_1, h_2, h_3\}$.
* **Primitive**:
  ```python
  class MultipleOutsResolver:
      def resolve_reveal(self, posterior_dist, active_context):
          top_h = posterior_dist.top(k=3)
          if top_h[0].probability >= 0.80:
              return DirectReveal(target=top_h[0])
          elif top_h[0].category == top_h[1].category:
              return CategoryClusterReveal(
                  category=top_h[0].category, candidates=[top_h[0], top_h[1]]
              )
          else:
              return DualRealityDeductionReveal(candidates=top_h)
  ```

### 3. Choice Architecture & Forcing Engine
* **Goal**: Bias participant selection toward high-prior target $H^*$ without explicit constraint.
* **Primitive**: UI layout presents 4 choices, but applies subtle visual saliency, default cursor positioning, and timing windows that empirically increase $P(H^*)$ from $0.25$ to $0.60$.
* **Failure Recovery Protocol**: If participant selects non-forced target $H_{\text{selected}}$, the system seamlessly falls back to standard Bayesian tracking or Equivocation re-framing.

---

## Verification & Safety Rules

1. **No Fake Telemetry**: Never synthesize fake webcam/gaze observations. All observation evidence must originate from actual client metrics.
2. **Internal Logical Consistency**: The Performance Engine must not alter or falsify the underlying Bayesian probability distribution maintained by the Inference Engine.
