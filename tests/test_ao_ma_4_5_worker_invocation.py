"""AO-MA-4.5 worker invocation tests.

Codex thread `019e74ef` AGREE (ready_for_impl: true). Two acceptance layers:

1. Unit/CLI smoke: ``spawn -> invoke`` writes a schema-valid
   ``worker_result.v1.json`` at the runner's ``expected_worker_result_path``;
   guard flags closed; ``actual_changed_files`` subset of declared write set;
   the invocation report validates against its schema.
2. Full dogfooding chain: ``plan -> spawn -> invoke -> review -> verify ->
   integrate`` reaches ``IntegrationDecision.overall_status == "all_accepted"``
   with a cross-provider chain (worker=local, reviewer=openai, verifier=tool).
   This uses the runtime ``WorkerInvoker.invoke()``, NOT an in-file surrogate.

Plus negative fail-closed cases: arbitrary adapter rejected, open
``live_adapter_execution`` rejected, non-eligible runner status skipped.

The worker fixture runs as a subprocess (``python -m
ao_kernel.fixtures.ao_ma_worker_stub``); the suite is invoked with
``PYTHONPATH`` pointed at this worktree so the subprocess imports the same
``ao_kernel`` under test.
"""

from __future__ import annotations

import json
import subprocess
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from jsonschema import Draft202012Validator

from ao_kernel.fixtures.ao_ma_worker_stub import WorkerStubError, emit_worker_result
from ao_kernel.orchestration.integrator import Integrator
from ao_kernel.orchestration.orchestrator import Orchestrator, SSOTPaths
from ao_kernel.orchestration.reviewer import ReviewInputs, Reviewer
from ao_kernel.orchestration.task_graph_builder import TaskSpec
from ao_kernel.orchestration.verifier import VerificationInputs, Verifier
from ao_kernel.orchestration.worker_invoker import (
    PINNED_FIXTURE_ID,
    WorkerInvocationError,
    WorkerInvoker,
    _check_emitted_binding,
)
from ao_kernel.orchestration.worker_runner import WorkerRunner

_REPO_ROOT = Path(__file__).resolve().parent.parent
_INVOCATION_SCHEMA_PATH = (
    _REPO_ROOT / "ao_kernel" / "defaults" / "schemas" / "ao-ma-worker-invocation-report.schema.v1.json"
)


# ---------------------------------------------------------------------------
# Test-harness git helpers
# ---------------------------------------------------------------------------


