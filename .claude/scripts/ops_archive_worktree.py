#!/usr/bin/env python3
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4


@dataclass(frozen=True)
class WorktreeInfo:
    path: Path
    branch: str


@dataclass(frozen=True)
class DirtyStatus:
    staged: int
    unstaged: int
    untracked: int

    @property
    def is_dirty(self) -> bool:
        return bool(self.staged or self.unstaged or self.untracked)


def _run_git(path: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    proc = subprocess.run(
        ["git", "-C", path.as_posix(), *args],
        check=False,
        capture_output=True,
        text=True,
    )
    if check and proc.returncode != 0:
        raise subprocess.CalledProcessError(
            proc.returncode,
            proc.args,
            output=proc.stdout,
            stderr=proc.stderr,
        )
    return proc


def _git_value(path: Path, *args: str) -> str:
    return _run_git(path, *args).stdout.strip()


def _git_lines(path: Path, *args: str) -> list[str]:
    return [line for line in _run_git(path, *args).stdout.splitlines() if line.strip()]


def _resolve_git_common_dir(repo_root: Path) -> Path:
    value = Path(_git_value(repo_root, "rev-parse", "--git-common-dir"))
    return value if value.is_absolute() else (repo_root / value).resolve()


def _parse_worktrees(repo_root: Path) -> list[WorktreeInfo]:
    lines = _run_git(repo_root, "worktree", "list", "--porcelain").stdout.splitlines()
    entries: list[WorktreeInfo] = []
    current_path: Path | None = None
    current_branch: str | None = None

    for line in lines + [""]:
        if not line:
            if current_path is not None:
                entries.append(
                    WorktreeInfo(
                        path=current_path.resolve(),
                        branch=current_branch or "(detached)",
                    )
                )
            current_path = None
            current_branch = None
            continue
        if line.startswith("worktree "):
            current_path = Path(line.removeprefix("worktree "))
        elif line.startswith("branch refs/heads/"):
            current_branch = line.removeprefix("branch refs/heads/")

    return entries


def _count_lines(path: Path, *args: str) -> int:
    return len(_git_lines(path, *args))


def _dirty_status(path: Path) -> DirtyStatus:
    return DirtyStatus(
        staged=_count_lines(path, "diff", "--cached", "--name-only"),
        unstaged=_count_lines(path, "diff", "--name-only"),
        untracked=_count_lines(path, "ls-files", "--others", "--exclude-standard"),
    )


def _branch_slug(branch: str) -> str:
    safe = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "-" for ch in branch)
    return safe.strip("-") or "detached"


def _write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _copy_untracked_files(target: Path, archive_dir: Path) -> list[str]:
    copied: list[str] = []
    for rel in _git_lines(target, "ls-files", "--others", "--exclude-standard"):
        source = target / rel
        if not source.is_file():
            continue
        destination = archive_dir / "untracked" / rel
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
        copied.append(rel)
    return copied


def _print_usage() -> None:
    print("Usage: bash .claude/scripts/ops.sh archive-worktree <path>", file=sys.stderr)


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        _print_usage()
        return 2

    cwd = Path.cwd().resolve()
    repo_root = Path(_git_value(cwd, "rev-parse", "--show-toplevel")).resolve()
    target = Path(argv[1]).expanduser().resolve()
    worktrees = _parse_worktrees(repo_root)
    known_paths = {entry.path: entry for entry in worktrees}

    print("== ops archive-worktree ==")
    print(f"Repo: {repo_root}")
    print(f"Requested target: {target}")

    if target == repo_root:
        print("Refusing to archive current worktree")
        return 1

    if target not in known_paths:
        print("Target is not an attached worktree for this repository")
        return 1

    info = known_paths[target]
    dirty = _dirty_status(target)
    print(f"Target branch: {info.branch}")
    print(
        "Target status: "
        f"staged={dirty.staged}, unstaged={dirty.unstaged}, untracked={dirty.untracked}"
    )

    if not dirty.is_dirty:
        print("Refusing to archive clean worktree")
        print("Next step: use `bash .claude/scripts/ops.sh close-worktree <path>`")
        return 1

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    common_git_dir = _resolve_git_common_dir(repo_root)
    archive_dir = (
        common_git_dir
        / "ops-worktree-archives"
        / f"{timestamp}-{_branch_slug(info.branch)}-{uuid4().hex[:8]}"
    )
    archive_dir.mkdir(parents=True, exist_ok=False)

    head_sha = _git_value(target, "rev-parse", "HEAD")
    _write_text(archive_dir / "status.txt", _run_git(target, "status", "--short", "--branch").stdout)
    _write_text(archive_dir / "staged.patch", _run_git(target, "diff", "--cached").stdout)
    _write_text(archive_dir / "unstaged.patch", _run_git(target, "diff").stdout)
    copied_untracked = _copy_untracked_files(target, archive_dir)
    _write_text(
        archive_dir / "untracked-files.txt",
        "\n".join(copied_untracked) + ("\n" if copied_untracked else ""),
    )
    _write_text(
        archive_dir / "RESTORE.md",
        "\n".join(
            [
                "# Worktree Archive Restore Notes",
                "",
                f"- Branch: `{info.branch}`",
                f"- Head SHA: `{head_sha}`",
                f"- Original path: `{target}`",
                "",
                "Suggested restore flow:",
                f"1. `git checkout -b {info.branch}-restore origin/main`",
                "2. Apply `staged.patch` then `unstaged.patch` if needed",
                "3. Copy files from `untracked/` back into the worktree",
            ]
        )
        + "\n",
    )
    meta = {
        "archive_version": "v1",
        "archived_at": datetime.now(timezone.utc).isoformat(),
        "repo_root": repo_root.as_posix(),
        "git_common_dir": common_git_dir.as_posix(),
        "target_path": target.as_posix(),
        "branch": info.branch,
        "head_sha": head_sha,
        "dirty_status": {
            "staged": dirty.staged,
            "unstaged": dirty.unstaged,
            "untracked": dirty.untracked,
        },
        "archive_dir": archive_dir.as_posix(),
    }
    _write_text(archive_dir / "archive-meta.json", json.dumps(meta, indent=2) + "\n")

    _run_git(repo_root, "worktree", "remove", "--force", target.as_posix())

    print("✓ Worktree archived and removed")
    print(f"Archive dir: {archive_dir}")
    print(f"Branch retained: {info.branch}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main(sys.argv))
    except subprocess.CalledProcessError as exc:
        message = exc.stderr.strip() or exc.output.strip() or str(exc)
        print(message, file=sys.stderr)
        raise SystemExit(exc.returncode)
