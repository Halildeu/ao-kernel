"""V5 security/SBOM/license preflight bundle invariants.

The bundle is current-state evidence for one production-readiness dimension.
It is useful evidence, not final release authority: the schema pins final
release binding and all three production guard flags false.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from ao_kernel.config import load_default


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_NAME = "v5-security-sbom-license-preflight-bundle.schema.v1.json"
SCHEMA_PATH = ROOT / "ao_kernel" / "defaults" / "schemas" / SCHEMA_NAME
FIXTURE_PATH = ROOT / "tests" / "fixtures" / "epic9" / "v5-security-sbom-license-preflight.current.json"
MATRIX_PATH = ROOT / "tests" / "fixtures" / "epic9" / "v5-production-readiness-matrix.current.json"
DOC_PATH = ROOT / ".claude" / "plans" / "V5-SECURITY-SBOM-LICENSE-PREFLIGHT-BUNDLE.md"
MATRIX_DOC_PATH = ROOT / ".claude" / "plans" / "V5-PRODUCTION-READINESS-MATRIX-BLOCKER.md"


def _schema() -> dict[str, Any]:
    return load_default("schemas", SCHEMA_NAME)


def _fixture() -> dict[str, Any]:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def _matrix() -> dict[str, Any]:
    return json.loads(MATRIX_PATH.read_text(encoding="utf-8"))


def _valid(payload: dict[str, Any]) -> bool:
    return not list(Draft202012Validator(_schema()).iter_errors(payload))


def test_schema_present_valid_and_strict() -> None:
    assert SCHEMA_PATH.is_file()
    schema = _schema()
    Draft202012Validator.check_schema(schema)
    assert schema["$id"] == "urn:ao:v5-security-sbom-license-preflight-bundle:v1"

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


def test_current_fixture_validates_and_pins_non_authority_state() -> None:
    payload = _fixture()
    assert _valid(payload)
    assert payload["dimension"] == "security_sbom_license_scans"
    assert payload["evidence_class"] == "preflight_current_state"
    assert payload["final_release_bound"] is False
    assert payload["support_widening"] is False
    assert payload["production_platform_claim"] is False
    assert payload["live_adapter_execution"] is False


def test_schema_rejects_final_release_or_guard_flip_claims() -> None:
    for field, value in (
        ("final_release_bound", True),
        ("support_widening", True),
        ("production_platform_claim", True),
        ("live_adapter_execution", True),
    ):
        payload = _fixture()
        payload[field] = value
        assert not _valid(payload), f"{field}={value!r} must fail closed"


def test_security_workflow_refs_exist_and_are_advisory() -> None:
    for key in ("codeql", "trivy"):
        workflow = _fixture()[key]
        path = ROOT / workflow["workflow_path"]
        assert path.is_file()
        text = path.read_text(encoding="utf-8")
        assert workflow["status"] == "configured_advisory"
        assert workflow["required_check"] is False
        assert workflow["security_events_write_permission"] is True
        assert "security-events: write" in text
        assert "pull_request:" in text

    assert "exit-code: \"0\"" in (ROOT / ".github/workflows/trivy.yml").read_text(encoding="utf-8")
    assert "advisory" in (ROOT / ".github/workflows/codeql.yml").read_text(encoding="utf-8").lower()


def test_sbom_and_license_refs_exist_and_match_current_inventory() -> None:
    payload = _fixture()
    for path_key in ("generator_path", "generator_test_path", "sample_fixture_path"):
        assert (ROOT / payload["sbom"][path_key]).is_file()

    for path_key in ("policy_path", "inventory_path", "inventory_schema_path"):
        assert (ROOT / payload["license_compliance"][path_key]).is_file()

    inventory = json.loads((ROOT / payload["license_compliance"]["inventory_path"]).read_text(encoding="utf-8"))
    summary = inventory["summary"]
    assert inventory["report_status"] == payload["license_compliance"]["inventory_report_status"]
    assert summary["deny_count"] == payload["license_compliance"]["deny_count"]
    assert summary["review_count"] == payload["license_compliance"]["review_count"]
    assert payload["license_compliance"]["operator_review_required"] is True


def test_residual_missing_evidence_keeps_pr_xfinal_blocked() -> None:
    missing = _fixture()["residual_missing_evidence"]
    assert "final v5 release-bound SBOM artifact" in missing
    assert any("license inventory" in item for item in missing)
    assert any("PR-Xfinal" in item for item in missing)
    assert any("operator disposition" in item for item in missing)


def test_matrix_references_security_preflight_bundle_but_stays_partial() -> None:
    dimensions = {dimension["id"]: dimension for dimension in _matrix()["dimensions"]}
    security = dimensions["security_sbom_license_scans"]
    assert security["status"] == "partial"
    assert "tests/fixtures/epic9/v5-security-sbom-license-preflight.current.json" in security[
        "current_evidence_refs"
    ]
    assert "final v5 release-bound SBOM artifact" in security["missing_evidence"]
    assert _matrix()["matrix_complete"] is False
    assert _matrix()["production_platform_claim"] is False


def test_docs_reference_bundle_without_positive_claim_tokens() -> None:
    doc = DOC_PATH.read_text(encoding="utf-8")
    matrix_doc = MATRIX_DOC_PATH.read_text(encoding="utf-8")
    assert SCHEMA_NAME in doc
    assert "v5-security-sbom-license-preflight.current.json" in doc
    assert "security/SBOM/license preflight bundle" in matrix_doc

    lowered = doc.lower()
    forbidden = (
        "production-ready",
        "production ready",
        "support_widening=true",
        "production_platform_claim=true",
        "live_adapter_execution=true",
        "final_release_bound=true",
    )
    for token in forbidden:
        assert token not in lowered, f"preflight doc must not include positive claim token: {token}"
