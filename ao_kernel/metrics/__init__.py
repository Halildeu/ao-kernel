"""ao-kernel metrics export (PR-B5).

Public package providing Prometheus textfile metrics export for
ao-kernel workspaces. See ``docs/METRICS.md`` for the operator guide.

Surface overview (populated across C1..C3b):

- :mod:`ao_kernel.metrics.policy` — ``policy_metrics.v1.json`` loader
  (``MetricsPolicy`` dataclass + ``load_metrics_policy``).
- :mod:`ao_kernel.metrics.errors` — five typed exceptions
  (``MetricsError`` base; ``MetricsDisabledError``,
  ``MetricsExtraNotInstalledError``, ``EvidenceSourceMissingError``,
  ``EvidenceSourceCorruptedError``, ``InvalidLabelAllowlistError``).
- :mod:`ao_kernel.metrics.registry` (C2) — lazy ``prometheus_client``
  wrapper with no-op fallback; builds the eight default metric
  families based on the policy's advanced-label allowlist.
- :mod:`ao_kernel.metrics.derivation` (C3) — evidence events scan →
  metric family population. Fail-closed on malformed JSONL.
- :mod:`ao_kernel.metrics.export` (C3) — Prometheus textfile
  serializer with dormant / cost-dormant banner comments.

The public re-exports below deliberately stay narrow: operators drive
metrics through the ``ao-kernel metrics`` CLI, and the library-mode
surface is the policy loader + typed errors.
"""

from __future__ import annotations

from ao_kernel.metrics.errors import (
    EvidenceSourceCorruptedError,
    EvidenceSourceMissingError,
    InvalidLabelAllowlistError,
    MetricsDisabledError,
    MetricsError,
    MetricsExtraNotInstalledError,
)
from ao_kernel.metrics.policy import (
    LabelsAdvanced,
    MetricsPolicy,
    load_metrics_policy,
)

__all__ = [
    "EvidenceSourceCorruptedError",
    "EvidenceSourceMissingError",
    "InvalidLabelAllowlistError",
    "LabelsAdvanced",
    "MetricsDisabledError",
    "MetricsError",
    "MetricsExtraNotInstalledError",
    "MetricsPolicy",
    "load_metrics_policy",
]
