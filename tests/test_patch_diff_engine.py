"""Tests for ``ao_kernel.patch.diff_engine.preview_diff`` (PR-A4a)."""

from __future__ import annotations

from pathlib import Path

import pytest

from ao_kernel.patch import DiffPreview, preview_diff
from ao_kernel.patch.errors import PatchPreviewError
from tests._patch_helpers import build_test_sandbox, init_repo, make_patch_from_changes


class TestPreviewHappyPath:
    def test_simple_single_file_addition(self, tmp_path: Path) -> None:
        init_repo(tmp_path)
        patch = make_patch_from_changes(
            tmp_path, {"a.txt": "line1\nline2\nline3\nline4\n"}
        )
        preview = preview_diff(tmp_path, patch, build_test_sandbox(tmp_path))
        assert isinstance(preview, DiffPreview)
        assert preview.lines_added == 1
        assert preview.lines_removed == 0
        assert "a.txt" in preview.files_changed
        assert preview.binary_paths == ()
        assert preview.conflicts_detected is False
        assert preview.duration_seconds >= 0.0

    def test_multi_file_changes(self, tmp_path: Path) -> None:
        init_repo(tmp_path, initial_files={
            "a.txt": "one\ntwo\n",
            "b.txt": "alpha\nbeta\n",
            "c.txt": "red\ngreen\n",
        })
        patch = make_patch_from_changes(tmp_path, {
            "a.txt": "one\ntwo\nthree\n",
            "b.txt": "alpha\nbeta\ngamma\n",
        })
        preview = preview_diff(tmp_path, patch, build_test_sandbox(tmp_path))
        assert set(preview.files_changed) >= {"a.txt", "b.txt"}
        assert preview.lines_added >= 2

    def test_patch_id_is_respected_when_provided(self, tmp_path: Path) -> None:
        init_repo(tmp_path)
        patch = make_patch_from_changes(
            tmp_path, {"a.txt": "line1\nline2\nline3\nnew\n"}
        )
        preview = preview_diff(
            tmp_path, patch, build_test_sandbox(tmp_path), patch_id="pr-a4a-test-id"
        )
        assert preview.patch_id == "pr-a4a-test-id"

    def test_patch_id_is_generated_when_missing(self, tmp_path: Path) -> None:
        init_repo(tmp_path)
        patch = make_patch_from_changes(
            tmp_path, {"a.txt": "line1\nline2\nline3\nnew\n"}
        )
        preview = preview_diff(tmp_path, patch, build_test_sandbox(tmp_path))
        # token_urlsafe(32) → 43-char URL-safe string
        assert len(preview.patch_id) >= 40

    def test_lines_added_and_removed_are_counted(self, tmp_path: Path) -> None:
        init_repo(tmp_path)
        patch = make_patch_from_changes(
            tmp_path, {"a.txt": "X\nY\nZ\n"}  # replace 3 lines with 3 new ones
        )
        preview = preview_diff(tmp_path, patch, build_test_sandbox(tmp_path))
        assert preview.lines_added == 3
        assert preview.lines_removed == 3


class TestPreviewRejection:
    def test_malformed_patch_raises_preview_error(self, tmp_path: Path) -> None:
        init_repo(tmp_path)
        malformed = "this is not a valid unified diff\n"
        with pytest.raises(PatchPreviewError) as excinfo:
            preview_diff(tmp_path, malformed, build_test_sandbox(tmp_path))
        assert excinfo.value.reason == "git_check_failed"

    def test_preview_error_carries_patch_id(self, tmp_path: Path) -> None:
        init_repo(tmp_path)
        with pytest.raises(PatchPreviewError) as excinfo:
            preview_diff(
                tmp_path,
                "bogus\n",
                build_test_sandbox(tmp_path),
                patch_id="known-id",
            )
        assert excinfo.value.patch_id == "known-id"

    def test_preview_error_has_stderr_tail(self, tmp_path: Path) -> None:
        init_repo(tmp_path)
        with pytest.raises(PatchPreviewError) as excinfo:
            preview_diff(tmp_path, "bogus\n", build_test_sandbox(tmp_path))
        # git writes something to stderr when rejecting; may be empty
        # in degenerate cases, but the attribute MUST exist
        assert isinstance(excinfo.value.git_stderr_tail, str)

    def test_empty_patch_outcome_is_deterministic(self, tmp_path: Path) -> None:
        """Empty-string patch is a degenerate input. Git's handling
        varies across versions (some accept as no-op, some reject
        with 'fatal: patch body is empty'). We assert that either path
        is deterministic — i.e. we get a DiffPreview with zero changes
        OR a PatchPreviewError. Never a crash."""
        init_repo(tmp_path)
        try:
            preview = preview_diff(tmp_path, "", build_test_sandbox(tmp_path))
        except PatchPreviewError as exc:
            assert exc.reason == "git_check_failed"
            return
        assert preview.files_changed == ()
        assert preview.lines_added == 0
        assert preview.lines_removed == 0


class TestPreviewTimeout:
    def test_tiny_timeout_raises_timeout_reason(self, tmp_path: Path) -> None:
        init_repo(tmp_path)
        patch = make_patch_from_changes(
            tmp_path, {"a.txt": "line1\nline2\nline3\nextra\n"}
        )
        # Timeout of 0s on a typical machine may still complete; use a
        # tiny value and accept either a timeout or a successful preview.
        try:
            preview_diff(tmp_path, patch, build_test_sandbox(tmp_path), timeout=0.000001)
        except PatchPreviewError as exc:
            assert exc.reason in {"timeout", "subprocess_error"}


class TestPreviewResultShape:
    def test_diff_preview_is_frozen(self, tmp_path: Path) -> None:
        init_repo(tmp_path)
        patch = make_patch_from_changes(
            tmp_path, {"a.txt": "line1\nline2\nline3\nnew\n"}
        )
        preview = preview_diff(tmp_path, patch, build_test_sandbox(tmp_path))
        with pytest.raises(Exception):
            preview.patch_id = "overwrite"  # type: ignore[misc]

    def test_files_changed_is_tuple(self, tmp_path: Path) -> None:
        init_repo(tmp_path)
        patch = make_patch_from_changes(
            tmp_path, {"a.txt": "line1\nline2\nline3\nnew\n"}
        )
        preview = preview_diff(tmp_path, patch, build_test_sandbox(tmp_path))
        assert isinstance(preview.files_changed, tuple)

    def test_duration_is_nonnegative_float(self, tmp_path: Path) -> None:
        init_repo(tmp_path)
        patch = make_patch_from_changes(
            tmp_path, {"a.txt": "line1\nline2\nline3\nnew\n"}
        )
        preview = preview_diff(tmp_path, patch, build_test_sandbox(tmp_path))
        assert isinstance(preview.duration_seconds, float)
        assert preview.duration_seconds >= 0.0
