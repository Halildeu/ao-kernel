"""V5 docs/runbooks preflight bundle invariants.

The V5 production readiness matrix keeps the docs/runbooks dimension partial
until a later operator-bound PR-Xfinal synchronizes final claim language,
release notes, and final runbook updates. This bundle records the current
preflight surface without authorizing support widening, production platform
claims, live adapter execution, hosted docs publication, or final v5.0.0
release wording.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from ao_kernel.config import load_default


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_NAME = "v5-docs-runbooks-preflight-bundle.schema.v1.json"
SCHEMA_PATH = ROOT / "ao_kernel" / "defaults" / "schemas" / SCHEMA_NAME
FIXTURE_PATH = ROOT / "tests" / "fixtures" / "epic9" / "v5-docs-runbooks-preflight.current.json"
MATRIX_FIXTURE_PATH = ROOT / "tests" / "fixtures" / "epic9" / "v5-production-readiness-matrix.current.json"
MATRIX_DOC_PATH = ROOT / ".claude" / "plans" / "V5-PRODUCTION-READINESS-MATRIX-BLOCKER.md"
BUNDLE_DOC_PATH = ROOT / ".claude" / "plans" / "V5-DOCS-RUNBOOKS-PREFLIGHT-BUNDLE.md"


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
    assert schema["$id"] == "urn:ao:v5-docs-runbooks-preflight-bundle:v1"

    for node in _object_nodes(schema):
        assert node.get("additionalProperties") is False
        assert node.get("unevaluatedProperties") is False


def test_current_fixture_validates_and_pins_non_authority_boundary() -> None:
    payload = _fixture()
    assert _is_valid(payload)
    assert payload["schema_version"] == "v5_docs_runbooks_preflight_bundle.v1"
    assert payload["artifact_kind"] == "v5_docs_runbooks_preflight_bundle"
    assert payload["repo"] == "Halildeu/ao-kernel"
    assert payload["work_package"] == "E-9-1"
    assert payload["dimension"] == "docs_runbooks"
    assert payload["evidence_class"] == "preflight_current_state"
    assert payload["final_claim_language_synced"] is False
    assert payload["final_release_notes_present"] is False
    assert payload["v5_runbook_finalized"] is False
    assert payload["support_widening"] is False
    assert payload["production_platform_claim"] is False
    assert payload["live_adapter_execution"] is False


def test_schema_rejects_claim_release_or_guard_flag_flips() -> None:
    for field in (
        "final_claim_language_synced",
        "final_release_notes_present",
        "v5_runbook_finalized",
        "support_widening",
        "production_platform_claim",
        "live_adapter_execution",
    ):
        payload = _fixture()
        payload[field] = True
        assert not _is_valid(payload), f"{field}=true must fail closed"


def test_schema_rejects_nested_authority_or_publication_claims() -> None:
    mutations: tuple[tuple[str, str], ...] = (
        ("operator_action_runbooks", "agent_executed_external_action"),
        ("operator_action_runbooks", "credential_material_committed"),
        ("api_reference", "hosted_docs_published"),
        ("migration_guide", "release_shipped"),
        ("incident_response", "is_contractual_sla"),
    )
    for section, field in mutations:
        payload = _fixture()
        payload[section][field] = True
        assert not _is_valid(payload), f"{section}.{field}=true must fail closed"


def test_schema_rejects_path_or_extra_field_drift() -> None:
    payload = _fixture()
    payload["api_reference"]["readme_path"] = "docs/api/other.md"
    assert not _is_valid(payload)

    payload = _fixture()
    payload["rollback_procedure"]["runbook_path"] = "docs/ROLLBACK.md"
    assert not _is_valid(payload)

    payload = _fixture()
    payload["unexpected"] = "not allowed"
    assert not _is_valid(payload)

    payload = _fixture()
    payload["incident_response"]["unexpected"] = "not allowed"
    assert not _is_valid(payload)


def test_all_referenced_artifacts_exist() -> None:
    payload = _fixture()
    path_sections = (
        "deployment_guide",
        "operator_runbook",
        "operator_action_runbooks",
        "rollback_procedure",
        "api_reference",
        "migration_guide",
        "incident_response",
        "vendor_escalation",
    )
    for section_name in path_sections:
        section = payload[section_name]
        for key, value in section.items():
            if key.endswith("_path"):
                assert (ROOT / value).exists(), f"{section_name}.{key} missing: {value}"


def test_deployment_and_operator_docs_cover_required_surfaces() -> None:
    payload = _fixture()
    deployment = payload["deployment_guide"]
    guide = (ROOT / deployment["doc_path"]).read_text(encoding="utf-8")
    guide_tests = (ROOT / deployment["test_path"]).read_text(encoding="utf-8")

    assert deployment["standalone_pattern"] is True
    assert deployment["docker_pattern"] is True
    assert deployment["kubernetes_pattern"] is True
    assert deployment["operator_bound_supersession_required"] is True
    assert "Standalone" in guide
    assert "Docker" in guide
    assert "Kubernetes" in guide
    assert "operator-bound supersession" in guide
    assert "test_guide_covers_standalone_pattern" in guide_tests
    assert "test_guide_three_guard_flags_const_false_disclaimer" in guide_tests

    runbook = payload["operator_runbook"]
    text = (ROOT / runbook["doc_path"]).read_text(encoding="utf-8")
    tests = (ROOT / runbook["test_path"]).read_text(encoding="utf-8")

    for token in ("Rollback", "Tag Revert", "Pause", "Emergency Stop", "Incident Triage"):
        assert token in text
    for test_name in (
        "test_runbook_covers_rollback_scenario",
        "test_runbook_covers_tag_revert_scenario",
        "test_runbook_covers_pause_scenario",
        "test_runbook_covers_emergency_stop_scenario",
        "test_runbook_covers_incident_triage_tree",
    ):
        assert test_name in tests


def test_operator_action_runbooks_keep_operator_and_credential_boundary() -> None:
    payload = _fixture()
    section = payload["operator_action_runbooks"]
    readme = (ROOT / section["readme_path"]).read_text(encoding="utf-8")
    checklist = json.loads((ROOT / section["checklist_path"]).read_text(encoding="utf-8"))
    tests = (ROOT / section["test_path"]).read_text(encoding="utf-8")

    assert section["operator_action_required"] is True
    assert section["agent_executed_external_action"] is False
    assert section["credential_material_committed"] is False
    assert "operator-action-checklist.v1.json" in readme
    assert "operator-action-checklist.schema.v1.json" in readme
    assert checklist["runbook_disclaimer"]["operator_action_required"] is True
    assert checklist["runbook_disclaimer"]["no_credential_committed"] is True
    assert "test_schema_rejects_agent_executed_external_action_true" in tests
    assert "test_schema_rejects_credential_material_committed_true" in tests


def test_rollback_procedure_records_recovery_discipline() -> None:
    payload = _fixture()
    section = payload["rollback_procedure"]
    runbook = (ROOT / section["runbook_path"]).read_text(encoding="utf-8")
    package_doc = (ROOT / section["package_rollback_doc_path"]).read_text(encoding="utf-8")

    assert section["archive_tag_preservation"] is True
    assert section["no_destructive_history_rewrite"] is True
    assert section["operator_ruleset_authority"] is True
    assert section["forward_fix_or_revert_pr_required"] is True
    assert "No destructive history rewrite" in runbook
    assert "Archive tag preservation" in runbook
    assert "Operator authority is preserved" in runbook
    assert "Forward fix" in runbook
    assert "Package-level rollback" in package_doc
    assert "Release rollback rule" in package_doc


def test_api_reference_scaffold_is_opt_in_and_excludes_live_provider_surfaces() -> None:
    payload = _fixture()
    section = payload["api_reference"]
    readme = (ROOT / section["readme_path"]).read_text(encoding="utf-8")
    conf = (ROOT / section["conf_path"]).read_text(encoding="utf-8")
    index = (ROOT / section["index_path"]).read_text(encoding="utf-8")
    tests = (ROOT / section["test_path"]).read_text(encoding="utf-8")

    assert section["sphinx_scaffold_present"] is True
    assert section["operator_invoked_build"] is True
    assert section["hosted_docs_published"] is False
    assert section["live_provider_surfaces_excluded"] is True
    assert "sphinx-build -b html docs/api docs/api/_build/html" in readme
    assert "Hosted-docs URL + GitHub Pages publication is a separate operator" in readme
    assert "Live provider client surfaces" in readme
    assert "sphinx.ext.autodoc" in conf
    assert "sphinx.ext.napoleon" in conf
    assert "_internal" in index
    assert "test_docs_extra_does_not_include_live_providers" in tests


def test_migration_and_incident_docs_keep_release_and_sla_boundaries() -> None:
    payload = _fixture()
    migration = payload["migration_guide"]
    migration_doc = (ROOT / migration["doc_path"]).read_text(encoding="utf-8")
    migration_tests = (ROOT / migration["test_path"]).read_text(encoding="utf-8")

    assert migration["target_version"] == "5.0.0"
    assert migration["downgrade_pin"] == "ao-kernel==4.1.0"
    assert migration["release_shipped"] is False
    assert "v5.0.0 is not yet released" in migration_doc
    assert "pip install ao-kernel==4.1.0" in migration_doc
    assert "test_migration_v5_conservative_public_claim" in migration_tests
    assert "test_migration_v5_downgrade_path_pinned" in migration_tests

    incident = payload["incident_response"]
    incident_readme = (ROOT / incident["readme_path"]).read_text(encoding="utf-8")
    incident_tests = (ROOT / incident["test_path"]).read_text(encoding="utf-8")

    assert incident["operator_owned"] is True
    assert incident["is_contractual_sla"] is False
    assert incident["no_live_dispatch"] is True
    assert "Not SLA" in incident_readme
    assert "Not a production platform claim" in incident_readme
    assert "no live PagerDuty/Opsgenie integration" in incident_readme
    assert "test_schema_rejects_is_contractual_sla_true" in incident_tests
    assert "test_readme_regulatory_and_vendor_boundary_sections" in incident_tests


def test_vendor_escalation_keeps_external_handoff_boundary() -> None:
    payload = _fixture()
    section = payload["vendor_escalation"]
    matrix = json.loads((ROOT / section["matrix_path"]).read_text(encoding="utf-8"))
    runbook = (ROOT / section["runbook_path"]).read_text(encoding="utf-8").lower()
    tests = (ROOT / section["test_path"]).read_text(encoding="utf-8")

    assert section["operator_owned_external_handoff"] is True
    assert section["no_vendor_sla_promise"] is True
    assert section["account_manager_contact_operator_provisioned"] is True
    assert section["no_pii_in_repo"] is True
    assert matrix["matrix_disclaimer"]["operator_owned_external_handoff"] is True
    assert matrix["matrix_disclaimer"]["no_vendor_sla_promise"] is True
    assert matrix["matrix_disclaimer"]["no_pii_in_repo"] is True
    assert "no vendor sla promise" in runbook or "do not promise vendor sla" in runbook
    assert "test_all_account_manager_contacts_operator_provisioned" in tests
    assert "test_no_personal_email_committed" in tests


def test_matrix_refs_docs_runbooks_bundle_but_keeps_dimension_partial() -> None:
    matrix = _matrix_fixture()
    dimension = _dimension(matrix, "docs_runbooks")

    assert dimension["status"] == "partial"
    assert ".claude/plans/V5-DOCS-RUNBOOKS-PREFLIGHT-BUNDLE.md" in dimension["current_evidence_refs"]
    assert "tests/fixtures/epic9/v5-docs-runbooks-preflight.current.json" in dimension["current_evidence_refs"]
    assert "docs/PRODUCTION-DEPLOYMENT-GUIDE.md" in dimension["current_evidence_refs"]
    assert "docs/ROLLBACK-RUNBOOK.md" in dimension["current_evidence_refs"]
    assert "docs/incident-response/README.md" in dimension["current_evidence_refs"]
    assert "final PR-Xfinal claim language sync" in dimension["missing_evidence"]
    assert "final release notes and v5.0.0 runbook update" in dimension["missing_evidence"]
    assert matrix["matrix_complete"] is False
    assert matrix["pr_xfinal_open_allowed"] is False
    assert matrix["support_widening"] is False
    assert matrix["production_platform_claim"] is False
    assert matrix["live_adapter_execution"] is False


def test_bundle_doc_has_cross_refs_without_positive_claim_tokens() -> None:
    text = BUNDLE_DOC_PATH.read_text(encoding="utf-8")
    matrix_doc = MATRIX_DOC_PATH.read_text(encoding="utf-8")

    assert "V5 Docs and Runbooks Preflight Bundle" in text
    assert "final_claim_language_synced=false" in text
    assert "final_release_notes_present=false" in text
    assert "v5_runbook_finalized=false" in text
    assert "V5-DOCS-RUNBOOKS-PREFLIGHT-BUNDLE.md" in matrix_doc
    assert "v5-docs-runbooks-preflight.current.json" in matrix_doc

    forbidden = (
        "production-ready",
        "production ready",
        "support_widening=true",
        "production_platform_claim=true",
        "live_adapter_execution=true",
        "final_claim_language_synced=true",
        "final_release_notes_present=true",
        "v5_runbook_finalized=true",
        "hosted_docs_published=true",
    )
    lowered = text.lower()
    for token in forbidden:
        assert token not in lowered, f"bundle doc must not include positive claim token: {token}"


def test_residual_missing_evidence_keeps_final_docs_work_explicit() -> None:
    missing = _fixture()["residual_missing_evidence"]
    assert missing == [
        "final v5.0.0 release notes",
        "final PR-Xfinal claim language sync",
        "final v5.0.0 runbook update",
        "hosted API docs publication decision",
        "operator-attested final docs review",
    ]
