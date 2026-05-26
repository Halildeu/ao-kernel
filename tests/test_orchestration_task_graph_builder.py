"""AO-MA-3 task graph builder unit tests."""

from __future__ import annotations

import datetime as _dt
import json
from pathlib import Path

import jsonschema
import pytest

from ao_kernel.orchestration.task_graph_builder import (
    TaskGraphBuilderError,
    TaskSpec,
    build_task_graph,
    deterministic_task_graph_id,
)

_SHA40 = "a" * 40
_REPO = "Halildeu/ao-kernel"
_REPO_ROOT = Path(__file__).resolve().parents[1]


def _load_schema(name: str) -> dict:
    return json.loads((_REPO_ROOT / "ao_kernel" / "defaults" / "schemas" / name).read_text(encoding="utf-8"))


def test_deterministic_task_graph_id_is_reproducible() -> None:
    now = _dt.datetime(2026, 5, 27, 0, 0, 0, tzinfo=_dt.UTC)
    id1 = deterministic_task_graph_id("goal x", _SHA40, ["a.py", "b.py"], utc_now=now)
    id2 = deterministic_task_graph_id("goal x", _SHA40, ["a.py", "b.py"], utc_now=now)
    assert id1 == id2
    assert id1.startswith("ao-ma-20260527-")
    assert len(id1.split("-")[-1]) == 7


def test_deterministic_task_graph_id_is_path_order_independent() -> None:
    now = _dt.datetime(2026, 5, 27, 0, 0, 0, tzinfo=_dt.UTC)
    id1 = deterministic_task_graph_id("goal x", _SHA40, ["b.py", "a.py"], utc_now=now)
    id2 = deterministic_task_graph_id("goal x", _SHA40, ["a.py", "b.py"], utc_now=now)
    assert id1 == id2


def test_deterministic_task_graph_id_changes_with_goal() -> None:
    now = _dt.datetime(2026, 5, 27, 0, 0, 0, tzinfo=_dt.UTC)
    id_a = deterministic_task_graph_id("goal alpha", _SHA40, [], utc_now=now)
    id_b = deterministic_task_graph_id("goal beta", _SHA40, [], utc_now=now)
    assert id_a != id_b


def test_deterministic_task_graph_id_changes_with_base_sha() -> None:
    now = _dt.datetime(2026, 5, 27, 0, 0, 0, tzinfo=_dt.UTC)
    id_a = deterministic_task_graph_id("goal x", "a" * 40, [], utc_now=now)
    id_b = deterministic_task_graph_id("goal x", "b" * 40, [], utc_now=now)
    assert id_a != id_b


def test_invalid_base_sha_fails_closed() -> None:
    with pytest.raises(TaskGraphBuilderError, match="40-char lowercase hex"):
        build_task_graph("goal", "deadbeef", repo=_REPO)


def test_empty_goal_fails_closed() -> None:
    with pytest.raises(TaskGraphBuilderError, match="non-empty string"):
        build_task_graph("", _SHA40, repo=_REPO)


def test_invalid_provider_fails_closed() -> None:
    with pytest.raises(TaskGraphBuilderError, match="agent_provider"):
        build_task_graph("goal", _SHA40, repo=_REPO, agent_provider="not_a_provider")


def test_no_declared_specs_emits_single_conservative_task() -> None:
    result = build_task_graph("conservative default", _SHA40, repo=_REPO)
    assert len(result.task_graph["tasks"]) == 1
    task = result.task_graph["tasks"][0]
    assert task["task_id"].startswith("task-001-operator-scope-unknown")
    assert task["declared_write_set"] == []
    assert task["high_risk"] is False
    assert result.task_graph["risk_class"] == "low"


def test_multi_slice_disjoint_write_sets_pass() -> None:
    specs = [
        TaskSpec("task-001", "fix foo", ["ao_kernel/foo.py"]),
        TaskSpec("task-002", "fix bar", ["ao_kernel/bar.py"]),
    ]
    result = build_task_graph("multi", _SHA40, repo=_REPO, declared_specs=specs)
    assert len(result.task_graph["tasks"]) == 2
    assert result.task_graph["max_parallel_workers"] == 2
    assert len(result.assignments) == 2


def test_multi_slice_overlap_fails_closed() -> None:
    specs = [
        TaskSpec("task-001", "fix foo", ["ao_kernel/shared.py"]),
        TaskSpec("task-002", "also fix shared", ["ao_kernel/shared.py"]),
    ]
    with pytest.raises(TaskGraphBuilderError, match="ao_ma_3_worker_overlap_detected"):
        build_task_graph("overlap", _SHA40, repo=_REPO, declared_specs=specs)


def test_duplicate_task_id_fails_closed() -> None:
    specs = [
        TaskSpec("task-001", "a", ["ao_kernel/a.py"]),
        TaskSpec("task-001", "b", ["ao_kernel/b.py"]),
    ]
    with pytest.raises(TaskGraphBuilderError, match="duplicate task id"):
        build_task_graph("dup", _SHA40, repo=_REPO, declared_specs=specs)


def test_invalid_task_id_pattern_fails_closed() -> None:
    specs = [TaskSpec("Bad_Task_ID!", "x", ["ao_kernel/x.py"])]
    with pytest.raises(TaskGraphBuilderError, match="does not match"):
        build_task_graph("invalid", _SHA40, repo=_REPO, declared_specs=specs)


def test_dependency_target_must_exist() -> None:
    specs = [
        TaskSpec("task-001", "a", ["ao_kernel/a.py"], depends_on=["task-999"]),
    ]
    with pytest.raises(TaskGraphBuilderError, match="unknown task"):
        build_task_graph("depmiss", _SHA40, repo=_REPO, declared_specs=specs)


