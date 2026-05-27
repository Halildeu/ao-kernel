"""AO-MA-5 integrator tests (Codex thread 019e6850 iter-1→iter-4 AGREE absorb).

22+ tests cover:
- Happy path (Crit-D 3-of-3 evidence)
- Missing evidence (Crit-E pending: missing_worker_result, missing_review_verdict,
  missing_verification_report)
- Hard rejects (review_revise, review_block, verification_failed,
  guard_flag_violation, schema_invalid, actual_write_set_overlap)
- CF3 conflict escalate (two accepted workers same file → both not_integratable)
- Trust boundary (manifest envelope + runner_report schema)
- assembly_plan structured data (argv form, operator_only=true)
- HARD RULE pins (no subprocess import, no gh/git push literals, no
  branch/worktree create, decision-not-raise for non-error states)
- verification_passed predicate across schema fields (skipped policy)
- worker_result_ref null sentinel
"""

from __future__ import annotations

import ast
import hashlib
import json
import subprocess
from collections.abc import Iterator
from pathlib import Path

import pytest

from ao_kernel.orchestration.integrator import (
    IntegrationDecision,
    Integrator,
    IntegratorError,
    render_assembly_plan_text,
    verification_passed,
)


def _run(cmd: list[str], cwd: Path | None = None) -> str:
    completed = subprocess.run(cmd, cwd=cwd, check=True, capture_output=True, text=True, timeout=20)
    return completed.stdout.strip()


def _git_init_repo(repo: Path) -> str:
    _run(["git", "init", "--initial-branch=main", str(repo)])
    _run(["git", "-C", str(repo), "config", "user.email", "test@example.com"])
    _run(["git", "-C", str(repo), "config", "user.name", "test"])
    (repo / "README.md").write_text("initial\n", encoding="utf-8")
    _run(["git", "-C", str(repo), "add", "README.md"])
    _run(["git", "-C", str(repo), "commit", "-m", "initial"])
    sha = _run(["git", "-C", str(repo), "rev-parse", "HEAD"])
    _run(["git", "-C", str(repo), "update-ref", "refs/remotes/origin/main", sha])
    return sha


