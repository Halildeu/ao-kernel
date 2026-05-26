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
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError

from ao_kernel.orchestration.runner_report_writer import (
    RunnerReportWriter,
    RunnerReportWriterError,
    sha256_of,
)


class WorkerRunnerError(RuntimeError):
    """Raised when the runner cannot prepare worktrees fail-closed."""


_SCHEMAS_DIR = Path(__file__).resolve().parent.parent / "defaults" / "schemas"

_TASK_GRAPH_SCHEMA_NAME = "ao-ma-task-graph.schema.v1.json"
_ASSIGNMENT_SCHEMA_NAME = "ao-ma-agent-assignment.schema.v1.json"
_RUNNER_REPORT_SCHEMA_NAME = "ao-ma-runner-report.schema.v1.json"


def _load_ao_ma_schema(name: str) -> dict[str, Any]:
    try:
        return cast(dict[str, Any], json.loads((_SCHEMAS_DIR / name).read_text(encoding="utf-8")))
    except (OSError, json.JSONDecodeError) as exc:
        raise WorkerRunnerError(f"failed to load bundled schema {name!r}: {exc}") from exc


def _validate_ao_ma_artifact(payload: dict[str, Any], schema_name: str, source: Path) -> None:
    """Codex iter-3 absorb: runtime schema validation against bundled AO-MA-2 schemas.

    A SHA256 match alone proves the bytes on disk equal what the orchestrator
    declared in the manifest. It does NOT prove the manifest itself was
    schema-conformant. Without runtime validation a stale or malformed
    artifact could pass through the runner and only surface mid-spawn as a
    cryptic KeyError. Fail-closed at the load boundary keeps the runner the
    trust gate AO-MA-2 designed it to be.
    """

    schema = _load_ao_ma_schema(schema_name)
    validator = Draft202012Validator(schema)
    try:
        validator.validate(payload)
    except ValidationError as exc:
        raise WorkerRunnerError(
            f"{source.name} failed schema {schema_name!r}: {exc.message} (at {list(exc.absolute_path)})"
        ) from exc


_TASK_GRAPH_ID_PATTERN = re.compile(r"^ao-ma-[0-9]{8}-[a-z0-9]{7}$")
_SHA256_PATTERN = re.compile(r"^sha256:[0-9a-f]{64}$")
_ARTIFACT_PATH_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*\.v1\.json$")
_EXPECTED_MANIFEST_SCHEMA_VERSION = "ao-ma-orchestration-manifest.v1"


def _validate_manifest_envelope(manifest: dict[str, Any], source: Path) -> None:
    """Codex iter-4 absorb: fail-closed manifest envelope validation.

    AO-MA-2 ships schemas for the inner artifacts (task_graph,
    agent_assignment, ...) but the orchestration manifest envelope
    itself is the runner's input contract. Without an envelope check
    a split-brain artifact set — e.g. manifest declares task_graph_id
    ``X`` while the on-disk task_graph.v1.json declares ``Y`` — passes
    SHA256 + inner-schema validation but still corrupts every
    downstream decision (worktree path, branch name, runner_report
    grouping). Fail-closed here keeps the runner the trust gate.

    Checks (all fail-closed):

    - ``schema_version == "ao-ma-orchestration-manifest.v1"``
    - ``task_graph_id`` is a string matching AO-MA-2 task-graph id pattern
    - ``artifacts`` is a non-empty array
    - exactly one artifact entry has path ``task_graph.v1.json``
    - every entry has ``path`` (no ``..``, no absolute, only ``*.v1.json``),
      ``sha256`` (sha256:[0-9a-f]{64}), ``size_bytes`` (positive int)
    - no duplicate ``path`` values across the artifact entries
    """

    if not isinstance(manifest, dict):
        raise WorkerRunnerError(f"{source.name} manifest must be a JSON object")

    schema_version = manifest.get("schema_version")
    if schema_version != _EXPECTED_MANIFEST_SCHEMA_VERSION:
        raise WorkerRunnerError(
            f"{source.name} schema_version mismatch: expected "
            f"{_EXPECTED_MANIFEST_SCHEMA_VERSION!r}, got {schema_version!r}"
        )

    task_graph_id = manifest.get("task_graph_id")
    if not isinstance(task_graph_id, str) or not _TASK_GRAPH_ID_PATTERN.match(task_graph_id):
        raise WorkerRunnerError(f"{source.name} task_graph_id {task_graph_id!r} does not match AO-MA-2 pattern")

    artifacts = manifest.get("artifacts")
    if not isinstance(artifacts, list) or not artifacts:
        raise WorkerRunnerError(f"{source.name} artifacts must be a non-empty array")

    seen_paths: set[str] = set()
    task_graph_entries = 0
    for index, entry in enumerate(artifacts):
        if not isinstance(entry, dict):
            raise WorkerRunnerError(f"{source.name} artifacts[{index}] must be a JSON object")
        path = entry.get("path")
        if not isinstance(path, str) or not path:
            raise WorkerRunnerError(f"{source.name} artifacts[{index}].path must be a non-empty string")
        # Reject traversal, absolute paths, or non-AO-MA artifact suffixes.
        if path.startswith("/") or ".." in Path(path).parts or "\\" in path:
            raise WorkerRunnerError(
                f"{source.name} artifacts[{index}].path {path!r} contains traversal/absolute components"
            )
        if not _ARTIFACT_PATH_PATTERN.match(path):
            raise WorkerRunnerError(
                f"{source.name} artifacts[{index}].path {path!r} does not match AO-MA artifact suffix '*.v1.json'"
            )
        if path in seen_paths:
            raise WorkerRunnerError(f"{source.name} duplicate artifact path: {path!r}")
        seen_paths.add(path)
        if path == "task_graph.v1.json":
            task_graph_entries += 1

        sha = entry.get("sha256")
        if not isinstance(sha, str) or not _SHA256_PATTERN.match(sha):
            raise WorkerRunnerError(
                f"{source.name} artifacts[{index}].sha256 {sha!r} must match 'sha256:[0-9a-f]{{64}}'"
            )
        size_bytes = entry.get("size_bytes")
        if not isinstance(size_bytes, int) or isinstance(size_bytes, bool) or size_bytes <= 0:
            raise WorkerRunnerError(
                f"{source.name} artifacts[{index}].size_bytes {size_bytes!r} must be a positive integer"
            )

    if task_graph_entries != 1:
        raise WorkerRunnerError(
            f"{source.name} must declare exactly one task_graph.v1.json artifact entry (got {task_graph_entries})"
        )


