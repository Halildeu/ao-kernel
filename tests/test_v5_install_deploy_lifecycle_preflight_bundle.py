"""V5 install/deploy lifecycle preflight bundle invariants.

The V5 production readiness matrix keeps the install/deploy lifecycle
dimension partial until a later operator-bound PR-Xfinal binds the evidence to
the actual v5.0.0 release artifact. This bundle records the current preflight
surface without authorizing a tag, publish, production claim, support widening,
or live adapter execution.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from ao_kernel.config import load_default


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_NAME = "v5-install-deploy-lifecycle-preflight-bundle.schema.v1.json"
SCHEMA_PATH = ROOT / "ao_kernel" / "defaults" / "schemas" / SCHEMA_NAME
FIXTURE_PATH = ROOT / "tests" / "fixtures" / "epic9" / "v5-install-deploy-lifecycle-preflight.current.json"
MATRIX_FIXTURE_PATH = ROOT / "tests" / "fixtures" / "epic9" / "v5-production-readiness-matrix.current.json"
MATRIX_DOC_PATH = ROOT / ".claude" / "plans" / "V5-PRODUCTION-READINESS-MATRIX-BLOCKER.md"
BUNDLE_DOC_PATH = ROOT / ".claude" / "plans" / "V5-INSTALL-DEPLOY-LIFECYCLE-PREFLIGHT-BUNDLE.md"


def _schema() -> dict[str, Any]:
    return load_default("schemas", SCHEMA_NAME)


def _fixture() -> dict[str, Any]:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def _matrix_fixture() -> dict[str, Any]:
    return json.loads(MATRIX_FIXTURE_PATH.read_text(encoding="utf-8"))


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
    assert schema["$id"] == "urn:ao:v5-install-deploy-lifecycle-preflight-bundle:v1"

    for node in _object_nodes(schema):
        assert node.get("additionalProperties") is False
        assert node.get("unevaluatedProperties") is False


def test_current_fixture_validates_and_pins_non_authority_boundary() -> None:
    payload = _fixture()
    assert _is_valid(payload)
    assert payload["schema_version"] == "v5_install_deploy_lifecycle_preflight_bundle.v1"
    assert payload["artifact_kind"] == "v5_install_deploy_lifecycle_preflight_bundle"
    assert payload["repo"] == "Halildeu/ao-kernel"
    assert payload["work_package"] == "E-9-1"
    assert payload["dimension"] == "install_deploy_lifecycle_smoke"
    assert payload["evidence_class"] == "preflight_current_state"
    assert payload["final_release_bound"] is False
    assert payload["support_widening"] is False
    assert payload["production_platform_claim"] is False
    assert payload["live_adapter_execution"] is False


def test_schema_rejects_final_release_or_guard_flag_flips() -> None:
    for field in (
        "final_release_bound",
        "support_widening",
        "production_platform_claim",
        "live_adapter_execution",
    ):
        payload = _fixture()
        payload[field] = True
        assert not _is_valid(payload), f"{field}=true must fail closed"


def test_schema_rejects_nested_release_artifact_claims() -> None:
    mutations: tuple[tuple[str, str], ...] = (
        ("standalone_install_smoke", "release_artifact_bound"),
        ("helm_lifecycle", "release_artifact_bound"),
        ("publish_lifecycle", "v5_tag_evidence_present"),
        ("publish_lifecycle", "v5_publish_evidence_present"),
        ("migration_guide", "release_shipped"),
    )
    for section, field in mutations:
        payload = _fixture()
        payload[section][field] = True
        assert not _is_valid(payload), f"{section}.{field}=true must fail closed"


def test_schema_rejects_path_or_extra_field_drift() -> None:
    payload = _fixture()
    payload["standalone_install_smoke"]["script_path"] = "scripts/other.py"
    assert not _is_valid(payload)

    payload = _fixture()
    payload["publish_lifecycle"]["trusted_publishing_environment"] = "prod"
    assert not _is_valid(payload)

    payload = _fixture()
    payload["unexpected"] = "not allowed"
    assert not _is_valid(payload)

    payload = _fixture()
    payload["operator_runbooks"]["unexpected"] = "not allowed"
    assert not _is_valid(payload)


def test_all_referenced_artifacts_exist() -> None:
    payload = _fixture()
    path_sections = (
        "standalone_install_smoke",
        "deployment_guide",
        "operator_runbooks",
        "helm_lifecycle",
        "publish_lifecycle",
        "migration_guide",
    )
    for section_name in path_sections:
        section = payload[section_name]
        for key, value in section.items():
            if key.endswith("_path"):
                assert (ROOT / value).exists(), f"{section_name}.{key} missing: {value}"


def test_standalone_install_smoke_surface_is_current_state_only() -> None:
    payload = _fixture()
    section = payload["standalone_install_smoke"]
    workflow = (ROOT / section["ci_workflow_path"]).read_text(encoding="utf-8")
    smoke_script = (ROOT / section["script_path"]).read_text(encoding="utf-8")
    ri7_test = (ROOT / section["ri7_packaging_smoke_test_path"]).read_text(encoding="utf-8")

    assert section["wheel_installed_smoke_present"] is True
    assert section["release_artifact_bound"] is False
    assert section["dist_cleanup_required"] is True
    assert "packaging-smoke:" in workflow
    assert "python scripts/packaging_smoke.py" in workflow
    assert "_smoke_repo_intelligence_cli" in smoke_script
    assert "ri7_scan_index_query_packaging_smoke_ready" in ri7_test


def test_deployment_guide_and_operator_runbooks_keep_claim_discipline() -> None:
    payload = _fixture()
    deployment = payload["deployment_guide"]
    guide = (ROOT / deployment["doc_path"]).read_text(encoding="utf-8")
    guide_tests = (ROOT / deployment["test_path"]).read_text(encoding="utf-8")

    assert deployment["standalone_pattern"] is True
    assert deployment["docker_pattern"] is True
    assert deployment["kubernetes_pattern"] is True
    assert deployment["operator_bound_supersession_required"] is True
    assert deployment["guard_flags_const_false_documented"] is True
    assert "Standalone" in guide
    assert "Docker" in guide
    assert "Kubernetes" in guide
    assert "operator-bound supersession" in guide
    assert "test_guide_covers_standalone_pattern" in guide_tests
    assert "test_guide_three_guard_flags_const_false_disclaimer" in guide_tests

    runbooks = payload["operator_runbooks"]
    runbook = (ROOT / runbooks["operator_runbook_path"]).read_text(encoding="utf-8")
    action_readme = (ROOT / runbooks["operator_action_readme_path"]).read_text(encoding="utf-8")
    action_tests = (ROOT / runbooks["operator_action_checklist_test_path"]).read_text(encoding="utf-8")

    assert runbooks["operator_action_required"] is True
    assert runbooks["agent_executed_external_action"] is False
    for token in ("rollback", "tag revert", "pause", "emergency stop", "incident triage"):
        assert token in runbook
    assert "operator-action-checklist.v1.json" in action_readme
    assert "agent_executed_external_action" in action_tests
    assert "operator_action_required" in action_tests


def test_helm_lifecycle_surface_is_operator_run_and_not_release_bound() -> None:
    payload = _fixture()
    section = payload["helm_lifecycle"]
    deployment_test = (ROOT / section["helm_unittest_suite_path"]).read_text(encoding="utf-8")
    helm_doc = (ROOT / section["helm_testing_runbook_path"]).read_text(encoding="utf-8")
    template = (ROOT / section["deployment_template_path"]).read_text(encoding="utf-8")

    assert section["default_safe_single_replica"] is True
    assert section["non_root_security_context_pinned"] is True
    assert section["operator_run_plugin_smoke_only"] is True
    assert section["release_artifact_bound"] is False
    assert "renders a single Deployment with replicas >= 1" in deployment_test
    assert "runAsNonRoot" in deployment_test
    assert "AO_KERNEL_DB_PASSWORD" in deployment_test
    assert "readOnlyRootFilesystem: true" in template
    assert "operator-run" in helm_doc
    assert "Does NOT flip any guard flag" in helm_doc


def test_publish_lifecycle_has_strict_dist_and_trusted_publishing_guards() -> None:
    payload = _fixture()
    section = payload["publish_lifecycle"]
    workflow = (ROOT / section["workflow_path"]).read_text(encoding="utf-8")
    workflow_tests = (ROOT / section["workflow_test_path"]).read_text(encoding="utf-8")
    runbook = (ROOT / section["operator_runbook_path"]).read_text(encoding="utf-8")

    assert section["trusted_publishing_environment"] == "pypi"
    assert section["workflow_dispatch_ref_required"] is True
    assert section["v_tag_guard_present"] is True
    assert section["strict_dist_globs"] is True
    assert section["v5_tag_evidence_present"] is False
    assert section["v5_publish_evidence_present"] is False
    assert "environment: pypi" in workflow
    assert "id-token: write" in workflow
    assert "workflow_dispatch:" in workflow
    assert "required: true" in workflow
    assert 'tags: ["v*"]' in workflow
    assert "twine check dist/*.whl dist/*.tar.gz" in workflow
    assert "python scripts/packaging_smoke.py" in workflow
    assert "test_publish_workflow_dispatch_ref_is_required_and_v_tag_guarded" in workflow_tests
    assert "test_publish_workflow_twine_args_are_strict_whitelist" in workflow_tests
    assert "operator" in runbook.lower()


def test_migration_guide_is_planned_and_keeps_downgrade_pin() -> None:
    payload = _fixture()
    section = payload["migration_guide"]
    guide = (ROOT / section["doc_path"]).read_text(encoding="utf-8")
    tests = (ROOT / section["test_path"]).read_text(encoding="utf-8")

    assert section["target_version"] == "5.0.0"
    assert section["downgrade_pin"] == "ao-kernel==4.1.0"
    assert section["guard_flags_const_false_documented"] is True
    assert section["release_shipped"] is False
    assert "v5.0.0 is not yet released" in guide
    assert "pip install ao-kernel==4.1.0" in guide
    assert "support_widening" in guide
    assert "production_platform_claim" in guide
    assert "live_adapter_execution" in guide
    assert "test_migration_v5_downgrade_path_pinned" in tests
    assert "test_migration_v5_guard_flag_constant_false_pinned" in tests


def test_residual_missing_evidence_pins_release_artifact_gap() -> None:
    residual = _fixture()["residual_missing_evidence"]
    expected = {
        "v5.0.0 tag evidence",
        "PyPI publish evidence for the v5.0.0 release artifact",
        "final standalone install smoke against that release artifact",
        "final Docker or container image smoke bound to that release artifact",
        "final Kubernetes/Helm deploy lifecycle smoke bound to the promoted artifact",
        "rollback and downgrade smoke from the promoted artifact back to the supported baseline",
    }
    assert set(residual) == expected


def test_matrix_dimension_references_bundle_but_remains_partial() -> None:
    matrix = _matrix_fixture()
    dimension = _dimension(matrix, "install_deploy_lifecycle_smoke")
    refs = set(dimension["current_evidence_refs"])
    missing = set(dimension["missing_evidence"])

    assert matrix["matrix_complete"] is False
    assert matrix["support_widening"] is False
    assert matrix["production_platform_claim"] is False
    assert matrix["live_adapter_execution"] is False
    assert dimension["status"] == "partial"
    assert ".claude/plans/V5-INSTALL-DEPLOY-LIFECYCLE-PREFLIGHT-BUNDLE.md" in refs
    assert "tests/fixtures/epic9/v5-install-deploy-lifecycle-preflight.current.json" in refs
    assert "v5.0.0 tag and publish evidence" in missing
    assert "final install and deployment lifecycle smoke bound to release artifact" in missing


def test_docs_reference_bundle_without_positive_claim_tokens() -> None:
    bundle_doc = BUNDLE_DOC_PATH.read_text(encoding="utf-8")
    matrix_doc = MATRIX_DOC_PATH.read_text(encoding="utf-8")
    lower = (bundle_doc + "\n" + matrix_doc).lower()

    assert "v5-install-deploy-lifecycle-preflight-bundle.schema.v1.json" in bundle_doc
    assert "v5-install-deploy-lifecycle-preflight.current.json" in bundle_doc
    assert "install/deploy lifecycle preflight bundle" in matrix_doc
    for token in (
        "production-ready",
        "production ready",
        "support_widening=true",
        "production_platform_claim=true",
        "live_adapter_execution=true",
        "final_release_bound=true",
        "matrix_complete=true",
    ):
        assert token not in lower, f"positive claim token found: {token}"


def test_fixture_copy_is_not_mutated_by_validation_helper() -> None:
    payload = _fixture()
    before = copy.deepcopy(payload)
    assert _is_valid(payload)
    assert payload == before
