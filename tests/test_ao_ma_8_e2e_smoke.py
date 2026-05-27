"""AO-MA-8 end-to-end smoke (shadow mode; evidence class).

Codex thread `019e6a30-1f93-7482-bf5d-bc089d974f26` iter-5 AGREE
(ready_for_impl: true) absorb. Single shared pipeline fixture exercises
AO-MA-3 → AO-MA-4 → AO-MA-4.5 mock surrogate → AO-MA-6 → AO-MA-7 →
AO-MA-5 with deterministic low-risk inputs, then 16 focused assertions
verify each invariant. NO LLM call. NO GitHub write. NO new runtime
surface added by this PR.
"""

from __future__ import annotations

import ast
import json
import os
import subprocess
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from ao_kernel.orchestration.integrator import Integrator
from ao_kernel.orchestration.orchestrator import Orchestrator, SSOTPaths
from ao_kernel.orchestration.reviewer import ReviewInputs, Reviewer
from ao_kernel.orchestration.task_graph_builder import TaskSpec
from ao_kernel.orchestration.verifier import VerificationInputs, Verifier
from ao_kernel.orchestration.worker_runner import WorkerRunner

# Receipt + schema paths (committed in this PR)
_REPO_ROOT = Path(__file__).resolve().parent.parent
_RECEIPT_PATH = _REPO_ROOT / ".claude" / "plans" / "AO-MA-8-E2E-SMOKE-EVIDENCE.v1.json"
_RECEIPT_SCHEMA_PATH = _REPO_ROOT / "ao_kernel" / "defaults" / "schemas" / "ao-ma-8-e2e-smoke-evidence.schema.v1.json"


# ---------------------------------------------------------------------------
# Test-harness helpers (git boundaries per AO-MA-8 plan §Hard stops)
# ---------------------------------------------------------------------------


def _run(cmd: list[str], cwd: Path | None = None) -> str:
    """Run a git/subprocess command and return stdout. Test-harness only;
    no runtime/CLI/Worker subprocess use crosses this boundary (plan §Hard stops).
    """

    completed = subprocess.run(cmd, cwd=cwd, check=True, capture_output=True, text=True, timeout=20)
    return completed.stdout.strip()


def _git_init_repo(repo: Path) -> str:
    _run(["git", "init", "--initial-branch=main", str(repo)])
    _run(["git", "-C", str(repo), "config", "user.email", "test@example.com"])
    _run(["git", "-C", str(repo), "config", "user.name", "test"])
    (repo / "README.md").write_text("initial\n", encoding="utf-8")
    (repo / "src").mkdir(parents=True, exist_ok=True)
    (repo / "src" / "a.py").write_text("def a():\n    return 1\n", encoding="utf-8")
    _run(["git", "-C", str(repo), "add", "README.md", "src/a.py"])
    _run(["git", "-C", str(repo), "commit", "-m", "initial"])
    sha = _run(["git", "-C", str(repo), "rev-parse", "HEAD"])
    _run(["git", "-C", str(repo), "update-ref", "refs/remotes/origin/main", sha])
    return sha


