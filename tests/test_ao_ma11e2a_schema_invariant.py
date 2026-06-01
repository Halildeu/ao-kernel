"""AO-MA-11E-2a schema invariant tests.

Pins:
- Schema is valid Draft 2020-12.
- Schema contract structure (additionalProperties false, required fields, enums).
- Round-trip: DriftReport.to_dict() → validates against schema for every exit_decision.
"""

from __future__ import annotations

import json
from pathlib import Path

import jsonschema
import pytest

from ao_kernel._internal.ao_ma.github_mirror_drift import (
    DriftFinding,
    DriftReport,
    ExitDecision,
)


_REPO_ROOT = Path(__file__).resolve().parent.parent
_SCHEMA_PATH = _REPO_ROOT / "ao_kernel" / "defaults" / "schemas" / "ao-ma-github-mirror-drift-report.schema.v1.json"


def _load_schema() -> dict:
    return json.loads(_SCHEMA_PATH.read_text(encoding="utf-8"))


def test_schema_is_valid_draft_2020_12() -> None:
    schema = _load_schema()
    jsonschema.Draft202012Validator.check_schema(schema)


def test_schema_has_additionalproperties_false() -> None:
    schema = _load_schema()
    assert schema.get("additionalProperties") is False, (
        "schema MUST set additionalProperties:false at root (strict envelope)"
    )
    # All nested object types also strict
    drift_item = schema["properties"]["drift"]["items"]
    assert drift_item.get("additionalProperties") is False
    expected_counts = schema["properties"]["expected_counts"]
    assert expected_counts.get("additionalProperties") is False


def test_schema_pins_const_schema_version() -> None:
    schema = _load_schema()
    sv = schema["properties"]["schema_version"]
    assert sv.get("const") == "ao-ma-github-mirror-drift-report.v1"


def test_schema_pins_exit_decision_enum() -> None:
    schema = _load_schema()
    exits = schema["properties"]["exit_decision"]["enum"]
    assert set(exits) == {
        "synced",
        "mirror_drift_detected",
        "network_not_allowed",
        "api_error",
        "usage_error",
    }


def test_schema_pins_drift_category_enum() -> None:
    schema = _load_schema()
    cats = schema["properties"]["drift"]["items"]["properties"]["category"]["enum"]
    expected = {
        "missing_milestone",
        "milestone_metadata_mismatch",
        "missing_issue",
        "extra_issue",
        "label_mismatch",
        "anchor_mismatch",
        "anchor_schema_mismatch",
        "anchor_sha_format_invalid",
        "anchor_placeholder_unresolved",
        "project_missing",
        "project_item_count_mismatch",
        "project_item_url_mismatch",
    }
    assert set(cats) == expected


def test_schema_pins_severity_enum_only_blocker_and_info() -> None:
    schema = _load_schema()
    sevs = schema["properties"]["drift"]["items"]["properties"]["severity"]["enum"]
    assert set(sevs) == {"blocker", "info"}, (
        "severity tier MUST be exactly {blocker, info} — warning intentionally absent "
        "to prevent bulanik exit semantics (Codex iter-1 §D absorb)."
    )


def test_schema_enforces_synced_empty_drift_invariant() -> None:
    """When exit_decision=synced, drift MUST be empty (allOf if/then)."""
    schema = _load_schema()
    validator = jsonschema.Draft202012Validator(schema)
    bad = {
        "schema_version": "ao-ma-github-mirror-drift-report.v1",
        "projection_manifest": "x.json",
        "manifest_sha256": "sha256:" + "0" * 64,
        "checked_at": "2026-06-01T07:00:00Z",
        "network_allowed": True,
        "token_env": "GH_TOKEN",
        "token_present": False,
        "github_owner": "Halildeu",
        "github_repo": "ao-kernel",
        "expected_counts": {"issues": 0, "labels": 0, "project_items": 0},
        "drift": [
            {
                "category": "missing_issue",
                "severity": "blocker",
                "object_type": "issue",
                "object_id": "x",
                "expected": None,
                "actual": None,
            }
        ],
        "exit_decision": "synced",
    }
    errors = list(validator.iter_errors(bad))
    assert errors, "schema MUST reject synced + non-empty drift (invariant violation)"


