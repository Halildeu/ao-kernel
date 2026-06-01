"""AO-MA-11E-2b schema invariant tests for sync report schema."""

from __future__ import annotations

import json
from pathlib import Path

import jsonschema
import pytest

from ao_kernel._internal.ao_ma.github_mirror_sync import (
    EnvironmentPreflight,
    SyncReport,
    SyncState,
)


_REPO_ROOT = Path(__file__).resolve().parent.parent
_SCHEMA_PATH = _REPO_ROOT / "ao_kernel" / "defaults" / "schemas" / "ao-ma-github-mirror-sync-report.schema.v1.json"


def _load() -> dict:
    return json.loads(_SCHEMA_PATH.read_text(encoding="utf-8"))


def test_schema_is_valid_draft_2020_12() -> None:
    schema = _load()
    jsonschema.Draft202012Validator.check_schema(schema)


def test_schema_has_additionalproperties_false() -> None:
    schema = _load()
    assert schema["additionalProperties"] is False
    # Nested
    env = schema["properties"]["environment_preflight"]
    assert env["additionalProperties"] is False
    change_ref = schema["$defs"]["changeRecord"]
    assert change_ref["additionalProperties"] is False


def test_schema_pins_schema_version() -> None:
    schema = _load()
    assert schema["properties"]["schema_version"]["const"] == "ao-ma-github-mirror-sync-report.v1"


def test_schema_pins_sync_state_enum() -> None:
    schema = _load()
    states = set(schema["properties"]["sync_state"]["enum"])
    expected = {s.value for s in SyncState}
    assert states == expected


def test_schema_pins_change_category_enum() -> None:
    schema = _load()
    cats = set(schema["$defs"]["changeRecord"]["properties"]["category"]["enum"])
    expected = {
        "issue_body_rewrite",
        "label_add",
        "label_remove",
        "project_item_add",
        "project_item_remove",
    }
    assert cats == expected


def test_schema_pins_environment_decision_enum() -> None:
    schema = _load()
    decisions = set(
        schema["properties"]["environment_preflight"]["properties"]["environment_preflight_decision"]["enum"]
    )
    expected = {"pass", "fail_closed_missing", "fail_closed_no_reviewers", "skipped_dry_run"}
    assert decisions == expected


def test_schema_rejects_dry_run_with_applied_changes() -> None:
    schema = _load()
    validator = jsonschema.Draft202012Validator(schema)
    bad = _make_base_report()
    bad["apply_mode"] = False
    bad["applied_changes"] = [
        {
            "category": "issue_body_rewrite",
            "object_type": "issue",
            "object_id": "1",
            "before": "x",
            "after": "y",
        }
    ]
    errors = list(validator.iter_errors(bad))
    assert errors


def test_schema_rejects_apply_state_with_wrong_confirmation() -> None:
    schema = _load()
    validator = jsonschema.Draft202012Validator(schema)
    bad = _make_base_report()
    bad["apply_mode"] = True
    bad["sync_state"] = "applied"
    bad["confirmation_provided"] = "WRONG-TOKEN"
    bad["accepted_dry_run_report_digest"] = "sha256:" + "a" * 64
    bad["applied_changes"] = [
        {
            "category": "issue_body_rewrite",
            "object_type": "issue",
            "object_id": "1",
            "before": "x",
            "after": "y",
        }
    ]
    errors = list(validator.iter_errors(bad))
    assert errors, "schema must reject apply state with wrong confirmation"


def test_schema_rejects_apply_state_with_empty_applied_changes() -> None:
    schema = _load()
    validator = jsonschema.Draft202012Validator(schema)
    bad = _make_base_report()
    bad["apply_mode"] = True
    bad["sync_state"] = "applied"
    bad["confirmation_provided"] = "AO-MA-11E-2B-APPLY"
    bad["accepted_dry_run_report_digest"] = "sha256:" + "a" * 64
    bad["applied_changes"] = []  # empty for applied state — schema rejects
    errors = list(validator.iter_errors(bad))
    assert errors


def test_schema_rejects_dry_run_with_apply_state() -> None:
    schema = _load()
    validator = jsonschema.Draft202012Validator(schema)
    bad = _make_base_report()
    bad["apply_mode"] = False
    bad["sync_state"] = "applied"  # dry-run can't reach apply state
    errors = list(validator.iter_errors(bad))
    assert errors


def test_report_to_dict_validates_dry_run_complete() -> None:
    schema = _load()
    validator = jsonschema.Draft202012Validator(schema)
    report = SyncReport(
        projection_manifest="x.json",
        manifest_sha256="sha256:" + "0" * 64,
        checked_at="2026-06-01T00:00:00Z",
        network_allowed=True,
        token_env="GH_TOKEN",
        token_present=True,
        github_owner="Halildeu",
        github_repo="ao-kernel",
        apply_mode=False,
        confirmation_provided=None,
        accepted_dry_run_report_digest=None,
        environment_preflight=EnvironmentPreflight(
            environment_name="ao-ma-mirror-sync",
            environment_exists=False,
            required_reviewers_count=0,
            environment_preflight_decision="skipped_dry_run",
        ),
        sync_state=SyncState.DRY_RUN_COMPLETE,
    )
    errors = list(validator.iter_errors(report.to_dict()))
    assert not errors, f"dry-run report failed validation: {errors}"


@pytest.mark.parametrize(
    "state,apply_mode,changes_present",
    [
        ("applied", True, True),
        ("dry_run_complete", False, False),
        ("apply_aborted", True, False),
        ("api_error", True, False),
        ("usage_error", False, False),
    ],
)
def test_report_validates_across_states(state, apply_mode, changes_present):
    schema = _load()
    validator = jsonschema.Draft202012Validator(schema)
    base = _make_base_report()
    base["apply_mode"] = apply_mode
    base["sync_state"] = state
    base["reason"] = None if state == "dry_run_complete" else "test reason"
    if state == "applied":
        base["confirmation_provided"] = "AO-MA-11E-2B-APPLY"
        base["accepted_dry_run_report_digest"] = "sha256:" + "a" * 64
        base["applied_changes"] = [
            {
                "category": "issue_body_rewrite",
                "object_type": "issue",
                "object_id": "1",
                "before": "x",
                "after": "y",
            }
        ]
    errors = list(validator.iter_errors(base))
    assert not errors, f"state={state}: {errors}"


def _make_base_report() -> dict:
    return {
        "schema_version": "ao-ma-github-mirror-sync-report.v1",
        "projection_manifest": "x.json",
        "manifest_sha256": "sha256:" + "0" * 64,
        "checked_at": "2026-06-01T00:00:00Z",
        "network_allowed": True,
        "token_env": "GH_TOKEN",
        "token_present": True,
        "github_owner": "Halildeu",
        "github_repo": "ao-kernel",
        "apply_mode": False,
        "confirmation_provided": None,
        "accepted_dry_run_report_digest": None,
        "planned_changes": [],
        "applied_changes": [],
        "pre_drift_snapshot": None,
        "post_drift_snapshot": None,
        "environment_preflight": {
            "environment_name": "ao-ma-mirror-sync",
            "environment_exists": False,
            "required_reviewers_count": 0,
            "environment_preflight_decision": "skipped_dry_run",
        },
        "sync_state": "dry_run_complete",
        "reason": None,
    }
