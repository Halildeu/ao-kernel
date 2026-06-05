"""V5 multi-tenancy isolation preflight bundle invariants.

The V5 production readiness matrix keeps the multi-tenancy dimension partial
until a later operator-bound PR supplies live cluster validation, cross-tenant
leak-prevention evidence, per-tenant quota/cost proof, and final release-bound
operator attestation. This bundle records current advisory evidence only.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from ao_kernel.config import load_default


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_NAME = "v5-multi-tenancy-isolation-preflight-bundle.schema.v1.json"
SCHEMA_PATH = ROOT / "ao_kernel" / "defaults" / "schemas" / SCHEMA_NAME
FIXTURE_PATH = ROOT / "tests" / "fixtures" / "epic9" / "v5-multi-tenancy-isolation-preflight.current.json"
MATRIX_FIXTURE_PATH = ROOT / "tests" / "fixtures" / "epic9" / "v5-production-readiness-matrix.current.json"
MATRIX_DOC_PATH = ROOT / ".claude" / "plans" / "V5-PRODUCTION-READINESS-MATRIX-BLOCKER.md"
BUNDLE_DOC_PATH = ROOT / ".claude" / "plans" / "V5-MULTI-TENANCY-ISOLATION-PREFLIGHT-BUNDLE.md"
TENANT_MATRIX_PATH = ROOT / ".claude" / "plans" / "tenant_isolation_matrix.v1.json"

EXPECTED_DIMENSIONS = [
    "namespace_isolation",
    "rbac_scope",
    "secret_isolation",
    "network_policy",
    "resource_quota",
    "audit_boundary",
    "cost_tracking_advisory",
]


def _schema() -> dict[str, Any]:
    return load_default("schemas", SCHEMA_NAME)


def _fixture() -> dict[str, Any]:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def _matrix_fixture() -> dict[str, Any]:
    return json.loads(MATRIX_FIXTURE_PATH.read_text(encoding="utf-8"))


def _tenant_matrix() -> dict[str, Any]:
    return json.loads(TENANT_MATRIX_PATH.read_text(encoding="utf-8"))


def _is_valid(payload: dict[str, Any]) -> bool:
    return not list(Draft202012Validator(_schema()).iter_errors(payload))


def _object_nodes(node: Any) -> list[dict[str, Any]]:
    nodes: list[dict[str, Any]] = []
    if isinstance(node, dict):
        if node.get("type") == "object":
            nodes.append(node)
        for value in node.values():
            nodes.extend(_object_nodes(value))
    elif isinstance(node, list):
        for value in node:
            nodes.extend(_object_nodes(value))
    return nodes


def _dimension(payload: dict[str, Any], dimension_id: str) -> dict[str, Any]:
    for dimension in payload["dimensions"]:
        if dimension["id"] == dimension_id:
            return dimension
    raise AssertionError(f"dimension not found: {dimension_id}")


def test_schema_present_valid_and_strict() -> None:
    assert SCHEMA_PATH.is_file()
    schema = _schema()
    Draft202012Validator.check_schema(schema)
    assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
    assert schema["$id"] == "urn:ao:v5-multi-tenancy-isolation-preflight-bundle:v1"

    for node in _object_nodes(schema):
        assert node.get("additionalProperties") is False
        assert node.get("unevaluatedProperties") is False


def test_current_fixture_validates_and_pins_non_authority_boundary() -> None:
    payload = _fixture()
    assert _is_valid(payload)
    assert payload["schema_version"] == "v5_multi_tenancy_isolation_preflight_bundle.v1"
    assert payload["artifact_kind"] == "v5_multi_tenancy_isolation_preflight_bundle"
    assert payload["repo"] == "Halildeu/ao-kernel"
    assert payload["work_package"] == "E-9-1"
    assert payload["dimension"] == "multi_tenancy_isolation"
    assert payload["evidence_class"] == "preflight_current_state"
    assert payload["runtime_enforced"] is False
    assert payload["operator_enforceable"] is True
    assert payload["operator_action_required"] is True
    assert payload["live_validated"] is False
    assert payload["tenant_isolation_ready"] is False
    assert payload["support_widening"] is False
    assert payload["production_platform_claim"] is False
    assert payload["live_adapter_execution"] is False


def test_schema_rejects_runtime_live_ready_or_guard_flips() -> None:
    for field in (
        "runtime_enforced",
        "live_validated",
        "tenant_isolation_ready",
        "support_widening",
        "production_platform_claim",
        "live_adapter_execution",
    ):
        payload = _fixture()
        payload[field] = True
        assert not _is_valid(payload), f"{field}=true must fail closed"


def test_schema_rejects_nested_authority_or_boundary_claim_flips() -> None:
    mutations: tuple[tuple[str, str, bool], ...] = (
        ("advisory_matrix", "runtime_enforced_global", True),
        ("advisory_matrix", "live_validated_global", True),
        ("deployment_runbook", "runtime_enforced", True),
        ("deployment_runbook", "live_validated", True),
        ("deployment_runbook", "live_cluster_commands_embedded", True),
        ("config_recipe", "inline_secret_material_present", True),
        ("helm_boundary", "cluster_scoped_rbac_present", True),
        ("helm_boundary", "resourcequota_rendered_by_chart", True),
        ("rate_limit", "live_adapter_execution", True),
    )
    for section, field, value in mutations:
        payload = _fixture()
        payload[section][field] = value
        assert not _is_valid(payload), f"{section}.{field}={value!r} must fail closed"


def test_schema_rejects_path_or_extra_field_drift() -> None:
    payload = _fixture()
    payload["deployment_runbook"]["doc_path"] = "docs/OTHER.md"
    assert not _is_valid(payload)

    payload = _fixture()
    payload["rate_limit"]["doc_path"] = "docs/OTHER.md"
    assert not _is_valid(payload)

    payload = _fixture()
    payload["unexpected"] = "not allowed"
    assert not _is_valid(payload)

    payload = _fixture()
    payload["helm_boundary"]["unexpected"] = "not allowed"
    assert not _is_valid(payload)


def test_all_referenced_artifacts_exist() -> None:
    payload = _fixture()
    for section_name in ("advisory_matrix", "deployment_runbook", "config_recipe", "helm_boundary", "rate_limit"):
        section = payload[section_name]
        for key, value in section.items():
            if key.endswith("_path") or key in {"chart_root", "values_path"}:
                assert (ROOT / value).exists(), f"{section_name}.{key} missing: {value}"


def test_advisory_matrix_exactly_binds_final_seal_without_live_claim() -> None:
    payload = _fixture()
    section = payload["advisory_matrix"]
    matrix = _tenant_matrix()

    assert section["matrix_status"] == "e_4_2b_final_seal"
    assert section["exact_dimensions"] == EXPECTED_DIMENSIONS
    assert matrix["matrix_status"] == "e_4_2b_final_seal"
    assert matrix["advisory_only"] is True
    assert matrix["runtime_enforced_global"] is False
    assert matrix["live_validated_global"] is False
    assert len(matrix["dimensions"]) == 7
    assert [entry["dimension"] for entry in matrix["dimensions"]] == EXPECTED_DIMENSIONS

    for entry in matrix["dimensions"]:
        assert entry["entry_status"] == "filled"
        assert entry["runtime_enforced"] is False
        assert entry["operator_enforceable"] is True
        assert entry["operator_action_required"] is True
        assert entry["live_validated"] is False
        assert entry["downstream_evidence_ref"]


def test_deployment_runbook_keeps_advisory_boundary_and_no_live_cluster_commands() -> None:
    section = _fixture()["deployment_runbook"]
    doc = (ROOT / section["doc_path"]).read_text(encoding="utf-8")
    lower = doc.lower()

    assert section["advisory_boundary"] is True
    assert section["runtime_enforced"] is False
    assert section["live_validated"] is False
    assert "advisory boundary" in lower
    assert "runtime_enforced: false" in doc
    assert "live_validated: false" in doc
    assert "no live cross-tenant attack test has run" in lower
    for command in ("helm install", "helm upgrade", "kubectl apply"):
        assert command not in doc, f"deployment runbook must not embed live cluster command: {command}"


def test_config_recipe_covers_namespace_per_tenant_without_inline_secrets() -> None:
    section = _fixture()["config_recipe"]
    doc = (ROOT / section["doc_path"]).read_text(encoding="utf-8")
    tests = (ROOT / section["test_path"]).read_text(encoding="utf-8")
    lower = doc.lower()

    assert section["namespace_per_tenant"] is True
    assert section["dedicated_database_and_secret"] is True
    assert section["network_policy_default_deny"] is True
    assert section["resource_quota_operator_owned"] is True
    assert section["inline_secret_material_present"] is False
    assert "deployment-level isolation" in lower
    assert "dedicated postgresql" in lower
    assert "networkpolicy default-deny" in lower
    assert "resourcequota applied" in lower
    assert "secretname" in lower
    for slice_id in ("E-4-2a", "E-4-3", "E-4-4", "E-4-5"):
        assert slice_id in doc
    assert "test_recipe_overlay_uses_secretkeyref_not_inline" in tests


def test_helm_boundary_has_namespace_scope_secret_refs_and_no_chart_quota() -> None:
    section = _fixture()["helm_boundary"]
    chart_root = ROOT / section["chart_root"]
    values = (ROOT / section["values_path"]).read_text(encoding="utf-8")
    rbac = (chart_root / "templates" / "rbac.yaml").read_text(encoding="utf-8")
    deployment = (chart_root / "templates" / "deployment.yaml").read_text(encoding="utf-8")

    assert section["namespace_scoped_rbac"] is True
    assert section["cluster_scoped_rbac_present"] is False
    assert section["secret_key_ref_only"] is True
    assert section["network_policy_template_present"] is True
    assert section["pod_resources_present"] is True
    assert section["resourcequota_rendered_by_chart"] is False
    assert "kind: Role" in rbac
    assert "kind: RoleBinding" in rbac
    assert "kind: ClusterRole" not in rbac
    assert "kind: ClusterRoleBinding" not in rbac
    assert "secretKeyRef" in deployment
    assert "resources:" in values
    assert (chart_root / "templates" / "networkpolicy.yaml").is_file()
    assert (chart_root / "templates" / "servicemonitor.yaml").is_file()
    assert not list(chart_root.glob("templates/*resourcequota*"))


def test_rate_limit_preflight_records_per_tenant_bucket_isolation_only() -> None:
    section = _fixture()["rate_limit"]
    doc = (ROOT / section["doc_path"]).read_text(encoding="utf-8")
    tests = (ROOT / section["test_path"]).read_text(encoding="utf-8")

    assert section["per_tenant_key_pattern"] is True
    assert section["bucket_isolation_tested"] is True
    assert section["live_adapter_execution"] is False
    assert '"<tenant>:<provider>"' in doc or "{tenant_id}:{provider_id}" in doc
    assert "test_per_tenant_key_isolates_buckets" in tests
    assert "live adapter execution" in doc.lower()
    assert "const false" in doc.lower()


def test_matrix_refs_multi_tenancy_bundle_but_keeps_dimension_partial() -> None:
    matrix = _matrix_fixture()
    dimension = _dimension(matrix, "multi_tenancy_isolation")

    assert dimension["status"] == "partial"
    assert ".claude/plans/V5-MULTI-TENANCY-ISOLATION-PREFLIGHT-BUNDLE.md" in dimension["current_evidence_refs"]
    assert "tests/fixtures/epic9/v5-multi-tenancy-isolation-preflight.current.json" in dimension["current_evidence_refs"]
    assert "docs/MULTI-TENANT-DEPLOYMENT.md" in dimension["current_evidence_refs"]
    assert "docs/MULTI-TENANT-CONFIG-RECIPE.md" in dimension["current_evidence_refs"]
    assert "docs/RATE-LIMIT-TUNING.md" in dimension["current_evidence_refs"]
    assert ".claude/plans/tenant_isolation_matrix.v1.json" in dimension["current_evidence_refs"]
    assert "live cluster CNI/RBAC/NetworkPolicy validation evidence" in dimension["missing_evidence"]
    assert "cross-tenant leak prevention or attack-test evidence" in dimension["missing_evidence"]
    assert "per-tenant live cost/quota dashboard evidence" in dimension["missing_evidence"]
    assert matrix["matrix_complete"] is False
    assert matrix["pr_xfinal_open_allowed"] is False
    assert matrix["support_widening"] is False
    assert matrix["production_platform_claim"] is False
    assert matrix["live_adapter_execution"] is False


def test_bundle_doc_has_cross_refs_without_positive_claim_tokens() -> None:
    text = BUNDLE_DOC_PATH.read_text(encoding="utf-8")
    matrix_doc = MATRIX_DOC_PATH.read_text(encoding="utf-8")

    assert "V5 Multi-Tenancy Isolation Preflight Bundle" in text
    assert "runtime_enforced=false" in text
    assert "live_validated=false" in text
    assert "tenant_isolation_ready=false" in text
    assert "V5-MULTI-TENANCY-ISOLATION-PREFLIGHT-BUNDLE.md" in matrix_doc
    assert "v5-multi-tenancy-isolation-preflight.current.json" in matrix_doc

    forbidden = (
        "production-ready",
        "production ready",
        "support_widening=true",
        "production_platform_claim=true",
        "live_adapter_execution=true",
        "runtime_enforced=true",
        "live_validated=true",
        "tenant_isolation_ready=true",
        "matrix_complete=true",
        "pr_xfinal_open_allowed=true",
    )
    lowered = text.lower()
    for token in forbidden:
        assert token not in lowered, f"bundle doc must not include positive claim token: {token}"


def test_residual_missing_evidence_keeps_live_tenant_work_explicit() -> None:
    assert _fixture()["residual_missing_evidence"] == [
        "live cluster CNI/RBAC/NetworkPolicy validation evidence",
        "cross-tenant leak prevention or attack-test evidence",
        "operator-applied ResourceQuota and LimitRange evidence",
        "per-tenant live cost/quota dashboard evidence",
        "operator-attested tenant isolation review bound to final release artifact",
    ]
