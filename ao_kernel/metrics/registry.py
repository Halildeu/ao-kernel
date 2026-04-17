"""Prometheus registry adapter (PR-B5 C2).

Lazy-imports ``prometheus_client`` — when the ``[metrics]`` optional
extra is not installed, every public helper returns a no-op sentinel
(``None`` for the registry, ``False`` for availability). Mirrors the
OTEL adapter pattern in :mod:`ao_kernel.telemetry`.

Eight metric families (plan v4 §2.2):

- ``ao_llm_call_duration_seconds`` — histogram, label ``provider``
  (+``model`` when advanced allowlist opts in).
- ``ao_llm_tokens_used_total`` — counter, labels ``provider`` /
  ``direction`` (+``model``).
- ``ao_llm_cost_usd_total`` — counter, label ``provider`` (+``model``).
- ``ao_llm_usage_missing_total`` — counter, label ``provider``
  (+``model``).
- ``ao_policy_check_total`` — counter, label ``outcome``.
- ``ao_workflow_duration_seconds`` — histogram, label ``final_state``.
- ``ao_claim_active_total`` — gauge (+``agent_id`` when advanced).
- ``ao_claim_takeover_total`` — counter, no labels.

Plan v4 §2 cost-disjunction: when cost tracking is dormant at the
derivation layer, the ``ao_llm_*`` families are still registered here
(metadata only); they simply have no samples. The textfile export
omits empty families when the metric family has never been observed,
which delivers the "metric family absent" guarantee demanded by the
cost-dormant acceptance checklist. See
:func:`ao_kernel.metrics.registry.build_registry` for the lazy
"register only if cost-active" branch.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ao_kernel.metrics.policy import MetricsPolicy


# ── prometheus_client Availability Check ────────────────────────────

_PROMETHEUS_AVAILABLE: bool | None = None


def _check_prometheus() -> bool:
    """Cache the availability check for the ``[metrics]`` extra.

    Mirrors :func:`ao_kernel.telemetry._check_otel`: first call imports
    ``prometheus_client`` (or catches ImportError), subsequent calls
    return the cached bool.
    """
    global _PROMETHEUS_AVAILABLE
    if _PROMETHEUS_AVAILABLE is not None:
        return _PROMETHEUS_AVAILABLE
    try:
        import prometheus_client  # noqa: F401
        _PROMETHEUS_AVAILABLE = True
    except ImportError:
        _PROMETHEUS_AVAILABLE = False
    return _PROMETHEUS_AVAILABLE


def is_metrics_available() -> bool:
    """Return True if ``prometheus-client`` is importable.

    Drives the CLI exit-code branching for the "extra missing"
    informational banner (plan v4 §2.6 exit 3).
    """
    return _check_prometheus()


# ── Histogram Buckets ───────────────────────────────────────────────

# Plan v4 §2.2: LLM upper raised to 600 (GPT-4-turbo outlier tolerance).
_LLM_DURATION_BUCKETS: tuple[float, ...] = (
    0.1, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0, 300.0, 600.0,
)

# Workflow buckets extend to 7200s (2h) because human-approval steps
# can dwell overnight.
_WORKFLOW_DURATION_BUCKETS: tuple[float, ...] = (
    1.0, 5.0, 15.0, 60.0, 300.0, 900.0, 3600.0, 7200.0,
)


# ── Built Registry ──────────────────────────────────────────────────


@dataclass(frozen=True)
class BuiltRegistry:
    """Container for the eight metric families built from a policy.

    Fields are ``Any`` typed because ``prometheus_client`` types are
    only available when the extra is installed; the dataclass is the
    single surface the rest of the subsystem imports, keeping
    :mod:`prometheus_client` imports contained to this module.

    ``include_llm_metrics`` reflects the plan v4 cost-disjunction:
    when cost tracking is dormant the caller constructs the registry
    with ``include_llm_metrics=False`` and the four ``ao_llm_*``
    fields are ``None``.
    """

    registry: Any  # prometheus_client.CollectorRegistry
    llm_call_duration: Any | None
    llm_tokens_used: Any | None
    llm_cost_usd: Any | None
    llm_usage_missing: Any | None
    policy_check: Any
    workflow_duration: Any
    claim_active: Any
    claim_takeover: Any


def _label_names(
    base: tuple[str, ...],
    advanced_candidates: tuple[str, ...],
    allowlist: tuple[str, ...],
) -> tuple[str, ...]:
    """Expand ``base`` with the subset of ``advanced_candidates`` the
    policy allows.

    Example: ``_label_names(("provider",), ("model",), ("model",))``
    returns ``("provider", "model")``. When the allowlist is empty the
    function returns the ``base`` labels unchanged so the default
    low-cardinality surface is preserved.
    """
    advanced = tuple(
        name for name in advanced_candidates if name in allowlist
    )
    return base + advanced


def build_registry(
    policy: MetricsPolicy,
    *,
    include_llm_metrics: bool = True,
) -> BuiltRegistry | None:
    """Construct the metric families driven by ``policy``.

    Returns ``None`` when ``prometheus-client`` is not installed (the
    caller is expected to surface an "extra missing" banner rather
    than crash on import errors).

    Parameters:
        policy: ``MetricsPolicy`` controlling the advanced-label
            allowlist. The policy's ``enabled`` flag is NOT consulted
            here — the export CLI owns the dormant/enabled branching.
            This function just builds the families.
        include_llm_metrics: Plan v4 cost-disjunction hook. When
            ``False`` (cost tracking dormant), the four ``ao_llm_*``
            families are skipped entirely so they do not appear in
            the textfile output even as metadata. The derivation
            layer is responsible for deciding the value: if
            ``policy_cost_tracking.v1.json.enabled=false`` at the
            same workspace, the LLM families are absent.
    """
    if not _check_prometheus():
        return None

    from prometheus_client import (
        CollectorRegistry,
        Counter,
        Gauge,
        Histogram,
    )

    registry = CollectorRegistry()
    allowlist = policy.advanced_allowlist()

    # LLM families — plan v4 §2.2 + cost-disjunction gate.
    llm_call_duration: Any | None = None
    llm_tokens_used: Any | None = None
    llm_cost_usd: Any | None = None
    llm_usage_missing: Any | None = None
    if include_llm_metrics:
        llm_duration_labels = _label_names(
            ("provider",), ("model",), allowlist,
        )
        llm_call_duration = Histogram(
            "ao_llm_call_duration_seconds",
            "Wall-clock seconds spent in a single LLM transport call, "
            "derived from llm_spend_recorded.duration_ms (PR-B5 C2b).",
            labelnames=llm_duration_labels,
            buckets=_LLM_DURATION_BUCKETS,
            registry=registry,
        )
        llm_tokens_labels = _label_names(
            ("provider", "direction"), ("model",), allowlist,
        )
        llm_tokens_used = Counter(
            "ao_llm_tokens_used_total",
            "Token counts from llm_spend_recorded.tokens_input / "
            "tokens_output / cached_tokens (direction label).",
            labelnames=llm_tokens_labels,
            registry=registry,
        )
        llm_cost_labels = _label_names(
            ("provider",), ("model",), allowlist,
        )
        llm_cost_usd = Counter(
            "ao_llm_cost_usd_total",
            "Actual billed cost from llm_spend_recorded.cost_usd.",
            labelnames=llm_cost_labels,
            registry=registry,
        )
        llm_usage_missing = Counter(
            "ao_llm_usage_missing_total",
            "Count of llm_usage_missing events (adapter responses "
            "without usage fields; cost reservation held).",
            labelnames=llm_cost_labels,
            registry=registry,
        )

    # Non-LLM families — always registered.
    policy_check = Counter(
        "ao_policy_check_total",
        "Policy evaluations derived from policy_checked.violations_count "
        "(outcome=allow when violations_count==0, deny when >0).",
        labelnames=("outcome",),
        registry=registry,
    )

    workflow_duration = Histogram(
        "ao_workflow_duration_seconds",
        "Wall-clock seconds per workflow run; cancelled runs derive "
        "duration from state.v1.json.completed_at (plan v4 Q3).",
        labelnames=("final_state",),
        buckets=_WORKFLOW_DURATION_BUCKETS,
        registry=registry,
    )

    claim_active_labels = _label_names(
        (), ("agent_id",), allowlist,
    )
    claim_active = Gauge(
        "ao_claim_active_total",
        "Live coordination claims, computed via "
        "coordination.registry.live_claims_count() (plan v4 Q1).",
        labelnames=claim_active_labels,
        registry=registry,
    )

    claim_takeover = Counter(
        "ao_claim_takeover_total",
        "Count of claim_takeover events (coordination forced "
        "takeover path).",
        labelnames=(),
        registry=registry,
    )

    return BuiltRegistry(
        registry=registry,
        llm_call_duration=llm_call_duration,
        llm_tokens_used=llm_tokens_used,
        llm_cost_usd=llm_cost_usd,
        llm_usage_missing=llm_usage_missing,
        policy_check=policy_check,
        workflow_duration=workflow_duration,
        claim_active=claim_active,
        claim_takeover=claim_takeover,
    )


__all__ = [
    "BuiltRegistry",
    "build_registry",
    "is_metrics_available",
]
