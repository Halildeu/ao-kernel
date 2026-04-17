"""Typed exceptions for ao-kernel metrics export (PR-B5).

Five error types cover the dormant-policy + fail-closed-derivation +
cardinality-guard surface of the metrics package:

- :class:`MetricsError` — common base (catch-all for metrics subsystem).
- :class:`MetricsDisabledError` — operator called an API that requires
  ``policy_metrics.enabled=true`` while the policy was dormant.
- :class:`MetricsExtraNotInstalledError` — ``[metrics]`` optional extra
  (``prometheus-client``) is not installed; lazy-import failed.
- :class:`EvidenceSourceMissingError` — the evidence events source file
  referenced by a scoped export is absent (not raised for dormant-mode
  empty workspace; only for explicit run-scoped queries in debug-query).
- :class:`EvidenceSourceCorruptedError` — evidence JSONL contains
  malformed lines. Mirrors the coordination package's fail-closed
  posture (``timeline.py`` ``json.JSONDecodeError → ValueError``): a
  corrupt audit trail MUST NOT silently yield half-correct metrics.
- :class:`InvalidLabelAllowlistError` — runtime defence-in-depth when
  a programmatically-constructed policy (bypassing schema validation)
  carries an ``allowlist`` value outside the closed enum
  ``{"model", "agent_id"}``.
"""

from __future__ import annotations


class MetricsError(Exception):
    """Base class for all metrics-subsystem errors.

    Callers that want a single catch-all (``except MetricsError``) can
    rely on every error in this package inheriting from this class.
    """


class MetricsDisabledError(MetricsError):
    """Raised when a metrics API is called while policy is dormant.

    ``policy_metrics.enabled=false`` is the bundled-default posture;
    APIs that require metrics (e.g. ``build_registry`` called without
    the dormant-graceful path) surface this error rather than silently
    returning a no-op registry.
    """


class MetricsExtraNotInstalledError(MetricsError):
    """Raised when ``[metrics]`` optional extra is not installed.

    Lazy-imports of :mod:`prometheus_client` fail with ``ImportError``;
    the metrics subsystem translates this into a typed error so CLI
    exit-code mapping (exit 3 informational) is deterministic.
    """


class EvidenceSourceMissingError(MetricsError, FileNotFoundError):
    """Raised when a scoped evidence source is missing.

    Specifically raised by debug-query when ``--run <run_id>`` targets
    a non-existent run directory, or ``--since`` filters result in an
    explicit empty source that should be surfaced to the operator.

    Not raised by default textfile export: a missing workspace returns
    an empty registry (dormant parity) rather than erroring.
    """


class EvidenceSourceCorruptedError(MetricsError, ValueError):
    """Raised when evidence JSONL contains malformed lines.

    Fail-closed derivation: the metrics subsystem never produces
    half-correct output from a partially-unreadable audit trail.
    Operators are expected to run ``ao-kernel doctor`` or inspect the
    evidence run directory manually before re-running export.

    Mirrors the ``ao_kernel._internal.evidence.timeline`` pattern
    (``json.JSONDecodeError → ValueError``) so the two subsystems
    share identical fail-closed semantics.
    """


class InvalidLabelAllowlistError(MetricsError, ValueError):
    """Raised when ``labels_advanced.allowlist`` contains an unknown value.

    Schema validation normally catches this at load time (the closed
    enum rejects typos). This runtime guard defends against
    programmatic construction that bypasses
    :func:`ao_kernel.metrics.policy.load_metrics_policy` — e.g., a
    caller builds a :class:`MetricsPolicy` directly from a raw dict
    without running ``_validate``. Defence in depth: the subsystem
    refuses to proceed with a non-closed-enum allowlist regardless of
    how the policy object was constructed.
    """


__all__ = [
    "MetricsError",
    "MetricsDisabledError",
    "MetricsExtraNotInstalledError",
    "EvidenceSourceMissingError",
    "EvidenceSourceCorruptedError",
    "InvalidLabelAllowlistError",
]
