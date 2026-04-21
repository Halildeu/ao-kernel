"""Tests for the bundled ``ao_kernel.fixtures.codex_stub`` helper."""

from __future__ import annotations

from ao_kernel.fixtures.codex_stub import resolve_canned_diff


class TestResolveCannedDiff:
    def test_prefers_bugfix_repo_shape_when_present(self, tmp_path) -> None:
        src_dir = tmp_path / "src"
        src_dir.mkdir(parents=True, exist_ok=True)
        (src_dir / "foo.py").write_text("x = 1\n", encoding="utf-8")

        diff = resolve_canned_diff(tmp_path)

        assert "--- a/src/foo.py" in diff
        assert "+++ b/src/foo.py" in diff
        assert "+x = 2" in diff

    def test_preserves_legacy_hello_target_when_available(self, tmp_path) -> None:
        (tmp_path / "hello.txt").write_text("hello\n", encoding="utf-8")

        diff = resolve_canned_diff(tmp_path)

        assert "--- a/hello.txt" in diff
        assert "+++ b/hello.txt" in diff
        assert "+hello world" in diff

    def test_falls_back_to_repo_agnostic_new_file_patch(self, tmp_path) -> None:
        diff = resolve_canned_diff(tmp_path)

        assert "diff --git a/codex_stub_generated.txt b/codex_stub_generated.txt" in diff
        assert "--- /dev/null" in diff
        assert "+++ b/codex_stub_generated.txt" in diff
