"""LOKI-Hypothesis: explicit probabilistic reasoning layer (plan §4.5, Stage A).

Classical, non-neural reference implementation: Bayesian updates over a finite
hypothesis space plus entropy metrics. Every learned component in later stages
must beat this baseline before it replaces it (plan §16).
"""
