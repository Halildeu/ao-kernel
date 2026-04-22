from __future__ import annotations

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