def _write_synthetic_ssot(repo: Path) -> None:
    """AO-MA-3 orchestrator requires AGENTS.md + .claude/plans/gpp_status.v1.json
    with all three promotion flags closed. Plan §gpp_status synthesized under
    tmp repo root so verifier artifact_hashes (repo-relative) can record it
    deterministically.
    """

    (repo / "AGENTS.md").write_text("# AGENTS\nAO-MA-8 smoke synthetic SSOT.\n", encoding="utf-8")
    plans_dir = repo / ".claude" / "plans"
    plans_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": "gpp_status.v1",
        "current_wp": {
            "id": "AO-MA-8-smoke",
            "support_widening_allowed": False,
            "production_platform_claim_allowed": False,
            "live_adapter_execution_allowed": False,
        },
        "support_widening_allowed": False,
        "production_platform_claim_allowed": False,
        "live_adapter_execution_allowed": False,
    }
    (plans_dir / "gpp_status.v1.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def _emit_mock_worker_result(
    *,
    worktree_dir: Path,
    out_dir: Path,
    task_graph_id: str,
    task_id: str,
    declared: list[str],
    base_sha: str,
) -> tuple[Path, str, list[str]]:
    """AO-MA-4.5 surrogate: modify a real file from declared_write_set,
    commit (NO --allow-empty), capture head_sha via rev-parse + actual
    changed file list via ``git diff --name-only base_sha..HEAD``, then
    write a schema-valid worker_result.v1.json into the spawned worktree's
    ``<manifest_dir>/workers/<task_id>/`` directory AFTER the commit.
    Returns ``(worker_result_path, head_sha, actual_changed_files)``.

    No LLM call. No GitHub fetch. Test-harness subprocess (git add/commit/
    rev-parse/diff) allowed per the subprocess boundary in plan §Hard stops.
    """

    # 1. Modify a real file from declared_write_set in the spawned worktree
    target_rel = declared[0]
    target_abs = worktree_dir / target_rel
    target_abs.parent.mkdir(parents=True, exist_ok=True)
    existing = target_abs.read_text(encoding="utf-8") if target_abs.exists() else ""
    target_abs.write_text(existing + "\n# AO-MA-8 surrogate change\n", encoding="utf-8")

    # 2. Commit (NO --allow-empty)
    _run(["git", "-C", str(worktree_dir), "add", target_rel])
    _run(["git", "-C", str(worktree_dir), "commit", "-m", f"AO-MA-8 surrogate change for {task_id}"])

    # 3. head_sha + actual_changed via subprocess (boundary: test-harness only)
    head_sha = _run(["git", "-C", str(worktree_dir), "rev-parse", "HEAD"])
    actual_changed = [
        line.strip()
        for line in _run(["git", "-C", str(worktree_dir), "diff", "--name-only", f"{base_sha}..HEAD"]).splitlines()
        if line.strip()
    ]

    # 4. Write schema-valid worker_result AFTER commit
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
            "provider": "anthropic",
            "session_id": f"ao-ma-8-smoke-{task_graph_id}",
        },
        "base_ref": "refs/heads/main",
        "base_sha": base_sha,
        "head_ref": f"codex/ao-ma-{task_graph_id}/{task_id}",
        "head_sha": head_sha,
        "declared_write_set": declared,
        "actual_changed_files": actual_changed,
        "summary": "AO-MA-8 e2e smoke surrogate implementer",
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
    return wr_path, head_sha, actual_changed


def _emit_findings_json(tmp_path: Path) -> Path:
    findings = [{"severity": "info", "title": "AO-MA-8 smoke finding", "body": "no blockers"}]
    p = tmp_path / "findings.json"
    p.write_text(json.dumps(findings, indent=2), encoding="utf-8")
    return p