def _run(cmd: list[str], cwd: Path | None = None) -> str:
    completed = subprocess.run(cmd, cwd=cwd, check=True, capture_output=True, text=True, timeout=30)
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
    (repo / "AGENTS.md").write_text("# AGENTS\nAO-MA-4.5 smoke synthetic SSOT.\n", encoding="utf-8")
    plans_dir = repo / ".claude" / "plans"
    plans_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": "gpp_status.v1",
        "current_wp": {
            "id": "AO-MA-4.5-smoke",
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


def _build_manifest(repo: Path, base_sha: str, *, worktree_base: Path, dry_run: bool = False) -> dict[str, Any]:
    """plan -> spawn; return a context dict with manifest_path + runner_report."""

    ssot = SSOTPaths.default(repo)
    orchestrator = Orchestrator(repo_root=repo, ssot=ssot, output_dir=None)
    manifest = orchestrator.plan(
        goal="AO-MA-4.5 worker invocation smoke",
        declared_specs=[
            TaskSpec(
                task_id="task-001",
                description="AO-MA-4.5 deterministic worker",
                write_paths=["src/a.py"],
                depends_on=[],
            )
        ],
        base_sha=base_sha,
        base_ref="refs/heads/main",
        repo="Halildeu/ao-kernel",
    )
    task_graph_id = manifest["task_graph_id"]
    manifest_path = repo / ".ao" / "orchestration" / task_graph_id / "manifest.v1.json"
    runner = WorkerRunner(repo_root=repo, worktree_base=worktree_base, dry_run=dry_run)
    runner_report = runner.spawn(manifest_path=manifest_path)
    return {
        "manifest": manifest,
        "manifest_path": manifest_path,
        "task_graph_id": task_graph_id,
        "runner_report": runner_report,
    }


# ---------------------------------------------------------------------------
# Shared pipeline fixture: plan -> spawn -> invoke -> review -> verify -> integrate
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def chain(tmp_path_factory: pytest.TempPathFactory) -> Iterator[dict[str, Any]]:
    tmp_path = tmp_path_factory.mktemp("ao_ma_4_5")
    repo = tmp_path / "repo"
    base_sha = _git_init_repo(repo)
    _write_synthetic_ssot(repo)
    # Worktrees live OUTSIDE repo_root (realistic: ../ao-kernel-feat-X). The
    # invoker bridges each worktree-root worker_result into the manifest
    # base_dir consumption point, so the downstream chain integrates it
    # regardless of worktree location.
    worktree_base = tmp_path / "worktrees"

    built = _build_manifest(repo, base_sha, worktree_base=worktree_base)
    manifest_path = built["manifest_path"]
    task_id = "task-001"

    # AO-MA-4.5: the real worker invoker writes worker_result.v1.json at the
    # worktree root (producer SSOT) and bridges a copy into base_dir.
    invoker = WorkerInvoker(repo_root=repo)
    invocation_report = invoker.invoke(manifest_path=manifest_path)

    worker_entry = next(w for w in built["runner_report"]["workers"] if w["task_id"] == task_id)
    wr_path = Path(worker_entry["expected_worker_result_path"])  # worktree SSOT
    integrated_path = Path(invocation_report["invoked"][0]["integrated_worker_result_path"])

    # AO-MA-6: reviewer (worker=local, reviewer=openai)
    diff_text = _run(["git", "-C", worker_entry["actual_worktree"], "diff", f"{base_sha}..HEAD"])
    workers_dir = manifest_path.parent / "workers" / task_id
    workers_dir.mkdir(parents=True, exist_ok=True)
    pr_diff_path = workers_dir / "pr_diff.patch"
    pr_diff_path.write_text(diff_text, encoding="utf-8")
    findings_path = tmp_path / "findings.json"
    findings_path.write_text(
        json.dumps([{"severity": "info", "title": "AO-MA-4.5 smoke", "body": "no blockers"}]),
        encoding="utf-8",
    )
    reviewer = Reviewer(repo_root=repo)
    review_decision = reviewer.review(
        ReviewInputs(
            manifest_path=manifest_path,
            task_id=task_id,
            worker_result_paths={task_id: integrated_path},
            reviewer_agent_id="codex-reviewer",
            reviewer_provider="openai",
            reviewer_session_id="ao-ma-4-5-reviewer",
            verdict="AGREE",
            findings_path=findings_path,
            diff_path=pr_diff_path,
        )
    )

    # AO-MA-7: verifier (verifier=tool)
    verifier = Verifier(repo_root=repo)
    verification_result = verifier.verify(
        VerificationInputs(
            manifest_path=manifest_path,
            task_id=task_id,
            worker_result_paths={task_id: integrated_path},
            verifier_agent_id="verifier-tool",
            verifier_provider="tool",
            verifier_session_id="ao-ma-4-5-verifier",
            review_verdict_path=workers_dir / "review_verdict.v1.json",
            gpp_status_path=repo / ".claude" / "plans" / "gpp_status.v1.json",
        )
    )

    # AO-MA-5: integrator
    integrator = Integrator(
        repo_root=repo,
        integrator_agent_id="claude-integrator",
        integrator_provider="anthropic",
        integrator_session_id="ao-ma-4-5-integrator",
    )
    integration_decision = integrator.integrate(
        manifest_path=manifest_path,
        runner_report_path=None,
        worker_result_paths={task_id: integrated_path},
        review_verdict_paths={task_id: workers_dir / "review_verdict.v1.json"},
        verification_report_paths={task_id: workers_dir / "verification_report.v1.json"},
    )

    yield {
        "repo": repo,
        "base_sha": base_sha,
        "task_id": task_id,
        "manifest_path": manifest_path,
        "runner_report": built["runner_report"],
        "invocation_report": invocation_report,
        "worker_entry": worker_entry,
        "wr_path": wr_path,
        "integrated_path": integrated_path,
        "review_decision": review_decision,
        "verification_result": verification_result,
        "integration_decision": integration_decision,
    }


# ---------------------------------------------------------------------------
# Layer 1 — unit/CLI smoke over the invoker output
# ---------------------------------------------------------------------------


def test_invoke_emits_schema_valid_invocation_report(chain: dict[str, Any]) -> None:
    schema = json.loads(_INVOCATION_SCHEMA_PATH.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema).validate(chain["invocation_report"])
    report = chain["invocation_report"]
    assert report["fixture_id"] == PINNED_FIXTURE_ID
    assert len(report["invoked"]) == 1
    assert report["invoked"][0]["status"] == "invoked"


def test_invoke_writes_worker_result_at_expected_path(chain: dict[str, Any]) -> None:
    wr_path = chain["wr_path"]
    assert wr_path.exists(), f"worker_result.v1.json missing at expected path {wr_path}"
    # Path matches the invocation report entry's worker_result_path SSOT
    assert chain["invocation_report"]["invoked"][0]["worker_result_path"] == str(wr_path)


def test_invoke_worker_result_is_schema_valid_and_local_provider(chain: dict[str, Any]) -> None:
    wr = json.loads(chain["wr_path"].read_text(encoding="utf-8"))
    schema_path = _REPO_ROOT / "ao_kernel" / "defaults" / "schemas" / "ao-ma-worker-result.schema.v1.json"
    Draft202012Validator(json.loads(schema_path.read_text(encoding="utf-8"))).validate(wr)
    assert wr["worker"]["provider"] == "local"
    assert wr["worker"]["agent_type"] == "implementer"


def test_invoke_actual_changed_files_subset_of_declared(chain: dict[str, Any]) -> None:
    wr = json.loads(chain["wr_path"].read_text(encoding="utf-8"))
    actual = set(wr["actual_changed_files"])
    declared = set(wr["declared_write_set"])
    assert actual, "deterministic worker produced no actual_changed_files"
    assert actual.issubset(declared), f"actual {actual} not subset of declared {declared}"


def test_invoke_worker_result_head_sha_is_real_commit(chain: dict[str, Any]) -> None:
    wr = json.loads(chain["wr_path"].read_text(encoding="utf-8"))
    actual_head = _run(["git", "-C", chain["worker_entry"]["actual_worktree"], "rev-parse", "HEAD"])
    assert wr["head_sha"] == actual_head
    assert wr["head_sha"] != chain["base_sha"], "head must differ from base after the worker commit"


def test_invoke_guard_flags_closed(chain: dict[str, Any]) -> None:
    for artifact in (chain["invocation_report"], json.loads(chain["wr_path"].read_text(encoding="utf-8"))):
        gf = artifact["guard_flags"]
        assert gf["support_widening"] is False
        assert gf["production_platform_claim"] is False
        assert gf["live_adapter_execution"] is False


def test_invoke_bridges_worker_result_into_base_dir(chain: dict[str, Any]) -> None:
    """The invoker bridges the worktree-root worker_result into the manifest
    base_dir consumption point so AO-MA-5/6/7 can integrate it. The producer
    SSOT (worktree root) and the bridged copy are distinct paths with identical
    content, and the bridged copy lives under the manifest base_dir.
    """

    entry = chain["invocation_report"]["invoked"][0]
    integrated = Path(entry["integrated_worker_result_path"])
    base_dir = chain["manifest_path"].parent.parent
    assert integrated.exists()
    assert integrated != chain["wr_path"], "bridged copy must be distinct from the worktree SSOT path"
    integrated.resolve().relative_to(base_dir.resolve())  # raises if outside base_dir
    assert json.loads(integrated.read_text(encoding="utf-8")) == json.loads(
        chain["wr_path"].read_text(encoding="utf-8")
    ), "bridged worker_result content must equal the worktree SSOT content"


def test_invoke_report_persisted_to_disk(chain: dict[str, Any]) -> None:
    report_path = chain["manifest_path"].parent / "worker_invocation_report.v1.json"
    assert report_path.exists()
    persisted = json.loads(report_path.read_text(encoding="utf-8"))
    assert persisted["schema_version"] == "ao-ma-worker-invocation-report.v1"
    assert persisted["task_graph_id"] == chain["invocation_report"]["task_graph_id"]


# ---------------------------------------------------------------------------
# Layer 2 — full dogfooding chain reaches all_accepted
# ---------------------------------------------------------------------------


def test_full_chain_integration_all_accepted(chain: dict[str, Any]) -> None:
    decision = chain["integration_decision"]
    report = decision.report
    assert decision.overall_status == "all_accepted", f"got {decision.overall_status!r}"
    assert len(report["accepted_worker_results"]) == 1
    assert report["rejected_worker_results"] == []
    assert report["conflicts"] == []


def test_full_chain_cross_provider_distinct(chain: dict[str, Any]) -> None:
    wr = json.loads(chain["wr_path"].read_text(encoding="utf-8"))
    reviewer_provider = chain["review_decision"].report["reviewer"]["provider"]
    verifier_provider = chain["verification_result"].report["verifier"]["provider"]
    providers = {wr["worker"]["provider"], reviewer_provider, verifier_provider}
    assert wr["worker"]["provider"] == "local"
    assert reviewer_provider == "openai"
    assert verifier_provider == "tool"
    assert len(providers) == 3, f"cross-provider chain not distinct: {providers}"


def test_full_chain_assignment_provider_differs_from_worker_provider(chain: dict[str, Any]) -> None:
    """Codex regression pin: assignment.agent.provider defaults to 'anthropic'
    while worker_result.worker.provider is the honest 'local'; no AO-MA layer
    enforces equality, so integration still reaches all_accepted. Guards the
    chain if someone later adds an (incorrect) assignment-provider equality check.
    """

    manifest_dir = chain["manifest_path"].parent
    assignment_files = sorted(manifest_dir.glob("agent_assignment-*.v1.json"))
    assert assignment_files, "no agent_assignment artifact emitted by orchestrator"
    assignment = json.loads(assignment_files[0].read_text(encoding="utf-8"))
    wr = json.loads(chain["wr_path"].read_text(encoding="utf-8"))
    assert assignment["agent"]["provider"] == "anthropic"
    assert wr["worker"]["provider"] == "local"
    assert chain["integration_decision"].overall_status == "all_accepted"


# ---------------------------------------------------------------------------
# Layer 3 — negative fail-closed cases
# ---------------------------------------------------------------------------


def test_invoke_rejects_arbitrary_adapter(tmp_path: Path) -> None:
    """fixture_id other than the pinned deterministic worker (e.g. a live
    claude-code-cli) is rejected fail-closed before any manifest read.
    """

    invoker = WorkerInvoker(repo_root=tmp_path)
    with pytest.raises(WorkerInvocationError, match="claude-code-cli"):
        invoker.invoke(manifest_path=tmp_path / "manifest.v1.json", fixture_id="claude-code-cli")


def test_invoke_rejects_open_live_adapter_execution_guard(tmp_path: Path) -> None:
    """A manifest with live_adapter_execution=true is rejected fail-closed."""

    manifest_path = tmp_path / "manifest.v1.json"
    manifest_path.write_text(
        json.dumps(
            {
                "schema_version": "ao-ma-orchestration-manifest.v1",
                "task_graph_id": "ao-ma-20260529-abc1234",
                "guard_flags": {
                    "support_widening": False,
                    "production_platform_claim": False,
                    "live_adapter_execution": True,
                },
            }
        ),
        encoding="utf-8",
    )
    invoker = WorkerInvoker(repo_root=tmp_path)
    with pytest.raises(WorkerInvocationError, match="live_adapter_execution"):
        invoker.invoke(manifest_path=manifest_path)


def test_invoke_skips_non_eligible_runner_status(tmp_path_factory: pytest.TempPathFactory) -> None:
    """A dry-run spawn yields status 'skipped_dry_run' (a real runner enum
    value, not 'prepared'); the invoker records it as skipped_not_eligible and
    does NOT write a worker_result.
    """

    tmp_path = tmp_path_factory.mktemp("ao_ma_4_5_dryrun")
    repo = tmp_path / "repo"
    base_sha = _git_init_repo(repo)
    _write_synthetic_ssot(repo)
    worktree_base = tmp_path / "worktrees"
    built = _build_manifest(repo, base_sha, worktree_base=worktree_base, dry_run=True)

    # Sanity: the runner reported a non-eligible status for dry-run.
    statuses = {w["status"] for w in built["runner_report"]["workers"]}
    assert statuses == {"skipped_dry_run"}, f"expected dry-run skip, got {statuses}"

    invoker = WorkerInvoker(repo_root=repo)
    report = invoker.invoke(manifest_path=built["manifest_path"])
    assert len(report["invoked"]) == 1
    entry = report["invoked"][0]
    assert entry["status"] == "skipped_not_eligible"
    assert not Path(entry["worker_result_path"]).exists(), "no worker_result should be written for a skip"


# ---------------------------------------------------------------------------
# Layer 4 — fixture core unit tests (direct emit_worker_result; the invoker
# runs the fixture as a subprocess, so direct calls are needed to exercise and
# measure the fixture's guard / error logic)
# ---------------------------------------------------------------------------


def _write_assignment(path: Path, *, base_sha: str, declared: list[str], guard: dict[str, bool] | None = None) -> None:
    payload = {
        "schema_version": "ao-ma-agent-assignment.v1",
        "assignment_id": "ao-ma-4-5-task-001",
        "task_graph_id": "ao-ma-20260529-abc1234",
        "task_id": "task-001",
        "agent": {
            "agent_id": "planner-x",
            "agent_type": "implementer",
            "provider": "anthropic",
            "session_id": "s1",
        },
        "base_ref": "refs/heads/main",
        "base_sha": base_sha,
        "branch": "codex/ao-ma-4-5-task-001",
        "worktree": "worktrees/task-001",
        "declared_write_set": declared,
        "expected_output_artifact": "worker_result.v1.json",
        "status": "pending",
        "guard_flags": guard
        or {"support_widening": False, "production_platform_claim": False, "live_adapter_execution": False},
    }
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_worker_stub_emit_happy_path(tmp_path: Path) -> None:
    wt = tmp_path / "wt"
    base_sha = _git_init_repo(wt)
    # The fixture's defense-in-depth git gate expects the worktree on the
    # assignment branch at base_sha HEAD (as AO-MA-4 prepares it).
    _run(["git", "-C", str(wt), "checkout", "-b", "codex/ao-ma-4-5-task-001"])
    assignment_path = tmp_path / "assignment.json"
    _write_assignment(assignment_path, base_sha=base_sha, declared=["src/a.py"])
    out = tmp_path / "worker_result.v1.json"
    result = emit_worker_result(assignment_path=assignment_path, worktree=wt, output_path=out)
    assert out.exists()
    schema_path = _REPO_ROOT / "ao_kernel" / "defaults" / "schemas" / "ao-ma-worker-result.schema.v1.json"
    Draft202012Validator(json.loads(schema_path.read_text(encoding="utf-8"))).validate(result)
    assert result["worker"]["provider"] == "local"
    assert result["worker"]["agent_type"] == "implementer"
    assert result["head_sha"] != base_sha
    assert result["actual_changed_files"] == ["src/a.py"]
    assert result["guard_flags"]["live_adapter_execution"] is False


def test_worker_stub_rejects_open_live_adapter_guard(tmp_path: Path) -> None:
    wt = tmp_path / "wt"
    base_sha = _git_init_repo(wt)
    assignment_path = tmp_path / "assignment.json"
    _write_assignment(
        assignment_path,
        base_sha=base_sha,
        declared=["src/a.py"],
        guard={"support_widening": False, "production_platform_claim": False, "live_adapter_execution": True},
    )
    with pytest.raises(WorkerStubError, match="live_adapter_execution"):
        emit_worker_result(assignment_path=assignment_path, worktree=wt, output_path=tmp_path / "o.json")
    assert not (tmp_path / "o.json").exists()


def test_worker_stub_rejects_empty_declared_write_set(tmp_path: Path) -> None:
    wt = tmp_path / "wt"
    base_sha = _git_init_repo(wt)
    assignment_path = tmp_path / "assignment.json"
    _write_assignment(assignment_path, base_sha=base_sha, declared=[])
    with pytest.raises(WorkerStubError, match="declared_write_set"):
        emit_worker_result(assignment_path=assignment_path, worktree=wt, output_path=tmp_path / "o.json")


def test_worker_stub_rejects_missing_worktree(tmp_path: Path) -> None:
    assignment_path = tmp_path / "assignment.json"
    _write_assignment(assignment_path, base_sha="0" * 40, declared=["src/a.py"])
    with pytest.raises(WorkerStubError, match="worktree"):
        emit_worker_result(assignment_path=assignment_path, worktree=tmp_path / "nope", output_path=tmp_path / "o.json")


def test_invoke_fails_when_runner_report_missing(tmp_path_factory: pytest.TempPathFactory) -> None:
    """Valid manifest (envelope passes) but the runner_report.v1.json is absent
    → fail-closed (the invoker is downstream of AO-MA-4 spawn).
    """

    tmp_path = tmp_path_factory.mktemp("ao_ma_4_5_norr")
    repo = tmp_path / "repo"
    base_sha = _git_init_repo(repo)
    _write_synthetic_ssot(repo)
    built = _build_manifest(repo, base_sha, worktree_base=tmp_path / "worktrees")
    (built["manifest_path"].parent / "runner_report.v1.json").unlink()
    with pytest.raises(WorkerInvocationError, match="not found"):
        WorkerInvoker(repo_root=repo).invoke(manifest_path=built["manifest_path"])


# ---------------------------------------------------------------------------
# Layer 5 — trust boundary + emitted-binding fail-closed (Codex post-impl RED)
# ---------------------------------------------------------------------------


def test_worker_stub_rejects_traversal_declared_path(tmp_path: Path) -> None:
    """A tampered assignment with a traversal declared path must NOT cause an
    out-of-worktree write (the fixture self-defends even if called standalone).
    """

    wt = tmp_path / "wt"
    base_sha = _git_init_repo(wt)
    _run(["git", "-C", str(wt), "checkout", "-b", "codex/ao-ma-4-5-task-001"])
    assignment_path = tmp_path / "assignment.json"
    _write_assignment(assignment_path, base_sha=base_sha, declared=["../escape.txt"])
    with pytest.raises(WorkerStubError, match="traversal|absolute|escape"):
        emit_worker_result(assignment_path=assignment_path, worktree=wt, output_path=tmp_path / "o.json")
    assert not (tmp_path / "escape.txt").exists(), "fixture wrote outside the worktree"


def test_invoke_rejects_tampered_assignment_sha(tmp_path_factory: pytest.TempPathFactory) -> None:
    """Mutating the assignment after spawn breaks its sha256 pin → the worker is
    recorded failed and the fixture never runs.
    """

    tmp_path = tmp_path_factory.mktemp("ao_ma_4_5_sha")
    repo = tmp_path / "repo"
    base_sha = _git_init_repo(repo)
    _write_synthetic_ssot(repo)
    built = _build_manifest(repo, base_sha, worktree_base=tmp_path / "worktrees")
    manifest_dir = built["manifest_path"].parent
    assignment_file = next(manifest_dir.glob("agent_assignment-*.v1.json"))
    # Tamper: append a byte so sha256 diverges from the runner_report pin.
    assignment_file.write_text(assignment_file.read_text(encoding="utf-8") + " ", encoding="utf-8")

    report = WorkerInvoker(repo_root=repo).invoke(manifest_path=built["manifest_path"])
    entry = report["invoked"][0]
    assert entry["status"] == "failed"
    assert "assignment_sha256 mismatch" in entry["reason"]


def test_invoke_rejects_stale_runner_report_manifest_sha(tmp_path_factory: pytest.TempPathFactory) -> None:
    """A runner_report whose manifest_sha256 does not match the on-disk manifest
    is rejected fail-closed (stale/tampered report)."""

    tmp_path = tmp_path_factory.mktemp("ao_ma_4_5_stale")
    repo = tmp_path / "repo"
    base_sha = _git_init_repo(repo)
    _write_synthetic_ssot(repo)
    built = _build_manifest(repo, base_sha, worktree_base=tmp_path / "worktrees")
    runner_report_path = built["manifest_path"].parent / "runner_report.v1.json"
    report = json.loads(runner_report_path.read_text(encoding="utf-8"))
    report["manifest_sha256"] = "sha256:" + "0" * 64
    runner_report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    with pytest.raises(WorkerInvocationError, match="manifest_sha256"):
        WorkerInvoker(repo_root=repo).invoke(manifest_path=built["manifest_path"])


def _binding_fixture() -> dict[str, Any]:
    return {
        "task_graph_id": "ao-ma-20260529-abc1234",
        "task_id": "task-001",
        "base_sha": "a" * 40,
        "head_ref": "codex/ao-ma-4-5-task-001",
        "declared_write_set": ["src/a.py"],
        "actual_changed_files": ["src/a.py"],
    }


def test_check_emitted_binding_passes_on_full_match() -> None:
    assert (
        _check_emitted_binding(
            emitted=_binding_fixture(),
            task_graph_id="ao-ma-20260529-abc1234",
            task_id="task-001",
            base_sha="a" * 40,
            branch="codex/ao-ma-4-5-task-001",
        )
        is None
    )


def test_check_emitted_binding_detects_wrong_graph_and_overlap() -> None:
    wrong_graph = {**_binding_fixture(), "task_graph_id": "ao-ma-20260529-deadbee"}
    assert _check_emitted_binding(
        emitted=wrong_graph,
        task_graph_id="ao-ma-20260529-abc1234",
        task_id="task-001",
        base_sha="a" * 40,
        branch="codex/ao-ma-4-5-task-001",
    )
    overlap = {**_binding_fixture(), "actual_changed_files": ["src/evil.py"]}
    assert _check_emitted_binding(
        emitted=overlap,
        task_graph_id="ao-ma-20260529-abc1234",
        task_id="task-001",
        base_sha="a" * 40,
        branch="codex/ao-ma-4-5-task-001",
    )


def test_invoke_rejects_out_of_repo_worktree(tmp_path_factory: pytest.TempPathFactory) -> None:
    """A tampered runner_report pointing actual_worktree at a plain directory
    outside the repo must NOT drive a write there: the worker is failed and the
    outside directory stays empty.
    """

    tmp_path = tmp_path_factory.mktemp("ao_ma_4_5_oow")
    repo = tmp_path / "repo"
    base_sha = _git_init_repo(repo)
    _write_synthetic_ssot(repo)
    built = _build_manifest(repo, base_sha, worktree_base=tmp_path / "worktrees")
    runner_report_path = built["manifest_path"].parent / "runner_report.v1.json"
    report = json.loads(runner_report_path.read_text(encoding="utf-8"))
    outside = tmp_path / "outside"
    outside.mkdir()
    for w in report["workers"]:
        w["actual_worktree"] = str(outside)
        w["expected_worker_result_path"] = str(outside / "worker_result.v1.json")
    runner_report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    invoke_report = WorkerInvoker(repo_root=repo).invoke(manifest_path=built["manifest_path"])
    entry = invoke_report["invoked"][0]
    assert entry["status"] == "failed"
    assert "worker entry integrity failed" in entry["reason"]
    assert list(outside.iterdir()) == [], "fixture wrote into the out-of-repo directory"


def test_invoke_rejects_foreign_git_worktree(tmp_path_factory: pytest.TempPathFactory) -> None:
    """A tampered runner_report pointing actual_worktree at a DIFFERENT git repo
    (not a worktree of repo_root) is rejected fail-closed.
    """

    tmp_path = tmp_path_factory.mktemp("ao_ma_4_5_foreign")
    repo = tmp_path / "repo"
    base_sha = _git_init_repo(repo)
    _write_synthetic_ssot(repo)
    built = _build_manifest(repo, base_sha, worktree_base=tmp_path / "worktrees")
    foreign = tmp_path / "foreign"
    _git_init_repo(foreign)  # independent repo, own HEAD / common-dir
    runner_report_path = built["manifest_path"].parent / "runner_report.v1.json"
    report = json.loads(runner_report_path.read_text(encoding="utf-8"))
    for w in report["workers"]:
        w["actual_worktree"] = str(foreign)
        w["expected_worker_result_path"] = str(foreign / "worker_result.v1.json")
    runner_report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    invoke_report = WorkerInvoker(repo_root=repo).invoke(manifest_path=built["manifest_path"])
    entry = invoke_report["invoked"][0]
    assert entry["status"] == "failed"
    assert not (foreign / "worker_result.v1.json").exists()
