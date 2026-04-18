"""Shared fixtures for PR-B7 benchmarks.

`--benchmark-mode` flag intentionally NOT exposed — fast mode is
the only mode B7 ships (full real-adapter mode deferred to B7.1
per plan v5 §7).
"""

from __future__ import annotations

import json
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

import pytest

from tests._driver_helpers import build_driver, install_workspace


_BUNDLED_ROOT = Path(__file__).resolve().parents[2] / "ao_kernel" / "defaults"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@pytest.fixture
def workspace_root(tmp_path: Path) -> Path:
    """Materialise a tmp workspace with `.ao/` + git skeleton and
    bundled policies / workflows / adapters copied in, so the
    driver + governance path reads a real filesystem.

    `install_workspace` from the shared driver helpers does the git
    init + base `.ao/` dirs; we layer the bundled defaults on top.
    """
    install_workspace(tmp_path)
    ao = tmp_path / ".ao"
    # `install_workspace` creates workflows/adapters/evidence/runs
    # but not policies — create it before copying bundled files.
    (ao / "policies").mkdir(parents=True, exist_ok=True)
    for policy in (_BUNDLED_ROOT / "policies").glob("policy_*.v1.json"):
        shutil.copy2(policy, ao / "policies" / policy.name)
    for workflow in (_BUNDLED_ROOT / "workflows").glob("*.v1.json"):
        shutil.copy2(workflow, ao / "workflows" / workflow.name)
    for adapter in (_BUNDLED_ROOT / "adapters").glob("*.manifest.v1.json"):
        shutil.copy2(adapter, ao / "adapters" / adapter.name)

    # Benchmark-specific workflow fixtures (B7 v1 — bundled
    # bug_fix_flow needs git/pytest workspace allowlist; simpler
    # bench variant deferred from that tuning).
    bench_workflows = Path(__file__).resolve().parent / "fixtures" / "workflows"
    if bench_workflows.is_dir():
        for workflow in bench_workflows.glob("*.v1.json"):
            shutil.copy2(workflow, ao / "workflows" / workflow.name)
    return tmp_path


@pytest.fixture
def seeded_budget() -> dict[str, Any]:
    """Canonical budget axes the benchmark runs assume.

    `fail_closed_on_exhaust=True` mirrors the real budget guard.
    `cost_usd` reconcile is deferred to B7.1 — the assertion layer
    only verifies the axis was seeded, not that spend landed on it.
    """
    return {
        "fail_closed_on_exhaust": True,
        "cost_usd": {"limit": 10.0, "remaining": 10.0},
        "tokens": {"limit": 50_000, "remaining": 50_000},
        "time_seconds": {"limit": 600, "remaining": 600},
    }


def seed_benchmark_run(
    workspace_root: Path,
    workflow_id: str,
    *,
    workflow_version: str = "1.0.0",
    budget: Mapping[str, Any],
) -> str:
    """Write a schema-minimal run record with `budget` seeded so
    `assert_budget_axis_seeded` can verify the axis later.

    Returns the new run_id.
    """
    from ao_kernel.workflow.run_store import run_revision

    run_id = str(uuid.uuid4())
    run_dir = workspace_root / ".ao" / "runs" / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    record: dict[str, Any] = {
        "run_id": run_id,
        "workflow_id": workflow_id,
        "workflow_version": workflow_version,
        "state": "created",
        "created_at": _now_iso(),
        "revision": "0" * 64,
        "intent": {
            "kind": "inline_prompt",
            "payload": f"benchmark {workflow_id}",
        },
        "steps": [],
        "policy_refs": [
            "ao_kernel/defaults/policies/policy_worktree_profile.v1.json",
        ],
        "adapter_refs": [],
        "evidence_refs": [
            f".ao/evidence/workflows/{run_id}/events.jsonl",
        ],
        "budget": dict(budget),
    }
    record["revision"] = run_revision(record)
    (run_dir / "state.v1.json").write_text(
        json.dumps(record, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    return run_id


@pytest.fixture
def seeded_run(workspace_root: Path, seeded_budget: dict[str, Any]):
    """Factory — returns a callable that seeds a run for a named
    workflow and returns the run_id."""

    def _seed(workflow_id: str, *, version: str = "1.0.0") -> str:
        return seed_benchmark_run(
            workspace_root,
            workflow_id,
            workflow_version=version,
            budget=seeded_budget,
        )

    return _seed


@pytest.fixture
def benchmark_driver(workspace_root: Path):
    """Driver bound to the bundled workspace (covers `codex-stub`
    + `gh-cli-pr` for both scenarios)."""
    return build_driver(workspace_root)
