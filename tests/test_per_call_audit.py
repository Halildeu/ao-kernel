"""V5 Epic 2 E-2-2 invariants: per-call audit schema + writer.

Schema invariants mirror E-2-1's fail-closed discipline (strict closure at every
object, guard-flag pins, decimal cost, calendar-coupling RFC3339, parametrized
negatives). Writer invariants prove the fail-closed contract:
  - schema-invalid row raises BEFORE any write
  - library mode (workspace_root=None) skips persistence
  - workspace mode appends valid JSONL; hard_breached is cross-referenced
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

import pytest
from jsonschema import Draft202012Validator

from ao_kernel._internal.evidence.per_call_audit import (
    PerCallAuditValidationError,
    record_call,
)
from ao_kernel.config import load_default

_REPO_ROOT = Path(__file__).resolve().parents[1]
_SCHEMA_NAME = "per_call_audit.schema.v1.json"
_SCHEMA_PATH = _REPO_ROOT / "ao_kernel" / "defaults" / "schemas" / _SCHEMA_NAME


def _schema() -> dict[str, Any]:
    return load_default("schemas", _SCHEMA_NAME)


def _is_valid(payload: dict[str, Any]) -> bool:
    return not list(Draft202012Validator(_schema()).iter_errors(payload))


def _valid_row() -> dict[str, Any]:
    return {
        "schema_version": "per-call-audit.v1",
        "artifact_kind": "per_call_audit",
        "envelope_digest": "a" * 64,
        "provider_id": "openai",
        "model": "gpt-4o-mini",
        "request_id": "0a1b2c3d-4e5f-6071-8293-a4b5c6d7e8f9",
        "intent": "FAST_TEXT",
        "input_tokens": 12,
        "output_tokens": 8,
        "total_tokens": 20,
        "actual_cost_usd": "0.00000660",
        "latency_ms": 0,
        "status": "dry_run_emitted",
        "cost_breach_state": "not_applicable",
        "live_adapter_execution": False,
        "recorded_at": "2026-06-04T10:00:00Z",
    }


def _soft_breach_row() -> dict[str, Any]:
    row = _valid_row()
    row["status"] = "ok"
    row["cost_breach_state"] = "soft_breached"
    row["cost_breach_handling"] = {
        "decision": "continued",
        "soft_threshold_usd": "0.50000000",
        "cumulative_cost_usd": "0.51000000",
        "decided_at": "2026-06-04T10:00:01Z",
    }
    return row


# ---- 1. schema health (2) ----------------------------------------------


def test_schema_present_and_valid_draft_2020_12() -> None:
    assert _SCHEMA_PATH.is_file(), f"{_SCHEMA_NAME} missing (E-2-2)"
    schema = _schema()
    Draft202012Validator.check_schema(schema)
    assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"


def test_valid_rows_validate() -> None:
    assert _is_valid(_valid_row())
    assert _is_valid(_soft_breach_row())


# ---- 2. guard-flag pins (2) --------------------------------------------


def test_live_adapter_execution_pinned_false() -> None:
    row = _valid_row()
    row["live_adapter_execution"] = True
    assert not _is_valid(row), "live_adapter_execution=true must be rejected"


def test_optional_guard_flags_false_if_present() -> None:
    for flag in ("support_widening", "production_platform_claim"):
        bad = _valid_row()
        bad[flag] = True
        assert not _is_valid(bad), f"{flag}=true must be rejected"
        ok = _valid_row()
        ok[flag] = False
        assert _is_valid(ok), f"{flag}=false must be accepted"


# ---- 3. strict closure + required (2) ----------------------------------


@pytest.mark.parametrize("path", [(), ("cost_breach_handling",)])
def test_additional_properties_rejected_at_every_object(path: tuple[str, ...]) -> None:
    payload = _soft_breach_row()  # has cost_breach_handling populated
    target: Any = payload
    for key in path:
        target = target[key]
    target["unexpected_field"] = "x"
    assert not _is_valid(payload), f"additionalProperties at {path or 'root'} must be rejected"


@pytest.mark.parametrize(
    "field",
    [
        "schema_version",
        "artifact_kind",
        "envelope_digest",
        "provider_id",
        "model",
        "request_id",
        "intent",
        "input_tokens",
        "output_tokens",
        "total_tokens",
        "actual_cost_usd",
        "latency_ms",
        "status",
        "cost_breach_state",
        "live_adapter_execution",
        "recorded_at",
    ],
)
def test_each_required_field_enforced(field: str) -> None:
    row = _valid_row()
    del row[field]
    assert not _is_valid(row), f"removing required '{field}' must fail"


# ---- 4. const + enum pins (3) ------------------------------------------


def test_const_pins_reject_wrong_values() -> None:
    for field, bad in (("schema_version", "per-call-audit.v2"), ("artifact_kind", "other")):
        row = _valid_row()
        row[field] = bad
        assert not _is_valid(row), f"{field} const must reject '{bad}'"


def test_status_enum_complete() -> None:
    statuses = set(_schema()["properties"]["status"]["enum"])
    assert statuses == {"ok", "error", "stub_emitted", "dry_run_emitted"}


def test_cost_breach_state_enum_complete() -> None:
    states = set(_schema()["properties"]["cost_breach_state"]["enum"])
    assert states == {"ok", "soft_breached", "hard_breached", "not_applicable"}


# ---- 5. cost + digest + timestamp fail-closed (3) ----------------------


def test_cost_must_be_decimal_8dp_not_float() -> None:
    row = _valid_row()
    row["actual_cost_usd"] = 0.0000066
    assert not _is_valid(row), "float cost must be rejected"
    row2 = _valid_row()
    row2["actual_cost_usd"] = "0.01"
    assert not _is_valid(row2), "2dp cost must be rejected; 8dp required"


def test_envelope_digest_bare_sha256() -> None:
    row = _valid_row()
    row["envelope_digest"] = "sha256:" + ("a" * 64)
    assert not _is_valid(row), "envelope_digest must be bare 64-hex"


def test_recorded_at_calendar_coupling() -> None:
    for bad in ("not-a-date", "2026-99-99T00:00:00Z", "2026-02-31T00:00:00Z", "2026-04-31T00:00:00Z"):
        row = _valid_row()
        row["recorded_at"] = bad
        assert not _is_valid(row), f"recorded_at must reject {bad!r}"
    # Feb-29 accepted by regex (leap validity is recompute-time, see E-2-1 boundary)
    ok = _valid_row()
    ok["recorded_at"] = "2026-02-29T00:00:00Z"
    assert _is_valid(ok)


# ---- 6. conditional invariants (allOf) (2) -----------------------------


def test_soft_breach_requires_handling() -> None:
    row = _valid_row()
    row["cost_breach_state"] = "soft_breached"
    # no cost_breach_handling
    assert not _is_valid(row), "soft_breached without cost_breach_handling must be rejected"
    assert _is_valid(_soft_breach_row()), "soft_breached with handling must validate"


def test_hard_breach_requires_error_status() -> None:
    row = _valid_row()
    row["cost_breach_state"] = "hard_breached"
    row["status"] = "ok"  # mismatched
    assert not _is_valid(row), "hard_breached must require status=error"
    row["status"] = "error"
    assert _is_valid(row), "hard_breached + status=error must validate"


# ---- 7. writer: fail-closed + library/workspace modes (5) --------------


def test_writer_rejects_invalid_row_before_write(tmp_path: Path) -> None:
    bad = _valid_row()
    del bad["actual_cost_usd"]  # fail-closed: missing cost
    with pytest.raises(PerCallAuditValidationError):
        record_call(bad, workspace_root=tmp_path)
    # nothing was written
    assert not (tmp_path / "evidence" / "per_call_audit.jsonl").exists()


def test_writer_library_mode_skips_persistence() -> None:
    receipt = record_call(_valid_row(), workspace_root=None)
    assert receipt == {"persisted": False, "mode": "library", "paths": []}


def test_writer_workspace_mode_appends_jsonl(tmp_path: Path) -> None:
    receipt = record_call(_valid_row(), workspace_root=tmp_path)
    assert receipt["persisted"] is True and receipt["mode"] == "workspace"
    audit = tmp_path / "evidence" / "per_call_audit.jsonl"
    assert audit.is_file()
    rows = [json.loads(line) for line in audit.read_text(encoding="utf-8").splitlines()]
    assert len(rows) == 1 and rows[0]["envelope_digest"] == "a" * 64


def test_writer_appends_are_cumulative(tmp_path: Path) -> None:
    record_call(_valid_row(), workspace_root=tmp_path)
    record_call(_valid_row(), workspace_root=tmp_path)
    audit = tmp_path / "evidence" / "per_call_audit.jsonl"
    rows = audit.read_text(encoding="utf-8").splitlines()
    assert len(rows) == 2, "append must be cumulative (O_APPEND), not overwrite"


def test_writer_hard_breach_cross_referenced(tmp_path: Path) -> None:
    row = _valid_row()
    row["cost_breach_state"] = "hard_breached"
    row["status"] = "error"
    receipt = record_call(row, workspace_root=tmp_path)
    assert (tmp_path / "evidence" / "per_call_audit.jsonl").is_file()
    breach = tmp_path / "evidence" / "cost_hard_breach.jsonl"
    assert breach.is_file(), "hard_breached row must also land in cost_hard_breach.jsonl"
    assert str(breach) in receipt["paths"]


# ---- 8. governance: no workflow mutation (1) ---------------------------


def test_no_workflow_mutation_in_diff() -> None:
    added = subprocess.run(
        [
            "git",
            "diff",
            "--diff-filter=A",
            "--name-only",
            "origin/main...HEAD",
            "--",
            "tests/test_per_call_audit.py",
        ],
        cwd=_REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if added.returncode != 0:
        pytest.skip(f"git diff unavailable: {added.stderr.strip()}")
    if not added.stdout.strip():
        pytest.skip("E-2-2 test not ADDED by this PR (introducer pattern); invariant N/A")
    proc = subprocess.run(
        ["git", "diff", "--name-only", "origin/main...HEAD", "--", ".github/workflows/"],
        cwd=_REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        pytest.skip(f"git diff unavailable: {proc.stderr.strip()}")
    touched = [p for p in proc.stdout.split() if p]
    assert not touched, f"E-2-2 must not touch .github/workflows/. Touched: {touched}"
