# Research Taxonomy: Human Mentalism & Psychological Techniques

This document analyzes the psychological, information-theoretic, and performance methods used by professional mentalists and magicians to create the perception of mind reading.

To maintain scientific integrity and engineering rigor, techniques are explicitly categorized by their evidence base:

1. **Documented Empirical Psychological Effects** (empirically validated in cognitive science / psychology literature)
2. **Established Magic & Mentalism Techniques** (proven theatrical deception methods used by performers)
3. **Statistical & Information-Theoretic Foundations** (mathematical principles governing inference and uncertainty)
4. **Performer Anecdotes & Theatrical Wisdom** (practitioner heuristics and staging guidelines)
5. **Speculative / Weakly-Supported Claims** (popular myths or overhyped techniques with limited empirical reliability)

---

## 1. Documented Empirical Psychological Effects

### 1.1 Barnum / Forer Effect
* **Mechanism**: Individuals give high accuracy ratings to descriptions of their personality that supposedly are tailored specifically for them, but which are in fact vague and general enough to apply to a wide range of people.
* **Empirical Support**: Extremely high (Forer, 1949; Dickson & Kelly, 1985).
* **Key Factors**: Subject's belief in the test's validity, perceived authority of the evaluator, emphasis on positive/double-sided traits (e.g., "You are generally introverted, but can be the life of the party when comfortable").
* **Digital Relevance**: Generating personalized-sounding character profiles from weak or latent feature clusters.

### 1.2 Cognitive Priming and Suggestion
* **Mechanism**: Exposure to a stimulus influences a response to a subsequent stimulus, without conscious guidance or intention.
* **Empirical Support**: Moderate to High (Meyer & Schvaneveldt, 1971; Bargh et al., 1996). Note: Replication limits exist for social priming, but semantic and perceptual priming are robust.
* **Key Factors**: Semantic association networks, recency, implicit visual/auditory cues.
* **Digital Relevance**: Subtle UI/UX framing, word choice, or visual assets that subtly bias participant choices toward high-prior targets.

### 1.3 Choice Blindness and Illusion of Agency
* **Mechanism**: People often fail to notice mismatched outcomes between their choices and the actual results, subsequently constructing rationalizations for choices they did not actually make.
* **Empirical Support**: High (Johansson et al., 2005).
* **Key Factors**: Retrospective narrative construction, participant belief that they retain full agency throughout the interaction.
* **Digital Relevance**: Framing choices so participants feel they had absolute freedom, even when the decision space was tightly constrained or forced.

### 1.4 Memory Effects & Retrospective Distortion
* **Mechanism**: Human memory is reconstructive. Participants remember hits vividly ("It knew my card!") and forget misses, broad guesses, or probing questions ("It asked me 10 questions first").
* **Empirical Support**: High (Loftus, 1979; Wiseman et al., 2003 on magic perception).
* **Key Factors**: Time delay, dramatic framing, confirmation bias, omission of process steps during retrospective recall.
* **Digital Relevance**: Post-session summaries and reveal structures that highlight the directness of the guess while minimizing visible question history.

### 1.5 False Attribution of Causality
* **Mechanism**: The tendency to infer a causal relationship between two temporally correlated events, even when no causal mechanism exists.
* **Empirical Support**: High (Matute et al., 2015).
* **Key Factors**: Dramatic timing, presentation of unrelated behavioral observations right before a reveal.
* **Digital Relevance**: Presenting weak behavioral telemetry (e.g., typing speed or gaze pause) as the "source" of intuitive insight.

---

## 2. Established Magic & Mentalism Techniques

### 2.1 Equivocation (Magician's Choice)
* **Mechanism**: A method of choice manipulation where the performer assigns meaning to choices retroactively, ensuring a predetermined outcome regardless of participant selection.
* **Process**: "Pick two piles." If target is in Pile A: "We'll keep Pile A." If target is in Pile B: "We'll discard Pile A."
* **Evidence Base**: Established theatrical technique (Corinda, 1958, *13 Steps to Mentalism*).
* **Digital Relevance**: Branching interaction trees where distinct user inputs converge gracefully to the same target state or reveal strategy without exposing the trick.

