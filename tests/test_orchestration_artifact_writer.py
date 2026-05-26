"""AO-MA-3 artifact writer unit tests."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from ao_kernel.orchestration.artifact_writer import ArtifactWriter, ArtifactWriterError


def _sample_task_graph(task_graph_id: str = "ao-ma-20260527-abcd123") -> dict:
    return {
        "schema_version": "ao-ma-task-graph.v1",
        "task_graph_id": task_graph_id,
        "repo": "Halildeu/ao-kernel",
        "goal": "test",
        "base_ref": "refs/heads/main",
        "base_sha": "a" * 40,
        "risk_class": "low",
        "max_parallel_workers": 1,
        "tasks": [{"task_id": "task-001", "description": "x", "write_paths": [], "depends_on": []}],
        "fan_in_policy": "integrator_owned_single_pr",
        "review_policy": "cross_provider_ai_review_only",
        "guard_flags": {
            "support_widening": False,
            "production_platform_claim": False,
            "live_adapter_execution": False,
        },
    }


def _sample_assignment(task_id: str = "task-001", task_graph_id: str = "ao-ma-20260527-abcd123") -> dict:
    return {
        "schema_version": "ao-ma-agent-assignment.v1",
        "assignment_id": f"{task_graph_id}-{task_id}",
        "task_graph_id": task_graph_id,
        "task_id": task_id,
        "agent": {"label": "claude", "kind": "ai", "provider": "anthropic"},
        "base_ref": "refs/heads/main",
        "base_sha": "a" * 40,
        "branch": f"codex/ao-ma-{task_graph_id}/{task_id}",
        "worktree": f".ao/orchestration/{task_graph_id}/workers/{task_id}",
        "declared_write_set": [],
        "expected_output_artifact": "worker_result.v1",
        "status": "planned",
        "guard_flags": {
            "support_widening": False,
            "production_platform_claim": False,
            "live_adapter_execution": False,
        },
    }


def test_emit_writes_three_files(tmp_path: Path) -> None:
    writer = ArtifactWriter(base_dir=tmp_path)
    graph = _sample_task_graph()
    assignments = [_sample_assignment()]
    manifest = writer.emit(graph, assignments)

    out_dir = tmp_path / graph["task_graph_id"]
    assert (out_dir / "task_graph.v1.json").exists()
    assert (out_dir / "agent_assignment-task-001.v1.json").exists()
    assert (out_dir / "manifest.v1.json").exists()
    assert manifest["task_graph_id"] == graph["task_graph_id"]
    assert manifest["schema_version"] == "ao-ma-orchestration-manifest.v1"


def test_manifest_sha256_matches_disk(tmp_path: Path) -> None:
    writer = ArtifactWriter(base_dir=tmp_path)
    graph = _sample_task_graph()
    assignments = [_sample_assignment()]
    manifest = writer.emit(graph, assignments)

    out_dir = tmp_path / graph["task_graph_id"]
    for entry in manifest["artifacts"]:
        path = out_dir / entry["path"]
        data = path.read_bytes()
        expected = "sha256:" + hashlib.sha256(data).hexdigest()
        assert entry["sha256"] == expected
        assert entry["size_bytes"] == len(data)


def test_manifest_does_not_reference_itself(tmp_path: Path) -> None:
    writer = ArtifactWriter(base_dir=tmp_path)
    graph = _sample_task_graph()
    manifest = writer.emit(graph, [_sample_assignment()])
    artifact_paths = {entry["path"] for entry in manifest["artifacts"]}
    assert "manifest.v1.json" not in artifact_paths


def test_emit_rejects_missing_task_graph_id(tmp_path: Path) -> None:
    writer = ArtifactWriter(base_dir=tmp_path)
    graph = _sample_task_graph()
    graph["task_graph_id"] = ""
    with pytest.raises(ArtifactWriterError, match="task_graph_id"):
        writer.emit(graph, [_sample_assignment()])


def test_emit_rejects_assignment_without_task_id(tmp_path: Path) -> None:
    writer = ArtifactWriter(base_dir=tmp_path)
    graph = _sample_task_graph()
    assignment = _sample_assignment()
    del assignment["task_id"]
    with pytest.raises(ArtifactWriterError, match="missing task_id"):
        writer.emit(graph, [assignment])


def test_atomic_write_no_partial_files_on_success(tmp_path: Path) -> None:
    writer = ArtifactWriter(base_dir=tmp_path)
    writer.emit(_sample_task_graph(), [_sample_assignment()])
    out_dir = tmp_path / "ao-ma-20260527-abcd123"
    # No .tmp leftovers
    assert not list(out_dir.glob(".*.tmp"))


def test_artifacts_have_valid_json(tmp_path: Path) -> None:
    writer = ArtifactWriter(base_dir=tmp_path)
    graph = _sample_task_graph()
    writer.emit(graph, [_sample_assignment()])
    out_dir = tmp_path / graph["task_graph_id"]
    files = list(out_dir.glob("*.json"))
    assert len(files) >= 3  # task_graph + assignment + manifest
    # All emitted files should parse as JSON
    for jf in files:
        parsed = json.loads(jf.read_text(encoding="utf-8"))
        assert isinstance(parsed, dict)
