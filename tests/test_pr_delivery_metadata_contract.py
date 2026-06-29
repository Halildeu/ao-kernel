"""PR delivery metadata contract tests.

These tests pin the adapted delivery ceremony from platform-k8s-gitops without
changing ao-kernel release authority. The actual release authority remains
ao-release-gate plus GitHub branch protection.
"""

from __future__ import annotations

import json
from pathlib import Path

from jsonschema import Draft202012Validator

from ao_kernel.pr_metadata import (
    extract_pr_delivery_metadata_block,
    validate_pr_delivery_metadata_markdown,
)


ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / ".github" / "PULL_REQUEST_TEMPLATE.md"
RUNBOOK = ROOT / "docs" / "operator-runbooks" / "06-pr-delivery-metadata.md"
SCHEMA = ROOT / "ao_kernel" / "defaults" / "schemas" / "pr-delivery-metadata.schema.v1.json"


def _load_schema() -> dict:
    return json.loads(SCHEMA.read_text(encoding="utf-8"))


def test_pr_delivery_metadata_schema_is_meta_valid() -> None:
    schema = _load_schema()
    Draft202012Validator.check_schema(schema)
    assert schema["$id"] == "urn:ao:pr-delivery-metadata:v1"


def test_pr_template_exposes_delivery_metadata_fields() -> None:
    text = TEMPLATE.read_text(encoding="utf-8")
    required = [
        "## Delivery metadata",
        "```json pr-delivery-metadata",
        '"issue"',
        '"tracked_by"',
        '"work_package"',
        '"risk_class"',
        '"release_authority_impact"',
        '"critical_fix"',
        "## Boundary declaration",
        "credential-read",
        "credential-write",
        "state-mutation (test/sandbox)",
        "state-mutation (production)",
        "boundary-cross",
        "user-communication",
        "none of the above",
        "## Cross-AI review evidence",
        '"implementer_provider"',
        '"reviewer_providers"',
        '"review_artifacts"',
        '"verdict"',
        '"same_provider_exception"',
    ]
    for item in required:
        assert item in text, f"missing PR template contract field: {item}"


def test_pr_template_preserves_release_authority_boundary() -> None:
    text = TEMPLATE.read_text(encoding="utf-8")
    assert "AI review is evidence only" in text
    assert "Release authority remains `ao-release-gate` plus" in text
    assert "No support widening, production-platform claim, live-adapter execution" in text
    assert "admin merge" in text


def test_pr_template_metadata_block_validates_against_bundled_schema() -> None:
    text = TEMPLATE.read_text(encoding="utf-8")
    block = extract_pr_delivery_metadata_block(text)
    assert block is not None
    payload = json.loads(block)
    schema = _load_schema()
    errors = list(Draft202012Validator(schema).iter_errors(payload))
    assert errors == [], [error.message for error in errors]


def test_pr_template_metadata_block_validates_with_product_helper() -> None:
    text = TEMPLATE.read_text(encoding="utf-8")
    result = validate_pr_delivery_metadata_markdown(text)
    assert result.valid is True
    assert result.finding_code == "pr_delivery_metadata_ok"
    assert result.risk_class == "normal"


def test_schema_validates_minimal_low_risk_metadata() -> None:
    schema = _load_schema()
    payload = {
        "issue": "#1001",
        "tracked_by": "N/A",
        "work_package": "AO-MA-delivery-metadata",
        "risk_class": "low",
        "release_authority_impact": "ao-release-gate-input-only",
        "critical_fix": False,
        "boundary_declaration": {
            "credential_read": False,
            "credential_write": False,
            "state_mutation_test": False,
            "state_mutation_production": False,
            "boundary_cross": False,
            "user_communication": False,
            "none_of_the_above": True,
            "user_approval_evidence": "N/A",
        },
        "cross_ai_review": {
            "implementer_provider": "openai",
            "reviewer_providers": ["anthropic"],
            "review_artifacts": ["https://github.com/Halildeu/ao-kernel/pull/1001#issuecomment-1"],
            "verdict": "AGREE",
            "same_provider_exception": "N/A",
        },
    }
    errors = list(Draft202012Validator(schema).iter_errors(payload))
    assert errors == [], [error.message for error in errors]


def test_schema_rejects_none_boundary_with_other_boundary_selected() -> None:
    schema = _load_schema()
    payload = {
        "issue": "#1001",
        "tracked_by": "N/A",
        "work_package": "AO-MA-delivery-metadata",
        "risk_class": "normal",
        "release_authority_impact": "none",
        "critical_fix": False,
        "boundary_declaration": {
            "credential_read": True,
            "credential_write": False,
            "state_mutation_test": False,
            "state_mutation_production": False,
            "boundary_cross": False,
            "user_communication": False,
            "none_of_the_above": True,
            "user_approval_evidence": "N/A",
        },
        "cross_ai_review": {
            "implementer_provider": "openai",
            "reviewer_providers": ["anthropic"],
            "review_artifacts": ["https://github.com/Halildeu/ao-kernel/pull/1001#issuecomment-1"],
            "verdict": "AGREE",
            "same_provider_exception": "N/A",
        },
    }
    errors = list(Draft202012Validator(schema).iter_errors(payload))
    assert errors, "credential_read with none_of_the_above must fail closed"


