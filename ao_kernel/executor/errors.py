"""Executor subsystem exceptions + PolicyViolation record.

Typed hierarchy for runtime adapter invocation failures. Callers switch
on exception type (and ``reason`` / ``kind`` fields) rather than parse
messages. ``PolicyViolation`` is a structured record (not an exception);
``PolicyViolationError`` wraps a list of them for the fail-closed raise.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


class ExecutorError(Exception):
    """Base for all executor-related errors."""


@dataclass(frozen=True)
class PolicyViolation:
    """Structured violation record for plan v2 Q2/Q4/Q5 hardened enforcement.

    ``kind`` taxonomy:
    - ``env_unknown``: parent env key present but not in allowed_keys.
    - ``env_missing_required``: required env key absent with no
      explicit_additions entry.
    - ``command_not_allowlisted``: resolved command does not match any
      ``command_allowlist`` entry.
    - ``command_path_outside_policy``: resolved command realpath is not
      under any policy-declared path prefix (PATH poisoning guard).
    - ``cwd_escape``: requested cwd resolves outside the worktree root.
    - ``secret_exposure_denied``: secret value appears in a channel not
      listed in ``policy.secrets.exposure_modes``.
    - ``secret_missing``: secret id in ``allowlist_secret_ids`` has no
      value in resolved env.
    - ``http_header_exposure_unauthorized``: HTTP adapter binds an
      ``auth_secret_id_ref`` but ``policy.secrets.exposure_modes`` does
      not include ``"http_header"``.
    """

    kind: Literal[
        "env_unknown",
        "env_missing_required",
        "command_not_allowlisted",
        "command_path_outside_policy",
        "cwd_escape",
        "secret_exposure_denied",
        "secret_missing",
        "http_header_exposure_unauthorized",
    ]
    detail: str
    policy_ref: str
    field_path: str


class PolicyViolationError(ExecutorError):
    """Raised when adapter invocation would violate
    ``policy_worktree_profile``.

    ``violations`` is the structured issue list; callers / audit writers
    project it into ``policy_denied`` evidence events.
    """

    def __init__(self, *, violations: list[PolicyViolation]) -> None:
        self.violations = violations
        if violations:
            first = violations[0]
            tail = (
                f" (+{len(violations) - 1} more)"
                if len(violations) > 1
                else ""
            )
            super().__init__(
                f"{len(violations)} policy violation(s): "
                f"{first.kind}={first.detail}{tail}"
            )
        else:
            super().__init__("0 policy violations (defensive raise)")


class AdapterInvocationFailedError(ExecutorError):
    """Adapter invocation failed at transport layer (before output parse).

    ``reason`` enumerates transport-level failure modes; callers map
    these to ``output_envelope.error.category`` for the workflow run
    record.
    """

    _REASONS = frozenset({
        "command_not_found",
        "timeout",
        "non_zero_exit",
        "http_error",
        "http_timeout",
        "connection_refused",
        "stdin_write_failed",
        "subprocess_crash",
    })

    def __init__(self, *, reason: str, detail: str = "") -> None:
        self.reason = reason
        self.detail = detail
        super().__init__(f"Adapter invocation failed ({reason}): {detail}")


class AdapterOutputParseError(ExecutorError):
    """Adapter returned a payload that could not be parsed as
    ``output_envelope``.

    ``raw_excerpt`` is redacted up to a small length for diagnostics.
    Plan v2 text/plain triple-gate (Q4 B7): embedded-diff-in-prose is
    ambiguous and surfaces here.
    """

    def __init__(self, *, raw_excerpt: str, detail: str = "") -> None:
        self.raw_excerpt = raw_excerpt
        self.detail = detail
        super().__init__(
            f"Adapter output parse failed: {detail} "
            f"(excerpt={raw_excerpt[:120]!r})"
        )


class WorktreeBuilderError(ExecutorError):
    """Per-run worktree creation or cleanup failed."""

    _REASONS = frozenset({
        "git_worktree_failed",
        "permissions",
        "cleanup_failed",
        "disk_full",
        "already_exists",
    })

    def __init__(self, *, reason: str, detail: str = "") -> None:
        self.reason = reason
        self.detail = detail
        super().__init__(f"Worktree operation failed ({reason}): {detail}")


class EvidenceEmitError(ExecutorError):
    """Evidence JSONL write failed (lock acquisition, fsync, disk)."""

    def __init__(self, *, run_id: str, detail: str = "") -> None:
        self.run_id = run_id
        self.detail = detail
        super().__init__(
            f"Evidence emit failed for run={run_id!r}: {detail}"
        )


__all__ = [
    "ExecutorError",
    "PolicyViolation",
    "PolicyViolationError",
    "AdapterInvocationFailedError",
    "AdapterOutputParseError",
    "WorktreeBuilderError",
    "EvidenceEmitError",
]
