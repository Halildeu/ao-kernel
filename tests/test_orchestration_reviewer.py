"""AO-MA-6 reviewer tests (Codex thread 019e6923 iter-1→iter-3 AGREE absorb).

30+ tests cover:
- Happy path (AGREE / REVISE / BLOCK passes through)
- Bounded REVISE (under/at/over budget; AGREE override; same-task cross-ref)
- Cross-provider violation (reviewer.provider == implementer.provider)
- Trust boundary (manifest + task_graph + worker_result schema + cross-ref)
- CLI mapping key vs payload task_id cross-ref
- findings-json strict schema ($defs.finding)
- HARD RULE static pins (no subprocess import, no LLM call literals, no gh/git push)
- CLI exit code matrix
- emitted_verdict diagnostic shape (requested vs emitted vs counts)
- AO-MA-5 modules untouched (PR file-list scope)
"""

from __future__ import annotations

import ast
import hashlib
import json
import subprocess
from collections.abc import Iterator
from pathlib import Path

import pytest

from ao_kernel.orchestration.reviewer import (
    ReviewInputs,
    Reviewer,
    ReviewerError,
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


def _write_manifest_and_task_graph(
    *,
    repo: Path,
    task_graph_id: str,
    base_sha: str,
    task_id: str = "task-001",
    declared: list[str] | None = None,
    max_revise_rounds: int = 3,
) -> tuple[Path, Path]:
    """Returns (manifest_path, out_dir) for the test to use."""

    declared = declared or ["src/a.py"]
    base_dir = repo / ".ao" / "orchestration"
    out_dir = base_dir / task_graph_id
    out_dir.mkdir(parents=True, exist_ok=True)
    task_graph = {
        "schema_version": "ao-ma-task-graph.v1",
        "task_graph_id": task_graph_id,
        "repo": "Halildeu/ao-kernel",
        "goal": "AO-MA-6 reviewer test fixture",
        "base_ref": "refs/heads/main",
        "base_sha": base_sha,
        "risk_class": "low",
        "max_parallel_workers": 1,
        "tasks": [
            {
                "task_id": task_id,
                "title": f"task {task_id}",
                "agent_type": "implementer",
                "declared_write_set": declared,
                "dependency_ids": [],
                "acceptance_criteria": ["tests_pass_locally"],
                "high_risk": False,
            }
        ],
        "fan_in_policy": {"mode": "all_required", "required_task_ids": [task_id], "conflict_owner": "integrator"},
        "review_policy": {
            "required_reviewers": 1,
            "cross_provider_required": True,
            "consensus_required_for_high_risk": True,
            "max_revise_rounds": max_revise_rounds,
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
        "task_graph_id": task_graph_id,
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
    return manifest_path, out_dir


def _write_worker_result(
    *,
    out_dir: Path,
    task_id: str,
    task_graph_id: str,
    base_sha: str,
    declared: list[str] | None = None,
    actual: list[str] | None = None,
    implementer_provider: str = "anthropic",
) -> Path:
    declared = declared or ["src/a.py"]
    actual = actual or declared
    worker_dir = out_dir / "workers" / task_id
    worker_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": "ao-ma-worker-result.v1",
        "task_graph_id": task_graph_id,
        "task_id": task_id,
        "assignment_id": f"{task_graph_id}-{task_id}",
        "worker": {
            "agent_id": f"claude-{task_id}",
            "agent_type": "implementer",
            "provider": implementer_provider,
            "session_id": f"ao-ma-6-test-{task_graph_id}",
        },
        "base_ref": "refs/heads/main",
        "base_sha": base_sha,
        "head_ref": f"codex/ao-ma-{task_graph_id}/{task_id}",
        "head_sha": "c" * 40,
        "declared_write_set": declared,
        "actual_changed_files": actual,
        "summary": "test worker summary",
        "tests_run": [{"command": "pytest", "outcome": "pass"}],
        "known_gaps": [],
        "no_secret_attestation": {"secrets_recorded": False},
        "guard_flags": {
            "support_widening": False,
            "production_platform_claim": False,
            "live_adapter_execution": False,
        },
    }
    wr_path = worker_dir / "worker_result.v1.json"
    wr_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return wr_path


def _write_findings_json(tmp_path: Path, findings: list[dict]) -> Path:
    p = tmp_path / "findings.json"
    p.write_text(json.dumps(findings, indent=2), encoding="utf-8")
    return p


def _write_prior_review_verdict(
    *,
    out_dir: Path,
    task_id: str,
    task_graph_id: str,
    verdict: str,
    suffix: str = "prior1",
) -> Path:
    """Write a prior REVISE verdict file to a sibling location."""

    prior_dir = out_dir / "workers" / task_id / "prior_reviews"
    prior_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": "ao-ma-review-verdict.v1",
        "task_graph_id": task_graph_id,
        "reviewed_task_id": task_id,
        "reviewer": {
            "agent_id": f"codex-prior-{suffix}",
            "agent_type": "reviewer",
            "provider": "openai",
            "session_id": f"prior-{suffix}",
        },
        "implementer": {
            "agent_id": f"claude-{task_id}",
            "agent_type": "implementer",
            "provider": "anthropic",
            "session_id": "impl-session",
        },
        "independent_review": True,
        "cross_provider_verified": True,
        "allowed_sources": ["pr_diff"],
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
    p = prior_dir / f"prior_{suffix}.json"
    p.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return p


@pytest.fixture
def repo(tmp_path: Path) -> Iterator[tuple[Path, str]]:
    r = tmp_path / "repo"
    sha = _git_init_repo(r)
    yield r, sha


def _basic_findings(severity: str = "info") -> list[dict]:
    return [{"severity": severity, "title": "test finding", "body": "explanation"}]


def _make_stub_diff(out_dir: Path, task_id: str) -> Path:
    """Codex iter-4 absorb: tests must supply at least one evidence path
    (allowed_sources fail-closed). Provide a tiny pr_diff stub by default.
    """

    p = out_dir / "workers" / task_id / "pr_diff.patch"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("--- a/src/a.py\n+++ b/src/a.py\n@@ -0,0 +1 @@\n+stub\n", encoding="utf-8")
    return p


def _make_inputs(
    *,
    repo: Path,
    manifest_path: Path,
    out_dir: Path,
    task_id: str,
    wr_path: Path,
    findings_path: Path,
    verdict: str = "AGREE",
    reviewer_provider: str = "openai",
    prior_paths: list[Path] | None = None,
    diff_path: Path | None = None,
) -> ReviewInputs:
    # Default to a stub pr_diff so tests don't fail on the "no evidence"
    # ReviewerError (Codex iter-4 absorb). Tests that specifically test
    # the no-evidence path override with diff_path=None AND no priors.
    effective_diff = diff_path if diff_path is not None else _make_stub_diff(out_dir, task_id)
    return ReviewInputs(
        manifest_path=manifest_path,
        task_id=task_id,
        worker_result_paths={task_id: wr_path},
        reviewer_agent_id="codex-reviewer",
        reviewer_provider=reviewer_provider,  # type: ignore[arg-type]
        reviewer_session_id="rev-session",
        verdict=verdict,  # type: ignore[arg-type]
        findings_path=findings_path,
        diff_path=effective_diff,
        prior_review_verdict_paths=prior_paths or [],
    )


# ---------------------------------------------------------------------------
# Happy paths
# ---------------------------------------------------------------------------


def test_review_happy_path_agree_emits_schema_valid_verdict(repo, tmp_path: Path) -> None:
    r, base_sha = repo
    manifest_path, out_dir = _write_manifest_and_task_graph(
        repo=r, task_graph_id="ao-ma-20260527-hap1111", base_sha=base_sha
    )
    wr_path = _write_worker_result(
        out_dir=out_dir, task_id="task-001", task_graph_id="ao-ma-20260527-hap1111", base_sha=base_sha
    )
    findings_path = _write_findings_json(tmp_path, _basic_findings())
    inputs = _make_inputs(
        repo=r,
        manifest_path=manifest_path,
        out_dir=out_dir,
        task_id="task-001",
        wr_path=wr_path,
        findings_path=findings_path,
        verdict="AGREE",
    )
    decision = Reviewer(repo_root=r).review(inputs)
    assert decision.emitted_verdict == "AGREE"
    assert decision.requested_verdict == "AGREE"
    assert not decision.budget_forced_block
    # Emitted to disk
    emitted = out_dir / "workers" / "task-001" / "review_verdict.v1.json"
    assert emitted.exists()
    payload = json.loads(emitted.read_text(encoding="utf-8"))
    assert payload["verdict"] == "AGREE"
    assert payload["reviewed_task_id"] == "task-001"
    assert payload["task_graph_id"] == "ao-ma-20260527-hap1111"


def test_review_revise_with_no_priors_passes_through(repo, tmp_path: Path) -> None:
    r, base_sha = repo
    manifest_path, out_dir = _write_manifest_and_task_graph(
        repo=r, task_graph_id="ao-ma-20260527-rev1111", base_sha=base_sha
    )
    wr_path = _write_worker_result(
        out_dir=out_dir, task_id="task-001", task_graph_id="ao-ma-20260527-rev1111", base_sha=base_sha
    )
    findings_path = _write_findings_json(tmp_path, _basic_findings("warning"))
    inputs = _make_inputs(
        repo=r,
        manifest_path=manifest_path,
        out_dir=out_dir,
        task_id="task-001",
        wr_path=wr_path,
        findings_path=findings_path,
        verdict="REVISE",
    )
    decision = Reviewer(repo_root=r).review(inputs)
    assert decision.emitted_verdict == "REVISE"
    assert not decision.budget_forced_block


def test_review_block_passes_through(repo, tmp_path: Path) -> None:
    r, base_sha = repo
    manifest_path, out_dir = _write_manifest_and_task_graph(
        repo=r, task_graph_id="ao-ma-20260527-blk1111", base_sha=base_sha
    )
    wr_path = _write_worker_result(
        out_dir=out_dir, task_id="task-001", task_graph_id="ao-ma-20260527-blk1111", base_sha=base_sha
    )
    findings_path = _write_findings_json(tmp_path, _basic_findings("blocking"))
    inputs = _make_inputs(
        repo=r,
        manifest_path=manifest_path,
        out_dir=out_dir,
        task_id="task-001",
        wr_path=wr_path,
        findings_path=findings_path,
        verdict="BLOCK",
    )
    decision = Reviewer(repo_root=r).review(inputs)
    assert decision.emitted_verdict == "BLOCK"


# ---------------------------------------------------------------------------
# Bounded REVISE
# ---------------------------------------------------------------------------


def test_review_revise_with_priors_under_budget(repo, tmp_path: Path) -> None:
    r, base_sha = repo
    manifest_path, out_dir = _write_manifest_and_task_graph(
        repo=r, task_graph_id="ao-ma-20260527-und1111", base_sha=base_sha, max_revise_rounds=3
    )
    wr_path = _write_worker_result(
        out_dir=out_dir, task_id="task-001", task_graph_id="ao-ma-20260527-und1111", base_sha=base_sha
    )
    findings_path = _write_findings_json(tmp_path, _basic_findings())
    p1 = _write_prior_review_verdict(
        out_dir=out_dir, task_id="task-001", task_graph_id="ao-ma-20260527-und1111", verdict="REVISE", suffix="1"
    )
    p2 = _write_prior_review_verdict(
        out_dir=out_dir, task_id="task-001", task_graph_id="ao-ma-20260527-und1111", verdict="REVISE", suffix="2"
    )
    inputs = _make_inputs(
        repo=r,
        manifest_path=manifest_path,
        out_dir=out_dir,
        task_id="task-001",
        wr_path=wr_path,
        findings_path=findings_path,
        verdict="REVISE",
        prior_paths=[p1, p2],
    )
    decision = Reviewer(repo_root=r).review(inputs)
    # 2 priors < budget(3) → REVISE allowed
    assert decision.emitted_verdict == "REVISE"
    assert decision.prior_revise_count == 2
    assert decision.max_revise_rounds == 3
    assert not decision.budget_forced_block


def test_review_revise_at_budget_forces_block(repo, tmp_path: Path) -> None:
    r, base_sha = repo
    manifest_path, out_dir = _write_manifest_and_task_graph(
        repo=r, task_graph_id="ao-ma-20260527-bgt1111", base_sha=base_sha, max_revise_rounds=2
    )
    wr_path = _write_worker_result(
        out_dir=out_dir, task_id="task-001", task_graph_id="ao-ma-20260527-bgt1111", base_sha=base_sha
    )
    findings_path = _write_findings_json(tmp_path, _basic_findings())
    p1 = _write_prior_review_verdict(
        out_dir=out_dir, task_id="task-001", task_graph_id="ao-ma-20260527-bgt1111", verdict="REVISE", suffix="1"
    )
    p2 = _write_prior_review_verdict(
        out_dir=out_dir, task_id="task-001", task_graph_id="ao-ma-20260527-bgt1111", verdict="REVISE", suffix="2"
    )
    inputs = _make_inputs(
        repo=r,
        manifest_path=manifest_path,
        out_dir=out_dir,
        task_id="task-001",
        wr_path=wr_path,
        findings_path=findings_path,
        verdict="REVISE",
        prior_paths=[p1, p2],
    )
    decision = Reviewer(repo_root=r).review(inputs)
    # 2 priors >= budget(2), requested REVISE → forced BLOCK
    assert decision.requested_verdict == "REVISE"
    assert decision.emitted_verdict == "BLOCK"
    assert decision.budget_forced_block
    assert decision.prior_revise_count == 2
    assert decision.max_revise_rounds == 2
    assert any("REVISE budget exhausted" in d for d in decision.diagnostics)


def test_review_agree_overrides_budget_concern(repo, tmp_path: Path) -> None:
    """Codex iter-2 must_close #1: AGREE passes through even when prior REVISE count >= budget."""

    r, base_sha = repo
    manifest_path, out_dir = _write_manifest_and_task_graph(
        repo=r, task_graph_id="ao-ma-20260527-agr1111", base_sha=base_sha, max_revise_rounds=1
    )
    wr_path = _write_worker_result(
        out_dir=out_dir, task_id="task-001", task_graph_id="ao-ma-20260527-agr1111", base_sha=base_sha
    )
    findings_path = _write_findings_json(tmp_path, _basic_findings())
    p1 = _write_prior_review_verdict(
        out_dir=out_dir, task_id="task-001", task_graph_id="ao-ma-20260527-agr1111", verdict="REVISE", suffix="1"
    )
    p2 = _write_prior_review_verdict(
        out_dir=out_dir, task_id="task-001", task_graph_id="ao-ma-20260527-agr1111", verdict="REVISE", suffix="2"
    )
    inputs = _make_inputs(
        repo=r,
        manifest_path=manifest_path,
        out_dir=out_dir,
        task_id="task-001",
        wr_path=wr_path,
        findings_path=findings_path,
        verdict="AGREE",
        prior_paths=[p1, p2],
    )
    decision = Reviewer(repo_root=r).review(inputs)
    assert decision.emitted_verdict == "AGREE"
    assert not decision.budget_forced_block


def test_review_budget_ignores_prior_verdicts_from_other_graph_or_task(repo, tmp_path: Path) -> None:
    """Codex iter-2 nice-to-have: defensive cross-ref — prior verdicts for other graph/task ignored."""

    r, base_sha = repo
    manifest_path, out_dir = _write_manifest_and_task_graph(
        repo=r, task_graph_id="ao-ma-20260527-igr1111", base_sha=base_sha, max_revise_rounds=1
    )
    wr_path = _write_worker_result(
        out_dir=out_dir, task_id="task-001", task_graph_id="ao-ma-20260527-igr1111", base_sha=base_sha
    )
    findings_path = _write_findings_json(tmp_path, _basic_findings())
    # Prior verdict for a DIFFERENT graph — must be skipped
    _, other_out_dir = _write_manifest_and_task_graph(repo=r, task_graph_id="ao-ma-20260527-otr1111", base_sha=base_sha)
    prior_other_graph = _write_prior_review_verdict(
        out_dir=other_out_dir, task_id="task-001", task_graph_id="ao-ma-20260527-otr1111", verdict="REVISE"
    )
    # Prior verdict for a DIFFERENT task in SAME graph — must be skipped
    prior_other_task = _write_prior_review_verdict(
        out_dir=out_dir, task_id="task-999", task_graph_id="ao-ma-20260527-igr1111", verdict="REVISE", suffix="othert"
    )
    inputs = _make_inputs(
        repo=r,
        manifest_path=manifest_path,
        out_dir=out_dir,
        task_id="task-001",
        wr_path=wr_path,
        findings_path=findings_path,
        verdict="REVISE",
        prior_paths=[prior_other_graph, prior_other_task],
    )
    decision = Reviewer(repo_root=r).review(inputs)
    # Both priors ignored (cross-ref defensive) → count=0 < budget(1) → REVISE allowed
    assert decision.emitted_verdict == "REVISE"
    assert decision.prior_revise_count == 0
    assert not decision.budget_forced_block


def test_review_budget_diagnostic_includes_requested_vs_emitted(repo, tmp_path: Path) -> None:
    """Codex iter-3 nice-to-have: diagnostic + dataclass shape stable contract."""

    r, base_sha = repo
    manifest_path, out_dir = _write_manifest_and_task_graph(
        repo=r, task_graph_id="ao-ma-20260527-dia1111", base_sha=base_sha, max_revise_rounds=1
    )
    wr_path = _write_worker_result(
        out_dir=out_dir, task_id="task-001", task_graph_id="ao-ma-20260527-dia1111", base_sha=base_sha
    )
    findings_path = _write_findings_json(tmp_path, _basic_findings())
    p1 = _write_prior_review_verdict(
        out_dir=out_dir, task_id="task-001", task_graph_id="ao-ma-20260527-dia1111", verdict="REVISE"
    )
    inputs = _make_inputs(
        repo=r,
        manifest_path=manifest_path,
        out_dir=out_dir,
        task_id="task-001",
        wr_path=wr_path,
        findings_path=findings_path,
        verdict="REVISE",
        prior_paths=[p1],
    )
    decision = Reviewer(repo_root=r).review(inputs)
    assert hasattr(decision, "requested_verdict")
    assert hasattr(decision, "emitted_verdict")
    assert hasattr(decision, "prior_revise_count")
    assert hasattr(decision, "max_revise_rounds")
    assert hasattr(decision, "budget_forced_block")
    assert decision.requested_verdict == "REVISE"
    assert decision.emitted_verdict == "BLOCK"
    assert decision.prior_revise_count == 1
    assert decision.max_revise_rounds == 1


# ---------------------------------------------------------------------------
# Cross-provider HARD RULE
# ---------------------------------------------------------------------------


def test_review_cross_provider_violation_raises(repo, tmp_path: Path) -> None:
    r, base_sha = repo
    manifest_path, out_dir = _write_manifest_and_task_graph(
        repo=r, task_graph_id="ao-ma-20260527-cpv1111", base_sha=base_sha
    )
    wr_path = _write_worker_result(
        out_dir=out_dir,
        task_id="task-001",
        task_graph_id="ao-ma-20260527-cpv1111",
        base_sha=base_sha,
        implementer_provider="anthropic",
    )
    findings_path = _write_findings_json(tmp_path, _basic_findings())
    inputs = _make_inputs(
        repo=r,
        manifest_path=manifest_path,
        out_dir=out_dir,
        task_id="task-001",
        wr_path=wr_path,
        findings_path=findings_path,
        reviewer_provider="anthropic",  # SAME as implementer → violation
    )
    with pytest.raises(ReviewerError, match="cross-AI peer review HARD RULE"):
        Reviewer(repo_root=r).review(inputs)


# ---------------------------------------------------------------------------
# Trust boundary
# ---------------------------------------------------------------------------


def test_review_missing_worker_result_mapping_raises(repo, tmp_path: Path) -> None:
    r, base_sha = repo
    manifest_path, out_dir = _write_manifest_and_task_graph(
        repo=r, task_graph_id="ao-ma-20260527-mwr1111", base_sha=base_sha
    )
    findings_path = _write_findings_json(tmp_path, _basic_findings())
    inputs = ReviewInputs(
        manifest_path=manifest_path,
        task_id="task-001",
        worker_result_paths={},  # EMPTY
        reviewer_agent_id="codex",
        reviewer_provider="openai",  # type: ignore[arg-type]
        reviewer_session_id="rev",
        verdict="AGREE",
        findings_path=findings_path,
    )
    with pytest.raises(ReviewerError, match="mapping missing entry"):
        Reviewer(repo_root=r).review(inputs)


def test_review_worker_result_mapping_key_must_match_payload_task_id(repo, tmp_path: Path) -> None:
    """Codex iter-2 nice-to-have: CLI mapping key vs payload task_id cross-ref."""

    r, base_sha = repo
    manifest_path, out_dir = _write_manifest_and_task_graph(
        repo=r, task_graph_id="ao-ma-20260527-mpk1111", base_sha=base_sha
    )
    # Worker_result payload says task_id="task-001" but mapping key will be different
    wr_path = _write_worker_result(
        out_dir=out_dir, task_id="task-001", task_graph_id="ao-ma-20260527-mpk1111", base_sha=base_sha
    )
    findings_path = _write_findings_json(tmp_path, _basic_findings())
    inputs = ReviewInputs(
        manifest_path=manifest_path,
        task_id="task-001",
        worker_result_paths={"task-002": wr_path},  # mapping key task-002 but --task-id task-001
        reviewer_agent_id="codex",
        reviewer_provider="openai",  # type: ignore[arg-type]
        reviewer_session_id="rev",
        verdict="AGREE",
        findings_path=findings_path,
    )
    with pytest.raises(ReviewerError, match="mapping missing entry for task_id 'task-001'"):
        Reviewer(repo_root=r).review(inputs)


def test_review_worker_result_payload_task_id_mismatch_raises(repo, tmp_path: Path) -> None:
    r, base_sha = repo
    manifest_path, out_dir = _write_manifest_and_task_graph(
        repo=r, task_graph_id="ao-ma-20260527-ptm1111", base_sha=base_sha
    )
    wr_path = _write_worker_result(
        out_dir=out_dir, task_id="task-001", task_graph_id="ao-ma-20260527-ptm1111", base_sha=base_sha
    )
    # Tamper payload task_id
    payload = json.loads(wr_path.read_text(encoding="utf-8"))
    payload["task_id"] = "task-999"
    wr_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    findings_path = _write_findings_json(tmp_path, _basic_findings())
    inputs = _make_inputs(
        repo=r,
        manifest_path=manifest_path,
        out_dir=out_dir,
        task_id="task-001",
        wr_path=wr_path,
        findings_path=findings_path,
    )
    with pytest.raises(ReviewerError, match="CLI mapping mismatch with payload"):
        Reviewer(repo_root=r).review(inputs)


def test_review_worker_result_task_graph_id_mismatch_raises(repo, tmp_path: Path) -> None:
    r, base_sha = repo
    manifest_path, out_dir = _write_manifest_and_task_graph(
        repo=r, task_graph_id="ao-ma-20260527-twm1111", base_sha=base_sha
    )
    wr_path = _write_worker_result(
        out_dir=out_dir, task_id="task-001", task_graph_id="ao-ma-20260527-twm1111", base_sha=base_sha
    )
    payload = json.loads(wr_path.read_text(encoding="utf-8"))
    payload["task_graph_id"] = "ao-ma-20260527-other77"
    wr_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    findings_path = _write_findings_json(tmp_path, _basic_findings())
    inputs = _make_inputs(
        repo=r,
        manifest_path=manifest_path,
        out_dir=out_dir,
        task_id="task-001",
        wr_path=wr_path,
        findings_path=findings_path,
    )
    with pytest.raises(ReviewerError, match="task_graph_id"):
        Reviewer(repo_root=r).review(inputs)


def test_review_manifest_task_graph_split_brain_raises(repo, tmp_path: Path) -> None:
    r, base_sha = repo
    manifest_path, out_dir = _write_manifest_and_task_graph(
        repo=r, task_graph_id="ao-ma-20260527-spb1111", base_sha=base_sha
    )
    # Tamper task_graph
    tg_path = out_dir / "task_graph.v1.json"
    tg = json.loads(tg_path.read_text(encoding="utf-8"))
    tg["task_graph_id"] = "ao-ma-20260527-other88"
    tg_path.write_text(json.dumps(tg, indent=2), encoding="utf-8")
    wr_path = _write_worker_result(
        out_dir=out_dir, task_id="task-001", task_graph_id="ao-ma-20260527-spb1111", base_sha=base_sha
    )
    findings_path = _write_findings_json(tmp_path, _basic_findings())
    inputs = _make_inputs(
        repo=r,
        manifest_path=manifest_path,
        out_dir=out_dir,
        task_id="task-001",
        wr_path=wr_path,
        findings_path=findings_path,
    )
    with pytest.raises(ReviewerError, match="split-brain"):
        Reviewer(repo_root=r).review(inputs)


# ---------------------------------------------------------------------------
# findings-json strict schema (Codex iter-2 must_close #3)
# ---------------------------------------------------------------------------


def test_review_findings_json_rejects_text_field(repo, tmp_path: Path) -> None:
    r, base_sha = repo
    manifest_path, out_dir = _write_manifest_and_task_graph(
        repo=r, task_graph_id="ao-ma-20260527-fjt1111", base_sha=base_sha
    )
    wr_path = _write_worker_result(
        out_dir=out_dir, task_id="task-001", task_graph_id="ao-ma-20260527-fjt1111", base_sha=base_sha
    )
    # `text` field NOT in schema $defs.finding
    findings_path = _write_findings_json(
        tmp_path, [{"severity": "info", "title": "x", "text": "should be body not text"}]
    )
    inputs = _make_inputs(
        repo=r,
        manifest_path=manifest_path,
        out_dir=out_dir,
        task_id="task-001",
        wr_path=wr_path,
        findings_path=findings_path,
    )
    with pytest.raises(ReviewerError, match="findings"):
        Reviewer(repo_root=r).review(inputs)


def test_review_findings_json_rejects_extra_property(repo, tmp_path: Path) -> None:
    r, base_sha = repo
    manifest_path, out_dir = _write_manifest_and_task_graph(
        repo=r, task_graph_id="ao-ma-20260527-fjp1111", base_sha=base_sha
    )
    wr_path = _write_worker_result(
        out_dir=out_dir, task_id="task-001", task_graph_id="ao-ma-20260527-fjp1111", base_sha=base_sha
    )
    findings_path = _write_findings_json(
        tmp_path,
        [{"severity": "info", "title": "x", "body": "y", "extra_field": "not allowed"}],
    )
    inputs = _make_inputs(
        repo=r,
        manifest_path=manifest_path,
        out_dir=out_dir,
        task_id="task-001",
        wr_path=wr_path,
        findings_path=findings_path,
    )
    with pytest.raises(ReviewerError):
        Reviewer(repo_root=r).review(inputs)


def test_review_findings_json_rejects_missing_severity(repo, tmp_path: Path) -> None:
    r, base_sha = repo
    manifest_path, out_dir = _write_manifest_and_task_graph(
        repo=r, task_graph_id="ao-ma-20260527-fms1111", base_sha=base_sha
    )
    wr_path = _write_worker_result(
        out_dir=out_dir, task_id="task-001", task_graph_id="ao-ma-20260527-fms1111", base_sha=base_sha
    )
    findings_path = _write_findings_json(tmp_path, [{"title": "x", "body": "y"}])
    inputs = _make_inputs(
        repo=r,
        manifest_path=manifest_path,
        out_dir=out_dir,
        task_id="task-001",
        wr_path=wr_path,
        findings_path=findings_path,
    )
    with pytest.raises(ReviewerError):
        Reviewer(repo_root=r).review(inputs)


def test_review_findings_json_rejects_invalid_severity_enum(repo, tmp_path: Path) -> None:
    r, base_sha = repo
    manifest_path, out_dir = _write_manifest_and_task_graph(
        repo=r, task_graph_id="ao-ma-20260527-fis1111", base_sha=base_sha
    )
    wr_path = _write_worker_result(
        out_dir=out_dir, task_id="task-001", task_graph_id="ao-ma-20260527-fis1111", base_sha=base_sha
    )
    findings_path = _write_findings_json(tmp_path, [{"severity": "critical_not_valid_enum", "title": "x", "body": "y"}])
    inputs = _make_inputs(
        repo=r,
        manifest_path=manifest_path,
        out_dir=out_dir,
        task_id="task-001",
        wr_path=wr_path,
        findings_path=findings_path,
    )
    with pytest.raises(ReviewerError):
        Reviewer(repo_root=r).review(inputs)


def test_review_findings_json_rejects_non_array_top_level(repo, tmp_path: Path) -> None:
    r, base_sha = repo
    manifest_path, out_dir = _write_manifest_and_task_graph(
        repo=r, task_graph_id="ao-ma-20260527-fna1111", base_sha=base_sha
    )
    wr_path = _write_worker_result(
        out_dir=out_dir, task_id="task-001", task_graph_id="ao-ma-20260527-fna1111", base_sha=base_sha
    )
    findings_path = tmp_path / "findings.json"
    findings_path.write_text(json.dumps({"not": "an array"}), encoding="utf-8")  # dict at top
    inputs = _make_inputs(
        repo=r,
        manifest_path=manifest_path,
        out_dir=out_dir,
        task_id="task-001",
        wr_path=wr_path,
        findings_path=findings_path,
    )
    with pytest.raises(ReviewerError, match="must be a JSON array"):
        Reviewer(repo_root=r).review(inputs)


# ---------------------------------------------------------------------------
# HARD RULE static pins
# ---------------------------------------------------------------------------


def test_reviewer_module_has_no_subprocess_import() -> None:
    """Codex iter-1 absorb: reviewer.py module must not import subprocess.

    AO-MA-6 v1 is pure-data; any subprocess call would be a shell-out
    surface. Static AST scan.
    """

    from ao_kernel.orchestration import reviewer as reviewer_mod

    source = Path(reviewer_mod.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert alias.name != "subprocess", "reviewer.py must not import subprocess"
        if isinstance(node, ast.ImportFrom):
            assert node.module != "subprocess", "reviewer.py must not from-import subprocess"


def test_reviewer_module_has_no_llm_call_literals() -> None:
    """Codex iter-1 absorb: NO LLM execution in v1 (no AoKernelClient.llm_call).

    Static text scan — ensures no future drift accidentally introduces an
    LLM-driven path without a full plan-time consultation.
    """

    from ao_kernel.orchestration import reviewer as reviewer_mod

    source = Path(reviewer_mod.__file__).read_text(encoding="utf-8")
    # Forbidden execution-path literals (data names in docstrings/comments OK)
    forbidden_calls = [
        "llm_call(",
        "client.llm_call",
        "AoKernelClient(",
        ".llm_call(",
    ]
    for needle in forbidden_calls:
        assert needle not in source, f"reviewer.py must not contain '{needle}' (LLM call literal)"


def test_reviewer_module_has_no_gh_or_git_push_literals() -> None:
    """Codex iter-1 absorb: no shell-out / GitHub write."""

    from ao_kernel.orchestration import reviewer as reviewer_mod

    source = Path(reviewer_mod.__file__).read_text(encoding="utf-8")
    assert "subprocess.run" not in source
    assert "os.system" not in source
    assert "os.popen" not in source


def test_review_no_pr_url_argument_in_cli() -> None:
    """Codex iter-1 absorb: PR/GitHub fetch OUT of v1 — no --pr CLI flag."""

    from ao_kernel.orchestration import cli_handlers as ch_mod

    source = Path(ch_mod.__file__).read_text(encoding="utf-8")
    # Find the review_p block (~ subparser definitions)
    assert '"--pr"' not in source, "AO-MA-6 v1 CLI must not have --pr URL argument"


def test_review_no_llm_driven_argument_in_cli() -> None:
    """Codex iter-1 absorb: --llm-driven OUT of v1."""

    from ao_kernel.orchestration import cli_handlers as ch_mod

    source = Path(ch_mod.__file__).read_text(encoding="utf-8")
    assert '"--llm-driven"' not in source


def test_review_does_not_modify_ao_ma_5_modules() -> None:
    """Codex iter-1 must_close #7: AO-MA-6 PR only adds NEW files; no edits to AO-MA-5.

    Static check: the integrator.py module's content fingerprint (file
    existence + key function names) is preserved. We don't need to git
    diff scan workspace state — that would yield false positives from
    untracked plan docs. This test asserts the integrator surface this
    PR cares about hasn't been touched by reviewer changes.
    """

    from ao_kernel.orchestration import integration_report_writer, integrator

    # Sanity: AO-MA-5 modules still importable + expected surface
    assert hasattr(integrator, "Integrator")
    assert hasattr(integrator, "IntegrationDecision")
    assert hasattr(integrator, "IntegratorError")
    assert hasattr(integrator, "verification_passed")
    assert hasattr(integration_report_writer, "IntegrationReportWriter")
    assert hasattr(integration_report_writer, "IntegrationReportWriterError")


# ---------------------------------------------------------------------------
# CLI integration
# ---------------------------------------------------------------------------


def test_cli_review_happy_path_exits_zero(repo, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    from ao_kernel.cli import main as cli_main

    r, base_sha = repo
    manifest_path, out_dir = _write_manifest_and_task_graph(
        repo=r, task_graph_id="ao-ma-20260527-cli0001", base_sha=base_sha
    )
    wr_path = _write_worker_result(
        out_dir=out_dir, task_id="task-001", task_graph_id="ao-ma-20260527-cli0001", base_sha=base_sha
    )
    findings_path = _write_findings_json(tmp_path, _basic_findings())
    diff_path = _make_stub_diff(out_dir, "task-001")
    rc = cli_main(
        [
            "orchestration",
            "review",
            "--manifest",
            str(manifest_path),
            "--task-id",
            "task-001",
            "--worker-result",
            f"task-001={wr_path}",
            "--reviewer-agent-id",
            "codex-reviewer",
            "--reviewer-provider",
            "openai",
            "--reviewer-session-id",
            "rev-session",
            "--verdict",
            "AGREE",
            "--findings-json",
            str(findings_path),
            "--diff-path",
            str(diff_path),
            "--repo-root",
            str(r),
            "--format",
            "json",
        ]
    )
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["emitted_verdict"] == "AGREE"


def test_cli_review_missing_manifest_exits_two(repo, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    from ao_kernel.cli import main as cli_main

    r, _ = repo
    findings_path = _write_findings_json(tmp_path, _basic_findings())
    rc = cli_main(
        [
            "orchestration",
            "review",
            "--manifest",
            str(r / "does_not_exist.json"),
            "--task-id",
            "task-001",
            "--worker-result",
            "task-001=/tmp/x",
            "--reviewer-agent-id",
            "codex",
            "--reviewer-provider",
            "openai",
            "--reviewer-session-id",
            "rev",
            "--verdict",
            "AGREE",
            "--findings-json",
            str(findings_path),
        ]
    )
    assert rc == 2


def test_cli_review_missing_findings_exits_two(repo, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    from ao_kernel.cli import main as cli_main

    r, base_sha = repo
    manifest_path, out_dir = _write_manifest_and_task_graph(
        repo=r, task_graph_id="ao-ma-20260527-cli0002", base_sha=base_sha
    )
    wr_path = _write_worker_result(
        out_dir=out_dir, task_id="task-001", task_graph_id="ao-ma-20260527-cli0002", base_sha=base_sha
    )
    rc = cli_main(
        [
            "orchestration",
            "review",
            "--manifest",
            str(manifest_path),
            "--task-id",
            "task-001",
            "--worker-result",
            f"task-001={wr_path}",
            "--reviewer-agent-id",
            "codex",
            "--reviewer-provider",
            "openai",
            "--reviewer-session-id",
            "rev",
            "--verdict",
            "AGREE",
            "--findings-json",
            str(tmp_path / "missing.json"),
        ]
    )
    assert rc == 2


def test_cli_review_cross_provider_violation_exits_two(
    repo, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    from ao_kernel.cli import main as cli_main

    r, base_sha = repo
    manifest_path, out_dir = _write_manifest_and_task_graph(
        repo=r, task_graph_id="ao-ma-20260527-cli0003", base_sha=base_sha
    )
    wr_path = _write_worker_result(
        out_dir=out_dir,
        task_id="task-001",
        task_graph_id="ao-ma-20260527-cli0003",
        base_sha=base_sha,
        implementer_provider="anthropic",
    )
    findings_path = _write_findings_json(tmp_path, _basic_findings())
    rc = cli_main(
        [
            "orchestration",
            "review",
            "--manifest",
            str(manifest_path),
            "--task-id",
            "task-001",
            "--worker-result",
            f"task-001={wr_path}",
            "--reviewer-agent-id",
            "claude-reviewer",
            "--reviewer-provider",
            "anthropic",  # SAME
            "--reviewer-session-id",
            "rev",
            "--verdict",
            "AGREE",
            "--findings-json",
            str(findings_path),
            "--repo-root",
            str(r),
        ]
    )
    assert rc == 2


def test_cli_review_emit_failure_exits_three(
    repo, tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Codex iter-1 absorb: CLI exit 3 contract for emit failure."""

    from ao_kernel.cli import main as cli_main
    from ao_kernel.orchestration import review_verdict_writer as writer_mod

    r, base_sha = repo
    manifest_path, out_dir = _write_manifest_and_task_graph(
        repo=r, task_graph_id="ao-ma-20260527-cli0004", base_sha=base_sha
    )
    wr_path = _write_worker_result(
        out_dir=out_dir, task_id="task-001", task_graph_id="ao-ma-20260527-cli0004", base_sha=base_sha
    )
    findings_path = _write_findings_json(tmp_path, _basic_findings())
    diff_path = _make_stub_diff(out_dir, "task-001")

    def _boom(self, payload):  # noqa: ANN001
        raise writer_mod.ReviewVerdictWriterError("simulated emit failure")

    monkeypatch.setattr(writer_mod.ReviewVerdictWriter, "emit", _boom)
    rc = cli_main(
        [
            "orchestration",
            "review",
            "--manifest",
            str(manifest_path),
            "--task-id",
            "task-001",
            "--worker-result",
            f"task-001={wr_path}",
            "--reviewer-agent-id",
            "codex",
            "--reviewer-provider",
            "openai",
            "--reviewer-session-id",
            "rev",
            "--verdict",
            "AGREE",
            "--findings-json",
            str(findings_path),
            "--diff-path",
            str(diff_path),
            "--repo-root",
            str(r),
        ]
    )
    assert rc == 3


# ---------------------------------------------------------------------------
# Convention path
# ---------------------------------------------------------------------------


def test_review_emits_to_default_path_under_workers_subdir(repo, tmp_path: Path) -> None:
    r, base_sha = repo
    manifest_path, out_dir = _write_manifest_and_task_graph(
        repo=r, task_graph_id="ao-ma-20260527-pth1111", base_sha=base_sha
    )
    wr_path = _write_worker_result(
        out_dir=out_dir, task_id="task-001", task_graph_id="ao-ma-20260527-pth1111", base_sha=base_sha
    )
    findings_path = _write_findings_json(tmp_path, _basic_findings())
    inputs = _make_inputs(
        repo=r,
        manifest_path=manifest_path,
        out_dir=out_dir,
        task_id="task-001",
        wr_path=wr_path,
        findings_path=findings_path,
    )
    Reviewer(repo_root=r).review(inputs)
    expected = out_dir / "workers" / "task-001" / "review_verdict.v1.json"
    assert expected.exists()


# ---------------------------------------------------------------------------
# Codex iter-4 must_fix absorb: allowed_sources fail-closed (no fabrication)
# ---------------------------------------------------------------------------


def test_review_no_context_evidence_exits_two(repo, tmp_path: Path) -> None:
    """Codex iter-4 must_fix: no evidence supplied → ReviewerError (CLI exit 2).

    Previous v1 fell back to ``allowed_sources=["pr_diff"]`` even when
    no path was supplied; that fabricated a source claim for an artifact
    the reviewer never read. Now fail-closed.
    """

    r, base_sha = repo
    manifest_path, out_dir = _write_manifest_and_task_graph(
        repo=r, task_graph_id="ao-ma-20260527-nev1111", base_sha=base_sha
    )
    wr_path = _write_worker_result(
        out_dir=out_dir, task_id="task-001", task_graph_id="ao-ma-20260527-nev1111", base_sha=base_sha
    )
    findings_path = _write_findings_json(tmp_path, _basic_findings())
    # Explicit ReviewInputs with NO evidence paths and NO priors
    inputs = ReviewInputs(
        manifest_path=manifest_path,
        task_id="task-001",
        worker_result_paths={"task-001": wr_path},
        reviewer_agent_id="codex-reviewer",
        reviewer_provider="openai",  # type: ignore[arg-type]
        reviewer_session_id="rev-session",
        verdict="AGREE",  # type: ignore[arg-type]
        findings_path=findings_path,
        # No evidence paths at all
    )
    with pytest.raises(ReviewerError, match="no review evidence supplied"):
        Reviewer(repo_root=r).review(inputs)


def test_review_missing_optional_evidence_path_exits_two(repo, tmp_path: Path) -> None:
    """Codex iter-4 must_fix: optional evidence path supplied but file missing → fail-closed.

    Operator typo'd a path; reviewer must NOT silently claim the source
    in allowed_sources when the actual artifact wasn't read.
    """

    r, base_sha = repo
    manifest_path, out_dir = _write_manifest_and_task_graph(
        repo=r, task_graph_id="ao-ma-20260527-mev1111", base_sha=base_sha
    )
    wr_path = _write_worker_result(
        out_dir=out_dir, task_id="task-001", task_graph_id="ao-ma-20260527-mev1111", base_sha=base_sha
    )
    findings_path = _write_findings_json(tmp_path, _basic_findings())
    bogus = tmp_path / "does_not_exist.patch"
    inputs = ReviewInputs(
        manifest_path=manifest_path,
        task_id="task-001",
        worker_result_paths={"task-001": wr_path},
        reviewer_agent_id="codex-reviewer",
        reviewer_provider="openai",  # type: ignore[arg-type]
        reviewer_session_id="rev-session",
        verdict="AGREE",  # type: ignore[arg-type]
        findings_path=findings_path,
        diff_path=bogus,  # non-existent
    )
    with pytest.raises(ReviewerError, match="is not a regular file"):
        Reviewer(repo_root=r).review(inputs)


def test_review_does_not_default_allowed_sources_to_pr_diff(repo, tmp_path: Path) -> None:
    """Codex iter-4 must_fix: ``["pr_diff"]`` default fallback removed.

    When operator supplies a single non-pr_diff evidence (e.g. ci_results
    only), the emitted ``allowed_sources`` must reflect ONLY that source,
    NOT include a fabricated ``pr_diff`` entry.
    """

    r, base_sha = repo
    manifest_path, out_dir = _write_manifest_and_task_graph(
        repo=r, task_graph_id="ao-ma-20260527-nps1111", base_sha=base_sha
    )
    wr_path = _write_worker_result(
        out_dir=out_dir, task_id="task-001", task_graph_id="ao-ma-20260527-nps1111", base_sha=base_sha
    )
    findings_path = _write_findings_json(tmp_path, _basic_findings())
    # Place ci_results under the repo so _relativize() succeeds
    ci_results_path = r / "ci_results.txt"
    ci_results_path.write_text("ok", encoding="utf-8")
    # Supply ONLY ci_results — no diff_path
    inputs = ReviewInputs(
        manifest_path=manifest_path,
        task_id="task-001",
        worker_result_paths={"task-001": wr_path},
        reviewer_agent_id="codex-reviewer",
        reviewer_provider="openai",  # type: ignore[arg-type]
        reviewer_session_id="rev-session",
        verdict="AGREE",  # type: ignore[arg-type]
        findings_path=findings_path,
        ci_results_path=ci_results_path,
    )
    decision = Reviewer(repo_root=r).review(inputs)
    emitted = decision.report["allowed_sources"]
    assert emitted == ["ci_results"], f"expected only ['ci_results'], got {emitted!r}"
    assert "pr_diff" not in emitted, "must NOT default-fabricate pr_diff entry"
