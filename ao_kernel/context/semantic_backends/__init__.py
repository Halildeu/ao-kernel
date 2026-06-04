"""Semantic retrieval backends (V5 Epic 7 E-7-5).

Pluggable backend protocol so the existing pure-Python cosine
implementation in ``semantic_retrieval.py`` can run alongside an
opt-in pgvector backend without forcing the pgvector + psycopg2
dependencies into every install.

Two backends ship in this slice:

- :class:`~ao_kernel.context.semantic_backends.in_memory.InMemoryBackend`
  — default; wraps the existing pure-Python cosine path. No new deps.
- :class:`~ao_kernel.context.semantic_backends.pgvector.PgVectorBackend`
  — opt-in; requires ``pip install 'ao-kernel[pgvector]'``. Lazy imports
  pgvector + psycopg2; raises a typed error if the extras are missing.

The backend selection is operator-owned: there is NO automatic
detection of the pgvector extension on a connected database. The
caller picks the backend explicitly. Default = in-memory.

Discipline:

- ``live_adapter_execution`` guard flag remains ``const false`` —
  embedding calls still use the existing ``embed_text`` provider path
  (operator-bound via env API key); the backend only stores + queries
  the resulting vectors.
- ``support_widening`` guard flag remains ``const false`` — adding a
  database-backed storage layer does not widen the support matrix on
  its own; operator owns DB provisioning + retention + backups.
- ``production_platform_claim`` remains ``const false`` — pgvector
  backend is a building block, not a production claim.
"""

from __future__ import annotations

from .base import SemanticBackend, SemanticBackendError, SemanticSearchResult
from .in_memory import InMemoryBackend

__all__ = [
    "SemanticBackend",
    "SemanticBackendError",
    "SemanticSearchResult",
    "InMemoryBackend",
]
