#!/usr/bin/env python3
from __future__ import annotations

import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path, PurePosixPath


@dataclass(frozen=True)
class WorktreeInfo:
    path: Path
    branch: str


@dataclass(frozen=True)
class WorktreeSnapshot:
    path: Path
    branch: str
    base_label: str
    committed_paths: tuple[str, ...]
    staged_paths: tuple[str, ...]
    unstaged_paths: tuple[str, ...]
    untracked_paths: tuple[str, ...]
    changed_paths: tuple[str, ...]
    areas: tuple[str, ...]


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


def _git_lines(path: Path, *args: str) -> list[str]:
    proc = _run_git(path, *args)
    return [line for line in proc.stdout.splitlines() if line.strip()]


def _git_value(path: Path, *args: str) -> str:
    return _run_git(path, *args).stdout.strip()


def _ref_exists(path: Path, ref: str) -> bool:
    proc = _run_git(path, "rev-parse", "--verify", "--quiet", ref, check=False)
    return proc.returncode == 0


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
                        path=current_path,
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


def _resolve_base_label(path: Path) -> str:
    upstream = _run_git(
        path,
        "rev-parse",
        "--abbrev-ref",
        "--symbolic-full-name",
        "@{upstream}",
        check=False,
    )
    candidate_refs: list[str] = []
    if upstream.returncode == 0:
        candidate_refs.append(upstream.stdout.strip())
    candidate_refs.extend(["origin/main", "main"])

    for candidate in candidate_refs:
        if candidate and _ref_exists(path, candidate):
            return candidate
    return "(none)"


def _sorted_unique(paths: list[str]) -> tuple[str, ...]:
    return tuple(sorted({path for path in paths if path}))


def _path_area(path: str) -> str:
    parts = PurePosixPath(path).parts
    if not parts:
        return "(unknown)"
    return parts[0]


def _collect_snapshot(info: WorktreeInfo) -> WorktreeSnapshot:
    base_label = _resolve_base_label(info.path)
    committed_paths: list[str] = []

    if base_label != "(none)":
        merge_base = _run_git(
            info.path,
            "merge-base",
            "HEAD",
            base_label,
            check=False,
        )
        if merge_base.returncode == 0:
            committed_paths = _git_lines(
                info.path,
                "diff",
                "--name-only",
                f"{merge_base.stdout.strip()}..HEAD",
            )

    staged_paths = _git_lines(info.path, "diff", "--cached", "--name-only")
    unstaged_paths = _git_lines(info.path, "diff", "--name-only")
    untracked_paths = _git_lines(
        info.path,
        "ls-files",
        "--others",
        "--exclude-standard",
    )
    changed_paths = _sorted_unique(
        committed_paths + staged_paths + unstaged_paths + untracked_paths
    )
    areas = _sorted_unique([_path_area(path) for path in changed_paths])

    return WorktreeSnapshot(
        path=info.path,
        branch=info.branch,
        base_label=base_label,
        committed_paths=_sorted_unique(committed_paths),
        staged_paths=_sorted_unique(staged_paths),
        unstaged_paths=_sorted_unique(unstaged_paths),
        untracked_paths=_sorted_unique(untracked_paths),
        changed_paths=changed_paths,
        areas=areas,
    )


def _format_sample(items: tuple[str, ...], limit: int = 5) -> str:
    if not items:
        return "none"
    sample = ", ".join(items[:limit])
    if len(items) > limit:
        sample += ", ..."
    return sample


def _compute_exact_overlaps(
    snapshots: list[WorktreeSnapshot],
) -> list[tuple[str, list[str]]]:
    overlaps: dict[str, list[str]] = {}
    for snapshot in snapshots:
        for path in snapshot.changed_paths:
            overlaps.setdefault(path, []).append(snapshot.branch)
    return sorted(
        [
            (path, sorted(branches))
            for path, branches in overlaps.items()
            if len(branches) > 1
        ],
        key=lambda item: (len(item[1]) * -1, item[0]),
    )


def _compute_area_overlaps(
    snapshots: list[WorktreeSnapshot],
) -> list[tuple[str, list[str]]]:
    overlaps: dict[str, list[str]] = {}
    for snapshot in snapshots:
        for area in snapshot.areas:
            overlaps.setdefault(area, []).append(snapshot.branch)
    return sorted(
        [
            (area, sorted(branches))
            for area, branches in overlaps.items()
            if len(branches) > 1
        ],
        key=lambda item: (len(item[1]) * -1, item[0]),
    )


def main() -> int:
    repo_root = Path(_git_value(Path.cwd(), "rev-parse", "--show-toplevel"))
    snapshots = [
        _collect_snapshot(info)
        for info in sorted(_parse_worktrees(repo_root), key=lambda item: item.path.as_posix())
    ]

    exact_overlaps = _compute_exact_overlaps(snapshots)
    area_overlaps = _compute_area_overlaps(snapshots)

    print("== ops overlap-check ==")
    print(f"Repo: {repo_root}")
    print(f"Attached worktrees: {len(snapshots)}")
    print()
    print("Worktrees:")
    for snapshot in snapshots:
        print(f"  - {snapshot.path} [{snapshot.branch}]")
        print(f"    base: {snapshot.base_label}")
        print(
            "    change-set: "
            f"{len(snapshot.changed_paths)} path(s) "
            f"(committed={len(snapshot.committed_paths)}, "
            f"staged={len(snapshot.staged_paths)}, "
            f"unstaged={len(snapshot.unstaged_paths)}, "
            f"untracked={len(snapshot.untracked_paths)})"
        )
        print(f"    sample: {_format_sample(snapshot.changed_paths)}")
        print(f"    areas: {_format_sample(snapshot.areas)}")

    print()
    print("Exact file overlaps:")
    if exact_overlaps:
        for path, branches in exact_overlaps:
            print(f"  - {path}")
            print(f"    worktrees: {', '.join(branches)}")
    else:
        print("  - none")

    print()
    print("Shared top-level areas:")
    if area_overlaps:
        for area, branches in area_overlaps:
            print(f"  - {area}")
            print(f"    worktrees: {', '.join(branches)}")
    else:
        print("  - none")

    print()
    print("Summary:")
    if exact_overlaps or area_overlaps:
        print("⚠ Overlap risk detected")
        print(f"  - exact file overlaps: {len(exact_overlaps)}")
        print(f"  - shared top-level areas: {len(area_overlaps)}")
    else:
        print("✓ No overlapping changed paths detected")

    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except subprocess.CalledProcessError as exc:
        message = exc.stderr.strip() or exc.output.strip() or str(exc)
        print(message, file=sys.stderr)
        raise SystemExit(exc.returncode)
