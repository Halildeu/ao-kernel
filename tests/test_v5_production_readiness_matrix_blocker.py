"""V5 production readiness matrix blocker invariants.

The V5 roadmap defines a 9-dimensional production readiness matrix for the
future Epic 9 PR-Xfinal. This test pins the current state as fail-closed:
the matrix is incomplete, PR-Xfinal is not openable, and no guard flag can
flip under the blocker schema.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from ao_kernel.config import load_default


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_NAME = "v5-production-readiness-matrix-blocker.schema.v1.json"
SCHEMA_PATH = ROOT / "ao_kernel" / "defaults" / "schemas" / SCHEMA_NAME
FIXTURE_PATH = ROOT / "tests" / "fixtures" / "epic9" / "v5-production-readiness-matrix.current.json"
DOC_PATH = ROOT / ".claude" / "plans" / "V5-PRODUCTION-READINESS-MATRIX-BLOCKER.md"
XFINAL_DOC_PATH = ROOT / ".claude" / "plans" / "EPIC-9-FINAL-SUPERSESSION-PR.md"
ROADMAP_PATH = ROOT / ".claude" / "plans" / "V5-FULL-PRODUCTION-PROMOTION-ROADMAP.md"


EXPECTED_DIMENSIONS = {
    "public_support_matrix",
    "protected_real_provider_live_calls",
    "cost_rate_circuit_breaker_evidence",
    "observability_production_tunables",
    "security_sbom_license_scans",
    "install_deploy_lifecycle_smoke",
    "multi_tenancy_isolation",
    "docs_runbooks",
    "bypassless_release_governance",
}


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
    assert schema["$id"] == "urn:ao:v5-production-readiness-matrix-blocker:v1"

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


def test_current_fixture_validates_and_pins_closed_gate_state() -> None:
    payload = _fixture()
    assert _valid(payload)
    assert payload["matrix_complete"] is False
    assert payload["pr_xfinal_open_allowed"] is False
    assert payload["support_widening"] is False
    assert payload["production_platform_claim"] is False
    assert payload["live_adapter_execution"] is False
    assert payload["operator_bound_supersession_required"] is True


def test_fixture_contains_exact_nine_roadmap_dimensions() -> None:
    payload = _fixture()
    ids = {dimension["id"] for dimension in payload["dimensions"]}
    assert ids == EXPECTED_DIMENSIONS
    assert len(payload["dimensions"]) == 9

    for dimension in payload["dimensions"]:
        assert dimension["status"] in {"not_ready", "partial"}
        assert dimension["required_evidence"]
        assert dimension["missing_evidence"]
        assert dimension["source_documents"]


def test_schema_rejects_matrix_completion_or_any_guard_flip() -> None:
    for field, value in (
        ("matrix_complete", True),
        ("pr_xfinal_open_allowed", True),
        ("support_widening", True),
        ("production_platform_claim", True),
        ("live_adapter_execution", True),
        ("operator_bound_supersession_required", False),
    ):
        payload = _fixture()
        payload[field] = value
        assert not _valid(payload), f"{field}={value!r} must fail closed in blocker v1"


def test_schema_rejects_ready_dimension_claims_in_blocker_v1() -> None:
    for index, dimension in enumerate(_fixture()["dimensions"]):
        payload = _fixture()
        payload["dimensions"][index]["status"] = "ready"
        assert not _valid(payload), f"{dimension['id']} ready claim must fail closed"


def test_schema_rejects_dimension_cardinality_or_id_drift() -> None:
    payload = _fixture()
    payload["dimensions"] = payload["dimensions"][:-1]
    assert not _valid(payload)

    payload = _fixture()
    payload["dimensions"][0]["id"] = "unexpected_dimension"
    assert not _valid(payload)

    payload = _fixture()
    payload["dimensions"][0]["missing_evidence"] = []
    assert not _valid(payload)

    payload = _fixture()
    payload["extra"] = "not allowed"
    assert not _valid(payload)


def test_doc_and_xfinal_gate_c_reference_matrix_blocker() -> None:
    doc = DOC_PATH.read_text(encoding="utf-8")
    xfinal_doc = XFINAL_DOC_PATH.read_text(encoding="utf-8")
    roadmap = ROADMAP_PATH.read_text(encoding="utf-8")

    assert "9-dimensional" in doc
    assert "matrix_complete=false" in doc
    assert "production_platform_claim=false" in doc
    assert "v5-production-readiness-matrix-blocker.schema.v1.json" in doc
    assert "v5-production-readiness-matrix.current.json" in doc
    assert "V5-PRODUCTION-READINESS-MATRIX-BLOCKER.md" in xfinal_doc
    assert "9 boyutta evidence matrix" in roadmap


def test_doc_does_not_authorize_production_claim_tokens() -> None:
    text = DOC_PATH.read_text(encoding="utf-8").lower()
    forbidden = (
        "production-ready",
        "production ready",
        "support_widening=true",
        "production_platform_claim=true",
        "live_adapter_execution=true",
        "pr_xfinal_open_allowed=true",
        "matrix_complete=true",
    )
    for token in forbidden:
        assert token not in text, f"blocker doc must not include positive claim token: {token}"


def test_fixture_source_documents_and_current_refs_exist() -> None:
    for dimension in _fixture()["dimensions"]:
        for source in dimension["source_documents"]:
            assert (ROOT / source).exists(), f"source document missing: {source}"
        for ref in dimension["current_evidence_refs"]:
            assert (ROOT / ref).exists(), f"current evidence ref missing: {ref}"


def test_issue_refs_match_xfinal_blocker_issue_set() -> None:
    assert _fixture()["issue_refs"] == [
        "https://github.com/Halildeu/ao-kernel/issues/775",
        "https://github.com/Halildeu/ao-kernel/issues/776",
        "https://github.com/Halildeu/ao-kernel/issues/782",
        "https://github.com/Halildeu/ao-kernel/issues/895",
    ]
