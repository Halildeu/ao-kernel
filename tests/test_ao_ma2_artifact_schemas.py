"""AO-MA-2 artifact schema contract tests.

AO-MA-2 is schema/test only: it defines explicit multi-agent coordination
artifacts without spawning agents, changing workflows, mutating rulesets, or
widening support.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any, cast

import pytest
from jsonschema import Draft202012Validator

from ao_kernel.config import load_default


ROOT = Path(__file__).resolve().parents[1]
FIXTURE_DIR = ROOT / "tests" / "fixtures" / "ao_ma_2"
AO_MA_1_DOC = ROOT / ".claude" / "plans" / "AO-MA-1-MULTI-AGENT-ORCHESTRATION-DESIGN.md"


SCHEMA_FIXTURES = {
    "ao-ma-task-graph.schema.v1.json": "task_graph.valid.json",
    "ao-ma-agent-assignment.schema.v1.json": "agent_assignment.valid.json",
    "ao-ma-worker-result.schema.v1.json": "worker_result.valid.json",
    "ao-ma-review-verdict.schema.v1.json": "review_verdict.valid.json",
    "ao-ma-verification-report.schema.v1.json": "verification_report.valid.json",
    "ao-ma-integration-report.schema.v1.json": "integration_report.valid.json",
}


def _schema(name: str) -> dict[str, Any]:
    return load_default("schemas", name)


def _fixture(name: str) -> dict[str, Any]:
    return cast(dict[str, Any], json.loads((FIXTURE_DIR / name).read_text(encoding="utf-8")))


def _is_invalid(schema_name: str, payload: dict[str, Any]) -> bool:
    errors = list(Draft202012Validator(_schema(schema_name)).iter_errors(payload))
    return bool(errors)


@pytest.mark.parametrize("schema_name", SCHEMA_FIXTURES)
def test_ao_ma2_schemas_are_valid_draft_2020_12(schema_name: str) -> None:
    schema = _schema(schema_name)
    Draft202012Validator.check_schema(schema)
    assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
    assert schema["$id"].startswith("urn:ao:ao-ma-")


@pytest.mark.parametrize(("schema_name", "fixture_name"), SCHEMA_FIXTURES.items())
def test_ao_ma2_valid_fixtures_pass(schema_name: str, fixture_name: str) -> None:
    errors = list(Draft202012Validator(_schema(schema_name)).iter_errors(_fixture(fixture_name)))
    assert errors == []


@pytest.mark.parametrize(("schema_name", "fixture_name"), SCHEMA_FIXTURES.items())
def test_ao_ma2_required_schema_version_is_pinned(schema_name: str, fixture_name: str) -> None:
    payload = _fixture(fixture_name)
    payload.pop("schema_version")
    assert _is_invalid(schema_name, payload)


@pytest.mark.parametrize(("schema_name", "fixture_name"), SCHEMA_FIXTURES.items())
def test_ao_ma2_rejects_unknown_top_level_properties(schema_name: str, fixture_name: str) -> None:
    payload = _fixture(fixture_name)
    payload["implementer_narrative"] = "not allowed"
    assert _is_invalid(schema_name, payload)


@pytest.mark.parametrize(
    ("schema_name", "fixture_name", "enum_path", "bad_value"),
    [
        ("ao-ma-task-graph.schema.v1.json", "task_graph.valid.json", ("risk_class",), "urgent"),
        (
            "ao-ma-agent-assignment.schema.v1.json",
            "agent_assignment.valid.json",
            ("agent", "agent_type"),
            "merge_executor",
        ),
        (
            "ao-ma-worker-result.schema.v1.json",
            "worker_result.valid.json",
            ("tests_run", 0, "outcome"),
            "maybe",
        ),
        ("ao-ma-review-verdict.schema.v1.json", "review_verdict.valid.json", ("verdict",), "APPROVED"),
        (
            "ao-ma-verification-report.schema.v1.json",
            "verification_report.valid.json",
            ("commands", 0, "outcome"),
            "unknown",
        ),
        (
            "ao-ma-integration-report.schema.v1.json",
            "integration_report.valid.json",
            ("release_authority",),
            "claude-agree",
        ),
    ],
)
def test_ao_ma2_rejects_invalid_enums(
    schema_name: str,
    fixture_name: str,
    enum_path: tuple[str | int, ...],
    bad_value: str,
) -> None:
    payload = _fixture(fixture_name)
    cursor: Any = payload
    for part in enum_path[:-1]:
        cursor = cursor[part]
    cursor[enum_path[-1]] = bad_value
    assert _is_invalid(schema_name, payload)


@pytest.mark.parametrize(("schema_name", "fixture_name"), SCHEMA_FIXTURES.items())
def test_ao_ma2_guard_flags_must_stay_closed(schema_name: str, fixture_name: str) -> None:
    payload = _fixture(fixture_name)
    for flag in ("support_widening", "production_platform_claim", "live_adapter_execution"):
        mutated = copy.deepcopy(payload)
        mutated["guard_flags"][flag] = True
        assert _is_invalid(schema_name, mutated)


def test_ao_ma2_review_verdict_pins_zero_implementer_narrative_boundary() -> None:
    payload = _fixture("review_verdict.valid.json")
    schema_name = "ao-ma-review-verdict.schema.v1.json"

    not_independent = copy.deepcopy(payload)
    not_independent["independent_review"] = False
    assert _is_invalid(schema_name, not_independent)

    leaked_narrative = copy.deepcopy(payload)
    leaked_narrative["prohibited_sources_absent"] = False
    assert _is_invalid(schema_name, leaked_narrative)

    bad_source = copy.deepcopy(payload)
    bad_source["allowed_sources"].append("implementer_chat")
    assert _is_invalid(schema_name, bad_source)

    same_provider = copy.deepcopy(payload)
    same_provider["cross_provider_verified"] = False
    assert _is_invalid(schema_name, same_provider)


def test_ao_ma2_task_graph_pins_high_risk_consensus_policy() -> None:
    payload = _fixture("task_graph.valid.json")
    schema_name = "ao-ma-task-graph.schema.v1.json"

    no_cross_provider = copy.deepcopy(payload)
    no_cross_provider["review_policy"]["cross_provider_required"] = False
    assert _is_invalid(schema_name, no_cross_provider)

    no_high_risk_consensus = copy.deepcopy(payload)
    no_high_risk_consensus["review_policy"]["consensus_required_for_high_risk"] = False
    assert _is_invalid(schema_name, no_high_risk_consensus)


def test_ao_ma2_path_fields_reject_absolute_and_parent_escape() -> None:
    schema_name = "ao-ma-worker-result.schema.v1.json"
    payload = _fixture("worker_result.valid.json")

    absolute = copy.deepcopy(payload)
    absolute["actual_changed_files"] = ["/tmp/leak.txt"]
    assert _is_invalid(schema_name, absolute)

    parent_escape = copy.deepcopy(payload)
    parent_escape["actual_changed_files"] = ["../secrets.txt"]
    assert _is_invalid(schema_name, parent_escape)


def test_ao_ma2_artifact_reference_chain_is_consistent() -> None:
    task_graph = _fixture("task_graph.valid.json")
    assignment = _fixture("agent_assignment.valid.json")
    worker = _fixture("worker_result.valid.json")
    review = _fixture("review_verdict.valid.json")
    verification = _fixture("verification_report.valid.json")
    integration = _fixture("integration_report.valid.json")

    task_ids = {task["task_id"] for task in task_graph["tasks"]}
    assert assignment["task_graph_id"] == task_graph["task_graph_id"]
    assert assignment["task_id"] in task_ids
    assert worker["task_graph_id"] == task_graph["task_graph_id"]
    assert worker["task_id"] == assignment["task_id"]
    assert worker["assignment_id"] == assignment["assignment_id"]
    assert review["task_graph_id"] == task_graph["task_graph_id"]
    assert review["reviewed_task_id"] == worker["task_id"]
    assert set(verification["verified_task_ids"]) <= task_ids
    assert integration["task_graph_id"] == task_graph["task_graph_id"]
    assert integration["release_authority"] == "ao-release-gate+github-ruleset"


def test_ao_ma2_schema_files_match_ao_ma1_artifact_model() -> None:
    doc = AO_MA_1_DOC.read_text(encoding="utf-8")
    assert "`task_graph.v1`" in doc
    assert "`agent_assignment.v1`" in doc
    assert "`worker_result.v1`" in doc
    assert "`review_verdict.v1`" in doc
    assert "`verification_report.v1`" in doc
    assert "`integration_report.v1`" in doc

    for schema_name in SCHEMA_FIXTURES:
        assert (ROOT / "ao_kernel" / "defaults" / "schemas" / schema_name).is_file()


def test_ao_ma1_status_wording_is_recorded_not_planned() -> None:
    text = AO_MA_1_DOC.read_text(encoding="utf-8")
    assert "**Status:** recorded / design slice - documentation and invariant test only" in text
    assert "**Status:** planned / design slice" not in text
