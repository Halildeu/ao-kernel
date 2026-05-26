"""AO-MA-4 parallel worktree runner.

Consumes an AO-MA-3 manifest + assignments and prepares one git worktree
per assignment under a declared write scope. Worker execution (LLM call,
code generation, ``worker_result.v1`` write) is NOT AO-MA-4's job; that
belongs to AO-MA-5/6/7 worker execution + reviewer + verifier.

Codex thread 019e666f iter-1 absorb invariants:

- Manifest SHA256 verification before any worktree creation
- Cross-reference verification: assignment.task_graph_id matches task graph
- Base sync verification: assignment.base_sha matches origin/main at runtime
- File ownership via ``verify_diff()``: actual_changed_files SUBSET of
  declared_write_set (not equality)
- Branch conflict fail-closed (no automatic -N suffix)
- Idempotent skip only when branch + worktree + HEAD all align
- Empty declared write set fail-closed (AO-MA-3 sentinel detection)
- No rebase: stale manifest fails closed; orchestrator must re-run
"""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from ao_kernel.orchestration.runner_report_writer import (
    RunnerReportWriter,
    RunnerReportWriterError,
    sha256_of,
)


class WorkerRunnerError(RuntimeError):
    """Raised when the runner cannot prepare worktrees fail-closed."""