# ---------------------------------------------------------------------------
# Single shared pipeline fixture (Codex iter-2 nice-to-have #3)
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def pipeline_run(tmp_path_factory: pytest.TempPathFactory) -> Iterator[dict[str, Any]]:
    """Build the AO-MA-8 e2e shadow-mode pipeline ONCE, then reuse for
    16 focused assertions across tests. Test perf < 5s target.
    """

    tmp_path = tmp_path_factory.mktemp("ao_ma_8_smoke")
    repo = tmp_path / "repo"

    # 1. Synthetic origin/main (Codex iter-1 must_close #4 shadow_mode pin)
    base_sha = _git_init_repo(repo)
    _write_synthetic_ssot(repo)

    # Codex post-impl iter-1 must_fix #1 absorb: capture gpp_status BEFORE
    # the pipeline runs (not after). Comparing post-vs-post would be
    # tautological; we need pre-vs-post byte identity to prove no mutation.
    gpp_status_pre = (repo / ".claude" / "plans" / "gpp_status.v1.json").read_bytes()

    # 2. AO-MA-3: Orchestrator.plan() → task_graph + manifest emit
    task_id = "task-001"
    declared = ["src/a.py"]
    out_dir = repo / ".ao" / "orchestration"
    ssot = SSOTPaths.default(repo)
    orchestrator = Orchestrator(repo_root=repo, ssot=ssot, output_dir=None)
    manifest = orchestrator.plan(
        goal="AO-MA-8 e2e smoke",
        declared_specs=[
            TaskSpec(
                task_id=task_id,
                description="AO-MA-8 e2e smoke surrogate",
                write_paths=list(declared),
                depends_on=[],
            )
        ],
        base_sha=base_sha,
        base_ref="refs/heads/main",
        repo="Halildeu/ao-kernel",
    )
    task_graph_id = manifest["task_graph_id"]
    real_out_dir = out_dir / task_graph_id
    manifest_path = real_out_dir / "manifest.v1.json"
    assert manifest_path.exists(), f"orchestrator did not emit manifest at {manifest_path}"

    # 3. AO-MA-4: WorkerRunner.spawn() → runner_report + worktree
    worktree_base = tmp_path / "worktrees"
    runner = WorkerRunner(repo_root=repo, worktree_base=worktree_base)
    runner_report = runner.spawn(manifest_path=manifest_path)
    workers = runner_report["workers"]
    worker_entry = next(w for w in workers if w["task_id"] == task_id)
    worktree_dir = Path(worker_entry["actual_worktree"])
    assert worktree_dir.exists(), f"worker_runner did not create worktree {worktree_dir}"

    # 4. AO-MA-4.5 surrogate: mock implementer commits + emits worker_result
    wr_path, head_sha, actual_changed = _emit_mock_worker_result(
        worktree_dir=worktree_dir,
        out_dir=real_out_dir,
        task_graph_id=task_graph_id,
        task_id=task_id,
        declared=declared,
        base_sha=base_sha,
    )

    # 5. AO-MA-6: Reviewer.review() — use real git diff as pr_diff artifact
    diff_text = _run(["git", "-C", str(worktree_dir), "diff", f"{base_sha}..HEAD"])
    pr_diff_path = real_out_dir / "workers" / task_id / "pr_diff.patch"
    pr_diff_path.write_text(diff_text, encoding="utf-8")
    findings_path = _emit_findings_json(tmp_path)
    reviewer = Reviewer(repo_root=repo)
    review_decision = reviewer.review(
        ReviewInputs(
            manifest_path=manifest_path,
            task_id=task_id,
            worker_result_paths={task_id: wr_path},
            reviewer_agent_id="codex-reviewer",
            reviewer_provider="openai",
            reviewer_session_id="ao-ma-8-smoke-reviewer",
            verdict="AGREE",
            findings_path=findings_path,
            diff_path=pr_diff_path,
        )
    )

    # 6. AO-MA-7: Verifier.verify() — explicit gpp_status_path under tmp repo root
    gpp_status_path = repo / ".claude" / "plans" / "gpp_status.v1.json"
    verifier = Verifier(repo_root=repo)
    verification_result = verifier.verify(
        VerificationInputs(
            manifest_path=manifest_path,
            task_id=task_id,
            worker_result_paths={task_id: wr_path},
            verifier_agent_id="verifier-tool",
            verifier_provider="tool",
            verifier_session_id="ao-ma-8-smoke-verifier",
            review_verdict_path=real_out_dir / "workers" / task_id / "review_verdict.v1.json",
            gpp_status_path=gpp_status_path,
        )
    )

    # 7. AO-MA-5: Integrator.integrate() → integration_report + assembly_plan
    integrator = Integrator(
        repo_root=repo,
        integrator_agent_id="claude-integrator",
        integrator_provider="anthropic",
        integrator_session_id="ao-ma-8-smoke-integrator",
    )
    integration_decision = integrator.integrate(
        manifest_path=manifest_path,
        runner_report_path=None,
        worker_result_paths={task_id: wr_path},
        review_verdict_paths={task_id: real_out_dir / "workers" / task_id / "review_verdict.v1.json"},
        verification_report_paths={task_id: real_out_dir / "workers" / task_id / "verification_report.v1.json"},
    )

    yield {
        "tmp_path": tmp_path,
        "repo": repo,
        "base_sha": base_sha,
        "task_graph_id": task_graph_id,
        "task_id": task_id,
        "declared": declared,
        "manifest": manifest,
        "manifest_path": manifest_path,
        "runner_report": runner_report,
        "worktree_dir": worktree_dir,
        "wr_path": wr_path,
        "head_sha": head_sha,
        "actual_changed": actual_changed,
        "review_decision": review_decision,
        "verification_result": verification_result,
        "integration_decision": integration_decision,
        "gpp_status_path": gpp_status_path,
        "gpp_status_pre": gpp_status_pre,
    }