def _sha256(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _write_artifact_set(
    *,
    base_dir: Path,
    task_graph_id: str,
    base_sha: str,
    workers: list[dict],
) -> tuple[Path, Path]:
    """Build a minimal AO-MA-3 manifest + runner_report + per-worker artifacts.

    Returns (manifest_path, base_dir/<task_graph_id>) for the test to use.
    """

    out_dir = base_dir / task_graph_id
    out_dir.mkdir(parents=True, exist_ok=True)

    task_graph = {
        "schema_version": "ao-ma-task-graph.v1",
        "task_graph_id": task_graph_id,
        "repo": "Halildeu/ao-kernel",
        "goal": "AO-MA-5 integrator test fixture",
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
    # Per-worker assignment artifact (for envelope completeness)
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
                "session_id": f"ao-ma-5-test-{task_graph_id}",
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

    # runner_report (minimal schema-valid; we won't have AO-MA-4 SHAs here)
    runner_report = {
        "schema_version": "ao-ma-runner-report.v1",
        "task_graph_id": task_graph_id,
        "manifest_sha256": _sha256(manifest_path),
        "base_sha": base_sha,
        "generated_at": "2026-05-27T00:00:00Z",
        "conflict_check": "pass",
        "base_sync_check": "pass",
        "workers": [
            {
                "assignment_ref": f"agent_assignment-{w['task_id']}.v1.json",
                "assignment_sha256": _sha256(out_dir / f"agent_assignment-{w['task_id']}.v1.json"),
                "task_id": w["task_id"],
                "branch": f"codex/ao-ma-{task_graph_id}/{w['task_id']}",
                "planned_worktree": f".ao/orchestration/{task_graph_id}/workers/{w['task_id']}",
                "actual_worktree": f"/tmp/work/{w['task_id']}",
                "status": "prepared",
                "reason": "worktree + branch created",
                "expected_worker_result_path": str(out_dir / f"workers/{w['task_id']}/worker_result.v1.json"),
            }
            for w in workers
        ],
        "guard_flags": {
            "support_widening": False,
            "production_platform_claim": False,
            "live_adapter_execution": False,
        },
    }
    runner_report_path = out_dir / "runner_report.v1.json"
    runner_report_path.write_text(json.dumps(runner_report, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    return manifest_path, out_dir


def _write_worker_result(
    *,
    out_dir: Path,
    task_id: str,
    task_graph_id: str,
    base_sha: str,
    declared_write_set: list[str],
    actual_changed_files: list[str],
    guard_flags_overrides: dict | None = None,
    secrets_recorded: bool = False,
) -> Path:
    """Write a schema-valid worker_result.v1.json into <out_dir>/workers/<task_id>/."""

    worker_dir = out_dir / "workers" / task_id
    worker_dir.mkdir(parents=True, exist_ok=True)
    guard_flags = {
        "support_widening": False,
        "production_platform_claim": False,
        "live_adapter_execution": False,
    }
    if guard_flags_overrides:
        guard_flags.update(guard_flags_overrides)
    payload = {
        "schema_version": "ao-ma-worker-result.v1",
        "task_graph_id": task_graph_id,
        "task_id": task_id,
        "assignment_id": f"{task_graph_id}-{task_id}",
        "worker": {
            "agent_id": f"claude-{task_id}",
            "agent_type": "implementer",
            "provider": "anthropic",
            "session_id": f"ao-ma-5-test-{task_graph_id}",
        },
        "base_ref": "refs/heads/main",
        "base_sha": base_sha,
        "head_ref": f"codex/ao-ma-{task_graph_id}/{task_id}",
        "head_sha": "c" * 40,
        "declared_write_set": declared_write_set,
        "actual_changed_files": actual_changed_files,
        "summary": "test worker summary",
        "tests_run": [{"command": "pytest", "outcome": "pass"}],
        "known_gaps": [],
        "no_secret_attestation": {"secrets_recorded": secrets_recorded},
        "guard_flags": guard_flags,
    }
    wr_path = worker_dir / "worker_result.v1.json"
    wr_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return wr_path


def _write_review_verdict(
    *,
    out_dir: Path,
    task_id: str,
    task_graph_id: str,
    verdict: str,
) -> Path:
    worker_dir = out_dir / "workers" / task_id
    worker_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": "ao-ma-review-verdict.v1",
        "task_graph_id": task_graph_id,
        "reviewed_task_id": task_id,
        "reviewer": {
            "agent_id": "codex-reviewer",
            "agent_type": "reviewer",
            "provider": "openai",
            "session_id": "review-session",
        },
        "implementer": {
            "agent_id": f"claude-{task_id}",
            "agent_type": "implementer",
            "provider": "anthropic",
            "session_id": "impl-session",
        },
        "independent_review": True,
        "cross_provider_verified": True,
        "allowed_sources": ["pr_diff", "issue_acceptance"],
        "prohibited_sources_absent": True,
        "verdict": verdict,
        "findings": [],
        "reviewed_artifacts": [],
        "no_secret_attestation": {"secrets_recorded": False},
        "guard_flags": {
            "support_widening": False,
            "production_platform_claim": False,
            "live_adapter_execution": False,
        },
    }
    rv_path = worker_dir / "review_verdict.v1.json"
    rv_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return rv_path


def _write_verification_report(
    *,
    out_dir: Path,
    task_id: str,
    task_graph_id: str,
    failed_checks: list[str] | None = None,
    scope_passed: bool = True,
    secret_scan_passed: bool = True,
    command_outcomes: list[str] | None = None,
) -> Path:
    worker_dir = out_dir / "workers" / task_id
    worker_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": "ao-ma-verification-report.v1",
        "task_graph_id": task_graph_id,
        "verified_task_ids": [task_id],
        "verifier": {
            "agent_id": "claude-verifier",
            "agent_type": "verifier",
            "provider": "anthropic",
            "session_id": "verify-session",
        },
        "commands": [
            {"command": f"check-{i}", "outcome": outcome} for i, outcome in enumerate(command_outcomes or ["pass"])
        ],
        "artifact_hashes": [],
        "failed_checks": failed_checks or [],
        "scope_check": {"passed": scope_passed},
        "secret_scan": {"passed": secret_scan_passed},
        "guard_flags": {
            "support_widening": False,
            "production_platform_claim": False,
            "live_adapter_execution": False,
        },
    }
    vr_path = worker_dir / "verification_report.v1.json"
    vr_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return vr_path


@pytest.fixture
def repo(tmp_path: Path) -> Iterator[tuple[Path, str]]:
    r = tmp_path / "repo"
    sha = _git_init_repo(r)
    yield r, sha


# ---------------------------------------------------------------------------
# Happy path + Crit-D acceptance
# ---------------------------------------------------------------------------


def test_integrate_accepts_3_of_3_workers_full_evidence(repo: tuple[Path, str], tmp_path: Path) -> None:
    """Crit-D: worker_result + review AGREE + verify pass → accept."""

    r, base_sha = repo
    base_dir = r / ".ao" / "orchestration"
    manifest_path, out_dir = _write_artifact_set(
        base_dir=base_dir,
        task_graph_id="ao-ma-20260527-acc1111",
        base_sha=base_sha,
        workers=[
            {"task_id": "task-001", "declared_write_set": ["src/a.py"]},
            {"task_id": "task-002", "declared_write_set": ["src/b.py"]},
            {"task_id": "task-003", "declared_write_set": ["src/c.py"]},
        ],
    )
    rv_paths = {}
    vr_paths = {}
    for tid, decl in [("task-001", ["src/a.py"]), ("task-002", ["src/b.py"]), ("task-003", ["src/c.py"])]:
        _write_worker_result(
            out_dir=out_dir,
            task_id=tid,
            task_graph_id="ao-ma-20260527-acc1111",
            base_sha=base_sha,
            declared_write_set=decl,
            actual_changed_files=decl,
        )
        rv_paths[tid] = _write_review_verdict(
            out_dir=out_dir, task_id=tid, task_graph_id="ao-ma-20260527-acc1111", verdict="AGREE"
        )
        vr_paths[tid] = _write_verification_report(out_dir=out_dir, task_id=tid, task_graph_id="ao-ma-20260527-acc1111")
    integrator = Integrator(repo_root=r)
    decision = integrator.integrate(
        manifest_path=manifest_path,
        review_verdict_paths=rv_paths,
        verification_report_paths=vr_paths,
    )
    assert decision.overall_status == "all_accepted", decision.diagnostics
    assert not decision.has_pending
    assert not decision.has_rejections
    assert not decision.has_conflicts
    assert len(decision.report["accepted_worker_results"]) == 3
    assert decision.report["final_changed_files"] == sorted(["src/a.py", "src/b.py", "src/c.py"])


# ---------------------------------------------------------------------------
# Crit-E missing evidence
# ---------------------------------------------------------------------------


def test_integrate_not_integratable_when_worker_result_missing(repo: tuple[Path, str], tmp_path: Path) -> None:
    r, base_sha = repo
    base_dir = r / ".ao" / "orchestration"
    manifest_path, _ = _write_artifact_set(
        base_dir=base_dir,
        task_graph_id="ao-ma-20260527-mwr1111",
        base_sha=base_sha,
        workers=[{"task_id": "task-001", "declared_write_set": ["src/a.py"]}],
    )
    # NO worker_result, NO review, NO verify
    decision = Integrator(repo_root=r).integrate(manifest_path=manifest_path)
    assert decision.has_pending
    assert decision.report["worker_decisions"][0]["decision"] == "not_integratable"
    assert decision.report["worker_decisions"][0]["reason_code"] == "missing_worker_result"
    assert decision.report["worker_decisions"][0]["worker_result_ref"] is None


def test_integrate_not_integratable_when_review_missing(repo: tuple[Path, str]) -> None:
    r, base_sha = repo
    base_dir = r / ".ao" / "orchestration"
    manifest_path, out_dir = _write_artifact_set(
        base_dir=base_dir,
        task_graph_id="ao-ma-20260527-mrv1111",
        base_sha=base_sha,
        workers=[{"task_id": "task-001", "declared_write_set": ["src/a.py"]}],
    )
    _write_worker_result(
        out_dir=out_dir,
        task_id="task-001",
        task_graph_id="ao-ma-20260527-mrv1111",
        base_sha=base_sha,
        declared_write_set=["src/a.py"],
        actual_changed_files=["src/a.py"],
    )
    # NO review, NO verify
    decision = Integrator(repo_root=r).integrate(manifest_path=manifest_path)
    assert decision.has_pending
    assert decision.report["worker_decisions"][0]["reason_code"] == "missing_review_verdict"


def test_integrate_not_integratable_when_verify_missing(repo: tuple[Path, str]) -> None:
    r, base_sha = repo
    base_dir = r / ".ao" / "orchestration"
    manifest_path, out_dir = _write_artifact_set(
        base_dir=base_dir,
        task_graph_id="ao-ma-20260527-mvr1111",
        base_sha=base_sha,
        workers=[{"task_id": "task-001", "declared_write_set": ["src/a.py"]}],
    )
    _write_worker_result(
        out_dir=out_dir,
        task_id="task-001",
        task_graph_id="ao-ma-20260527-mvr1111",
        base_sha=base_sha,
        declared_write_set=["src/a.py"],
        actual_changed_files=["src/a.py"],
    )
    rv_path = _write_review_verdict(
        out_dir=out_dir, task_id="task-001", task_graph_id="ao-ma-20260527-mvr1111", verdict="AGREE"
    )
    # NO verify
    decision = Integrator(repo_root=r).integrate(
        manifest_path=manifest_path,
        review_verdict_paths={"task-001": rv_path},
    )
    assert decision.has_pending
    assert decision.report["worker_decisions"][0]["reason_code"] == "missing_verification_report"


# ---------------------------------------------------------------------------
# Hard rejects
# ---------------------------------------------------------------------------


def test_integrate_rejects_when_review_revise(repo: tuple[Path, str]) -> None:
    r, base_sha = repo
    base_dir = r / ".ao" / "orchestration"
    manifest_path, out_dir = _write_artifact_set(
        base_dir=base_dir,
        task_graph_id="ao-ma-20260527-rrv1111",
        base_sha=base_sha,
        workers=[{"task_id": "task-001", "declared_write_set": ["src/a.py"]}],
    )
    _write_worker_result(
        out_dir=out_dir,
        task_id="task-001",
        task_graph_id="ao-ma-20260527-rrv1111",
        base_sha=base_sha,
        declared_write_set=["src/a.py"],
        actual_changed_files=["src/a.py"],
    )
    rv_path = _write_review_verdict(
        out_dir=out_dir, task_id="task-001", task_graph_id="ao-ma-20260527-rrv1111", verdict="REVISE"
    )
    decision = Integrator(repo_root=r).integrate(
        manifest_path=manifest_path,
        review_verdict_paths={"task-001": rv_path},
    )
    assert decision.has_rejections
    assert decision.report["worker_decisions"][0]["reason_code"] == "review_revise"


def test_integrate_rejects_when_review_block(repo: tuple[Path, str]) -> None:
    r, base_sha = repo
    base_dir = r / ".ao" / "orchestration"
    manifest_path, out_dir = _write_artifact_set(
        base_dir=base_dir,
        task_graph_id="ao-ma-20260527-rbk1111",
        base_sha=base_sha,
        workers=[{"task_id": "task-001", "declared_write_set": ["src/a.py"]}],
    )
    _write_worker_result(
        out_dir=out_dir,
        task_id="task-001",
        task_graph_id="ao-ma-20260527-rbk1111",
        base_sha=base_sha,
        declared_write_set=["src/a.py"],
        actual_changed_files=["src/a.py"],
    )
    rv_path = _write_review_verdict(
        out_dir=out_dir, task_id="task-001", task_graph_id="ao-ma-20260527-rbk1111", verdict="BLOCK"
    )
    decision = Integrator(repo_root=r).integrate(
        manifest_path=manifest_path,
        review_verdict_paths={"task-001": rv_path},
    )
    assert decision.has_rejections
    assert decision.report["worker_decisions"][0]["reason_code"] == "review_block"


def test_integrate_rejects_when_verify_failed(repo: tuple[Path, str]) -> None:
    r, base_sha = repo
    base_dir = r / ".ao" / "orchestration"
    manifest_path, out_dir = _write_artifact_set(
        base_dir=base_dir,
        task_graph_id="ao-ma-20260527-vfl1111",
        base_sha=base_sha,
        workers=[{"task_id": "task-001", "declared_write_set": ["src/a.py"]}],
    )
    _write_worker_result(
        out_dir=out_dir,
        task_id="task-001",
        task_graph_id="ao-ma-20260527-vfl1111",
        base_sha=base_sha,
        declared_write_set=["src/a.py"],
        actual_changed_files=["src/a.py"],
    )
    rv_path = _write_review_verdict(
        out_dir=out_dir, task_id="task-001", task_graph_id="ao-ma-20260527-vfl1111", verdict="AGREE"
    )
    vr_path = _write_verification_report(
        out_dir=out_dir,
        task_id="task-001",
        task_graph_id="ao-ma-20260527-vfl1111",
        failed_checks=["scope_violation"],
    )
    decision = Integrator(repo_root=r).integrate(
        manifest_path=manifest_path,
        review_verdict_paths={"task-001": rv_path},
        verification_report_paths={"task-001": vr_path},
    )
    assert decision.has_rejections
    assert decision.report["worker_decisions"][0]["reason_code"] == "verification_failed"


def test_integrate_rejects_when_worker_result_guard_flag_violation(repo: tuple[Path, str]) -> None:
    """worker_result.v1 schema has `const: false` on each guard flag; setting
    True triggers schema_invalid first (schema is the first trust gate, BEFORE
    the integrator's defensive guard_flag_violation check). Both reason_codes
    remain valid in the enum — schema is the SSOT for this invariant."""

    r, base_sha = repo
    base_dir = r / ".ao" / "orchestration"
    manifest_path, out_dir = _write_artifact_set(
        base_dir=base_dir,
        task_graph_id="ao-ma-20260527-gfv1111",
        base_sha=base_sha,
        workers=[{"task_id": "task-001", "declared_write_set": ["src/a.py"]}],
    )
    _write_worker_result(
        out_dir=out_dir,
        task_id="task-001",
        task_graph_id="ao-ma-20260527-gfv1111",
        base_sha=base_sha,
        declared_write_set=["src/a.py"],
        actual_changed_files=["src/a.py"],
        guard_flags_overrides={"support_widening": True},
    )
    decision = Integrator(repo_root=r).integrate(manifest_path=manifest_path)
    assert decision.has_rejections
    # Schema catches the const violation first; integrator labels schema_invalid
    assert decision.report["worker_decisions"][0]["reason_code"] == "schema_invalid"


def test_integrate_rejects_when_worker_result_secrets_recorded_true(repo: tuple[Path, str]) -> None:
    r, base_sha = repo
    base_dir = r / ".ao" / "orchestration"
    manifest_path, out_dir = _write_artifact_set(
        base_dir=base_dir,
        task_graph_id="ao-ma-20260527-sec1111",
        base_sha=base_sha,
        workers=[{"task_id": "task-001", "declared_write_set": ["src/a.py"]}],
    )
    _write_worker_result(
        out_dir=out_dir,
        task_id="task-001",
        task_graph_id="ao-ma-20260527-sec1111",
        base_sha=base_sha,
        declared_write_set=["src/a.py"],
        actual_changed_files=["src/a.py"],
        secrets_recorded=True,
    )
    decision = Integrator(repo_root=r).integrate(manifest_path=manifest_path)
    assert decision.has_rejections
    # worker_result.v1 schema has no_secret_attestation.secrets_recorded
    # const false — schema catches True first → schema_invalid (semantic
    # equivalent to guard_flag_violation; schema is SSOT for the invariant)
    assert decision.report["worker_decisions"][0]["reason_code"] == "schema_invalid"


def test_integrate_rejects_when_actual_outside_declared(repo: tuple[Path, str]) -> None:
    """actual_changed_files NOT ⊆ declared_write_set → reject with actual_write_set_overlap."""

    r, base_sha = repo
    base_dir = r / ".ao" / "orchestration"
    manifest_path, out_dir = _write_artifact_set(
        base_dir=base_dir,
        task_graph_id="ao-ma-20260527-aws1111",
        base_sha=base_sha,
        workers=[{"task_id": "task-001", "declared_write_set": ["src/a.py"]}],
    )
    _write_worker_result(
        out_dir=out_dir,
        task_id="task-001",
        task_graph_id="ao-ma-20260527-aws1111",
        base_sha=base_sha,
        declared_write_set=["src/a.py"],
        actual_changed_files=["src/a.py", "src/UNDECLARED.py"],
    )
    decision = Integrator(repo_root=r).integrate(manifest_path=manifest_path)
    assert decision.has_rejections
    assert decision.report["worker_decisions"][0]["reason_code"] == "actual_write_set_overlap"


# ---------------------------------------------------------------------------
# CF3 conflict between accepted workers
# ---------------------------------------------------------------------------


def test_integrate_conflict_two_accepted_workers_same_file(repo: tuple[Path, str]) -> None:
    r, base_sha = repo
    base_dir = r / ".ao" / "orchestration"
    manifest_path, out_dir = _write_artifact_set(
        base_dir=base_dir,
        task_graph_id="ao-ma-20260527-cnf1111",
        base_sha=base_sha,
        workers=[
            {"task_id": "task-001", "declared_write_set": ["src/shared.py"]},
            {"task_id": "task-002", "declared_write_set": ["src/shared.py"]},
        ],
    )
    rv_paths = {}
    vr_paths = {}
    for tid in ("task-001", "task-002"):
        _write_worker_result(
            out_dir=out_dir,
            task_id=tid,
            task_graph_id="ao-ma-20260527-cnf1111",
            base_sha=base_sha,
            declared_write_set=["src/shared.py"],
            actual_changed_files=["src/shared.py"],
        )
        rv_paths[tid] = _write_review_verdict(
            out_dir=out_dir, task_id=tid, task_graph_id="ao-ma-20260527-cnf1111", verdict="AGREE"
        )
        vr_paths[tid] = _write_verification_report(out_dir=out_dir, task_id=tid, task_graph_id="ao-ma-20260527-cnf1111")
    decision = Integrator(repo_root=r).integrate(
        manifest_path=manifest_path,
        review_verdict_paths=rv_paths,
        verification_report_paths=vr_paths,
    )
    assert decision.has_conflicts
    assert len(decision.report["conflicts"]) == 1
    assert decision.report["conflicts"][0]["path"] == "src/shared.py"
    # Both workers moved to not_integratable with actual_write_set_overlap
    reasons = [d["reason_code"] for d in decision.report["worker_decisions"]]
    assert reasons.count("actual_write_set_overlap") == 2


# ---------------------------------------------------------------------------
# Trust boundary
# ---------------------------------------------------------------------------


def test_integrate_manifest_envelope_invalid_raises(repo: tuple[Path, str]) -> None:
    r, base_sha = repo
    base_dir = r / ".ao" / "orchestration"
    manifest_path, _ = _write_artifact_set(
        base_dir=base_dir,
        task_graph_id="ao-ma-20260527-mev1111",
        base_sha=base_sha,
        workers=[{"task_id": "task-001", "declared_write_set": ["src/a.py"]}],
    )
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["schema_version"] = "WRONG"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    with pytest.raises(IntegratorError, match="schema_version"):
        Integrator(repo_root=r).integrate(manifest_path=manifest_path)


def test_integrate_runner_report_schema_invalid_raises(repo: tuple[Path, str]) -> None:
    r, base_sha = repo
    base_dir = r / ".ao" / "orchestration"
    manifest_path, out_dir = _write_artifact_set(
        base_dir=base_dir,
        task_graph_id="ao-ma-20260527-rrs1111",
        base_sha=base_sha,
        workers=[{"task_id": "task-001", "declared_write_set": ["src/a.py"]}],
    )
    rr = json.loads((out_dir / "runner_report.v1.json").read_text(encoding="utf-8"))
    rr["conflict_check"] = "totally_invalid"
    (out_dir / "runner_report.v1.json").write_text(json.dumps(rr, indent=2), encoding="utf-8")
    with pytest.raises(IntegratorError, match="failed schema"):
        Integrator(repo_root=r).integrate(manifest_path=manifest_path)


# ---------------------------------------------------------------------------
# assembly_plan structured data
# ---------------------------------------------------------------------------


def test_integrate_emits_assembly_plan_data(repo: tuple[Path, str]) -> None:
    """Codex iter-3 nice-to-have: assembly_plan always written when emit boundary valid."""

    r, base_sha = repo
    base_dir = r / ".ao" / "orchestration"
    manifest_path, out_dir = _write_artifact_set(
        base_dir=base_dir,
        task_graph_id="ao-ma-20260527-asm1111",
        base_sha=base_sha,
        workers=[{"task_id": "task-001", "declared_write_set": ["src/a.py"]}],
    )
    _write_worker_result(
        out_dir=out_dir,
        task_id="task-001",
        task_graph_id="ao-ma-20260527-asm1111",
        base_sha=base_sha,
        declared_write_set=["src/a.py"],
        actual_changed_files=["src/a.py"],
    )
    rv = _write_review_verdict(
        out_dir=out_dir, task_id="task-001", task_graph_id="ao-ma-20260527-asm1111", verdict="AGREE"
    )
    vr = _write_verification_report(out_dir=out_dir, task_id="task-001", task_graph_id="ao-ma-20260527-asm1111")
    decision = Integrator(repo_root=r).integrate(
        manifest_path=manifest_path,
        review_verdict_paths={"task-001": rv},
        verification_report_paths={"task-001": vr},
    )
    assert decision.assembly_plan, "assembly_plan must be non-empty when at least one worker accepted"
    # Every step is data (argv-form, operator_only=true)
    for step in decision.assembly_plan:
        assert isinstance(step["argv"], list)
        assert all(isinstance(x, str) for x in step["argv"])
        assert step["operator_only"] is True
        assert step["side_effect"] in {
            "local_git_merge",
            "remote_pr_create",
            "local_branch_create",
            "local_worktree_remove",
        }


def test_operator_plan_is_data_not_executed(repo: tuple[Path, str]) -> None:
    """No remote/local state change after integrate (no git push/merge/branch/worktree)."""

    r, base_sha = repo
    pre_branches = _run(["git", "-C", str(r), "branch", "-a"])
    manifest_path, out_dir = _write_artifact_set(
        base_dir=r / ".ao" / "orchestration",
        task_graph_id="ao-ma-20260527-pln1111",
        base_sha=base_sha,
        workers=[{"task_id": "task-001", "declared_write_set": ["src/a.py"]}],
    )
    _write_worker_result(
        out_dir=out_dir,
        task_id="task-001",
        task_graph_id="ao-ma-20260527-pln1111",
        base_sha=base_sha,
        declared_write_set=["src/a.py"],
        actual_changed_files=["src/a.py"],
    )
    rv = _write_review_verdict(
        out_dir=out_dir, task_id="task-001", task_graph_id="ao-ma-20260527-pln1111", verdict="AGREE"
    )
    vr = _write_verification_report(out_dir=out_dir, task_id="task-001", task_graph_id="ao-ma-20260527-pln1111")
    Integrator(repo_root=r).integrate(
        manifest_path=manifest_path,
        review_verdict_paths={"task-001": rv},
        verification_report_paths={"task-001": vr},
    )
    post_branches = _run(["git", "-C", str(r), "branch", "-a"])
    assert pre_branches == post_branches, "integrator must not create or delete branches"


# ---------------------------------------------------------------------------
# HARD RULE static pins (AST + text scan)
# ---------------------------------------------------------------------------


def test_integrator_module_has_no_subprocess_import() -> None:
    """Codex iter-2 absorb: integrator.py module must not import subprocess.

    Static AST scan — operator runnable assembly_plan is DATA; integrator never shells out.
    """

    from ao_kernel.orchestration import integrator as integrator_mod

    source = Path(integrator_mod.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert alias.name != "subprocess", "integrator.py must not import subprocess"
        if isinstance(node, ast.ImportFrom):
            assert node.module != "subprocess", "integrator.py must not from-import subprocess"


def test_integrator_module_has_no_gh_or_git_push_literals() -> None:
    """Codex iter-2 absorb: integrator.py source must not contain execute-path literals.

    Schema/docs/test/text renderer scope is fine (data names); only the
    implementation module is checked. assembly_plan items in tests use
    `gh`/`git` as argv DATA strings, not executed.
    """

    from ao_kernel.orchestration import integrator as integrator_mod

    source = Path(integrator_mod.__file__).read_text(encoding="utf-8")
    # The integrator BUILDS assembly_plan steps containing "git", "gh" tokens as
    # data — but it must not CALL subprocess on them. Static check: no
    # `subprocess.run`, no `os.system`, no `os.popen`.
    assert "subprocess.run" not in source, "integrator.py must not call subprocess.run"
    assert "os.system" not in source, "integrator.py must not call os.system"
    assert "os.popen" not in source, "integrator.py must not call os.popen"


# ---------------------------------------------------------------------------
# IntegrationDecision API/CLI split
# ---------------------------------------------------------------------------


def test_integrator_integrate_returns_decision_object_not_raises_for_not_integratable(
    repo: tuple[Path, str],
) -> None:
    """Codex iter-2 absorb: not_integratable / rejected / conflict are normal decision states; no exception."""

    r, base_sha = repo
    manifest_path, _ = _write_artifact_set(
        base_dir=r / ".ao" / "orchestration",
        task_graph_id="ao-ma-20260527-dec1111",
        base_sha=base_sha,
        workers=[{"task_id": "task-001", "declared_write_set": ["src/a.py"]}],
    )
    # NO evidence → not_integratable, but no exception
    decision = Integrator(repo_root=r).integrate(manifest_path=manifest_path)
    assert isinstance(decision, IntegrationDecision)
    assert decision.has_pending
    assert decision.overall_status == "all_blocked"


# ---------------------------------------------------------------------------
# verification_passed predicate (Codex iter-3 must_close #1)
# ---------------------------------------------------------------------------


def test_verification_passed_all_pass() -> None:
    assert verification_passed(
        {
            "failed_checks": [],
            "scope_check": {"passed": True},
            "secret_scan": {"passed": True},
            "commands": [{"command": "pytest", "outcome": "pass"}],
            "guard_flags": {
                "support_widening": False,
                "production_platform_claim": False,
                "live_adapter_execution": False,
            },
        }
    )


def test_verification_passed_skipped_only_predicate_true() -> None:
    """Codex iter-4 nice-to-have absorb: skipped-only commands list is OK
    when the other gates (failed_checks, scope_check, secret_scan, guard_flags) hold."""

    assert verification_passed(
        {
            "failed_checks": [],
            "scope_check": {"passed": True},
            "secret_scan": {"passed": True},
            "commands": [{"command": "lint", "outcome": "skipped"}],
            "guard_flags": {
                "support_widening": False,
                "production_platform_claim": False,
                "live_adapter_execution": False,
            },
        }
    )


def test_verification_passed_fails_when_failed_checks_non_empty() -> None:
    assert not verification_passed(
        {
            "failed_checks": ["scope_violation"],
            "scope_check": {"passed": True},
            "secret_scan": {"passed": True},
            "commands": [],
            "guard_flags": {
                "support_widening": False,
                "production_platform_claim": False,
                "live_adapter_execution": False,
            },
        }
    )


def test_verification_passed_fails_when_scope_check_not_true() -> None:
    assert not verification_passed(
        {
            "failed_checks": [],
            "scope_check": {"passed": False},
            "secret_scan": {"passed": True},
            "commands": [],
            "guard_flags": {
                "support_widening": False,
                "production_platform_claim": False,
                "live_adapter_execution": False,
            },
        }
    )


def test_verification_passed_fails_when_secret_scan_not_true() -> None:
    assert not verification_passed(
        {
            "failed_checks": [],
            "scope_check": {"passed": True},
            "secret_scan": {"passed": False},
            "commands": [],
            "guard_flags": {
                "support_widening": False,
                "production_platform_claim": False,
                "live_adapter_execution": False,
            },
        }
    )


def test_verification_passed_fails_when_any_command_outcome_fail() -> None:
    assert not verification_passed(
        {
            "failed_checks": [],
            "scope_check": {"passed": True},
            "secret_scan": {"passed": True},
            "commands": [{"command": "pytest", "outcome": "fail"}],
            "guard_flags": {
                "support_widening": False,
                "production_platform_claim": False,
                "live_adapter_execution": False,
            },
        }
    )


def test_verification_passed_fails_when_guard_flag_open() -> None:
    assert not verification_passed(
        {
            "failed_checks": [],
            "scope_check": {"passed": True},
            "secret_scan": {"passed": True},
            "commands": [],
            "guard_flags": {
                "support_widening": True,
                "production_platform_claim": False,
                "live_adapter_execution": False,
            },
        }
    )


# ---------------------------------------------------------------------------
# worker_result_ref null sentinel (Codex iter-3 must_close #2)
# ---------------------------------------------------------------------------


def test_worker_result_ref_is_null_when_missing(repo: tuple[Path, str]) -> None:
    r, base_sha = repo
    manifest_path, _ = _write_artifact_set(
        base_dir=r / ".ao" / "orchestration",
        task_graph_id="ao-ma-20260527-nul1111",
        base_sha=base_sha,
        workers=[{"task_id": "task-001", "declared_write_set": ["src/a.py"]}],
    )
    decision = Integrator(repo_root=r).integrate(manifest_path=manifest_path)
    wd = decision.report["worker_decisions"][0]
    assert wd["worker_result_ref"] is None, "worker_result_ref must be null (not string 'missing')"


# ---------------------------------------------------------------------------
# render_assembly_plan_text
# ---------------------------------------------------------------------------


def test_render_assembly_plan_text_includes_argv_strings() -> None:
    plan = [
        {
            "argv": ["git", "checkout", "-b", "codex/test/integration", "origin/main"],
            "operator_only": True,
            "side_effect": "local_branch_create",
            "note": "Create integrator branch",
        },
        {
            "argv": ["git", "merge", "--no-ff", "codex/test/task-001"],
            "operator_only": True,
            "side_effect": "local_git_merge",
        },
    ]
    text = render_assembly_plan_text(plan)
    assert "git checkout -b codex/test/integration origin/main" in text
    assert "git merge --no-ff codex/test/task-001" in text
    assert "operator-runnable" in text


def test_render_assembly_plan_text_empty() -> None:
    text = render_assembly_plan_text([])
    assert "no accepted workers" in text


# ---------------------------------------------------------------------------
# CLI integration tests
# ---------------------------------------------------------------------------


def test_cli_integrate_happy_path_exits_zero(repo: tuple[Path, str], capsys: pytest.CaptureFixture[str]) -> None:
    from ao_kernel.cli import main as cli_main

    r, base_sha = repo
    manifest_path, out_dir = _write_artifact_set(
        base_dir=r / ".ao" / "orchestration",
        task_graph_id="ao-ma-20260527-cli0001",
        base_sha=base_sha,
        workers=[{"task_id": "task-001", "declared_write_set": ["src/a.py"]}],
    )
    _write_worker_result(
        out_dir=out_dir,
        task_id="task-001",
        task_graph_id="ao-ma-20260527-cli0001",
        base_sha=base_sha,
        declared_write_set=["src/a.py"],
        actual_changed_files=["src/a.py"],
    )
    rv = _write_review_verdict(
        out_dir=out_dir, task_id="task-001", task_graph_id="ao-ma-20260527-cli0001", verdict="AGREE"
    )
    vr = _write_verification_report(out_dir=out_dir, task_id="task-001", task_graph_id="ao-ma-20260527-cli0001")
    rc = cli_main(
        [
            "orchestration",
            "integrate",
            "--manifest",
            str(manifest_path),
            "--repo-root",
            str(r),
            "--review-verdict",
            f"task-001={rv}",
            "--verification-report",
            f"task-001={vr}",
            "--format",
            "json",
        ]
    )
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["overall_status"] == "all_accepted"


def test_cli_integrate_pending_exits_one(repo: tuple[Path, str], capsys: pytest.CaptureFixture[str]) -> None:
    from ao_kernel.cli import main as cli_main

    r, base_sha = repo
    manifest_path, _ = _write_artifact_set(
        base_dir=r / ".ao" / "orchestration",
        task_graph_id="ao-ma-20260527-cli0002",
        base_sha=base_sha,
        workers=[{"task_id": "task-001", "declared_write_set": ["src/a.py"]}],
    )
    rc = cli_main(
        [
            "orchestration",
            "integrate",
            "--manifest",
            str(manifest_path),
            "--repo-root",
            str(r),
            "--format",
            "json",
        ]
    )
    assert rc == 1
    out = json.loads(capsys.readouterr().out)
    assert out["has_pending"] is True


def test_cli_integrate_missing_manifest_exits_two(repo: tuple[Path, str], capsys: pytest.CaptureFixture[str]) -> None:
    from ao_kernel.cli import main as cli_main

    r, _ = repo
    rc = cli_main(
        [
            "orchestration",
            "integrate",
            "--manifest",
            str(r / "does_not_exist.json"),
            "--repo-root",
            str(r),
        ]
    )
    assert rc == 2
    err = capsys.readouterr().err
    assert "manifest not found" in err


def test_cli_integrate_malformed_per_task_path_arg_exits_systemexit(
    repo: tuple[Path, str], capsys: pytest.CaptureFixture[str]
) -> None:
    """SystemExit (operator CLI error) when --review-verdict missing '=' separator."""

    from ao_kernel.cli import main as cli_main

    r, base_sha = repo
    manifest_path, _ = _write_artifact_set(
        base_dir=r / ".ao" / "orchestration",
        task_graph_id="ao-ma-20260527-cli0003",
        base_sha=base_sha,
        workers=[{"task_id": "task-001", "declared_write_set": ["src/a.py"]}],
    )
    with pytest.raises(SystemExit, match="review-verdict"):
        cli_main(
            [
                "orchestration",
                "integrate",
                "--manifest",
                str(manifest_path),
                "--repo-root",
                str(r),
                "--review-verdict",
                "BAD_NO_EQUALS_SIGN",
            ]
        )


# ---------------------------------------------------------------------------
# Codex iter-5 absorb tests (cross-ref binding + _relativize fail-closed +
# no_workers fail-closed + CLI exit 3 contract)
# ---------------------------------------------------------------------------


def test_integrate_rejects_split_brain_task_graph_id(repo: tuple[Path, str]) -> None:
    """Codex iter-5 HIGH-1: task_graph.task_graph_id != manifest.task_graph_id → IntegratorError exit 2."""

    r, base_sha = repo
    base_dir = r / ".ao" / "orchestration"
    manifest_path, out_dir = _write_artifact_set(
        base_dir=base_dir,
        task_graph_id="ao-ma-20260527-spl1111",
        base_sha=base_sha,
        workers=[{"task_id": "task-001", "declared_write_set": ["src/a.py"]}],
    )
    # Tamper task_graph.task_graph_id (manifest still says ao-ma-20260527-spl1111)
    tg_path = out_dir / "task_graph.v1.json"
    tg = json.loads(tg_path.read_text(encoding="utf-8"))
    tg["task_graph_id"] = "ao-ma-20260527-other11"
    tg_path.write_text(json.dumps(tg, indent=2), encoding="utf-8")
    with pytest.raises(IntegratorError, match="split-brain artifact set"):
        Integrator(repo_root=r).integrate(manifest_path=manifest_path)


def test_integrate_rejects_split_brain_runner_report_task_graph_id(repo: tuple[Path, str]) -> None:
    """Codex iter-5 HIGH-1: runner_report.task_graph_id != manifest.task_graph_id."""

    r, base_sha = repo
    base_dir = r / ".ao" / "orchestration"
    manifest_path, out_dir = _write_artifact_set(
        base_dir=base_dir,
        task_graph_id="ao-ma-20260527-rsb1111",
        base_sha=base_sha,
        workers=[{"task_id": "task-001", "declared_write_set": ["src/a.py"]}],
    )
    rr_path = out_dir / "runner_report.v1.json"
    rr = json.loads(rr_path.read_text(encoding="utf-8"))
    rr["task_graph_id"] = "ao-ma-20260527-other22"
    rr_path.write_text(json.dumps(rr, indent=2), encoding="utf-8")
    with pytest.raises(IntegratorError, match="task_graph_id"):
        Integrator(repo_root=r).integrate(manifest_path=manifest_path)


def test_integrate_rejects_runner_report_manifest_sha256_mismatch(repo: tuple[Path, str]) -> None:
    """Codex iter-5 HIGH-1: runner_report.manifest_sha256 != sha256_of(manifest_path)."""

    r, base_sha = repo
    base_dir = r / ".ao" / "orchestration"
    manifest_path, out_dir = _write_artifact_set(
        base_dir=base_dir,
        task_graph_id="ao-ma-20260527-msm1111",
        base_sha=base_sha,
        workers=[{"task_id": "task-001", "declared_write_set": ["src/a.py"]}],
    )
    rr_path = out_dir / "runner_report.v1.json"
    rr = json.loads(rr_path.read_text(encoding="utf-8"))
    rr["manifest_sha256"] = "sha256:" + "0" * 64
    rr_path.write_text(json.dumps(rr, indent=2), encoding="utf-8")
    with pytest.raises(IntegratorError, match="manifest_sha256"):
        Integrator(repo_root=r).integrate(manifest_path=manifest_path)


def test_integrate_rejects_runner_report_base_sha_mismatch(repo: tuple[Path, str]) -> None:
    """Codex iter-5 HIGH-1: runner_report.base_sha != task_graph.base_sha."""

    r, base_sha = repo
    base_dir = r / ".ao" / "orchestration"
    manifest_path, out_dir = _write_artifact_set(
        base_dir=base_dir,
        task_graph_id="ao-ma-20260527-bsm1111",
        base_sha=base_sha,
        workers=[{"task_id": "task-001", "declared_write_set": ["src/a.py"]}],
    )
    rr_path = out_dir / "runner_report.v1.json"
    rr = json.loads(rr_path.read_text(encoding="utf-8"))
    rr["base_sha"] = "f" * 40
    rr_path.write_text(json.dumps(rr, indent=2), encoding="utf-8")
    with pytest.raises(IntegratorError, match="base_sha"):
        Integrator(repo_root=r).integrate(manifest_path=manifest_path)


def test_integrate_rejects_worker_result_with_wrong_task_id(repo: tuple[Path, str]) -> None:
    """Codex iter-5 HIGH-1: worker_result.task_id != runner_report worker.task_id."""

    r, base_sha = repo
    base_dir = r / ".ao" / "orchestration"
    manifest_path, out_dir = _write_artifact_set(
        base_dir=base_dir,
        task_graph_id="ao-ma-20260527-wti1111",
        base_sha=base_sha,
        workers=[{"task_id": "task-001", "declared_write_set": ["src/a.py"]}],
    )
    # Write worker_result with WRONG task_id
    _write_worker_result(
        out_dir=out_dir,
        task_id="task-001",
        task_graph_id="ao-ma-20260527-wti1111",
        base_sha=base_sha,
        declared_write_set=["src/a.py"],
        actual_changed_files=["src/a.py"],
    )
    wr_path = out_dir / "workers/task-001/worker_result.v1.json"
    payload = json.loads(wr_path.read_text(encoding="utf-8"))
    payload["task_id"] = "task-999"  # mismatch
    wr_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    decision = Integrator(repo_root=r).integrate(manifest_path=manifest_path)
    assert decision.has_rejections
    assert decision.report["worker_decisions"][0]["reason_code"] == "schema_invalid"


def test_integrate_rejects_review_verdict_with_wrong_reviewed_task_id(repo: tuple[Path, str]) -> None:
    """Codex iter-5 HIGH-1: review.reviewed_task_id != runner_report worker.task_id."""

    r, base_sha = repo
    base_dir = r / ".ao" / "orchestration"
    manifest_path, out_dir = _write_artifact_set(
        base_dir=base_dir,
        task_graph_id="ao-ma-20260527-rti1111",
        base_sha=base_sha,
        workers=[{"task_id": "task-001", "declared_write_set": ["src/a.py"]}],
    )
    _write_worker_result(
        out_dir=out_dir,
        task_id="task-001",
        task_graph_id="ao-ma-20260527-rti1111",
        base_sha=base_sha,
        declared_write_set=["src/a.py"],
        actual_changed_files=["src/a.py"],
    )
    rv_path = _write_review_verdict(
        out_dir=out_dir, task_id="task-001", task_graph_id="ao-ma-20260527-rti1111", verdict="AGREE"
    )
    # Tamper reviewed_task_id
    rv = json.loads(rv_path.read_text(encoding="utf-8"))
    rv["reviewed_task_id"] = "task-999"
    rv_path.write_text(json.dumps(rv, indent=2), encoding="utf-8")
    decision = Integrator(repo_root=r).integrate(
        manifest_path=manifest_path,
        review_verdict_paths={"task-001": rv_path},
    )
    assert decision.has_rejections
    assert decision.report["worker_decisions"][0]["reason_code"] == "schema_invalid"


def test_integrate_rejects_verification_missing_task_in_verified_task_ids(repo: tuple[Path, str]) -> None:
    """Codex iter-5 HIGH-1: task_id not in verification_report.verified_task_ids."""

    r, base_sha = repo
    base_dir = r / ".ao" / "orchestration"
    manifest_path, out_dir = _write_artifact_set(
        base_dir=base_dir,
        task_graph_id="ao-ma-20260527-vti1111",
        base_sha=base_sha,
        workers=[{"task_id": "task-001", "declared_write_set": ["src/a.py"]}],
    )
    _write_worker_result(
        out_dir=out_dir,
        task_id="task-001",
        task_graph_id="ao-ma-20260527-vti1111",
        base_sha=base_sha,
        declared_write_set=["src/a.py"],
        actual_changed_files=["src/a.py"],
    )
    rv_path = _write_review_verdict(
        out_dir=out_dir, task_id="task-001", task_graph_id="ao-ma-20260527-vti1111", verdict="AGREE"
    )
    vr_path = _write_verification_report(out_dir=out_dir, task_id="task-001", task_graph_id="ao-ma-20260527-vti1111")
    # Tamper verified_task_ids
    vr = json.loads(vr_path.read_text(encoding="utf-8"))
    vr["verified_task_ids"] = ["task-999"]
    vr_path.write_text(json.dumps(vr, indent=2), encoding="utf-8")
    decision = Integrator(repo_root=r).integrate(
        manifest_path=manifest_path,
        review_verdict_paths={"task-001": rv_path},
        verification_report_paths={"task-001": vr_path},
    )
    assert decision.has_rejections
    assert decision.report["worker_decisions"][0]["reason_code"] == "schema_invalid"


def test_integrate_empty_runner_report_workers_raises(repo: tuple[Path, str], tmp_path: Path) -> None:
    """Codex iter-5 MEDIUM: empty runner_report.workers → IntegratorError → exit 2 (no emit)."""

    r, base_sha = repo
    base_dir = r / ".ao" / "orchestration"
    # Manually craft manifest + empty runner_report (the fixture requires ≥1 worker)
    out_dir = base_dir / "ao-ma-20260527-emp1111"
    out_dir.mkdir(parents=True, exist_ok=True)
    task_graph = {
        "schema_version": "ao-ma-task-graph.v1",
        "task_graph_id": "ao-ma-20260527-emp1111",
        "repo": "Halildeu/ao-kernel",
        "goal": "empty workers fixture",
        "base_ref": "refs/heads/main",
        "base_sha": base_sha,
        "risk_class": "low",
        "max_parallel_workers": 1,
        "tasks": [
            {
                "task_id": "stub",
                "title": "stub",
                "agent_type": "implementer",
                "declared_write_set": ["src/a.py"],
                "dependency_ids": [],
                "acceptance_criteria": ["tests_pass_locally"],
                "high_risk": False,
            }
        ],
        "fan_in_policy": {"mode": "all_required", "required_task_ids": ["stub"], "conflict_owner": "integrator"},
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
    tg_path = out_dir / "task_graph.v1.json"
    tg_path.write_text(json.dumps(task_graph, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    manifest = {
        "schema_version": "ao-ma-orchestration-manifest.v1",
        "task_graph_id": "ao-ma-20260527-emp1111",
        "generated_at": "2026-05-27T00:00:00Z",
        "base_dir": str(out_dir),
        "artifacts": [
            {
                "path": "task_graph.v1.json",
                "sha256": _sha256(tg_path),
                "size_bytes": tg_path.stat().st_size,
            }
        ],
        "guard_flags": {
            "support_widening": False,
            "production_platform_claim": False,
            "live_adapter_execution": False,
        },
    }
    manifest_path = out_dir / "manifest.v1.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    runner_report = {
        "schema_version": "ao-ma-runner-report.v1",
        "task_graph_id": "ao-ma-20260527-emp1111",
        "manifest_sha256": _sha256(manifest_path),
        "base_sha": base_sha,
        "generated_at": "2026-05-27T00:00:00Z",
        "conflict_check": "pass",
        "base_sync_check": "pass",
        "workers": [],  # EMPTY
        "guard_flags": {
            "support_widening": False,
            "production_platform_claim": False,
            "live_adapter_execution": False,
        },
    }
    rr_path = out_dir / "runner_report.v1.json"
    rr_path.write_text(json.dumps(runner_report, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    with pytest.raises(IntegratorError, match="no worker entries"):
        Integrator(repo_root=r).integrate(manifest_path=manifest_path)
    # Confirm NO integration_report was written
    assert not (out_dir / "integration_report.v1.json").exists()


def test_relativize_path_outside_base_dir_raises_integrator_error(repo: tuple[Path, str], tmp_path: Path) -> None:
    """Codex iter-5 HIGH-2: _relativize fail-closed when path outside base_dir."""

    from ao_kernel.orchestration.integrator import _relativize

    base_dir = tmp_path / "base"
    base_dir.mkdir()
    # An absolute path OUTSIDE base_dir → should raise IntegratorError
    outside = tmp_path / "elsewhere" / "worker_result.v1.json"
    with pytest.raises(IntegratorError, match="outside the integration artifact base"):
        _relativize(str(outside), base_dir)


def test_relativize_preserves_none_sentinel(tmp_path: Path) -> None:
    """_relativize(None, ...) returns None (worker_result_ref null sentinel preserved)."""

    from ao_kernel.orchestration.integrator import _relativize

    assert _relativize(None, tmp_path) is None


def test_integrate_rejects_runner_status_failed_branch_exists_mismatch(repo: tuple[Path, str]) -> None:
    """Codex iter-6 must_fix: runner worker status outside allowlist → IntegratorError exit 2.

    AO-MA-4 preparation truth: failed_* statuses mean the worker was NOT
    successfully prepared. The accept gate must not bypass that.
    """

    r, base_sha = repo
    base_dir = r / ".ao" / "orchestration"
    manifest_path, out_dir = _write_artifact_set(
        base_dir=base_dir,
        task_graph_id="ao-ma-20260527-rsf1111",
        base_sha=base_sha,
        workers=[{"task_id": "task-001", "declared_write_set": ["src/a.py"]}],
    )
    rr_path = out_dir / "runner_report.v1.json"
    rr = json.loads(rr_path.read_text(encoding="utf-8"))
    rr["workers"][0]["status"] = "failed_branch_exists_mismatch"
    rr_path.write_text(json.dumps(rr, indent=2), encoding="utf-8")
    with pytest.raises(IntegratorError, match="integrate-eligible"):
        Integrator(repo_root=r).integrate(manifest_path=manifest_path)
    # NO integration_report emitted
    assert not (out_dir / "integration_report.v1.json").exists()


def test_integrate_rejects_runner_status_skipped_dry_run(repo: tuple[Path, str]) -> None:
    """Codex iter-6 must_fix: skipped_dry_run runner workers must NOT integrate-eligible."""

    r, base_sha = repo
    base_dir = r / ".ao" / "orchestration"
    manifest_path, out_dir = _write_artifact_set(
        base_dir=base_dir,
        task_graph_id="ao-ma-20260527-sdr1111",
        base_sha=base_sha,
        workers=[{"task_id": "task-001", "declared_write_set": ["src/a.py"]}],
    )
    rr_path = out_dir / "runner_report.v1.json"
    rr = json.loads(rr_path.read_text(encoding="utf-8"))
    rr["workers"][0]["status"] = "skipped_dry_run"
    rr_path.write_text(json.dumps(rr, indent=2), encoding="utf-8")
    with pytest.raises(IntegratorError, match="integrate-eligible"):
        Integrator(repo_root=r).integrate(manifest_path=manifest_path)


def test_integrate_accepts_runner_status_skipped_existing_idempotent(repo: tuple[Path, str]) -> None:
    """Codex iter-6 must_fix: skipped_existing_idempotent IS integrate-eligible.

    AO-MA-4 semantic: worker already prepared on disk at the correct branch+HEAD;
    AO-MA-5 can integrate as if it were freshly prepared.
    """

    r, base_sha = repo
    base_dir = r / ".ao" / "orchestration"
    manifest_path, out_dir = _write_artifact_set(
        base_dir=base_dir,
        task_graph_id="ao-ma-20260527-sei1111",
        base_sha=base_sha,
        workers=[{"task_id": "task-001", "declared_write_set": ["src/a.py"]}],
    )
    rr_path = out_dir / "runner_report.v1.json"
    rr = json.loads(rr_path.read_text(encoding="utf-8"))
    rr["workers"][0]["status"] = "skipped_existing_idempotent"
    rr_path.write_text(json.dumps(rr, indent=2), encoding="utf-8")
    _write_worker_result(
        out_dir=out_dir,
        task_id="task-001",
        task_graph_id="ao-ma-20260527-sei1111",
        base_sha=base_sha,
        declared_write_set=["src/a.py"],
        actual_changed_files=["src/a.py"],
    )
    rv = _write_review_verdict(
        out_dir=out_dir, task_id="task-001", task_graph_id="ao-ma-20260527-sei1111", verdict="AGREE"
    )
    vr = _write_verification_report(out_dir=out_dir, task_id="task-001", task_graph_id="ao-ma-20260527-sei1111")
    decision = Integrator(repo_root=r).integrate(
        manifest_path=manifest_path,
        review_verdict_paths={"task-001": rv},
        verification_report_paths={"task-001": vr},
    )
    assert decision.overall_status == "all_accepted", decision.diagnostics


def test_cli_integrate_emit_failure_exits_three(
    repo: tuple[Path, str], capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Codex iter-5 nice-to-have: CLI exit 3 contract for integration emit failure."""

    from ao_kernel.cli import main as cli_main
    from ao_kernel.orchestration import integration_report_writer as writer_mod

    r, base_sha = repo
    manifest_path, out_dir = _write_artifact_set(
        base_dir=r / ".ao" / "orchestration",
        task_graph_id="ao-ma-20260527-emt1111",
        base_sha=base_sha,
        workers=[{"task_id": "task-001", "declared_write_set": ["src/a.py"]}],
    )
    _write_worker_result(
        out_dir=out_dir,
        task_id="task-001",
        task_graph_id="ao-ma-20260527-emt1111",
        base_sha=base_sha,
        declared_write_set=["src/a.py"],
        actual_changed_files=["src/a.py"],
    )
    rv = _write_review_verdict(
        out_dir=out_dir, task_id="task-001", task_graph_id="ao-ma-20260527-emt1111", verdict="AGREE"
    )
    vr = _write_verification_report(out_dir=out_dir, task_id="task-001", task_graph_id="ao-ma-20260527-emt1111")

    # Force the writer to fail by monkey-patching emit to raise
    def _boom(self, **kwargs):  # noqa: ANN001
        raise writer_mod.IntegrationReportWriterError("simulated emit failure")

    monkeypatch.setattr(writer_mod.IntegrationReportWriter, "emit", _boom)
    rc = cli_main(
        [
            "orchestration",
            "integrate",
            "--manifest",
            str(manifest_path),
            "--repo-root",
            str(r),
            "--review-verdict",
            f"task-001={rv}",
            "--verification-report",
            f"task-001={vr}",
            "--format",
            "json",
        ]
    )
    assert rc == 3, "emit failure must exit 3 per Codex iter-2 §5 matrix"
    err = capsys.readouterr().err
    assert "emit failure" in err
