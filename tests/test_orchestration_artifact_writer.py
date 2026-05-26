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
        "tasks": [
            {
                "task_id": "task-001",
                "title": "sample task",
                "agent_type": "implementer",
                "declared_write_set": [],
                "dependency_ids": [],
                "acceptance_criteria": ["tests_pass_locally"],
                "high_risk": False,
            }
        ],
        "fan_in_policy": {
            "mode": "all_required",
            "required_task_ids": ["task-001"],
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


def _sample_assignment(task_id: str = "task-001", task_graph_id: str = "ao-ma-20260527-abcd123") -> dict:
    return {
        "schema_version": "ao-ma-agent-assignment.v1",
        "assignment_id": f"{task_graph_id}-{task_id}",
        "task_graph_id": task_graph_id,
        "task_id": task_id,
        "agent": {
            "agent_id": f"claude-{task_id}",
            "agent_type": "implementer",
            "provider": "anthropic",
            "session_id": f"ao-ma-3-orchestrator-{task_graph_id}",
        },
        "base_ref": "refs/heads/main",
        "base_sha": "a" * 40,
        "branch": f"codex/ao-ma-{task_graph_id}/{task_id}",
        "worktree": f".ao/orchestration/{task_graph_id}/workers/{task_id}",
        "declared_write_set": [],
        "expected_output_artifact": "worker_result.v1",
        "status": "pending",
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
    # With runtime schema validation in place, removing required task_id is
    # caught at the schema layer before the path-pattern guard fires.
    writer = ArtifactWriter(base_dir=tmp_path)
    graph = _sample_task_graph()
    assignment = _sample_assignment()
    del assignment["task_id"]
    with pytest.raises(ArtifactWriterError, match="schema validation"):
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


# ---------------------------------------------------------------------------
# Codex iter-2 absorb — containment + runtime schema validation tests
# ---------------------------------------------------------------------------


def test_writer_rejects_task_graph_id_with_path_traversal(tmp_path: Path) -> None:
    writer = ArtifactWriter(base_dir=tmp_path)
    graph = _sample_task_graph(task_graph_id="ao-ma-../etc/passwd")
    with pytest.raises(ArtifactWriterError, match="task_graph_id"):
        writer.emit(graph, [_sample_assignment()])


def test_writer_rejects_task_graph_id_with_slash(tmp_path: Path) -> None:
    writer = ArtifactWriter(base_dir=tmp_path)
    graph = _sample_task_graph(task_graph_id="ao-ma-foo/bar")
    with pytest.raises(ArtifactWriterError, match="task_graph_id"):
        writer.emit(graph, [_sample_assignment()])


def test_writer_rejects_task_graph_id_outside_pattern(tmp_path: Path) -> None:
    writer = ArtifactWriter(base_dir=tmp_path)
    graph = _sample_task_graph(task_graph_id="WRONG-PREFIX-id")
    with pytest.raises(ArtifactWriterError, match="AO-MA-2 schema"):
        writer.emit(graph, [_sample_assignment()])


def test_writer_runtime_schema_validation_catches_bad_task_graph(tmp_path: Path) -> None:
    writer = ArtifactWriter(base_dir=tmp_path)
    graph = _sample_task_graph()
    # Tamper: remove a required field after construction
    del graph["risk_class"]
    with pytest.raises(ArtifactWriterError, match="schema validation"):
        writer.emit(graph, [_sample_assignment()])


def test_writer_runtime_schema_validation_catches_bad_assignment(tmp_path: Path) -> None:
    writer = ArtifactWriter(base_dir=tmp_path)
    graph = _sample_task_graph()
    bad = _sample_assignment()
    bad["status"] = "planned"  # not in enum [pending|running|completed|failed|superseded]
    with pytest.raises(ArtifactWriterError, match="schema validation"):
        writer.emit(graph, [bad])


def test_writer_rejects_task_id_outside_pattern(tmp_path: Path) -> None:
    writer = ArtifactWriter(base_dir=tmp_path)
    graph = _sample_task_graph()
    bad = _sample_assignment(task_id="Bad/Task")
    with pytest.raises(ArtifactWriterError):
        writer.emit(graph, [bad])
