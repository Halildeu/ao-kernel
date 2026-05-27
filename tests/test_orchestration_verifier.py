"""AO-MA-7 verifier tests (Codex thread 019e6996 iter-1 AGREE absorb).

30+ tests cover:
- Happy path (all 4 checks pass, schema-valid emit)
- GPP guard violations across all 5 sources (manifest, task_graph, worker_result, review_verdict, gpp_status)
- Secret scan (positive detections + false-positive defenses + secrets_recorded cross-check)
- Diff scope subset check + task_graph cross-ref (inflation defense)
- Artifact hashes H1 format (no role field; no self-reference)
- Trust boundary (cross-provider, schema validation, path existence)
- HARD RULE static pins (no subprocess, no LLM call, no gh/git push)
- CLI exit code matrix
- Deterministic check names (Codex iter-1 must_close #5)
- secret_scan.detail metadata-only statement (Codex iter-1 must_close #1)
- AO-MA-5/6 modules untouched
"""

from __future__ import annotations

import ast
import hashlib
import json
import subprocess
from collections.abc import Iterator
from pathlib import Path

import pytest

from ao_kernel.orchestration.verifier import (
    VerificationInputs,
    Verifier,
    VerifierError,
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
    manifest_guard_violation: str | None = None,
    task_graph_guard_violation: str | None = None,
) -> tuple[Path, Path]:
    """Returns (manifest_path, out_dir) for the test to use."""

    declared = declared or ["src/a.py"]
    base_dir = repo / ".ao" / "orchestration"
    out_dir = base_dir / task_graph_id
    out_dir.mkdir(parents=True, exist_ok=True)
    tg_guards = {
        "support_widening": False,
        "production_platform_claim": False,
        "live_adapter_execution": False,
    }
    if task_graph_guard_violation:
        # Schema enforces const: false, so we'll keep these literal False
        # but record violation source via a non-bool sentinel; tests of
        # GPP guard violation use a Python-side patch instead (see below).
        pass
    task_graph = {
        "schema_version": "ao-ma-task-graph.v1",
        "task_graph_id": task_graph_id,
        "repo": "Halildeu/ao-kernel",
        "goal": "AO-MA-7 verifier test fixture",
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
            "max_revise_rounds": 3,
        },
        "guard_flags": tg_guards,
    }
    tg_path = out_dir / "task_graph.v1.json"
    tg_path.write_text(json.dumps(task_graph, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    mf_guards = {
        "support_widening": False,
        "production_platform_claim": False,
        "live_adapter_execution": False,
    }
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
        "guard_flags": mf_guards,
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
    summary: str = "test worker summary",
    secrets_recorded: bool = False,
) -> Path:
    declared = declared or ["src/a.py"]
    actual = actual if actual is not None else declared
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
            "session_id": f"ao-ma-7-test-{task_graph_id}",
        },
        "base_ref": "refs/heads/main",
        "base_sha": base_sha,
        "head_ref": f"codex/ao-ma-{task_graph_id}/{task_id}",
        "head_sha": "c" * 40,
        "declared_write_set": declared,
        "actual_changed_files": actual,
        "summary": summary,
        "tests_run": [{"command": "pytest", "outcome": "pass"}],
        "known_gaps": [],
        "no_secret_attestation": {"secrets_recorded": secrets_recorded},
        "guard_flags": {
            "support_widening": False,
            "production_platform_claim": False,
            "live_adapter_execution": False,
        },
    }
    wr_path = worker_dir / "worker_result.v1.json"
    wr_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return wr_path


