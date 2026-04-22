#!/usr/bin/env python3
from __future__ import annotations

import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class WorktreeInfo:
    path: Path
    branch: str


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


def _count_lines(path: Path, *args: str) -> int:
    output = _run_git(path, *args).stdout.splitlines()
    return sum(1 for line in output if line.strip())


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


def _print_usage() -> None:
    print("Usage: bash .claude/scripts/ops.sh close-worktree <path>", file=sys.stderr)


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        _print_usage()
        return 2

    cwd = Path.cwd().resolve()
    repo_root = Path(_git_value(cwd, "rev-parse", "--show-toplevel")).resolve()
    target = Path(argv[1]).expanduser().resolve()
    worktrees = _parse_worktrees(repo_root)
    known_paths = {entry.path: entry for entry in worktrees}

    print("== ops close-worktree ==")
    print(f"Repo: {repo_root}")
    print(f"Requested target: {target}")

    if target == repo_root:
        print("Refusing to close current worktree")
        return 1

    if target not in known_paths:
        print("Target is not an attached worktree for this repository")
        return 1

    info = known_paths[target]
    staged = _count_lines(target, "diff", "--cached", "--name-only")
    unstaged = _count_lines(target, "diff", "--name-only")
    untracked = _count_lines(target, "ls-files", "--others", "--exclude-standard")

    print(f"Target branch: {info.branch}")
    print(
        "Target status: "
        f"staged={staged}, unstaged={unstaged}, untracked={untracked}"
    )

    if staged or unstaged or untracked:
        print("Refusing to close dirty worktree")
        print("Next step: commit/clean changes first; archive flow WP-6.4'te gelecek")
        return 1

    _run_git(repo_root, "worktree", "remove", target.as_posix())
    print("✓ Worktree closed")
    print(f"Closed path: {target}")
    print(f"Branch retained: {info.branch}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main(sys.argv))
    except subprocess.CalledProcessError as exc:
        message = exc.stderr.strip() or exc.output.strip() or str(exc)
        print(message, file=sys.stderr)
        raise SystemExit(exc.returncode)
