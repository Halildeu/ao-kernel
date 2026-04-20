"""Runtime policy enforcement for adapter invocations.

Pure validation over ``policy_worktree_profile.v1.json`` — no I/O, no
subprocess. Returns structured ``PolicyViolation`` records so the
orchestrator can emit ``policy_denied`` evidence events and transition
the run to ``failed`` without partial state.

Plan v2 hardening (CNS-20260415-022 iter-1 B1-B2):

- PATH is policy-anchored. By default the host PATH is NOT inherited.
  PATH is synthesized from ``command_allowlist.prefixes`` or taken from
  ``env_allowlist.explicit_additions.PATH`` when the operator sets one.
- Command resolution uses ``shutil.which`` against the sandboxed PATH,
  then expands to ``os.path.realpath`` to catch symlink pivots, then
  checks the resolved realpath is under a policy-declared path prefix.
  A basename-alone match (e.g. ``python3`` in allowlist) does NOT
  authorize an arbitrary filesystem location — the resolved realpath
  must be anchored in policy.

Secret handling (§6 of policy docs):

- Values listed in ``policy.secrets.allowlist_secret_ids`` are read
  from the caller-supplied ``all_env`` mapping and folded into
  ``env_vars`` ONLY when ``policy.secrets.exposure_modes`` includes
  ``"env"``.
- ``validate_command`` scans resolved argv for verbatim secret values;
  a hit raises ``secret_exposure_denied`` with the offending argument
  index.
- HTTP adapter gate (Q4 W): when an adapter declares
  ``invocation.http.auth_secret_id_ref`` but the policy does NOT allow
  ``"http_header"`` exposure, this module surfaces
  ``http_header_exposure_unauthorized``.
"""

from __future__ import annotations

import os
import re
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping

from ao_kernel.executor.errors import PolicyViolation

# ---------------------------------------------------------------------------
# Configuration records
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RedactionConfig:
    """Compiled redaction patterns for evidence emission + log capture."""

    env_keys_matching: tuple[re.Pattern[str], ...]
    stdout_patterns: tuple[re.Pattern[str], ...]
    file_content_patterns: tuple[re.Pattern[str], ...]


@dataclass(frozen=True)
class SandboxedEnvironment:
    """Resolved sandbox context for one adapter invocation.

    ``policy_derived_path_entries`` (plan v2 B1): the authoritative list
    of filesystem directories a resolved command may live under. When
    ``command_allowlist.prefixes`` lists ``/usr/bin/``, the path entry
    is ``/usr/bin``. The current runtime interpreter directory is also
    added so wheel-installed subprocess adapters can stay hermetic
    without falling back to host PATH lookups.
    """

    env_vars: Mapping[str, str]
    cwd: Path
    allowed_commands_exact: frozenset[str]
    allowed_command_prefixes: tuple[str, ...]
    policy_derived_path_entries: tuple[Path, ...]
    exposure_modes: frozenset[str]
    evidence_redaction: RedactionConfig
    inherit_from_parent: bool


# ---------------------------------------------------------------------------
# Build sandbox
# ---------------------------------------------------------------------------