def _path_is_under(child: Path, parent: Path) -> bool:
    """Return True when ``child`` is the same as or under ``parent``."""

    try:
        child.relative_to(parent)
        return True
    except ValueError:
        return False


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
        # Codex iter-4 absorb: envelope validation BEFORE we trust any
        # downstream field. Catches split-brain artifact sets, traversal
        # in entry paths, malformed sha256/size_bytes, duplicate entries.
        _validate_manifest_envelope(manifest, manifest_path)
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
        _validate_ao_ma_artifact(task_graph, _TASK_GRAPH_SCHEMA_NAME, task_graph_path)

        # Codex iter-4 absorb: manifest task_graph_id MUST equal the
        # task_graph.v1.json task_graph_id. SHA256 + inner-schema
        # validation pass even when the two declare different ids,
        # which would silently corrupt the runner_report output dir
        # and worktree path namespace.
        inner_task_graph_id = task_graph.get("task_graph_id")
        if inner_task_graph_id != task_graph_id:
            raise WorkerRunnerError(
                f"manifest task_graph_id {task_graph_id!r} != task_graph.v1.json task_graph_id {inner_task_graph_id!r}"
            )

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
            _validate_ao_ma_artifact(assignment, _ASSIGNMENT_SCHEMA_NAME, assignment_path)
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
        base_sha: str | None = None,
    ) -> dict[str, Any]:
        """Verify actual changed files ⊆ declared_write_set (subset).

        Codex iter-2 absorb: the actual changed set is the UNION of:

        - committed changes since ``base_sha`` (``git diff --name-only base_sha..HEAD``)
        - staged changes (``git diff --name-only --staged``)
        - unstaged changes (``git diff --name-only``)
        - untracked files (``git ls-files --others --exclude-standard``)

        ``HEAD``-only diff missed (a) untracked files and (b) committed
        worker changes relative to the orchestrator-supplied base. The union
        captures every place a worker might write while still preserving the
        subset (rather than equality) semantic.
        """

        actual_set: set[str] = set()
        actual_set.update(self._git_lines(worktree, ["diff", "--name-only"]))
        actual_set.update(self._git_lines(worktree, ["diff", "--name-only", "--staged"]))
        actual_set.update(self._git_lines(worktree, ["ls-files", "--others", "--exclude-standard"]))
        if base_sha:
            actual_set.update(self._git_lines(worktree, ["diff", "--name-only", f"{base_sha}..HEAD"]))
        actual = sorted(actual_set)
        declared = set(declared_write_set)
        extras = [f for f in actual if f not in declared]
        return {"ok": not extras, "actual": actual, "extras": extras}

    def _git_lines(self, worktree: Path, args: list[str]) -> list[str]:
        """Run ``git -C worktree <args>`` and return non-empty stdout lines.

        Codex iter-3 absorb: non-zero exit codes are NOT silently swallowed.
        A bad base_sha, missing ref, or broken git invocation would otherwise
        cause verify_diff to return ``ok=True`` with empty extras, hiding
        committed out-of-scope work. The runner is the trust boundary; git
        failures are fail-closed surface errors.
        """

        try:
            completed = subprocess.run(
                ["git", "-C", str(worktree), *args],
                check=False,
                capture_output=True,
                text=True,
                timeout=10,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise WorkerRunnerError(f"git {args!r} failed in {worktree!s}: {exc}") from exc
        if completed.returncode != 0:
            raise WorkerRunnerError(
                f"git {args!r} in {worktree!s} exited {completed.returncode}: "
                f"{completed.stderr.strip() or completed.stdout.strip()}"
            )
        return [line.strip() for line in completed.stdout.splitlines() if line.strip()]

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
        # Codex iter-4 absorb nice-to-have: cleanup also re-validates the
        # report against the bundled schema. The writer already validates
        # on emit, but the on-disk file is a trust boundary: an operator
        # or rogue process could mutate it between spawn and cleanup. A
        # schema-invalid report would mean we operate on undefined worker
        # entries; fail-closed here keeps the runner the trust gate.
        _validate_ao_ma_artifact(report, _RUNNER_REPORT_SCHEMA_NAME, report_path)

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
                # Codex iter-4 absorb: honor _delete_branch return; record
                # in kept_branches when git refused the delete.
                if self._delete_branch(worker["branch"]):
                    deleted_branches.append(worker["branch"])
                else:
                    kept_branches.append(worker["branch"])
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
        """Resolve planned + actual worktree paths with containment fail-closed.

        Codex iter-2 absorb: ``actual`` must stay under either ``worktree_base``
        (when override is in effect) or under ``repo_root`` (default). Path
        traversal or symlink escape via ``..`` / absolute paths is rejected
        so the runner cannot accidentally provision outside its allowed root.
        """

        import re as _re

        planned = Path(assignment["worktree"])
        task_id = assignment["task_id"]
        if not _re.match(r"^[a-z0-9][a-z0-9._-]{1,80}$", task_id):
            raise WorkerRunnerError(f"task_id {task_id!r} does not match AO-MA-2 id pattern; refuse path build")
        if self.worktree_base is not None:
            resolved_base = self.worktree_base.resolve()
            actual = (resolved_base / task_id).resolve()
            if not _path_is_under(actual, resolved_base):
                raise WorkerRunnerError(f"task_id {task_id!r} escapes worktree_base {resolved_base!s}")
        else:
            resolved_repo = self.repo_root.resolve()
            if planned.is_absolute():
                actual = planned.resolve()
            else:
                actual = (resolved_repo / planned).resolve()
            if not _path_is_under(actual, resolved_repo):
                raise WorkerRunnerError(f"planned worktree {planned!s} escapes repo_root {resolved_repo!s}")
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
            # Codex iter-4 absorb: report failed_overlap (honest signal),
            # not failed_base_mismatch — top-level conflict_check is
            # failed_overlap so the worker label must agree.
            return {
                **base_entry,
                "status": "failed_overlap",
                "reason": "manifest conflict_check failed_overlap; refuse spawn",
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

        # Codex iter-4 absorb: post-add TOCTOU verify. After git reports
        # success the runner must still confirm the new worktree is on
        # the EXPECTED branch at the EXPECTED commit. Concurrent spawn,
        # ref tampering, or symlink swap between the pre-check and the
        # post-add can land us on something else; fail-closed here so
        # AO-MA-5/6/7 never operate on a mismatched worktree.
        if not self._worktree_branch_matches(actual_worktree, branch, base_sha):
            return {
                **base_entry,
                "status": "failed_post_add_verify",
                "reason": "worktree post-add branch+HEAD verify failed; possible TOCTOU or ref tampering",
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
        """Codex iter-4 absorb: idempotent skip MUST verify branch identity AND HEAD.

        Previously only `HEAD == base_sha` was checked, so an existing
        worktree attached to the WRONG branch but at the SAME commit
        would silently pass as ``skipped_existing_idempotent``. The
        runner is the trust gate; a wrong-branch worktree must be
        reported as ``failed_worktree_exists_mismatch``, not skipped.
        """

        head_completed = subprocess.run(
            ["git", "-C", str(worktree), "rev-parse", "HEAD"],
            check=False,
            capture_output=True,
            text=True,
            timeout=10,
        )
        if head_completed.returncode != 0 or head_completed.stdout.strip() != base_sha:
            return False
        branch_completed = subprocess.run(
            ["git", "-C", str(worktree), "symbolic-ref", "--short", "HEAD"],
            check=False,
            capture_output=True,
            text=True,
            timeout=10,
        )
        if branch_completed.returncode != 0:
            # Detached HEAD: not on a branch at all, never idempotent.
            return False
        return branch_completed.stdout.strip() == branch

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
        """Codex iter-3 absorb: fail-closed when git worktree remove fails."""

        completed = subprocess.run(
            ["git", "-C", str(self.repo_root), "worktree", "remove", str(worktree)],
            check=False,
            capture_output=True,
            text=True,
            timeout=30,
        )
        if completed.returncode != 0:
            raise WorkerRunnerError(
                f"git worktree remove {worktree!s} exited {completed.returncode}: "
                f"{completed.stderr.strip() or completed.stdout.strip()}"
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

    def _delete_branch(self, branch: str) -> bool:
        """Codex iter-4 absorb: return True only if `git branch -d` succeeded.

        Previously the exit code was ignored and the caller would always
        record the branch in ``deleted_branches`` even when git refused
        the delete (e.g., unmerged commits, branch in use). Now the
        caller can put the branch in ``kept_branches`` on soft failure.
        """

        completed = subprocess.run(
            ["git", "-C", str(self.repo_root), "branch", "-d", branch],
            check=False,
            capture_output=True,
            text=True,
            timeout=10,
        )
        return completed.returncode == 0
