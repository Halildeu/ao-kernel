"""Patch rollback primitive.

``rollback_patch`` replays the reverse-diff artifact produced by
``apply_patch``. Idempotent when index + worktree are both clean
(Plan v2 invariant #11). ``files_reverted`` is computed from the
reverse-diff content itself (CNS-023 iter-1 W3 absorb) because
``git diff --cached --name-only`` often returns empty after rollback
(index cleared).
"""

from __future__ import annotations

import re
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

from ao_kernel.executor.errors import PolicyViolationError
from ao_kernel.executor.policy_enforcer import (
    SandboxedEnvironment,
    validate_command,
)
from ao_kernel.patch._ids import validate_patch_id
from ao_kernel.patch.errors import PatchRollbackError


# Unified diff file header: "+++ b/<path>" (new-file side) or
# "--- a/<path>" (old-file side). For reverse diffs these are swapped,
# but either side's paths tell us which file was touched. Match either.
_DIFF_PATH = re.compile(r"^(?:\+\+\+|---) [ab]/(.+)$", re.MULTILINE)


@dataclass(frozen=True)
class RollbackResult:
    """Outcome of a rollback invocation. Frozen."""

    patch_id: str
    rolled_back: bool
    idempotent_skip: bool
    files_reverted: tuple[str, ...]
    duration_seconds: float


def rollback_patch(
    worktree_root: Path,
    reverse_diff_id: str,
    sandbox: SandboxedEnvironment,
    run_dir: Path,
    *,
    timeout: float = 60.0,
) -> RollbackResult:
    """Replay the reverse diff for ``reverse_diff_id``.

    Raises ``PatchRollbackError`` with a structured ``reason`` when the
    reverse diff is missing, the worktree has UNRELATED dirty changes
    pre-rollback, or the reverse apply itself fails. Raises
    ``PolicyViolationError`` when ``git`` cannot be resolved under the
    sandbox's policy prefixes (PR-A4a B1 absorb); raises ``ValueError``
    when ``reverse_diff_id`` fails the narrow identifier regex (B3).

    The dirty-check (B2 absorb) compares ``git status --porcelain``
    paths against the files touched by the reverse diff. Changes
    **confined to** the revdiff path set are expected — they are the
    staged result of ``apply_patch`` and rollback will undo them.
    Changes OUTSIDE the revdiff path set are unrelated dirt and
    trigger ``worktree_dirty``.
    """
    validate_patch_id(reverse_diff_id)
    start = time.monotonic()

    revdiff_path = run_dir / "patches" / f"{reverse_diff_id}.revdiff"
    if not revdiff_path.exists():
        raise PatchRollbackError(
            patch_id=reverse_diff_id,
            reason="reverse_diff_missing",
        )

    revdiff_content = revdiff_path.read_text(encoding="utf-8")
    revdiff_paths = frozenset(_extract_paths_from_diff(revdiff_content))

    # Dirty worktree that is NOT the reverse diff's own touched paths
    # → fail-closed. Paths confined to the revdiff set are expected
    # (the apply we're about to undo). Anything else is unrelated dirt.
    unrelated = _unrelated_dirty_paths(
        worktree_root, sandbox.env_vars, revdiff_paths, timeout=timeout,
    )
    if unrelated:
        raise PatchRollbackError(
            patch_id=reverse_diff_id,
            reason="worktree_dirty",
        )

    # Preflight subprocess command against policy
    cmd_check = ["git", "apply", "--check", "--3way", "--index", "-"]
    violations = validate_command(
        cmd_check[0], tuple(cmd_check[1:]), sandbox, secret_values={},
    )
    if violations:
        raise PolicyViolationError(violations=list(violations))

    # Attempt replay. A pre-check with ``git apply --check`` lets us
    # distinguish "already rolled back" (→ idempotent_skip) from a real
    # failure. When the reverse diff cannot be applied cleanly AND the
    # REVERSE of the reverse diff also cannot be applied, we have a
    # state mismatch → fail. When the reverse-of-reverse DOES apply,
    # the worktree is already in the post-rollback state.
    try:
        proc_check = subprocess.run(  # noqa: S603
            cmd_check,
            cwd=worktree_root,
            input=revdiff_content.encode("utf-8"),
            capture_output=True,
            timeout=timeout,
            env=dict(sandbox.env_vars),
            check=False,
        )
    except (subprocess.TimeoutExpired, subprocess.SubprocessError, OSError) as exc:
        raise PatchRollbackError(
            patch_id=reverse_diff_id,
            reason="reverse_apply_failed",
            git_stderr_tail=str(exc),
        ) from None
    if proc_check.returncode != 0:
        # Reverse diff doesn't apply. Is that because we are ALREADY in
        # the post-rollback state? Apply the reverse of the reverse —
        # if THAT applies cleanly, the current worktree already matches
        # the rollback target and this is an idempotent skip.
        try:
            reverse_of_reverse = subprocess.run(  # noqa: S603
                ["git", "apply", "--check", "--3way", "--index", "--reverse", "-"],
                cwd=worktree_root,
                input=revdiff_content.encode("utf-8"),
                capture_output=True,
                timeout=timeout,
                env=dict(sandbox.env_vars),
                check=False,
            )
        except (subprocess.TimeoutExpired, subprocess.SubprocessError, OSError) as exc:
            raise PatchRollbackError(
                patch_id=reverse_diff_id,
                reason="reverse_apply_failed",
                git_stderr_tail=str(exc),
            ) from None
        if reverse_of_reverse.returncode == 0:
            duration = time.monotonic() - start
            return RollbackResult(
                patch_id=reverse_diff_id,
                rolled_back=False,
                idempotent_skip=True,
                files_reverted=(),
                duration_seconds=duration,
            )
        raise PatchRollbackError(
            patch_id=reverse_diff_id,
            reason="reverse_apply_failed",
            git_stderr_tail=_decode(proc_check.stderr),
        )

    # Snapshot the index tree SHA before apply. Compare afterwards —
    # if the SHA is unchanged, ``git apply --3way`` recognised the diff
    # as already-applied-in-spirit (no-op). That case is idempotent.
    pre_sha = _index_tree_sha(worktree_root, sandbox.env_vars, timeout=timeout)

    # Check passed — actually replay
    cmd = ["git", "apply", "--3way", "--index", "-"]
    try:
        proc = subprocess.run(  # noqa: S603
            cmd,
            cwd=worktree_root,
            input=revdiff_content.encode("utf-8"),
            capture_output=True,
            timeout=timeout,
            env=dict(sandbox.env_vars),
        )
    except (subprocess.TimeoutExpired, subprocess.SubprocessError, OSError) as exc:
        raise PatchRollbackError(
            patch_id=reverse_diff_id,
            reason="reverse_apply_failed",
            git_stderr_tail=str(exc),
        ) from None

    if proc.returncode != 0:
        raise PatchRollbackError(
            patch_id=reverse_diff_id,
            reason="reverse_apply_failed",
            git_stderr_tail=_decode(proc.stderr),
        )

    post_sha = _index_tree_sha(worktree_root, sandbox.env_vars, timeout=timeout)
    duration = time.monotonic() - start

    if pre_sha and post_sha and pre_sha == post_sha:
        # Index tree unchanged — apply was semantically a no-op. Report
        # as idempotent skip so callers can distinguish real rollbacks
        # from "already-there" replays (B2 crash-safety + double-call).
        return RollbackResult(
            patch_id=reverse_diff_id,
            rolled_back=False,
            idempotent_skip=True,
            files_reverted=(),
            duration_seconds=duration,
        )

    files = _extract_paths_from_diff(revdiff_content)
    return RollbackResult(
        patch_id=reverse_diff_id,
        rolled_back=True,
        idempotent_skip=False,
        files_reverted=files,
        duration_seconds=duration,
    )