def build_sandbox(
    *,
    policy: Mapping[str, Any],
    worktree_root: Path,
    resolved_secrets: Mapping[str, str],
    parent_env: Mapping[str, str],
) -> tuple[SandboxedEnvironment, list[PolicyViolation]]:
    """Resolve the sandboxed environment for an invocation.

    Returns ``(sandbox, violations)``. The caller MUST abort when
    ``violations`` is non-empty.
    """
    violations: list[PolicyViolation] = []

    env_spec: Mapping[str, Any] = policy.get("env_allowlist", {})
    allowed_keys = frozenset(env_spec.get("allowed_keys", ()))
    explicit_additions: Mapping[str, str] = env_spec.get(
        "explicit_additions", {}
    ) or {}
    inherit_from_parent = bool(env_spec.get("inherit_from_parent", False))
    deny_on_unknown = bool(env_spec.get("deny_on_unknown", True))

    cmd_spec: Mapping[str, Any] = policy.get("command_allowlist", {})
    allowed_exact = frozenset(cmd_spec.get("exact", ()))
    allowed_prefixes = tuple(cmd_spec.get("prefixes", ()))

    secrets_spec: Mapping[str, Any] = policy.get("secrets", {})
    exposure_modes = frozenset(secrets_spec.get("exposure_modes", ()))

    # --- env construction -------------------------------------------------
    env_vars: dict[str, str] = {}

    if inherit_from_parent:
        # Passthrough only keys on the allowlist; unknown keys dropped
        # (deny_on_unknown is the default).
        for key in allowed_keys:
            if key in parent_env:
                env_vars[key] = parent_env[key]
        if not deny_on_unknown:
            # Soft mode: allow extras from parent that are on allowlist
            # but not required. (Kept for symmetry; in strict default
            # mode nothing changes.)
            pass
    # Explicit additions always wins over passthrough.
    for key, value in explicit_additions.items():
        env_vars[key] = str(value)

    # --- PATH resolution (B1+B2) ------------------------------------------
    # Priority: explicit_additions.PATH > inherited parent PATH > synth.
    if "PATH" not in env_vars:
        if inherit_from_parent and "PATH" in parent_env:
            env_vars["PATH"] = parent_env["PATH"]
        else:
            env_vars["PATH"] = ":".join(
                p.rstrip("/") for p in allowed_prefixes
            )

    # Compute authoritative policy-derived path entries (real directories
    # that commands may be anchored in).
    policy_path_entries: list[Path] = []
    for prefix in allowed_prefixes:
        try:
            policy_path_entries.append(Path(prefix).resolve())
        except OSError:
            # Missing prefix is not a violation — it just cannot authorize
            # a command later.
            pass

    try:
        runtime_realpath = Path(sys.executable).resolve()
        policy_path_entries.append(runtime_realpath.parent)
        allowed_exact = frozenset({*allowed_exact, runtime_realpath.name})
    except OSError:
        pass

    # --- secret exposure: fold allowed secrets into env when permitted ----
    if "env" in exposure_modes:
        for secret_id, secret_value in resolved_secrets.items():
            env_vars[secret_id] = secret_value

    # --- redaction config --------------------------------------------------
    redaction_spec: Mapping[str, Any] = policy.get("evidence_redaction", {})
    env_key_regexes = tuple(
        re.compile(p) for p in redaction_spec.get("env_keys_matching", ())
    )
    stdout_regexes = tuple(
        re.compile(p) for p in redaction_spec.get("stdout_patterns", ())
    )
    file_regexes = tuple(
        re.compile(p) for p in redaction_spec.get("file_content_patterns", ())
    )
    redaction = RedactionConfig(
        env_keys_matching=env_key_regexes,
        stdout_patterns=stdout_regexes,
        file_content_patterns=file_regexes,
    )

    sandbox = SandboxedEnvironment(
        env_vars=dict(env_vars),
        cwd=worktree_root,
        allowed_commands_exact=allowed_exact,
        allowed_command_prefixes=allowed_prefixes,
        policy_derived_path_entries=tuple(policy_path_entries),
        exposure_modes=exposure_modes,
        evidence_redaction=redaction,
        inherit_from_parent=inherit_from_parent,
    )
    return sandbox, violations


# ---------------------------------------------------------------------------
# Validators
# ---------------------------------------------------------------------------


def validate_command(
    command: str,
    resolved_args: tuple[str, ...],
    sandbox: SandboxedEnvironment,
    secret_values: Mapping[str, str],
) -> list[PolicyViolation]:
    """Validate ``command`` against the allowlist + PATH-anchor and scan
    ``resolved_args`` for secret leakage.

    Steps (plan v2 B1 hardening):
    1. Resolve via ``shutil.which`` using sandbox PATH.
    2. If missing → ``command_not_allowlisted``.
    3. Compute realpath (expand symlinks).
    4. Accept if realpath is under ANY of
       ``allowed_command_prefixes`` OR (basename is in
       ``allowed_commands_exact`` AND realpath parent is under a
       ``policy_derived_path_entries`` entry).
    5. Else → ``command_path_outside_policy``.
    6. For each arg: if any secret value appears verbatim →
       ``secret_exposure_denied`` with ``field_path=args[i]``.
    """
    violations: list[PolicyViolation] = []
    policy_ref = "ao_kernel/defaults/policies/policy_worktree_profile.v1.json"

    resolved = shutil.which(command, path=sandbox.env_vars.get("PATH", ""))
    if resolved is None:
        violations.append(PolicyViolation(
            kind="command_not_allowlisted",
            detail=f"command {command!r} not resolvable via sandbox PATH",
            policy_ref=policy_ref,
            field_path="command_allowlist",
        ))
        return violations

    realpath = Path(os.path.realpath(resolved))
    basename = realpath.name

    prefix_ok = any(
        _is_path_under(realpath, Path(prefix))
        for prefix in sandbox.allowed_command_prefixes
    )
    exact_ok_with_anchor = (
        basename in sandbox.allowed_commands_exact
        and any(
            _is_path_under(realpath, anchor)
            for anchor in sandbox.policy_derived_path_entries
        )
    )
    if not (prefix_ok or exact_ok_with_anchor):
        violations.append(PolicyViolation(
            kind="command_path_outside_policy",
            detail=(
                f"command {command!r} resolved to {realpath} which is "
                f"outside policy-declared path prefixes"
            ),
            policy_ref=policy_ref,
            field_path="command_allowlist",
        ))

    for idx, arg in enumerate(resolved_args):
        for secret_id, secret_value in secret_values.items():
            if secret_value and secret_value in arg:
                violations.append(PolicyViolation(
                    kind="secret_exposure_denied",
                    detail=(
                        f"secret {secret_id!r} value appears in args[{idx}]"
                    ),
                    policy_ref=policy_ref,
                    field_path=f"args[{idx}]",
                ))

    return violations


