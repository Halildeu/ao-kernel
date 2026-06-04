"""V5 cost/rate/circuit-breaker preflight bundle invariants.

The bundle is current-state evidence for one production-readiness dimension.
It is useful evidence, not final release authority: the schema pins final
release binding and all three production guard flags false.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from ao_kernel.config import load_default


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_NAME = "v5-cost-rate-circuit-breaker-preflight-bundle.schema.v1.json"
SCHEMA_PATH = ROOT / "ao_kernel" / "defaults" / "schemas" / SCHEMA_NAME
FIXTURE_PATH = ROOT / "tests" / "fixtures" / "epic9" / "v5-cost-rate-circuit-breaker-preflight.current.json"
MATRIX_PATH = ROOT / "tests" / "fixtures" / "epic9" / "v5-production-readiness-matrix.current.json"
DOC_PATH = ROOT / ".claude" / "plans" / "V5-COST-RATE-CIRCUIT-BREAKER-PREFLIGHT-BUNDLE.md"
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
    assert schema["$id"] == "urn:ao:v5-cost-rate-circuit-breaker-preflight-bundle:v1"

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
    assert payload["dimension"] == "cost_rate_circuit_breaker_evidence"
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

    payload = _fixture()
    payload["cost_tracking_policy"]["bundled_default_enabled"] = True
    assert not _valid(payload)

    payload = _fixture()
    payload["usage_cost_evidence"]["live_evidence_available"] = True
    assert not _valid(payload)

    payload = _fixture()
    payload["rate_and_circuit_breaker"]["final_traffic_policy_evidence_present"] = True
    assert not _valid(payload)


def test_referenced_artifacts_exist() -> None:
    payload = _fixture()
    paths = [
        payload["cost_tracking_policy"]["doc_path"],
        payload["cost_tracking_policy"]["policy_path"],
        payload["cost_tracking_policy"]["policy_schema_path"],
        payload["cost_tracking_policy"]["policy_test_path"],
        payload["cost_ceiling"]["module_path"],
        payload["cost_ceiling"]["policy_path"],
        payload["cost_ceiling"]["test_path"],
        payload["per_call_audit"]["doc_path"],
        payload["per_call_audit"]["schema_path"],
        payload["per_call_audit"]["writer_path"],
        payload["per_call_audit"]["test_path"],
        payload["usage_cost_evidence"]["script_path"],
        payload["usage_cost_evidence"]["schema_path"],
        payload["usage_cost_evidence"]["test_path"],
        payload["rate_and_circuit_breaker"]["rate_limiter_path"],
        payload["rate_and_circuit_breaker"]["rate_limiter_test_path"],
        payload["rate_and_circuit_breaker"]["circuit_breaker_path"],
        payload["rate_and_circuit_breaker"]["circuit_breaker_test_path"],
        payload["incident_response"]["cost_burn_scenario_path"],
        payload["incident_response"]["sli_catalog_path"],
        payload["pricing_snapshot"]["snapshot_path"],
    ]
    for path in paths:
        assert (ROOT / path).is_file(), f"missing referenced artifact: {path}"


def test_cost_tracking_policy_defaults_are_dormant_but_fail_closed() -> None:
    policy_ref = _fixture()["cost_tracking_policy"]
    policy = json.loads((ROOT / policy_ref["policy_path"]).read_text(encoding="utf-8"))
    assert policy["enabled"] is policy_ref["bundled_default_enabled"]
    assert policy["fail_closed_on_exhaust"] is policy_ref["fail_closed_on_exhaust"]
    assert policy["fail_closed_on_missing_usage"] is policy_ref["fail_closed_on_missing_usage"]
    assert policy["strict_freshness"] is policy_ref["strict_freshness"]
    assert policy["routing_by_cost"]["enabled"] is policy_ref["routing_by_cost_enabled"]


def test_cost_ceiling_policy_and_tests_pin_soft_hard_breach_contract() -> None:
    ceiling = _fixture()["cost_ceiling"]
    policy = json.loads((ROOT / ceiling["policy_path"]).read_text(encoding="utf-8"))
    tests = (ROOT / ceiling["test_path"]).read_text(encoding="utf-8")
    module = (ROOT / ceiling["module_path"]).read_text(encoding="utf-8")

    assert policy["soft_usd"] == ceiling["soft_usd"]
    assert policy["hard_usd"] == ceiling["hard_usd"]
    assert policy["live_adapter_execution"] is False
    assert policy["support_widening"] is False
    assert policy["production_platform_claim"] is False
    assert "CostCeilingExceeded" in tests
    assert "hard_breached" in tests
    assert ceiling["workspace_state_jsonl"] in module
    assert ceiling["hard_breach_audit_write"] is True
    assert ceiling["concurrency_lock_serialized"] is True


def test_per_call_audit_and_usage_cost_evidence_are_not_provider_execution() -> None:
    payload = _fixture()
    audit_doc = (ROOT / payload["per_call_audit"]["doc_path"]).read_text(encoding="utf-8")
    usage_script = (ROOT / payload["usage_cost_evidence"]["script_path"]).read_text(encoding="utf-8")
    usage_tests = (ROOT / payload["usage_cost_evidence"]["test_path"]).read_text(encoding="utf-8")

    assert "Does NOT make a real provider call" in audit_doc
    assert payload["per_call_audit"]["actual_cost_required_decimal_string"] is True
    assert payload["per_call_audit"]["provider_call_made"] is False
    assert "The script never emits live evidence" in usage_script
    assert "``evidence_class`` is fixed to ``simulated``" in usage_script
    assert payload["usage_cost_evidence"]["autonomous_evidence_class"] == "simulated"
    assert payload["usage_cost_evidence"]["live_evidence_available"] is False
    assert "live_adapter_execution=true" in usage_tests


def test_rate_circuit_breaker_and_budget_burn_surfaces_are_preflight_only() -> None:
    payload = _fixture()
    rate_tests = (ROOT / payload["rate_and_circuit_breaker"]["rate_limiter_test_path"]).read_text(encoding="utf-8")
    breaker_tests = (ROOT / payload["rate_and_circuit_breaker"]["circuit_breaker_test_path"]).read_text(
        encoding="utf-8"
    )
    incident = (ROOT / payload["incident_response"]["cost_burn_scenario_path"]).read_text(encoding="utf-8")
    catalog = json.loads((ROOT / payload["incident_response"]["sli_catalog_path"]).read_text(encoding="utf-8"))

    assert "test_reset_all_clears" in rate_tests
    assert "test_open_transitions_to_half_open" in breaker_tests
    assert payload["rate_and_circuit_breaker"]["final_traffic_policy_evidence_present"] is False
    assert payload["incident_response"]["indicator_name"] == "monthly_cost_burn_projection_usd"
    assert "Recording-only in v1" in incident
    indicator = next(item for item in catalog["indicators"] if item["name"] == "monthly_cost_burn_projection_usd")
    assert indicator["objective_kind"] == payload["incident_response"]["objective_kind"]


def test_pricing_snapshot_digest_and_boundary_match_fixture() -> None:
    pricing = _fixture()["pricing_snapshot"]
    path = ROOT / pricing["snapshot_path"]
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    data = json.loads(path.read_text(encoding="utf-8"))

    assert f"sha256:{digest}" == pricing["snapshot_sha256"]
    assert data["source_authority"] == pricing["source_authority"]
    assert data["currency"] == pricing["currency"]
    assert data["precision_decimal_places"] == pricing["precision_decimal_places"]
    assert pricing["final_fresh_pricing_snapshot"] is False


def test_residual_missing_evidence_keeps_pr_xfinal_blocked() -> None:
    missing = _fixture()["residual_missing_evidence"]
    assert "live cost evidence bound to the authorized 7-day provider window" in missing
    assert any("protected live run" in item for item in missing)
    assert any("rollback evidence" in item for item in missing)
    assert any("fresh pricing-source snapshot" in item for item in missing)


def test_matrix_references_cost_preflight_bundle_but_stays_partial() -> None:
    dimensions = {dimension["id"]: dimension for dimension in _matrix()["dimensions"]}
    cost = dimensions["cost_rate_circuit_breaker_evidence"]
    assert cost["status"] == "partial"
    assert "tests/fixtures/epic9/v5-cost-rate-circuit-breaker-preflight.current.json" in cost[
        "current_evidence_refs"
    ]
    assert "live cost evidence bound to 7-day window" in cost["missing_evidence"]
    assert _matrix()["matrix_complete"] is False
    assert _matrix()["production_platform_claim"] is False
    assert _matrix()["live_adapter_execution"] is False


def test_docs_reference_bundle_without_positive_claim_tokens() -> None:
    doc = DOC_PATH.read_text(encoding="utf-8")
    matrix_doc = MATRIX_DOC_PATH.read_text(encoding="utf-8")
    assert SCHEMA_NAME in doc
    assert "v5-cost-rate-circuit-breaker-preflight.current.json" in doc
    assert "cost/rate/circuit breaker preflight bundle" in matrix_doc

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
