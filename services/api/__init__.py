"""LOKI API service: FastAPI surface over the effect engine (plan §9 Backend).

Sessions are held in memory and die with the process — deliberately aligned
with the privacy architecture (plan §11): Phase 1 persists nothing. SQLite /
PostgreSQL arrive with the LOKI Interaction Dataset (Phase 5+), which stores
consented, pseudonymized records only.
"""

from __future__ import annotations
