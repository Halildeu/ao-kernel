from __future__ import annotations

import json
import subprocess
from pathlib import Path


OPS_SCRIPT = (
    Path(__file__).resolve().parents[1] / ".claude" / "scripts" / "ops.sh"
)


def _run(cmd: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
    )


def _git(cwd: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return _run(["git", *args], cwd=cwd)


def _init_remote_clone(tmp_path: Path) -> Path:
    remote = tmp_path / "origin.git"
    seed = tmp_path / "seed"
    work = tmp_path / "work"

    _run(["git", "init", "--bare", remote.as_posix()], cwd=tmp_path)
    _run(["git", "clone", remote.as_posix(), seed.as_posix()], cwd=tmp_path)
    _git(seed, "config", "user.email", "t@e")
    _git(seed, "config", "user.name", "t")
    (seed / "README.md").write_text("seed\n", encoding="utf-8")
    _git(seed, "add", "README.md")
    _git(seed, "commit", "-m", "seed")
    _git(seed, "branch", "-M", "main")
    _git(seed, "push", "-u", "origin", "main")
    _run(
        [
            "git",
            "--git-dir",
            remote.as_posix(),
            "symbolic-ref",
            "HEAD",
            "refs/heads/main",
        ],
        cwd=tmp_path,
    )
    _run(["git", "clone", remote.as_posix(), work.as_posix()], cwd=tmp_path)
    _git(work, "config", "user.email", "t@e")
    _git(work, "config", "user.name", "t")
    return work


def _run_preflight(cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", str(OPS_SCRIPT), "preflight"],
        cwd=cwd,
        check=False,
        capture_output=True,
        text=True,
        timeout=20,
    )


def _run_overlap_check(cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", str(OPS_SCRIPT), "overlap-check"],
        cwd=cwd,
        check=False,
        capture_output=True,
        text=True,
        timeout=20,
    )


def _run_close_worktree(cwd: Path, target: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", str(OPS_SCRIPT), "close-worktree", target.as_posix()],
        cwd=cwd,
        check=False,
        capture_output=True,
        text=True,
        timeout=20,
    )


def _run_archive_worktree(cwd: Path, target: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", str(OPS_SCRIPT), "archive-worktree", target.as_posix()],
        cwd=cwd,
        check=False,
        capture_output=True,
        text=True,
        timeout=20,
    )


def test_ops_preflight_clean_repo(tmp_path: Path) -> None:
    work = _init_remote_clone(tmp_path)

    proc = _run_preflight(work)

    assert proc.returncode == 0
    assert "== ops preflight ==" in proc.stdout
    assert "Current worktree: clean" in proc.stdout
    assert "Other worktrees:" in proc.stdout
    assert "  - none" in proc.stdout
    assert "✓ Preflight clean" in proc.stdout


def test_ops_preflight_warns_on_dirty_worktree(tmp_path: Path) -> None:
    work = _init_remote_clone(tmp_path)
    (work / "README.md").write_text("dirty\n", encoding="utf-8")
    (work / "notes.txt").write_text("untracked\n", encoding="utf-8")

    proc = _run_preflight(work)

    assert proc.returncode == 0
    assert "Current worktree: dirty" in proc.stdout
    assert "⚠ Preflight completed with warnings" in proc.stdout
    assert "  - current worktree dirty" in proc.stdout


def test_ops_preflight_fails_on_forbidden_branch_pattern(
    tmp_path: Path,
) -> None:
    work = _init_remote_clone(tmp_path)
    _git(work, "checkout", "-b", "claude/stale", "origin/main")

    proc = _run_preflight(work)

    assert proc.returncode == 1
    assert "YASAK branch pattern: claude/stale" in proc.stdout


def test_ops_overlap_check_clean_single_worktree(tmp_path: Path) -> None:
    work = _init_remote_clone(tmp_path)

    proc = _run_overlap_check(work)

    assert proc.returncode == 0
    assert "== ops overlap-check ==" in proc.stdout
    assert "Attached worktrees: 1" in proc.stdout
    assert "Exact file overlaps:" in proc.stdout
    assert "Shared top-level areas:" in proc.stdout
    assert "  - none" in proc.stdout
    assert "✓ No overlapping changed paths detected" in proc.stdout


def test_ops_overlap_check_reports_exact_file_and_area_overlap(
    tmp_path: Path,
) -> None:
    work = _init_remote_clone(tmp_path)
    wt_a = tmp_path / "wt-a"
    wt_b = tmp_path / "wt-b"

    _run(
        ["git", "worktree", "add", "-b", "feature-a", wt_a.as_posix(), "origin/main"],
        cwd=work,
    )
    _run(
        ["git", "worktree", "add", "-b", "feature-b", wt_b.as_posix(), "origin/main"],
        cwd=work,
    )

    (wt_a / "pkg").mkdir()
    (wt_a / "pkg" / "shared.py").write_text("print('a')\n", encoding="utf-8")
    (wt_a / "pkg" / "only_a.py").write_text("print('only a')\n", encoding="utf-8")
    _git(wt_a, "add", "pkg/shared.py")
    _git(wt_a, "commit", "-m", "add shared path in feature-a")

    (wt_b / "pkg").mkdir()
    (wt_b / "pkg" / "shared.py").write_text("print('b')\n", encoding="utf-8")
    (wt_b / "tests").mkdir()
    (wt_b / "tests" / "test_demo.py").write_text("def test_demo():\n    assert True\n", encoding="utf-8")

    proc = _run_overlap_check(work)

    assert proc.returncode == 0
    assert "Attached worktrees: 3" in proc.stdout
    assert "feature-a" in proc.stdout
    assert "feature-b" in proc.stdout
    assert "pkg/shared.py" in proc.stdout
    assert "pkg" in proc.stdout
    assert "⚠ Overlap risk detected" in proc.stdout


def test_ops_overlap_check_uses_mainline_base_for_pushed_feature_branches(
    tmp_path: Path,
) -> None:
    work = _init_remote_clone(tmp_path)
    wt_a = tmp_path / "wt-a"
    wt_b = tmp_path / "wt-b"

    _run(
        ["git", "worktree", "add", "-b", "feature-a", wt_a.as_posix(), "origin/main"],
        cwd=work,
    )
    _run(
        ["git", "worktree", "add", "-b", "feature-b", wt_b.as_posix(), "origin/main"],
        cwd=work,
    )

    (wt_a / "pkg").mkdir()
    (wt_a / "pkg" / "shared.py").write_text("print('a')\n", encoding="utf-8")
    _git(wt_a, "add", "pkg/shared.py")
    _git(wt_a, "commit", "-m", "feature-a change")
    _git(wt_a, "push", "-u", "origin", "feature-a")

    (wt_b / "pkg").mkdir()
    (wt_b / "pkg" / "shared.py").write_text("print('b')\n", encoding="utf-8")
    _git(wt_b, "add", "pkg/shared.py")
    _git(wt_b, "commit", "-m", "feature-b change")
    _git(wt_b, "push", "-u", "origin", "feature-b")

    proc = _run_overlap_check(work)

    assert proc.returncode == 0
    assert "base: origin/main" in proc.stdout
    assert "pkg/shared.py" in proc.stdout
    assert "feature-a" in proc.stdout
    assert "feature-b" in proc.stdout
    assert "⚠ Overlap risk detected" in proc.stdout


def test_ops_close_worktree_closes_clean_secondary_worktree(
    tmp_path: Path,
) -> None:
    work = _init_remote_clone(tmp_path)
    wt = tmp_path / "wt-close"

    _run(
        ["git", "worktree", "add", "-b", "feature-close", wt.as_posix(), "origin/main"],
        cwd=work,
    )

    proc = _run_close_worktree(work, wt)

    assert proc.returncode == 0
    assert "== ops close-worktree ==" in proc.stdout
    assert "✓ Worktree closed" in proc.stdout
    assert not wt.exists()
    assert wt.as_posix() not in _git(work, "worktree", "list", "--porcelain").stdout


def test_ops_close_worktree_refuses_dirty_secondary_worktree(
    tmp_path: Path,
) -> None:
    work = _init_remote_clone(tmp_path)
    wt = tmp_path / "wt-dirty"

    _run(
        ["git", "worktree", "add", "-b", "feature-dirty", wt.as_posix(), "origin/main"],
        cwd=work,
    )
    (wt / "notes.txt").write_text("dirty\n", encoding="utf-8")

    proc = _run_close_worktree(work, wt)

    assert proc.returncode == 1
    assert "Refusing to close dirty worktree" in proc.stdout
    assert "archive-worktree" in proc.stdout
    assert wt.exists()
    assert wt.as_posix() in _git(work, "worktree", "list", "--porcelain").stdout


def test_ops_close_worktree_refuses_current_worktree(tmp_path: Path) -> None:
    work = _init_remote_clone(tmp_path)

    proc = _run_close_worktree(work, work)

    assert proc.returncode == 1
    assert "Refusing to close current worktree" in proc.stdout


def test_ops_close_worktree_rejects_unknown_target(tmp_path: Path) -> None:
    work = _init_remote_clone(tmp_path)
    unknown = tmp_path / "missing"

    proc = _run_close_worktree(work, unknown)

    assert proc.returncode == 1
    assert "Target is not an attached worktree for this repository" in proc.stdout


def test_ops_archive_worktree_archives_dirty_secondary_and_removes_it(
    tmp_path: Path,
) -> None:
    work = _init_remote_clone(tmp_path)
    wt = tmp_path / "wt-archive"

    _run(
        ["git", "worktree", "add", "-b", "feature-archive", wt.as_posix(), "origin/main"],
        cwd=work,
    )
    (wt / "tracked.txt").write_text("dirty tracked\n", encoding="utf-8")
    _git(wt, "add", "tracked.txt")
    (wt / "tracked.txt").write_text("dirty tracked updated\n", encoding="utf-8")
    (wt / "notes.txt").write_text("untracked note\n", encoding="utf-8")

    proc = _run_archive_worktree(work, wt)

    assert proc.returncode == 0
    assert "== ops archive-worktree ==" in proc.stdout
    assert "✓ Worktree archived and removed" in proc.stdout
    assert not wt.exists()
    assert wt.as_posix() not in _git(work, "worktree", "list", "--porcelain").stdout
    assert "feature-archive" in _git(work, "branch", "--list").stdout

    common_git_dir = (work / ".git").resolve()
    archives = sorted((common_git_dir / "ops-worktree-archives").glob("*feature-archive*"))
    assert len(archives) == 1
    archive_dir = archives[0]
    meta = json.loads((archive_dir / "archive-meta.json").read_text(encoding="utf-8"))
    assert meta["branch"] == "feature-archive"
    assert meta["dirty_status"] == {"staged": 1, "unstaged": 1, "untracked": 1}
    assert "tracked.txt" in (archive_dir / "staged.patch").read_text(encoding="utf-8")
    assert "tracked.txt" in (archive_dir / "unstaged.patch").read_text(encoding="utf-8")
    assert (archive_dir / "untracked" / "notes.txt").read_text(encoding="utf-8") == "untracked note\n"
    assert "notes.txt" in (archive_dir / "untracked-files.txt").read_text(encoding="utf-8")


def test_ops_archive_worktree_refuses_clean_secondary_worktree(
    tmp_path: Path,
) -> None:
    work = _init_remote_clone(tmp_path)
    wt = tmp_path / "wt-clean-archive"

    _run(
        ["git", "worktree", "add", "-b", "feature-clean-archive", wt.as_posix(), "origin/main"],
        cwd=work,
    )

    proc = _run_archive_worktree(work, wt)

    assert proc.returncode == 1
    assert "Refusing to archive clean worktree" in proc.stdout
    assert "close-worktree" in proc.stdout
    assert wt.exists()


def test_ops_archive_worktree_refuses_current_worktree(tmp_path: Path) -> None:
    work = _init_remote_clone(tmp_path)

    proc = _run_archive_worktree(work, work)

    assert proc.returncode == 1
    assert "Refusing to archive current worktree" in proc.stdout


def test_ops_archive_worktree_rejects_unknown_target(tmp_path: Path) -> None:
    work = _init_remote_clone(tmp_path)
    unknown = tmp_path / "missing"

    proc = _run_archive_worktree(work, unknown)

    assert proc.returncode == 1
    assert "Target is not an attached worktree for this repository" in proc.stdout