def _load_receipt() -> dict[str, Any]:
    data: dict[str, Any] = json.loads(_RECEIPT_PATH.read_text(encoding="utf-8"))
    return data


# ---------------------------------------------------------------------------
# 16 focused assertions over the single shared pipeline fixture
# ---------------------------------------------------------------------------


def test_ao_ma_8_e2e_smoke_pipeline_emits_accepted_integration_report(
    pipeline_run: dict[str, Any],
) -> None:
    """Full happy path: 6 stages + IntegrationDecision.overall_status == 'all_accepted'
    + report shape (accepted_worker_results=1, rejected_worker_results=0,
    conflicts=[], assembly_plan>=1).
    """

    decision = pipeline_run["integration_decision"]
    report = decision.report
    assert decision.overall_status == "all_accepted", f"got {decision.overall_status!r}"
    assert len(report["accepted_worker_results"]) == 1
    assert len(report["rejected_worker_results"]) == 0
    assert report["conflicts"] == []
    assert len(report["assembly_plan"]) >= 1


def test_ao_ma_8_e2e_smoke_worker_result_uses_real_local_head_sha(
    pipeline_run: dict[str, Any],
) -> None:
    """head_sha matches git rev-parse HEAD in worktree (no placeholder).
    Codex iter-1 nice-to-have #1 absorb.
    """

    wr = json.loads(pipeline_run["wr_path"].read_text(encoding="utf-8"))
    actual_head = _run(["git", "-C", str(pipeline_run["worktree_dir"]), "rev-parse", "HEAD"])
    assert wr["head_sha"] == actual_head == pipeline_run["head_sha"]
    # Sanity: NOT placeholder hex like 'c'*40
    assert wr["head_sha"] != "c" * 40
    assert wr["head_sha"] != pipeline_run["base_sha"], "head must differ from base after commit"


def test_ao_ma_8_e2e_smoke_actual_changed_files_matches_git_diff_exactly(
    pipeline_run: dict[str, Any],
) -> None:
    """Codex iter-2 must_close #2 absorb + post-impl iter-1 must_fix #2 absorb:
    test independently recomputes ``git diff --name-only base_sha..HEAD`` in
    the worker's worktree and asserts exact set-equality with
    ``worker_result.actual_changed_files``. Does NOT reuse the helper-captured
    value (which would be tautological — comparing helper output to itself).
    """

    wr = json.loads(pipeline_run["wr_path"].read_text(encoding="utf-8"))
    # Independent re-measure: run git diff fresh against the worktree state
    independent_diff = _run(
        [
            "git",
            "-C",
            str(pipeline_run["worktree_dir"]),
            "diff",
            "--name-only",
            f"{pipeline_run['base_sha']}..HEAD",
        ]
    )
    independent_changed = {line.strip() for line in independent_diff.splitlines() if line.strip()}
    actual = set(wr["actual_changed_files"])
    assert actual == independent_changed, (
        f"worker_result.actual_changed_files mismatch with independent git diff: "
        f"worker_result={actual}, fresh_git_diff={independent_changed}"
    )
    # Subset of declared (scope discipline)
    declared = set(wr["declared_write_set"])
    assert actual.issubset(declared)
    # Sanity: independent measurement is non-empty (proves a real commit happened)
    assert independent_changed, "no files changed between base_sha..HEAD — surrogate did not commit"


