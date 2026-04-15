"""Tests for ``ao_kernel.workflow.schema_validator``.

Covers the Draft 2020-12 validator wrapper, cached schema / validator
(``@lru_cache``), meta-validation, and the structured error format
(``json_path`` + ``message`` + ``validator``).
"""

from __future__ import annotations

import uuid
from typing import Any

import pytest
from jsonschema.validators import Draft202012Validator

from ao_kernel.workflow import WorkflowSchemaValidationError, validate_workflow_run
from ao_kernel.workflow.schema_validator import (
    _get_validator,
    load_workflow_run_schema,
)


def _valid_record(**overrides: Any) -> dict[str, Any]:
    """Construct a minimal schema-valid workflow-run record."""
    base = {
        "run_id": str(uuid.uuid4()),
        "workflow_id": "bug_fix_flow",
        "workflow_version": "1.0.0",
        "state": "created",
        "created_at": "2026-04-15T12:00:00+03:00",
        "revision": "a" * 64,
        "intent": {"kind": "inline_prompt", "payload": "test"},
        "steps": [],
        "policy_refs": [
            "ao_kernel/defaults/policies/policy_worktree_profile.v1.json"
        ],
        "adapter_refs": [],
        "evidence_refs": [".ao/evidence/workflows/x/events.jsonl"],
        "budget": {"fail_closed_on_exhaust": True},
    }
    base.update(overrides)
    return base


class TestSchemaLoad:
    def test_schema_id_is_workflow_run_v1(self) -> None:
        schema = load_workflow_run_schema()
        assert schema["$id"] == "urn:ao:workflow-run:v1"

    def test_schema_cached_once_per_process(self) -> None:
        a = load_workflow_run_schema()
        b = load_workflow_run_schema()
        assert a is b, "load_workflow_run_schema must be cached"

    def test_validator_cached(self) -> None:
        v1 = _get_validator()
        v2 = _get_validator()
        assert v1 is v2

    def test_schema_self_meta_validates(self) -> None:
        """The bundled schema itself must pass Draft 2020-12 meta-validation."""
        schema = load_workflow_run_schema()
        Draft202012Validator.check_schema(schema)  # raises on failure
        assert schema.get("$schema", "").endswith("draft/2020-12/schema")


class TestValidPayloads:
    def test_minimal_valid_record_passes(self) -> None:
        rec = _valid_record()
        # validate_workflow_run is void; success = no exception raised.
        assert validate_workflow_run(rec) is None

    def test_with_optional_fields_passes(self) -> None:
        rec = _valid_record(
            started_at="2026-04-15T12:01:00+03:00",
            updated_at="2026-04-15T12:02:00+03:00",
            adapter_refs=["claude-code-cli"],
            error={
                "code": "X_TEST",
                "message": "stub",
                "category": "other",
            },
        )
        assert validate_workflow_run(rec) is None


class TestStructuredErrors:
    def test_invalid_state_reports_json_path_and_validator(self) -> None:
        rec = _valid_record(state="nonsense")
        with pytest.raises(WorkflowSchemaValidationError) as ei:
            validate_workflow_run(rec, run_id=rec["run_id"])
        err = ei.value
        # at least one entry targets $.state with validator=enum
        targeted = [
            e
            for e in err.errors
            if "state" in e["json_path"] and e["validator"] == "enum"
        ]
        assert targeted, err.errors

    def test_missing_required_revision_surfaces_required_validator(self) -> None:
        rec = _valid_record()
        del rec["revision"]
        with pytest.raises(WorkflowSchemaValidationError) as ei:
            validate_workflow_run(rec)
        validators = {e["validator"] for e in ei.value.errors}
        assert "required" in validators, validators

    def test_wrong_type_on_steps_surfaces_type_validator(self) -> None:
        rec = _valid_record(steps="not-a-list")
        with pytest.raises(WorkflowSchemaValidationError) as ei:
            validate_workflow_run(rec)
        validators = {e["validator"] for e in ei.value.errors}
        # 'type' or 'array' depending on jsonschema phrasing; 'type' is canonical
        assert "type" in validators, validators

    def test_errors_sorted_by_json_path(self) -> None:
        """Two errors in the same payload are returned in json_path order."""
        rec = _valid_record(state="nonsense", budget={"fail_closed_on_exhaust": False})
        with pytest.raises(WorkflowSchemaValidationError) as ei:
            validate_workflow_run(rec)
        errors = ei.value.errors
        paths = [e["json_path"] for e in errors]
        assert paths == sorted(paths)

    def test_exception_str_includes_summary(self) -> None:
        rec = _valid_record(state="nonsense")
        with pytest.raises(WorkflowSchemaValidationError) as ei:
            validate_workflow_run(rec, run_id=rec["run_id"])
        msg = str(ei.value)
        assert "state" in msg or "enum" in msg

    def test_run_id_propagates_into_exception(self) -> None:
        rec = _valid_record(state="nonsense")
        run_id = rec["run_id"]
        with pytest.raises(WorkflowSchemaValidationError) as ei:
            validate_workflow_run(rec, run_id=run_id)
        assert ei.value.run_id == run_id


class TestAdditionalPropertiesGuard:
    def test_unknown_top_level_field_rejected(self) -> None:
        """`additionalProperties: false` at the root should reject extras."""
        rec = _valid_record(vendor_extra="not-allowed")
        with pytest.raises(WorkflowSchemaValidationError) as ei:
            validate_workflow_run(rec)
        validators = {e["validator"] for e in ei.value.errors}
        assert "additionalProperties" in validators, validators
