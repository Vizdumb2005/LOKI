# AI Mentalist System Architecture & Architectural Diagnosis

## 1. Architectural Diagnosis: Why the Current System Feels Like Akinator

The initial prototype implementation (Phase 1/2) functions as a classic **Akinator-style decision tree with Bayesian state tracking**:

1. **Explicit Interrogation Loop**: The system repeatedly asks explicit binary/categorical questions ($Q_1, Q_2, \dots, Q_n$), directly reducing entropy $H(P)$ until a confidence threshold is met.
2. **Exposed Algorithm**: Questions clearly isolate hypothesis dimensions (e.g. "Is the person alive?", "Is it a heart?"). The participant can easily map every question to a database filter column.
3. **Linear Monolithic State**: Inference and performance are tightly coupled. The engine asks questions purely to maximize Information Gain ($\text{EIG}$) and immediately reveals the prediction upon reaching threshold.
4. **Zero Illusion of Mystery**: Because every unit of entropy reduction requires an explicit, visible participant answer, the **Information Mystery Gap** is zero:
   $$\text{Mystery Gap} = \text{Actual Bits Gathered} - \text{Apparent Bits Gathered} \approx 0$$
   The participant feels: *"It asked me 8 questions and statistically eliminated candidates until 1 remained."*

---

## 2. Target Mentalist Architecture

To transition from a guessing engine to a digital mentalist, the system decouples **Inference** from **Performance** and introduces a **Mentalist Controller** with a strategic **Method Selection Layer**.

```text
                                  ┌───────────────────────────┐
                                  │    Participant Model      │
                                  │ beliefs/preferences/priors│
                                  └─────────────┬─────────────┘
                                                │
                                                ▼
                                 ┌─────────────────────────────┐
                                 │    Mentalist Controller     │
                                 │                             │
                                 │ • Method Selection Layer    │
                                 │ • Strategic Dialogue Policy │
                                 │ • Reveal Planner            │
                                 └──────────────┬──────────────┘
                                                │
                 ┌──────────────────────────────┼──────────────────────────────┐
                 ▼                              ▼                              ▼
      ┌────────────────────┐         ┌────────────────────┐         ┌────────────────────┐
      │ Direct Inference   │         │ Covert Fishing     │         │ Psychological      │
      │ & Passive Signals  │         │ & Cold Reading     │         │ Choice Forcing     │
      └──────────┬─────────┘         └──────────┬─────────┘         └──────────┬─────────┘
                 │                              │                              │
                 └──────────────────────────────┼──────────────────────────────┘
                                                ▼
                                     ┌──────────────────┐
                                     │  Inference Engine│
                                     │ Bayesian Posterior│
                                     │ & Uncertainty    │
                                     └──────────┬───────┘
                                                ▼
                                     ┌──────────────────┐
                                     │ Performance      │
                                     │ Engine & Reveal  │
                                     └──────────────────┘
```

---

## 3. Layer Separation & Boundaries

### 3.1 Inference Engine
* **Responsibility**: Compute exact Bayesian posterior distribution over hypotheses $P(H_i \mid E_{1:t})$.
* **Rule**: Pure probabilistic tracking. Calculates entropy, information gain, posterior updating, and confidence intervals.
* **Boundary**: Outputs structured session state only (JSON). Never generates user-facing text.

### 3.2 Performance Engine
* **Responsibility**: Renders dialogue, frames questions as intuitive observations, structures theatrical reveals, and manages dramatic timing/hesitation.
* **Boundary**: Must NOT falsify or manipulate the underlying Bayesian state of the Inference Engine.

### 3.3 Method Selection Layer
Selects the active interaction strategy for each turn based on confidence, turn count, participant telemetry, and target domain:

1. **Direct Inference**: Make high-probability leaps from passive signals (gaze dwell, response latency, demographic priors) without visible questions.
2. **Covert Fishing / Cold Reading**: Formulate statements that gather information while appearing as intuitive reads.
3. **Progressive Narrowing**: Use indirect, associative questions rather than binary field filters.
4. **Choice Architecture & Forcing**: Bias participant selection probabilities $P(X)$ in interactive UI components.
5. **Multiple Outs**: Route the final reveal through pre-staged alternative pathways depending on posterior spread across top candidates.
6. **Reveal Construction**: Staged, progressive revelation with calculated uncertainty ("I feel a warm color... not a spade... it's a diamond, specifically the 8 of Diamonds").

---

## 4. Failure Recovery & Robustness

When an inference path fails (e.g., unexpected participant answer or failed choice force):
1. **Bayesian Soft Updates**: No hard elimination ($P(H_i) \to 0$). Likelihoods use answer noise/reliability modeling ($\eta \in [0.05, 0.20]$).
2. **Re-framing / Equivocation**: Re-interpret the response in dialogue ("Ah, that indicates their public image rather than their private life...").
3. **Multiple Outs Shift**: Switch from a direct single-target reveal to a cluster/category deduction reveal.
