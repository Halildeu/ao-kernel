"""Coverage for ``ao_kernel.patch.errors`` + ``ao_kernel.patch._ids``."""

from __future__ import annotations

import pytest

from ao_kernel.patch._ids import validate_patch_id
from ao_kernel.patch.errors import (
    PatchApplyConflictError,
    PatchApplyError,
    PatchBinaryUnsupportedError,
    PatchError,
    PatchPreviewError,
    PatchRollbackError,
)


class TestPatchPreviewError:
    def test_default_reason_is_git_check_failed(self) -> None:
        err = PatchPreviewError(patch_id="p1")
        assert err.reason == "git_check_failed"
        assert err.patch_id == "p1"
        assert err.files_rejected == ()
        assert err.git_stderr_tail == ""

    def test_carries_files_rejected(self) -> None:
        err = PatchPreviewError(
            patch_id="p1",
            files_rejected=("a.txt", "b.txt"),
            git_stderr_tail="error: patch failed: a.txt:10",
            reason="git_check_failed",
        )
        assert err.files_rejected == ("a.txt", "b.txt")
        assert "a.txt:10" in err.git_stderr_tail

    def test_timeout_reason_accepted(self) -> None:
        err = PatchPreviewError(patch_id="p1", reason="timeout")
        assert err.reason == "timeout"

    def test_subprocess_error_reason(self) -> None:
        err = PatchPreviewError(patch_id="p1", reason="subprocess_error")
        assert err.reason == "subprocess_error"


class TestPatchApplyError:
    def test_carries_exit_code(self) -> None:
        err = PatchApplyError(patch_id="p1", exit_code=128)
        assert err.exit_code == 128
        assert err.patch_id == "p1"


class TestPatchApplyConflictError:
    def test_captures_conflict_paths(self) -> None:
        err = PatchApplyConflictError(
            patch_id="p1",
            conflict_paths=("a.txt.rej", "b.txt.rej"),
            rejected_hunks=("a.txt: @@ -1,3 +1,3 @@",),
            dirty_paths=(" M a.txt", "?? a.txt.rej"),
        )
        assert err.conflict_paths == ("a.txt.rej", "b.txt.rej")
        assert err.rejected_hunks == ("a.txt: @@ -1,3 +1,3 @@",)
        assert err.dirty_paths == (" M a.txt", "?? a.txt.rej")
        assert "2 file(s)" in str(err)

    def test_empty_optionals_default_to_empty_tuples(self) -> None:
        err = PatchApplyConflictError(patch_id="p1", conflict_paths=("x",))
        assert err.rejected_hunks == ()
        assert err.dirty_paths == ()


class TestPatchRollbackError:
    @pytest.mark.parametrize(
        "reason",
        ["reverse_diff_missing", "reverse_apply_failed", "worktree_dirty"],
    )
    def test_reason_variants(self, reason: str) -> None:
        err = PatchRollbackError(patch_id="p1", reason=reason)
        assert err.reason == reason
        assert reason in str(err)


class TestPatchBinaryUnsupportedError:
    def test_reports_binary_paths(self) -> None:
        err = PatchBinaryUnsupportedError(
            patch_id="p1",
            binary_paths=("image.png", "bin/tool"),
        )
        assert err.binary_paths == ("image.png", "bin/tool")
        assert "2 binary path" in str(err)


class TestPatchErrorHierarchy:
    def test_all_subclass_patch_error(self) -> None:
        assert issubclass(PatchPreviewError, PatchError)
        assert issubclass(PatchApplyError, PatchError)
        assert issubclass(PatchApplyConflictError, PatchError)
        assert issubclass(PatchRollbackError, PatchError)
        assert issubclass(PatchBinaryUnsupportedError, PatchError)


class TestValidatePatchId:
    def test_accepts_typical_token_urlsafe(self) -> None:
        validate_patch_id("abc123_DEF-456")

    def test_rejects_non_string(self) -> None:
        with pytest.raises(ValueError, match="must be a string"):
            validate_patch_id(123)  # type: ignore[arg-type]

    def test_rejects_dot(self) -> None:
        with pytest.raises(ValueError, match="must match"):
            validate_patch_id("has.dot")

    def test_rejects_over_length(self) -> None:
        with pytest.raises(ValueError):
            validate_patch_id("a" * 129)

    def test_accepts_max_length(self) -> None:
        # Returns None on success; no exception is the assertion.
        result = validate_patch_id("a" * 128)
        assert result is None
