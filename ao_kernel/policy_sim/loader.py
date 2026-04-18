"""Proposed-policy loader + baseline source resolver + in-memory
override context for the policy simulation harness (PR-B4 C3).

Three surfaces:

1. :class:`BaselineSource` enum (plan v3 N2 absorb) — controls
   whether the simulator's baseline comes from bundled defaults,
   on-disk workspace overrides, or an explicit dict.
2. :func:`validate_proposed_policy` — structural shape check
   against :mod:`_policy_shape_registry` (plan v3 N1 absorb).
3. :func:`policy_override_context` — monkey-patches
   ``ao_kernel.config.load_with_override`` so that
   ``governance.check_policy`` reads proposed policy dicts from
   memory instead of disk. Non-overridden policy names fall
   through to the original loader unchanged.
"""

from __future__ import annotations

import enum
from contextlib import contextmanager
from typing import Any, Iterator, Mapping

from ao_kernel import config as _config
from ao_kernel.config import load_default
from ao_kernel.policy_sim._policy_shape_registry import (
    _MISSING,
    aggregated_required_keys,
    aggregated_type_contracts,
    walk_policy,
)
from ao_kernel.policy_sim.errors import (
    ProposedPolicyInvalidError,
    TargetPolicyNotFoundError,
)


class BaselineSource(enum.Enum):
    """How to assemble the baseline policy set."""

    BUNDLED = "bundled"
    WORKSPACE_OVERRIDE = "workspace_override"
    EXPLICIT = "explicit"


def validate_proposed_policy(
    policy_name: str, policy: Mapping[str, Any]
) -> None:
    """Run structural shape checks for ``policy``.

    Uses the shape registry aggregators so a single policy that
    is read by multiple primitives still satisfies every
    consumer in one pass. Unknown policy names pass through
    without checks — the JSON schema (loaded separately) is the
    authoritative contract for those cases.
    """
    required = aggregated_required_keys(policy_name)
    type_contracts = aggregated_type_contracts(policy_name)
    if not required and not type_contracts:
        return

    violations: list[str] = []
    for key in sorted(required):
        if key not in policy:
            violations.append(f"missing required top-level key {key!r}")

    for path, expected in type_contracts.items():
        observed = walk_policy(policy, path)
        if observed is _MISSING:
            violations.append(
                f"missing required path {'.'.join(path)!r}"
            )
            continue
        if not isinstance(observed, expected):
            violations.append(
                f"path {'.'.join(path)!r} expected {expected.__name__}, "
                f"got {type(observed).__name__}"
            )

    if violations:
        raise ProposedPolicyInvalidError(
            policy_name=policy_name,
            violations=tuple(violations),
        )


def resolve_target_policy(
    *,
    policy_name: str,
    scenario_id: str,
    proposed_policies: Mapping[str, Mapping[str, Any]],
    baseline_source: BaselineSource,
    baseline_overrides: Mapping[str, Mapping[str, Any]] | None,
) -> Mapping[str, Any]:
    """Resolve the *baseline* policy for ``policy_name``.

    Precedence follows ``baseline_source``:

    - ``EXPLICIT``: ``baseline_overrides[policy_name]`` wins; falls
      back to bundled if absent only when the scenario can't find
      one anywhere.
    - ``WORKSPACE_OVERRIDE``: use
      :func:`ao_kernel.config.load_with_override` (disk read).
    - ``BUNDLED``: :func:`ao_kernel.config.load_default` directly.

    Raises :class:`TargetPolicyNotFoundError` when no source
    has a policy with the requested name.
    """
    if baseline_source is BaselineSource.EXPLICIT and baseline_overrides:
        explicit = baseline_overrides.get(policy_name)
        if explicit is not None:
            return dict(explicit)

    if baseline_source is BaselineSource.WORKSPACE_OVERRIDE:
        # load_with_override consults disk; the simulator wraps
        # this call in policy_override_context so proposed
        # policies do not leak through during baseline assembly.
        from ao_kernel import config as _cfg

        try:
            return _cfg.load_with_override("policies", policy_name)
        except Exception:
            pass  # fall back to bundled

    # Bundled fallback for any path that didn't short-circuit.
    try:
        return load_default("policies", policy_name)
    except Exception as exc:
        # If even bundled defaults miss the name AND proposed_policies
        # doesn't have it either, the scenario is mis-targeted.
        if policy_name not in proposed_policies:
            raise TargetPolicyNotFoundError(
                scenario_id=scenario_id,
                policy_name=policy_name,
            ) from exc
        # Proposed-only policy: baseline is the proposed dict itself
        # (operator is introducing a brand-new policy file).
        return dict(proposed_policies[policy_name])


@contextmanager
def policy_override_context(
    policy_overrides: Mapping[str, Mapping[str, Any]],
) -> Iterator[None]:
    """Monkey-patch :func:`ao_kernel.config.load_with_override`
    so it returns the in-memory dict for any ``filename`` in
    ``policy_overrides``. Other names fall through to the
    original implementation unchanged.

    ``governance.check_policy`` performs
    ``from ao_kernel.config import load_with_override`` inside
    its function body (see ``ao_kernel/governance.py:40``), so
    the patch applies on every call — even in threads that
    imported the module before the context started.

    Thread-safety note: the monkey-patch mutates module-level
    state. Simulations run single-threaded; the patch is
    restored in ``finally`` for exception safety.
    """
    original = _config.load_with_override

    def _patched(
        resource_type: str,
        filename: str,
        workspace: Any = None,
    ) -> dict[str, Any]:
        override = policy_overrides.get(filename)
        if override is not None:
            # Defensive copy so callers cannot mutate the
            # simulator's proposed dict through the returned
            # value.
            return dict(override)
        return original(resource_type, filename, workspace=workspace)

    _config.load_with_override = _patched  # type: ignore[assignment]
    try:
        yield
    finally:
        _config.load_with_override = original  # type: ignore[assignment]


__all__ = [
    "BaselineSource",
    "policy_override_context",
    "resolve_target_policy",
    "validate_proposed_policy",
]