def _index_tree_sha(
    worktree_root: Path,
    env_vars: Mapping[str, str],
    *,
    timeout: float,
) -> str:
    """Return ``git write-tree`` output (tree SHA) or empty on failure.

    Used to snapshot the index state before and after a reverse-diff
    apply. Semantic no-ops produce identical pre/post SHAs even if
    ``git apply --3way`` returned success — a reliable idempotency
    signal across git versions.
    """
    try:
        proc = subprocess.run(  # noqa: S603
            ["git", "write-tree"],
            cwd=worktree_root,
            capture_output=True,
            timeout=timeout,
            env=dict(env_vars),
            check=False,
        )
    except (subprocess.TimeoutExpired, subprocess.SubprocessError, OSError):
        return ""
    if proc.returncode != 0:
        return ""
    return _decode(proc.stdout).strip()


def _unrelated_dirty_paths(
    worktree_root: Path,
    env_vars: Mapping[str, str],
    expected_paths: frozenset[str],
    *,
    timeout: float,
) -> tuple[str, ...]:
    """Return dirty-path set NOT covered by ``expected_paths``.

    ``git status --porcelain`` lines look like ``XY <path>`` (2-char
    status code + space + path). We extract the path and compare
    against the revdiff's touched-file set. Paths in ``expected_paths``
    are the staged result of ``apply_patch`` that rollback will undo;
    anything outside that set is unrelated dirt and must not be
    clobbered.
    """
    try:
        proc = subprocess.run(  # noqa: S603
            ["git", "status", "--porcelain"],
            cwd=worktree_root,
            capture_output=True,
            timeout=timeout,
            env=dict(env_vars),
            check=False,
        )
    except (subprocess.TimeoutExpired, subprocess.SubprocessError, OSError):
        # Conservative fallback: treat as fully unrelated dirt.
        return ("<git-status-unavailable>",)
    if proc.returncode != 0:
        return ("<git-status-nonzero>",)

    unrelated: list[str] = []
    for line in _decode(proc.stdout).splitlines():
        if not line or len(line) < 4:
            continue
        # Porcelain format: XY <path>; XY is 2 chars + space.
        path = line[3:].strip()
        # Rename entries use "orig -> new" — take the new path.
        if " -> " in path:
            path = path.split(" -> ", 1)[1]
        # Strip optional quotes that git adds for paths with spaces.
        path = path.strip('"')
        if path not in expected_paths:
            unrelated.append(path)
    return tuple(unrelated)


def _extract_paths_from_diff(diff_content: str) -> tuple[str, ...]:
    """Pull touched-file paths from unified diff headers."""
    seen: dict[str, None] = {}
    for m in _DIFF_PATH.finditer(diff_content):
        path = m.group(1)
        if path == "/dev/null":
            continue
        seen.setdefault(path, None)
    return tuple(seen.keys())


def _decode(b: bytes | None) -> str:
    if not b:
        return ""
    return b.decode("utf-8", errors="replace")


__all__ = ["RollbackResult", "rollback_patch"]
