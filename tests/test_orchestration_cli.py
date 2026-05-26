"""AO-MA-3 + AO-MA-4 CLI handler tests (end-to-end CLI smoke).

Section 1 (AO-MA-3): plan / declared-spec parser / thin wrapper.
Section 2 (AO-MA-4 — Codex iter-3 absorb): ``orchestration {spawn,cleanup}``
exercised through the canonical ``ao_kernel.cli.main`` entrypoint with a
real git fixture, asserting exit codes + JSON envelope + worktree side
effects + fail-closed paths.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from ao_kernel.cli import main as cli_main
from ao_kernel.orchestration.cli_handlers import _parse_declared_specs

_REPO_ROOT = Path(__file__).resolve().parents[1]


def test_parse_declared_specs_single() -> None:
    specs = _parse_declared_specs(["task-001:ao_kernel/foo.py,tests/test_foo.py:Fix foo"])
    assert specs is not None
    assert len(specs) == 1
    spec = specs[0]
    assert spec.task_id == "task-001"
    assert spec.write_paths == ["ao_kernel/foo.py", "tests/test_foo.py"]
    assert spec.description == "Fix foo"


def test_parse_declared_specs_multiple() -> None:
    specs = _parse_declared_specs(
        [
            "task-001:ao_kernel/a.py:slice A",
            "task-002:tests/test_b.py:slice B",
        ]
    )
    assert specs is not None
    assert len(specs) == 2


def test_parse_declared_specs_default_description() -> None:
    specs = _parse_declared_specs(["task-001:ao_kernel/foo.py"])
    assert specs is not None
    assert specs[0].description == "Slice task-001"


def test_parse_declared_specs_empty_returns_none() -> None:
    assert _parse_declared_specs(None) is None
    assert _parse_declared_specs([]) is None


def test_parse_declared_specs_invalid_format_exits() -> None:
    with pytest.raises(SystemExit, match="<task_id>:<comma-paths>"):
        _parse_declared_specs(["bad-input"])


def test_cli_plan_emits_artifacts(tmp_path: Path) -> None:
    out_dir = tmp_path / "out"
    rc = cli_main(
        [
            "orchestration",
            "plan",
            "--goal",
            "AO-MA-3 unit test smoke",
            "--output-dir",
            str(out_dir),
            "--base-sha",
            "a" * 40,
            "--repo",
            "Halildeu/ao-kernel",
            "--repo-root",
            str(_REPO_ROOT),
            "--format",
            "json",
        ]
    )
    assert rc == 0
    # Find the produced task_graph_id directory
    subdirs = [p for p in out_dir.iterdir() if p.is_dir()]
    assert len(subdirs) == 1
    subdir = subdirs[0]
    assert (subdir / "task_graph.v1.json").exists()
    assert (subdir / "manifest.v1.json").exists()
    manifest = json.loads((subdir / "manifest.v1.json").read_text(encoding="utf-8"))
    assert manifest["task_graph_id"].startswith("ao-ma-")


def test_cli_plan_overlap_exit_nonzero(tmp_path: Path) -> None:
    out_dir = tmp_path / "out"
    rc = cli_main(
        [
            "orchestration",
            "plan",
            "--goal",
            "overlap smoke",
            "--output-dir",
            str(out_dir),
            "--base-sha",
            "a" * 40,
            "--repo",
            "Halildeu/ao-kernel",
            "--repo-root",
            str(_REPO_ROOT),
            "--declared-spec",
            "task-001:ao_kernel/foo.py:A",
            "--declared-spec",
            "task-002:ao_kernel/foo.py:B",
            "--format",
            "json",
        ]
    )
    assert rc == 1


def test_thin_wrapper_script_invocation(tmp_path: Path) -> None:
    """scripts/ao_orchestrator.py thin wrapper forwards to canonical CLI."""

    out_dir = tmp_path / "out"
    completed = subprocess.run(
        [
            sys.executable,
            str(_REPO_ROOT / "scripts" / "ao_orchestrator.py"),
            "plan",
            "--goal",
            "thin wrapper smoke",
            "--output-dir",
            str(out_dir),
            "--base-sha",
            "a" * 40,
            "--repo",
            "Halildeu/ao-kernel",
            "--repo-root",
            str(_REPO_ROOT),
            "--format",
            "json",
        ],
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert completed.returncode == 0, f"stderr: {completed.stderr}"
    assert "task_graph_id" in completed.stdout


# ---------------------------------------------------------------------------
# AO-MA-4 spawn / cleanup CLI integration tests (Codex iter-3 absorb)
# ---------------------------------------------------------------------------

import hashlib as _hashlib  # noqa: E402 — local imports keep AO-MA-3 block clean
from collections.abc import Iterator as _Iterator  # noqa: E402


def _ao4_run(cmd: list[str], cwd: Path | None = None) -> str:
    completed = subprocess.run(cmd, cwd=cwd, check=True, capture_output=True, text=True, timeout=20)
    return completed.stdout.strip()


def _ao4_git_init_repo(repo: Path) -> str:
    """Init a fresh git repo with one initial commit + synthesized origin/main."""

    _ao4_run(["git", "init", "--initial-branch=main", str(repo)])
    _ao4_run(["git", "-C", str(repo), "config", "user.email", "test@example.com"])
    _ao4_run(["git", "-C", str(repo), "config", "user.name", "test"])
    (repo / "README.md").write_text("initial\n", encoding="utf-8")
    _ao4_run(["git", "-C", str(repo), "add", "README.md"])
    _ao4_run(["git", "-C", str(repo), "commit", "-m", "initial"])
    sha = _ao4_run(["git", "-C", str(repo), "rev-parse", "HEAD"])
    _ao4_run(["git", "-C", str(repo), "update-ref", "refs/remotes/origin/main", sha])
    return sha


def _ao4_sha256(path: Path) -> str:
    return "sha256:" + _hashlib.sha256(path.read_bytes()).hexdigest()


def _ao4_write_manifest(
    *,
    base_dir: Path,
    task_graph_id: str,
    base_sha: str,
    workers: list[dict],
) -> Path:
    """Emit a minimal AO-MA-3-compatible artifact set + return manifest path."""

    out_dir = base_dir / task_graph_id
    out_dir.mkdir(parents=True, exist_ok=True)
    task_graph = {
        "schema_version": "ao-ma-task-graph.v1",
        "task_graph_id": task_graph_id,
        "repo": "Halildeu/ao-kernel",
        "goal": "AO-MA-4 cli fixture",
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
            "sha256": _ao4_sha256(task_graph_path),
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
                "session_id": f"ao-ma-4-cli-{task_graph_id}",
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
                "sha256": _ao4_sha256(assignment_path),
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
def cli_repo(tmp_path: Path) -> _Iterator[tuple[Path, str]]:
    repo = tmp_path / "repo"
    sha = _ao4_git_init_repo(repo)
    yield repo, sha


def test_cli_spawn_success_exits_zero_and_prints_report(
    cli_repo: tuple[Path, str],
    capsys: pytest.CaptureFixture[str],
) -> None:
    """CLI spawn happy path: prepares worktree, exit 0, JSON report parseable."""

    repo, base_sha = cli_repo
    base_dir = repo / ".ao" / "orchestration"
    manifest_path = _ao4_write_manifest(
        base_dir=base_dir,
        task_graph_id="ao-ma-20260527-cli0001",
        base_sha=base_sha,
        workers=[{"task_id": "task-001", "declared_write_set": ["src/a.py"]}],
    )
    rc = cli_main(
        [
            "orchestration",
            "spawn",
            "--manifest",
            str(manifest_path),
            "--repo-root",
            str(repo),
            "--format",
            "json",
        ]
    )
    assert rc == 0
    report = json.loads(capsys.readouterr().out)
    assert report["task_graph_id"] == "ao-ma-20260527-cli0001"
    assert report["base_sync_check"] == "pass"
    assert report["conflict_check"] == "pass"
    assert [w["status"] for w in report["workers"]] == ["prepared"]
    assert (repo / ".ao/orchestration/ao-ma-20260527-cli0001/workers/task-001/.git").exists()


def test_cli_spawn_empty_write_set_exits_one(
    cli_repo: tuple[Path, str],
    capsys: pytest.CaptureFixture[str],
) -> None:
    """CLI spawn fail-closed: empty declared_write_set => failed_empty_write_set + exit 1."""

    repo, base_sha = cli_repo
    base_dir = repo / ".ao" / "orchestration"
    manifest_path = _ao4_write_manifest(
        base_dir=base_dir,
        task_graph_id="ao-ma-20260527-cli0002",
        base_sha=base_sha,
        workers=[{"task_id": "task-001", "declared_write_set": []}],
    )
    rc = cli_main(
        [
            "orchestration",
            "spawn",
            "--manifest",
            str(manifest_path),
            "--repo-root",
            str(repo),
            "--format",
            "json",
        ]
    )
    assert rc == 1
    report = json.loads(capsys.readouterr().out)
    assert report["workers"][0]["status"] == "failed_empty_write_set"


def test_cli_spawn_missing_manifest_exits_two(
    cli_repo: tuple[Path, str],
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Missing --manifest path => operator error code (2), not runner failure (1)."""

    repo, _ = cli_repo
    rc = cli_main(
        [
            "orchestration",
            "spawn",
            "--manifest",
            str(repo / "does_not_exist.json"),
            "--repo-root",
            str(repo),
        ]
    )
    assert rc == 2
    err = capsys.readouterr().err
    assert "manifest not found" in err


