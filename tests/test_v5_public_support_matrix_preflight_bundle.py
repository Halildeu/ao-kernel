"""V5 public support matrix preflight bundle invariants.

The bundle is current-state evidence for one production-readiness dimension.
It records the existing support boundary without widening support or promoting
the public claim. Final authority remains PR-Xfinal.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from ao_kernel.config import load_default


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_NAME = "v5-public-support-matrix-preflight-bundle.schema.v1.json"
SCHEMA_PATH = ROOT / "ao_kernel" / "defaults" / "schemas" / SCHEMA_NAME
FIXTURE_PATH = ROOT / "tests" / "fixtures" / "epic9" / "v5-public-support-matrix-preflight.current.json"
MATRIX_PATH = ROOT / "tests" / "fixtures" / "epic9" / "v5-production-readiness-matrix.current.json"
DOC_PATH = ROOT / ".claude" / "plans" / "V5-PUBLIC-SUPPORT-MATRIX-PREFLIGHT-BUNDLE.md"
MATRIX_DOC_PATH = ROOT / ".claude" / "plans" / "V5-PRODUCTION-READINESS-MATRIX-BLOCKER.md"


EXPECTED_SURFACES = {
    "provider",
    "python_version",
    "os_platform",
    "db_backend",
    "deployment_topology",
}


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
    assert schema["$id"] == "urn:ao:v5-public-support-matrix-preflight-bundle:v1"

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
    assert payload["dimension"] == "public_support_matrix"
    assert payload["evidence_class"] == "preflight_current_state"
    assert payload["final_release_bound"] is False
    assert payload["support_widening"] is False
    assert payload["production_platform_claim"] is False
    assert payload["live_adapter_execution"] is False
    assert payload["current_boundary"]["stable_support_layer"] == "shipped_baseline_only"
    assert payload["current_boundary"]["future_v5_support_matrix_present"] is False


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

    payload = _fixture()
    payload["current_boundary"]["support_widening_allowed"] = True
    assert not _valid(payload)

    payload = _fixture()
    payload["current_boundary"]["public_claim_widened"] = True
    assert not _valid(payload)

    payload = _fixture()
    payload["current_boundary"]["future_v5_support_matrix_present"] = True
    assert not _valid(payload)


def test_support_documents_exist_and_preserve_current_boundary_language() -> None:
    payload = _fixture()
    docs = payload["support_documents"]
    public_beta = ROOT / docs["public_beta_path"]
    support_boundary = ROOT / docs["support_boundary_path"]
    support_inventory = ROOT / docs["support_surface_inventory_path"]
    for path in (public_beta, support_boundary, support_inventory):
        assert path.is_file()

    public_beta_text = public_beta.read_text(encoding="utf-8")
    support_boundary_text = support_boundary.read_text(encoding="utf-8")
    support_inventory_text = support_inventory.read_text(encoding="utf-8")

    assert "Stable Support Boundary" in public_beta_text
    assert "Shipped (v4.0.0 stable)" in public_beta_text
    assert "Beta" in public_beta_text
    assert "Deferred" in public_beta_text
    assert "does not claim ao-kernel is a general-purpose" in public_beta_text
    assert "ST-2 stable boundary freeze" in support_boundary_text
    assert "support_widening" in support_inventory_text
    assert "announces no widening" in support_inventory_text


def test_surface_inventory_matches_support_surface_inventory_document() -> None:
    payload = _fixture()
    surfaces = {item["surface_class"] for item in payload["surface_inventory"]}
    assert surfaces == EXPECTED_SURFACES

    inventory_text = (ROOT / payload["support_documents"]["support_surface_inventory_path"]).read_text(
        encoding="utf-8"
    )
    for surface in EXPECTED_SURFACES:
        assert f"`{surface}`" in inventory_text

    for item in payload["surface_inventory"]:
        assert item["current_state"] == "inventory_only_or_existing_boundary"
        assert item["live_evidence_required"] is True
        assert item["operator_authorization_required"] is True
        assert item["future_widening_prerequisite"]


def test_residual_missing_evidence_keeps_pr_xfinal_blocked() -> None:
    missing = _fixture()["residual_missing_evidence"]
    assert "final v5.0.0 public support matrix with promoted support tier" in missing
    assert any("operator-authorized public claim" in item for item in missing)
    assert any("issue 776" in item for item in missing)
    assert any("PR-Xfinal" in item for item in missing)


def test_matrix_references_public_support_preflight_bundle_but_stays_partial() -> None:
    dimensions = {dimension["id"]: dimension for dimension in _matrix()["dimensions"]}
    public_support = dimensions["public_support_matrix"]
    assert public_support["status"] == "partial"
    assert "tests/fixtures/epic9/v5-public-support-matrix-preflight.current.json" in public_support[
        "current_evidence_refs"
    ]
    assert "final v5.0.0 public support matrix with promoted support tier" in public_support[
        "missing_evidence"
    ]
    assert _matrix()["matrix_complete"] is False
    assert _matrix()["support_widening"] is False
    assert _matrix()["production_platform_claim"] is False


def test_docs_reference_bundle_without_positive_claim_tokens() -> None:
    doc = DOC_PATH.read_text(encoding="utf-8")
    matrix_doc = MATRIX_DOC_PATH.read_text(encoding="utf-8")
    assert SCHEMA_NAME in doc
    assert "v5-public-support-matrix-preflight.current.json" in doc
    assert "public support matrix preflight bundle" in matrix_doc

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
