"""Centralised policy shape registry for the simulation harness
(PR-B4 plan v3 N1 absorb).

Each entry declares the keys a consuming primitive reads from a
policy document. Validators use the registry to reject proposed
policies whose shape does not match a consumer's expectations
without duplicating primitive internals.

Commit-1 ships a minimal surface: the fields consumed by
``executor.policy_enforcer.build_sandbox``,
``resolve_allowed_secrets``, and ``check_http_header_exposure``
for ``policy_worktree_profile.v1.json``, plus the
``check_policy``-backed ``intents`` / ``defaults.mode`` axis for
``policy_autonomy.v1.json``. C3 extends the registry with the
full tool-calling policy surface.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping


@dataclass(frozen=True)
class PolicyShapeEntry:
    """One primitive's view into a policy document.

    - ``primitive_name``: human-readable label ("build_sandbox",
      "check_policy::autonomy", ...).
    - ``policy_name_target``: the policy file the primitive
      reads, e.g. ``policy_worktree_profile.v1.json``.
    - ``required_top_keys``: top-level keys that must be present.
    - ``consumed_sub_paths``: tuple of key paths (each a tuple)
      the primitive dereferences. Used to build structural
      violation records without duplicating primitive logic.
    - ``type_contracts``: ``{sub_path: expected_type}`` for the
      handful of type checks the primitive relies on (e.g.
      ``env_allowlist.allowed_keys`` must be ``list``).
    """

    primitive_name: str
    policy_name_target: str
    required_top_keys: frozenset[str]
    consumed_sub_paths: tuple[tuple[str, ...], ...]
    type_contracts: Mapping[tuple[str, ...], type]


# Registry keyed by policy_name. A single policy may be consumed
# by multiple primitives; the loader aggregates required_top_keys
# and type_contracts across entries so a proposed policy must
# satisfy every consumer in one pass.
POLICY_SHAPE_REGISTRY: Mapping[str, tuple[PolicyShapeEntry, ...]] = {
    "policy_worktree_profile.v1.json": (
        PolicyShapeEntry(
            primitive_name="build_sandbox",
            policy_name_target="policy_worktree_profile.v1.json",
            required_top_keys=frozenset(
                {
                    "version",
                    "enabled",
                    "worktree",
                    "env_allowlist",
                    "secrets",
                    "command_allowlist",
                    "cwd_confinement",
                    "evidence_redaction",
                    "rollout",
                }
            ),
            consumed_sub_paths=(
                ("env_allowlist", "allowed_keys"),
                ("secrets", "exposure_modes"),
                ("command_allowlist", "prefixes"),
                ("cwd_confinement", "allowed_prefixes"),
                ("evidence_redaction", "patterns"),
            ),
            type_contracts={
                ("env_allowlist", "allowed_keys"): list,
                ("secrets", "exposure_modes"): list,
                ("command_allowlist", "prefixes"): list,
                ("cwd_confinement", "allowed_prefixes"): list,
                ("evidence_redaction", "patterns"): list,
            },
        ),
    ),
    "policy_autonomy.v1.json": (
        PolicyShapeEntry(
            primitive_name="check_policy::autonomy",
            policy_name_target="policy_autonomy.v1.json",
            required_top_keys=frozenset({"version", "intents", "defaults"}),
            consumed_sub_paths=(
                ("intents",),
                ("defaults", "mode"),
            ),
            type_contracts={
                ("intents",): list,
                ("defaults", "mode"): str,
            },
        ),
    ),
}


def get_registry_entries(policy_name: str) -> tuple[PolicyShapeEntry, ...]:
    """Return the registry entries for ``policy_name`` or an empty
    tuple when no primitive reads the policy yet (validator still
    enforces JSON-schema-level structural checks elsewhere)."""
    return POLICY_SHAPE_REGISTRY.get(policy_name, ())


def aggregated_required_keys(policy_name: str) -> frozenset[str]:
    """Union of ``required_top_keys`` across every registered
    primitive for ``policy_name``."""
    entries = get_registry_entries(policy_name)
    if not entries:
        return frozenset()
    merged: set[str] = set()
    for entry in entries:
        merged.update(entry.required_top_keys)
    return frozenset(merged)


def aggregated_type_contracts(
    policy_name: str,
) -> Mapping[tuple[str, ...], type]:
    """Union of ``type_contracts`` across every registered
    primitive for ``policy_name``. When two primitives disagree
    on a sub-path (should not happen in v1 — contracts are
    disjoint), the first registered wins and a caller-level test
    surfaces the drift."""
    entries = get_registry_entries(policy_name)
    merged: dict[tuple[str, ...], type] = {}
    for entry in entries:
        for path, expected in entry.type_contracts.items():
            merged.setdefault(path, expected)
    return merged


def walk_policy(
    policy: Mapping[str, Any],
    path: tuple[str, ...],
) -> Any:
    """Safely navigate ``policy`` down ``path``. Returns a
    sentinel ``_MISSING`` when any segment is absent so callers
    can report a structured violation without ``KeyError``
    surprises.
    """
    current: Any = policy
    for segment in path:
        if not isinstance(current, Mapping):
            return _MISSING
        if segment not in current:
            return _MISSING
        current = current[segment]
    return current


class _MissingSentinel:
    def __repr__(self) -> str:  # pragma: no cover - debug aid
        return "<_MISSING>"


_MISSING = _MissingSentinel()


__all__ = [
    "PolicyShapeEntry",
    "POLICY_SHAPE_REGISTRY",
    "_MISSING",
    "aggregated_required_keys",
    "aggregated_type_contracts",
    "get_registry_entries",
    "walk_policy",
]
