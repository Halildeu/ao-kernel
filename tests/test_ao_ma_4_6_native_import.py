"""AO-MA-4.6-1 native worker result importer functional tests.

Pattern parity with test_ao_ma_4_5_worker_invocation.py / test_ao_ma_11h_notifier.py:
synthetic artifact directory in tmp_path, JSON files wired with real SHA256
bindings, then exercise the importer through both the happy path and every
fatal trust-boundary + reportable policy-invalid branch.

Codex thread 019e8000 AGREE contract (CNS-20260601-001 iter-1..4):
- Fatal trust-boundary errors raise NativeWorkerImportError BEFORE any report
  is emitted and BEFORE any integrated copy is written.
- Reportable policy-invalid emits a schema-valid import_report with
  valid=false, integrated_path/sha=null, no copy.
- All-pass emits a schema-valid valid=true report + atomic canonical copy.
- valid flag is always recomputed; forged valid=true is rejected by
  verify_import_binding.
"""

from __future__ import annotations

import copy
import hashlib
import json
from importlib import resources
from pathlib import Path
from typing import Any

import pytest

from ao_kernel.orchestration.native_worker_import import (
    DEFAULT_SOURCE_INTERFACE_ALLOWLIST,
    IMPORT_MODE,
    NativeWorkerImportError,
    REQUIRED_CHECK_KEYS,
    SCHEMA_VERSION,
    _canonical_integrated_path,
    _compute_sha256,
    _recompute_valid,
    import_native_worker_result,
    verify_import_binding,
)


# ---------------------------------------------------------------------------
# Shared schema loader
# ---------------------------------------------------------------------------


def _load(name: str) -> dict[str, Any]:
    path = resources.files("ao_kernel.defaults.schemas").joinpath(name)
    return json.loads(path.read_text(encoding="utf-8"))  # type: ignore[no-any-return]


SCHEMAS: dict[str, dict[str, Any]] = {
    "worker_result": _load("ao-ma-worker-result.schema.v1.json"),
    "runner_report": _load("ao-ma-runner-report.schema.v1.json"),
    "task_graph": _load("ao-ma-task-graph.schema.v1.json"),
    "assignment": _load("ao-ma-agent-assignment.schema.v1.json"),
    "import_report": _load("ao-ma-native-worker-import-report.schema.v1.json"),
}


def _kwargs() -> dict[str, Any]:
    return {
        "worker_result_schema": SCHEMAS["worker_result"],
        "runner_report_schema": SCHEMAS["runner_report"],
        "task_graph_schema": SCHEMAS["task_graph"],
        "assignment_schema": SCHEMAS["assignment"],
        "import_report_schema": SCHEMAS["import_report"],
    }


# ---------------------------------------------------------------------------
# Synthetic-artifact fixture
# ---------------------------------------------------------------------------


_TASK_GRAPH_ID = "ao-ma-4-6-test"
_TASK_ID = "slice-a"
_ASSIGNMENT_ID = "asg-slice-a"
_BASE_REF = "refs/heads/main"
_BASE_SHA = "0" * 40
_BRANCH = "codex/slice-a"
_DECLARED = ["src/module_a.py", "tests/test_module_a.py"]


