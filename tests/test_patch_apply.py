"""Tests for ``ao_kernel.patch.apply.apply_patch`` (PR-A4a)."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from ao_kernel.patch import ApplyResult, apply_patch
from ao_kernel.patch.errors import (
    PatchApplyConflictError,
    PatchApplyError,
    PatchPreviewError,
)
from tests._patch_helpers import build_test_sandbox, init_repo, make_patch_from_changes


def _run_dir(tmp_path: Path) -> Path:
    run_dir = tmp_path / "_run"
    run_dir.mkdir()
    return run_dir


class TestApplyHappyPath:
    def test_simple_modification_applies(self, tmp_path: Path) -> None:
        repo = tmp_path / "repo"
        repo.mkdir()
        init_repo(repo)
        patch = make_patch_from_changes(repo, {"a.txt": "X\nY\nZ\n"})
        run_dir = _run_dir(tmp_path)
        result = apply_patch(repo, patch, build_test_sandbox(repo), run_dir)
        assert isinstance(result, ApplyResult)
        assert result.applied is True
        assert (repo / "a.txt").read_text() == "X\nY\nZ\n"

    def test_reverse_diff_file_written(self, tmp_path: Path) -> None:
        repo = tmp_path / "repo"
        repo.mkdir()
        init_repo(repo)
        patch = make_patch_from_changes(repo, {"a.txt": "X\nY\nZ\n"})
        run_dir = _run_dir(tmp_path)
        result = apply_patch(repo, patch, build_test_sandbox(repo), run_dir)
        assert result.reverse_diff_path.exists()
        assert result.reverse_diff_path == run_dir / "patches" / f"{result.patch_id}.revdiff"
        assert result.reverse_diff_path.read_text()

    def test_reverse_diff_id_equals_patch_id(self, tmp_path: Path) -> None:
        repo = tmp_path / "repo"
        repo.mkdir()
        init_repo(repo)
        patch = make_patch_from_changes(repo, {"a.txt": "X\nY\nZ\n"})
        run_dir = _run_dir(tmp_path)
        result = apply_patch(repo, patch, build_test_sandbox(repo), run_dir)
        assert result.reverse_diff_id == result.patch_id

    def test_custom_patch_id_is_propagated(self, tmp_path: Path) -> None:
        repo = tmp_path / "repo"
        repo.mkdir()
        init_repo(repo)
        patch = make_patch_from_changes(repo, {"a.txt": "X\nY\nZ\n"})
        run_dir = _run_dir(tmp_path)
        result = apply_patch(
            repo, patch, build_test_sandbox(repo), run_dir, patch_id="custom-apply-id"
        )
        assert result.patch_id == "custom-apply-id"
        assert result.reverse_diff_path.name == "custom-apply-id.revdiff"

    def test_applied_sha_is_captured(self, tmp_path: Path) -> None:
        repo = tmp_path / "repo"
        repo.mkdir()
        init_repo(repo)
        patch = make_patch_from_changes(repo, {"a.txt": "X\nY\nZ\n"})
        run_dir = _run_dir(tmp_path)
        result = apply_patch(repo, patch, build_test_sandbox(repo), run_dir)
        # applied_sha should be a 40-char hex commit hash
        assert len(result.applied_sha) == 40
        assert all(c in "0123456789abcdef" for c in result.applied_sha)

    def test_index_is_staged_after_apply(self, tmp_path: Path) -> None:
        repo = tmp_path / "repo"
        repo.mkdir()
        init_repo(repo)
        patch = make_patch_from_changes(repo, {"a.txt": "X\nY\nZ\n"})
        run_dir = _run_dir(tmp_path)
        apply_patch(repo, patch, build_test_sandbox(repo), run_dir)
        proc = subprocess.run(
            ["git", "-C", str(repo), "diff", "--cached", "--name-only"],
            capture_output=True, text=True, check=True,
        )
        assert "a.txt" in proc.stdout

    def test_files_changed_populated(self, tmp_path: Path) -> None:
        repo = tmp_path / "repo"
        repo.mkdir()
        init_repo(repo, initial_files={"a.txt": "x\n", "b.txt": "y\n"})
        patch = make_patch_from_changes(repo, {"a.txt": "x\nmore\n", "b.txt": "y\nmore\n"})
        run_dir = _run_dir(tmp_path)
        result = apply_patch(repo, patch, build_test_sandbox(repo), run_dir)
        assert set(result.files_changed) >= {"a.txt", "b.txt"}


class TestApplyRejectsBadInput:
    def test_preflight_failure_prevents_apply(self, tmp_path: Path) -> None:
        repo = tmp_path / "repo"
        repo.mkdir()
        init_repo(repo)
        run_dir = _run_dir(tmp_path)
        with pytest.raises(PatchPreviewError):
            apply_patch(repo, "not a patch\n", build_test_sandbox(repo), run_dir)
        # No reverse diff file should have been created
        patches_dir = run_dir / "patches"
        if patches_dir.exists():
            assert list(patches_dir.glob("*.revdiff")) == []


class TestApplyConflict:
    def test_conflict_raises_with_rej_paths(self, tmp_path: Path) -> None:
        repo = tmp_path / "repo"
        repo.mkdir()
        init_repo(repo, initial_files={"a.txt": "line1\nline2\nline3\n"})
        # Build a patch against a NEW state of a.txt...
        patch = make_patch_from_changes(repo, {"a.txt": "line1\nline2\nline3\nadded\n"})
        # ...but mutate a.txt differently on disk so --3way conflicts
        (repo / "a.txt").write_text("completely\ndifferent\ncontent\nhere\n")
        subprocess.run(
            ["git", "-c", "user.name=t", "-c", "user.email=t@t.t", "-C", str(repo),
             "commit", "-am", "drift"],
            check=True, capture_output=True,
        )
        run_dir = _run_dir(tmp_path)
        with pytest.raises((PatchApplyConflictError, PatchApplyError, PatchPreviewError)):
            apply_patch(repo, patch, build_test_sandbox(repo), run_dir)


class TestApplyPolicyPreflight:
    """PR-A4a B1 absorb: subprocess spawn MUST go through
    ``validate_command`` preflight; disallowed commands raise
    ``PolicyViolationError`` before any git invocation."""

    def test_disallowed_git_raises_policy_violation(self, tmp_path: Path) -> None:
        from ao_kernel.executor.errors import PolicyViolationError
        repo = tmp_path / "repo"
        repo.mkdir()
        init_repo(repo)
        patch = make_patch_from_changes(repo, {"a.txt": "X\nY\nZ\n"})
        run_dir = _run_dir(tmp_path)
        # Build a sandbox with a restricted command allowlist that omits git
        narrow = build_test_sandbox(
            repo,
            allowed_commands_exact=frozenset({"python3"}),
            allowed_prefixes=("/nonexistent-prefix",),
        )
        with pytest.raises(PolicyViolationError):
            apply_patch(repo, patch, narrow, run_dir)


class TestApplyPatchIdTraversal:
    """PR-A4a B3 absorb: ``patch_id`` must reject path-separator or
    parent-traversal strings BEFORE any filesystem write."""

    def test_rejects_parent_traversal(self, tmp_path: Path) -> None:
        repo = tmp_path / "repo"
        repo.mkdir()
        init_repo(repo)
        patch = make_patch_from_changes(repo, {"a.txt": "X\nY\nZ\n"})
        run_dir = _run_dir(tmp_path)
        with pytest.raises(ValueError):
            apply_patch(
                repo, patch, build_test_sandbox(repo), run_dir,
                patch_id="../escape",
            )

    def test_rejects_path_separator(self, tmp_path: Path) -> None:
        repo = tmp_path / "repo"
        repo.mkdir()
        init_repo(repo)
        patch = make_patch_from_changes(repo, {"a.txt": "X\nY\nZ\n"})
        run_dir = _run_dir(tmp_path)
        with pytest.raises(ValueError):
            apply_patch(
                repo, patch, build_test_sandbox(repo), run_dir,
                patch_id="nested/path",
            )

    def test_rejects_empty_id(self, tmp_path: Path) -> None:
        repo = tmp_path / "repo"
        repo.mkdir()
        init_repo(repo)
        patch = make_patch_from_changes(repo, {"a.txt": "X\nY\nZ\n"})
        run_dir = _run_dir(tmp_path)
        with pytest.raises(ValueError):
            apply_patch(
                repo, patch, build_test_sandbox(repo), run_dir,
                patch_id="",
            )

    def test_accepts_token_urlsafe_format(self, tmp_path: Path) -> None:
        import secrets as _s
        repo = tmp_path / "repo"
        repo.mkdir()
        init_repo(repo)
        patch = make_patch_from_changes(repo, {"a.txt": "X\nY\nZ\n"})
        run_dir = _run_dir(tmp_path)
        custom_id = _s.token_urlsafe(32)  # 43 URL-safe chars
        result = apply_patch(
            repo, patch, build_test_sandbox(repo), run_dir,
            patch_id=custom_id,
        )
        assert result.patch_id == custom_id


class TestApplyRollbackWithoutCommit:
    """PR-A4a B2 absorb: rollback MUST work immediately after apply
    (before any commit). The dirty-check compares status paths against
    the revdiff path set, so apply-staged paths do not count as
    'unrelated dirt'."""

    def test_apply_then_rollback_round_trip_no_commit(
        self, tmp_path: Path,
    ) -> None:
        from ao_kernel.patch import rollback_patch
        repo = tmp_path / "repo"
        repo.mkdir()
        init_repo(repo, initial_files={"a.txt": "original\n"})
        patch = make_patch_from_changes(repo, {"a.txt": "modified\n"})
        run_dir = _run_dir(tmp_path)
        sandbox = build_test_sandbox(repo)
        apply_result = apply_patch(repo, patch, sandbox, run_dir)
        assert (repo / "a.txt").read_text() == "modified\n"
        # Rollback with NO commit in between — staged state is expected
        rb = rollback_patch(repo, apply_result.reverse_diff_id, sandbox, run_dir)
        assert rb.rolled_back is True
        # File is back to original (index + worktree both staged to "original")
        assert (repo / "a.txt").read_text() == "original\n"

    def test_second_rollback_no_commit_is_idempotent(
        self, tmp_path: Path,
    ) -> None:
        from ao_kernel.patch import rollback_patch
        repo = tmp_path / "repo"
        repo.mkdir()
        init_repo(repo, initial_files={"a.txt": "original\n"})
        patch = make_patch_from_changes(repo, {"a.txt": "modified\n"})
        run_dir = _run_dir(tmp_path)
        sandbox = build_test_sandbox(repo)
        apply_result = apply_patch(repo, patch, sandbox, run_dir)
        rollback_patch(repo, apply_result.reverse_diff_id, sandbox, run_dir)
        # Second rollback — the staged revdiff is still staged but is
        # now a no-op relative to HEAD. Either it skips OR raises a
        # controlled error; it MUST NOT silently re-apply.
        second = rollback_patch(
            repo, apply_result.reverse_diff_id, sandbox, run_dir,
        )
        # Codex iter-4 W1: pin the contract — idempotent_skip contract
        # states rolled_back=False, idempotent_skip=True, files_reverted=().
        assert second.idempotent_skip is True
        assert second.rolled_back is False
        assert second.files_reverted == ()


class TestApplyResultShape:
    def test_apply_result_is_frozen(self, tmp_path: Path) -> None:
        repo = tmp_path / "repo"
        repo.mkdir()
        init_repo(repo)
        patch = make_patch_from_changes(repo, {"a.txt": "X\nY\nZ\n"})
        run_dir = _run_dir(tmp_path)
        result = apply_patch(repo, patch, build_test_sandbox(repo), run_dir)
        with pytest.raises(Exception):
            result.applied = False  # type: ignore[misc]

    def test_duration_is_nonnegative(self, tmp_path: Path) -> None:
        repo = tmp_path / "repo"
        repo.mkdir()
        init_repo(repo)
        patch = make_patch_from_changes(repo, {"a.txt": "X\nY\nZ\n"})
        run_dir = _run_dir(tmp_path)
        result = apply_patch(repo, patch, build_test_sandbox(repo), run_dir)
        assert result.duration_seconds >= 0.0


class TestApplyRevdiffArtifact:
    def test_patches_dir_is_created(self, tmp_path: Path) -> None:
        repo = tmp_path / "repo"
        repo.mkdir()
        init_repo(repo)
        patch = make_patch_from_changes(repo, {"a.txt": "X\nY\nZ\n"})
        run_dir = _run_dir(tmp_path)
        apply_patch(repo, patch, build_test_sandbox(repo), run_dir)
        assert (run_dir / "patches").is_dir()

    def test_revdiff_content_contains_diff_markers(self, tmp_path: Path) -> None:
        repo = tmp_path / "repo"
        repo.mkdir()
        init_repo(repo)
        patch = make_patch_from_changes(repo, {"a.txt": "X\nY\nZ\n"})
        run_dir = _run_dir(tmp_path)
        result = apply_patch(repo, patch, build_test_sandbox(repo), run_dir)
        content = result.reverse_diff_path.read_text()
        # Reverse diff is a unified diff; at least one "diff --git" line
        assert "diff --git" in content or "@@" in content