def test_ao_ma_8_e2e_smoke_cross_provider_chain_intact(pipeline_run: dict[str, Any]) -> None:
    """implementer=anthropic, reviewer=openai, verifier=tool (cross-provider HARD RULE)."""

    wr = json.loads(pipeline_run["wr_path"].read_text(encoding="utf-8"))
    assert wr["worker"]["provider"] == "anthropic"
    rv = pipeline_run["review_decision"].report
    assert rv["reviewer"]["provider"] == "openai"
    vr = pipeline_run["verification_result"].report
    assert vr["verifier"]["provider"] == "tool"
    # No two providers match in the chain
    providers = {wr["worker"]["provider"], rv["reviewer"]["provider"], vr["verifier"]["provider"]}
    assert len(providers) == 3, f"cross-provider chain not distinct: {providers}"


def test_ao_ma_8_e2e_smoke_verifier_overall_pass_no_failed_checks(
    pipeline_run: dict[str, Any],
) -> None:
    """verifier.verify().overall_pass=True; failed_checks=[]; secret_scan.passed; scope_check.passed."""

    result = pipeline_run["verification_result"]
    assert result.overall_pass is True
    assert result.failed_checks == []
    report = result.report
    assert report["secret_scan"]["passed"] is True
    assert report["scope_check"]["passed"] is True


def test_ao_ma_8_e2e_smoke_reviewer_agree_not_force_blocked(pipeline_run: dict[str, Any]) -> None:
    """review_decision.emitted_verdict=AGREE; budget_forced_block=False."""

    decision = pipeline_run["review_decision"]
    assert decision.emitted_verdict == "AGREE"
    assert decision.requested_verdict == "AGREE"
    assert decision.budget_forced_block is False


def test_ao_ma_8_e2e_smoke_integration_report_assembly_plan_length(
    pipeline_run: dict[str, Any],
) -> None:
    """assembly_plan must have at least one entry (Codex iter-1 must_close #4 invariant)."""

    report = pipeline_run["integration_decision"].report
    assert "assembly_plan" in report
    assert len(report["assembly_plan"]) >= 1


def test_ao_ma_8_e2e_smoke_integration_report_conflict_count_zero(
    pipeline_run: dict[str, Any],
) -> None:
    """Single low-risk task → no conflicts expected."""

    report = pipeline_run["integration_decision"].report
    assert report["conflicts"] == []


def test_ao_ma_8_e2e_smoke_all_guard_flags_closed_in_chain(
    pipeline_run: dict[str, Any],
) -> None:
    """guard_flags closed across all 6 produced artifacts."""

    artifacts: list[dict[str, Any]] = [
        pipeline_run["manifest"],
        pipeline_run["runner_report"],
        json.loads(pipeline_run["wr_path"].read_text(encoding="utf-8")),
        pipeline_run["review_decision"].report,
        pipeline_run["verification_result"].report,
        pipeline_run["integration_decision"].report,
    ]
    for artifact in artifacts:
        gf = artifact["guard_flags"]
        assert gf["support_widening"] is False
        assert gf["production_platform_claim"] is False
        assert gf["live_adapter_execution"] is False