def _file_sha(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _file_size(path: Path) -> int:
    return path.stat().st_size


def _make_artifact_dir(tmp_path: Path) -> dict[str, Any]:
    """Construct a fully sha-bound AO-MA artifact set in tmp_path/artifacts.

    Returns a dict with:
      - artifact_dir: Path
      - source_path:  Path to worker_result.v1.json (the 'native AI output')
      - runner_report_path: Path to runner_report.v1.json
    """

    artifact_dir = tmp_path / "artifacts"
    artifact_dir.mkdir()

    # task_graph.v1.json
    task_graph = {
        "schema_version": "ao-ma-task-graph.v1",
        "task_graph_id": _TASK_GRAPH_ID,
        "repo": "Halildeu/ao-kernel",
        "goal": "Test slice for 4.6-1 native import",
        "base_ref": _BASE_REF,
        "base_sha": _BASE_SHA,
        "risk_class": "normal",
        "max_parallel_workers": 1,
        "tasks": [
            {
                "task_id": _TASK_ID,
                "title": "slice a",
                "agent_type": "implementer",
                "declared_write_set": _DECLARED,
                "dependency_ids": [],
                "acceptance_criteria": ["module renders + tests pass"],
                "high_risk": False,
            }
        ],
        "fan_in_policy": {
            "mode": "all_required",
            "required_task_ids": [_TASK_ID],
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
    tg_path = artifact_dir / "task_graph.v1.json"
    tg_path.write_text(json.dumps(task_graph, sort_keys=True), encoding="utf-8")

    # agent_assignment-<task_id>.v1.json
    assignment = {
        "schema_version": "ao-ma-agent-assignment.v1",
        "assignment_id": _ASSIGNMENT_ID,
        "task_graph_id": _TASK_GRAPH_ID,
        "task_id": _TASK_ID,
        "agent": {
            "agent_id": "claude-implementer-1",
            "agent_type": "implementer",
            "provider": "anthropic",
            "session_id": "session-anthropic-1",
        },
        "base_ref": _BASE_REF,
        "base_sha": _BASE_SHA,
        "branch": _BRANCH,
        "worktree": f"wt/{_TASK_ID}",
        "declared_write_set": _DECLARED,
        "expected_output_artifact": f"workers/{_TASK_ID}/worker_result.v1.json",
        "status": "pending",
        "guard_flags": {
            "support_widening": False,
            "production_platform_claim": False,
            "live_adapter_execution": False,
        },
    }
    asg_filename = f"agent_assignment-{_TASK_ID}.v1.json"
    asg_path = artifact_dir / asg_filename
    asg_path.write_text(json.dumps(assignment, sort_keys=True), encoding="utf-8")

    # manifest.v1.json (envelope)
    tg_sha = _file_sha(tg_path)
    asg_sha = _file_sha(asg_path)
    manifest = {
        "schema_version": "ao-ma-orchestration-manifest.v1",
        "task_graph_id": _TASK_GRAPH_ID,
        "base_dir": str(artifact_dir),
        "generated_at": "2026-06-01T01:00:00Z",
        "artifacts": [
            {
                "path": "task_graph.v1.json",
                "sha256": tg_sha,
                "size_bytes": _file_size(tg_path),
            },
            {
                "path": asg_filename,
                "sha256": asg_sha,
                "size_bytes": _file_size(asg_path),
            },
        ],
    }
    manifest_path = artifact_dir / "manifest.v1.json"
    manifest_path.write_text(json.dumps(manifest, sort_keys=True), encoding="utf-8")
    manifest_sha = _file_sha(manifest_path)

    # runner_report.v1.json
    runner_report = {
        "schema_version": "ao-ma-runner-report.v1",
        "task_graph_id": _TASK_GRAPH_ID,
        "manifest_sha256": manifest_sha,
        "base_sha": _BASE_SHA,
        "generated_at": "2026-06-01T01:00:01Z",
        "conflict_check": "pass",
        "base_sync_check": "pass",
        "workers": [
            {
                "task_id": _TASK_ID,
                "assignment_ref": asg_filename,
                "assignment_sha256": asg_sha,
                "branch": _BRANCH,
                "planned_worktree": str(tmp_path / "wt" / _TASK_ID),
                "actual_worktree": str(tmp_path / "wt" / _TASK_ID),
                "status": "prepared",
                "reason": "ok",
                "expected_worker_result_path": str(artifact_dir / "workers" / _TASK_ID / "worker_result.v1.json"),
            }
        ],
        "guard_flags": {
            "support_widening": False,
            "production_platform_claim": False,
            "live_adapter_execution": False,
        },
    }
    runner_report_path = artifact_dir / "runner_report.v1.json"
    runner_report_path.write_text(json.dumps(runner_report, sort_keys=True), encoding="utf-8")

    # source worker_result.v1.json (the operator/AI native output)
    worker_result = {
        "schema_version": "ao-ma-worker-result.v1",
        "task_graph_id": _TASK_GRAPH_ID,
        "task_id": _TASK_ID,
        "assignment_id": _ASSIGNMENT_ID,
        "worker": {
            "agent_id": "claude-implementer-1",
            "agent_type": "implementer",
            "provider": "anthropic",
            "session_id": "session-anthropic-1",
        },
        "base_ref": _BASE_REF,
        "base_sha": _BASE_SHA,
        "head_ref": _BRANCH,
        "head_sha": "1" * 40,
        "declared_write_set": _DECLARED,
        "actual_changed_files": [_DECLARED[0]],
        "summary": "added module_a + tests",
        "tests_run": [{"command": "pytest", "outcome": "pass"}],
        "known_gaps": [],
        "no_secret_attestation": {"secrets_recorded": False},
        "guard_flags": {
            "support_widening": False,
            "production_platform_claim": False,
            "live_adapter_execution": False,
        },
    }
    source_dir = tmp_path / "operator_native_output"
    source_dir.mkdir()
    source_path = source_dir / "worker_result.v1.json"
    source_path.write_text(json.dumps(worker_result, sort_keys=True), encoding="utf-8")

    return {
        "artifact_dir": artifact_dir,
        "source_path": source_path,
        "runner_report_path": runner_report_path,
        "manifest_path": manifest_path,
        "tg_path": tg_path,
        "asg_path": asg_path,
        "task_graph": task_graph,
        "assignment": assignment,
        "manifest": manifest,
        "runner_report": runner_report,
        "worker_result": worker_result,
    }


def _rewrite(path: Path, data: dict[str, Any]) -> None:
    path.write_text(json.dumps(data, sort_keys=True), encoding="utf-8")


def _rebind_manifest(ctx: dict[str, Any]) -> None:
    """Recompute artifact sha entries + manifest_sha + runner_report after edit."""

    manifest = ctx["manifest"]
    tg_sha = _file_sha(ctx["tg_path"])
    asg_sha = _file_sha(ctx["asg_path"])
    for entry in manifest["artifacts"]:
        if entry["path"] == "task_graph.v1.json":
            entry["sha256"] = tg_sha
            entry["size_bytes"] = _file_size(ctx["tg_path"])
        elif entry["path"].startswith("agent_assignment-"):
            entry["sha256"] = asg_sha
            entry["size_bytes"] = _file_size(ctx["asg_path"])
    _rewrite(ctx["manifest_path"], manifest)
    manifest_sha = _file_sha(ctx["manifest_path"])
    ctx["runner_report"]["manifest_sha256"] = manifest_sha
    for w in ctx["runner_report"]["workers"]:
        if w["task_id"] == _TASK_ID:
            w["assignment_sha256"] = asg_sha
    _rewrite(ctx["runner_report_path"], ctx["runner_report"])


@pytest.fixture()
def chain(tmp_path: Path) -> dict[str, Any]:
    return _make_artifact_dir(tmp_path)


# ---------------------------------------------------------------------------
# Layer 1 — constants & helpers
# ---------------------------------------------------------------------------


def test_constants_pinned() -> None:
    assert SCHEMA_VERSION == "ao-ma-native-worker-import-report.v1"
    assert IMPORT_MODE == "import_only"
    assert set(DEFAULT_SOURCE_INTERFACE_ALLOWLIST) == {
        "claude-cli",
        "codex-cli",
        "mavis-cli",
        "local-file",
    }
    assert len(REQUIRED_CHECK_KEYS) == 20
    assert REQUIRED_CHECK_KEYS[0] == "source_json_readable"


def test_canonical_integrated_path_is_pinned() -> None:
    path = _canonical_integrated_path(Path("/a/b"), "task-x")
    assert path == Path("/a/b/workers/task-x/worker_result.v1.json")


def test_recompute_valid_all_pass_true() -> None:
    checks = {k: {"outcome": "pass"} for k in REQUIRED_CHECK_KEYS}
    assert _recompute_valid(checks) is True


def test_recompute_valid_any_fail_false() -> None:
    checks = {k: {"outcome": "pass"} for k in REQUIRED_CHECK_KEYS}
    checks["actual_non_empty"] = {"outcome": "fail"}
    assert _recompute_valid(checks) is False


def test_recompute_valid_missing_key_false() -> None:
    checks = {k: {"outcome": "pass"} for k in REQUIRED_CHECK_KEYS}
    del checks["actual_non_empty"]
    assert _recompute_valid(checks) is False


def test_recompute_valid_skipped_not_pass() -> None:
    checks = {k: {"outcome": "pass"} for k in REQUIRED_CHECK_KEYS}
    checks["source_integrated_hash_match"] = {"outcome": "skipped"}
    assert _recompute_valid(checks) is False


# ---------------------------------------------------------------------------
# Layer 2 — happy path
# ---------------------------------------------------------------------------


def test_happy_path_valid_true_and_integrated_copy(chain: dict[str, Any]) -> None:
    report = import_native_worker_result(
        source_result_path=chain["source_path"],
        runner_report_path=chain["runner_report_path"],
        source_interface="claude-cli",
        imported_at="2026-06-01T01:00:02Z",
        **_kwargs(),
    )
    assert report["validation_status"] == "valid"
    assert report["valid"] is True
    assert report["integrated_worker_result_path"] is not None
    integrated = Path(report["integrated_worker_result_path"])
    assert integrated.exists()
    assert integrated.relative_to(chain["artifact_dir"]) == Path("workers") / _TASK_ID / "worker_result.v1.json"
    assert report["integrated_worker_result_sha256"] == _compute_sha256(integrated)
    assert report["integrated_worker_result_sha256"] == report["source_result_sha256"]
    assert report["effective_source_interface_allowlist"] == list(DEFAULT_SOURCE_INTERFACE_ALLOWLIST)
    # head_sha_not_git_recomputed is always emitted as warning
    severities = {f["code"]: f["severity"] for f in report["validation_findings"]}
    assert severities.get("head_sha_not_git_recomputed") == "warning"


def test_happy_path_idempotent_when_existing_matches(chain: dict[str, Any]) -> None:
    # First import
    import_native_worker_result(
        source_result_path=chain["source_path"],
        runner_report_path=chain["runner_report_path"],
        source_interface="claude-cli",
        imported_at="2026-06-01T01:00:02Z",
        **_kwargs(),
    )
    # Second import with same source -> idempotent OK
    r2 = import_native_worker_result(
        source_result_path=chain["source_path"],
        runner_report_path=chain["runner_report_path"],
        source_interface="claude-cli",
        imported_at="2026-06-01T01:00:03Z",
        **_kwargs(),
    )
    assert r2["valid"] is True
    msg = r2["checks"]["source_integrated_hash_match"].get("message", "")
    assert "idempotent" in msg


def test_happy_path_narrow_allowlist_records_effective(chain: dict[str, Any]) -> None:
    report = import_native_worker_result(
        source_result_path=chain["source_path"],
        runner_report_path=chain["runner_report_path"],
        source_interface="claude-cli",
        imported_at="2026-06-01T01:00:02Z",
        source_interface_allowlist=("claude-cli",),
        **_kwargs(),
    )
    assert report["valid"] is True
    assert report["effective_source_interface_allowlist"] == ["claude-cli"]


def test_happy_path_explicit_artifact_dir_matching(chain: dict[str, Any]) -> None:
    report = import_native_worker_result(
        source_result_path=chain["source_path"],
        runner_report_path=chain["runner_report_path"],
        source_interface="claude-cli",
        imported_at="2026-06-01T01:00:02Z",
        artifact_dir=chain["artifact_dir"],
        **_kwargs(),
    )
    assert report["valid"] is True


# ---------------------------------------------------------------------------
# Layer 3 — fatal trust-boundary
# ---------------------------------------------------------------------------


def test_fatal_imported_at_not_rfc3339(chain: dict[str, Any]) -> None:
    with pytest.raises(NativeWorkerImportError, match="RFC3339"):
        import_native_worker_result(
            source_result_path=chain["source_path"],
            runner_report_path=chain["runner_report_path"],
            source_interface="claude-cli",
            imported_at="not-a-timestamp",
            **_kwargs(),
        )


def test_fatal_source_interface_unknown(chain: dict[str, Any]) -> None:
    with pytest.raises(NativeWorkerImportError, match="source_interface"):
        import_native_worker_result(
            source_result_path=chain["source_path"],
            runner_report_path=chain["runner_report_path"],
            source_interface="unknown-cli",
            imported_at="2026-06-01T01:00:02Z",
            **_kwargs(),
        )


def test_fatal_artifact_dir_mismatch(chain: dict[str, Any], tmp_path: Path) -> None:
    other_dir = tmp_path / "different_dir"
    other_dir.mkdir()
    with pytest.raises(NativeWorkerImportError, match="artifact_dir"):
        import_native_worker_result(
            source_result_path=chain["source_path"],
            runner_report_path=chain["runner_report_path"],
            source_interface="claude-cli",
            imported_at="2026-06-01T01:00:02Z",
            artifact_dir=other_dir,
            **_kwargs(),
        )


def test_fatal_source_file_missing(chain: dict[str, Any], tmp_path: Path) -> None:
    missing = tmp_path / "no-such-file.json"
    with pytest.raises(NativeWorkerImportError, match="worker_result.*not found"):
        import_native_worker_result(
            source_result_path=missing,
            runner_report_path=chain["runner_report_path"],
            source_interface="claude-cli",
            imported_at="2026-06-01T01:00:02Z",
            **_kwargs(),
        )


def test_fatal_source_json_corrupt(chain: dict[str, Any]) -> None:
    chain["source_path"].write_text("{not json", encoding="utf-8")
    with pytest.raises(NativeWorkerImportError, match="JSON parse error"):
        import_native_worker_result(
            source_result_path=chain["source_path"],
            runner_report_path=chain["runner_report_path"],
            source_interface="claude-cli",
            imported_at="2026-06-01T01:00:02Z",
            **_kwargs(),
        )


def test_fatal_worker_result_schema_invalid_guard_open(chain: dict[str, Any]) -> None:
    """guard_flags.live_adapter_execution=true at the worker_result is a
    schema boundary violation (worker_result schema pins it const false).
    Fatal trust-boundary."""

    wr = copy.deepcopy(chain["worker_result"])
    wr["guard_flags"]["live_adapter_execution"] = True
    _rewrite(chain["source_path"], wr)
    with pytest.raises(NativeWorkerImportError, match="worker_result.*schema-invalid"):
        import_native_worker_result(
            source_result_path=chain["source_path"],
            runner_report_path=chain["runner_report_path"],
            source_interface="claude-cli",
            imported_at="2026-06-01T01:00:02Z",
            **_kwargs(),
        )


def test_fatal_worker_result_no_secret_violation(chain: dict[str, Any]) -> None:
    wr = copy.deepcopy(chain["worker_result"])
    wr["no_secret_attestation"]["secrets_recorded"] = True
    _rewrite(chain["source_path"], wr)
    with pytest.raises(NativeWorkerImportError, match="worker_result.*schema-invalid"):
        import_native_worker_result(
            source_result_path=chain["source_path"],
            runner_report_path=chain["runner_report_path"],
            source_interface="claude-cli",
            imported_at="2026-06-01T01:00:02Z",
            **_kwargs(),
        )


def test_fatal_runner_report_schema_invalid(chain: dict[str, Any]) -> None:
    rr = copy.deepcopy(chain["runner_report"])
    rr["guard_flags"]["support_widening"] = True
    _rewrite(chain["runner_report_path"], rr)
    with pytest.raises(NativeWorkerImportError, match="runner_report.*schema-invalid"):
        import_native_worker_result(
            source_result_path=chain["source_path"],
            runner_report_path=chain["runner_report_path"],
            source_interface="claude-cli",
            imported_at="2026-06-01T01:00:02Z",
            **_kwargs(),
        )


def test_fatal_manifest_missing(chain: dict[str, Any]) -> None:
    chain["manifest_path"].unlink()
    with pytest.raises(NativeWorkerImportError, match="manifest.*not found"):
        import_native_worker_result(
            source_result_path=chain["source_path"],
            runner_report_path=chain["runner_report_path"],
            source_interface="claude-cli",
            imported_at="2026-06-01T01:00:02Z",
            **_kwargs(),
        )


def test_fatal_manifest_sha_mismatch(chain: dict[str, Any]) -> None:
    # Tamper the manifest after runner_report was generated
    bad = copy.deepcopy(chain["manifest"])
    bad["generated_at"] = "2099-01-01T00:00:00Z"
    _rewrite(chain["manifest_path"], bad)
    with pytest.raises(NativeWorkerImportError, match="manifest_sha_mismatch"):
        import_native_worker_result(
            source_result_path=chain["source_path"],
            runner_report_path=chain["runner_report_path"],
            source_interface="claude-cli",
            imported_at="2026-06-01T01:00:02Z",
            **_kwargs(),
        )


def test_fatal_task_graph_sha_mismatch(chain: dict[str, Any]) -> None:
    # Edit task_graph after manifest was built
    tg = copy.deepcopy(chain["task_graph"])
    tg["goal"] = "mutated goal"
    _rewrite(chain["tg_path"], tg)
    with pytest.raises(NativeWorkerImportError, match="task_graph_sha_mismatch"):
        import_native_worker_result(
            source_result_path=chain["source_path"],
            runner_report_path=chain["runner_report_path"],
            source_interface="claude-cli",
            imported_at="2026-06-01T01:00:02Z",
            **_kwargs(),
        )


def test_fatal_assignment_sha_mismatch_manifest(chain: dict[str, Any]) -> None:
    asg = copy.deepcopy(chain["assignment"])
    asg["agent"]["session_id"] = "different-session"
    _rewrite(chain["asg_path"], asg)
    # rebuild runner_report so it doesn't catch first (we want manifest to catch)
    # Actually: manifest_sha changes if we rebind; we want to keep manifest_sha
    # in runner_report stale -> manifest sha check fires first.
    # Here we don't rebind: manifest still has old sha entry, runner_report
    # still has old manifest_sha. So path order:
    # manifest sha matches runner -> assignment sha mismatches manifest entry -> fatal.
    with pytest.raises(NativeWorkerImportError, match="assignment_sha_mismatch"):
        import_native_worker_result(
            source_result_path=chain["source_path"],
            runner_report_path=chain["runner_report_path"],
            source_interface="claude-cli",
            imported_at="2026-06-01T01:00:02Z",
            **_kwargs(),
        )


def test_fatal_runner_entry_missing_for_task_id(chain: dict[str, Any]) -> None:
    # Change source worker_result.task_id to one not present in runner_report.workers
    wr = copy.deepcopy(chain["worker_result"])
    wr["task_id"] = "slice-z-missing"
    _rewrite(chain["source_path"], wr)
    with pytest.raises(NativeWorkerImportError, match="runner_report.workers"):
        import_native_worker_result(
            source_result_path=chain["source_path"],
            runner_report_path=chain["runner_report_path"],
            source_interface="claude-cli",
            imported_at="2026-06-01T01:00:02Z",
            **_kwargs(),
        )


def test_fatal_cross_id_task_graph_id_mismatch(chain: dict[str, Any]) -> None:
    wr = copy.deepcopy(chain["worker_result"])
    wr["task_graph_id"] = "ao-ma-other-graph"
    _rewrite(chain["source_path"], wr)
    with pytest.raises(NativeWorkerImportError, match="cross_id_mismatch"):
        import_native_worker_result(
            source_result_path=chain["source_path"],
            runner_report_path=chain["runner_report_path"],
            source_interface="claude-cli",
            imported_at="2026-06-01T01:00:02Z",
            **_kwargs(),
        )


def test_fatal_cross_id_assignment_id_mismatch(chain: dict[str, Any]) -> None:
    wr = copy.deepcopy(chain["worker_result"])
    wr["assignment_id"] = "asg-other"
    _rewrite(chain["source_path"], wr)
    with pytest.raises(NativeWorkerImportError, match="cross_id_mismatch"):
        import_native_worker_result(
            source_result_path=chain["source_path"],
            runner_report_path=chain["runner_report_path"],
            source_interface="claude-cli",
            imported_at="2026-06-01T01:00:02Z",
            **_kwargs(),
        )


# ---------------------------------------------------------------------------
# Layer 4 — reportable policy-invalid (schema-valid invalid report, no copy)
# ---------------------------------------------------------------------------


def _import_or_fail(chain: dict[str, Any], **overrides: Any) -> dict[str, Any]:
    args = {
        "source_result_path": chain["source_path"],
        "runner_report_path": chain["runner_report_path"],
        "source_interface": "claude-cli",
        "imported_at": "2026-06-01T01:00:02Z",
    }
    args.update(overrides)
    return import_native_worker_result(**args, **_kwargs())


def test_reportable_source_interface_not_in_allowlist(chain: dict[str, Any]) -> None:
    report = _import_or_fail(chain, source_interface_allowlist=("codex-cli",))
    assert report["valid"] is False
    assert report["validation_status"] == "invalid"
    assert report["integrated_worker_result_path"] is None
    assert report["integrated_worker_result_sha256"] is None
    assert report["checks"]["source_interface_allowed"]["outcome"] == "fail"
    codes = {f["code"] for f in report["validation_findings"]}
    assert "source_interface_not_allowed" in codes


def test_reportable_source_interface_provider_mismatch(chain: dict[str, Any]) -> None:
    # operator declares claude-cli but worker_result.provider is openai
    wr = copy.deepcopy(chain["worker_result"])
    wr["worker"]["provider"] = "openai"
    _rewrite(chain["source_path"], wr)
    report = _import_or_fail(chain)
    assert report["valid"] is False
    assert report["checks"]["source_interface_provider_consistent"]["outcome"] == "fail"


def test_reportable_runner_entry_status_not_eligible(chain: dict[str, Any]) -> None:
    rr = copy.deepcopy(chain["runner_report"])
    rr["workers"][0]["status"] = "failed_base_mismatch"
    _rewrite(chain["runner_report_path"], rr)
    report = _import_or_fail(chain)
    assert report["valid"] is False
    assert report["checks"]["runner_entry_eligible"]["outcome"] == "fail"


def test_reportable_actual_empty(chain: dict[str, Any]) -> None:
    wr = copy.deepcopy(chain["worker_result"])
    wr["actual_changed_files"] = []
    _rewrite(chain["source_path"], wr)
    report = _import_or_fail(chain)
    assert report["valid"] is False
    assert report["checks"]["actual_non_empty"]["outcome"] == "fail"


def test_reportable_actual_outside_declared(chain: dict[str, Any]) -> None:
    wr = copy.deepcopy(chain["worker_result"])
    wr["actual_changed_files"] = ["src/module_a.py", "src/UNDECLARED.py"]
    _rewrite(chain["source_path"], wr)
    report = _import_or_fail(chain)
    assert report["valid"] is False
    assert report["checks"]["actual_subset_declared"]["outcome"] == "fail"


def test_reportable_known_gaps_non_empty(chain: dict[str, Any]) -> None:
    wr = copy.deepcopy(chain["worker_result"])
    wr["known_gaps"] = ["coverage incomplete"]
    _rewrite(chain["source_path"], wr)
    report = _import_or_fail(chain)
    assert report["valid"] is False
    assert report["checks"]["known_gaps_empty"]["outcome"] == "fail"


def test_reportable_declared_write_set_mismatch_assignment(chain: dict[str, Any]) -> None:
    asg = copy.deepcopy(chain["assignment"])
    asg["declared_write_set"] = ["src/module_a.py"]  # differs from worker_result + task_graph
    _rewrite(chain["asg_path"], asg)
    _rebind_manifest(chain)
    report = _import_or_fail(chain)
    assert report["valid"] is False
    assert report["checks"]["declared_write_set_bound"]["outcome"] == "fail"


def test_reportable_existing_integrated_different_hash_refuses_overwrite(
    chain: dict[str, Any],
) -> None:
    # Pre-create a different-hash integrated file
    integrated = _canonical_integrated_path(chain["artifact_dir"], _TASK_ID)
    integrated.parent.mkdir(parents=True, exist_ok=True)
    integrated.write_text('{"different": "payload"}', encoding="utf-8")
    pre_existing_sha = _compute_sha256(integrated)
    report = _import_or_fail(chain)
    assert report["valid"] is False
    assert report["checks"]["source_integrated_hash_match"]["outcome"] == "fail"
    codes = {f["code"] for f in report["validation_findings"]}
    assert "existing_integrated_different_hash" in codes
    # NOT overwritten
    assert _compute_sha256(integrated) == pre_existing_sha


def test_reportable_cross_ref_base_sha_mismatch(chain: dict[str, Any]) -> None:
    wr = copy.deepcopy(chain["worker_result"])
    wr["base_sha"] = "9" * 40
    _rewrite(chain["source_path"], wr)
    report = _import_or_fail(chain)
    assert report["valid"] is False
    assert report["checks"]["cross_ref_consistent"]["outcome"] == "fail"


# ---------------------------------------------------------------------------
# Layer 5 — verify_import_binding
# ---------------------------------------------------------------------------


def test_verify_happy_round_trip(chain: dict[str, Any]) -> None:
    report = _import_or_fail(chain)
    assert report["valid"] is True
    verify_import_binding(report, import_report_schema=SCHEMAS["import_report"])


def test_verify_forged_valid_true_rejected(chain: dict[str, Any]) -> None:
    report = _import_or_fail(chain, source_interface_allowlist=("codex-cli",))
    assert report["valid"] is False
    # Forge: flip valid + add an integrated_path stub
    forged = copy.deepcopy(report)
    forged["valid"] = True
    forged["validation_status"] = "valid"
    # schema requires integrated_path string when valid; place a real path
    integrated = chain["artifact_dir"] / "workers" / _TASK_ID / "worker_result.v1.json"
    integrated.parent.mkdir(parents=True, exist_ok=True)
    integrated.write_text(chain["source_path"].read_text(encoding="utf-8"), encoding="utf-8")
    forged["integrated_worker_result_path"] = str(integrated)
    forged["integrated_worker_result_sha256"] = _compute_sha256(integrated)
    with pytest.raises(NativeWorkerImportError, match="forged valid flag"):
        verify_import_binding(forged, import_report_schema=SCHEMAS["import_report"])


def test_verify_source_changed_after_import(chain: dict[str, Any]) -> None:
    report = _import_or_fail(chain)
    # mutate source after import
    chain["source_path"].write_text('{"changed": true}', encoding="utf-8")
    with pytest.raises(NativeWorkerImportError, match="source_result file has changed"):
        verify_import_binding(report, import_report_schema=SCHEMAS["import_report"])


def test_verify_integrated_changed_after_import(chain: dict[str, Any]) -> None:
    report = _import_or_fail(chain)
    assert report["valid"] is True
    integrated = Path(report["integrated_worker_result_path"])
    integrated.write_text('{"tampered": true}', encoding="utf-8")
    with pytest.raises(NativeWorkerImportError, match="integrated file has changed"):
        verify_import_binding(report, import_report_schema=SCHEMAS["import_report"])


def test_verify_guard_flag_drift_rejected(chain: dict[str, Any]) -> None:
    report = _import_or_fail(chain)
    forged = copy.deepcopy(report)
    forged["guard_flags"]["live_adapter_execution"] = True
    # schema is const false so jsonschema will block; expect schema-invalid path
    with pytest.raises(NativeWorkerImportError, match="schema-invalid"):
        verify_import_binding(forged, import_report_schema=SCHEMAS["import_report"])


def test_verify_register_authority_drift_rejected(chain: dict[str, Any]) -> None:
    report = _import_or_fail(chain)
    forged = copy.deepcopy(report)
    forged["register_authority"] = "wider_authority"
    with pytest.raises(NativeWorkerImportError, match="schema-invalid"):
        verify_import_binding(forged, import_report_schema=SCHEMAS["import_report"])


# ---------------------------------------------------------------------------
# Layer 6 — schema-level negative
# ---------------------------------------------------------------------------


def test_schema_import_mode_must_be_import_only(chain: dict[str, Any]) -> None:
    report = _import_or_fail(chain)
    forged = copy.deepcopy(report)
    forged["import_mode"] = "live_execute"
    with pytest.raises(NativeWorkerImportError, match="schema-invalid"):
        verify_import_binding(forged, import_report_schema=SCHEMAS["import_report"])


def test_schema_execution_performed_by_ao_kernel_must_be_false(chain: dict[str, Any]) -> None:
    report = _import_or_fail(chain)
    forged = copy.deepcopy(report)
    forged["execution_performed_by_ao_kernel"] = True
    with pytest.raises(NativeWorkerImportError, match="schema-invalid"):
        verify_import_binding(forged, import_report_schema=SCHEMAS["import_report"])


def test_schema_ai_output_release_authority_must_be_false(chain: dict[str, Any]) -> None:
    report = _import_or_fail(chain)
    forged = copy.deepcopy(report)
    forged["ai_output_release_authority"] = True
    with pytest.raises(NativeWorkerImportError, match="schema-invalid"):
        verify_import_binding(forged, import_report_schema=SCHEMAS["import_report"])


def test_schema_github_write_authorized_must_be_false(chain: dict[str, Any]) -> None:
    report = _import_or_fail(chain)
    forged = copy.deepcopy(report)
    forged["github_write_authorized"] = True
    with pytest.raises(NativeWorkerImportError, match="schema-invalid"):
        verify_import_binding(forged, import_report_schema=SCHEMAS["import_report"])


def test_schema_check_outcome_invalid_enum_rejected(chain: dict[str, Any]) -> None:
    report = _import_or_fail(chain)
    forged = copy.deepcopy(report)
    forged["checks"]["actual_non_empty"]["outcome"] = "maybe"
    with pytest.raises(NativeWorkerImportError, match="schema-invalid"):
        verify_import_binding(forged, import_report_schema=SCHEMAS["import_report"])


def test_schema_missing_required_check_key(chain: dict[str, Any]) -> None:
    report = _import_or_fail(chain)
    forged = copy.deepcopy(report)
    del forged["checks"]["actual_non_empty"]
    with pytest.raises(NativeWorkerImportError, match="schema-invalid"):
        verify_import_binding(forged, import_report_schema=SCHEMAS["import_report"])


def test_schema_finding_severity_enum_rejected(chain: dict[str, Any]) -> None:
    report = _import_or_fail(chain)
    forged = copy.deepcopy(report)
    forged["validation_findings"].append({"code": "x", "severity": "info", "message": "y"})
    with pytest.raises(NativeWorkerImportError, match="schema-invalid"):
        verify_import_binding(forged, import_report_schema=SCHEMAS["import_report"])


def test_schema_valid_true_requires_integrated_string(chain: dict[str, Any]) -> None:
    """if/then: validation_status=valid requires integrated_path string."""

    report = _import_or_fail(chain)
    forged = copy.deepcopy(report)
    forged["integrated_worker_result_path"] = None
    with pytest.raises(NativeWorkerImportError, match="schema-invalid"):
        verify_import_binding(forged, import_report_schema=SCHEMAS["import_report"])


def test_schema_valid_false_requires_integrated_null(chain: dict[str, Any]) -> None:
    """if/then: validation_status=invalid requires integrated_path null."""

    report = _import_or_fail(chain, source_interface_allowlist=("codex-cli",))
    forged = copy.deepcopy(report)
    forged["integrated_worker_result_path"] = "/tmp/whatever"
    with pytest.raises(NativeWorkerImportError, match="schema-invalid"):
        verify_import_binding(forged, import_report_schema=SCHEMAS["import_report"])


# ---------------------------------------------------------------------------
# Layer 7 — manifest envelope coverage (Codex iter-2 absorb: anchoring)
# ---------------------------------------------------------------------------


def test_fatal_manifest_not_object(chain: dict[str, Any]) -> None:
    chain["manifest_path"].write_text("[]", encoding="utf-8")
    with pytest.raises(NativeWorkerImportError, match="manifest_sha_mismatch|manifest must be"):
        _import_or_fail(chain)


def test_fatal_manifest_schema_version_wrong(chain: dict[str, Any]) -> None:
    bad = copy.deepcopy(chain["manifest"])
    bad["schema_version"] = "wrong-version"
    _rewrite(chain["manifest_path"], bad)
    # manifest_sha_mismatch triggers first (we mutated content); accept either
    with pytest.raises(NativeWorkerImportError, match="manifest"):
        _import_or_fail(chain)


def test_fatal_manifest_task_graph_id_bad_pattern(chain: dict[str, Any]) -> None:
    bad = copy.deepcopy(chain["manifest"])
    bad["task_graph_id"] = "NOT-MA-CONFORMANT"
    _rewrite(chain["manifest_path"], bad)
    with pytest.raises(NativeWorkerImportError, match="manifest"):
        _import_or_fail(chain)


def test_fatal_manifest_artifacts_not_list(chain: dict[str, Any]) -> None:
    bad = copy.deepcopy(chain["manifest"])
    bad["artifacts"] = "not a list"
    _rewrite(chain["manifest_path"], bad)
    with pytest.raises(NativeWorkerImportError, match="manifest"):
        _import_or_fail(chain)


def test_fatal_manifest_artifact_traversal_path(chain: dict[str, Any]) -> None:
    bad = copy.deepcopy(chain["manifest"])
    bad["artifacts"].append(
        {"path": "../escape.v1.json", "sha256": "sha256:" + "f" * 64, "size_bytes": 10}
    )
    _rewrite(chain["manifest_path"], bad)
    with pytest.raises(NativeWorkerImportError, match="manifest"):
        _import_or_fail(chain)


def test_fatal_manifest_duplicate_artifact_path(chain: dict[str, Any]) -> None:
    bad = copy.deepcopy(chain["manifest"])
    # duplicate the task_graph entry
    bad["artifacts"].append(dict(bad["artifacts"][0]))
    _rewrite(chain["manifest_path"], bad)
    with pytest.raises(NativeWorkerImportError, match="manifest"):
        _import_or_fail(chain)


def test_fatal_manifest_zero_task_graph_entries(chain: dict[str, Any]) -> None:
    bad = copy.deepcopy(chain["manifest"])
    bad["artifacts"] = [
        e for e in bad["artifacts"] if e["path"] != "task_graph.v1.json"
    ]
    _rewrite(chain["manifest_path"], bad)
    with pytest.raises(NativeWorkerImportError, match="manifest"):
        _import_or_fail(chain)


def test_fatal_manifest_missing_task_graph_entry_after_rebind(chain: dict[str, Any]) -> None:
    # Drop task_graph entry then properly re-sync runner_report
    bad = copy.deepcopy(chain["manifest"])
    bad["artifacts"] = [e for e in bad["artifacts"] if e["path"] != "task_graph.v1.json"]
    _rewrite(chain["manifest_path"], bad)
    new_manifest_sha = _file_sha(chain["manifest_path"])
    rr = copy.deepcopy(chain["runner_report"])
    rr["manifest_sha256"] = new_manifest_sha
    _rewrite(chain["runner_report_path"], rr)
    with pytest.raises(NativeWorkerImportError, match="manifest"):
        _import_or_fail(chain)


# ---------------------------------------------------------------------------
# Layer 8 — assignment / cross-id fatal coverage
# ---------------------------------------------------------------------------


def test_fatal_cross_id_task_id_worker_vs_assignment(chain: dict[str, Any]) -> None:
    asg = copy.deepcopy(chain["assignment"])
    asg["task_id"] = "other-task"
    _rewrite(chain["asg_path"], asg)
    _rebind_manifest(chain)
    with pytest.raises(NativeWorkerImportError, match="task_id"):
        _import_or_fail(chain)


def test_fatal_assignment_ref_missing_in_runner_entry(chain: dict[str, Any]) -> None:
    rr = copy.deepcopy(chain["runner_report"])
    rr["workers"][0]["assignment_ref"] = ""
    _rewrite(chain["runner_report_path"], rr)
    # mutated runner_report changes manifest_sha bind reasoning; rebind to keep
    # manifest sha consistent — but runner_report.manifest_sha256 stays valid
    # because manifest was not changed; only runner_report mutated.
    # However, runner_report schema requires assignment_ref minLength 1 — so
    # schema-invalid fatal will fire on runner_report instead. Accept either.
    with pytest.raises(NativeWorkerImportError, match="runner_report|assignment_ref"):
        _import_or_fail(chain)


# ---------------------------------------------------------------------------
# Layer 9 — verify defensive branches
# ---------------------------------------------------------------------------


def test_verify_skips_source_check_when_source_missing(chain: dict[str, Any]) -> None:
    report = _import_or_fail(chain)
    # Remove the source file; verify should still pass (source check is
    # only performed when the source path still exists on disk).
    chain["source_path"].unlink()
    verify_import_binding(report, import_report_schema=SCHEMAS["import_report"])


def test_verify_invalid_report_does_not_require_integrated(chain: dict[str, Any]) -> None:
    report = _import_or_fail(chain, source_interface_allowlist=("codex-cli",))
    assert report["valid"] is False
    # No integrated path required when valid=false; verify_import_binding
    # should not raise on integrated absence.
    verify_import_binding(report, import_report_schema=SCHEMAS["import_report"])


# ---------------------------------------------------------------------------
# Layer 10 — Codex iter-5 absorb: allowlist pre-validation (fatal)
# ---------------------------------------------------------------------------


def test_allowlist_duplicate_entry_fatal_before_copy(chain: dict[str, Any]) -> None:
    integrated = _canonical_integrated_path(chain["artifact_dir"], _TASK_ID)
    # Ensure no copy yet
    assert not integrated.exists()
    with pytest.raises(NativeWorkerImportError, match="duplicate"):
        _import_or_fail(chain, source_interface_allowlist=("claude-cli", "claude-cli"))
    # NO copy was written (Codex iter-5 contract)
    assert not integrated.exists()


def test_allowlist_unknown_entry_fatal_before_copy(chain: dict[str, Any]) -> None:
    integrated = _canonical_integrated_path(chain["artifact_dir"], _TASK_ID)
    assert not integrated.exists()
    with pytest.raises(NativeWorkerImportError, match="unknown"):
        _import_or_fail(chain, source_interface_allowlist=("claude-cli", "bogus-cli"))
    assert not integrated.exists()


def test_allowlist_empty_fatal(chain: dict[str, Any]) -> None:
    with pytest.raises(NativeWorkerImportError, match="non-empty"):
        _import_or_fail(chain, source_interface_allowlist=())


def test_allowlist_non_string_entry_fatal(chain: dict[str, Any]) -> None:
    with pytest.raises(NativeWorkerImportError, match="non-string"):
        # type: ignore[arg-type]
        _import_or_fail(chain, source_interface_allowlist=("claude-cli", 42))  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Layer 11 — Codex iter-5 absorb: invalid worker_status omitted (not faked)
# ---------------------------------------------------------------------------


def test_invalid_runner_status_omits_worker_status_field(chain: dict[str, Any]) -> None:
    rr = copy.deepcopy(chain["runner_report"])
    rr["workers"][0]["status"] = "failed_overlap"
    _rewrite(chain["runner_report_path"], rr)
    report = _import_or_fail(chain)
    assert report["valid"] is False
    # worker_status MUST NOT be set to a misleading "prepared" placeholder.
    assert "worker_status" not in report["runner_report_ref"]


# ---------------------------------------------------------------------------
# Layer 12 — Codex iter-5 absorb: verify full cross-bind replay
# ---------------------------------------------------------------------------


def _verify_kwargs() -> dict[str, Any]:
    return {
        "import_report_schema": SCHEMAS["import_report"],
        "worker_result_schema": SCHEMAS["worker_result"],
        "runner_report_schema": SCHEMAS["runner_report"],
        "task_graph_schema": SCHEMAS["task_graph"],
        "assignment_schema": SCHEMAS["assignment"],
    }


def test_verify_full_replay_happy(chain: dict[str, Any]) -> None:
    report = _import_or_fail(chain)
    assert report["valid"] is True
    verify_import_binding(report, **_verify_kwargs())


def test_verify_full_replay_detects_runner_report_drift(chain: dict[str, Any]) -> None:
    report = _import_or_fail(chain)
    # Tamper runner_report after import; sha bind in report now stale.
    rr = copy.deepcopy(chain["runner_report"])
    rr["generated_at"] = "2099-01-01T00:00:00Z"
    _rewrite(chain["runner_report_path"], rr)
    with pytest.raises(NativeWorkerImportError, match="runner_report sha drift"):
        verify_import_binding(report, **_verify_kwargs())


def test_verify_full_replay_detects_manifest_drift(chain: dict[str, Any]) -> None:
    report = _import_or_fail(chain)
    mf = copy.deepcopy(chain["manifest"])
    mf["generated_at"] = "2099-01-01T00:00:00Z"
    _rewrite(chain["manifest_path"], mf)
    with pytest.raises(NativeWorkerImportError, match="manifest sha drift"):
        verify_import_binding(report, **_verify_kwargs())


def test_verify_full_replay_detects_assignment_drift(chain: dict[str, Any]) -> None:
    report = _import_or_fail(chain)
    asg = copy.deepcopy(chain["assignment"])
    asg["agent"]["session_id"] = "tampered-session"
    _rewrite(chain["asg_path"], asg)
    with pytest.raises(NativeWorkerImportError, match="assignment sha drift"):
        verify_import_binding(report, **_verify_kwargs())


def test_verify_full_replay_detects_task_graph_drift(chain: dict[str, Any]) -> None:
    report = _import_or_fail(chain)
    tg = copy.deepcopy(chain["task_graph"])
    tg["goal"] = "tampered goal"
    _rewrite(chain["tg_path"], tg)
    with pytest.raises(NativeWorkerImportError, match="task_graph sha drift"):
        verify_import_binding(report, **_verify_kwargs())


def test_verify_source_integrated_sha_equality(chain: dict[str, Any]) -> None:
    """Codex iter-5: valid report's source/integrated sha MUST be equal."""

    report = _import_or_fail(chain)
    forged = copy.deepcopy(report)
    forged["source_result_sha256"] = "sha256:" + "a" * 64
    with pytest.raises(NativeWorkerImportError, match="source/integrated sha mismatch|source_result file has changed"):
        verify_import_binding(forged, **_verify_kwargs())


# ---------------------------------------------------------------------------
# Layer 13 — Codex iter-5 absorb: CLI forbidden flag pin (RI-7.8c)
# ---------------------------------------------------------------------------


def _build_main_parser() -> Any:
    """Replicate cli.py main() parser construction in isolation."""

    import argparse

    from ao_kernel.orchestration.cli_handlers import add_orchestration_subparser

    parser = argparse.ArgumentParser(prog="ao-kernel")
    sub = parser.add_subparsers(dest="command")
    add_orchestration_subparser(sub)
    return parser


@pytest.mark.parametrize(
    "forbidden_flag",
    ["--adapter", "--prompt", "--model", "--api-key", "--url", "--pr-write"],
)
def test_cli_rejects_forbidden_flags_via_argparse(forbidden_flag: str) -> None:
    parser = _build_main_parser()
    base = [
        "orchestration",
        "native-import",
        "--result",
        "/tmp/x.json",
        "--runner-report",
        "/tmp/r.json",
        "--source-interface",
        "claude-cli",
        "--out",
        "/tmp/o.json",
    ]
    with pytest.raises(SystemExit):
        parser.parse_args(base + [forbidden_flag, "value"])


def test_cli_rejects_unknown_allow_source_interface_via_choices() -> None:
    parser = _build_main_parser()
    base = [
        "orchestration",
        "native-import",
        "--result",
        "/tmp/x.json",
        "--runner-report",
        "/tmp/r.json",
        "--source-interface",
        "claude-cli",
        "--out",
        "/tmp/o.json",
        "--allow-source-interface",
        "bogus-cli",
    ]
    with pytest.raises(SystemExit):
        parser.parse_args(base)


# ---------------------------------------------------------------------------
# Layer 14 — verify cross-bind replay coverage (extra branches)
# ---------------------------------------------------------------------------


def test_verify_full_replay_detects_runner_report_missing(chain: dict[str, Any]) -> None:
    report = _import_or_fail(chain)
    chain["runner_report_path"].unlink()
    with pytest.raises(NativeWorkerImportError, match="runner_report file missing"):
        verify_import_binding(report, **_verify_kwargs())


def test_verify_full_replay_detects_manifest_missing(chain: dict[str, Any]) -> None:
    report = _import_or_fail(chain)
    chain["manifest_path"].unlink()
    with pytest.raises(NativeWorkerImportError, match="manifest file missing"):
        verify_import_binding(report, **_verify_kwargs())


def test_verify_full_replay_detects_task_graph_missing(chain: dict[str, Any]) -> None:
    report = _import_or_fail(chain)
    chain["tg_path"].unlink()
    with pytest.raises(NativeWorkerImportError, match="task_graph file missing"):
        verify_import_binding(report, **_verify_kwargs())


def test_verify_full_replay_detects_assignment_missing(chain: dict[str, Any]) -> None:
    report = _import_or_fail(chain)
    chain["asg_path"].unlink()
    with pytest.raises(NativeWorkerImportError, match="assignment file missing"):
        verify_import_binding(report, **_verify_kwargs())


def test_verify_full_replay_detects_cross_id_drift(chain: dict[str, Any]) -> None:
    report = _import_or_fail(chain)
    # Mutate task_graph_id in task_graph; this forces an envelope rewrite.
    tg = copy.deepcopy(chain["task_graph"])
    tg["task_graph_id"] = "ao-ma-different"
    _rewrite(chain["tg_path"], tg)
    # task_graph sha drifts first.
    with pytest.raises(NativeWorkerImportError):
        verify_import_binding(report, **_verify_kwargs())


def test_verify_full_replay_detects_runner_entry_missing(chain: dict[str, Any]) -> None:
    report = _import_or_fail(chain)
    rr = copy.deepcopy(chain["runner_report"])
    rr["workers"] = []  # drop the entry
    _rewrite(chain["runner_report_path"], rr)
    # runner sha will drift first.
    with pytest.raises(NativeWorkerImportError):
        verify_import_binding(report, **_verify_kwargs())


# ---------------------------------------------------------------------------
# Layer 15 — Codex iter-6 absorb: verify full semantic replay
# (rebound refs + semantic mismatch must still be rejected)
# ---------------------------------------------------------------------------


def _rebind_to_disk(chain: dict[str, Any]) -> None:
    """Recompute manifest + runner_report shas after task_graph/assignment
    were mutated. This produces a coherent on-disk set whose ref sha
    bindings match the new disk state; only the semantic chain can fail."""

    manifest = copy.deepcopy(chain["manifest"])
    tg_sha = _file_sha(chain["tg_path"])
    asg_sha = _file_sha(chain["asg_path"])
    for entry in manifest["artifacts"]:
        if entry["path"] == "task_graph.v1.json":
            entry["sha256"] = tg_sha
            entry["size_bytes"] = _file_size(chain["tg_path"])
        elif entry["path"].startswith("agent_assignment-"):
            entry["sha256"] = asg_sha
            entry["size_bytes"] = _file_size(chain["asg_path"])
    _rewrite(chain["manifest_path"], manifest)
    new_manifest_sha = _file_sha(chain["manifest_path"])
    rr = copy.deepcopy(chain["runner_report"])
    rr["manifest_sha256"] = new_manifest_sha
    for w in rr["workers"]:
        if w["task_id"] == _TASK_ID:
            w["assignment_sha256"] = asg_sha
    _rewrite(chain["runner_report_path"], rr)


def _rebound_report(chain: dict[str, Any], original_report: dict[str, Any]) -> dict[str, Any]:
    """Forge an import_report whose artifact refs match the (newly rebound)
    on-disk state. Used to drive the semantic-replay branches."""

    forged = copy.deepcopy(original_report)
    forged["runner_report_ref"]["sha256"] = _file_sha(chain["runner_report_path"])
    forged["manifest_ref"]["sha256"] = _file_sha(chain["manifest_path"])
    forged["task_graph_ref"]["sha256"] = _file_sha(chain["tg_path"])
    forged["assignment_ref"]["sha256"] = _file_sha(chain["asg_path"])
    return forged


def test_verify_full_replay_rejects_integrated_path_non_canonical(
    chain: dict[str, Any], tmp_path: Path
) -> None:
    report = _import_or_fail(chain)
    forged = copy.deepcopy(report)
    # Move the integrated file to a non-canonical sub-path under artifact_dir.
    alt = chain["artifact_dir"] / "workers" / "alt-sub" / "worker_result.v1.json"
    alt.parent.mkdir(parents=True, exist_ok=True)
    src = Path(report["integrated_worker_result_path"])
    alt.write_bytes(src.read_bytes())
    forged["integrated_worker_result_path"] = str(alt)
    # keep the integrated sha equal to source
    with pytest.raises(NativeWorkerImportError, match="canonical"):
        verify_import_binding(forged, **_verify_kwargs())


def test_verify_full_replay_rejects_worker_result_task_graph_id_drift(
    chain: dict[str, Any],
) -> None:
    report = _import_or_fail(chain)
    integrated = Path(report["integrated_worker_result_path"])
    wr = json.loads(integrated.read_text(encoding="utf-8"))
    wr["task_graph_id"] = "ao-ma-attacker-graph"
    integrated.write_text(json.dumps(wr, sort_keys=True), encoding="utf-8")
    # integrated sha drifts first
    with pytest.raises(NativeWorkerImportError):
        verify_import_binding(report, **_verify_kwargs())


def test_verify_full_replay_rejects_declared_write_set_drift(
    chain: dict[str, Any],
) -> None:
    report = _import_or_fail(chain)
    # Mutate assignment declared_write_set; rebind refs so sha kapısı geçer.
    asg = copy.deepcopy(chain["assignment"])
    asg["declared_write_set"] = ["src/different.py"]
    _rewrite(chain["asg_path"], asg)
    _rebind_to_disk(chain)
    forged = _rebound_report(chain, report)
    with pytest.raises(NativeWorkerImportError, match="declared_write_set"):
        verify_import_binding(forged, **_verify_kwargs())


def test_verify_full_replay_rejects_cross_ref_drift(chain: dict[str, Any]) -> None:
    report = _import_or_fail(chain)
    # Mutate assignment.base_sha so cross-ref breaks; rebind refs.
    asg = copy.deepcopy(chain["assignment"])
    asg["base_sha"] = "9" * 40
    _rewrite(chain["asg_path"], asg)
    _rebind_to_disk(chain)
    forged = _rebound_report(chain, report)
    with pytest.raises(NativeWorkerImportError, match="base_sha"):
        verify_import_binding(forged, **_verify_kwargs())


def test_verify_full_replay_rejects_known_gaps_drift(chain: dict[str, Any]) -> None:
    report = _import_or_fail(chain)
    integrated = Path(report["integrated_worker_result_path"])
    wr = json.loads(integrated.read_text(encoding="utf-8"))
    wr["known_gaps"] = ["something missing"]
    integrated.write_text(json.dumps(wr, sort_keys=True), encoding="utf-8")
    # integrated sha drifts first
    with pytest.raises(NativeWorkerImportError):
        verify_import_binding(report, **_verify_kwargs())


# ---------------------------------------------------------------------------
# Layer 16 — semantic-replay coverage: rebound integrated content
# ---------------------------------------------------------------------------


def _re_import_with_mutated_source(
    chain: dict[str, Any], mutator: Any
) -> dict[str, Any]:
    """Mutate the source worker_result via ``mutator(dict)``, re-import to
    keep all build-side bindings coherent, return the new valid report.
    The mutator may only change fields the build-side semantic checks
    do NOT cover (so the result is still valid). Currently used to
    pre-stage rebound semantic-mismatch via post-import overwrite."""

    wr = json.loads(chain["source_path"].read_text(encoding="utf-8"))
    mutator(wr)
    chain["source_path"].write_text(json.dumps(wr, sort_keys=True), encoding="utf-8")
    return _import_or_fail(chain)


def test_verify_full_replay_rejects_worker_result_head_ref_drift(
    chain: dict[str, Any],
) -> None:
    report = _import_or_fail(chain)
    integrated = Path(report["integrated_worker_result_path"])
    wr = json.loads(integrated.read_text(encoding="utf-8"))
    wr["head_ref"] = "codex/different-branch"
    new_bytes = json.dumps(wr, sort_keys=True).encode("utf-8")
    integrated.write_bytes(new_bytes)
    # Forge: rebase source_sha + integrated_sha to the new content so the
    # sha equality kapısını geçer; semantic head_ref drift verify'da
    # yakalanmalı.
    forged = copy.deepcopy(report)
    new_sha = "sha256:" + hashlib.sha256(new_bytes).hexdigest()
    chain["source_path"].write_bytes(new_bytes)
    forged["source_result_sha256"] = new_sha
    forged["integrated_worker_result_sha256"] = new_sha
    with pytest.raises(NativeWorkerImportError, match="head_ref"):
        verify_import_binding(forged, **_verify_kwargs())


def test_verify_full_replay_rejects_worker_result_task_id_drift(
    chain: dict[str, Any],
) -> None:
    report = _import_or_fail(chain)
    integrated = Path(report["integrated_worker_result_path"])
    wr = json.loads(integrated.read_text(encoding="utf-8"))
    wr["task_id"] = "different-slice"
    new_bytes = json.dumps(wr, sort_keys=True).encode("utf-8")
    integrated.write_bytes(new_bytes)
    chain["source_path"].write_bytes(new_bytes)
    forged = copy.deepcopy(report)
    new_sha = "sha256:" + hashlib.sha256(new_bytes).hexdigest()
    forged["source_result_sha256"] = new_sha
    forged["integrated_worker_result_sha256"] = new_sha
    with pytest.raises(NativeWorkerImportError, match="task_id"):
        verify_import_binding(forged, **_verify_kwargs())


def test_verify_full_replay_rejects_worker_result_assignment_id_drift(
    chain: dict[str, Any],
) -> None:
    report = _import_or_fail(chain)
    integrated = Path(report["integrated_worker_result_path"])
    wr = json.loads(integrated.read_text(encoding="utf-8"))
    wr["assignment_id"] = "different-asg"
    new_bytes = json.dumps(wr, sort_keys=True).encode("utf-8")
    integrated.write_bytes(new_bytes)
    chain["source_path"].write_bytes(new_bytes)
    forged = copy.deepcopy(report)
    new_sha = "sha256:" + hashlib.sha256(new_bytes).hexdigest()
    forged["source_result_sha256"] = new_sha
    forged["integrated_worker_result_sha256"] = new_sha
    with pytest.raises(NativeWorkerImportError, match="assignment_id"):
        verify_import_binding(forged, **_verify_kwargs())


def test_verify_full_replay_rejects_worker_result_actual_empty(
    chain: dict[str, Any],
) -> None:
    report = _import_or_fail(chain)
    integrated = Path(report["integrated_worker_result_path"])
    wr = json.loads(integrated.read_text(encoding="utf-8"))
    wr["actual_changed_files"] = []
    new_bytes = json.dumps(wr, sort_keys=True).encode("utf-8")
    integrated.write_bytes(new_bytes)
    chain["source_path"].write_bytes(new_bytes)
    forged = copy.deepcopy(report)
    new_sha = "sha256:" + hashlib.sha256(new_bytes).hexdigest()
    forged["source_result_sha256"] = new_sha
    forged["integrated_worker_result_sha256"] = new_sha
    with pytest.raises(NativeWorkerImportError, match="empty"):
        verify_import_binding(forged, **_verify_kwargs())


def test_verify_full_replay_rejects_worker_result_actual_outside_declared(
    chain: dict[str, Any],
) -> None:
    report = _import_or_fail(chain)
    integrated = Path(report["integrated_worker_result_path"])
    wr = json.loads(integrated.read_text(encoding="utf-8"))
    wr["actual_changed_files"] = ["src/UNDECLARED.py"]
    new_bytes = json.dumps(wr, sort_keys=True).encode("utf-8")
    integrated.write_bytes(new_bytes)
    chain["source_path"].write_bytes(new_bytes)
    forged = copy.deepcopy(report)
    new_sha = "sha256:" + hashlib.sha256(new_bytes).hexdigest()
    forged["source_result_sha256"] = new_sha
    forged["integrated_worker_result_sha256"] = new_sha
    with pytest.raises(NativeWorkerImportError, match="subset"):
        verify_import_binding(forged, **_verify_kwargs())


# ---------------------------------------------------------------------------
# Layer 17 — Codex iter-7 absorb: verify replays runner-status, allowlist,
# and provider consistency invariants
# ---------------------------------------------------------------------------


def test_verify_full_replay_rejects_rebound_runner_status_non_eligible(
    chain: dict[str, Any],
) -> None:
    report = _import_or_fail(chain)
    # Mutate runner_status on disk; rebind shas so all artifact sha checks pass.
    rr = copy.deepcopy(chain["runner_report"])
    rr["workers"][0]["status"] = "failed_overlap"
    _rewrite(chain["runner_report_path"], rr)
    forged = copy.deepcopy(report)
    forged["runner_report_ref"]["sha256"] = _file_sha(chain["runner_report_path"])
    # remove worker_status mirror (rebound report shouldn't claim "prepared")
    forged["runner_report_ref"].pop("worker_status", None)
    with pytest.raises(NativeWorkerImportError, match="runner_entry.status"):
        verify_import_binding(forged, **_verify_kwargs())


def test_verify_full_replay_rejects_worker_status_mirror_drift(
    chain: dict[str, Any],
) -> None:
    report = _import_or_fail(chain)
    # On-disk runner_status is "prepared"; report mirrors that. Forge
    # the mirror to a different (also eligible) value to drive the
    # mirror-mismatch branch.
    forged = copy.deepcopy(report)
    forged["runner_report_ref"]["worker_status"] = "skipped_existing_idempotent"
    with pytest.raises(NativeWorkerImportError, match="worker_status"):
        verify_import_binding(forged, **_verify_kwargs())


def test_verify_full_replay_rejects_source_interface_not_in_allowlist(
    chain: dict[str, Any],
) -> None:
    report = _import_or_fail(chain)
    forged = copy.deepcopy(report)
    forged["effective_source_interface_allowlist"] = ["codex-cli"]  # excludes claude-cli
    with pytest.raises(NativeWorkerImportError, match="not in.*effective_source_interface_allowlist"):
        verify_import_binding(forged, **_verify_kwargs())


def test_verify_full_replay_rejects_source_interface_provider_mismatch(
    chain: dict[str, Any],
) -> None:
    report = _import_or_fail(chain)
    forged = copy.deepcopy(report)
    forged["worker_provider"] = "openai"  # mismatch with claude-cli
    with pytest.raises(NativeWorkerImportError, match="expects worker_provider"):
        verify_import_binding(forged, **_verify_kwargs())


def test_verify_full_replay_rejects_worker_provider_disk_drift(
    chain: dict[str, Any],
) -> None:
    report = _import_or_fail(chain)
    # On-disk integrated worker.provider differs from report; rebase sha.
    integrated = Path(report["integrated_worker_result_path"])
    wr = json.loads(integrated.read_text(encoding="utf-8"))
    # keep worker_provider in report = anthropic; flip integrated to openai
    # (will fail the (source_interface, worker_provider) map check first,
    #  because report.worker_provider remains anthropic but disk says openai
    #  — disk vs report compare path triggers)
    wr["worker"]["provider"] = "openai"
    new_bytes = json.dumps(wr, sort_keys=True).encode("utf-8")
    integrated.write_bytes(new_bytes)
    chain["source_path"].write_bytes(new_bytes)
    forged = copy.deepcopy(report)
    new_sha = "sha256:" + hashlib.sha256(new_bytes).hexdigest()
    forged["source_result_sha256"] = new_sha
    forged["integrated_worker_result_sha256"] = new_sha
    with pytest.raises(NativeWorkerImportError, match="provider"):
        verify_import_binding(forged, **_verify_kwargs())
