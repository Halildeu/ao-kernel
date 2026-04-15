"""Per-run git worktree builder.

Creates a per-run filesystem sandbox at
``<workspace_root>/.ao/runs/<run_id>/worktree/`` so adapters can mutate
files freely without touching the primary checkout. Three strategies
per ``policy.worktree.strategy``:

- ``new_per_run`` (bundled default): fresh ``git worktree add
  --detach`` at HEAD. Cleaned up on completion.
- ``shared_readonly``: chmod-adjusted bind of the main checkout
  (analysis-only adapters). PR-A3 implements the minimal surface;
  practical read-only mount is documented but kept simple (shutil
  copy-on-read).
- ``reuse_per_agent``: stretch goal; deferred behind a ``feature``
  flag. PR-A3 raises for this branch until PR-A4 ships per-agent
  lifecycle.

Permission hardening: the created worktree directory is ``chmod 0o700``
immediately after creation so other users cannot read any extracted
context or intermediate state.

POSIX-only: ``git worktree`` requires a POSIX filesystem and the git
CLI. Callers on Windows see a ``WorktreeBuilderError`` with a clear
message pointing at the Tranche D Windows work.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal, Mapping

from ao_kernel.executor.errors import WorktreeBuilderError


@dataclass(frozen=True)
class WorktreeHandle:
    """Descriptor for a created worktree."""

    run_id: str
    path: Path
    base_revision: str
    strategy: Literal["new_per_run", "reuse_per_agent", "shared_readonly"]
    created_at: str


def create_worktree(
    *,
    workspace_root: Path,
    run_id: str,
    policy: Mapping[str, Any],
) -> WorktreeHandle:
    """Create a worktree per ``policy.worktree.strategy``.

    ``workspace_root`` must point at a git repository or a parent that
    contains ``.git/``. The worktree is created under
    ``workspace_root / ".ao" / "runs" / run_id / "worktree"``.

    Raises ``WorktreeBuilderError`` on git failure, permission issues,
    or unsupported strategy values.
    """
    if sys.platform == "win32":
        raise WorktreeBuilderError(
            reason="permissions",
            detail=(
                "worktree builder is POSIX-only; Windows support is "
                "Tranche D"
            ),
        )

    worktree_spec: Mapping[str, Any] = policy.get("worktree", {})
    strategy_raw = worktree_spec.get("strategy", "new_per_run")
    if strategy_raw not in {
        "new_per_run",
        "reuse_per_agent",
        "shared_readonly",
    }:
        raise WorktreeBuilderError(
            reason="git_worktree_failed",
            detail=f"unknown worktree strategy: {strategy_raw!r}",
        )
    strategy: Literal[
        "new_per_run", "reuse_per_agent", "shared_readonly"
    ] = strategy_raw

    worktree_path = workspace_root / ".ao" / "runs" / run_id / "worktree"
    worktree_path.parent.mkdir(parents=True, exist_ok=True)

    if worktree_path.exists():
        raise WorktreeBuilderError(
            reason="already_exists",
            detail=f"worktree path {worktree_path} already present",
        )

    if strategy == "reuse_per_agent":
        raise WorktreeBuilderError(
            reason="git_worktree_failed",
            detail=(
                "reuse_per_agent strategy is reserved for PR-A4; use "
                "new_per_run for PR-A3 demos"
            ),
        )

    if strategy == "new_per_run":
        base_revision = _run_new_per_run(workspace_root, worktree_path)
    else:  # shared_readonly
        base_revision = _run_shared_readonly(workspace_root, worktree_path)

    try:
        os.chmod(worktree_path, 0o700)
    except OSError as exc:
        _best_effort_rmtree(worktree_path)
        raise WorktreeBuilderError(
            reason="permissions",
            detail=f"chmod 0o700 failed on {worktree_path}: {exc}",
        ) from exc

    return WorktreeHandle(
        run_id=run_id,
        path=worktree_path,
        base_revision=base_revision,
        strategy=strategy,
        created_at=datetime.now(timezone.utc).isoformat(),
    )


def cleanup_worktree(
    handle: WorktreeHandle,
    *,
    workspace_root: Path,
) -> None:
    """Remove the worktree directory and prune git metadata.

    Idempotent: absent worktree is a no-op. Raises
    ``WorktreeBuilderError(reason="cleanup_failed")`` only on explicit
    I/O errors (permissions, disk issue).
    """
    if sys.platform == "win32":
        return  # Windows isn't supported anyway.
    if not handle.path.exists():
        return

    # Try the git-native removal first; it prunes the worktree registry.
    try:
        subprocess.run(
            ["git", "worktree", "remove", "--force", str(handle.path)],
            cwd=str(workspace_root),
            check=False,
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (OSError, subprocess.SubprocessError):
        pass  # fall through to filesystem cleanup

    # Fallback / guarantee: remove the directory tree if it still exists.
    if handle.path.exists():
        try:
            shutil.rmtree(handle.path, ignore_errors=False)
        except OSError as exc:
            raise WorktreeBuilderError(
                reason="cleanup_failed",
                detail=f"rmtree failed on {handle.path}: {exc}",
            ) from exc


# ---------------------------------------------------------------------------
# Strategy implementations
# ---------------------------------------------------------------------------


def _run_new_per_run(
    workspace_root: Path,
    worktree_path: Path,
) -> str:
    """Create a detached-HEAD worktree at HEAD."""
    head_rev = _git_head(workspace_root)
    try:
        proc = subprocess.run(
            [
                "git",
                "worktree",
                "add",
                "--detach",
                str(worktree_path),
                head_rev,
            ],
            cwd=str(workspace_root),
            check=False,
            capture_output=True,
            text=True,
            timeout=60,
        )
    except FileNotFoundError as exc:
        raise WorktreeBuilderError(
            reason="git_worktree_failed",
            detail="git binary not found on PATH",
        ) from exc
    except OSError as exc:
        raise WorktreeBuilderError(
            reason="git_worktree_failed",
            detail=f"git subprocess failed: {exc}",
        ) from exc
    if proc.returncode != 0:
        stderr = (proc.stderr or "").strip()
        reason: Literal[
            "git_worktree_failed",
            "permissions",
            "cleanup_failed",
            "disk_full",
            "already_exists",
        ] = "git_worktree_failed"
        if "No space left" in stderr:
            reason = "disk_full"
        elif "already exists" in stderr or "already checked out" in stderr:
            reason = "already_exists"
        raise WorktreeBuilderError(
            reason=reason,
            detail=stderr or f"git worktree add exited {proc.returncode}",
        )
    return head_rev


def _run_shared_readonly(
    workspace_root: Path,
    worktree_path: Path,
) -> str:
    """Minimal shared_readonly strategy: copy main checkout into the run
    path and chmod the tree read-only. This is NOT a kernel-level
    bind mount; it's a best-effort filesystem copy that prevents adapter
    writes from bleeding back into the primary checkout."""
    head_rev = _git_head(workspace_root)
    try:
        shutil.copytree(
            workspace_root,
            worktree_path,
            ignore=shutil.ignore_patterns(".ao", ".git", "__pycache__"),
            dirs_exist_ok=False,
        )
    except OSError as exc:
        raise WorktreeBuilderError(
            reason="git_worktree_failed",
            detail=f"shared_readonly copytree failed: {exc}",
        ) from exc
    # After copy, chmod -R a-w is the strict interpretation; we chmod the
    # top dir to 0o500 (owner read+execute). Callers wanting to write
    # should use new_per_run.
    try:
        os.chmod(worktree_path, 0o500)
    except OSError as exc:
        _best_effort_rmtree(worktree_path)
        raise WorktreeBuilderError(
            reason="permissions",
            detail=f"chmod 0o500 failed on {worktree_path}: {exc}",
        ) from exc
    return head_rev


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _git_head(workspace_root: Path) -> str:
    """Return the HEAD commit SHA for ``workspace_root``'s git repo."""
    try:
        proc = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=str(workspace_root),
            check=False,
            capture_output=True,
            text=True,
            timeout=10,
        )
    except OSError as exc:
        raise WorktreeBuilderError(
            reason="git_worktree_failed",
            detail=f"git rev-parse failed: {exc}",
        ) from exc
    if proc.returncode != 0:
        raise WorktreeBuilderError(
            reason="git_worktree_failed",
            detail=(proc.stderr or "").strip() or "git rev-parse non-zero exit",
        )
    return proc.stdout.strip()


def _best_effort_rmtree(path: Path) -> None:
    try:
        if path.exists():
            shutil.rmtree(path, ignore_errors=True)
    except OSError:
        pass


__all__ = [
    "WorktreeHandle",
    "create_worktree",
    "cleanup_worktree",
]