def test_ao_ma_8_e2e_smoke_no_assembly_plan_executed(pipeline_run: dict[str, Any]) -> None:
    """Shadow mode pin: assembly_plan persisted in report but NOT invoked.

    Side-effect absence: no remote git push, no gh CLI invocation. We assert
    by checking that the repo's remote refs are unchanged after the pipeline:
    only refs/remotes/origin/main exists (from _git_init_repo) and points to
    base_sha (not head_sha). assembly_plan execution would push a new ref.
    """

    repo = pipeline_run["repo"]
    base_sha = pipeline_run["base_sha"]
    # origin/main still points at the base commit; integrator did NOT push HEAD
    origin_main_sha = _run(["git", "-C", str(repo), "rev-parse", "refs/remotes/origin/main"])
    assert origin_main_sha == base_sha, (
        f"origin/main moved during shadow pipeline: {origin_main_sha} (expected {base_sha})"
    )


def test_ao_ma_8_e2e_smoke_evidence_receipt_matches_runtime_artifact(
    pipeline_run: dict[str, Any],
) -> None:
    """Codex iter-1 nice-to-have #2 absorb: receipt expected_invariants
    match the runtime integration_report. Drift defense — if behaviour
    changes, the receipt must be updated to keep the test green.
    """

    receipt = _load_receipt()
    decision = pipeline_run["integration_decision"]
    report = decision.report
    inv = receipt["expected_invariants"]

    assert decision.overall_status == inv["decision_overall_status"]
    assert len(report["conflicts"]) == inv["report_conflicts_length"]
    assert len(report["accepted_worker_results"]) == inv["report_accepted_worker_results_length"]
    assert len(report["rejected_worker_results"]) == inv["report_rejected_worker_results_length"]
    assert len(report["assembly_plan"]) >= inv["report_assembly_plan_length_min"]
    gf = report["guard_flags"]
    closed_now = (
        gf["support_widening"] is False
        and gf["production_platform_claim"] is False
        and gf["live_adapter_execution"] is False
    )
    assert closed_now == inv["guard_flags_closed"]


def test_ao_ma_8_e2e_smoke_no_gpp_status_mutation(pipeline_run: dict[str, Any]) -> None:
    """gpp_status.v1.json byte-identical pre/post pipeline."""

    gpp_path = pipeline_run["gpp_status_path"]
    current = gpp_path.read_bytes()
    assert current == pipeline_run["gpp_status_pre"], (
        "gpp_status.v1.json mutated during pipeline (pre-vs-post byte mismatch)"
    )


def test_ao_ma_8_e2e_smoke_no_branch_protection_or_workflow_mutation(
    pipeline_run: dict[str, Any],
) -> None:
    """Shadow mode pin: no .github/workflows/, gpp_status, scripts/gp5_platform_claim_decision mutation.

    The synthetic repo doesn't even have these files; the pipeline must not
    create them. We assert their absence (since the test repo only has the
    files synthesized in _git_init_repo + _write_synthetic_ssot + the
    pipeline's own artifact emission dirs).
    """

    repo = pipeline_run["repo"]
    forbidden = [
        repo / ".github" / "workflows",
        repo / "scripts" / "gp5_platform_claim_decision.py",
    ]
    for path in forbidden:
        assert not path.exists(), f"shadow pipeline created forbidden surface: {path}"


def test_ao_ma_8_runtime_modules_have_no_new_subprocess_imports() -> None:
    """Static AST check: AO-MA-5/6/7 pure-data runtime modules subprocess-free.

    Subprocess boundary per plan §Hard stops: test harness git use is allowed
    here in this file (and in WorkerRunner — pre-existing module from AO-MA-4),
    but AO-MA-5 (integrator), AO-MA-6 (reviewer), AO-MA-7 (verifier) and
    their writers must stay pure-data, no shell-out.
    """

    pure_data_modules = [
        "ao_kernel/orchestration/integrator.py",
        "ao_kernel/orchestration/integration_report_writer.py",
        "ao_kernel/orchestration/reviewer.py",
        "ao_kernel/orchestration/review_verdict_writer.py",
        "ao_kernel/orchestration/verifier.py",
        "ao_kernel/orchestration/verification_report_writer.py",
    ]
    for rel_path in pure_data_modules:
        source_path = _REPO_ROOT / rel_path
        source = source_path.read_text(encoding="utf-8")
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert alias.name != "subprocess", f"{rel_path} must not import subprocess"
            if isinstance(node, ast.ImportFrom):
                assert node.module != "subprocess", f"{rel_path} must not from-import subprocess"


