"""V5 protected real-provider live-calls preflight bundle invariants.

The bundle records current preflight assets for one V5 production-readiness
dimension. It is not release authority: the schema pins final release binding,
workflow dispatch, provider calls, secret reference, and all three production
guard flags false.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from ao_kernel.config import load_default


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_NAME = "v5-protected-real-provider-live-calls-preflight-bundle.schema.v1.json"
SCHEMA_PATH = ROOT / "ao_kernel" / "defaults" / "schemas" / SCHEMA_NAME
FIXTURE_PATH = ROOT / "tests" / "fixtures" / "epic9" / "v5-protected-real-provider-live-calls-preflight.current.json"
MATRIX_PATH = ROOT / "tests" / "fixtures" / "epic9" / "v5-production-readiness-matrix.current.json"
DOC_PATH = ROOT / ".claude" / "plans" / "V5-PROTECTED-REAL-PROVIDER-LIVE-CALLS-PREFLIGHT-BUNDLE.md"
MATRIX_DOC_PATH = ROOT / ".claude" / "plans" / "V5-PRODUCTION-READINESS-MATRIX-BLOCKER.md"
GPP_STATUS_PATH = ROOT / ".claude" / "plans" / "gpp_status.v1.json"
FINAL_DECISION_PATH = ROOT / ".claude" / "plans" / "RI-7.8c-FINAL-PROMOTE-DECISION.v1.json"
SUBMANIFEST_PATH = ROOT / ".claude" / "plans" / "RI-7.8-EVIDENCE-MANIFEST.v1.json"


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
    assert schema["$id"] == "urn:ao:v5-protected-real-provider-live-calls-preflight-bundle:v1"

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
    assert payload["dimension"] == "protected_real_provider_live_calls"
    assert payload["evidence_class"] == "preflight_current_state"
    assert payload["final_release_bound"] is False
    assert payload["support_widening"] is False
    assert payload["production_platform_claim"] is False
    assert payload["live_adapter_execution"] is False
    assert payload["execution_boundary"]["workflow_dispatched"] is False
    assert payload["execution_boundary"]["provider_call_performed"] is False
    assert payload["execution_boundary"]["secret_referenced"] is False


def test_schema_rejects_final_release_or_execution_claims() -> None:
    for field, value in (
        ("final_release_bound", True),
        ("support_widening", True),
        ("production_platform_claim", True),
        ("live_adapter_execution", True),
    ):
        payload = _fixture()
        payload[field] = value
        assert not _valid(payload), f"{field}={value!r} must fail closed"

    for field in (
        "workflow_dispatched",
        "provider_call_performed",
        "secret_referenced",
        "bc10_aggregate_recorded",
        "current_decision_authorizes_execution",
    ):
        payload = _fixture()
        payload["execution_boundary"][field] = True
        assert not _valid(payload), f"execution_boundary.{field}=true must fail closed"


def test_referenced_assets_exist() -> None:
    payload = _fixture()
    refs = [
        payload["current_authority"]["gpp_status_path"],
        payload["current_authority"]["final_non_promotion_decision_path"],
        payload["current_authority"]["bc10_defer_decision_path"],
        *payload["preauthorization_assets"].values(),
    ]
    for ref in refs:
        if isinstance(ref, str):
            assert (ROOT / ref).exists(), f"missing referenced artifact: {ref}"


def test_current_authority_matches_gpp_status_and_final_decision() -> None:
    payload = _fixture()
    gpp_status = json.loads(GPP_STATUS_PATH.read_text(encoding="utf-8"))
    final_decision = json.loads(FINAL_DECISION_PATH.read_text(encoding="utf-8"))

    assert payload["current_authority"]["gpp_exit_decision"] == gpp_status["current_wp"]["exit_decision"]
    assert payload["current_authority"]["support_widening_allowed"] is gpp_status["support_widening_allowed"]
    assert payload["current_authority"]["production_platform_claim_allowed"] is gpp_status[
        "production_platform_claim_allowed"
    ]
    assert payload["current_authority"]["live_adapter_execution_allowed"] is gpp_status[
        "live_adapter_execution_allowed"
    ]
    rationale = final_decision["non_promotion_rationale"]
    assert rationale["current_usage_pattern_is_cli_only_monthly_subscription"] is True
    assert rationale["no_programmatic_api_call_in_current_or_planned_use"] is True
    assert rationale["bc10_chain_deferred_under_cli_only_per_pr_731"] is True
    assert final_decision["future_promotion_authority_chain"][
        "future_promotion_requires_full_production_matrix_evidence"
    ] is True


def test_bc10_execution_contract_assets_are_dormant_not_live_evidence() -> None:
    payload = _fixture()
    assets = payload["preauthorization_assets"]
    authorization = json.loads((ROOT / assets["bc10_6a_authorization_evidence"]).read_text(encoding="utf-8"))
    protected_window = json.loads((ROOT / assets["bc10_6b_protected_window_evidence"]).read_text(encoding="utf-8"))
    defer_decision = json.loads((ROOT / assets["bc10_6c_defer_decision_evidence"]).read_text(encoding="utf-8"))
    submanifest = json.loads(SUBMANIFEST_PATH.read_text(encoding="utf-8"))

    assert authorization["authorization_effect"].endswith("no_billable_call_no_secret_reference")
    assert authorization["activation_requirements"]["activation_requires_manual_approval_review"] is True
    assert authorization["future_workflow_contract"]["model_allowlist"] == ["openai/gpt-4o-mini"]
    assert protected_window["authority_mode"] == "manual_protected_environment"
    assert protected_window["authorization_effect"].endswith("pending_operator_dispatch_no_billable_call_no_submanifest_flip")
    assert protected_window["autonomous_trigger_allowed"] is False
    assert protected_window["run_budget"]["max_billable_calls_count"] == 4
    assert protected_window["mutations_performed"]["provider_call_performed"] is False
    assert protected_window["mutations_performed"]["secret_referenced_in_repo"] is False
    assert "billable_provider_call_ever_under_this_decision" in defer_decision["does_not_authorize"]
    assert defer_decision["live_adapter_execution"] is False
    assert submanifest["bc10_real_adapter_usage_cost_aggregate_recorded"] is False
    assert submanifest["bc10_defer_decision_recorded"] is True


def test_dormant_workflow_and_scripts_are_present_but_not_dispatched() -> None:
    payload = _fixture()
    assets = payload["preauthorization_assets"]
    boundary = payload["execution_boundary"]
    workflow = (ROOT / assets["workflow_path"]).read_text(encoding="utf-8")
    activation_script = (ROOT / assets["activation_script_path"]).read_text(encoding="utf-8")
    scenario_runner = (ROOT / assets["scenario_runner_path"]).read_text(encoding="utf-8")

    assert boundary["workflow_exists"] is True
    assert boundary["workflow_dispatched"] is False
    assert boundary["provider_call_performed"] is False
    assert boundary["assets_dormant_for_future_api_mode"] is True
    assert "workflow_dispatch" in workflow
    assert "manual_protected_environment" in activation_script
    assert "budget_cap_precheck_denied" in scenario_runner


def test_matrix_references_protected_real_provider_preflight_bundle_but_stays_blocked() -> None:
    dimensions = {dimension["id"]: dimension for dimension in _matrix()["dimensions"]}
    protected = dimensions["protected_real_provider_live_calls"]
    assert protected["status"] == "partial"
    assert ".claude/plans/V5-PROTECTED-REAL-PROVIDER-LIVE-CALLS-PREFLIGHT-BUNDLE.md" in protected[
        "current_evidence_refs"
    ]
    assert "tests/fixtures/epic9/v5-protected-real-provider-live-calls-preflight.current.json" in protected[
        "current_evidence_refs"
    ]
    assert any("fresh operator-bound API-mode supersession" in item for item in protected["missing_evidence"])
    assert _matrix()["matrix_complete"] is False
    assert _matrix()["production_platform_claim"] is False
    assert _matrix()["live_adapter_execution"] is False


def test_docs_reference_bundle_without_positive_claim_tokens() -> None:
    doc = DOC_PATH.read_text(encoding="utf-8")
    matrix_doc = MATRIX_DOC_PATH.read_text(encoding="utf-8")
    assert SCHEMA_NAME in doc
    assert "v5-protected-real-provider-live-calls-preflight.current.json" in doc
    assert "protected real-provider live-calls preflight bundle" in matrix_doc

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
