# Magic Factor Metric & Evaluation Framework

## 1. Core Philosophy: Perceived Impossibility

Traditional machine learning systems optimize for **Accuracy** or **Top-k Accuracy**.

In an AI Mentalist, raw accuracy is insufficient. A system that achieves 95% accuracy by asking 20 explicit binary questions feels like an algorithmic database query (Akinator). Conversely, a system that achieves 80% accuracy while asking zero explicit questions creates a profound experience of mind reading.

The primary objective metric of this project is the **Magic Factor ($M$)**:

$$M = \frac{\text{Prediction Accuracy}}{\text{Apparent Information Used}}$$

---

## 2. Quantitative Metric Definitions

Let:
* $H_0 = H(P_{\text{prior}})$ be the initial entropy of the hypothesis space in bits.
* $H_{\text{final}} = H(P_{\text{posterior}})$ be the final entropy at decision commit.
* $\Delta H_{\text{actual}} = H_0 - H_{\text{final}}$ be the actual entropy reduced by the inference engine through all evidence (explicit answers + passive signals).
* $I_{\text{visible}}$ be the information explicitly and consciously provided by the participant through visible interrogation (in bits).

### 2.1 Visible Information ($I_{\text{visible}}$)
For each explicit question $Q_k$ with $m$ options presented to the user:
$$I_{\text{visible}}(Q_k) = \log_2(m)$$
For standard binary questions ($Yes/No$), $I_{\text{visible}}(Q_k) = 1.0\text{ bit}$.
Total visible information:
$$I_{\text{visible}} = \sum_{k=1}^{T} I_{\text{visible}}(Q_k)$$

### 2.1 Amendment (ROADMAP Phase 2): interaction-mode weighting

Direct questions and covert fishing statements (docs/covert-fishing.md) are accounted
differently:

- a **direct** question with m options: $I_{visible}(Q_k) = \log_2(m)$;
- a **covert** assertion answered on the agreement scale (3 buttons): $I_{visible} = \kappa \cdot \log_2(3)$.

κ ("visibility weight") models how interrogating a statement-reaction feels relative to
answering an explicit question. **It is a modeling assumption, not a measurement** — until
human studies calibrate it (ROADMAP Phase 6, perceived-interrogation Likert items):

- the eval harness reports the full sweep κ ∈ {0, 0.25, 0.5, 0.75, 1.0} on every run;
- the headline uses κ = 0.25, the largest sweep value at which the mixed policy meets all
  measured gates (docs/covert-fishing.md §6);
- κ = 1.0 is the fully-visible conservative bound — under it, covert fishing loses to direct
  questioning everywhere;
- the measured **breakeven** is κ\* ≈ 0.33–0.40 across effects: fishing pays iff participants
  perceive a statement-reaction as less than ~⅓ as interrogating as an explicit question.

Do not tune κ to flatter a result; report the sweep.

### 2.2 Information Mystery Gap ($\Delta H_{\text{mystery}}$)
The difference between actual information gathered and the information the participant realizes they provided:
$$\Delta H_{\text{mystery}} = \Delta H_{\text{actual}} - I_{\text{visible}}$$

* **Akinator System**: $\Delta H_{\text{actual}} \approx I_{\text{visible}} \implies \Delta H_{\text{mystery}} \approx 0$ (Zero Illusion).
* **Digital Mentalist System**: $\Delta H_{\text{actual}} \gg I_{\text{visible}} \implies \Delta H_{\text{mystery}} > 0$ (High Illusion).

### 2.3 Magic Factor Ratio ($M$)
To evaluate strategies cleanly across effects:
$$M = \frac{\text{Accuracy}_{\text{top1}}}{1.0 + I_{\text{visible}}}$$

---

## 3. Comprehensive Evaluation Protocol

Every strategy or policy evaluated in simulation or human trials must report:

1. **Top-1 Accuracy**: Proportion of sessions resolving to the true target.
2. **Average Turns ($T$)**: Mean number of conversational steps.
3. **Actual Bits Gathered ($\Delta H_{\text{actual}}$)**: Mean entropy reduction.
4. **Visible Bits ($I_{\text{visible}}$)**: Mean visible information requested.
5. **Information Mystery Gap ($\Delta H_{\text{mystery}}$)**: Mean mystery gap bits.
6. **Magic Factor ($M$)**: Overall performance ratio.
7. **Forced Commit Rate**: Proportion of sessions reaching max turns before reaching the entropy threshold.

---

## 4. Experiential & Human Evaluation Metrics

In human trials, post-session surveys capture experiential metrics on a 1–7 Likert scale:

* **Perceived Impossibility**: *"There is no way the AI could have known my answer based on what I told it."*
* **Perceived Freedom**: *"I felt completely free to choose any option without being steered."*
* **Conversational Naturalness**: *"The interaction felt like a natural performance rather than a survey or interrogation."*
* **Surprise / Delighted Shock**: *"The final reveal was unexpected and dramatic."*