def test_ao_ma_8_pr_scope_only_touches_allowlisted_files() -> None:
    """Codex iter-2 nice-to-have #4 absorb: PR scope allowlist enforced.

    AO-MA-8 PR diff is restricted to:
      1. .claude/plans/AO-MA-8-E2E-SMOKE.md
      2. .claude/plans/AO-MA-8-E2E-SMOKE-EVIDENCE.v1.json
      3. ao_kernel/defaults/schemas/ao-ma-8-e2e-smoke-evidence.schema.v1.json
      4. tests/test_ao_ma_8_e2e_smoke.py
      5. local-ai-review-evidence.v1.json

    The static check uses `git diff --name-only origin/main..HEAD` to verify
    no other files are touched. NO new runtime orchestration module changes.

    Skip when not in CI/PR context (sandbox tarball runs may not have a
    discoverable origin/main); the gate's job in CI.
    """

    in_ci = os.environ.get("CI") == "true"
    if not in_ci:
        pytest.skip("PR scope allowlist enforced in CI; local skip OK")
    # Codex post-impl iter-1 nice-to-have #3 absorb: in CI, git diff failure
    # must fail-closed (not skip) — silently skipping in CI would leave the
    # PR-scope invariant unenforced and let allowlist violations through.
    try:
        diff_out = _run(["git", "diff", "--name-only", "origin/main..HEAD"], cwd=_REPO_ROOT)
    except subprocess.CalledProcessError as exc:
        pytest.fail(f"CI cannot resolve git diff origin/main..HEAD; PR-scope invariant unenforceable: {exc}")
    changed = {line.strip() for line in diff_out.splitlines() if line.strip()}
    allowlist = {
        ".claude/plans/AO-MA-8-E2E-SMOKE.md",
        ".claude/plans/AO-MA-8-E2E-SMOKE-EVIDENCE.v1.json",
        "ao_kernel/defaults/schemas/ao-ma-8-e2e-smoke-evidence.schema.v1.json",
        "tests/test_ao_ma_8_e2e_smoke.py",
        "local-ai-review-evidence.v1.json",
    }
    extra = changed - allowlist
    assert not extra, f"AO-MA-8 PR touches files outside allowlist: {sorted(extra)}"


def test_ao_ma_8_evidence_receipt_schema_valid() -> None:
    """Receipt JSON validates against its bundled schema."""

    from jsonschema import Draft202012Validator

    schema = json.loads(_RECEIPT_SCHEMA_PATH.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    receipt = _load_receipt()
    Draft202012Validator(schema).validate(receipt)


def test_ao_ma_8_e2e_smoke_authority_artifact_is_integration_report(
    pipeline_run: dict[str, Any],
) -> None:
    """Receipt declares authority_artifact='integration_report.v1.json'; pipeline emitted it."""

    receipt = _load_receipt()
    assert receipt["authority_artifact"] == "integration_report.v1.json"
    # Check the actual integration_report.v1.json file lands on disk
    out_dir = pipeline_run["manifest_path"].parent
    integration_report_path = out_dir / "integration_report.v1.json"
    assert integration_report_path.exists(), (
        f"integration_report.v1.json (authority artifact) was not emitted at {integration_report_path}"
    )
    runtime = json.loads(integration_report_path.read_text(encoding="utf-8"))
    # Sanity: schema version matches AO-MA-5 producer
    assert runtime["schema_version"] == "ao-ma-integration-report.v1"
