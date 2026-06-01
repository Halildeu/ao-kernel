"""AO-MA-11A-2 gate report schema invariants."""

from __future__ import annotations

import json
from pathlib import Path

import jsonschema

_REPO_ROOT = Path(__file__).resolve().parent.parent
_SCHEMA_PATH = (
    _REPO_ROOT / "ao_kernel" / "defaults" / "schemas" / "ao-ma-11a-2-plan-approval-gate-report.schema.v1.json"
)


def _load():
    return json.loads(_SCHEMA_PATH.read_text(encoding="utf-8"))


def test_schema_is_valid_draft_2020_12():
    schema = _load()
    jsonschema.Draft202012Validator.check_schema(schema)


def test_schema_additional_properties_false_at_root():
    schema = _load()
    assert schema["additionalProperties"] is False


def test_schema_pins_schema_version_const():
    schema = _load()
    sv = schema["properties"]["schema_version"]
    assert sv["const"] == "ao-ma-11a-2-plan-approval-gate-report.v1"


def test_schema_pins_environment_name_const():
    schema = _load()
    en = schema["properties"]["environment_name"]
    assert en["const"] == "ao-ma-plan-approval"


def test_schema_pins_9_final_decision_enum():
    schema = _load()
    enum = set(schema["properties"]["final_decision"]["enum"])
    expected = {
        "approved",
        "rejected_path",
        "rejected_sha",
        "rejected_binding",
        "rejected_consensus",
        "rejected_identity",
        "rejected_approval_validator",
        "api_error",
        "usage_error",
    }
    assert enum == expected


def test_schema_pins_approval_api_state_enum():
    schema = _load()
    enum = set(schema["properties"]["approval_api_state"]["enum"])
    expected = {
        "approved",
        "rejected",
        "pending",
        "empty",
        "wrong_environment",
        "api_error",
    }
    assert enum == expected


def test_schema_pins_base_sha_40_hex_pattern():
    schema = _load()
    pat = schema["properties"]["base_sha"]["pattern"]
    assert pat == "^[0-9a-f]{40}$"


def test_schema_pins_audit_url_pattern():
    schema = _load()
    pat = schema["properties"]["audit_url"]["pattern"]
    # Pattern uses escaped dot; check segments
    assert "github" in pat
    assert "\\.com" in pat or "com" in pat
    assert "actions/runs" in pat


def test_schema_enforces_approved_all_stages_pass():
    """Approved → all 5 stage pass flags + bypass:false + approval_api_state=approved."""
    schema = _load()
    validator = jsonschema.Draft202012Validator(schema)
    bad = _make_base()
    bad["final_decision"] = "approved"
    bad["path_containment_pass"] = False  # contradicts approved
    bad["stage_fail_reason"] = None
    errors = list(validator.iter_errors(bad))
    assert errors, "schema MUST reject approved + any stage fail"


def test_schema_enforces_approved_bypass_false():
    schema = _load()
    validator = jsonschema.Draft202012Validator(schema)
    bad = _make_base()
    bad["final_decision"] = "approved"
    bad["path_containment_pass"] = True
    bad["sha_recompute_pass"] = True
    bad["plan_binding_pass"] = True
    bad["consensus_validator_pass"] = True
    bad["approval_validator_pass"] = True
    bad["approval_api_state"] = "approved"
    bad["approving_login"] = "user"
    bad["approving_at"] = "2026-06-01T00:00:00Z"
    bad["bypass_detected"] = True  # contradicts approved
    bad["stage_fail_reason"] = None
    errors = list(validator.iter_errors(bad))
    assert errors, "schema MUST reject approved + bypass_detected=true"


def test_schema_enforces_non_approved_has_fail_reason():
    schema = _load()
    validator = jsonschema.Draft202012Validator(schema)
    bad = _make_base()
    bad["final_decision"] = "rejected_path"
    bad["stage_fail_reason"] = None  # MUST be populated when not approved
    errors = list(validator.iter_errors(bad))
    assert errors


def test_schema_enforces_approval_api_state_approved_has_login_and_at():
    """Codex iter-2 Blocker 4 absorb: approval_api_state=approved requires identity fields."""
    schema = _load()
    validator = jsonschema.Draft202012Validator(schema)
    bad = _make_base()
    bad["final_decision"] = "rejected_identity"
    bad["approval_api_state"] = "approved"
    bad["approving_login"] = None  # contradicts state
    bad["approving_at"] = None
    bad["stage_fail_reason"] = "test"
    errors = list(validator.iter_errors(bad))
    assert errors


def _make_base():
    return {
        "schema_version": "ao-ma-11a-2-plan-approval-gate-report.v1",
        "final_decision": "usage_error",
        "path_containment_pass": False,
        "sha_recompute_pass": False,
        "plan_binding_pass": False,
        "consensus_validator_pass": False,
        "approval_validator_pass": False,
        "approval_api_state": "empty",
        "approving_login": None,
        "approving_at": None,
        "no_bypass_state_observed": False,
        "self_review_rejected": False,
        "required_reviewer_configured": False,
        "bypass_detected": True,
        "environment_name": "ao-ma-plan-approval",
        "run_id": "123",
        "repository_full_name": "Halildeu/ao-kernel",
        "base_sha": "a" * 40,
        "triggering_actor": "bot",
        "audit_url": "https://github.com/Halildeu/ao-kernel/actions/runs/123",
        "stage_fail_reason": "not_started",
    }
