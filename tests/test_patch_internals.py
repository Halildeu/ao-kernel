"""Internal helper coverage for ``ao_kernel.patch.apply`` and
``ao_kernel.patch.rollback``.

These tests exercise private helpers directly (``_find_rej_files``,
``_extract_rej_hunks``, ``_git_rev_parse_head``, ``_generate_reverse_diff``,
``_atomic_write_text``, ``_decode``, ``_tail``, ``_unrelated_dirty_paths``,
``_index_tree_sha``, ``_extract_paths_from_diff``) so the forensic /
cleanup / query paths that are hard to trigger through the public API
(3-way conflict reject writing ``.rej`` files deterministically) still
have coverage.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from ao_kernel.patch.apply import (
    _atomic_write_text,
    _capture_forensics,
    _cleanup_worktree,
    _decode,
    _extract_rej_hunks,
    _find_rej_files,
    _generate_reverse_diff,
    _git_porcelain,
    _git_rev_parse_head,
    _tail,
)
from ao_kernel.patch.rollback import (
    _extract_paths_from_diff,
    _index_tree_sha,
    _unrelated_dirty_paths,
)
from tests._patch_helpers import host_env_for_git, init_repo


def _gen_rej(root: Path, rel: str, body: str = "@@ -1,3 +1,3 @@\n-old\n+new\n") -> Path:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")
    return path


class TestFindRejFiles:
    def test_flat_rej_file_listed(self, tmp_path: Path) -> None:
        _gen_rej(tmp_path, "a.txt.rej")
        result = _find_rej_files(tmp_path)
        assert "a.txt.rej" in result

    def test_nested_rej_file_listed(self, tmp_path: Path) -> None:
        _gen_rej(tmp_path, "sub/dir/b.txt.rej")
        result = _find_rej_files(tmp_path)
        assert any(r.endswith("b.txt.rej") for r in result)

    def test_non_rej_file_ignored(self, tmp_path: Path) -> None:
        (tmp_path / "regular.txt").write_text("hello")
        result = _find_rej_files(tmp_path)
        assert result == ()

    def test_empty_tree_returns_empty(self, tmp_path: Path) -> None:
        assert _find_rej_files(tmp_path) == ()


class TestExtractRejHunks:
    def test_first_hunk_header_extracted(self, tmp_path: Path) -> None:
        _gen_rej(
            tmp_path,
            "x.rej",
            body="@@ -1,3 +1,3 @@\n-old\n+new\n@@ -10,3 +10,3 @@\nsecond\n",
        )
        hunks = _extract_rej_hunks(tmp_path, ("x.rej",))
        assert len(hunks) == 1
        assert "x.rej" in hunks[0]
        assert "@@ -1,3 +1,3 @@" in hunks[0]

    def test_missing_file_skipped(self, tmp_path: Path) -> None:
        # Does not exist but was named; no crash, no entry
        result = _extract_rej_hunks(tmp_path, ("nonexistent.rej",))
        assert result == ()

    def test_rej_without_hunk_marker_returns_empty(self, tmp_path: Path) -> None:
        _gen_rej(tmp_path, "y.rej", body="no hunk marker here\n")
        result = _extract_rej_hunks(tmp_path, ("y.rej",))
        assert result == ()


class TestGitRevParseHead:
    def test_returns_sha_for_valid_repo(self, tmp_path: Path) -> None:
        init_repo(tmp_path)
        sha = _git_rev_parse_head(
            tmp_path, host_env_for_git(), timeout=30.0,
        )
        assert len(sha) == 40
        assert all(c in "0123456789abcdef" for c in sha)

    def test_returns_empty_outside_repo(self, tmp_path: Path) -> None:
        # tmp_path is not a git repo → rev-parse fails non-zero
        sha = _git_rev_parse_head(
            tmp_path, host_env_for_git(), timeout=30.0,
        )
        assert sha == ""


class TestGitPorcelain:
    def test_clean_repo_returns_empty(self, tmp_path: Path) -> None:
        init_repo(tmp_path)
        result = _git_porcelain(tmp_path, host_env_for_git())
        assert result == ()

    def test_dirty_worktree_lists_paths(self, tmp_path: Path) -> None:
        init_repo(tmp_path)
        (tmp_path / "a.txt").write_text("dirty content\n")
        result = _git_porcelain(tmp_path, host_env_for_git())
        assert any("a.txt" in line for line in result)


class TestGenerateReverseDiff:
    def test_empty_index_produces_empty_diff(self, tmp_path: Path) -> None:
        init_repo(tmp_path)
        diff = _generate_reverse_diff(
            tmp_path, host_env_for_git(), timeout=30.0,
        )
        assert diff == ""

    def test_staged_change_produces_reverse_diff(self, tmp_path: Path) -> None:
        init_repo(tmp_path)
        (tmp_path / "a.txt").write_text("completely new\n")
        subprocess.run(
            ["git", "-C", str(tmp_path), "add", "a.txt"],
            check=True, capture_output=True,
        )
        diff = _generate_reverse_diff(
            tmp_path, host_env_for_git(), timeout=30.0,
        )
        # Reverse of "line1/2/3 -> completely new" contains the marker
        assert "diff --git" in diff


class TestAtomicWriteText:
    def test_writes_new_file(self, tmp_path: Path) -> None:
        target = tmp_path / "out.txt"
        _atomic_write_text(target, "hello\nworld\n")
        assert target.read_text() == "hello\nworld\n"

    def test_overwrites_existing_file(self, tmp_path: Path) -> None:
        target = tmp_path / "out.txt"
        target.write_text("old")
        _atomic_write_text(target, "new")
        assert target.read_text() == "new"

    def test_creates_parent_dir(self, tmp_path: Path) -> None:
        target = tmp_path / "nested" / "dir" / "out.txt"
        _atomic_write_text(target, "ok")
        assert target.read_text() == "ok"
        assert target.parent.is_dir()


class TestDecodeAndTail:
    def test_decode_empty_bytes(self) -> None:
        assert _decode(b"") == ""
        assert _decode(None) == ""

    def test_decode_non_utf8_replaces(self) -> None:
        result = _decode(b"\xff\xfe invalid")
        assert isinstance(result, str)

    def test_tail_returns_last_lines(self) -> None:
        text = "\n".join(f"line{i}" for i in range(50))
        out = _tail(text, max_lines=5)
        assert "line49" in out
        assert "line0" not in out

    def test_tail_empty_input(self) -> None:
        assert _tail("", max_lines=10) == ""

    def test_tail_byte_cap_shortens(self) -> None:
        huge = "x" * 100_000
        out = _tail(huge, max_lines=10, max_bytes=100)
        assert len(out.encode("utf-8")) <= 100


class TestExtractPathsFromDiff:
    def test_extracts_both_sides(self) -> None:
        diff = (
            "diff --git a/foo.txt b/foo.txt\n"
            "--- a/foo.txt\n"
            "+++ b/foo.txt\n"
            "@@ -1 +1 @@\n-old\n+new\n"
        )
        paths = _extract_paths_from_diff(diff)
        assert "foo.txt" in paths

    def test_dev_null_excluded(self) -> None:
        diff = (
            "diff --git a/new.txt b/new.txt\n"
            "--- /dev/null\n"
            "+++ b/new.txt\n"
            "@@ -0,0 +1 @@\n+content\n"
        )
        paths = _extract_paths_from_diff(diff)
        assert "new.txt" in paths
        assert "/dev/null" not in paths

    def test_empty_diff_empty_result(self) -> None:
        assert _extract_paths_from_diff("") == ()


class TestIndexTreeSha:
    def test_returns_sha_for_valid_repo(self, tmp_path: Path) -> None:
        init_repo(tmp_path)
        sha = _index_tree_sha(
            tmp_path, host_env_for_git(), timeout=30.0,
        )
        assert len(sha) == 40

    def test_returns_empty_outside_repo(self, tmp_path: Path) -> None:
        # tmp_path is not a git repo → write-tree fails
        sha = _index_tree_sha(
            tmp_path, host_env_for_git(), timeout=30.0,
        )
        assert sha == ""


class TestCaptureForensics:
    def test_captures_rej_files_into_tarball(self, tmp_path: Path) -> None:
        import tarfile
        worktree = tmp_path / "wt"
        worktree.mkdir()
        _gen_rej(worktree, "a.txt.rej", body="@@ -1 +1 @@\n-old\n+new\n")
        run_dir = tmp_path / "run"
        run_dir.mkdir()
        _capture_forensics(
            run_dir, "patch-xyz", worktree, ("a.txt.rej",),
        )
        tar_path = run_dir / "artifacts" / "rejected" / "patch-xyz.tgz"
        assert tar_path.exists()
        with tarfile.open(tar_path, "r:gz") as tar:
            names = tar.getnames()
            assert "a.txt.rej" in names
            assert "REJECTED_PATHS.txt" in names

    def test_missing_rej_file_does_not_crash(self, tmp_path: Path) -> None:
        worktree = tmp_path / "wt"
        worktree.mkdir()
        run_dir = tmp_path / "run"
        run_dir.mkdir()
        # Pass a rej path that doesn't actually exist on disk
        _capture_forensics(
            run_dir, "p1", worktree, ("nonexistent.rej",),
        )
        # Still creates the output path with the manifest entry
        assert (run_dir / "artifacts" / "rejected" / "p1.tgz").exists()


class TestCleanupWorktree:
    def test_reset_removes_rej_files(self, tmp_path: Path) -> None:
        init_repo(tmp_path)
        (tmp_path / "a.txt").write_text("dirty\n")
        _gen_rej(tmp_path, "a.txt.rej")
        _cleanup_worktree(tmp_path, host_env_for_git())
        # .rej files removed
        assert not (tmp_path / "a.txt.rej").exists()

    def test_cleanup_on_non_repo_is_lenient(self, tmp_path: Path) -> None:
        # Non-git dir — reset will fail non-zero, but cleanup is lenient
        _gen_rej(tmp_path, "a.rej")
        # Should not raise
        _cleanup_worktree(tmp_path, host_env_for_git())
        # The lenient cleanup loop still removes the .rej file
        assert not (tmp_path / "a.rej").exists()


class TestUnrelatedDirtyPaths:
    def test_clean_repo_empty(self, tmp_path: Path) -> None:
        init_repo(tmp_path)
        result = _unrelated_dirty_paths(
            tmp_path, host_env_for_git(),
            expected_paths=frozenset(),
            timeout=30.0,
        )
        assert result == ()

    def test_expected_path_is_filtered(self, tmp_path: Path) -> None:
        init_repo(tmp_path)
        (tmp_path / "a.txt").write_text("dirty\n")
        result = _unrelated_dirty_paths(
            tmp_path, host_env_for_git(),
            expected_paths=frozenset({"a.txt"}),
            timeout=30.0,
        )
        assert result == ()

    def test_unrelated_path_surfaces(self, tmp_path: Path) -> None:
        init_repo(tmp_path)
        (tmp_path / "a.txt").write_text("dirty\n")
        (tmp_path / "b.txt").write_text("also dirty\n")
        result = _unrelated_dirty_paths(
            tmp_path, host_env_for_git(),
            expected_paths=frozenset({"a.txt"}),
            timeout=30.0,
        )
        assert "b.txt" in result

    def test_broken_git_returns_sentinel(self, tmp_path: Path) -> None:
        # Not a git repo → porcelain exits non-zero
        result = _unrelated_dirty_paths(
            tmp_path, host_env_for_git(),
            expected_paths=frozenset(),
            timeout=30.0,
        )
        # Conservative sentinel when git fails
        assert result == ("<git-status-nonzero>",)
