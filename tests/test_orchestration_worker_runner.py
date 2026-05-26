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