def test_cli_spawn_then_cleanup_clean_round_trip(
    cli_repo: tuple[Path, str],
    capsys: pytest.CaptureFixture[str],
) -> None:
    """End-to-end CLI: spawn then cleanup; clean worktree is removed; both exit 0."""

    repo, base_sha = cli_repo
    base_dir = repo / ".ao" / "orchestration"
    manifest_path = _ao4_write_manifest(
        base_dir=base_dir,
        task_graph_id="ao-ma-20260527-cli0003",
        base_sha=base_sha,
        workers=[{"task_id": "task-001", "declared_write_set": ["src/a.py"]}],
    )

    rc_spawn = cli_main(
        [
            "orchestration",
            "spawn",
            "--manifest",
            str(manifest_path),
            "--repo-root",
            str(repo),
            "--format",
            "json",
        ]
    )
    assert rc_spawn == 0
    capsys.readouterr()  # discard spawn output

    rc_cleanup = cli_main(
        [
            "orchestration",
            "cleanup",
            "--manifest",
            str(manifest_path),
            "--repo-root",
            str(repo),
            "--format",
            "json",
        ]
    )
    assert rc_cleanup == 0
    result = json.loads(capsys.readouterr().out)
    worktree = repo / ".ao/orchestration/ao-ma-20260527-cli0003/workers/task-001"
    assert not worktree.exists()
    assert any(str(worktree.resolve()) == w for w in result["removed_worktrees"])
    assert result["kept_dirty"] == []


