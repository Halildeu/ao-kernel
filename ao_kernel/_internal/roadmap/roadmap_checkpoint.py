"""Roadmap checkpoint/resume — workflow-level progress persistence.

Saves checkpoint after each milestone, enabling resume from last completed point.
Pattern follows session checkpoint (ao_kernel/context/checkpoint.py) with
workflow-specific state.

Storage: .cache/roadmap_checkpoints/{run_id}/progress.v1.json
Audit:   .cache/roadmap_checkpoints/{run_id}/steps.log.jsonl
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ao_kernel._internal.shared.utils import write_json_atomic


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


@dataclass
class RoadmapCheckpoint:
    """Workflow progress checkpoint."""

    run_id: str
    plan_id: str
    timestamp: str
    completed_milestones: list[str]
    completed_steps: list[str]
    current_milestone_id: str | None = None
    current_step_id: str | None = None
    state_snapshot: dict[str, Any] = field(default_factory=dict)
    errors: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class StepResult:
    """Result of a single step execution."""

    step_id: str
    status: str  # OK | SKIP | FAIL
    duration_ms: int = 0
    output: dict[str, Any] = field(default_factory=dict)
    error: dict[str, Any] | None = None
    timestamp: str = ""

    def __post_init__(self) -> None:
        if not self.timestamp:
            self.timestamp = _now_iso()


def _compute_hash(data: dict[str, Any]) -> str:
    content = json.dumps(data, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(content.encode()).hexdigest()[:16]


class RoadmapCheckpointManager:
    """Manages workflow-level checkpoints for roadmap execution."""

    def __init__(self, workspace_root: Path) -> None:
        self._checkpoints_dir = workspace_root / ".cache" / "roadmap_checkpoints"

    def save(
        self,
        run_id: str,
        plan_id: str,
        *,
        completed_milestones: list[str],
        completed_steps: list[str],
        current_milestone_id: str | None = None,
        current_step_id: str | None = None,
        state_snapshot: dict[str, Any] | None = None,
        errors: list[dict[str, Any]] | None = None,
    ) -> Path:
        """Save checkpoint atomically.

        Returns path to checkpoint file.
        """
        run_dir = self._checkpoints_dir / run_id
        run_dir.mkdir(parents=True, exist_ok=True)

        cp = RoadmapCheckpoint(
            run_id=run_id,
            plan_id=plan_id,
            timestamp=_now_iso(),
            completed_milestones=completed_milestones,
            completed_steps=completed_steps,
            current_milestone_id=current_milestone_id,
            current_step_id=current_step_id,
            state_snapshot=state_snapshot or {},
            errors=errors or [],
        )

        cp_dict = {
            "run_id": cp.run_id,
            "plan_id": cp.plan_id,
            "timestamp": cp.timestamp,
            "completed_milestones": cp.completed_milestones,
            "completed_steps": cp.completed_steps,
            "current_milestone_id": cp.current_milestone_id,
            "current_step_id": cp.current_step_id,
            "state_snapshot": cp.state_snapshot,
            "errors": cp.errors,
        }

        data = {"checkpoint": cp_dict, "hash": _compute_hash(cp_dict)}
        path = run_dir / "progress.v1.json"
        write_json_atomic(path, data)
        return path

    def load(self, run_id: str) -> RoadmapCheckpoint | None:
        """Load checkpoint if exists and valid. Returns None on missing/corrupt."""
        path = self._checkpoints_dir / run_id / "progress.v1.json"
        if not path.exists():
            return None

        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            cp_dict = data.get("checkpoint", {})
            stored_hash = data.get("hash", "")

            if _compute_hash(cp_dict) != stored_hash:
                return None  # Corrupted

            return RoadmapCheckpoint(**cp_dict)
        except (json.JSONDecodeError, TypeError, KeyError):
            return None

    def log_step(self, run_id: str, result: StepResult) -> None:
        """Append step result to JSONL audit log."""
        run_dir = self._checkpoints_dir / run_id
        run_dir.mkdir(parents=True, exist_ok=True)

        log_path = run_dir / "steps.log.jsonl"
        entry = {
            "step_id": result.step_id,
            "status": result.status,
            "duration_ms": result.duration_ms,
            "timestamp": result.timestamp,
        }
        if result.error:
            entry["error"] = result.error

        with log_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    def get_resume_skip_set(self, run_id: str) -> set[str]:
        """Get set of completed step IDs for resume (steps to skip)."""
        cp = self.load(run_id)
        if cp is None:
            return set()
        return set(cp.completed_steps)
