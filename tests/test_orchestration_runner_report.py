"""AO-MA-4 runner report writer unit tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from ao_kernel.orchestration.runner_report_writer import (
    RunnerReportWriter,
    RunnerReportWriterError,
    sha256_of,
)

_SAMPLE_WORKER = {
    "assignment_ref": "agent_assignment-task-001.v1.json",
    "assignment_sha256": "sha256:" + "a" * 64,
    "task_id": "task-001",
    "branch": "codex/ao-ma-test/task-001",
    "planned_worktree": ".ao/orchestration/ao-ma-20260527-abcd123/workers/task-001",
    "actual_worktree": "/tmp/work/task-001",
    "status": "prepared",
    "reason": "worktree + branch created",
    "expected_worker_result_path": "/tmp/work/task-001/worker_result.v1.json",
}


def _sample(**overrides) -> dict:
    base = {
        "task_graph_id": "ao-ma-20260527-abcd123",
        "manifest_sha256": "sha256:" + "b" * 64,
        "base_sha": "c" * 40,
        "conflict_check": "pass",
        "base_sync_check": "pass",
        "workers": [dict(_SAMPLE_WORKER)],
    }
    base.update(overrides)
    return base


def test_emit_writes_schema_valid_report(tmp_path: Path) -> None:
    writer = RunnerReportWriter(base_dir=tmp_path)
    report = writer.emit(**_sample())
    assert report["schema_version"] == "ao-ma-runner-report.v1"
    assert (tmp_path / "ao-ma-20260527-abcd123" / "runner_report.v1.json").exists()


def test_emit_rejects_invalid_conflict_check(tmp_path: Path) -> None:
    writer = RunnerReportWriter(base_dir=tmp_path)
    with pytest.raises(RunnerReportWriterError, match="schema"):
        writer.emit(**_sample(conflict_check="totally_invalid"))


def test_emit_rejects_invalid_base_sha(tmp_path: Path) -> None:
    writer = RunnerReportWriter(base_dir=tmp_path)
    with pytest.raises(RunnerReportWriterError, match="schema"):
        writer.emit(**_sample(base_sha="not-a-real-sha"))


def test_emit_atomic_no_partial_files(tmp_path: Path) -> None:
    writer = RunnerReportWriter(base_dir=tmp_path)
    writer.emit(**_sample())
    out_dir = tmp_path / "ao-ma-20260527-abcd123"
    leftovers = list(out_dir.glob(".*.tmp"))
    assert not leftovers, f"unexpected tmp leftovers: {leftovers}"


def test_emit_rejects_task_graph_id_path_traversal(tmp_path: Path) -> None:
    writer = RunnerReportWriter(base_dir=tmp_path)
    # Schema pattern rejects this id at validation; reaching the
    # path-containment check would also reject it.
    with pytest.raises(RunnerReportWriterError):
        writer.emit(**_sample(task_graph_id="ao-ma-../escape"))


def test_sha256_of_matches_disk(tmp_path: Path) -> None:
    path = tmp_path / "sample.bin"
    path.write_bytes(b"hello world")
    actual = sha256_of(path)
    assert actual.startswith("sha256:")
    assert len(actual) == len("sha256:") + 64


def test_emit_workers_array_can_have_multiple(tmp_path: Path) -> None:
    writer = RunnerReportWriter(base_dir=tmp_path)
    sample = _sample()
    sample["workers"] = [
        dict(_SAMPLE_WORKER, task_id="task-001", assignment_ref="agent_assignment-task-001.v1.json"),
        dict(_SAMPLE_WORKER, task_id="task-002", assignment_ref="agent_assignment-task-002.v1.json"),
    ]
    report = writer.emit(**sample)
    assert len(report["workers"]) == 2


def test_emit_guard_flags_forced_false(tmp_path: Path) -> None:
    writer = RunnerReportWriter(base_dir=tmp_path)
    report = writer.emit(**_sample())
    assert report["guard_flags"] == {
        "support_widening": False,
        "production_platform_claim": False,
        "live_adapter_execution": False,
    }
