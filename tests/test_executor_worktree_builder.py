"""Tests for ``ao_kernel.executor.worktree_builder``.

Covers per-run worktree creation under a tmp git repo, chmod 0o700
enforcement, cleanup idempotency, and strategy dispatch.
"""

from __future__ import annotations

import os
import stat
import subprocess
from pathlib import Path
from typing import Any

import pytest

from ao_kernel.executor import (
    WorktreeBuilderError,
    WorktreeHandle,
    cleanup_worktree,
    create_worktree,
)


def _init_git_repo(root: Path) -> None:
    """Initialize a minimal git repo at ``root`` with one commit."""
    subprocess.run(
        ["git", "init", "-q", str(root)],
        check=True,
    )
    subprocess.run(
        ["git", "-C", str(root), "config", "user.email", "t@e"],
        check=True,
    )
    subprocess.run(
        ["git", "-C", str(root), "config", "user.name", "t"],
        check=True,
    )
    (root / "seed.txt").write_text("seed\n", encoding="utf-8")
    subprocess.run(
        ["git", "-C", str(root), "add", "seed.txt"],
        check=True,
    )
    subprocess.run(
        ["git", "-C", str(root), "commit", "-q", "-m", "seed"],
        check=True,
    )


def _policy(strategy: str = "new_per_run") -> dict[str, Any]:
    return {"worktree": {"strategy": strategy}}


class TestCreateNewPerRun:
    def test_creates_worktree_at_expected_path(self, tmp_path: Path) -> None:
        _init_git_repo(tmp_path)
        rid = "00000000-0000-4000-8000-0000000000a1"
        handle = create_worktree(
            workspace_root=tmp_path, run_id=rid, policy=_policy()
        )
        assert isinstance(handle, WorktreeHandle)
        assert handle.path == tmp_path / ".ao" / "runs" / rid / "worktree"
        assert handle.path.exists()
        assert handle.strategy == "new_per_run"
        assert handle.base_revision  # non-empty SHA

    def test_chmod_0o700_applied(self, tmp_path: Path) -> None:
        _init_git_repo(tmp_path)
        rid = "00000000-0000-4000-8000-0000000000a2"
        handle = create_worktree(
            workspace_root=tmp_path, run_id=rid, policy=_policy()
        )
        mode = stat.S_IMODE(os.stat(handle.path).st_mode)
        assert mode == 0o700, f"got mode {oct(mode)}"

    def test_duplicate_run_id_rejected(self, tmp_path: Path) -> None:
        _init_git_repo(tmp_path)
        rid = "00000000-0000-4000-8000-0000000000a3"
        create_worktree(workspace_root=tmp_path, run_id=rid, policy=_policy())
        with pytest.raises(WorktreeBuilderError) as ei:
            create_worktree(
                workspace_root=tmp_path, run_id=rid, policy=_policy()
            )
        assert ei.value.reason == "already_exists"


class TestStrategy:
    def test_reuse_per_agent_not_in_pr_a3(self, tmp_path: Path) -> None:
        _init_git_repo(tmp_path)
        rid = "00000000-0000-4000-8000-0000000000a4"
        with pytest.raises(WorktreeBuilderError):
            create_worktree(
                workspace_root=tmp_path,
                run_id=rid,
                policy=_policy("reuse_per_agent"),
            )

    def test_unknown_strategy_rejected(self, tmp_path: Path) -> None:
        _init_git_repo(tmp_path)
        rid = "00000000-0000-4000-8000-0000000000a5"
        with pytest.raises(WorktreeBuilderError):
            create_worktree(
                workspace_root=tmp_path,
                run_id=rid,
                policy=_policy("something_nonsense"),
            )


class TestCleanup:
    def test_cleanup_removes_worktree(self, tmp_path: Path) -> None:
        _init_git_repo(tmp_path)
        rid = "00000000-0000-4000-8000-0000000000a6"
        handle = create_worktree(
            workspace_root=tmp_path, run_id=rid, policy=_policy()
        )
        assert handle.path.exists()
        cleanup_worktree(handle, workspace_root=tmp_path)
        assert not handle.path.exists()

    def test_cleanup_idempotent(self, tmp_path: Path) -> None:
        _init_git_repo(tmp_path)
        rid = "00000000-0000-4000-8000-0000000000a7"
        handle = create_worktree(
            workspace_root=tmp_path, run_id=rid, policy=_policy()
        )
        cleanup_worktree(handle, workspace_root=tmp_path)
        # Second call on absent path is a no-op, not an error.
        cleanup_worktree(handle, workspace_root=tmp_path)
        # Idempotent = after both calls the path still doesn't exist.
        assert not handle.path.exists()
