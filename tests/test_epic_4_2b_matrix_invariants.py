"""V5 Epic 4 E-4-2b final multi-tenant matrix seal invariants."""

from __future__ import annotations

import json
import re
from copy import deepcopy
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

_REPO_ROOT = Path(__file__).resolve().parent.parent
_DOC_PATH = _REPO_ROOT / "docs" / "MULTI-TENANT-DEPLOYMENT.md"
_MATRIX_PATH = _REPO_ROOT / ".claude" / "plans" / "tenant_isolation_matrix.v1.json"
_EVIDENCE_PATH = _REPO_ROOT / ".claude" / "plans" / "E-4-2b-MULTI-TENANT-FINAL-SEAL.v1.json"
_BASE_MATRIX_SCHEMA_PATH = _REPO_ROOT / "ao_kernel" / "defaults" / "schemas" / "tenant-isolation-matrix.schema.v1.json"
_FINAL_MATRIX_SCHEMA_PATH = (
    _REPO_ROOT / "ao_kernel" / "defaults" / "schemas" / "e-4-2b-tenant-isolation-matrix.schema.v1.json"
)
_EVIDENCE_SCHEMA_PATH = (
    _REPO_ROOT / "ao_kernel" / "defaults" / "schemas" / "e-4-2b-multi-tenant-final-seal-evidence.schema.v1.json"
)

_EXPECTED_DIMENSIONS = {
    "namespace_isolation",
    "rbac_scope",
    "secret_isolation",
    "network_policy",
    "resource_quota",
    "audit_boundary",
    "cost_tracking_advisory",
}

_REQUIRED_DOWNSTREAM_SUBSTRINGS = ("E-4-3", "E-4-4", "E-4-5")
_REQUIRED_PROVIDER_PARTICIPANTS = {"anthropic", "openai", "minimax"}
_REQUIRED_INDEPENDENT_REVIEWERS = {"anthropic", "minimax"}
_EXPECTED_DOWNSTREAM_REFS = {
    "namespace_isolation": ".claude/plans/E-4-1-HELM-CHART-SKELETON.v1.json",
    "rbac_scope": ".claude/plans/E-4-1-HELM-CHART-SKELETON.v1.json",
    "secret_isolation": ".claude/plans/E-4-3-POSTGRES-PROVISIONING.md",
    "network_policy": ".claude/plans/E-4-5-NETWORKPOLICY-PSS.md",
    "resource_quota": "deploy/helm/ao-kernel/values.yaml",
    "audit_boundary": ".claude/plans/E-4-4-OBSERVABILITY-SURFACE.md",
    "cost_tracking_advisory": ".claude/plans/E-4-4-OBSERVABILITY-SURFACE.md",
}
_OVERCLAIM_PHRASES = (
    "isolation achieved",
    "isolation enforced",
    "fully isolated",
    "runtime enforces",
    "isolation guaranteed",
    "isolation proven",
    "strict isolation",
)


def _load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(data, dict), f"expected object at {path}; got {type(data).__name__}"
    return data


def _schema_errors(schema_path: Path, data_path: Path) -> list[str]:
    schema = _load_json(schema_path)
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema)
    data = _load_json(data_path)
    return [f"{list(error.path)} -> {error.message}" for error in sorted(validator.iter_errors(data), key=lambda e: list(e.path))]


def test_matrix_is_final_seal_with_exact_seven_dimensions() -> None:
    matrix = _load_json(_MATRIX_PATH)
    assert matrix["matrix_status"] == "e_4_2b_final_seal"
    assert matrix["advisory_only"] is True
    assert matrix["runtime_enforced_global"] is False
    assert matrix["live_validated_global"] is False
    dimensions = matrix["dimensions"]
    assert len(dimensions) == 7
    assert {entry["dimension"] for entry in dimensions} == _EXPECTED_DIMENSIONS


def test_all_entries_are_filled_advisory_constants() -> None:
    matrix = _load_json(_MATRIX_PATH)
    for entry in matrix["dimensions"]:
        assert entry["entry_status"] == "filled", entry["dimension"]
        assert entry["runtime_enforced"] is False, entry["dimension"]
        assert entry["operator_enforceable"] is True, entry["dimension"]
        assert entry["operator_action_required"] is True, entry["dimension"]
        assert entry["live_validated"] is False, entry["dimension"]
        assert entry["downstream_evidence_ref"], entry["dimension"]


