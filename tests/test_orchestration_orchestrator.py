"""AO-MA-3 orchestrator façade unit tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from ao_kernel.orchestration.orchestrator import (
    OrchestrationError,
    Orchestrator,
    SSOTPaths,
)
from ao_kernel.orchestration.task_graph_builder import TaskSpec


_REPO_ROOT = Path(__file__).resolve().parents[1]


def _make_minimal_ssot(tmp_path: Path) -> SSOTPaths:
    """Write minimal SSOT fixtures that satisfy the orchestrator guard."""

    agents_md = tmp_path / "AGENTS.md"
    agents_md.write_text("# Agent contract stub\n", encoding="utf-8")

    plans_dir = tmp_path / ".claude" / "plans"
    plans_dir.mkdir(parents=True, exist_ok=True)
    gpp_status = plans_dir / "gpp_status.v1.json"
    gpp_status.write_text(
        json.dumps(
            {
                "support_widening_allowed": False,
                "production_platform_claim_allowed": False,
                "live_adapter_execution_allowed": False,
            }
        ),
        encoding="utf-8",
    )
    return SSOTPaths(agents_md=agents_md, gpp_status=gpp_status)


def test_ssot_paths_default_anchors_at_repo_root() -> None:
    ssot = SSOTPaths.default(_REPO_ROOT)
    assert ssot.agents_md == _REPO_ROOT / "AGENTS.md"
    assert ssot.gpp_status == _REPO_ROOT / ".claude" / "plans" / "gpp_status.v1.json"


def test_plan_emits_manifest(tmp_path: Path) -> None:
    ssot = _make_minimal_ssot(tmp_path)
    orch = Orchestrator(
        repo_root=tmp_path,
        ssot=ssot,
        output_dir=tmp_path / ".ao" / "orchestration",
    )
    manifest = orch.plan(
        goal="orchestrator smoke",
        base_sha="b" * 40,
        repo="Halildeu/ao-kernel",
    )
    assert manifest["task_graph_id"].startswith("ao-ma-")
    assert manifest["schema_version"] == "ao-ma-orchestration-manifest.v1"
    assert len(manifest["artifacts"]) >= 2


def test_plan_fails_closed_when_agents_md_missing(tmp_path: Path) -> None:
    ssot = SSOTPaths(
        agents_md=tmp_path / "no-such-AGENTS.md",
        gpp_status=tmp_path / "no-such-status.json",
    )
    orch = Orchestrator(repo_root=tmp_path, ssot=ssot)
    with pytest.raises(OrchestrationError, match="AGENTS.md"):
        orch.plan(goal="x", base_sha="a" * 40, repo="r/r")


def test_plan_fails_closed_when_guard_flag_open(tmp_path: Path) -> None:
    ssot = _make_minimal_ssot(tmp_path)
    # Tamper: open the live_adapter flag
    data = json.loads(ssot.gpp_status.read_text(encoding="utf-8"))
    data["live_adapter_execution_allowed"] = True
    ssot.gpp_status.write_text(json.dumps(data), encoding="utf-8")

    orch = Orchestrator(repo_root=tmp_path, ssot=ssot)
    with pytest.raises(OrchestrationError, match="live_adapter_execution_allowed"):
        orch.plan(goal="x", base_sha="a" * 40, repo="r/r")


def test_plan_declared_specs_routes_through_builder(tmp_path: Path) -> None:
    ssot = _make_minimal_ssot(tmp_path)
    orch = Orchestrator(
        repo_root=tmp_path,
        ssot=ssot,
        output_dir=tmp_path / ".ao" / "orchestration",
    )
    specs = [
        TaskSpec("task-001", "a", ["ao_kernel/a.py"]),
        TaskSpec("task-002", "b", ["ao_kernel/b.py"]),
    ]
    manifest = orch.plan(
        goal="multi slice",
        declared_specs=specs,
        base_sha="c" * 40,
        repo="r/r",
    )
    out_dir = tmp_path / ".ao" / "orchestration" / manifest["task_graph_id"]
    graph = json.loads((out_dir / "task_graph.v1.json").read_text(encoding="utf-8"))
    assert len(graph["tasks"]) == 2
    assert graph["max_parallel_workers"] == 2


def test_plan_overlap_in_declared_specs_fails_closed(tmp_path: Path) -> None:
    ssot = _make_minimal_ssot(tmp_path)
    orch = Orchestrator(repo_root=tmp_path, ssot=ssot)
    specs = [
        TaskSpec("task-001", "a", ["ao_kernel/shared.py"]),
        TaskSpec("task-002", "b", ["ao_kernel/shared.py"]),
    ]
    with pytest.raises(OrchestrationError, match="overlap"):
        orch.plan(
            goal="overlap",
            declared_specs=specs,
            base_sha="d" * 40,
            repo="r/r",
        )


def test_repo_root_must_be_path() -> None:
    with pytest.raises(OrchestrationError, match="Path"):
        Orchestrator(repo_root="not-a-path")  # type: ignore[arg-type]
