"""Prometheus textfile exporter (PR-B5 C3).

Thin wrapper over :func:`prometheus_client.generate_latest` that
prepends operator-readable banner comments for two dormant-mode
paths (plan v4 §2.6):

- ``metrics policy dormant`` — ``policy_metrics.enabled=false``.
- ``cost tracking dormant`` — ``policy_cost_tracking.enabled=false``
  (no ``ao_llm_*`` metric family in the output; derivation skipped
  building them via :func:`build_registry(..., include_llm_metrics=False)`).

Both banners are valid Prometheus textfile comments (``# `` prefix)
so they pass the exposition-format parser without emitting synthetic
samples. Grafana renders the resulting dashboards as "No data" while
the operator understands the root cause from the comment.

Cumulative-only contract (plan v4 §2.6): the exporter always produces
the full registry snapshot. Windowed / run-scoped queries live on the
separate ``ao-kernel metrics debug-query`` subcommand (C3b) which
emits JSON, never Prometheus textfile.
"""

from __future__ import annotations

from typing import Any

from ao_kernel.metrics.errors import MetricsExtraNotInstalledError
from ao_kernel.metrics.registry import BuiltRegistry, is_metrics_available


_DORMANT_BANNER = (
    "# ao-kernel metrics: dormant (policy_metrics.enabled=false). "
    "Operator action: copy "
    "ao_kernel/defaults/policies/policy_metrics.v1.json to "
    ".ao/policies/ and set enabled=true.\n"
)

_COST_DORMANT_BANNER = (
    "# ao-kernel metrics: cost tracking dormant "
    "(policy_cost_tracking.enabled=false); LLM metric family absent. "
    "See docs/METRICS.md §6 for the cost-tracking prerequisite.\n"
)

_EXTRA_MISSING_BANNER = (
    "# ao-kernel metrics: [metrics] optional extra not installed; "
    "no textfile content. pip install 'ao-kernel[metrics]' to enable.\n"
)


def generate_textfile(
    built: BuiltRegistry | None,
    *,
    metrics_dormant: bool,
    cost_dormant: bool,
) -> str:
    """Return the Prometheus textfile payload as a UTF-8 string.

    Parameters:
        built: The constructed registry (from
            :func:`ao_kernel.metrics.registry.build_registry`) or
            ``None`` when the optional extra is absent. The export
            CLI translates ``None`` into an exit-3 informational
            banner via the ``# extra missing`` comment below.
        metrics_dormant: ``True`` when the metrics policy is dormant
            (``policy_metrics.enabled=false``). The caller still
            builds a registry (for shape tests and cardinality
            assertions) but the exporter prepends the dormant banner
            so Grafana displays "No data" with explicit rationale.
        cost_dormant: ``True`` when the cost-tracking policy is
            dormant. The ``ao_llm_*`` families are absent from the
            registry (cost-disjunction), and this banner makes the
            absence visible.

    Raises:
        MetricsExtraNotInstalledError: Callers that demand strict
            behaviour (rather than the informational banner) use
            :func:`generate_textfile_strict`; this helper tolerates
            ``built=None`` by default per plan v4 exit-3 semantics.
    """
    if built is None:
        return _EXTRA_MISSING_BANNER
    header = ""
    if metrics_dormant:
        header += _DORMANT_BANNER
    if cost_dormant:
        header += _COST_DORMANT_BANNER
    body = _serialize(built.registry)
    return header + body


def generate_textfile_strict(
    built: BuiltRegistry | None,
    *,
    metrics_dormant: bool,
    cost_dormant: bool,
) -> str:
    """Strict variant that raises when the extra is missing.

    Useful for tests that want to assert the happy-path body size
    without stepping through the banner-only branch.
    """
    if built is None:
        if not is_metrics_available():
            raise MetricsExtraNotInstalledError(
                "prometheus-client not installed; "
                "cannot serialize metrics without the [metrics] extra"
            )
        # is_metrics_available() true + built None is a caller bug.
        raise MetricsExtraNotInstalledError(
            "built registry is None despite prometheus-client present; "
            "caller must pass a valid BuiltRegistry"
        )
    return generate_textfile(
        built,
        metrics_dormant=metrics_dormant,
        cost_dormant=cost_dormant,
    )


def _serialize(registry: Any) -> str:
    """Delegate to prometheus_client.generate_latest.

    Imported inside the function so importing this module does not
    pull in ``prometheus_client`` unconditionally (respects the
    lazy-import contract mirrored from :mod:`ao_kernel.telemetry`).
    """
    from prometheus_client import generate_latest

    return generate_latest(registry).decode("utf-8")


__all__ = [
    "generate_textfile",
    "generate_textfile_strict",
]