def validate_cwd(
    requested_cwd: Path,
    sandbox: SandboxedEnvironment,
) -> list[PolicyViolation]:
    """Ensure ``requested_cwd`` resolves under ``sandbox.cwd``.

    Resolves symlinks on both sides; rejects ``..`` escapes and
    absolute paths outside the worktree root.
    """
    policy_ref = "ao_kernel/defaults/policies/policy_worktree_profile.v1.json"
    try:
        resolved_req = requested_cwd.resolve()
        resolved_root = sandbox.cwd.resolve()
    except OSError as exc:
        return [PolicyViolation(
            kind="cwd_escape",
            detail=f"could not resolve cwd {requested_cwd}: {exc}",
            policy_ref=policy_ref,
            field_path="cwd_confinement.root_template",
        )]

    if not _is_path_under(resolved_req, resolved_root):
        return [PolicyViolation(
            kind="cwd_escape",
            detail=(
                f"resolved cwd {resolved_req} is outside worktree root "
                f"{resolved_root}"
            ),
            policy_ref=policy_ref,
            field_path="cwd_confinement.root_template",
        )]
    return []


def resolve_allowed_secrets(
    policy: Mapping[str, Any],
    all_env: Mapping[str, str],
) -> tuple[dict[str, str], list[PolicyViolation]]:
    """Pick only the secrets listed in
    ``policy.secrets.allowlist_secret_ids`` from ``all_env``.

    Returns ``(resolved_secrets, violations)``. Missing allowlisted
    secret surfaces as ``secret_missing``.
    """
    violations: list[PolicyViolation] = []
    policy_ref = "ao_kernel/defaults/policies/policy_worktree_profile.v1.json"

    secrets_spec: Mapping[str, Any] = policy.get("secrets", {})
    allowlist: Iterable[str] = secrets_spec.get("allowlist_secret_ids", ())

    resolved: dict[str, str] = {}
    for secret_id in allowlist:
        if secret_id in all_env:
            resolved[secret_id] = all_env[secret_id]
        else:
            violations.append(PolicyViolation(
                kind="secret_missing",
                detail=f"secret {secret_id!r} not present in host env",
                policy_ref=policy_ref,
                field_path="secrets.allowlist_secret_ids",
            ))
    return resolved, violations


def check_http_header_exposure(
    *,
    policy: Mapping[str, Any],
    adapter_manifest_invocation: Mapping[str, Any],
) -> list[PolicyViolation]:
    """Plan v2 Q4 W: HTTP adapter gate.

    If the adapter declares ``invocation.http.auth_secret_id_ref`` (i.e.
    it WILL inject a secret into an HTTP header), the policy MUST allow
    ``"http_header"`` in ``secrets.exposure_modes``. Otherwise the
    invocation is denied before any request is built.
    """
    if adapter_manifest_invocation.get("transport") != "http":
        return []
    auth_ref = adapter_manifest_invocation.get("auth_secret_id_ref")
    if not auth_ref:
        return []
    exposure_modes = frozenset(
        policy.get("secrets", {}).get("exposure_modes", ())
    )
    if "http_header" in exposure_modes:
        return []
    return [PolicyViolation(
        kind="http_header_exposure_unauthorized",
        detail=(
            f"HTTP adapter binds auth_secret_id_ref={auth_ref!r} but "
            f"policy.secrets.exposure_modes does not include 'http_header'"
        ),
        policy_ref="ao_kernel/defaults/policies/policy_worktree_profile.v1.json",
        field_path="secrets.exposure_modes",
    )]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _is_path_under(candidate: Path, root: Path) -> bool:
    """Return True iff ``candidate`` is equal to or a descendant of ``root``.

    Both paths must already be resolved (``realpath``-form). Uses
    ``Path.parts`` prefix comparison so no string-level false positives.
    """
    try:
        candidate_parts = candidate.parts
        root_parts = root.parts
    except (TypeError, ValueError):
        return False
    if len(candidate_parts) < len(root_parts):
        return False
    return candidate_parts[: len(root_parts)] == root_parts


__all__ = [
    "RedactionConfig",
    "SandboxedEnvironment",
    "build_sandbox",
    "validate_command",
    "validate_cwd",
    "resolve_allowed_secrets",
    "check_http_header_exposure",
]