def test_schema_rejects_empty_boundary_declaration() -> None:
    schema = _load_schema()
    payload = {
        "issue": "#1001",
        "tracked_by": "N/A",
        "work_package": "AO-MA-delivery-metadata",
        "risk_class": "normal",
        "release_authority_impact": "none",
        "critical_fix": False,
        "boundary_declaration": {
            "credential_read": False,
            "credential_write": False,
            "state_mutation_test": False,
            "state_mutation_production": False,
            "boundary_cross": False,
            "user_communication": False,
            "none_of_the_above": False,
            "user_approval_evidence": "N/A",
        },
        "cross_ai_review": {
            "implementer_provider": "openai",
            "reviewer_providers": [],
            "review_artifacts": [],
            "verdict": "N/A",
            "same_provider_exception": "N/A",
        },
    }
    errors = list(Draft202012Validator(schema).iter_errors(payload))
    assert errors, "boundary declaration must select a real boundary or none_of_the_above"


def test_schema_rejects_sensitive_boundary_without_approval_evidence() -> None:
    schema = _load_schema()
    payload = {
        "issue": "#1001",
        "tracked_by": "N/A",
        "work_package": "AO-MA-delivery-metadata",
        "risk_class": "normal",
        "release_authority_impact": "none",
        "critical_fix": False,
        "boundary_declaration": {
            "credential_read": True,
            "credential_write": False,
            "state_mutation_test": False,
            "state_mutation_production": False,
            "boundary_cross": False,
            "user_communication": False,
            "none_of_the_above": False,
            "user_approval_evidence": "N/A",
        },
        "cross_ai_review": {
            "implementer_provider": "openai",
            "reviewer_providers": [],
            "review_artifacts": [],
            "verdict": "N/A",
            "same_provider_exception": "N/A",
        },
    }
    errors = list(Draft202012Validator(schema).iter_errors(payload))
    assert errors, "credential-read boundary must require approval evidence"


def test_schema_rejects_agree_without_reviewer_or_artifact() -> None:
    schema = _load_schema()
    payload = {
        "issue": "#1001",
        "tracked_by": "N/A",
        "work_package": "AO-MA-delivery-metadata",
        "risk_class": "low",
        "release_authority_impact": "none",
        "critical_fix": False,
        "boundary_declaration": {
            "credential_read": False,
            "credential_write": False,
            "state_mutation_test": False,
            "state_mutation_production": False,
            "boundary_cross": False,
            "user_communication": False,
            "none_of_the_above": True,
            "user_approval_evidence": "N/A",
        },
        "cross_ai_review": {
            "implementer_provider": "openai",
            "reviewer_providers": [],
            "review_artifacts": [],
            "verdict": "AGREE",
            "same_provider_exception": "N/A",
        },
    }
    errors = list(Draft202012Validator(schema).iter_errors(payload))
    assert errors, "non-N/A verdict must include reviewer provider and artifact"


def test_schema_rejects_same_provider_without_exception() -> None:
    schema = _load_schema()
    payload = {
        "issue": "#1001",
        "tracked_by": "N/A",
        "work_package": "AO-MA-delivery-metadata",
        "risk_class": "high",
        "release_authority_impact": "ao-release-gate-input-only",
        "critical_fix": False,
        "boundary_declaration": {
            "credential_read": False,
            "credential_write": False,
            "state_mutation_test": False,
            "state_mutation_production": False,
            "boundary_cross": False,
            "user_communication": False,
            "none_of_the_above": True,
            "user_approval_evidence": "N/A",
        },
        "cross_ai_review": {
            "implementer_provider": "openai",
            "reviewer_providers": ["openai"],
            "review_artifacts": ["https://github.com/Halildeu/ao-kernel/pull/1001#issuecomment-1"],
            "verdict": "AGREE",
            "same_provider_exception": "N/A",
        },
    }
    errors = list(Draft202012Validator(schema).iter_errors(payload))
    assert errors, "same-provider reviewer must require an explicit exception"


def test_runbook_documents_adoption_sequence_and_non_goals() -> None:
    text = RUNBOOK.read_text(encoding="utf-8")
    assert "Release authority remains the repo-owned `ao-release-gate`" in text
    assert "This contract does not authorize support widening" in text
    assert "Metadata-only PR body gate" in text
    assert "Merge-to-issue evidence workflow" in text
    assert "YAML boolean parsing is no longer" in text
    assert "same-provider implementer/reviewer overlap" in text