def test_downstream_refs_exist_and_cover_required_slices() -> None:
    matrix = _load_json(_MATRIX_PATH)
    refs_by_dimension = {entry["dimension"]: entry["downstream_evidence_ref"] for entry in matrix["dimensions"]}
    assert refs_by_dimension == _EXPECTED_DOWNSTREAM_REFS
    refs = list(refs_by_dimension.values())
    missing = [ref for ref in refs if not (_REPO_ROOT / ref).is_file()]
    assert missing == [], f"downstream_evidence_ref must point to existing repo files: {missing}"
    for substring in _REQUIRED_DOWNSTREAM_SUBSTRINGS:
        assert any(substring in ref for ref in refs), f"missing downstream ref containing {substring}"


def test_matrix_validates_against_base_and_final_schemas() -> None:
    base_errors = _schema_errors(_BASE_MATRIX_SCHEMA_PATH, _MATRIX_PATH)
    final_errors = _schema_errors(_FINAL_MATRIX_SCHEMA_PATH, _MATRIX_PATH)
    assert base_errors == [], "base matrix schema errors:\n" + "\n".join(base_errors)
    assert final_errors == [], "E-4-2b final matrix schema errors:\n" + "\n".join(final_errors)


def test_base_schema_rejects_mixed_lifecycle_states() -> None:
    schema = _load_json(_BASE_MATRIX_SCHEMA_PATH)
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema)
    matrix = _load_json(_MATRIX_PATH)

    final_with_null_ref = deepcopy(matrix)
    final_with_null_ref["dimensions"][0]["downstream_evidence_ref"] = None
    assert list(validator.iter_errors(final_with_null_ref)), "final seal with null downstream ref must be rejected"

    final_with_placeholder_entry = deepcopy(matrix)
    final_with_placeholder_entry["dimensions"][0]["entry_status"] = "placeholder"
    assert list(validator.iter_errors(final_with_placeholder_entry)), "final seal with placeholder entry must be rejected"

    placeholder_with_filled_entry = deepcopy(matrix)
    placeholder_with_filled_entry["matrix_status"] = "e_4_2a_contract_placeholder"
    placeholder_with_filled_entry["dimensions"][0]["entry_status"] = "filled"
    assert list(validator.iter_errors(placeholder_with_filled_entry)), "placeholder matrix with filled entry must be rejected"

    placeholder_with_string_ref = deepcopy(matrix)
    placeholder_with_string_ref["matrix_status"] = "e_4_2a_contract_placeholder"
    placeholder_with_string_ref["dimensions"][0]["entry_status"] = "placeholder"
    assert list(validator.iter_errors(placeholder_with_string_ref)), "placeholder matrix with string downstream ref must be rejected"


def test_evidence_validates_and_records_three_provider_review() -> None:
    errors = _schema_errors(_EVIDENCE_SCHEMA_PATH, _EVIDENCE_PATH)
    assert errors == [], "E-4-2b evidence schema errors:\n" + "\n".join(errors)
    evidence = _load_json(_EVIDENCE_PATH)
    assert set(evidence["provider_participants"]) == _REQUIRED_PROVIDER_PARTICIPANTS
    assert evidence["implementation_evidence"] == {
        "agent": "codex",
        "provider": "openai",
        "role": "implementer",
        "notes": evidence["implementation_evidence"]["notes"],
    }
    records = evidence["review_evidence"]
    assert {record["provider"] for record in records} == _REQUIRED_INDEPENDENT_REVIEWERS
    assert {record["verdict"] for record in records} == {"AGREE"}


def test_evidence_schema_rejects_unavailable_review_as_agree() -> None:
    schema = _load_json(_EVIDENCE_SCHEMA_PATH)
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema)
    evidence = _load_json(_EVIDENCE_PATH)
    mutated = deepcopy(evidence)
    mutated["review_evidence"][0]["evidence_kind"] = "unavailable_fail_closed"
    assert list(validator.iter_errors(mutated)), "unavailable review evidence must not validate as AGREE"


def test_deployment_doc_uses_final_seal_language_without_overclaim() -> None:
    text = _DOC_PATH.read_text(encoding="utf-8")
    assert "final seal" in text.lower()
    assert "E-4-2b" in text
    lower = text.lower()
    hits = []
    for phrase in _OVERCLAIM_PHRASES:
        if phrase in lower:
            hits.append(phrase)
    assert hits == [], f"deployment doc contains overclaim phrases: {hits}"
    assert len(re.findall(r"runtime_enforced:\s*false", text)) >= 3
    assert len(re.findall(r"live_validated:\s*false", text)) >= 3


def test_deployment_doc_does_not_embed_live_cluster_commands() -> None:
    text = _DOC_PATH.read_text(encoding="utf-8")
    forbidden = ("helm install", "helm upgrade", "kubectl apply")
    hits = [cmd for cmd in forbidden if cmd in text]
    assert hits == [], f"deployment doc must not embed live cluster commands: {hits}"
