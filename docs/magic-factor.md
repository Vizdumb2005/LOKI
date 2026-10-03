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
