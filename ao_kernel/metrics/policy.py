"""Metrics export policy loader (PR-B5).

Loads and validates ``policy_metrics.v1.json`` from the bundled
defaults or a workspace override, mirrors it into a typed
:class:`MetricsPolicy` dataclass, and exposes the advanced-label
allowlist accessor used by the registry adapter.

Semantic notes:

- **Dormant default:** the bundled policy ships ``enabled: false``.
  The export CLI produces a banner-only textfile when the policy is
  dormant; opt-in is a deliberate operator action.
- **Low-cardinality baseline:** when ``labels_advanced.enabled=false``
  (bundled default), only the low-cardinality label set is emitted
  (``provider``, ``direction``, ``outcome``, ``final_state``).
- **Advanced labels are closed-enum:** ``labels_advanced.allowlist``
  entries must be members of ``{"model", "agent_id"}``. Schema
  validation rejects typos at load time; :class:`InvalidLabelAllowlistError`
  is a runtime defence-in-depth guard for programmatically-constructed
  policies that bypass ``_validate``.
- **Defence in depth:** both ``labels_advanced.enabled=true`` AND a
  non-empty ``allowlist`` must hold for any advanced label to appear.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from ao_kernel.config import load_default
from ao_kernel.errors import DefaultsNotFoundError
from ao_kernel.metrics.errors import InvalidLabelAllowlistError


_POLICY_SCHEMA_CACHE: dict[str, Any] | None = None

# Closed enum mirror of the schema's
# ``labels_advanced.allowlist.items.enum``. The schema is authoritative
# but the runtime also guards programmatic construction that bypasses
# :func:`load_metrics_policy` (e.g., :class:`MetricsPolicy` built from a
# raw dict in a test helper). Drift between this set and the schema
# enum would be a real bug; the parity is covered by a dedicated test.
_LEGAL_ADVANCED_LABELS: frozenset[str] = frozenset({"model", "agent_id"})


def _policy_schema() -> dict[str, Any]:
    """Load and cache ``policy-metrics.schema.v1.json``."""
    global _POLICY_SCHEMA_CACHE
    if _POLICY_SCHEMA_CACHE is None:
        _POLICY_SCHEMA_CACHE = load_default(
            "schemas", "policy-metrics.schema.v1.json",
        )
    return _POLICY_SCHEMA_CACHE


@dataclass(frozen=True)
class LabelsAdvanced:
    """Typed view of ``policy_metrics.labels_advanced``.

    The outer ``enabled`` flag gates the allowlist: if ``enabled=false``
    the ``allowlist`` tuple is treated as empty regardless of contents
    (consistent with the schema's "both switches must align" semantic).
    """

    enabled: bool
    allowlist: tuple[str, ...]


@dataclass(frozen=True)
class MetricsPolicy:
    """Typed view of ``policy_metrics.v1.json``.

    Scalar fields mirror the schema one-to-one. The dataclass is frozen
    so policy objects are hashable and safe to share across the
    registry / derivation / export subsystems.
    """

    enabled: bool
    labels_advanced: LabelsAdvanced
    version: str = "v1"

    def advanced_allowlist(self) -> tuple[str, ...]:
        """Return the effective advanced-label allowlist.

        Honors the defence-in-depth invariant: if
        ``labels_advanced.enabled=false``, returns an empty tuple even
        when the underlying list is non-empty. Callers use this as the
        single source of truth for "which advanced labels should we
        expose on metric families?".
        """
        if not self.labels_advanced.enabled:
            return ()
        return self.labels_advanced.allowlist


def _check_allowlist(allowlist: tuple[str, ...]) -> None:
    """Runtime defence: allowlist subset of the closed enum.

    Schema validation should catch typos at load time; this guard
    protects against callers who construct :class:`MetricsPolicy`
    programmatically (e.g., from raw dicts in tests) while bypassing
    :func:`_validate`.
    """
    illegal = set(allowlist) - _LEGAL_ADVANCED_LABELS
    if illegal:
        raise InvalidLabelAllowlistError(
            "labels_advanced.allowlist contains non-closed-enum "
            f"values: {sorted(illegal)!r}; expected subset of "
            f"{sorted(_LEGAL_ADVANCED_LABELS)!r}"
        )


def _from_dict(doc: Mapping[str, Any]) -> MetricsPolicy:
    """Map a schema-valid policy dict to :class:`MetricsPolicy`.

    Applies the runtime allowlist guard before returning so callers
    that construct the dataclass via this helper are protected.
    """
    la_raw = doc.get("labels_advanced") or {}
    allowlist = tuple(la_raw.get("allowlist") or ())
    _check_allowlist(allowlist)
    labels_advanced = LabelsAdvanced(
        enabled=bool(la_raw.get("enabled", False)),
        allowlist=allowlist,
    )
    return MetricsPolicy(
        enabled=bool(doc["enabled"]),
        labels_advanced=labels_advanced,
        version=str(doc.get("version", "v1")),
    )


def _validate(doc: Mapping[str, Any]) -> None:
    """Validate ``doc`` against the bundled schema; raises on failure.

    Uses :mod:`jsonschema` Draft 2020-12. Malformed overrides must not
    be silently ignored (CLAUDE.md §2 fail-closed posture); callers
    surface the raised ``ValidationError`` to the operator.
    """
    from jsonschema import Draft202012Validator

    Draft202012Validator(_policy_schema()).validate(doc)


def load_metrics_policy(
    workspace_root: Path,
    *,
    override: Mapping[str, Any] | None = None,
) -> MetricsPolicy:
    """Load the metrics export policy.

    Resolution order:

    1. If ``override`` is supplied (a dict), validate it against the
       schema and return the parsed policy. Used by tests and by
       callers that want to evaluate a hypothetical policy without
       touching the filesystem.
    2. Workspace override at
       ``{workspace_root}/.ao/policies/policy_metrics.v1.json``.
       If present and schema-valid, used.
    3. Bundled default at
       ``ao_kernel/defaults/policies/policy_metrics.v1.json``
       (dormant by default).

    Fail-closed: a malformed override (invalid JSON, schema violation)
    raises the underlying parse / validation exception. The export CLI
    never silently falls back to the bundled default when the operator
    has explicitly placed an override file.

    Raises:
        json.JSONDecodeError: Workspace override JSON is malformed.
        jsonschema.ValidationError: Workspace override violates schema.
        InvalidLabelAllowlistError: ``allowlist`` contains values
            outside the closed enum (mainly a programmatic-construction
            guard; schema validation normally catches this first).
        DefaultsNotFoundError: Bundled default is missing (should never
            happen in a shipped wheel).
    """
    if override is not None:
        _validate(override)
        return _from_dict(override)

    workspace_override = (
        workspace_root / ".ao" / "policies" / "policy_metrics.v1.json"
    )
    if workspace_override.is_file():
        doc = json.loads(workspace_override.read_text(encoding="utf-8"))
        _validate(doc)
        return _from_dict(doc)

    # Bundled default (dormant enabled=false)
    try:
        bundled = load_default("policies", "policy_metrics.v1.json")
    except DefaultsNotFoundError:
        # Shouldn't happen — the bundled policy ships with the wheel.
        raise
    _validate(bundled)
    return _from_dict(bundled)


__all__ = [
    "LabelsAdvanced",
    "MetricsPolicy",
    "load_metrics_policy",
]
