"""Typed errors for ``ao_kernel.patch`` primitives.

Base class ``PatchError`` is independent of ``ao_kernel.executor.errors``
so the patch package can be imported without pulling in executor
dependencies. Keyword-only constructors + structured fields follow the
PR-A3 ``PolicyViolation`` pattern.
"""

from __future__ import annotations

from typing import Literal


class PatchError(Exception):
    """Base class for patch-package errors."""


class PatchPreviewError(PatchError):
    """``git apply --check --3way --index -`` failed; patch cannot be applied.

    ``files_rejected`` captures the per-file paths extracted from git's
    stderr (``error: patch failed: <path>:N``). ``git_stderr_tail`` is
    the last ~20 lines of stderr, capped to 10 KB so evidence payloads
    remain bounded.
    """

    def __init__(
        self,
        *,
        patch_id: str,
        files_rejected: tuple[str, ...] = (),
        git_stderr_tail: str = "",
        reason: Literal["git_check_failed", "timeout", "subprocess_error"] = "git_check_failed",
    ) -> None:
        super().__init__(
            f"patch preview failed ({reason}): {len(files_rejected)} file(s) rejected"
        )
        self.patch_id = patch_id
        self.files_rejected = files_rejected
        self.git_stderr_tail = git_stderr_tail
        self.reason = reason


class PatchApplyError(PatchError):
    """``git apply --3way --index -`` failed non-conflict.

    Covers permission errors, malformed-diff surface, and unexpected
    exit codes that are NOT a 3-way conflict (for those, see
    ``PatchApplyConflictError``).
    """

    def __init__(
        self,
        *,
        patch_id: str,
        exit_code: int,
        git_stderr_tail: str = "",
    ) -> None:
        super().__init__(
            f"patch apply failed (exit={exit_code}): stderr tail omitted"
        )
        self.patch_id = patch_id
        self.exit_code = exit_code
        self.git_stderr_tail = git_stderr_tail


class PatchApplyConflictError(PatchError):
    """``git apply --3way`` partial; ``.rej`` files are present.

    ``conflict_paths`` lists the files whose hunks could not be resolved
    three-way. ``rejected_hunks`` is a tuple of the hunk headers
    extracted from the corresponding ``.rej`` files. ``dirty_paths``
    captures ``git status --porcelain`` output AFTER the partial apply
    so callers can record dirty-state forensics BEFORE cleanup.
    """

    def __init__(
        self,
        *,
        patch_id: str,
        conflict_paths: tuple[str, ...],
        rejected_hunks: tuple[str, ...] = (),
        dirty_paths: tuple[str, ...] = (),
    ) -> None:
        super().__init__(
            f"patch apply conflict: {len(conflict_paths)} file(s) with .rej hunks"
        )
        self.patch_id = patch_id
        self.conflict_paths = conflict_paths
        self.rejected_hunks = rejected_hunks
        self.dirty_paths = dirty_paths


class PatchRollbackError(PatchError):
    """Reverse-diff file missing or reverse apply failed.

    ``reason`` discriminates the failure mode so callers can triage:
    ``reverse_diff_missing`` (file absent), ``reverse_apply_failed``
    (reverse git apply non-zero exit), ``worktree_dirty`` (pre-rollback
    worktree has uncommitted changes; fail-closed to avoid clobbering).
    """

    def __init__(
        self,
        *,
        patch_id: str,
        reason: Literal[
            "reverse_diff_missing",
            "reverse_apply_failed",
            "worktree_dirty",
        ],
        git_stderr_tail: str = "",
    ) -> None:
        super().__init__(f"patch rollback failed ({reason})")
        self.patch_id = patch_id
        self.reason = reason
        self.git_stderr_tail = git_stderr_tail


class PatchBinaryUnsupportedError(PatchError):
    """Binary diff detected; PR-A4 scope disallows binary patches.

    Unified-diff textual patches are the only supported form. Binary
    deltas would require ``git apply --binary`` + index blob handling,
    deferred to FAZ-C agentic editing (#12 adopt+wrap) where Aider-style
    flow handles binary blobs under a different trust model.
    """

    def __init__(
        self,
        *,
        patch_id: str,
        binary_paths: tuple[str, ...],
    ) -> None:
        super().__init__(
            f"binary diff unsupported: {len(binary_paths)} binary path(s)"
        )
        self.patch_id = patch_id
        self.binary_paths = binary_paths


__all__ = [
    "PatchError",
    "PatchPreviewError",
    "PatchApplyError",
    "PatchApplyConflictError",
    "PatchRollbackError",
    "PatchBinaryUnsupportedError",
]
