"""Coordination policy loader (PR-B1).

Loads and validates ``policy_coordination_claims.v1.json`` from the
bundled defaults or a workspace override, mirrors it into a typed
:class:`CoordinationPolicy` dataclass, and exposes the resource-pattern
matcher used by acquire / takeover entry points.

Semantic notes:

- **Dormant default:** the bundled policy ships ``enabled: false``.
  The registry's public API raises :class:`ClaimCoordinationDisabledError`
  when an enabled check fails — opt-in is a deliberate operator action.
- **``max_claims_per_agent=0`` ⇒ unlimited (B1v3):** the schema allows
  ``0`` and the runtime treats it as quota-disabled rather than
  quota-zero-claims. The registry's quota check is
  ``if limit > 0 and count >= limit: raise`` — both conditions must
  hold, so ``limit=0`` bypasses the check regardless of count.
- **`claim_resource_patterns`:** glob-style allowlist. The dormant
  default ships ``["*"]`` (allow all) so that tests exercising a
  runtime-active policy do not need to narrow the list unless
  explicitly testing pattern deny. Operators that enable coordination
  are expected to narrow to their actual resource namespace.
"""

from __future__ import annotations

import fnmatch
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping

from ao_kernel.config import load_default
from ao_kernel.errors import DefaultsNotFoundError


_POLICY_SCHEMA_CACHE: dict[str, Any] | None = None


def _policy_schema() -> dict[str, Any]:
    """Load and cache ``policy-coordination-claims.schema.v1.json``."""
    global _POLICY_SCHEMA_CACHE
    if _POLICY_SCHEMA_CACHE is None:
        _POLICY_SCHEMA_CACHE = load_default(
            "schemas", "policy-coordination-claims.schema.v1.json",
        )
    return _POLICY_SCHEMA_CACHE


@dataclass(frozen=True)
class EvidenceRedaction:
    """Redaction configuration for coordination event payloads.

    Mirrors ``policy_worktree_profile.evidence_redaction`` shape. All
    lists default to empty (no redaction) so the dormant policy is
    inert by construction.
    """

    env_keys_matching: tuple[str, ...] = ()
    stdout_patterns: tuple[str, ...] = ()
    file_content_patterns: tuple[str, ...] = ()
    patterns: tuple[str, ...] = ()


@dataclass(frozen=True)
class CoordinationPolicy:
    """Typed view of ``policy_coordination_claims.v1.json``.

    All scalar fields mirror the schema one-to-one. ``claim_resource_patterns``
    is stored as a tuple for hashability; :func:`match_resource_pattern`
    consumes it directly.
    """

    enabled: bool
    heartbeat_interval_seconds: int
    expiry_seconds: int
    takeover_grace_period_seconds: int
    max_claims_per_agent: int
    claim_resource_patterns: tuple[str, ...]
    evidence_redaction: EvidenceRedaction = field(default_factory=EvidenceRedaction)
    version: str = "v1"


def _from_dict(doc: Mapping[str, Any]) -> CoordinationPolicy:
    """Map a schema-valid policy dict to :class:`CoordinationPolicy`."""
    er_raw = doc.get("evidence_redaction") or {}
    redaction = EvidenceRedaction(
        env_keys_matching=tuple(er_raw.get("env_keys_matching") or ()),
        stdout_patterns=tuple(er_raw.get("stdout_patterns") or ()),
        file_content_patterns=tuple(er_raw.get("file_content_patterns") or ()),
        patterns=tuple(er_raw.get("patterns") or ()),
    )
    return CoordinationPolicy(
        enabled=bool(doc["enabled"]),
        heartbeat_interval_seconds=int(doc["heartbeat_interval_seconds"]),
        expiry_seconds=int(doc["expiry_seconds"]),
        takeover_grace_period_seconds=int(doc["takeover_grace_period_seconds"]),
        max_claims_per_agent=int(doc["max_claims_per_agent"]),
        claim_resource_patterns=tuple(doc["claim_resource_patterns"]),
        evidence_redaction=redaction,
        version=str(doc.get("version", "v1")),
    )


def _validate(doc: Mapping[str, Any]) -> None:
    """Validate ``doc`` against the bundled schema; raises on failure.

    Uses :mod:`jsonschema` Draft 2020-12. The caller decides whether
    to wrap the raised ``ValidationError`` in a domain-specific type;
    the coordination runtime treats policy load failure as fail-closed
    per CLAUDE.md §2 — a malformed override must not be silently
    ignored.
    """
    from jsonschema import Draft202012Validator

    Draft202012Validator(_policy_schema()).validate(doc)


def load_coordination_policy(
    workspace_root: Path,
    *,
    override: Mapping[str, Any] | None = None,
) -> CoordinationPolicy:
    """Load the coordination claims policy.

    Resolution order:

    1. If ``override`` is supplied (a dict), validate it against the
       schema and return the parsed policy. Used by tests and by
       callers that want to evaluate a hypothetical policy without
       touching the filesystem.
    2. Workspace override at ``{workspace_root}/.ao/policies/
       policy_coordination_claims.v1.json``. If present and schema-
       valid, used.
    3. Bundled default at ``ao_kernel/defaults/policies/
       policy_coordination_claims.v1.json`` (dormant by default).

    Fail-closed: a malformed override (invalid JSON, schema violation)
    raises the underlying parse / validation exception. The registry
    never silently falls back to the bundled default when the operator
    has explicitly placed an override file.

    Raises:
        json.JSONDecodeError: Workspace override JSON is malformed.
        jsonschema.ValidationError: Workspace override violates schema.
        DefaultsNotFoundError: Bundled default is missing (should never
            happen in a shipped wheel).
    """
    if override is not None:
        _validate(override)
        return _from_dict(override)

    workspace_override = (
        workspace_root / ".ao" / "policies" / "policy_coordination_claims.v1.json"
    )
    if workspace_override.is_file():
        doc = json.loads(workspace_override.read_text(encoding="utf-8"))
        _validate(doc)
        return _from_dict(doc)

    # Bundled default (dormant enabled=false)
    try:
        bundled = load_default("policies", "policy_coordination_claims.v1.json")
    except DefaultsNotFoundError:
        # Shouldn't happen — the bundled policy ships with the wheel.
        # Re-raise rather than fabricate defaults silently.
        raise
    _validate(bundled)
    return _from_dict(bundled)


def match_resource_pattern(policy: CoordinationPolicy, resource_id: str) -> bool:
    """Return True if ``resource_id`` matches any allowed pattern.

    Uses :mod:`fnmatch` glob semantics (``*`` matches any sequence of
    characters, ``?`` matches a single character). The dormant default
    ships ``["*"]`` so that once an operator flips ``enabled: true``,
    all resource ids are initially allowed; narrowing the pattern list
    is an explicit subsequent step.

    This check runs AFTER the ``_validate_resource_id`` path-traversal
    guard in the registry, so the glob patterns operate on known-safe
    strings (no ``../``, no separators, no wildcards in the id itself).
    """
    for pattern in policy.claim_resource_patterns:
        if fnmatch.fnmatchcase(resource_id, pattern):
            return True
    return False
