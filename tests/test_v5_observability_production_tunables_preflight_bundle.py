"""V5 observability production tunables preflight bundle invariants.

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
SCHEMA_NAME = "v5-observability-production-tunables-preflight-bundle.schema.v1.json"
SCHEMA_PATH = ROOT / "ao_kernel" / "defaults" / "schemas" / SCHEMA_NAME
FIXTURE_PATH = (
    ROOT
    / "tests"
    / "fixtures"
    / "epic9"
    / "v5-observability-production-tunables-preflight.current.json"
)
MATRIX_PATH = ROOT / "tests" / "fixtures" / "epic9" / "v5-production-readiness-matrix.current.json"
DOC_PATH = ROOT / ".claude" / "plans" / "V5-OBSERVABILITY-PRODUCTION-TUNABLES-PREFLIGHT-BUNDLE.md"
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
    assert schema["$id"] == "urn:ao:v5-observability-production-tunables-preflight-bundle:v1"

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
    assert payload["dimension"] == "observability_production_tunables"
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
    payload["sli_catalog"]["alerting_or_escalation_evidence_present"] = True
    assert not _valid(payload)

    payload = _fixture()
    payload["performance_policy"]["ci_blocking_enforced"] = True
    assert not _valid(payload)

    payload = _fixture()
    payload["grafana_dashboard"]["final_claim_bound"] = True
    assert not _valid(payload)


def test_observability_artifact_refs_exist_and_match_current_state() -> None:
    payload = _fixture()
    paths = [
        payload["grafana_dashboard"]["dashboard_path"],
        payload["grafana_dashboard"]["dashboard_readme_path"],
        payload["grafana_dashboard"]["dashboard_shape_test_path"],
        payload["sli_catalog"]["catalog_path"],
        payload["sli_catalog"]["catalog_schema_path"],
        payload["sli_catalog"]["catalog_doc_path"],
        payload["sli_catalog"]["catalog_test_path"],
        payload["performance_policy"]["readme_path"],
        payload["performance_policy"]["baseline_path"],
        payload["performance_policy"]["threshold_path"],
        payload["performance_policy"]["scenario_catalog_path"],
        payload["performance_policy"]["performance_test_path"],
    ]
    for path in paths:
        assert (ROOT / path).is_file(), f"missing referenced artifact: {path}"


def test_grafana_dashboard_shape_is_bound_without_final_claim() -> None:
    grafana = _fixture()["grafana_dashboard"]
    dashboard = json.loads((ROOT / grafana["dashboard_path"]).read_text(encoding="utf-8"))
    assert len(dashboard["panels"]) == grafana["documented_panel_count"]
    names = {item["name"] for item in dashboard["templating"]["list"]}
    assert grafana["datasource_variable"] in names
    assert grafana["advanced_overlay_required"] is False
    assert grafana["final_claim_bound"] is False


def test_sli_catalog_counts_and_guard_flags_match_fixture() -> None:
    sli = _fixture()["sli_catalog"]
    catalog = json.loads((ROOT / sli["catalog_path"]).read_text(encoding="utf-8"))
    indicators = catalog["indicators"]
    by_kind: dict[str, list[dict[str, Any]]] = {}
    for indicator in indicators:
        by_kind.setdefault(indicator["objective_kind"], []).append(indicator)

    assert len(indicators) == sli["indicator_count"]
    assert len([item for item in indicators if item.get("hard_slo") is True]) == sli["hard_slo_count"]
    assert len(by_kind["advisory_sli"]) == sli["advisory_sli_count"]
    assert len(by_kind["budget_objective"]) == sli["budget_objective_count"]
    assert catalog["uptime_status"]["in_scope"] == sli["uptime_in_scope"]
    assert catalog["guard_flags"] == {
        "support_widening_allowed": False,
        "production_platform_claim_allowed": False,
        "live_adapter_execution_allowed": False,
    }
    assert all(indicator["operator_owned"] is sli["operator_owned"] for indicator in indicators)
    assert all(indicator["is_contractual_sla"] is sli["contractual_sla"] for indicator in indicators)


def test_performance_policy_is_advisory_candidate_baseline_only() -> None:
    policy = _fixture()["performance_policy"]
    baseline = json.loads((ROOT / policy["baseline_path"]).read_text(encoding="utf-8"))
    threshold = json.loads((ROOT / policy["threshold_path"]).read_text(encoding="utf-8"))
    assert threshold["enforcement_mode"] == policy["enforcement_mode"]
    assert baseline["candidate_baseline"] is policy["candidate_baseline"]
    assert baseline["sample_count"] == policy["sample_count"]
    assert policy["final_claim_bound"] is False
    assert policy["ci_blocking_enforced"] is False
    assert baseline["guard_flags"] == threshold["guard_flags"] == {
        "support_widening_allowed": False,
        "production_platform_claim_allowed": False,
        "live_adapter_execution_allowed": False,
    }


def test_residual_missing_evidence_keeps_pr_xfinal_blocked() -> None:
    missing = _fixture()["residual_missing_evidence"]
    assert "final claim-bound observability smoke" in missing
    assert any("alerting or escalation evidence" in item for item in missing)
    assert any("PR-Xfinal" in item for item in missing)
    assert any("dashboard import" in item for item in missing)


def test_matrix_references_observability_preflight_bundle_but_stays_partial() -> None:
    dimensions = {dimension["id"]: dimension for dimension in _matrix()["dimensions"]}
    observability = dimensions["observability_production_tunables"]
    assert observability["status"] == "partial"
    assert "tests/fixtures/epic9/v5-observability-production-tunables-preflight.current.json" in observability[
        "current_evidence_refs"
    ]
    assert "final claim-bound observability smoke" in observability["missing_evidence"]
    assert _matrix()["matrix_complete"] is False
    assert _matrix()["production_platform_claim"] is False
    assert _matrix()["live_adapter_execution"] is False


def test_docs_reference_bundle_without_positive_claim_tokens() -> None:
    doc = DOC_PATH.read_text(encoding="utf-8")
    matrix_doc = MATRIX_DOC_PATH.read_text(encoding="utf-8")
    assert SCHEMA_NAME in doc
    assert "v5-observability-production-tunables-preflight.current.json" in doc
    assert "observability production tunables preflight bundle" in matrix_doc

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