def test_task_graph_is_ao_ma_2_schema_valid() -> None:
    schema = _load_schema("ao-ma-task-graph.schema.v1.json")
    specs = [
        TaskSpec("task-001", "fix foo", ["ao_kernel/foo.py"]),
        TaskSpec("task-002", "fix bar", ["ao_kernel/bar.py"]),
    ]
    result = build_task_graph("schema check", _SHA40, repo=_REPO, declared_specs=specs)
    # jsonschema.validate raises ValidationError on mismatch; reaching the
    # assertion confirms the task graph passed every required-field and
    # additionalProperties=false check.
    jsonschema.validate(result.task_graph, schema)
    assert result.task_graph["schema_version"] == "ao-ma-task-graph.v1"


def test_agent_assignment_is_ao_ma_2_schema_valid() -> None:
    schema = _load_schema("ao-ma-agent-assignment.schema.v1.json")
    specs = [TaskSpec("task-001", "fix foo", ["ao_kernel/foo.py"])]
    result = build_task_graph("assignment check", _SHA40, repo=_REPO, declared_specs=specs)
    assert len(result.assignments) == 1
    for assignment in result.assignments:
        jsonschema.validate(assignment, schema)
        assert assignment["schema_version"] == "ao-ma-agent-assignment.v1"


def test_guard_flags_always_closed() -> None:
    result = build_task_graph("flags", _SHA40, repo=_REPO)
    assert result.task_graph["guard_flags"] == {
        "support_widening": False,
        "production_platform_claim": False,
        "live_adapter_execution": False,
    }
    for assignment in result.assignments:
        assert assignment["guard_flags"] == {
            "support_widening": False,
            "production_platform_claim": False,
            "live_adapter_execution": False,
        }


def test_review_policy_routes_high_risk_to_two_reviewers() -> None:
    specs = [TaskSpec("task-001", "edit gate", ["scripts/ao_release_gate_decision.py"])]
    result = build_task_graph("gate edit", _SHA40, repo=_REPO, declared_specs=specs)
    assert result.task_graph["risk_class"] == "high"
    policy = result.task_graph["review_policy"]
    assert policy["required_reviewers"] == 2
    assert policy["cross_provider_required"] is True
    assert policy["consensus_required_for_high_risk"] is True


def test_review_policy_low_risk_is_single_cross_provider_reviewer() -> None:
    result = build_task_graph("low risk", _SHA40, repo=_REPO)
    assert result.task_graph["risk_class"] == "low"
    policy = result.task_graph["review_policy"]
    assert policy["required_reviewers"] == 1
    assert policy["cross_provider_required"] is True


def test_path_validation_rejects_absolute() -> None:
    specs = [TaskSpec("task-001", "x", ["/etc/passwd"])]
    with pytest.raises(TaskGraphBuilderError, match="absolute"):
        build_task_graph("abs", _SHA40, repo=_REPO, declared_specs=specs)


def test_path_validation_rejects_parent_traversal() -> None:
    specs = [TaskSpec("task-001", "x", ["ao_kernel/../etc/passwd"])]
    with pytest.raises(TaskGraphBuilderError, match="'\\.\\.'"):
        build_task_graph("parent", _SHA40, repo=_REPO, declared_specs=specs)


def test_path_validation_rejects_dot_alias() -> None:
    specs = [TaskSpec("task-001", "x", ["./ao_kernel/foo.py"])]
    with pytest.raises(TaskGraphBuilderError, match="'\\.\\.'"):
        build_task_graph("dot", _SHA40, repo=_REPO, declared_specs=specs)


def test_path_validation_rejects_backslash() -> None:
    specs = [TaskSpec("task-001", "x", ["ao_kernel\\foo.py"])]
    with pytest.raises(TaskGraphBuilderError, match="backslash"):
        build_task_graph("bs", _SHA40, repo=_REPO, declared_specs=specs)


def test_path_validation_rejects_empty_string() -> None:
    specs = [TaskSpec("task-001", "x", [""])]
    with pytest.raises(TaskGraphBuilderError, match="non-empty string"):
        build_task_graph("empty", _SHA40, repo=_REPO, declared_specs=specs)


def test_path_validation_rejects_double_slash() -> None:
    # Codex iter-3: ``foo//bar.py`` normalizes to ``foo/bar.py`` under
    # most path layers, silently bypassing the overlap fail-closed guard.
    specs = [TaskSpec("task-001", "x", ["ao_kernel//foo.py"])]
    with pytest.raises(TaskGraphBuilderError, match="empty segment"):
        build_task_graph("double-slash", _SHA40, repo=_REPO, declared_specs=specs)


def test_path_validation_rejects_trailing_slash() -> None:
    # Codex iter-3: ``foo/`` would canonicalize to ``foo`` under git tooling.
    specs = [TaskSpec("task-001", "x", ["ao_kernel/foo/"])]
    with pytest.raises(TaskGraphBuilderError, match="empty segment"):
        build_task_graph("trailing-slash", _SHA40, repo=_REPO, declared_specs=specs)


def test_branch_pattern_matches_schema() -> None:
    schema = _load_schema("ao-ma-agent-assignment.schema.v1.json")
    pattern = schema["properties"]["branch"]["pattern"]
    import re

    specs = [TaskSpec("task-001", "x", ["a.py"])]
    result = build_task_graph("branch", _SHA40, repo=_REPO, declared_specs=specs)
    branch = result.assignments[0]["branch"]
    assert re.match(pattern, branch), f"branch {branch!r} does not match {pattern}"
