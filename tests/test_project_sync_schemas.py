"""Schema validation tests for ao_kernel.project_sync artifacts."""

from __future__ import annotations

import json
from pathlib import Path

import jsonschema
import pytest

_SCHEMA_DIR = Path(__file__).resolve().parent.parent / "ao_kernel" / "defaults" / "schemas"


def _load_schema(name: str) -> dict[str, object]:
    return json.loads((_SCHEMA_DIR / name).read_text(encoding="utf-8"))


def test_drift_report_schema_is_valid_draft_2020_12() -> None:
    """Drift report schema parses and registers with Draft 2020-12."""
    schema = _load_schema("project-sync-drift-report.schema.v1.json")
    jsonschema.Draft202012Validator.check_schema(schema)
    assert schema["$schema"].endswith("draft/2020-12/schema")


def test_drift_report_minimal_payload_validates() -> None:
    """Minimal-but-valid drift report payload passes the schema."""
    schema = _load_schema("project-sync-drift-report.schema.v1.json")
    payload = {
        "schema_version": "project-sync-drift-report.v1",
        "command": "drift",
        "summary": {"issues_scanned": 0, "findings": 0, "healed": 0, "warnings": 0},
        "findings": [],
        "healed": [],
        "warnings": [],
        "guard_flags": {
            "live_adapter_execution": False,
            "support_widening": False,
            "production_platform_claim": False,
        },
        "register_authority": "evidence_record_only",
        "github_write_authorized": True,
    }
    jsonschema.Draft202012Validator(schema).validate(payload)


def test_drift_report_rejects_guard_flag_widening() -> None:
    """Flipping a guard flag to true is rejected by the schema (const false)."""
    schema = _load_schema("project-sync-drift-report.schema.v1.json")
    payload = {
        "schema_version": "project-sync-drift-report.v1",
        "command": "drift",
        "summary": {"issues_scanned": 0, "findings": 0, "healed": 0, "warnings": 0},
        "findings": [],
        "healed": [],
        "warnings": [],
        "guard_flags": {
            "live_adapter_execution": True,
            "support_widening": False,
            "production_platform_claim": False,
        },
        "register_authority": "evidence_record_only",
        "github_write_authorized": True,
    }
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.Draft202012Validator(schema).validate(payload)


def test_add_slice_request_schema_pins_consensus_enum() -> None:
    """add-slice request schema rejects unknown consensus values."""
    schema = _load_schema("project-sync-add-slice-request.schema.v1.json")
    jsonschema.Draft202012Validator.check_schema(schema)
    payload = {
        "schema_version": "project-sync-add-slice-request.v1",
        "epic": "1",
        "slice_id": "E-1-3",
        "title": "CI changelog",
        "risk": "normal",
        "plan_ref": ".claude/plans/x.md",
        "consensus": "magic",  # invalid
        "guard": "none",
        "depends_on": [],
        "guard_flags": {
            "live_adapter_execution": False,
            "support_widening": False,
            "production_platform_claim": False,
        },
        "register_authority": "evidence_record_only",
        "github_write_authorized": True,
    }
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.Draft202012Validator(schema).validate(payload)


def test_label_migration_report_schema_round_trip() -> None:
    """Label-migration report schema validates a realistic dropped entry."""
    schema = _load_schema("project-sync-label-migration-report.schema.v1.json")
    jsonschema.Draft202012Validator.check_schema(schema)
    payload = {
        "schema_version": "project-sync-label-migration-report.v1",
        "command": "label-cleanup",
        "dry_run": False,
        "summary": {"issues_scanned": 1, "entries": 1, "dropped": 1, "skipped": 0},
        "entries": [
            {
                "issue_number": 42,
                "label": "risk:high",
                "target_field": "Risk",
                "target_value": "high",
                "dropped": True,
            }
        ],
        "skipped": [],
        "warnings": [],
        "guard_flags": {
            "live_adapter_execution": False,
            "support_widening": False,
            "production_platform_claim": False,
        },
        "register_authority": "evidence_record_only",
        "github_write_authorized": True,
    }
    jsonschema.Draft202012Validator(schema).validate(payload)


def test_sync_report_schema_pins_manifest_digest_pattern() -> None:
    """Sync-report schema requires sha256: prefixed digest."""
    schema = _load_schema("project-sync-sync-report.schema.v1.json")
    jsonschema.Draft202012Validator.check_schema(schema)
    payload = {
        "schema_version": "project-sync-sync-report.v1",
        "command": "sync",
        "summary": {"issues_scanned": 0, "fields_set": 0, "items_added": 0, "items_existing": 0},
        "manifest_digest": "not-a-digest",
        "guard_flags": {
            "live_adapter_execution": False,
            "support_widening": False,
            "production_platform_claim": False,
        },
        "register_authority": "evidence_record_only",
        "github_write_authorized": True,
    }
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.Draft202012Validator(schema).validate(payload)


def test_cli_drift_payload_validates_against_drift_schema() -> None:
    """The CLI's actual ``_drift_payload`` output must validate.

    Regression guard for the Codex finding that the CLI emitted a
    payload missing ``schema_version`` / ``guard_flags`` / etc., so a
    workflow consuming the artifact via the schema would fail.
    """
    from ao_kernel.project_sync.cli import _drift_payload
    from ao_kernel.project_sync.drift_healer import DriftReport

    payload = _drift_payload("drift", DriftReport(), scanned=0)
    schema = _load_schema("project-sync-drift-report.schema.v1.json")
    jsonschema.Draft202012Validator(schema).validate(payload)


def test_cli_sync_payload_validates_against_sync_schema() -> None:
    """CLI ``_sync_payload`` round-trips through sync-report.v1 schema."""
    from ao_kernel.project_sync.cli import _sync_payload
    from ao_kernel.project_sync.drift_healer import DriftReport

    payload = _sync_payload(
        DriftReport(),
        scanned=0,
        manifest_digest="sha256:" + "0" * 64,
    )
    schema = _load_schema("project-sync-sync-report.schema.v1.json")
    jsonschema.Draft202012Validator(schema).validate(payload)


def test_cli_label_migration_payload_validates_against_schema() -> None:
    """CLI ``_migration_payload`` round-trips through label-migration schema."""
    from ao_kernel.project_sync.cli import _migration_payload
    from ao_kernel.project_sync.label_migrator import MigrationReport

    payload = _migration_payload(MigrationReport(), dry_run=True, scanned=0)
    schema = _load_schema("project-sync-label-migration-report.schema.v1.json")
    jsonschema.Draft202012Validator(schema).validate(payload)
