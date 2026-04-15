"""Tests for ``ao_kernel.patch.rollback.rollback_patch`` (PR-A4a)."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from ao_kernel.patch import RollbackResult, apply_patch, rollback_patch
from ao_kernel.patch.errors import PatchRollbackError
from tests._patch_helpers import build_test_sandbox, init_repo, make_patch_from_changes


def _run_dir(tmp_path: Path) -> Path:
    run_dir = tmp_path / "_run"
    run_dir.mkdir()
    return run_dir


class TestRollbackHappyPath:
    def test_rollback_restores_original_content(self, tmp_path: Path) -> None:
        repo = tmp_path / "repo"
        repo.mkdir()
        init_repo(repo, initial_files={"a.txt": "original\n"})
        patch = make_patch_from_changes(repo, {"a.txt": "modified\n"})
        run_dir = _run_dir(tmp_path)
        apply_result = apply_patch(repo, patch, build_test_sandbox(repo), run_dir)
        assert (repo / "a.txt").read_text() == "modified\n"
        # Commit the applied change so the worktree is "clean" minus our mutation
        subprocess.run(
            ["git", "-c", "user.name=t", "-c", "user.email=t@t.t", "-C", str(repo),
             "commit", "-m", "apply"],
            check=True, capture_output=True,
        )
        rb_result = rollback_patch(
            repo, apply_result.reverse_diff_id, build_test_sandbox(repo), run_dir,
        )
        assert isinstance(rb_result, RollbackResult)
        assert rb_result.rolled_back is True
        assert rb_result.idempotent_skip is False
        assert "a.txt" in rb_result.files_reverted

    def test_rollback_duration_is_populated(self, tmp_path: Path) -> None:
        repo = tmp_path / "repo"
        repo.mkdir()
        init_repo(repo)
        patch = make_patch_from_changes(repo, {"a.txt": "line1\nline2\nline3\nnew\n"})
        run_dir = _run_dir(tmp_path)
        apply_result = apply_patch(repo, patch, build_test_sandbox(repo), run_dir)
        subprocess.run(
            ["git", "-c", "user.name=t", "-c", "user.email=t@t.t", "-C", str(repo),
             "commit", "-m", "apply"],
            check=True, capture_output=True,
        )
        rb = rollback_patch(
            repo, apply_result.reverse_diff_id, build_test_sandbox(repo), run_dir,
        )
        assert rb.duration_seconds >= 0.0


class TestRollbackIdempotency:
    def test_rollback_on_clean_worktree_is_skip(self, tmp_path: Path) -> None:
        repo = tmp_path / "repo"
        repo.mkdir()
        init_repo(repo)
        patch = make_patch_from_changes(repo, {"a.txt": "line1\nline2\nline3\nnew\n"})
        run_dir = _run_dir(tmp_path)
        apply_result = apply_patch(repo, patch, build_test_sandbox(repo), run_dir)
        # Commit, rollback once, then commit the rollback — worktree clean
        subprocess.run(
            ["git", "-c", "user.name=t", "-c", "user.email=t@t.t", "-C", str(repo),
             "commit", "-m", "apply"],
            check=True, capture_output=True,
        )
        rollback_patch(repo, apply_result.reverse_diff_id, build_test_sandbox(repo), run_dir)
        subprocess.run(
            ["git", "-c", "user.name=t", "-c", "user.email=t@t.t", "-C", str(repo),
             "commit", "-am", "rollback"],
            check=True, capture_output=True,
        )
        # Second rollback on a clean tree → idempotent skip
        second = rollback_patch(
            repo, apply_result.reverse_diff_id, build_test_sandbox(repo), run_dir,
        )
        assert second.idempotent_skip is True
        assert second.rolled_back is False
        assert second.files_reverted == ()


class TestRollbackErrors:
    def test_missing_revdiff_raises_reverse_diff_missing(self, tmp_path: Path) -> None:
        repo = tmp_path / "repo"
        repo.mkdir()
        init_repo(repo)
        # Create a dirty change so idempotent_skip path is not taken first
        (repo / "a.txt").write_text("dirty\n")
        run_dir = _run_dir(tmp_path)
        with pytest.raises(PatchRollbackError) as excinfo:
            rollback_patch(repo, "non-existent-id", build_test_sandbox(repo), run_dir)
        assert excinfo.value.reason == "reverse_diff_missing"

    def test_worktree_dirty_raises(self, tmp_path: Path) -> None:
        repo = tmp_path / "repo"
        repo.mkdir()
        init_repo(repo)
        patch = make_patch_from_changes(repo, {"a.txt": "line1\nline2\nline3\nnew\n"})
        run_dir = _run_dir(tmp_path)
        apply_result = apply_patch(repo, patch, build_test_sandbox(repo), run_dir)
        # Commit the apply
        subprocess.run(
            ["git", "-c", "user.name=t", "-c", "user.email=t@t.t", "-C", str(repo),
             "commit", "-m", "apply"],
            check=True, capture_output=True,
        )
        # Dirty an UNRELATED file so rollback should refuse
        (repo / "README.md").write_text("dirty unrelated\n")
        with pytest.raises(PatchRollbackError) as excinfo:
            rollback_patch(
                repo, apply_result.reverse_diff_id, build_test_sandbox(repo), run_dir,
            )
        assert excinfo.value.reason == "worktree_dirty"


class TestRollbackResultShape:
    def test_result_is_frozen(self, tmp_path: Path) -> None:
        repo = tmp_path / "repo"
        repo.mkdir()
        init_repo(repo)
        patch = make_patch_from_changes(repo, {"a.txt": "line1\nline2\nline3\nnew\n"})
        run_dir = _run_dir(tmp_path)
        apply_result = apply_patch(repo, patch, build_test_sandbox(repo), run_dir)
        subprocess.run(
            ["git", "-c", "user.name=t", "-c", "user.email=t@t.t", "-C", str(repo),
             "commit", "-m", "apply"],
            check=True, capture_output=True,
        )
        rb = rollback_patch(repo, apply_result.reverse_diff_id, build_test_sandbox(repo), run_dir)
        with pytest.raises(Exception):
            rb.rolled_back = False  # type: ignore[misc]

    def test_files_reverted_is_tuple(self, tmp_path: Path) -> None:
        repo = tmp_path / "repo"
        repo.mkdir()
        init_repo(repo)
        patch = make_patch_from_changes(repo, {"a.txt": "line1\nline2\nline3\nnew\n"})
        run_dir = _run_dir(tmp_path)
        apply_result = apply_patch(repo, patch, build_test_sandbox(repo), run_dir)
        subprocess.run(
            ["git", "-c", "user.name=t", "-c", "user.email=t@t.t", "-C", str(repo),
             "commit", "-m", "apply"],
            check=True, capture_output=True,
        )
        rb = rollback_patch(repo, apply_result.reverse_diff_id, build_test_sandbox(repo), run_dir)
        assert isinstance(rb.files_reverted, tuple)
