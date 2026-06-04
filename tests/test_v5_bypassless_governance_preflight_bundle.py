"""V5 bypassless release governance preflight bundle invariants.

The bundle is current-state evidence for one production-readiness dimension
(matrix dimension 9: bypassless_release_governance). It records the already
active repo merge-governance controls — source-pinned required checks, empty
bypass actors, autonomous merge trail for low-risk changes, and cross-provider
review for guarded changes — without flipping any guard flag or claiming the
dimension complete. The matrix dimension stays ``partial``; final authority
remains PR-Xfinal.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from ao_kernel.config import load_default


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_NAME = "v5-bypassless-governance-preflight-bundle.schema.v1.json"
SCHEMA_PATH = ROOT / "ao_kernel" / "defaults" / "schemas" / SCHEMA_NAME
FIXTURE_PATH = ROOT / "tests" / "fixtures" / "epic9" / "v5-bypassless-governance-preflight.current.json"
MATRIX_PATH = ROOT / "tests" / "fixtures" / "epic9" / "v5-production-readiness-matrix.current.json"
DOC_PATH = ROOT / ".claude" / "plans" / "V5-BYPASSLESS-GOVERNANCE-PREFLIGHT-BUNDLE.md"


EXPECTED_CONTROLS = {
    "ao_release_gate_required_check_source_pin",
    "empty_bypass_actors",
    "autonomous_merge_trail_low_risk",
    "cross_provider_review_guarded_changes",
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
    assert schema["$id"] == "urn:ao:v5-bypassless-governance-preflight-bundle:v1"

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
    assert payload["dimension"] == "bypassless_release_governance"
    assert payload["evidence_class"] == "preflight_current_state"
    assert payload["final_release_bound"] is False
    assert payload["support_widening"] is False
    assert payload["production_platform_claim"] is False
    assert payload["live_adapter_execution"] is False
    boundary = payload["current_boundary"]
    assert boundary["bypass_actors_count"] == 0
    assert boundary["admin_merge_used"] is False
    assert boundary["autonomous_merge_for_low_risk"] is True
    assert boundary["cross_provider_review_for_guarded_changes"] is True
    assert boundary["final_ruleset_source_pin_bound_to_pr_xfinal"] is False
    assert set(boundary["required_checks"]) == {
        "ao-release-gate-technical",
        "ao-release-gate-review",
    }


def test_schema_rejects_guard_flip_or_bypass_claims() -> None:
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
    payload["current_boundary"]["bypass_actors_count"] = 1
    assert not _valid(payload), "non-empty bypass actors must fail closed"

    payload = _fixture()
    payload["current_boundary"]["admin_merge_used"] = True
    assert not _valid(payload), "admin merge claim must fail closed"

    payload = _fixture()
    payload["current_boundary"]["final_ruleset_source_pin_bound_to_pr_xfinal"] = True
    assert not _valid(payload), "premature PR-Xfinal binding must fail closed"


def test_governance_controls_match_expected_active_set() -> None:
    payload = _fixture()
    controls = payload["governance_controls"]
    assert {item["control"] for item in controls} == EXPECTED_CONTROLS
    for item in controls:
        assert item["current_state"] == "active_in_current_repo_governance"
        assert item["future_prerequisite_under_pr_xfinal"].strip()


def test_governance_documents_exist_and_carry_anchor_language() -> None:
    payload = _fixture()
    docs = payload["governance_documents"]
    repo_gov = ROOT / docs["repo_governance_path"]
    hardening = ROOT / docs["hardening_program_status_path"]
    gpp_status = ROOT / docs["gpp_status_path"]
    for path in (repo_gov, hardening, gpp_status):
        assert path.is_file()

    repo_gov_text = repo_gov.read_text(encoding="utf-8")
    assert "bypass" in repo_gov_text
    assert "admin" in repo_gov_text
    assert "keep_narrow_stable_runtime" in gpp_status.read_text(encoding="utf-8")


def test_matrix_dimension_stays_partial_and_incomplete() -> None:
    matrix = _matrix()
    assert matrix["matrix_complete"] is False
    dim = next(d for d in matrix["dimensions"] if d["id"] == "bypassless_release_governance")
    assert dim["status"] in {"not_ready", "partial"}


def test_doc_present_and_non_authority() -> None:
    assert DOC_PATH.is_file()
    text = DOC_PATH.read_text(encoding="utf-8")
    assert "bypassless_release_governance" in text
    assert "PR-Xfinal" in text
