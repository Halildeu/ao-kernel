"""Epic 9 PR-Xfinal readiness blocker invariants.

The V5 roadmap references a future ``EPIC-9-FINAL-SUPERSESSION-PR.md``.
This test suite pins that the current artifact is only a fail-closed draft
guardrail: PR-Xfinal is not ready to open, all guard flags remain false, and
the three independent gates stay ``not_ready`` until a later operator-bound
supersession supplies complete evidence.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from ao_kernel.config import load_default


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_NAME = "epic9-xfinal-readiness-blocker.schema.v1.json"
SCHEMA_PATH = ROOT / "ao_kernel" / "defaults" / "schemas" / SCHEMA_NAME
FIXTURE_PATH = ROOT / "tests" / "fixtures" / "epic9" / "xfinal-readiness-blocker.current.json"
DOC_PATH = ROOT / ".claude" / "plans" / "EPIC-9-FINAL-SUPERSESSION-PR.md"
ROADMAP_PATH = ROOT / ".claude" / "plans" / "V5-FULL-PRODUCTION-PROMOTION-ROADMAP.md"
PRE_CHECKLIST_PATH = ROOT / ".claude" / "plans" / "EPIC-9-PR-Xfinal-PRE-SUPERSESSION-CHECKLIST.md"


def _schema() -> dict[str, Any]:
    return load_default("schemas", SCHEMA_NAME)


def _fixture() -> dict[str, Any]:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def _valid(payload: dict[str, Any]) -> bool:
    return not list(Draft202012Validator(_schema()).iter_errors(payload))


def test_schema_present_valid_and_strict() -> None:
    assert SCHEMA_PATH.is_file()
    schema = _schema()
    Draft202012Validator.check_schema(schema)
    assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
    assert schema["$id"] == "urn:ao:epic9-xfinal-readiness-blocker:v1"

    def object_nodes(node: Any) -> list[dict[str, Any]]:
        nodes: list[dict[str, Any]] = []
        if isinstance(node, dict):
            if node.get("type") == "object":
                nodes.append(node)
            for value in node.values():
                nodes.extend(object_nodes(value))
        elif isinstance(node, list):
            for value in node:
                nodes.extend(object_nodes(value))
        return nodes

    for node in object_nodes(schema):
        assert node.get("additionalProperties") is False
        assert node.get("unevaluatedProperties") is False


def test_current_fixture_validates_and_pins_blocked_state() -> None:
    payload = _fixture()
    assert _valid(payload)
    assert payload["pr_xfinal_open_allowed"] is False
    assert payload["all_or_none_atomic_flip"] is True
    assert payload["partial_flip_allowed"] is False
    assert payload["support_widening"] is False
    assert payload["production_platform_claim"] is False
    assert payload["live_adapter_execution"] is False
    assert payload["operator_boundary"]["ai_output_is_release_authority"] is False
    assert payload["operator_boundary"]["repo_owned_required_check_is_release_authority"] is True


def test_all_three_gates_are_not_ready_and_issue_bound() -> None:
    payload = _fixture()
    assert set(payload["gates"]) == {
        "live_adapter_execution",
        "support_widening",
        "production_platform_claim",
    }
    for gate_name, gate in payload["gates"].items():
        assert gate["flag"] == gate_name
        assert gate["status"] == "not_ready"
        assert gate["required_evidence"]
        assert gate["missing_evidence"]
        assert gate["source_documents"]

    assert payload["issue_refs"] == [
        "https://github.com/Halildeu/ao-kernel/issues/775",
        "https://github.com/Halildeu/ao-kernel/issues/776",
        "https://github.com/Halildeu/ao-kernel/issues/782",
        "https://github.com/Halildeu/ao-kernel/issues/895",
    ]


def test_schema_rejects_any_open_or_partial_flip_attempt() -> None:
    for field, value in (
        ("pr_xfinal_open_allowed", True),
        ("partial_flip_allowed", True),
        ("support_widening", True),
        ("production_platform_claim", True),
        ("live_adapter_execution", True),
    ):
        payload = _fixture()
        payload[field] = value
        assert not _valid(payload), f"{field}={value!r} must fail closed in blocker v1"


def test_schema_rejects_ready_gate_claims_in_blocker_v1() -> None:
    for gate_name in ("live_adapter_execution", "support_widening", "production_platform_claim"):
        payload = _fixture()
        payload["gates"][gate_name]["status"] = "ready"
        assert not _valid(payload), f"{gate_name} ready claim must fail closed in blocker v1"


def test_schema_rejects_missing_evidence_or_cardinality_drift() -> None:
    payload = _fixture()
    payload["gates"]["live_adapter_execution"]["missing_evidence"] = []
    assert not _valid(payload)

    payload = _fixture()
    payload["issue_refs"].append("https://github.com/Halildeu/ao-kernel/issues/999")
    assert not _valid(payload)

    payload = _fixture()
    payload["extra"] = "not allowed"
    assert not _valid(payload)

    payload = _fixture()
    payload["gates"]["support_widening"]["extra"] = "not allowed"
    assert not _valid(payload)


def test_roadmap_reference_target_exists_and_doc_says_not_ready() -> None:
    assert DOC_PATH.is_file()
    assert PRE_CHECKLIST_PATH.is_file()
    roadmap = ROADMAP_PATH.read_text(encoding="utf-8")
    doc = DOC_PATH.read_text(encoding="utf-8")

    assert "EPIC-9-FINAL-SUPERSESSION-PR.md" in roadmap
    assert "PR-Xfinal is **not ready to open**" in doc
    assert "epic9-xfinal-readiness-blocker.schema.v1.json" in doc
    assert "xfinal-readiness-blocker.current.json" in doc
    assert "#775" in doc
    assert "#776" in doc
    assert "#782" in doc
    assert "#895" in doc


def test_doc_does_not_authorize_forbidden_positive_claims() -> None:
    doc = DOC_PATH.read_text(encoding="utf-8").lower()
    forbidden = (
        "support_widening=true",
        "production_platform_claim=true",
        "live_adapter_execution=true",
        "production-ready",
        "production ready",
        "partial flip allowed",
    )
    for token in forbidden:
        assert token not in doc, f"draft guardrail must not include positive claim token: {token}"


def test_fixture_source_documents_exist() -> None:
    for gate in _fixture()["gates"].values():
        for source in gate["source_documents"]:
            path = ROOT / source
            assert path.exists(), f"source document missing: {source}"


def test_no_future_final_schema_is_accidentally_added() -> None:
    """The current slice is blocker-only; a future final proposal schema is
    expected to be a separate operator-bound PR, not part of this draft."""
    forbidden_paths = [
        ROOT / "ao_kernel" / "defaults" / "schemas" / "epic9-xfinal-supersession.schema.v1.json",
        ROOT / "ao_kernel" / "defaults" / "schemas" / "epic9-final-promotion.schema.v1.json",
    ]
    for path in forbidden_paths:
        assert not path.exists(), f"final proposal schema must not be added by blocker slice: {path.name}"


def test_schema_rejects_operator_boundary_drift() -> None:
    for field, value in (
        ("operator_bound_supersession_required", False),
        ("ai_output_is_release_authority", True),
        ("repo_owned_required_check_is_release_authority", False),
        ("exact_operator_authorization_required", False),
    ):
        payload = _fixture()
        payload["operator_boundary"][field] = value
        assert not _valid(payload), f"operator boundary drift must fail closed: {field}"
