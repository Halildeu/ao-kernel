"""AO-MA-4 worker_runner end-to-end tests with real git worktrees."""

from __future__ import annotations

import hashlib
import json
import subprocess
from collections.abc import Iterator
from pathlib import Path

import pytest

from ao_kernel.orchestration.worker_runner import (
    WorkerRunner,
    WorkerRunnerError,
    _path_is_under,
)


def _run(cmd: list[str], cwd: Path | None = None) -> str:
    completed = subprocess.run(cmd, cwd=cwd, check=True, capture_output=True, text=True, timeout=20)
    return completed.stdout.strip()


def _git_init_repo(repo: Path) -> str:
    """Init a fresh git repo with one initial commit; return commit SHA."""

    _run(["git", "init", "--initial-branch=main", str(repo)])
    _run(["git", "-C", str(repo), "config", "user.email", "test@example.com"])
    _run(["git", "-C", str(repo), "config", "user.name", "test"])
    (repo / "README.md").write_text("initial\n", encoding="utf-8")
    _run(["git", "-C", str(repo), "add", "README.md"])
    _run(["git", "-C", str(repo), "commit", "-m", "initial"])
    sha = _run(["git", "-C", str(repo), "rev-parse", "HEAD"])
    # Synthesize an origin/main ref so the runner can resolve it without
    # actually pushing to a remote.
    _run(
        [
            "git",
            "-C",
            str(repo),
            "update-ref",
            "refs/remotes/origin/main",
            sha,
        ]
    )
    return sha