@dataclass
class WorkerRunner:
    """Prepare git worktrees from an AO-MA-3 manifest."""

    repo_root: Path
    worktree_base: Path | None = None
    dry_run: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.repo_root, Path):
            raise WorkerRunnerError("repo_root must be a Path instance")
        self.repo_root = self.repo_root.resolve()
        if self.worktree_base is not None:
            self.worktree_base = self.worktree_base.resolve()

    def spawn(self, manifest_path: Path) -> dict[str, Any]:
        """Read manifest, verify integrity, prepare worktrees, emit report."""

        manifest_path = manifest_path.resolve()
        manifest = self._load_json(manifest_path)
        manifest_sha256 = sha256_of(manifest_path)
        base_dir = manifest_path.parent.parent

        task_graph_id = manifest["task_graph_id"]
        artifacts_by_path = {entry["path"]: entry for entry in manifest.get("artifacts", [])}
        task_graph_artifact = artifacts_by_path.get("task_graph.v1.json")
        if task_graph_artifact is None:
            raise WorkerRunnerError("manifest missing task_graph.v1.json entry")

        task_graph_path = manifest_path.parent / "task_graph.v1.json"
        self._verify_sha256(task_graph_path, task_graph_artifact["sha256"])
        task_graph = self._load_json(task_graph_path)

        runtime_origin_main = self._resolve_origin_main_sha()
        manifest_base_sha = task_graph["base_sha"]
        base_sync_check = "pass" if runtime_origin_main == manifest_base_sha else "failed_base_mismatch"

        assignments: list[tuple[Path, dict[str, Any], dict[str, Any]]] = []
        for entry_path, entry in artifacts_by_path.items():
            if not entry_path.startswith("agent_assignment-"):
                continue
            assignment_path = manifest_path.parent / entry_path
            self._verify_sha256(assignment_path, entry["sha256"])
            assignment = self._load_json(assignment_path)
            self._verify_cross_ref(assignment, task_graph_id, manifest_base_sha)
            assignments.append((assignment_path, entry, assignment))

        if not assignments:
            raise WorkerRunnerError("manifest has no agent_assignment-* entries")

        seen_paths: dict[str, str] = {}
        conflict_check = "pass"
        for _, _, assignment in assignments:
            for path in assignment.get("declared_write_set", []):
                owner = seen_paths.get(path)
                if owner is not None and owner != assignment["task_id"]:
                    conflict_check = "failed_overlap"
                seen_paths[path] = assignment["task_id"]

        workers_report: list[dict[str, Any]] = []
        for assignment_path, entry, assignment in assignments:
            workers_report.append(
                self._spawn_one(
                    assignment_path=assignment_path,
                    assignment_entry=entry,
                    assignment=assignment,
                    base_sync_check=base_sync_check,
                    conflict_check=conflict_check,
                )
            )

        writer = RunnerReportWriter(base_dir=base_dir)
        try:
            return writer.emit(
                task_graph_id=task_graph_id,
                manifest_sha256=manifest_sha256,
                base_sha=manifest_base_sha,
                conflict_check=conflict_check,
                base_sync_check=base_sync_check,
                workers=workers_report,
            )
        except RunnerReportWriterError as exc:
            raise WorkerRunnerError(f"runner report write failed: {exc}") from exc

    def verify_diff(
        self,
        *,
        worktree: Path,
        declared_write_set: list[str],
    ) -> dict[str, Any]:
        """Verify actual changed files subset of declared_write_set."""

        try:
            completed = subprocess.run(
                ["git", "-C", str(worktree), "diff", "--name-only", "HEAD"],
                check=True,
                capture_output=True,
                text=True,
                timeout=10,
            )
        except (subprocess.CalledProcessError, OSError, subprocess.TimeoutExpired) as exc:
            raise WorkerRunnerError(f"git diff failed in {worktree!s}: {exc}") from exc
        actual = [line.strip() for line in completed.stdout.splitlines() if line.strip()]
        declared = set(declared_write_set)
        extras = [f for f in actual if f not in declared]
        return {"ok": not extras, "actual": actual, "extras": extras}

    def cleanup(
        self,
        manifest_path: Path,
        *,
        delete_branches: bool = False,
    ) -> dict[str, Any]:
        """Remove prepared worktrees (clean only) and optionally branches."""

        manifest_path = manifest_path.resolve()
        manifest = self._load_json(manifest_path)
        task_graph_id = manifest["task_graph_id"]
        base_dir = manifest_path.parent.parent

        report_path = base_dir / task_graph_id / "runner_report.v1.json"
        if not report_path.exists():
            raise WorkerRunnerError(
                f"runner_report.v1.json missing under {base_dir / task_graph_id}; spawn before cleanup"
            )
        report = self._load_json(report_path)

        removed: list[str] = []
        kept_dirty: list[str] = []
        kept_branches: list[str] = []
        deleted_branches: list[str] = []
        for worker in report.get("workers", []):
            worktree = Path(worker["actual_worktree"]).resolve()
            if not worktree.exists():
                continue
            if self._worktree_is_dirty(worktree):
                kept_dirty.append(str(worktree))
                continue
            self._remove_worktree(worktree)
            removed.append(str(worktree))
            if delete_branches and self._branch_is_clean_and_merged(worker["branch"]):
                self._delete_branch(worker["branch"])
                deleted_branches.append(worker["branch"])
            else:
                kept_branches.append(worker["branch"])
        return {
            "removed_worktrees": removed,
            "kept_dirty": kept_dirty,
            "deleted_branches": deleted_branches,
            "kept_branches": kept_branches,
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _load_json(self, path: Path) -> dict[str, Any]:
        if not path.exists():
            raise WorkerRunnerError(f"file not found: {path!s}")
        try:
            return cast(dict[str, Any], json.loads(path.read_text(encoding="utf-8")))
        except (OSError, json.JSONDecodeError) as exc:
            raise WorkerRunnerError(f"failed to read {path!s}: {exc}") from exc

    def _verify_sha256(self, path: Path, expected: str) -> None:
        actual = sha256_of(path)
        if actual != expected:
            raise WorkerRunnerError(f"sha256 mismatch for {path!s}: expected {expected}, got {actual}")

    def _verify_cross_ref(
        self,
        assignment: dict[str, Any],
        task_graph_id: str,
        base_sha: str,
    ) -> None:
        if assignment.get("task_graph_id") != task_graph_id:
            raise WorkerRunnerError(
                f"assignment task_graph_id mismatch: {assignment.get('task_graph_id')!r} != {task_graph_id!r}"
            )
        if assignment.get("base_sha") != base_sha:
            raise WorkerRunnerError(f"assignment base_sha mismatch: {assignment.get('base_sha')!r} != {base_sha!r}")

    def _resolve_origin_main_sha(self) -> str:
        try:
            completed = subprocess.run(
                ["git", "-C", str(self.repo_root), "rev-parse", "origin/main"],
                check=True,
                capture_output=True,
                text=True,
                timeout=10,
            )
        except (subprocess.CalledProcessError, OSError, subprocess.TimeoutExpired) as exc:
            raise WorkerRunnerError(f"failed to resolve origin/main: {exc}") from exc
        return completed.stdout.strip()

    def _resolve_worktree_path(self, assignment: dict[str, Any]) -> tuple[Path, Path]:
        planned = Path(assignment["worktree"])
        if self.worktree_base is not None:
            actual = (self.worktree_base / assignment["task_id"]).resolve()
        else:
            actual = (self.repo_root / planned).resolve() if not planned.is_absolute() else planned.resolve()
        return planned, actual

    def _spawn_one(
        self,
        *,
        assignment_path: Path,
        assignment_entry: dict[str, Any],
        assignment: dict[str, Any],
        base_sync_check: str,
        conflict_check: str,
    ) -> dict[str, Any]:
        task_id = assignment["task_id"]
        branch = assignment["branch"]
        base_sha = assignment["base_sha"]
        declared = list(assignment.get("declared_write_set", []))
        planned_worktree, actual_worktree = self._resolve_worktree_path(assignment)
        expected_result = str(actual_worktree / "worker_result.v1.json")
        base_entry = {
            "assignment_ref": assignment_path.name,
            "assignment_sha256": assignment_entry["sha256"],
            "task_id": task_id,
            "branch": branch,
            "planned_worktree": str(planned_worktree),
            "actual_worktree": str(actual_worktree),
            "expected_worker_result_path": expected_result,
        }

        if base_sync_check != "pass":
            return {**base_entry, "status": "failed_base_mismatch", "reason": "base_sha mismatch"}
        if conflict_check != "pass":
            return {
                **base_entry,
                "status": "failed_base_mismatch",
                "reason": "manifest conflict_check failed; refuse spawn",
            }
        if not declared:
            return {
                **base_entry,
                "status": "failed_empty_write_set",
                "reason": "assignment declared_write_set is empty; AO-MA-3 sentinel requires explicit operator scope",
            }

        if self.dry_run:
            return {**base_entry, "status": "skipped_dry_run", "reason": "--dry-run requested"}

        if actual_worktree.exists() and (actual_worktree / ".git").exists():
            if self._worktree_branch_matches(actual_worktree, branch, base_sha):
                return {
                    **base_entry,
                    "status": "skipped_existing_idempotent",
                    "reason": "existing worktree matches branch + base_sha",
                }
            return {
                **base_entry,
                "status": "failed_worktree_exists_mismatch",
                "reason": "worktree exists with different branch or HEAD",
            }

        if self._branch_exists(branch):
            if not self._branch_head_matches(branch, base_sha):
                return {
                    **base_entry,
                    "status": "failed_branch_exists_mismatch",
                    "reason": "branch exists with different HEAD; refuse auto-suffix",
                }

        actual_worktree.parent.mkdir(parents=True, exist_ok=True)
        try:
            if self._branch_exists(branch):
                subprocess.run(
                    ["git", "-C", str(self.repo_root), "worktree", "add", str(actual_worktree), branch],
                    check=True,
                    capture_output=True,
                    text=True,
                    timeout=30,
                )
            else:
                subprocess.run(
                    [
                        "git",
                        "-C",
                        str(self.repo_root),
                        "worktree",
                        "add",
                        str(actual_worktree),
                        "-b",
                        branch,
                        base_sha,
                    ],
                    check=True,
                    capture_output=True,
                    text=True,
                    timeout=30,
                )
        except (subprocess.CalledProcessError, OSError, subprocess.TimeoutExpired) as exc:
            return {
                **base_entry,
                "status": "failed_worktree_exists_mismatch",
                "reason": f"git worktree add failed: {exc}",
            }

        return {**base_entry, "status": "prepared", "reason": "worktree + branch created"}

    def _branch_exists(self, branch: str) -> bool:
        completed = subprocess.run(
            ["git", "-C", str(self.repo_root), "rev-parse", "--verify", f"refs/heads/{branch}"],
            check=False,
            capture_output=True,
            text=True,
            timeout=10,
        )
        return completed.returncode == 0

    def _branch_head_matches(self, branch: str, expected_sha: str) -> bool:
        completed = subprocess.run(
            ["git", "-C", str(self.repo_root), "rev-parse", f"refs/heads/{branch}"],
            check=False,
            capture_output=True,
            text=True,
            timeout=10,
        )
        return completed.returncode == 0 and completed.stdout.strip() == expected_sha

    def _worktree_branch_matches(
        self,
        worktree: Path,
        branch: str,
        base_sha: str,
    ) -> bool:
        completed = subprocess.run(
            ["git", "-C", str(worktree), "rev-parse", "HEAD"],
            check=False,
            capture_output=True,
            text=True,
            timeout=10,
        )
        return completed.returncode == 0 and completed.stdout.strip() == base_sha

    def _worktree_is_dirty(self, worktree: Path) -> bool:
        completed = subprocess.run(
            ["git", "-C", str(worktree), "status", "--porcelain"],
            check=False,
            capture_output=True,
            text=True,
            timeout=10,
        )
        if completed.returncode != 0:
            return True
        return bool(completed.stdout.strip())

    def _remove_worktree(self, worktree: Path) -> None:
        subprocess.run(
            ["git", "-C", str(self.repo_root), "worktree", "remove", str(worktree)],
            check=False,
            capture_output=True,
            text=True,
            timeout=30,
        )

    def _branch_is_clean_and_merged(self, branch: str) -> bool:
        completed = subprocess.run(
            [
                "git",
                "-C",
                str(self.repo_root),
                "merge-base",
                "--is-ancestor",
                f"refs/heads/{branch}",
                "origin/main",
            ],
            check=False,
            capture_output=True,
            text=True,
            timeout=10,
        )
        return completed.returncode == 0

    def _delete_branch(self, branch: str) -> None:
        subprocess.run(
            ["git", "-C", str(self.repo_root), "branch", "-d", branch],
            check=False,
            capture_output=True,
            text=True,
            timeout=10,
        )
