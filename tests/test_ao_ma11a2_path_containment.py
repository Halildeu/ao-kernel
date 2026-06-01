"""AO-MA-11A-2 path containment invariants (CLI security)."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from scripts.ao_ma11a2_plan_approval_gate import validate_path_containment


@pytest.fixture
def repo_root(tmp_path: Path) -> Path:
    (tmp_path / "subdir").mkdir()
    (tmp_path / "subdir" / "file.txt").write_text("ok")
    return tmp_path


def test_relative_path_accepted(repo_root):
    ok, err = validate_path_containment("subdir/file.txt", repo_root)
    assert ok, f"err: {err}"


def test_absolute_path_rejected(repo_root):
    ok, err = validate_path_containment("/etc/passwd", repo_root)
    assert not ok
    assert "absolute" in err.lower()


def test_dot_dot_segment_rejected(repo_root):
    ok, err = validate_path_containment("../outside.txt", repo_root)
    assert not ok
    assert ".." in err


def test_nested_dot_dot_segment_rejected(repo_root):
    ok, err = validate_path_containment("subdir/../../escape.txt", repo_root)
    assert not ok


def test_nonexistent_path_rejected(repo_root):
    ok, err = validate_path_containment("missing.txt", repo_root)
    assert not ok
    assert "does not exist" in err.lower()


def test_symlink_escape_rejected(repo_root, tmp_path):
    """Codex iter-3 implementation pin: resolved_path.is_relative_to(repo_root)."""
    # Create an outside file + symlink inside repo pointing to it
    outside = tmp_path.parent / "outside_target.txt"
    outside.write_text("escape")
    symlink_path = repo_root / "escape_link.txt"
    try:
        os.symlink(outside, symlink_path)
    except OSError:
        pytest.skip("symlink unsupported on this platform")
    ok, err = validate_path_containment("escape_link.txt", repo_root)
    assert not ok
    assert "escape" in err.lower() or "repo root" in err.lower()