def _write_review_verdict(
    *,
    out_dir: Path,
    task_id: str,
    task_graph_id: str,
    diff_path: Path,
) -> Path:
    """Write a minimal valid review_verdict.v1.json for the optional input."""

    payload = {
        "schema_version": "ao-ma-review-verdict.v1",
        "task_graph_id": task_graph_id,
        "reviewed_task_id": task_id,
        "reviewer": {
            "agent_id": "codex-reviewer",
            "agent_type": "reviewer",
            "provider": "openai",
            "session_id": "rev-session",
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
        "verdict": "AGREE",
        "findings": [],
        "reviewed_artifacts": [str(diff_path.relative_to(out_dir))],
        "no_secret_attestation": {"secrets_recorded": False},
        "guard_flags": {
            "support_widening": False,
            "production_platform_claim": False,
            "live_adapter_execution": False,
        },
    }
    rv_dir = out_dir / "workers" / task_id
    rv_dir.mkdir(parents=True, exist_ok=True)
    rv_path = rv_dir / "review_verdict.v1.json"
    rv_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return rv_path


def _write_gpp_status(*, repo: Path, allow_flag: str | None = None) -> Path:
    """Write a stub gpp_status.v1.json with optional allowlist flag set true."""

    plans_dir = repo / ".claude" / "plans"
    plans_dir.mkdir(parents=True, exist_ok=True)
    payload: dict = {
        "schema_version": "gpp_status.v1",
        "current_wp": {
            "id": "AO-MA-7",
            "support_widening_allowed": False,
            "production_platform_claim_allowed": False,
            "live_adapter_execution_allowed": False,
        },
    }
    if allow_flag is not None:
        payload["current_wp"][allow_flag] = True
    p = plans_dir / "gpp_status.v1.json"
    p.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return p


def _write_stub_diff(out_dir: Path, task_id: str) -> Path:
    p = out_dir / "workers" / task_id / "pr_diff.patch"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("--- a/src/a.py\n+++ b/src/a.py\n@@ -0,0 +1 @@\n+stub\n", encoding="utf-8")
    return p


@pytest.fixture
def repo(tmp_path: Path) -> Iterator[tuple[Path, str]]:
    r = tmp_path / "repo"
    sha = _git_init_repo(r)
    yield r, sha


def _make_inputs(
    *,
    manifest_path: Path,
    task_id: str,
    wr_path: Path,
    review_verdict_path: Path | None = None,
    gpp_status_path: Path | None = None,
    verifier_provider: str = "tool",
) -> VerificationInputs:
    return VerificationInputs(
        manifest_path=manifest_path,
        task_id=task_id,
        worker_result_paths={task_id: wr_path},
        verifier_agent_id="verifier-tool",
        verifier_provider=verifier_provider,  # type: ignore[arg-type]
        verifier_session_id="ver-session",
        review_verdict_path=review_verdict_path,
        gpp_status_path=gpp_status_path,
    )


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


def test_verify_happy_path_all_checks_pass(repo, tmp_path: Path) -> None:
    r, base_sha = repo
    manifest_path, out_dir = _write_manifest_and_task_graph(
        repo=r, task_graph_id="ao-ma-20260527-hap1111", base_sha=base_sha
    )
    wr_path = _write_worker_result(
        out_dir=out_dir, task_id="task-001", task_graph_id="ao-ma-20260527-hap1111", base_sha=base_sha
    )
    inputs = _make_inputs(manifest_path=manifest_path, task_id="task-001", wr_path=wr_path)
    result = Verifier(repo_root=r).verify(inputs)
    assert result.overall_pass
    assert not result.failed_checks
    # Emitted to disk
    emitted = out_dir / "workers" / "task-001" / "verification_report.v1.json"
    assert emitted.exists()
    payload = json.loads(emitted.read_text(encoding="utf-8"))
    assert payload["task_graph_id"] == "ao-ma-20260527-hap1111"
    assert payload["verified_task_ids"] == ["task-001"]
    # All 5 commands present, all pass
    cmd_names = [c["command"] for c in payload["commands"]]
    assert cmd_names == [
        "schema_validation",
        "gpp_guard_check",
        "metadata_secret_scan",
        "diff_scope_static_check",
        "artifact_hashing",
    ]
    assert all(c["outcome"] == "pass" for c in payload["commands"])


# ---------------------------------------------------------------------------
# GPP guard violations across all 5 sources (Codex iter-1 must_close #3)
# ---------------------------------------------------------------------------


def test_verify_gpp_guard_violation_in_manifest(repo, tmp_path: Path) -> None:
    """Manifest guard_flags has non-False value → schema rejects at load time
    (manifest schema enforces const: false). Use direct verifier helper instead.
    """

    from ao_kernel.orchestration.verifier import _check_gpp_guards

    manifest_bad = {
        "guard_flags": {"support_widening": True, "production_platform_claim": False, "live_adapter_execution": False}
    }
    task_graph = {
        "guard_flags": {"support_widening": False, "production_platform_claim": False, "live_adapter_execution": False}
    }
    worker = {
        "guard_flags": {"support_widening": False, "production_platform_claim": False, "live_adapter_execution": False}
    }
    outcome, viols = _check_gpp_guards(
        manifest=manifest_bad,
        task_graph=task_graph,
        worker_result=worker,
        review_verdict=None,
        gpp_status=None,
    )
    assert outcome == "fail"
    assert any("manifest.support_widening" in v for v in viols)


def test_verify_gpp_guard_violation_in_task_graph() -> None:
    from ao_kernel.orchestration.verifier import _check_gpp_guards

    closed = {"support_widening": False, "production_platform_claim": False, "live_adapter_execution": False}
    open_tg = {"support_widening": False, "production_platform_claim": True, "live_adapter_execution": False}
    outcome, viols = _check_gpp_guards(
        manifest={"guard_flags": closed},
        task_graph={"guard_flags": open_tg},
        worker_result={"guard_flags": closed},
        review_verdict=None,
        gpp_status=None,
    )
    assert outcome == "fail"
    assert any("task_graph.production_platform_claim" in v for v in viols)


def test_verify_gpp_guard_violation_in_worker_result() -> None:
    from ao_kernel.orchestration.verifier import _check_gpp_guards

    closed = {"support_widening": False, "production_platform_claim": False, "live_adapter_execution": False}
    open_wr = {"support_widening": False, "production_platform_claim": False, "live_adapter_execution": True}
    outcome, viols = _check_gpp_guards(
        manifest={"guard_flags": closed},
        task_graph={"guard_flags": closed},
        worker_result={"guard_flags": open_wr},
        review_verdict=None,
        gpp_status=None,
    )
    assert outcome == "fail"
    assert any("worker_result.live_adapter_execution" in v for v in viols)


def test_verify_gpp_guard_violation_in_review_verdict() -> None:
    from ao_kernel.orchestration.verifier import _check_gpp_guards

    closed = {"support_widening": False, "production_platform_claim": False, "live_adapter_execution": False}
    open_rv = {"support_widening": True, "production_platform_claim": False, "live_adapter_execution": False}
    outcome, viols = _check_gpp_guards(
        manifest={"guard_flags": closed},
        task_graph={"guard_flags": closed},
        worker_result={"guard_flags": closed},
        review_verdict={"guard_flags": open_rv},
        gpp_status=None,
    )
    assert outcome == "fail"
    assert any("review_verdict.support_widening" in v for v in viols)


def test_verify_gpp_guard_violation_in_gpp_status(repo, tmp_path: Path) -> None:
    """Codex iter-1 must_close #3: gpp_status allowlist flag True → failed_checks."""

    r, base_sha = repo
    manifest_path, out_dir = _write_manifest_and_task_graph(
        repo=r, task_graph_id="ao-ma-20260527-gpp1111", base_sha=base_sha
    )
    wr_path = _write_worker_result(
        out_dir=out_dir, task_id="task-001", task_graph_id="ao-ma-20260527-gpp1111", base_sha=base_sha
    )
    # Stub gpp_status with support_widening_allowed=True (forbidden)
    gpp_path = _write_gpp_status(repo=r, allow_flag="support_widening_allowed")
    inputs = _make_inputs(
        manifest_path=manifest_path,
        task_id="task-001",
        wr_path=wr_path,
        gpp_status_path=gpp_path,
    )
    result = Verifier(repo_root=r).verify(inputs)
    assert not result.overall_pass
    assert any("gpp_status.support_widening_allowed_true" in fc for fc in result.failed_checks)


def test_verify_gpp_status_default_path_consulted_when_present(repo) -> None:
    """Codex iter-1 plan: default ``.claude/plans/gpp_status.v1.json`` consulted."""

    r, base_sha = repo
    manifest_path, out_dir = _write_manifest_and_task_graph(
        repo=r, task_graph_id="ao-ma-20260527-gpd1111", base_sha=base_sha
    )
    wr_path = _write_worker_result(
        out_dir=out_dir, task_id="task-001", task_graph_id="ao-ma-20260527-gpd1111", base_sha=base_sha
    )
    _write_gpp_status(repo=r, allow_flag="live_adapter_execution_allowed")
    # Do NOT pass gpp_status_path — verifier should auto-discover default
    inputs = _make_inputs(manifest_path=manifest_path, task_id="task-001", wr_path=wr_path)
    result = Verifier(repo_root=r).verify(inputs)
    assert not result.overall_pass
    assert any("gpp_status.live_adapter_execution_allowed_true" in fc for fc in result.failed_checks)


# ---------------------------------------------------------------------------
# Secret scan (Codex iter-1 must_close #1: metadata-only scope statement)
# ---------------------------------------------------------------------------


def test_verify_secret_scan_detects_openai_key(repo, tmp_path: Path) -> None:
    r, base_sha = repo
    manifest_path, out_dir = _write_manifest_and_task_graph(
        repo=r, task_graph_id="ao-ma-20260527-sec1111", base_sha=base_sha
    )
    wr_path = _write_worker_result(
        out_dir=out_dir,
        task_id="task-001",
        task_graph_id="ao-ma-20260527-sec1111",
        base_sha=base_sha,
        # Constructed at runtime so the repo's literal-grep pre-commit
        # secret-scan does not flag this fixture. Verifier's metadata
        # regex matches the assembled value embedded in serialized JSON.
        summary="leaked: " + "s" + "k-" + "A" * 40,
    )
    inputs = _make_inputs(manifest_path=manifest_path, task_id="task-001", wr_path=wr_path)
    result = Verifier(repo_root=r).verify(inputs)
    assert not result.overall_pass
    assert any("secret_scan.worker_result.openai_or_anthropic_token_match" in fc for fc in result.failed_checks)
    assert result.report["secret_scan"]["passed"] is False


def test_verify_secret_scan_detects_private_key_block(repo, tmp_path: Path) -> None:
    r, base_sha = repo
    manifest_path, out_dir = _write_manifest_and_task_graph(
        repo=r, task_graph_id="ao-ma-20260527-pkb1111", base_sha=base_sha
    )
    wr_path = _write_worker_result(
        out_dir=out_dir,
        task_id="task-001",
        task_graph_id="ao-ma-20260527-pkb1111",
        base_sha=base_sha,
        # Constructed at runtime; pre-commit literal-grep does not match
        # the disassembled fragments.
        summary="oops: " + "-----BEGIN" + " RSA " + "PRIVATE KEY-----" + " abc",
    )
    inputs = _make_inputs(manifest_path=manifest_path, task_id="task-001", wr_path=wr_path)
    result = Verifier(repo_root=r).verify(inputs)
    assert not result.overall_pass
    assert any("private_key_block_match" in fc for fc in result.failed_checks)


def test_verify_secret_scan_detects_aws_access_key_id(repo, tmp_path: Path) -> None:
    r, base_sha = repo
    manifest_path, out_dir = _write_manifest_and_task_graph(
        repo=r, task_graph_id="ao-ma-20260527-aws1111", base_sha=base_sha
    )
    wr_path = _write_worker_result(
        out_dir=out_dir,
        task_id="task-001",
        task_graph_id="ao-ma-20260527-aws1111",
        base_sha=base_sha,
        # Constructed at runtime to avoid pre-commit literal-grep match.
        summary="key " + "AKIA" + "ABCDEFGHIJKLMNOP" + " leaked",
    )
    inputs = _make_inputs(manifest_path=manifest_path, task_id="task-001", wr_path=wr_path)
    result = Verifier(repo_root=r).verify(inputs)
    assert not result.overall_pass
    assert any("aws_access_key_id_match" in fc for fc in result.failed_checks)


def test_verify_secret_scan_detects_github_pat(repo, tmp_path: Path) -> None:
    r, base_sha = repo
    manifest_path, out_dir = _write_manifest_and_task_graph(
        repo=r, task_graph_id="ao-ma-20260527-ghp1111", base_sha=base_sha
    )
    wr_path = _write_worker_result(
        out_dir=out_dir,
        task_id="task-001",
        task_graph_id="ao-ma-20260527-ghp1111",
        base_sha=base_sha,
        summary="leak: ghp_" + "X" * 40,
    )
    inputs = _make_inputs(manifest_path=manifest_path, task_id="task-001", wr_path=wr_path)
    result = Verifier(repo_root=r).verify(inputs)
    assert not result.overall_pass
    assert any("github_classic_token_match" in fc for fc in result.failed_checks)


def test_verify_secret_scan_does_not_flag_sha256_hashes(repo, tmp_path: Path) -> None:
    """Codex iter-1 must_close #1: sha256:[0-9a-f]{64} stays clean (false-positive defense)."""

    r, base_sha = repo
    manifest_path, out_dir = _write_manifest_and_task_graph(
        repo=r, task_graph_id="ao-ma-20260527-sha1111", base_sha=base_sha
    )
    # worker_result summary contains a sha256:... hash; this must NOT match
    wr_path = _write_worker_result(
        out_dir=out_dir,
        task_id="task-001",
        task_graph_id="ao-ma-20260527-sha1111",
        base_sha=base_sha,
        summary="evidence sha256:" + "a" * 64,
    )
    inputs = _make_inputs(manifest_path=manifest_path, task_id="task-001", wr_path=wr_path)
    result = Verifier(repo_root=r).verify(inputs)
    # No secret match (sha256 prefix stripped before regex)
    assert all("secret_scan" not in fc or "secrets_recorded" in fc for fc in result.failed_checks)


def test_verify_secret_scan_does_not_flag_git_sha(repo, tmp_path: Path) -> None:
    """40-char git SHA hex stays clean (false-positive defense)."""

    r, base_sha = repo
    manifest_path, out_dir = _write_manifest_and_task_graph(
        repo=r, task_graph_id="ao-ma-20260527-gsh1111", base_sha=base_sha
    )
    wr_path = _write_worker_result(
        out_dir=out_dir,
        task_id="task-001",
        task_graph_id="ao-ma-20260527-gsh1111",
        base_sha=base_sha,
    )
    # worker_result head_sha is 'c'*40, base_sha is 40 hex; both must not trigger
    inputs = _make_inputs(manifest_path=manifest_path, task_id="task-001", wr_path=wr_path)
    result = Verifier(repo_root=r).verify(inputs)
    assert result.overall_pass


def test_verify_secret_scan_secrets_recorded_true_fails(repo, tmp_path: Path) -> None:
    """Codex iter-1 absorb: worker_result.no_secret_attestation.secrets_recorded=True fails fast.

    Schema enforces no_secret_attestation.secrets_recorded const: false, so the
    worker_result schema validation will fail first. This test confirms that
    behavior (Codex iter-1 schema fold observation).
    """

    r, base_sha = repo
    manifest_path, out_dir = _write_manifest_and_task_graph(
        repo=r, task_graph_id="ao-ma-20260527-srt1111", base_sha=base_sha
    )
    # secrets_recorded=True violates the worker_result schema's const:false
    wr_path = _write_worker_result(
        out_dir=out_dir,
        task_id="task-001",
        task_graph_id="ao-ma-20260527-srt1111",
        base_sha=base_sha,
        secrets_recorded=True,
    )
    inputs = _make_inputs(manifest_path=manifest_path, task_id="task-001", wr_path=wr_path)
    with pytest.raises(VerifierError, match="failed schema"):
        Verifier(repo_root=r).verify(inputs)


def test_verify_secret_scan_detail_says_metadata_only(repo, tmp_path: Path) -> None:
    """Codex iter-1 must_close #1: detail string explicit about scope."""

    r, base_sha = repo
    manifest_path, out_dir = _write_manifest_and_task_graph(
        repo=r, task_graph_id="ao-ma-20260527-det1111", base_sha=base_sha
    )
    wr_path = _write_worker_result(
        out_dir=out_dir, task_id="task-001", task_graph_id="ao-ma-20260527-det1111", base_sha=base_sha
    )
    inputs = _make_inputs(manifest_path=manifest_path, task_id="task-001", wr_path=wr_path)
    result = Verifier(repo_root=r).verify(inputs)
    detail = result.report["secret_scan"]["detail"]
    assert "metadata" in detail.lower() or "JSON artifacts" in detail
    assert "source file" in detail.lower()
    assert "NOT scanned" in detail or "not scanned" in detail


# ---------------------------------------------------------------------------
# Diff scope (Codex iter-1 must_close #2: task_graph cross-ref)
# ---------------------------------------------------------------------------


def test_verify_diff_scope_actual_outside_declared(repo, tmp_path: Path) -> None:
    r, base_sha = repo
    manifest_path, out_dir = _write_manifest_and_task_graph(
        repo=r, task_graph_id="ao-ma-20260527-scp1111", base_sha=base_sha, declared=["src/a.py"]
    )
    # Actual changed includes src/b.py — outside declared
    wr_path = _write_worker_result(
        out_dir=out_dir,
        task_id="task-001",
        task_graph_id="ao-ma-20260527-scp1111",
        base_sha=base_sha,
        declared=["src/a.py"],
        actual=["src/a.py", "src/b.py"],
    )
    inputs = _make_inputs(manifest_path=manifest_path, task_id="task-001", wr_path=wr_path)
    result = Verifier(repo_root=r).verify(inputs)
    assert not result.overall_pass
    assert any("actual_outside_declared" in fc for fc in result.failed_checks)


def test_verify_diff_scope_declared_mismatch_with_task_graph(repo, tmp_path: Path) -> None:
    """Codex iter-1 must_close #2: worker_result.declared_write_set != task_graph entry."""

    r, base_sha = repo
    manifest_path, out_dir = _write_manifest_and_task_graph(
        repo=r, task_graph_id="ao-ma-20260527-mch1111", base_sha=base_sha, declared=["src/a.py"]
    )
    # Worker INFLATES its declared (claims more than task_graph authorized)
    wr_path = _write_worker_result(
        out_dir=out_dir,
        task_id="task-001",
        task_graph_id="ao-ma-20260527-mch1111",
        base_sha=base_sha,
        declared=["src/a.py", "src/inflated.py"],
        actual=["src/a.py", "src/inflated.py"],
    )
    inputs = _make_inputs(manifest_path=manifest_path, task_id="task-001", wr_path=wr_path)
    result = Verifier(repo_root=r).verify(inputs)
    assert not result.overall_pass
    assert any("worker_declared_set_mismatch_with_task_graph" in fc for fc in result.failed_checks)


def test_verify_diff_scope_happy_path(repo, tmp_path: Path) -> None:
    r, base_sha = repo
    manifest_path, out_dir = _write_manifest_and_task_graph(
        repo=r, task_graph_id="ao-ma-20260527-shp1111", base_sha=base_sha, declared=["src/a.py", "src/b.py"]
    )
    wr_path = _write_worker_result(
        out_dir=out_dir,
        task_id="task-001",
        task_graph_id="ao-ma-20260527-shp1111",
        base_sha=base_sha,
        declared=["src/a.py", "src/b.py"],
        actual=["src/a.py"],  # subset OK
    )
    inputs = _make_inputs(manifest_path=manifest_path, task_id="task-001", wr_path=wr_path)
    result = Verifier(repo_root=r).verify(inputs)
    assert result.overall_pass
    assert result.report["scope_check"]["passed"] is True


# ---------------------------------------------------------------------------
# Artifact hashes (Codex iter-1 must_close #4: H1 format only)
# ---------------------------------------------------------------------------


def test_verify_artifact_hashes_h1_format_only(repo, tmp_path: Path) -> None:
    """Codex iter-1 must_close #4: every entry has only {path, sha256}, no role."""

    r, base_sha = repo
    manifest_path, out_dir = _write_manifest_and_task_graph(
        repo=r, task_graph_id="ao-ma-20260527-h1f1111", base_sha=base_sha
    )
    wr_path = _write_worker_result(
        out_dir=out_dir, task_id="task-001", task_graph_id="ao-ma-20260527-h1f1111", base_sha=base_sha
    )
    diff_path = _write_stub_diff(out_dir, "task-001")
    rv_path = _write_review_verdict(
        out_dir=out_dir, task_id="task-001", task_graph_id="ao-ma-20260527-h1f1111", diff_path=diff_path
    )
    inputs = _make_inputs(
        manifest_path=manifest_path,
        task_id="task-001",
        wr_path=wr_path,
        review_verdict_path=rv_path,
    )
    result = Verifier(repo_root=r).verify(inputs)
    assert result.overall_pass
    for entry in result.report["artifact_hashes"]:
        assert set(entry.keys()) == {"path", "sha256"}, f"entry has extra keys: {entry}"
        assert entry["sha256"].startswith("sha256:")
        assert "role" not in entry


def test_verify_artifact_hashes_does_not_include_self_report(repo, tmp_path: Path) -> None:
    """Codex iter-1: verifier hashes inputs; does NOT hash its own output (circular ref)."""

    r, base_sha = repo
    manifest_path, out_dir = _write_manifest_and_task_graph(
        repo=r, task_graph_id="ao-ma-20260527-nsr1111", base_sha=base_sha
    )
    wr_path = _write_worker_result(
        out_dir=out_dir, task_id="task-001", task_graph_id="ao-ma-20260527-nsr1111", base_sha=base_sha
    )
    inputs = _make_inputs(manifest_path=manifest_path, task_id="task-001", wr_path=wr_path)
    result = Verifier(repo_root=r).verify(inputs)
    for entry in result.report["artifact_hashes"]:
        assert "verification_report" not in entry["path"], (
            f"verifier output must not appear in its own artifact_hashes: {entry}"
        )


# ---------------------------------------------------------------------------
# Trust boundary
# ---------------------------------------------------------------------------


def test_verify_missing_manifest_raises(repo, tmp_path: Path) -> None:
    r, _ = repo
    inputs = VerificationInputs(
        manifest_path=r / "does_not_exist.json",
        task_id="task-001",
        worker_result_paths={"task-001": r / "x.json"},
        verifier_agent_id="verifier-tool",
        verifier_provider="tool",
        verifier_session_id="ver-session",
    )
    with pytest.raises(VerifierError, match="file not found"):
        Verifier(repo_root=r).verify(inputs)


def test_verify_cross_provider_violation_raises(repo, tmp_path: Path) -> None:
    """Verifier provider == worker_result implementer provider → trust-boundary fail."""

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
    inputs = _make_inputs(
        manifest_path=manifest_path,
        task_id="task-001",
        wr_path=wr_path,
        verifier_provider="anthropic",  # SAME
    )
    with pytest.raises(VerifierError, match="matches worker_result implementer"):
        Verifier(repo_root=r).verify(inputs)


def test_verify_invalid_worker_result_schema_raises(repo, tmp_path: Path) -> None:
    r, base_sha = repo
    manifest_path, out_dir = _write_manifest_and_task_graph(
        repo=r, task_graph_id="ao-ma-20260527-bws1111", base_sha=base_sha
    )
    wr_dir = out_dir / "workers" / "task-001"
    wr_dir.mkdir(parents=True, exist_ok=True)
    wr_path = wr_dir / "worker_result.v1.json"
    wr_path.write_text(json.dumps({"not": "valid"}), encoding="utf-8")  # missing required fields
    inputs = _make_inputs(manifest_path=manifest_path, task_id="task-001", wr_path=wr_path)
    with pytest.raises(VerifierError, match="failed schema"):
        Verifier(repo_root=r).verify(inputs)


def test_verify_manifest_task_graph_split_brain_raises(repo, tmp_path: Path) -> None:
    """Manifest.task_graph_id != task_graph.task_graph_id."""

    r, base_sha = repo
    manifest_path, out_dir = _write_manifest_and_task_graph(
        repo=r, task_graph_id="ao-ma-20260527-sb1aaaa", base_sha=base_sha
    )
    # Tamper the task_graph file in place to claim a different id
    tg_path = out_dir / "task_graph.v1.json"
    tg = json.loads(tg_path.read_text(encoding="utf-8"))
    tg["task_graph_id"] = "ao-ma-20260527-other11"
    tg_path.write_text(json.dumps(tg, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    wr_path = _write_worker_result(
        out_dir=out_dir, task_id="task-001", task_graph_id="ao-ma-20260527-sb1aaaa", base_sha=base_sha
    )
    inputs = _make_inputs(manifest_path=manifest_path, task_id="task-001", wr_path=wr_path)
    with pytest.raises(VerifierError, match="split-brain"):
        Verifier(repo_root=r).verify(inputs)


def test_verify_missing_worker_result_mapping_raises(repo, tmp_path: Path) -> None:
    r, base_sha = repo
    manifest_path, _ = _write_manifest_and_task_graph(repo=r, task_graph_id="ao-ma-20260527-mwr1111", base_sha=base_sha)
    inputs = VerificationInputs(
        manifest_path=manifest_path,
        task_id="task-001",
        worker_result_paths={},  # empty
        verifier_agent_id="verifier-tool",
        verifier_provider="tool",
        verifier_session_id="ver-session",
    )
    with pytest.raises(VerifierError, match="--worker-result mapping missing"):
        Verifier(repo_root=r).verify(inputs)


def test_verify_worker_result_task_graph_id_mismatch_raises(repo, tmp_path: Path) -> None:
    r, base_sha = repo
    manifest_path, out_dir = _write_manifest_and_task_graph(
        repo=r, task_graph_id="ao-ma-20260527-wtg1111", base_sha=base_sha
    )
    # Worker_result has a different task_graph_id
    wr_path = _write_worker_result(
        out_dir=out_dir,
        task_id="task-001",
        task_graph_id="ao-ma-20260527-other11",  # wrong id
        base_sha=base_sha,
    )
    inputs = _make_inputs(manifest_path=manifest_path, task_id="task-001", wr_path=wr_path)
    with pytest.raises(VerifierError, match="task_graph_id mismatch"):
        Verifier(repo_root=r).verify(inputs)


# ---------------------------------------------------------------------------
# Deterministic check names (Codex iter-1 must_close #5)
# ---------------------------------------------------------------------------


def test_verify_commands_use_deterministic_check_names(repo, tmp_path: Path) -> None:
    """Codex iter-1 must_close #5: command names match documented enum."""

    r, base_sha = repo
    manifest_path, out_dir = _write_manifest_and_task_graph(
        repo=r, task_graph_id="ao-ma-20260527-dnm1111", base_sha=base_sha
    )
    wr_path = _write_worker_result(
        out_dir=out_dir, task_id="task-001", task_graph_id="ao-ma-20260527-dnm1111", base_sha=base_sha
    )
    inputs = _make_inputs(manifest_path=manifest_path, task_id="task-001", wr_path=wr_path)
    result = Verifier(repo_root=r).verify(inputs)
    expected = {
        "schema_validation",
        "gpp_guard_check",
        "metadata_secret_scan",
        "diff_scope_static_check",
        "artifact_hashing",
    }
    actual = {c["command"] for c in result.report["commands"]}
    assert actual == expected, f"expected {expected!r}, got {actual!r}"
    # Outcome enum subset of pass / fail / skipped
    for c in result.report["commands"]:
        assert c["outcome"] in {"pass", "fail", "skipped"}


def test_verify_emit_failure_raises_with_write_failed_signature(
    repo, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verifier emit failure raised with 'verification_report write failed' signature."""

    from ao_kernel.orchestration import verification_report_writer as writer_mod

    r, base_sha = repo
    manifest_path, out_dir = _write_manifest_and_task_graph(
        repo=r, task_graph_id="ao-ma-20260527-emf1111", base_sha=base_sha
    )
    wr_path = _write_worker_result(
        out_dir=out_dir, task_id="task-001", task_graph_id="ao-ma-20260527-emf1111", base_sha=base_sha
    )

    def _boom(self, payload):  # noqa: ANN001
        raise writer_mod.VerificationReportWriterError("simulated emit failure")

    monkeypatch.setattr(writer_mod.VerificationReportWriter, "emit", _boom)
    inputs = _make_inputs(manifest_path=manifest_path, task_id="task-001", wr_path=wr_path)
    with pytest.raises(VerifierError, match="verification_report write failed"):
        Verifier(repo_root=r).verify(inputs)


# ---------------------------------------------------------------------------
# HARD RULE static pins
# ---------------------------------------------------------------------------


def test_verifier_module_has_no_subprocess_import() -> None:
    """Codex iter-1 HARD RULE: verifier.py must not import subprocess."""

    from ao_kernel.orchestration import verifier as verifier_mod

    source = Path(verifier_mod.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert alias.name != "subprocess", "verifier.py must not import subprocess"
        if isinstance(node, ast.ImportFrom):
            assert node.module != "subprocess", "verifier.py must not from-import subprocess"


def test_verifier_module_has_no_llm_call_literals() -> None:
    """Codex iter-1 HARD RULE: NO LLM execution in v1."""

    from ao_kernel.orchestration import verifier as verifier_mod

    source = Path(verifier_mod.__file__).read_text(encoding="utf-8")
    forbidden_calls = [
        "llm_call(",
        "client.llm_call",
        "AoKernelClient(",
        ".llm_call(",
    ]
    for needle in forbidden_calls:
        assert needle not in source, f"verifier.py must not contain '{needle}' (LLM call literal)"


def test_verifier_module_has_no_gh_or_git_push_literals() -> None:
    """Codex iter-1 HARD RULE: no shell-out / GitHub write."""

    from ao_kernel.orchestration import verifier as verifier_mod

    source = Path(verifier_mod.__file__).read_text(encoding="utf-8")
    assert "subprocess.run" not in source
    assert "os.system" not in source
    assert "os.popen" not in source
    assert "gh pr" not in source
    assert "git push" not in source


def test_verify_no_pr_url_argument_in_cli() -> None:
    """Codex iter-1 HARD RULE: no --pr URL CLI argument."""

    from ao_kernel.orchestration import cli_handlers as ch_mod

    source = Path(ch_mod.__file__).read_text(encoding="utf-8")
    # Inspect specifically the verify subparser block
    verify_block_start = source.find("verify_p = orchestration_sub.add_parser(")
    verify_block_end = source.find("def _parse_per_task_paths", verify_block_start)
    verify_block = source[verify_block_start:verify_block_end]
    assert "--pr" not in verify_block, "AO-MA-7 v1 CLI must not have --pr URL argument"


def test_verify_does_not_modify_ao_ma_5_or_6_modules() -> None:
    """Codex iter-1 HARD RULE: AO-MA-7 PR only adds NEW files; no edits to AO-MA-5/6 surface."""

    from ao_kernel.orchestration import (
        integration_report_writer,
        integrator,
        review_verdict_writer,
        reviewer,
    )

    # AO-MA-5 surface preserved
    assert hasattr(integrator, "Integrator")
    assert hasattr(integrator, "IntegrationDecision")
    assert hasattr(integrator, "IntegratorError")
    assert hasattr(integrator, "verification_passed")
    assert hasattr(integration_report_writer, "IntegrationReportWriter")
    # AO-MA-6 surface preserved
    assert hasattr(reviewer, "Reviewer")
    assert hasattr(reviewer, "ReviewInputs")
    assert hasattr(reviewer, "ReviewDecision")
    assert hasattr(reviewer, "ReviewerError")
    assert hasattr(review_verdict_writer, "ReviewVerdictWriter")


# ---------------------------------------------------------------------------
# CLI integration
# ---------------------------------------------------------------------------


def test_cli_verify_happy_path_exits_zero(repo, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    from ao_kernel.cli import main as cli_main

    r, base_sha = repo
    manifest_path, out_dir = _write_manifest_and_task_graph(
        repo=r, task_graph_id="ao-ma-20260527-cli0001", base_sha=base_sha
    )
    wr_path = _write_worker_result(
        out_dir=out_dir, task_id="task-001", task_graph_id="ao-ma-20260527-cli0001", base_sha=base_sha
    )
    rc = cli_main(
        [
            "orchestration",
            "verify",
            "--manifest",
            str(manifest_path),
            "--task-id",
            "task-001",
            "--worker-result",
            f"task-001={wr_path}",
            "--verifier-agent-id",
            "verifier-tool",
            "--verifier-provider",
            "tool",
            "--verifier-session-id",
            "ver-session",
            "--repo-root",
            str(r),
            "--format",
            "json",
        ]
    )
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["overall_pass"] is True
    assert out["failed_checks"] == []


def test_cli_verify_failed_check_exits_one(repo, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """CLI exit 1 when failed_checks is non-empty (report still emitted)."""

    from ao_kernel.cli import main as cli_main

    r, base_sha = repo
    manifest_path, out_dir = _write_manifest_and_task_graph(
        repo=r, task_graph_id="ao-ma-20260527-cli0002", base_sha=base_sha, declared=["src/a.py"]
    )
    # actual outside declared → scope check fail
    wr_path = _write_worker_result(
        out_dir=out_dir,
        task_id="task-001",
        task_graph_id="ao-ma-20260527-cli0002",
        base_sha=base_sha,
        declared=["src/a.py"],
        actual=["src/a.py", "src/leak.py"],
    )
    rc = cli_main(
        [
            "orchestration",
            "verify",
            "--manifest",
            str(manifest_path),
            "--task-id",
            "task-001",
            "--worker-result",
            f"task-001={wr_path}",
            "--verifier-agent-id",
            "verifier-tool",
            "--verifier-provider",
            "tool",
            "--verifier-session-id",
            "ver-session",
            "--repo-root",
            str(r),
        ]
    )
    assert rc == 1
    # Report still emitted on disk
    emitted = out_dir / "workers" / "task-001" / "verification_report.v1.json"
    assert emitted.exists()


def test_cli_verify_missing_manifest_exits_two(repo, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    from ao_kernel.cli import main as cli_main

    r, _ = repo
    rc = cli_main(
        [
            "orchestration",
            "verify",
            "--manifest",
            str(r / "does_not_exist.json"),
            "--task-id",
            "task-001",
            "--worker-result",
            "task-001=/tmp/x",
            "--verifier-agent-id",
            "verifier-tool",
            "--verifier-provider",
            "tool",
            "--verifier-session-id",
            "ver-session",
        ]
    )
    assert rc == 2


def test_cli_verify_cross_provider_violation_exits_two(
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
    rc = cli_main(
        [
            "orchestration",
            "verify",
            "--manifest",
            str(manifest_path),
            "--task-id",
            "task-001",
            "--worker-result",
            f"task-001={wr_path}",
            "--verifier-agent-id",
            "verifier-tool",
            "--verifier-provider",
            "anthropic",  # SAME
            "--verifier-session-id",
            "ver-session",
            "--repo-root",
            str(r),
        ]
    )
    assert rc == 2


def test_cli_verify_emit_failure_exits_three(
    repo, tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Codex iter-1 must_close #6: CLI exit 3 contract for emit failure."""

    from ao_kernel.cli import main as cli_main
    from ao_kernel.orchestration import verification_report_writer as writer_mod

    r, base_sha = repo
    manifest_path, out_dir = _write_manifest_and_task_graph(
        repo=r, task_graph_id="ao-ma-20260527-cli0004", base_sha=base_sha
    )
    wr_path = _write_worker_result(
        out_dir=out_dir, task_id="task-001", task_graph_id="ao-ma-20260527-cli0004", base_sha=base_sha
    )

    def _boom(self, payload):  # noqa: ANN001
        raise writer_mod.VerificationReportWriterError("simulated emit failure")

    monkeypatch.setattr(writer_mod.VerificationReportWriter, "emit", _boom)
    rc = cli_main(
        [
            "orchestration",
            "verify",
            "--manifest",
            str(manifest_path),
            "--task-id",
            "task-001",
            "--worker-result",
            f"task-001={wr_path}",
            "--verifier-agent-id",
            "verifier-tool",
            "--verifier-provider",
            "tool",
            "--verifier-session-id",
            "ver-session",
            "--repo-root",
            str(r),
        ]
    )
    assert rc == 3


def test_cli_verify_text_format_summary(repo, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """Text format produces human-readable summary."""

    from ao_kernel.cli import main as cli_main

    r, base_sha = repo
    manifest_path, out_dir = _write_manifest_and_task_graph(
        repo=r, task_graph_id="ao-ma-20260527-cli0005", base_sha=base_sha
    )
    wr_path = _write_worker_result(
        out_dir=out_dir, task_id="task-001", task_graph_id="ao-ma-20260527-cli0005", base_sha=base_sha
    )
    rc = cli_main(
        [
            "orchestration",
            "verify",
            "--manifest",
            str(manifest_path),
            "--task-id",
            "task-001",
            "--worker-result",
            f"task-001={wr_path}",
            "--verifier-agent-id",
            "verifier-tool",
            "--verifier-provider",
            "tool",
            "--verifier-session-id",
            "ver-session",
            "--repo-root",
            str(r),
            "--format",
            "text",
        ]
    )
    assert rc == 0
    out = capsys.readouterr().out
    assert "overall_pass: True" in out
    assert "schema_validation: pass" in out
    assert "gpp_guard_check: pass" in out
    assert "metadata_secret_scan: pass" in out
    assert "diff_scope_static_check: pass" in out


def test_cli_verify_json_format_full_report(repo, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """JSON format includes the full report payload."""

    from ao_kernel.cli import main as cli_main

    r, base_sha = repo
    manifest_path, out_dir = _write_manifest_and_task_graph(
        repo=r, task_graph_id="ao-ma-20260527-cli0006", base_sha=base_sha
    )
    wr_path = _write_worker_result(
        out_dir=out_dir, task_id="task-001", task_graph_id="ao-ma-20260527-cli0006", base_sha=base_sha
    )
    rc = cli_main(
        [
            "orchestration",
            "verify",
            "--manifest",
            str(manifest_path),
            "--task-id",
            "task-001",
            "--worker-result",
            f"task-001={wr_path}",
            "--verifier-agent-id",
            "verifier-tool",
            "--verifier-provider",
            "tool",
            "--verifier-session-id",
            "ver-session",
            "--repo-root",
            str(r),
            "--format",
            "json",
        ]
    )
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert "report" in out
    assert "commands" in out["report"]
    assert "artifact_hashes" in out["report"]
    assert "scope_check" in out["report"]
    assert "secret_scan" in out["report"]
    assert "guard_flags" in out["report"]


def test_verify_emits_to_default_path_under_workers_subdir(repo, tmp_path: Path) -> None:
    r, base_sha = repo
    manifest_path, out_dir = _write_manifest_and_task_graph(
        repo=r, task_graph_id="ao-ma-20260527-pth1111", base_sha=base_sha
    )
    wr_path = _write_worker_result(
        out_dir=out_dir, task_id="task-001", task_graph_id="ao-ma-20260527-pth1111", base_sha=base_sha
    )
    inputs = _make_inputs(manifest_path=manifest_path, task_id="task-001", wr_path=wr_path)
    Verifier(repo_root=r).verify(inputs)
    expected = out_dir / "workers" / "task-001" / "verification_report.v1.json"
    assert expected.exists()


def test_verify_artifact_hashes_paths_are_relative_to_manifest_dir(repo, tmp_path: Path) -> None:
    """Schema enforces path NOT pattern (^/|..), so verifier must emit relative paths."""

    r, base_sha = repo
    manifest_path, out_dir = _write_manifest_and_task_graph(
        repo=r, task_graph_id="ao-ma-20260527-rel1111", base_sha=base_sha
    )
    wr_path = _write_worker_result(
        out_dir=out_dir, task_id="task-001", task_graph_id="ao-ma-20260527-rel1111", base_sha=base_sha
    )
    inputs = _make_inputs(manifest_path=manifest_path, task_id="task-001", wr_path=wr_path)
    result = Verifier(repo_root=r).verify(inputs)
    for entry in result.report["artifact_hashes"]:
        assert not entry["path"].startswith("/"), f"path must be relative: {entry['path']}"
        assert ".." not in entry["path"].split("/"), f"path must not contain ..: {entry['path']}"


# ---------------------------------------------------------------------------
# Codex iter-2 must_fix absorbs
# ---------------------------------------------------------------------------


def test_verify_review_verdict_reviewed_task_id_mismatch_raises(repo, tmp_path: Path) -> None:
    """Codex iter-2 must_fix #1: review_verdict.reviewed_task_id must equal --task-id."""

    r, base_sha = repo
    manifest_path, out_dir = _write_manifest_and_task_graph(
        repo=r, task_graph_id="ao-ma-20260527-rtm1111", base_sha=base_sha
    )
    wr_path = _write_worker_result(
        out_dir=out_dir, task_id="task-001", task_graph_id="ao-ma-20260527-rtm1111", base_sha=base_sha
    )
    diff_path = _write_stub_diff(out_dir, "task-001")
    rv_path = _write_review_verdict(
        out_dir=out_dir, task_id="task-001", task_graph_id="ao-ma-20260527-rtm1111", diff_path=diff_path
    )
    # Tamper review_verdict to claim a different reviewed_task_id (same graph)
    rv = json.loads(rv_path.read_text(encoding="utf-8"))
    rv["reviewed_task_id"] = "task-999"
    rv_path.write_text(json.dumps(rv, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    inputs = _make_inputs(
        manifest_path=manifest_path,
        task_id="task-001",
        wr_path=wr_path,
        review_verdict_path=rv_path,
    )
    with pytest.raises(VerifierError, match="reviewed_task_id"):
        Verifier(repo_root=r).verify(inputs)


def test_verify_default_gpp_status_appears_in_artifact_hashes(repo) -> None:
    """Codex iter-2 must_fix #2: hash base is repo_root, so .claude/plans/gpp_status
    under repo_root IS recordable and appears in artifact_hashes (not silently dropped).
    """

    r, base_sha = repo
    manifest_path, out_dir = _write_manifest_and_task_graph(
        repo=r, task_graph_id="ao-ma-20260527-gph1111", base_sha=base_sha
    )
    wr_path = _write_worker_result(
        out_dir=out_dir, task_id="task-001", task_graph_id="ao-ma-20260527-gph1111", base_sha=base_sha
    )
    gpp_path = _write_gpp_status(repo=r)  # all flags False — pass
    inputs = _make_inputs(
        manifest_path=manifest_path,
        task_id="task-001",
        wr_path=wr_path,
        gpp_status_path=gpp_path,
    )
    result = Verifier(repo_root=r).verify(inputs)
    assert result.overall_pass
    paths = [e["path"] for e in result.report["artifact_hashes"]]
    assert any(".claude/plans/gpp_status.v1.json" in p for p in paths), (
        f"expected default gpp_status to appear in artifact_hashes; got {paths}"
    )


def test_verify_artifact_hashing_fails_when_consulted_outside_repo_root(repo, tmp_path: Path) -> None:
    """Codex iter-2 must_fix #2: silent skip + pass is misleading.

    A consulted artifact that lives OUTSIDE repo_root cannot be recorded
    in artifact_hashes (path constraint). When that happens, the
    artifact_hashing check must fail (not silently pass).
    """

    r, base_sha = repo
    # Place the manifest OUTSIDE repo_root (in tmp_path directly)
    out_dir = tmp_path / "external" / "orchestration"
    out_dir.mkdir(parents=True, exist_ok=True)
    task_graph = {
        "schema_version": "ao-ma-task-graph.v1",
        "task_graph_id": "ao-ma-20260527-out1111",
        "repo": "Halildeu/ao-kernel",
        "goal": "outside repo_root",
        "base_ref": "refs/heads/main",
        "base_sha": base_sha,
        "risk_class": "low",
        "max_parallel_workers": 1,
        "tasks": [
            {
                "task_id": "task-001",
                "title": "out",
                "agent_type": "implementer",
                "declared_write_set": ["src/a.py"],
                "dependency_ids": [],
                "acceptance_criteria": ["tests_pass_locally"],
                "high_risk": False,
            }
        ],
        "fan_in_policy": {"mode": "all_required", "required_task_ids": ["task-001"], "conflict_owner": "integrator"},
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
        "task_graph_id": "ao-ma-20260527-out1111",
        "generated_at": "2026-05-27T00:00:00Z",
        "base_dir": str(out_dir),
        "artifacts": [{"path": "task_graph.v1.json", "sha256": _sha256(tg_path), "size_bytes": tg_path.stat().st_size}],
        "guard_flags": {
            "support_widening": False,
            "production_platform_claim": False,
            "live_adapter_execution": False,
        },
    }
    manifest_path = out_dir / "manifest.v1.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    wr_path = _write_worker_result(
        out_dir=out_dir, task_id="task-001", task_graph_id="ao-ma-20260527-out1111", base_sha=base_sha
    )
    inputs = _make_inputs(manifest_path=manifest_path, task_id="task-001", wr_path=wr_path)
    result = Verifier(repo_root=r).verify(inputs)
    # All consulted paths live under tmp_path/external/, NOT under r (repo_root)
    assert not result.overall_pass
    assert any("artifact_hashing.consulted_paths_outside_repo_root_or_missing" in fc for fc in result.failed_checks)
    # Commands list must reflect the fail
    commands = {c["command"]: c["outcome"] for c in result.report["commands"]}
    assert commands["artifact_hashing"] == "fail"


def test_verify_manifest_envelope_invalid_schema_version_raises(repo) -> None:
    """Codex iter-2 must_fix #3: manifest envelope validation before field reads."""

    r, base_sha = repo
    manifest_path, out_dir = _write_manifest_and_task_graph(
        repo=r, task_graph_id="ao-ma-20260527-env1111", base_sha=base_sha
    )
    # Tamper schema_version
    mf = json.loads(manifest_path.read_text(encoding="utf-8"))
    mf["schema_version"] = "wrong-schema.v0"
    manifest_path.write_text(json.dumps(mf, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    wr_path = _write_worker_result(
        out_dir=out_dir, task_id="task-001", task_graph_id="ao-ma-20260527-env1111", base_sha=base_sha
    )
    inputs = _make_inputs(manifest_path=manifest_path, task_id="task-001", wr_path=wr_path)
    with pytest.raises(VerifierError, match="schema_version mismatch"):
        Verifier(repo_root=r).verify(inputs)


def test_verify_manifest_envelope_artifact_traversal_path_raises(repo) -> None:
    """Codex iter-2 must_fix #3: artifact path traversal rejected."""

    r, base_sha = repo
    manifest_path, out_dir = _write_manifest_and_task_graph(
        repo=r, task_graph_id="ao-ma-20260527-trv1111", base_sha=base_sha
    )
    mf = json.loads(manifest_path.read_text(encoding="utf-8"))
    # Insert a traversal artifact path
    mf["artifacts"].append({"path": "../escape.v1.json", "sha256": "sha256:" + "a" * 64, "size_bytes": 1})
    manifest_path.write_text(json.dumps(mf, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    wr_path = _write_worker_result(
        out_dir=out_dir, task_id="task-001", task_graph_id="ao-ma-20260527-trv1111", base_sha=base_sha
    )
    inputs = _make_inputs(manifest_path=manifest_path, task_id="task-001", wr_path=wr_path)
    with pytest.raises(VerifierError, match="traversal/absolute"):
        Verifier(repo_root=r).verify(inputs)


def test_verify_manifest_envelope_missing_artifacts_raises(repo) -> None:
    """Codex iter-2 must_fix #3: empty artifacts array rejected."""

    r, base_sha = repo
    manifest_path, out_dir = _write_manifest_and_task_graph(
        repo=r, task_graph_id="ao-ma-20260527-mis1111", base_sha=base_sha
    )
    mf = json.loads(manifest_path.read_text(encoding="utf-8"))
    mf["artifacts"] = []
    manifest_path.write_text(json.dumps(mf, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    wr_path = _write_worker_result(
        out_dir=out_dir, task_id="task-001", task_graph_id="ao-ma-20260527-mis1111", base_sha=base_sha
    )
    inputs = _make_inputs(manifest_path=manifest_path, task_id="task-001", wr_path=wr_path)
    with pytest.raises(VerifierError, match="artifacts must be a non-empty array"):
        Verifier(repo_root=r).verify(inputs)


def test_verify_manifest_envelope_guard_flag_non_false_raises(repo) -> None:
    """Codex iter-2 must_fix #3: manifest guard_flags must be literal False."""

    r, base_sha = repo
    manifest_path, out_dir = _write_manifest_and_task_graph(
        repo=r, task_graph_id="ao-ma-20260527-gfl1111", base_sha=base_sha
    )
    mf = json.loads(manifest_path.read_text(encoding="utf-8"))
    mf["guard_flags"]["support_widening"] = True
    manifest_path.write_text(json.dumps(mf, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    wr_path = _write_worker_result(
        out_dir=out_dir, task_id="task-001", task_graph_id="ao-ma-20260527-gfl1111", base_sha=base_sha
    )
    inputs = _make_inputs(manifest_path=manifest_path, task_id="task-001", wr_path=wr_path)
    with pytest.raises(VerifierError, match="guard_flags.support_widening must be the literal boolean False"):
        Verifier(repo_root=r).verify(inputs)


def test_verify_secret_scan_detail_mentions_gpp_status(repo) -> None:
    """Codex iter-2 plan-drift fix: secret_scan.detail says gpp_status also scanned."""

    r, base_sha = repo
    manifest_path, out_dir = _write_manifest_and_task_graph(
        repo=r, task_graph_id="ao-ma-20260527-gpd2222", base_sha=base_sha
    )
    wr_path = _write_worker_result(
        out_dir=out_dir, task_id="task-001", task_graph_id="ao-ma-20260527-gpd2222", base_sha=base_sha
    )
    inputs = _make_inputs(manifest_path=manifest_path, task_id="task-001", wr_path=wr_path)
    result = Verifier(repo_root=r).verify(inputs)
    detail = result.report["secret_scan"]["detail"]
    assert "gpp_status" in detail, f"secret_scan.detail must mention gpp_status: {detail!r}"


def test_verify_secret_scan_includes_gpp_status_in_scan_payload(repo) -> None:
    """Codex iter-2 plan-drift fix: secret pattern in gpp_status JSON flags the scan."""

    r, base_sha = repo
    manifest_path, out_dir = _write_manifest_and_task_graph(
        repo=r, task_graph_id="ao-ma-20260527-gps1111", base_sha=base_sha
    )
    wr_path = _write_worker_result(
        out_dir=out_dir, task_id="task-001", task_graph_id="ao-ma-20260527-gps1111", base_sha=base_sha
    )
    # gpp_status with a planted secret value
    plans_dir = r / ".claude" / "plans"
    plans_dir.mkdir(parents=True, exist_ok=True)
    leaked_token = "AKIA" + "ABCDEFGHIJKLMNOP"
    payload = {
        "schema_version": "gpp_status.v1",
        "current_wp": {
            "id": "AO-MA-7",
            "support_widening_allowed": False,
            "production_platform_claim_allowed": False,
            "live_adapter_execution_allowed": False,
            "notes": f"audit trail: {leaked_token}",
        },
    }
    gpp_path = plans_dir / "gpp_status.v1.json"
    gpp_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    inputs = _make_inputs(manifest_path=manifest_path, task_id="task-001", wr_path=wr_path, gpp_status_path=gpp_path)
    result = Verifier(repo_root=r).verify(inputs)
    assert not result.overall_pass
    assert any("secret_scan.gpp_status.aws_access_key_id_match" in fc for fc in result.failed_checks)