def test_schema_enforces_drift_detected_nonempty_invariant() -> None:
    """When exit_decision=mirror_drift_detected, drift MUST be non-empty."""
    schema = _load_schema()
    validator = jsonschema.Draft202012Validator(schema)
    bad = {
        "schema_version": "ao-ma-github-mirror-drift-report.v1",
        "projection_manifest": "x.json",
        "manifest_sha256": "sha256:" + "0" * 64,
        "checked_at": "2026-06-01T07:00:00Z",
        "network_allowed": True,
        "token_env": "GH_TOKEN",
        "token_present": False,
        "github_owner": "Halildeu",
        "github_repo": "ao-kernel",
        "expected_counts": {"issues": 0, "labels": 0, "project_items": 0},
        "drift": [],
        "exit_decision": "mirror_drift_detected",
    }
    errors = list(validator.iter_errors(bad))
    assert errors, "schema MUST reject mirror_drift_detected + empty drift"


def test_schema_enforces_network_not_allowed_invariant() -> None:
    """When exit_decision=network_not_allowed, network_allowed MUST be false."""
    schema = _load_schema()
    validator = jsonschema.Draft202012Validator(schema)
    bad = {
        "schema_version": "ao-ma-github-mirror-drift-report.v1",
        "projection_manifest": "x.json",
        "manifest_sha256": "sha256:" + "0" * 64,
        "checked_at": "2026-06-01T07:00:00Z",
        "network_allowed": True,  # contradicts exit_decision
        "token_env": "GH_TOKEN",
        "token_present": False,
        "github_owner": "Halildeu",
        "github_repo": "ao-kernel",
        "expected_counts": {"issues": 0, "labels": 0, "project_items": 0},
        "drift": [],
        "exit_decision": "network_not_allowed",
    }
    errors = list(validator.iter_errors(bad))
    assert errors, "schema MUST reject network_not_allowed + network_allowed=true (contradiction)"


def test_schema_enforces_sha256_pattern() -> None:
    schema = _load_schema()
    validator = jsonschema.Draft202012Validator(schema)
    bad = {
        "schema_version": "ao-ma-github-mirror-drift-report.v1",
        "projection_manifest": "x.json",
        "manifest_sha256": "not-a-valid-sha",
        "checked_at": "2026-06-01T07:00:00Z",
        "network_allowed": False,
        "token_env": "GH_TOKEN",
        "token_present": False,
        "github_owner": "Halildeu",
        "github_repo": "ao-kernel",
        "expected_counts": {"issues": 0, "labels": 0, "project_items": 0},
        "drift": [],
        "exit_decision": "network_not_allowed",
    }
    errors = list(validator.iter_errors(bad))
    assert errors, "schema MUST reject invalid SHA pattern"


@pytest.mark.parametrize(
    "decision,network_allowed,drift_count",
    [
        (ExitDecision.SYNCED, True, 0),
        (ExitDecision.NETWORK_NOT_ALLOWED, False, 0),
        (ExitDecision.MIRROR_DRIFT_DETECTED, True, 1),
        (ExitDecision.API_ERROR, True, 0),
    ],
)
def test_report_to_dict_validates_against_schema(decision, network_allowed, drift_count):
    schema = _load_schema()
    validator = jsonschema.Draft202012Validator(schema)
    drift = []
    if drift_count > 0:
        drift = [
            DriftFinding(
                category="missing_issue",
                severity="blocker",
                object_type="issue",
                object_id="999",
                expected=None,
                actual=999,
            )
        ]
    report = DriftReport(
        projection_manifest="x.json",
        manifest_sha256="sha256:" + "0" * 64,
        checked_at="2026-06-01T07:00:00Z",
        network_allowed=network_allowed,
        token_env="GH_TOKEN",
        token_present=False,
        github_owner="Halildeu",
        github_repo="ao-kernel",
        expected_counts={"issues": 1, "labels": 0, "project_items": 0},
        drift=drift,
        exit_decision=decision,
    )
    errors = list(validator.iter_errors(report.to_dict()))
    assert not errors, f"DriftReport.to_dict() FAILED schema for {decision.value}: {errors}"
