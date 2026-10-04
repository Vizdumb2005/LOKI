# Directive §14: System Formalism Comparison & Architectural Justification

Section 14 of the **AI Mentalist Directive** requires investigating how the interactive system should be formally represented:

> *"Investigate whether the project is best represented as: POMDP, contextual bandit, adaptive dialogue policy, Bayesian decision process, or reinforcement learning environment. Rather than prematurely committing to one, research and justify the choice."*

This document provides a mathematical and architectural comparison of all five formalisms and justifies LOKI's hybrid **Decoupled POMDP-Bandit Architecture**.

---

## 1. Candidate Formalisms Comparison

### 1.1 Partially Observable Markov Decision Process (POMDP)
* **Mathematical Formulation**: A tuple $\langle \mathcal{S}, \mathcal{A}, \mathcal{T}, \mathcal{R}, \Omega, \mathcal{O}, \gamma \rangle$:
  * State space $\mathcal{S}$: Hidden target identity $h^* \in \mathcal{H}$ + participant internal state (patience, noise parameter $\epsilon$, choice susceptibility $\sigma$).
  * Action space $\mathcal{A}$: Query selection $Q_k$, interaction mode $M_k \in \{\text{direct}, \text{covert}, \text{forced}\}$, or reveal commitment.
  * Observation space $\Omega$: Multi-modal responses (button clicks, natural language agreement, gaze dwell, response latency, typing rhythm).
  * Observation function $\mathcal{O}(o \mid s, a)$: Conditional probability $P(\text{response} \mid h^*, Q_k, \text{telemetry})$.
  * Belief state $b_t(s)$: Probability distribution over hypotheses $P(h \mid e_{1:t})$.
* **Strengths**: Fully models hidden state, noisy observations, sequential decision-making, and dynamic participant belief states.
* **Limitations**: Solving general POMDPs with continuous telemetry and combinatorial question spaces is computationally intractable ($PSPACE$-hard) without explicit decomposition.

### 1.2 Contextual Bandit
* **Mathematical Formulation**: At turn $t$, observe context $x_t \in \mathcal{X}$, choose action $a_t \in \mathcal{A}_{\text{allowed}}(x_t)$, observe immediate reward $r_t(x_t, a_t)$.
  * Context $x_t$: Discretized state tuple $(\text{phase}, \text{credibility}) \in \{0,1,2\} \times \{0,1,2\}$.
  * Action space $\mathcal{A}$: Turn strategy $\{\text{direct}, \text{covert}, \text{forced}\}$.
  * Reward $r_t$: $\Delta H_{\text{actual}}(t) - \lambda I_{\text{visible}}(t) + \text{terminal\_bonus}$.
* **Strengths**: Lightweight, sample-efficient, auditable, and directly optimizes the Magic Factor reward trade-off ($M$). Action masks enforce state machine invariants.
* **Limitations**: Lacks multi-turn value iteration / long-horizon credit assignment beyond immediate turn rewards and terminal outcome bonuses.

### 1.3 Adaptive Dialogue Policy
* **Mathematical Formulation**: Deterministic or stochastic state machine rules mapping $(\text{posterior}, \text{asked}, \text{fishing\_state}) \to \text{TurnPlan}$.
* **Strengths**: Guaranteed safety, total interpretability, zero training requirements, and strict enforcement of hard constraints (covert ration, reserve turns).
* **Limitations**: Static heuristics cannot adapt automatically to heterogeneous participant populations (e.g. evasive vs impulsive users).

### 1.4 Bayesian Decision Process
* **Mathematical Formulation**: Sequential decision process selecting queries that maximize Expected Information Gain (EIG) or Expected Utility under Bayesian posterior $P(h \mid e)$.
  $$\text{EIG}(Q) = H(P) - \sum_{a} P(a \mid Q) H(P(\cdot \mid Q, a))$$
* **Strengths**: Mathematically optimal entropy reduction per query under truthful/noisy answer assumptions; zero parameter training required.
* **Limitations**: Optimizes purely for information reduction, ignoring perceived interrogation bits ($I_{\text{visible}}$) and theatrical timing.

### 1.5 Reinforcement Learning Environment (Full RL)
* **Mathematical Formulation**: Deep Q-Learning or Actor-Critic policy $\pi_\theta(a \mid s)$ over continuous neural embeddings.
* **Strengths**: Can learn complex multi-turn conversational policies.
* **Limitations**: Violates the directive's core prohibitions (§15, §20): requires massive sample sizes, lacks state interpretability, and risks hallucinations or uncalibrated confidence.

---

## 2. Comparison Summary Matrix

| Formalism | State Representation | Tractability | Magic Factor Alignment | Safety & Interpretability |
|---|---|---|---|---|
| **POMDP** | Complete (Hidden Target + Telemetry) | Low ($PSPACE$-hard) | High | High (via exact belief filter) |
| **Contextual Bandit** | Discretized Context Cells | Very High ($O(1)$) | Very High (Direct $M$ Reward) | High (via Action Masks) |
| **Adaptive Dialogue** | Session State Machine | Maximum | Moderate (Static) | Maximum |
| **Bayesian Decision** | Exact Posterior $P(h \mid e)$ | Very High | Moderate (Ignores $I_{\text{visible}}$) | Maximum |
| **Full Deep RL** | Neural Embeddings | Low | High | Low (Black box) |

---

## 3. Justified Architectural Choice: Decoupled POMDP-Bandit Architecture

LOKI rejects a naive, monolithic model in favor of a **Decoupled POMDP-Bandit Architecture**:

```text
┌─────────────────────────────────────────────────────────────────────────┐
│                           POMDP BELIEF FILTER                           │
│  Exact Bayesian Update: P(h | e) ∝ P(e | h) · P(h)                     │
│  Inputs: Verbal answers, Covert reactions, Gaze dwell, Latency, Typing  │
└────────────────────────────────────┬────────────────────────────────────┘
                                     │
                                     ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                      CONTEXTUAL BANDIT CONTROLLER                       │
│  Context: (Phase, Credibility) Cell                                     │
│  Masked Actions: { Direct (InfoGain), Covert (Fishing), Forced (UI) }  │
│  Reward: ΔH_actual - λ · I_visible + Terminal Outcome                   │
└─────────────────────────────────────────────────────────────────────────┘
```

### Architectural Justification:
1. **Separation of Inference & Strategy**: Exact Bayesian filtering solves the POMDP state tracking problem without neural approximation.
2. **Bandit Strategy Selection**: The contextual bandit learns *when* to fish, force, or ask direct questions across synthetic participant profiles (`simulator/profiles.py`), directly maximizing $M$.
3. **Action Masking Sovereign Boundary**: Hard invariants (covert turn rations, cooldowns, termination criteria) are enforced as action masks, ensuring the system never violates safety bounds.