### 2.2 Multiple Outs
* **Mechanism**: Constructing the performance such that any one of several predetermined outcomes can be revealed as the intended prediction.
* **Process**: Preparing 4 different envelopes or prediction messages. When the participant picks, the performer reveals only the matching envelope, leaving the other 3 hidden.
* **Evidence Base**: Established theatrical technique (Annemann, 1938, *Practical Mental Effects*).
* **Digital Relevance**: Maintaining a portfolio of valid reveal paths across high-probability hypothesis clusters, selecting the matching path dynamically.

### 2.3 One-Ahead Principle
* **Mechanism**: Obtaining information about target $N$ while ostensibly reading or revealing target $N-1$.
* **Process**: The performer opens a secret channel or inspects a written card under the guise of verifying the previous reveal.
* **Evidence Base**: Established theatrical technique (Corinda, 1958).
* **Digital Relevance**: Asynchronous background inference—gathering evidence or running background queries for upcoming targets while engaging the user in a distraction task.

### 2.4 Dual Reality
* **Mechanism**: Structuring an interaction such that the target participant experiences one reality while observers (or a second participant) experience a completely different narrative.
* **Evidence Base**: Established theatrical technique (Knepper, 1990s; Derren Brown performances).
* **Digital Relevance**: Interface asymmetry—presenting prompts where the literal text implies one constraint to the user, but the computational engine interprets a richer semantic space.

### 2.5 Cold Reading and "Fishing"
* **Mechanism**: High-speed, high-density generation of probabilistic statements ("shotgunning"), monitoring user reactions (nod, hesitate, correct), and rapidly narrowing based on feedback.
* **Evidence Base**: Extensively documented in skepticism and performance literature (Hyman, 1977; Rowland, 2002, *The Full Facts of Cold Reading*).
* **Digital Relevance**: Conversational dialogue loops that disguise entropy-reduction questions as intuitive assertions or statements ("I sense someone connected to the arts...").

### 2.6 Psychological Forcing
* **Mechanism**: Structuring options, timing, or verbal prompts so a participant feels free to pick anything, but statistically favors a specific option (e.g., 7 of Spades, 37, Red Hammer).
* **Evidence Base**: Measured in magician-psychologist collaborations (Kuhn et al., 2014; Olson et al., 2015).
* **Effectiveness**: Highly context-dependent (success rates range from 20% to 65% depending on timing and cognitive load).
* **Digital Relevance**: Choice architecture and default biasing in UI components.

---

## 3. Statistical & Information-Theoretic Foundations

### 3.1 Bayesian Prior Exploitation
* **Mechanism**: Utilizing population priors and conditional probability distributions $P(\text{Target} \mid \text{Demographics}, \text{Context})$ to make high-probability leaps without asking explicit questions.
* **Mathematical Basis**: $P(H_i \mid E) = \frac{P(E \mid H_i) P(H_i)}{\sum_j P(E \mid H_j) P(H_j)}$.

### 3.2 Information Entropy Reduction (Information Gain)
* **Mechanism**: Selecting queries or observations that maximize Expected Information Gain (EIG):
  $$\text{EIG}(Q) = H(P) - \sum_a P(a \mid Q) H(P(\cdot \mid Q, a))$$
* **Digital Relevance**: Formulating questions or fishing statements that divide the active hypothesis space into equal probabilistic partitions.

---

## 4. Performer Anecdotes & Theatrical Wisdom

### 4.1 Reveal Escalation and Pacing
* **Heuristic**: Never reveal the answer all at once. Break the reveal into 3-4 progressive stages (e.g., Category $\rightarrow$ Visual Trait $\rightarrow$ First Letter $\rightarrow$ Exact Target).
* **Theatrical Purpose**: Builds suspense, validates partial hits, and increases perceived impossibility.

### 4.2 Strategic Hesitation & Faked Uncertainty
* **Heuristic**: Appearing too confident makes the system look like an algorithm or search engine. Hesitating ("Wait... no, that's not right... it's clearer now") makes the process feel human and intuitive.

---

## 5. Speculative or Weakly-Supported Claims

### 5.1 Micro-Expression "Lie Detection"
* **Status**: Highly contested / unviable in standard webcam conditions (Barrett et al., 2019).
* **Design Stance**: Do NOT attempt or claim real-time micro-expression emotion/truth detection. Rely instead on measurable telemetry (response latency, option selection, gaze dwell duration).

### 5.2 Subliminal Hypnotic Control
* **Status**: Mythologized in media. Subliminal words cannot reliably force complex choices in unconstrained environments.
* **Design Stance**: Focus on perceptual priming and statistical choice architecture rather than "hypnotic" claims.