def _sha256(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _write_manifest(
    *,
    base_dir: Path,
    task_graph_id: str,
    base_sha: str,
    workers: list[dict],
) -> Path:
    """Build a minimal AO-MA-3-compatible artifact set + return manifest path."""

    out_dir = base_dir / task_graph_id
    out_dir.mkdir(parents=True, exist_ok=True)

    task_graph = {
        "schema_version": "ao-ma-task-graph.v1",
        "task_graph_id": task_graph_id,
        "repo": "Halildeu/ao-kernel",
        "goal": "AO-MA-4 e2e fixture",
        "base_ref": "refs/heads/main",
        "base_sha": base_sha,
        "risk_class": "low",
        "max_parallel_workers": len(workers),
        "tasks": [
            {
                "task_id": w["task_id"],
                "title": f"task {w['task_id']}",
                "agent_type": "implementer",
                "declared_write_set": w["declared_write_set"],
                "dependency_ids": [],
                "acceptance_criteria": ["tests_pass_locally"],
                "high_risk": False,
            }
            for w in workers
        ],
        "fan_in_policy": {
            "mode": "all_required",
            "required_task_ids": [w["task_id"] for w in workers],
            "conflict_owner": "integrator",
        },
        "review_policy": {
            "required_reviewers": 1,
            "cross_provider_required": True,
            "consensus_required_for_high_risk": True,
            "max_revise_rounds": 3,
        },
        "guard_flags": {
            "support_widening": False,
            "production_platform_claim": False,
            "live_adapter_execution": False,
        },
    }
    task_graph_path = out_dir / "task_graph.v1.json"
    task_graph_path.write_text(json.dumps(task_graph, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    artifacts = [
        {
            "path": "task_graph.v1.json",
            "sha256": _sha256(task_graph_path),
            "size_bytes": task_graph_path.stat().st_size,
        }
    ]
    for w in workers:
        assignment = {
            "schema_version": "ao-ma-agent-assignment.v1",
            "assignment_id": f"{task_graph_id}-{w['task_id']}",
            "task_graph_id": task_graph_id,
            "task_id": w["task_id"],
            "agent": {
                "agent_id": f"claude-{w['task_id']}",
                "agent_type": "implementer",
                "provider": "anthropic",
                "session_id": f"ao-ma-4-test-{task_graph_id}",
            },
            "base_ref": "refs/heads/main",
            "base_sha": base_sha,
            "branch": f"codex/ao-ma-{task_graph_id}/{w['task_id']}",
            "worktree": f".ao/orchestration/{task_graph_id}/workers/{w['task_id']}",
            "declared_write_set": w["declared_write_set"],
            "expected_output_artifact": "worker_result.v1",
            "status": "pending",
            "guard_flags": {
                "support_widening": False,
                "production_platform_claim": False,
                "live_adapter_execution": False,
            },
        }
        assignment_path = out_dir / f"agent_assignment-{w['task_id']}.v1.json"
        assignment_path.write_text(json.dumps(assignment, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        artifacts.append(
            {
                "path": f"agent_assignment-{w['task_id']}.v1.json",
                "sha256": _sha256(assignment_path),
                "size_bytes": assignment_path.stat().st_size,
            }
        )

    manifest = {
        "schema_version": "ao-ma-orchestration-manifest.v1",
        "task_graph_id": task_graph_id,
        "generated_at": "2026-05-27T00:00:00Z",
        "base_dir": str(out_dir),
        "artifacts": artifacts,
        "guard_flags": {
            "support_widening": False,
            "production_platform_claim": False,
            "live_adapter_execution": False,
        },
    }
    manifest_path = out_dir / "manifest.v1.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return manifest_path


@pytest.fixture
def fixture_repo(tmp_path: Path) -> Iterator[tuple[Path, str]]:
    repo = tmp_path / "repo"
    sha = _git_init_repo(repo)
    yield repo, sha


def test_spawn_two_workers_prepares_worktrees(fixture_repo: tuple[Path, str], tmp_path: Path) -> None:
    repo, base_sha = fixture_repo
    base_dir = repo / ".ao" / "orchestration"
    manifest_path = _write_manifest(
        base_dir=base_dir,
        task_graph_id="ao-ma-20260527-aaa1111",
        base_sha=base_sha,
        workers=[
            {"task_id": "task-001", "declared_write_set": ["src/a.py"]},
            {"task_id": "task-002", "declared_write_set": ["src/b.py"]},
        ],
    )
    runner = WorkerRunner(repo_root=repo)
    report = runner.spawn(manifest_path=manifest_path)
    assert report["base_sync_check"] == "pass"
    assert report["conflict_check"] == "pass"
    statuses = [w["status"] for w in report["workers"]]
    assert statuses == ["prepared", "prepared"]


def test_spawn_empty_write_set_fails_closed(fixture_repo: tuple[Path, str], tmp_path: Path) -> None:
    repo, base_sha = fixture_repo
    base_dir = repo / ".ao" / "orchestration"
    manifest_path = _write_manifest(
        base_dir=base_dir,
        task_graph_id="ao-ma-20260527-bbb2222",
        base_sha=base_sha,
        workers=[{"task_id": "task-001", "declared_write_set": []}],
    )
    runner = WorkerRunner(repo_root=repo)
    report = runner.spawn(manifest_path=manifest_path)
    assert report["workers"][0]["status"] == "failed_empty_write_set"


def test_spawn_dry_run_no_worktree_created(fixture_repo: tuple[Path, str], tmp_path: Path) -> None:
    repo, base_sha = fixture_repo
    base_dir = repo / ".ao" / "orchestration"
    manifest_path = _write_manifest(
        base_dir=base_dir,
        task_graph_id="ao-ma-20260527-ccc3333",
        base_sha=base_sha,
        workers=[{"task_id": "task-001", "declared_write_set": ["src/x.py"]}],
    )
    runner = WorkerRunner(repo_root=repo, dry_run=True)
    report = runner.spawn(manifest_path=manifest_path)
    assert report["workers"][0]["status"] == "skipped_dry_run"
    # No worktree on disk
    expected_worktree = repo / ".ao/orchestration/ao-ma-20260527-ccc3333/workers/task-001"
    assert not expected_worktree.exists()


def test_spawn_base_sync_mismatch_fails(fixture_repo: tuple[Path, str], tmp_path: Path) -> None:
    repo, _real_sha = fixture_repo
    fake_sha = "f" * 40
    base_dir = repo / ".ao" / "orchestration"
    manifest_path = _write_manifest(
        base_dir=base_dir,
        task_graph_id="ao-ma-20260527-ddd4444",
        base_sha=fake_sha,
        workers=[{"task_id": "task-001", "declared_write_set": ["src/y.py"]}],
    )
    runner = WorkerRunner(repo_root=repo)
    report = runner.spawn(manifest_path=manifest_path)
    assert report["base_sync_check"] == "failed_base_mismatch"
    assert report["workers"][0]["status"] == "failed_base_mismatch"


def test_spawn_manifest_sha_mismatch_fails(fixture_repo: tuple[Path, str], tmp_path: Path) -> None:
    repo, base_sha = fixture_repo
    base_dir = repo / ".ao" / "orchestration"
    manifest_path = _write_manifest(
        base_dir=base_dir,
        task_graph_id="ao-ma-20260527-eee5555",
        base_sha=base_sha,
        workers=[{"task_id": "task-001", "declared_write_set": ["src/z.py"]}],
    )
    # Tamper with the task_graph.v1.json on disk after manifest hash was computed
    task_graph_path = base_dir / "ao-ma-20260527-eee5555" / "task_graph.v1.json"
    data = json.loads(task_graph_path.read_text(encoding="utf-8"))
    data["goal"] = "tampered after manifest"
    task_graph_path.write_text(json.dumps(data) + "\n", encoding="utf-8")
    runner = WorkerRunner(repo_root=repo)
    with pytest.raises(WorkerRunnerError, match="sha256 mismatch"):
        runner.spawn(manifest_path=manifest_path)


def test_verify_diff_subset_pass(fixture_repo: tuple[Path, str]) -> None:
    repo, _ = fixture_repo
    # Repo HEAD diff is empty initially; declared can be anything (subset trivially)
    runner = WorkerRunner(repo_root=repo)
    result = runner.verify_diff(worktree=repo, declared_write_set=["src/x.py"])
    assert result["ok"] is True
    assert result["actual"] == []


def test_verify_diff_extras_fail(fixture_repo: tuple[Path, str]) -> None:
    repo, _ = fixture_repo
    (repo / "untracked_outside_scope.py").write_text("# stray\n", encoding="utf-8")
    runner = WorkerRunner(repo_root=repo)
    result = runner.verify_diff(worktree=repo, declared_write_set=["src/x.py"])
    assert result["ok"] is False
    assert "untracked_outside_scope.py" in result["extras"]


def test_verify_diff_committed_since_base_catches_extras(
    fixture_repo: tuple[Path, str],
) -> None:
    """Codex iter-3 absorb: the base_sha..HEAD diff branch must catch
    committed out-of-scope work, not just unstaged/untracked changes.

    Reproduction: spawn a worktree at base_sha, commit a file that is
    NOT in declared_write_set, then call verify_diff(base_sha=base_sha).
    Without the base_sha..HEAD branch the runner would see a clean
    `git status` and return ok=True, hiding committed extras. With it,
    the committed file shows up in extras + ok=False.
    """

    repo, base_sha = fixture_repo
    base_dir = repo / ".ao" / "orchestration"
    manifest_path = _write_manifest(
        base_dir=base_dir,
        task_graph_id="ao-ma-20260527-cmt8888",
        base_sha=base_sha,
        workers=[{"task_id": "task-001", "declared_write_set": ["src/x.py"]}],
    )
    runner = WorkerRunner(repo_root=repo)
    runner.spawn(manifest_path=manifest_path)
    worktree = repo / ".ao/orchestration/ao-ma-20260527-cmt8888/workers/task-001"

    # Commit a file that is NOT in declared_write_set
    stray = worktree / "OUTSIDE_SCOPE.md"
    stray.write_text("# committed but out of scope\n", encoding="utf-8")
    _run(["git", "-C", str(worktree), "add", "OUTSIDE_SCOPE.md"])
    _run(["git", "-C", str(worktree), "commit", "-m", "stray commit"])

    # status is clean, but base_sha..HEAD must still expose the extra
    result = runner.verify_diff(
        worktree=worktree,
        declared_write_set=["src/x.py"],
        base_sha=base_sha,
    )
    assert result["ok"] is False, result
    assert "OUTSIDE_SCOPE.md" in result["extras"], result


def test_resolve_worktree_path_rejects_traversal(tmp_path: Path) -> None:
    runner = WorkerRunner(repo_root=tmp_path)
    with pytest.raises(WorkerRunnerError, match="escapes"):
        runner._resolve_worktree_path({"task_id": "task-001", "worktree": "../../etc/passwd"})


def test_resolve_worktree_path_rejects_bad_task_id(tmp_path: Path) -> None:
    runner = WorkerRunner(repo_root=tmp_path)
    with pytest.raises(WorkerRunnerError, match="AO-MA-2 id pattern"):
        runner._resolve_worktree_path({"task_id": "Bad/Task!", "worktree": ".ao/orchestration/x/workers/x"})


def test_resolve_worktree_path_under_repo_ok(tmp_path: Path) -> None:
    runner = WorkerRunner(repo_root=tmp_path)
    planned, actual = runner._resolve_worktree_path(
        {"task_id": "task-001", "worktree": ".ao/orchestration/foo/workers/task-001"}
    )
    assert actual.is_relative_to(tmp_path.resolve())


def test_resolve_worktree_path_with_worktree_base_override(tmp_path: Path) -> None:
    base = tmp_path / "external"
    base.mkdir()
    runner = WorkerRunner(repo_root=tmp_path / "repo", worktree_base=base)
    (tmp_path / "repo").mkdir()
    planned, actual = runner._resolve_worktree_path(
        {"task_id": "task-001", "worktree": ".ao/orchestration/foo/workers/task-001"}
    )
    assert actual.is_relative_to(base.resolve())


def test_path_is_under_helper() -> None:
    assert _path_is_under(Path("/tmp/foo/bar"), Path("/tmp/foo")) is True
    assert _path_is_under(Path("/tmp/foo"), Path("/tmp/foo")) is True
    assert _path_is_under(Path("/tmp/bar"), Path("/tmp/foo")) is False


def test_cleanup_refuses_dirty_worktree(fixture_repo: tuple[Path, str], tmp_path: Path) -> None:
    repo, base_sha = fixture_repo
    base_dir = repo / ".ao" / "orchestration"
    manifest_path = _write_manifest(
        base_dir=base_dir,
        task_graph_id="ao-ma-20260527-fff6666",
        base_sha=base_sha,
        workers=[{"task_id": "task-001", "declared_write_set": ["src/x.py"]}],
    )
    runner = WorkerRunner(repo_root=repo)
    runner.spawn(manifest_path=manifest_path)
    # Dirty the worktree
    worktree = repo / ".ao/orchestration/ao-ma-20260527-fff6666/workers/task-001"
    (worktree / "src").mkdir(parents=True, exist_ok=True)
    (worktree / "src" / "x.py").write_text("# work\n", encoding="utf-8")
    result = runner.cleanup(manifest_path=manifest_path)
    assert worktree.exists()
    assert str(worktree.resolve()) in result["kept_dirty"]


def test_cleanup_clean_worktree_removed(fixture_repo: tuple[Path, str], tmp_path: Path) -> None:
    repo, base_sha = fixture_repo
    base_dir = repo / ".ao" / "orchestration"
    manifest_path = _write_manifest(
        base_dir=base_dir,
        task_graph_id="ao-ma-20260527-aaa7777",
        base_sha=base_sha,
        workers=[{"task_id": "task-001", "declared_write_set": ["src/x.py"]}],
    )
    runner = WorkerRunner(repo_root=repo)
    runner.spawn(manifest_path=manifest_path)
    result = runner.cleanup(manifest_path=manifest_path)
    worktree = repo / ".ao/orchestration/ao-ma-20260527-aaa7777/workers/task-001"
    assert not worktree.exists()
    assert any(str(worktree.resolve()) == w for w in result["removed_worktrees"])


# ---------------------------------------------------------------------------
# Codex iter-4 absorb tests
# ---------------------------------------------------------------------------


def test_spawn_manifest_task_graph_id_split_brain_fails(
    fixture_repo: tuple[Path, str],
    tmp_path: Path,
) -> None:
    """Codex iter-4 HIGH-1: manifest task_graph_id != task_graph.v1.json task_graph_id

    Both artifacts pass their own SHA256 + schema validation; without
    the iter-4 envelope + cross-ref check the runner would silently
    fork the worktree namespace.
    """

    repo, base_sha = fixture_repo
    base_dir = repo / ".ao" / "orchestration"
    manifest_path = _write_manifest(
        base_dir=base_dir,
        task_graph_id="ao-ma-20260527-split11",
        base_sha=base_sha,
        workers=[{"task_id": "task-001", "declared_write_set": ["src/x.py"]}],
    )
    # Mutate ONLY the inner task_graph.v1.json task_graph_id and refresh
    # its sha256 in the manifest so the SHA256 verifier doesn't reject
    # this earlier — we want to land specifically on the cross-ref check.
    task_graph_path = base_dir / "ao-ma-20260527-split11" / "task_graph.v1.json"
    tg = json.loads(task_graph_path.read_text(encoding="utf-8"))
    tg["task_graph_id"] = "ao-ma-20260527-other22"
    task_graph_path.write_text(json.dumps(tg, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    for entry in manifest["artifacts"]:
        if entry["path"] == "task_graph.v1.json":
            entry["sha256"] = _sha256(task_graph_path)
            entry["size_bytes"] = task_graph_path.stat().st_size
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    runner = WorkerRunner(repo_root=repo)
    with pytest.raises(WorkerRunnerError, match="task_graph_id"):
        runner.spawn(manifest_path=manifest_path)


def test_spawn_manifest_envelope_rejects_bad_schema_version(
    fixture_repo: tuple[Path, str],
) -> None:
    """Manifest with wrong schema_version is fail-closed at envelope check."""

    repo, base_sha = fixture_repo
    base_dir = repo / ".ao" / "orchestration"
    manifest_path = _write_manifest(
        base_dir=base_dir,
        task_graph_id="ao-ma-20260527-env1111",
        base_sha=base_sha,
        workers=[{"task_id": "task-001", "declared_write_set": ["src/x.py"]}],
    )
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["schema_version"] = "ao-ma-orchestration-manifest.v999"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    runner = WorkerRunner(repo_root=repo)
    with pytest.raises(WorkerRunnerError, match="schema_version"):
        runner.spawn(manifest_path=manifest_path)


def test_spawn_manifest_envelope_rejects_traversal_in_artifact_path(
    fixture_repo: tuple[Path, str],
) -> None:
    """Manifest with `..` in artifact path is fail-closed at envelope check."""

    repo, base_sha = fixture_repo
    base_dir = repo / ".ao" / "orchestration"
    manifest_path = _write_manifest(
        base_dir=base_dir,
        task_graph_id="ao-ma-20260527-trav111",
        base_sha=base_sha,
        workers=[{"task_id": "task-001", "declared_write_set": ["src/x.py"]}],
    )
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    # Inject a bogus entry whose path contains traversal
    manifest["artifacts"].append({"path": "../escape.v1.json", "sha256": "sha256:" + "0" * 64, "size_bytes": 10})
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    runner = WorkerRunner(repo_root=repo)
    with pytest.raises(WorkerRunnerError, match="traversal/absolute"):
        runner.spawn(manifest_path=manifest_path)


def test_spawn_manifest_envelope_rejects_duplicate_artifact_path(
    fixture_repo: tuple[Path, str],
) -> None:
    """Duplicate artifact path entries are fail-closed."""

    repo, base_sha = fixture_repo
    base_dir = repo / ".ao" / "orchestration"
    manifest_path = _write_manifest(
        base_dir=base_dir,
        task_graph_id="ao-ma-20260527-dup1111",
        base_sha=base_sha,
        workers=[{"task_id": "task-001", "declared_write_set": ["src/x.py"]}],
    )
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    # Duplicate the task_graph entry
    manifest["artifacts"].append(dict(manifest["artifacts"][0]))
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    runner = WorkerRunner(repo_root=repo)
    with pytest.raises(WorkerRunnerError, match="duplicate artifact path"):
        runner.spawn(manifest_path=manifest_path)


def test_spawn_manifest_envelope_rejects_malformed_sha256(
    fixture_repo: tuple[Path, str],
) -> None:
    """Artifact entry with non-sha256-format sha is fail-closed."""

    repo, base_sha = fixture_repo
    base_dir = repo / ".ao" / "orchestration"
    manifest_path = _write_manifest(
        base_dir=base_dir,
        task_graph_id="ao-ma-20260527-sha1111",
        base_sha=base_sha,
        workers=[{"task_id": "task-001", "declared_write_set": ["src/x.py"]}],
    )
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["artifacts"][0]["sha256"] = "not-a-sha"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    runner = WorkerRunner(repo_root=repo)
    with pytest.raises(WorkerRunnerError, match="sha256:"):
        runner.spawn(manifest_path=manifest_path)


def test_spawn_inner_schema_rejects_assignment_with_invalid_enum(
    fixture_repo: tuple[Path, str],
) -> None:
    """Inner-schema validation (Codex iter-3) catches assignment status enum violation."""

    repo, base_sha = fixture_repo
    base_dir = repo / ".ao" / "orchestration"
    manifest_path = _write_manifest(
        base_dir=base_dir,
        task_graph_id="ao-ma-20260527-enum111",
        base_sha=base_sha,
        workers=[{"task_id": "task-001", "declared_write_set": ["src/x.py"]}],
    )
    # Tamper the assignment file to use an out-of-enum status, then
    # refresh its sha256 in the manifest so we land on the schema check
    # rather than SHA256.
    assignment_path = base_dir / "ao-ma-20260527-enum111" / "agent_assignment-task-001.v1.json"
    payload = json.loads(assignment_path.read_text(encoding="utf-8"))
    payload["status"] = "totally_invalid_status"
    assignment_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    for entry in manifest["artifacts"]:
        if entry["path"] == "agent_assignment-task-001.v1.json":
            entry["sha256"] = _sha256(assignment_path)
            entry["size_bytes"] = assignment_path.stat().st_size
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    runner = WorkerRunner(repo_root=repo)
    with pytest.raises(WorkerRunnerError, match="failed schema"):
        runner.spawn(manifest_path=manifest_path)


def test_spawn_idempotent_skip_only_when_branch_AND_head_match(
    fixture_repo: tuple[Path, str],
) -> None:
    """Codex iter-4 HIGH-2: same-SHA wrong-branch is NOT idempotent.

    Pre iter-4 absorb the helper only checked HEAD; same SHA on a
    different branch would silently pass as ``skipped_existing_idempotent``.
    Now the runner inspects both ``git symbolic-ref --short HEAD`` AND
    ``rev-parse HEAD``; a wrong-branch existing worktree is reported as
    ``failed_worktree_exists_mismatch``.
    """

    repo, base_sha = fixture_repo
    base_dir = repo / ".ao" / "orchestration"
    manifest_path = _write_manifest(
        base_dir=base_dir,
        task_graph_id="ao-ma-20260527-idem111",
        base_sha=base_sha,
        workers=[{"task_id": "task-001", "declared_write_set": ["src/x.py"]}],
    )
    runner = WorkerRunner(repo_root=repo)
    report = runner.spawn(manifest_path=manifest_path)
    assert report["workers"][0]["status"] == "prepared"

    # Move the worktree to a different branch at the same HEAD
    worktree = repo / ".ao/orchestration/ao-ma-20260527-idem111/workers/task-001"
    _run(["git", "-C", str(worktree), "checkout", "-b", "rogue-branch"])

    # Re-spawn: must NOT idempotent-skip because branch identity differs
    report2 = runner.spawn(manifest_path=manifest_path)
    assert report2["workers"][0]["status"] == "failed_worktree_exists_mismatch", report2


def test_spawn_idempotent_skip_when_branch_AND_head_both_match(
    fixture_repo: tuple[Path, str],
) -> None:
    """Re-spawning the same manifest on unchanged state idempotent-skips."""

    repo, base_sha = fixture_repo
    base_dir = repo / ".ao" / "orchestration"
    manifest_path = _write_manifest(
        base_dir=base_dir,
        task_graph_id="ao-ma-20260527-idem222",
        base_sha=base_sha,
        workers=[{"task_id": "task-001", "declared_write_set": ["src/x.py"]}],
    )
    runner = WorkerRunner(repo_root=repo)
    report1 = runner.spawn(manifest_path=manifest_path)
    assert report1["workers"][0]["status"] == "prepared"
    report2 = runner.spawn(manifest_path=manifest_path)
    assert report2["workers"][0]["status"] == "skipped_existing_idempotent"


def test_spawn_conflict_check_overlap_labels_worker_failed_overlap(
    fixture_repo: tuple[Path, str],
) -> None:
    """Codex iter-4 LOW-1: conflict_check=failed_overlap => worker status failed_overlap.

    Previously the worker label was failed_base_mismatch (wrong signal);
    operators triaging the report would chase the wrong cause.
    """

    repo, base_sha = fixture_repo
    base_dir = repo / ".ao" / "orchestration"
    manifest_path = _write_manifest(
        base_dir=base_dir,
        task_graph_id="ao-ma-20260527-ovl1111",
        base_sha=base_sha,
        workers=[
            {"task_id": "task-001", "declared_write_set": ["src/shared.py"]},
            {"task_id": "task-002", "declared_write_set": ["src/shared.py"]},
        ],
    )
    runner = WorkerRunner(repo_root=repo)
    report = runner.spawn(manifest_path=manifest_path)
    assert report["conflict_check"] == "failed_overlap"
    assert all(w["status"] == "failed_overlap" for w in report["workers"]), report["workers"]


def test_cleanup_validates_runner_report_against_schema(
    fixture_repo: tuple[Path, str],
    tmp_path: Path,
) -> None:
    """Codex iter-4 nice-to-have: cleanup fail-closes on tampered runner_report.

    The on-disk runner_report.v1.json is a trust boundary; cleanup must
    re-validate against the bundled schema, not just trust whatever
    JSON is on disk.
    """

    repo, base_sha = fixture_repo
    base_dir = repo / ".ao" / "orchestration"
    manifest_path = _write_manifest(
        base_dir=base_dir,
        task_graph_id="ao-ma-20260527-tamp111",
        base_sha=base_sha,
        workers=[{"task_id": "task-001", "declared_write_set": ["src/x.py"]}],
    )
    runner = WorkerRunner(repo_root=repo)
    runner.spawn(manifest_path=manifest_path)

    # Tamper the runner_report on disk with a schema-invalid mutation
    report_path = base_dir / "ao-ma-20260527-tamp111" / "runner_report.v1.json"
    payload = json.loads(report_path.read_text(encoding="utf-8"))
    payload["conflict_check"] = "totally_invalid_value"
    report_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    with pytest.raises(WorkerRunnerError, match="failed schema"):
        runner.cleanup(manifest_path=manifest_path)


def test_delete_branch_returns_false_when_git_refuses(
    fixture_repo: tuple[Path, str],
) -> None:
    """Codex iter-4 LOW-2: _delete_branch must return False when git refuses.

    Branch deletion via `git branch -d` is refused for unmerged branches.
    If the helper swallows that signal, cleanup() would falsely report
    the branch as deleted when it is in fact still on disk.
    """

    repo, base_sha = fixture_repo
    runner = WorkerRunner(repo_root=repo)

    # Create a branch with a commit NOT on main so `git branch -d` refuses
    _run(["git", "-C", str(repo), "checkout", "-b", "feature/unmerged"])
    (repo / "extra.txt").write_text("unmerged\n", encoding="utf-8")
    _run(["git", "-C", str(repo), "add", "extra.txt"])
    _run(["git", "-C", str(repo), "commit", "-m", "unmerged commit"])
    _run(["git", "-C", str(repo), "checkout", "main"])

    result = runner._delete_branch("feature/unmerged")
    assert result is False, "git refuses unmerged branch deletion"

    # Branch still exists on disk
    head = subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "--verify", "refs/heads/feature/unmerged"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert head.returncode == 0, "branch must still exist when delete refused"


def test_delete_branch_returns_true_when_git_succeeds(
    fixture_repo: tuple[Path, str],
) -> None:
    """_delete_branch returns True for the happy path."""

    repo, _base_sha = fixture_repo
    runner = WorkerRunner(repo_root=repo)
    _run(["git", "-C", str(repo), "branch", "easy-delete"])
    assert runner._delete_branch("easy-delete") is True


# ---------------------------------------------------------------------------
# Codex iter-5 absorb tests
# ---------------------------------------------------------------------------


def test_spawn_manifest_envelope_rejects_guard_flag_widening(
    fixture_repo: tuple[Path, str],
) -> None:
    """Codex iter-5 LOW: manifest guard_flags must be all literal False."""

    repo, base_sha = fixture_repo
    base_dir = repo / ".ao" / "orchestration"
    manifest_path = _write_manifest(
        base_dir=base_dir,
        task_graph_id="ao-ma-20260527-gf11111",
        base_sha=base_sha,
        workers=[{"task_id": "task-001", "declared_write_set": ["src/x.py"]}],
    )
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["guard_flags"]["support_widening"] = True
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    runner = WorkerRunner(repo_root=repo)
    with pytest.raises(WorkerRunnerError, match="support_widening"):
        runner.spawn(manifest_path=manifest_path)


def test_spawn_manifest_envelope_rejects_missing_guard_flags(
    fixture_repo: tuple[Path, str],
) -> None:
    """Manifest without guard_flags is fail-closed."""

    repo, base_sha = fixture_repo
    base_dir = repo / ".ao" / "orchestration"
    manifest_path = _write_manifest(
        base_dir=base_dir,
        task_graph_id="ao-ma-20260527-gf22222",
        base_sha=base_sha,
        workers=[{"task_id": "task-001", "declared_write_set": ["src/x.py"]}],
    )
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    del manifest["guard_flags"]
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    runner = WorkerRunner(repo_root=repo)
    with pytest.raises(WorkerRunnerError, match="guard_flags"):
        runner.spawn(manifest_path=manifest_path)


def test_cleanup_applies_manifest_envelope_validation(
    fixture_repo: tuple[Path, str],
) -> None:
    """Codex iter-5 MEDIUM: cleanup validates envelope BEFORE reading task_graph_id.

    The runner_report.v1.json file must already exist for cleanup to
    even reach its own report-load step; so we use a malformed
    manifest plus a pre-existing report path: cleanup must fail at
    envelope validation, not later with a KeyError.
    """

    repo, base_sha = fixture_repo
    base_dir = repo / ".ao" / "orchestration"
    manifest_path = _write_manifest(
        base_dir=base_dir,
        task_graph_id="ao-ma-20260527-mfn1111",
        base_sha=base_sha,
        workers=[{"task_id": "task-001", "declared_write_set": ["src/x.py"]}],
    )
    runner = WorkerRunner(repo_root=repo)
    runner.spawn(manifest_path=manifest_path)
    # Tamper the manifest envelope after spawn but before cleanup
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["schema_version"] = "totally-wrong"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    with pytest.raises(WorkerRunnerError, match="schema_version"):
        runner.cleanup(manifest_path=manifest_path)


def test_cleanup_manifest_sha256_mismatch_with_runner_report_fails(
    fixture_repo: tuple[Path, str],
) -> None:
    """Codex iter-5 MEDIUM cross-check: cleanup refuses when manifest_sha256
    in the report does not match the on-disk manifest hash.

    This protects against the operator running ``spawn`` on manifest A,
    then quietly swapping the manifest to manifest B, then running
    ``cleanup`` — cleanup would otherwise apply manifest A's worktree
    layout to manifest B's intent.
    """

    repo, base_sha = fixture_repo
    base_dir = repo / ".ao" / "orchestration"
    manifest_path = _write_manifest(
        base_dir=base_dir,
        task_graph_id="ao-ma-20260527-mfx1111",
        base_sha=base_sha,
        workers=[{"task_id": "task-001", "declared_write_set": ["src/x.py"]}],
    )
    runner = WorkerRunner(repo_root=repo)
    runner.spawn(manifest_path=manifest_path)
    # Mutate the manifest in a way that the envelope validator still
    # accepts (whitespace) so we reach the manifest_sha256 cross-check.
    text = manifest_path.read_text(encoding="utf-8")
    manifest_path.write_text(text + "\n", encoding="utf-8")
    with pytest.raises(WorkerRunnerError, match="manifest_sha256 mismatch"):
        runner.cleanup(manifest_path=manifest_path)
