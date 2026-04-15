"""Public facade for ``ao_kernel.patch`` — governed diff / patch engine.

PR-A4a primitives: ``preview_diff`` (pre-flight validation via
``git apply --check --3way --index -``), ``apply_patch`` (``git apply
--3way --index -`` + deterministic reverse-diff atomic write),
``rollback_patch`` (reverse-diff replay; idempotent on clean worktree).

Typed errors let callers triage without parsing messages:
``PatchPreviewError`` for check failures, ``PatchApplyError`` for
non-conflict apply failures, ``PatchApplyConflictError`` for 3-way
reject cases (with forensic capture + cleanup already performed),
``PatchRollbackError`` for rollback failures, and
``PatchBinaryUnsupportedError`` for binary diffs (scope out).

Internal helpers (``_atomic_write_text``, ``_find_rej_files``, etc.)
are intentionally NOT re-exported; the narrow surface prevents external
code from depending on forensic-capture implementation details.
"""

from __future__ import annotations

from ao_kernel.patch.apply import ApplyResult, apply_patch
from ao_kernel.patch.diff_engine import DiffPreview, preview_diff
from ao_kernel.patch.errors import (
    PatchApplyConflictError,
    PatchApplyError,
    PatchBinaryUnsupportedError,
    PatchError,
    PatchPreviewError,
    PatchRollbackError,
)
from ao_kernel.patch.rollback import RollbackResult, rollback_patch

__all__ = [
    # Results / DTOs
    "ApplyResult",
    "DiffPreview",
    "RollbackResult",
    # Primitives
    "apply_patch",
    "preview_diff",
    "rollback_patch",
    # Errors
    "PatchApplyConflictError",
    "PatchApplyError",
    "PatchBinaryUnsupportedError",
    "PatchError",
    "PatchPreviewError",
    "PatchRollbackError",
]
