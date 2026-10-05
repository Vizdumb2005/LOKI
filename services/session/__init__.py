"""Unified session context (mission Phase 2). Read-only views over a session's
event history — inference, participant, interaction, performance in one object.

No parallel state: snapshots derive from append-only events, so replay needs
nothing but ``session.history``. Formulas are transparent aggregates, not
models; the learned participant model arrives in a later phase.
"""
