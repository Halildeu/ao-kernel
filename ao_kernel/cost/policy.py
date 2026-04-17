"""Cost tracking policy loader (PR-B2).

Loads and validates ``policy_cost_tracking.v1.json`` from the bundled
defaults or a workspace override and mirrors it into a typed
:class:`CostTrackingPolicy` dataclass.

Semantic notes:

- **Dormant default:** the bundled policy ships ``enabled: false``.
  The cost middleware treats policy.enabled=false as a transparent
  bypass — no ledger writes, no evidence emits, no catalog load.
  Opt-in is a deliberate operator action.
- **``fail_closed_on_exhaust`` MUST be true** (schema ``const: true``).
  The loader enforces this at parse time; any override attempting to
  set it false fails schema validation before reaching runtime.
- **``fail_closed_on_missing_usage`` defaults true** (v2 iter-2 B4 absorb).
  Operators in audit-only environments (billing reconciled out of
  band) can set false to warn-log instead of raising
  :class:`LLMUsageMissingError`.
- **``idempotency_window_lines`` defaults 1000** (v2 iter-2 B2 absorb).
  Ledger idempotency scan tail window; bounded for performance.
  Operators with very long runs can raise up to 100000.
- **``routing_by_cost.enabled`` defaults false** — PR-B3's cost-aware
  routing is inert under B2 even when the cost policy is enabled.
  Operators flip the inner flag when ready for automatic model
  downgrades.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping

from ao_kernel.config import load_default


_POLICY_SCHEMA_CACHE: dict[str, Any] | None = None
_BUNDLED_POLICY_CACHE: dict[str, Any] | None = None


def _policy_schema() -> dict[str, Any]:
    """Load and cache ``policy-cost-tracking.schema.v1.json``."""
    global _POLICY_SCHEMA_CACHE
    if _POLICY_SCHEMA_CACHE is None:
        _POLICY_SCHEMA_CACHE = load_default(
            "schemas", "policy-cost-tracking.schema.v1.json",
        )
    return _POLICY_SCHEMA_CACHE


def _bundled_policy() -> dict[str, Any]:
    """Load and cache the bundled dormant policy."""
    global _BUNDLED_POLICY_CACHE
    if _BUNDLED_POLICY_CACHE is None:
        _BUNDLED_POLICY_CACHE = load_default(
            "policies", "policy_cost_tracking.v1.json",
        )
    return _BUNDLED_POLICY_CACHE


@dataclass(frozen=True)
class RoutingByCost:
    """Cost-aware routing toggle (PR-B3 runtime)."""

    enabled: bool


@dataclass(frozen=True)
class CostTrackingPolicy:
    """Typed view of ``policy_cost_tracking.v1.json``.

    Scalar fields mirror the schema one-to-one. The dormant default
    has ``enabled=False``; a workspace override at
    ``{workspace_root}/.ao/policies/policy_cost_tracking.v1.json``
    replaces the bundled values.
    """

    enabled: bool
    price_catalog_path: str
    spend_ledger_path: str
    fail_closed_on_exhaust: bool
    strict_freshness: bool
    fail_closed_on_missing_usage: bool
    idempotency_window_lines: int
    routing_by_cost: RoutingByCost = field(default_factory=lambda: RoutingByCost(enabled=False))
    version: str = "v1"


def _from_dict(doc: Mapping[str, Any]) -> CostTrackingPolicy:
    """Map a schema-valid policy dict to :class:`CostTrackingPolicy`."""
    routing_raw = doc.get("routing_by_cost") or {"enabled": False}
    routing = RoutingByCost(enabled=bool(routing_raw.get("enabled", False)))
    return CostTrackingPolicy(
        enabled=bool(doc["enabled"]),
        price_catalog_path=str(doc["price_catalog_path"]),
        spend_ledger_path=str(doc["spend_ledger_path"]),
        fail_closed_on_exhaust=bool(doc["fail_closed_on_exhaust"]),
        strict_freshness=bool(doc["strict_freshness"]),
        fail_closed_on_missing_usage=bool(
            doc.get("fail_closed_on_missing_usage", True)
        ),
        idempotency_window_lines=int(
            doc.get("idempotency_window_lines", 1000)
        ),
        routing_by_cost=routing,
        version=str(doc.get("version", "v1")),
    )


def _validate(doc: Mapping[str, Any]) -> None:
    """Validate ``doc`` against the bundled schema; raises on failure.

    Fail-closed per CLAUDE.md §2: a malformed override must not be
    silently ignored.
    """
    from jsonschema import Draft202012Validator

    Draft202012Validator(_policy_schema()).validate(doc)


def load_cost_policy(
    workspace_root: Path,
    *,
    override: Mapping[str, Any] | None = None,
) -> CostTrackingPolicy:
    """Load the cost tracking policy.

    Resolution order:

    1. If ``override`` is supplied (a dict), validate it against the
       schema and return the parsed policy. Used by tests and by
       callers that want to evaluate a hypothetical policy without
       touching the filesystem.
    2. Workspace override at ``{workspace_root}/.ao/policies/
       policy_cost_tracking.v1.json``. If present and schema-valid,
       used.
    3. Bundled default at ``ao_kernel/defaults/policies/
       policy_cost_tracking.v1.json`` (dormant by default).

    Fail-closed: a malformed override (invalid JSON, schema violation)
    raises the underlying parse / validation exception.
    """
    if override is not None:
        _validate(override)
        return _from_dict(override)

    ws_path = (
        workspace_root
        / ".ao"
        / "policies"
        / "policy_cost_tracking.v1.json"
    )
    if ws_path.is_file():
        with ws_path.open("r", encoding="utf-8") as fh:
            loaded: Mapping[str, Any] = json.load(fh)
        _validate(loaded)
        return _from_dict(loaded)

    bundled = _bundled_policy()
    # Bundled policy is schema-valid by construction (CI gate), but
    # guard against drift.
    _validate(bundled)
    return _from_dict(bundled)


__all__ = [
    "RoutingByCost",
    "CostTrackingPolicy",
    "load_cost_policy",
]
