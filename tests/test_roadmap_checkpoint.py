"""Tests for roadmap checkpoint/resume."""

from __future__ import annotations

import json
from pathlib import Path

from ao_kernel._internal.roadmap.roadmap_checkpoint import (
    RoadmapCheckpointManager,
    StepResult,
)


class TestRoadmapCheckpointManager:
    def test_save_and_load_roundtrip(self, tmp_path: Path):
        """Save checkpoint and load it back with same data."""
        mgr = RoadmapCheckpointManager(tmp_path)
        mgr.save(
            "run-001", "plan-abc",
            completed_milestones=["m1"],
            completed_steps=["s1", "s2"],
            current_milestone_id="m2",
            state_snapshot={"key": "value"},
        )

        cp = mgr.load("run-001")
        assert cp is not None
        assert cp.run_id == "run-001"
        assert cp.plan_id == "plan-abc"
        assert cp.completed_milestones == ["m1"]
        assert cp.completed_steps == ["s1", "s2"]
        assert cp.current_milestone_id == "m2"
        assert cp.state_snapshot == {"key": "value"}

    def test_load_missing_returns_none(self, tmp_path: Path):
        """Loading nonexistent checkpoint returns None."""
        mgr = RoadmapCheckpointManager(tmp_path)
        assert mgr.load("nonexistent") is None

    def test_corrupted_checkpoint_returns_none(self, tmp_path: Path):
        """Tampered checkpoint (hash mismatch) returns None."""
        mgr = RoadmapCheckpointManager(tmp_path)
        mgr.save("run-002", "plan-x", completed_milestones=[], completed_steps=[])

        # Tamper with checkpoint
        cp_path = tmp_path / ".cache" / "roadmap_checkpoints" / "run-002" / "progress.v1.json"
        data = json.loads(cp_path.read_text())
        data["checkpoint"]["completed_steps"] = ["tampered"]
        cp_path.write_text(json.dumps(data))

        assert mgr.load("run-002") is None

    def test_resume_skip_set(self, tmp_path: Path):
        """get_resume_skip_set returns completed step IDs."""
        mgr = RoadmapCheckpointManager(tmp_path)
        mgr.save(
            "run-003", "plan-y",
            completed_milestones=["m1"],
            completed_steps=["step-1", "step-2", "step-3"],
        )

        skip = mgr.get_resume_skip_set("run-003")
        assert skip == {"step-1", "step-2", "step-3"}

    def test_resume_skip_set_missing_returns_empty(self, tmp_path: Path):
        """Missing checkpoint → empty skip set."""
        mgr = RoadmapCheckpointManager(tmp_path)
        assert mgr.get_resume_skip_set("missing") == set()

    def test_log_step_creates_jsonl(self, tmp_path: Path):
        """Step results are logged as JSONL."""
        mgr = RoadmapCheckpointManager(tmp_path)
        mgr.log_step("run-004", StepResult(step_id="s1", status="OK", duration_ms=100))
        mgr.log_step("run-004", StepResult(step_id="s2", status="FAIL", error={"msg": "timeout"}))

        log_path = tmp_path / ".cache" / "roadmap_checkpoints" / "run-004" / "steps.log.jsonl"
        assert log_path.exists()
        lines = log_path.read_text().strip().split("\n")
        assert len(lines) == 2

        first = json.loads(lines[0])
        assert first["step_id"] == "s1"
        assert first["status"] == "OK"

        second = json.loads(lines[1])
        assert second["step_id"] == "s2"
        assert second["error"]["msg"] == "timeout"
