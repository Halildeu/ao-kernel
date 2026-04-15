"""Patch preview primitive.

``preview_diff`` runs ``git apply --check --3way --index --numstat -``
inside a hermetic sandbox. No side effects — the tree and index remain
unchanged. Called by the driver BEFORE ``apply_patch`` and emits the
``diff_previewed`` evidence event at the caller's layer (this module
itself does NOT touch the evidence emitter).

Flag alignment (CNS-023 iter-1 B6 absorb): preflight uses the SAME
``--3way --index`` flags as apply, so a patch that would succeed under
three-way reconciliation is not falsely rejected here. Plain
``--check`` would flag hunks that ``--3way`` can resolve.
"""

from __future__ import annotations

import re
import secrets
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path

from ao_kernel.executor.errors import PolicyViolationError
from ao_kernel.executor.policy_enforcer import (
    SandboxedEnvironment,
    validate_command,
)
from ao_kernel.patch._ids import validate_patch_id
from ao_kernel.patch.errors import PatchPreviewError


# ``--numstat`` prints one line per file: "<added>\t<removed>\t<path>".
# Binary diffs render as "-\t-\t<path>".
_NUMSTAT_LINE = re.compile(r"^([0-9]+|-)\t([0-9]+|-)\t(.+)$")


@dataclass(frozen=True)
class DiffPreview:
    """Result of a preview invocation. Frozen so callers cannot mutate."""

    patch_id: str
    files_changed: tuple[str, ...]
    lines_added: int
    lines_removed: int
    binary_paths: tuple[str, ...]
    conflicts_detected: bool
    git_check_stdout_tail: str
    git_check_stderr_tail: str
    duration_seconds: float


def preview_diff(
    worktree_root: Path,
    patch_content: str,
    sandbox: SandboxedEnvironment,
    *,
    patch_id: str | None = None,
    timeout: float = 30.0,
) -> DiffPreview:
    """Validate ``patch_content`` without side effects.

    Raises ``PatchPreviewError`` when the preflight check fails or when
    a binary-only diff is rejected. Detects binary paths inline but
    does not raise on them here — the caller receives
    ``DiffPreview.binary_paths`` and decides (``apply_patch`` will
    raise ``PatchBinaryUnsupportedError``).

    Raises ``PolicyViolationError`` when the ``git`` command cannot be
    resolved under ``sandbox``'s policy prefixes (PR-A4a B1 absorb —
    primitive now enforces command preflight instead of trusting the
    caller).
    """
    assigned_patch_id = patch_id or secrets.token_urlsafe(32)
    validate_patch_id(assigned_patch_id)
    start = time.monotonic()

    cmd = ["git", "apply", "--check", "--3way", "--index", "--numstat", "-"]
    _enforce_command_policy(cmd, sandbox)
    try:
        proc = subprocess.run(  # noqa: S603 - preflighted + hermetic env
            cmd,
            cwd=worktree_root,
            input=patch_content.encode("utf-8"),
            capture_output=True,
            timeout=timeout,
            env=dict(sandbox.env_vars),
        )
    except subprocess.TimeoutExpired as exc:
        raise PatchPreviewError(
            patch_id=assigned_patch_id,
            reason="timeout",
            git_stderr_tail=_tail(_decode(exc.stderr), 20),
        ) from exc
    except (OSError, subprocess.SubprocessError) as exc:
        raise PatchPreviewError(
            patch_id=assigned_patch_id,
            reason="subprocess_error",
            git_stderr_tail=str(exc),
        ) from None

    duration = time.monotonic() - start
    stdout = _decode(proc.stdout)
    stderr = _decode(proc.stderr)

    if proc.returncode != 0:
        rejected = _extract_rejected_paths(stderr)
        raise PatchPreviewError(
            patch_id=assigned_patch_id,
            files_rejected=rejected,
            git_stderr_tail=_tail(stderr, 20),
            reason="git_check_failed",
        )

    files, added, removed, binary = _parse_numstat(stdout)
    return DiffPreview(
        patch_id=assigned_patch_id,
        files_changed=files,
        lines_added=added,
        lines_removed=removed,
        binary_paths=binary,
        conflicts_detected=False,  # --check pass implies no conflicts
        git_check_stdout_tail=_tail(stdout, 20),
        git_check_stderr_tail=_tail(stderr, 20),
        duration_seconds=duration,
    )


def _enforce_command_policy(
    cmd: list[str],
    sandbox: SandboxedEnvironment,
) -> None:
    """Run PR-A3 validate_command for ``cmd[0]`` with ``cmd[1:]`` args.

    Raises ``PolicyViolationError`` when the resolved command is not
    under a policy prefix or the args leak secrets. No subprocess is
    spawned until this check passes.
    """
    violations = validate_command(
        cmd[0], tuple(cmd[1:]), sandbox, secret_values={},
    )
    if violations:
        raise PolicyViolationError(violations=list(violations))


def _parse_numstat(stdout: str) -> tuple[tuple[str, ...], int, int, tuple[str, ...]]:
    """Parse ``git apply --numstat`` output.

    Returns ``(files_changed, total_added, total_removed, binary_paths)``.
    Binary entries render as ``-\\t-\\t<path>`` and are accumulated into
    ``binary_paths``; their ``added/removed`` counts are 0 (not numeric).
    """
    files: list[str] = []
    binary: list[str] = []
    added = 0
    removed = 0
    for line in stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        m = _NUMSTAT_LINE.match(line)
        if m is None:
            continue
        a_raw, r_raw, path = m.group(1), m.group(2), m.group(3)
        if a_raw == "-" and r_raw == "-":
            binary.append(path)
            files.append(path)
            continue
        try:
            added += int(a_raw)
            removed += int(r_raw)
        except ValueError:
            continue
        files.append(path)
    return tuple(files), added, removed, tuple(binary)


_REJECTED_RE = re.compile(r"^error: patch failed: (.+?):\d+", re.MULTILINE)


def _extract_rejected_paths(stderr: str) -> tuple[str, ...]:
    """Pull unique rejected paths from git's stderr."""
    seen: dict[str, None] = {}
    for m in _REJECTED_RE.finditer(stderr):
        seen.setdefault(m.group(1), None)
    return tuple(seen.keys())


def _decode(b: bytes | None) -> str:
    if not b:
        return ""
    return b.decode("utf-8", errors="replace")


def _tail(text: str, max_lines: int, max_bytes: int = 10_000) -> str:
    """Return the last ``max_lines`` lines, capped at ``max_bytes``."""
    lines = text.splitlines()
    if not lines:
        return ""
    chunk = "\n".join(lines[-max_lines:])
    if len(chunk.encode("utf-8")) > max_bytes:
        chunk = chunk.encode("utf-8")[-max_bytes:].decode("utf-8", errors="replace")
    return chunk


__all__ = ["DiffPreview", "preview_diff"]