def test_cli_cleanup_dirty_worktree_exits_one(
    cli_repo: tuple[Path, str],
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Cleanup must refuse to remove a dirty worktree + exit 1 to surface the kept entry."""

    repo, base_sha = cli_repo
    base_dir = repo / ".ao" / "orchestration"
    manifest_path = _ao4_write_manifest(
        base_dir=base_dir,
        task_graph_id="ao-ma-20260527-cli0004",
        base_sha=base_sha,
        workers=[{"task_id": "task-001", "declared_write_set": ["src/a.py"]}],
    )
    rc_spawn = cli_main(
        [
            "orchestration",
            "spawn",
            "--manifest",
            str(manifest_path),
            "--repo-root",
            str(repo),
            "--format",
            "json",
        ]
    )
    assert rc_spawn == 0
    capsys.readouterr()

    # Dirty the worktree with an untracked file
    worktree = repo / ".ao/orchestration/ao-ma-20260527-cli0004/workers/task-001"
    (worktree / "stray.txt").write_text("uncommitted work\n", encoding="utf-8")

    rc_cleanup = cli_main(
        [
            "orchestration",
            "cleanup",
            "--manifest",
            str(manifest_path),
            "--repo-root",
            str(repo),
            "--format",
            "json",
        ]
    )
    assert rc_cleanup == 1
    result = json.loads(capsys.readouterr().out)
    assert worktree.exists()  # NOT removed because dirty
    assert str(worktree.resolve()) in result["kept_dirty"]
    assert result["removed_worktrees"] == []


def test_cli_cleanup_before_spawn_exits_one(
    cli_repo: tuple[Path, str],
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Cleanup before spawn => no runner_report.v1.json => fail-closed exit 1."""

    repo, base_sha = cli_repo
    base_dir = repo / ".ao" / "orchestration"
    manifest_path = _ao4_write_manifest(
        base_dir=base_dir,
        task_graph_id="ao-ma-20260527-cli0005",
        base_sha=base_sha,
        workers=[{"task_id": "task-001", "declared_write_set": ["src/a.py"]}],
    )
    rc = cli_main(
        [
            "orchestration",
            "cleanup",
            "--manifest",
            str(manifest_path),
            "--repo-root",
            str(repo),
            "--format",
            "json",
        ]
    )
    assert rc == 1
    err = capsys.readouterr().err
    assert "runner_report.v1.json missing" in err


def test_resolve_worktree_base_cli_flag_wins(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Codex iter-4 doc-drift absorb: CLI flag wins over env var."""

    from ao_kernel.orchestration.cli_handlers import _resolve_worktree_base

    cli_dir = tmp_path / "cli-base"
    env_dir = tmp_path / "env-base"
    cli_dir.mkdir()
    env_dir.mkdir()
    monkeypatch.setenv("AO_MA_WORKTREE_BASE", str(env_dir))
    assert _resolve_worktree_base(str(cli_dir)) == cli_dir.resolve()


def test_resolve_worktree_base_env_fallback(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """When no CLI flag, AO_MA_WORKTREE_BASE env is honored."""

    from ao_kernel.orchestration.cli_handlers import _resolve_worktree_base

    env_dir = tmp_path / "env-base"
    env_dir.mkdir()
    monkeypatch.setenv("AO_MA_WORKTREE_BASE", str(env_dir))
    assert _resolve_worktree_base(None) == env_dir.resolve()


def test_resolve_worktree_base_returns_none_when_neither_set(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Neither CLI flag nor env set => None (runner uses planned path)."""

    from ao_kernel.orchestration.cli_handlers import _resolve_worktree_base

    monkeypatch.delenv("AO_MA_WORKTREE_BASE", raising=False)
    assert _resolve_worktree_base(None) is None


def test_cli_spawn_uses_AO_MA_WORKTREE_BASE_env_var(
    cli_repo: tuple[Path, str],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    """End-to-end: AO_MA_WORKTREE_BASE env makes the worktree land under it."""

    repo, base_sha = cli_repo
    base_dir = repo / ".ao" / "orchestration"
    manifest_path = _ao4_write_manifest(
        base_dir=base_dir,
        task_graph_id="ao-ma-20260527-envb111",
        base_sha=base_sha,
        workers=[{"task_id": "task-001", "declared_write_set": ["src/a.py"]}],
    )
    override_base = tmp_path / "override-worktrees"
    override_base.mkdir()
    monkeypatch.setenv("AO_MA_WORKTREE_BASE", str(override_base))

    rc = cli_main(
        [
            "orchestration",
            "spawn",
            "--manifest",
            str(manifest_path),
            "--repo-root",
            str(repo),
            "--format",
            "json",
        ]
    )
    assert rc == 0
    report = json.loads(capsys.readouterr().out)
    actual_worktree = Path(report["workers"][0]["actual_worktree"])
    assert actual_worktree.is_relative_to(override_base.resolve()), (
        f"worktree {actual_worktree} not under env override {override_base.resolve()}"
    )
