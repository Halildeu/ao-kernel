"""V5 Epic 2 E-2-3 invariants: CostCeiling.

The module is infrastructure-only: no provider calls, no workflow mutation, no
guard-flag flip. Tests pin the explicit breach states, hard-breach audit write,
Decimal-only validation, and workspace-mode lock-backed concurrency contract.
"""

from __future__ import annotations

import json
import multiprocessing
import subprocess
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest

from ao_kernel.cost import (
    CostCeiling,
    CostCeilingExceeded,
    load_cost_ceiling_policy,
)

_REPO_ROOT = Path(__file__).resolve().parents[1]


def _valid_audit_row() -> dict[str, Any]:
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
        "status": "ok",
        "cost_breach_state": "ok",
        "live_adapter_execution": False,
        "recorded_at": "2026-06-04T10:00:00Z",
    }


def _state_rows(workspace_root: Path) -> list[dict[str, Any]]:
    path = workspace_root / "evidence" / "cost_ceiling_state.jsonl"
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def _concurrent_worker(workspace: str, session_id: str, idx: int) -> None:
    ceiling = CostCeiling(
        Decimal("0.05000000"),
        Decimal("1.00000000"),
        session_id=session_id,
        workspace_root=Path(workspace),
    )
    state = ceiling.record_call(Decimal("0.01000000"))
    assert state in {"ok", "soft_breached"}
    # Keep each child process touching the public read path too.
    assert ceiling.remaining_usd() >= Decimal("0.00000000")
    assert idx >= 0


def test_default_policy_loads_with_guard_pins() -> None:
    policy = load_cost_ceiling_policy()
    assert policy.soft_usd == Decimal("0.10000000")
    assert policy.hard_usd == Decimal("1.00000000")
    raw = _REPO_ROOT / "ao_kernel/defaults/policies/policy_cost_ceiling.v1.json"
    data = json.loads(raw.read_text(encoding="utf-8"))
    assert data["live_adapter_execution"] is False
    assert data["support_widening"] is False
    assert data["production_platform_claim"] is False


def test_threshold_validation_fail_closed() -> None:
    with pytest.raises(ValueError, match="soft_usd"):
        CostCeiling(Decimal("-0.01000000"), Decimal("1.00000000"))
    with pytest.raises(ValueError, match="hard_usd"):
        CostCeiling(Decimal("0.01000000"), Decimal("0.00000000"))
    with pytest.raises(ValueError, match="<="):
        CostCeiling(Decimal("2.00000000"), Decimal("1.00000000"))


def test_library_mode_returns_ok_soft_and_remaining() -> None:
    ceiling = CostCeiling(Decimal("0.10000000"), Decimal("1.00000000"))
    assert ceiling.record_call(Decimal("0.03000000")) == "ok"
    assert ceiling.record_call(Decimal("0.08000000")) == "soft_breached"
    assert ceiling.breach_state() == "soft_breached"
    assert ceiling.remaining_usd() == Decimal("0.89000000")


def test_hard_breach_raises_without_committing_total_library_mode() -> None:
    ceiling = CostCeiling(Decimal("0.10000000"), Decimal("0.20000000"))
    assert ceiling.record_call(Decimal("0.15000000")) == "soft_breached"
    with pytest.raises(CostCeilingExceeded) as excinfo:
        ceiling.record_call(Decimal("0.06000000"))
    assert excinfo.value.session_id == "default"
    assert ceiling.remaining_usd() == Decimal("0.05000000")


def test_record_call_rejects_invalid_cost_inputs() -> None:
    ceiling = CostCeiling(Decimal("0.10000000"), Decimal("1.00000000"))
    with pytest.raises(TypeError, match="Decimal"):
        ceiling.record_call(0.01)  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="non-negative"):
        ceiling.record_call(Decimal("-0.01000000"))
    with pytest.raises(ValueError, match="finite"):
        ceiling.record_call(Decimal("NaN"))
    with pytest.raises(ValueError, match="finite"):
        ceiling.record_call(Decimal("Infinity"))


def test_suspicious_zero_cost_live_context_is_rejected() -> None:
    ceiling = CostCeiling(Decimal("0.10000000"), Decimal("1.00000000"))
    with pytest.raises(ValueError, match="zero-cost suspicious"):
        ceiling.record_call(
            Decimal("0.00000000"),
            mode="live",
            status="ok",
            input_tokens=5,
            output_tokens=7,
            price_per_1k_usd=Decimal("0.10000000"),
        )
    assert ceiling.record_call(Decimal("0.00000000"), mode="dry_run", status="dry_run_emitted") == "ok"


def test_workspace_mode_writes_state_jsonl_with_0600(tmp_path: Path) -> None:
    ceiling = CostCeiling(
        Decimal("0.10000000"),
        Decimal("1.00000000"),
        session_id="session-a",
        workspace_root=tmp_path,
    )
    assert ceiling.record_call(Decimal("0.03000000")) == "ok"
    state = tmp_path / "evidence" / "cost_ceiling_state.jsonl"
    assert state.is_file()
    assert state.stat().st_mode & 0o777 == 0o600
    rows = _state_rows(tmp_path)
    assert rows[0]["schema_version"] == "cost-ceiling-state.v1"
    assert rows[0]["accepted"] is True
    assert rows[0]["cumulative_after_usd"] == "0.03000000"
    assert rows[0]["live_adapter_execution"] is False
    assert rows[0]["support_widening"] is False
    assert rows[0]["production_platform_claim"] is False


def test_workspace_hard_breach_records_state_and_per_call_audit(tmp_path: Path) -> None:
    ceiling = CostCeiling(
        Decimal("0.05000000"),
        Decimal("0.10000000"),
        session_id="hard-a",
        workspace_root=tmp_path,
    )
    assert ceiling.record_call(Decimal("0.08000000")) == "soft_breached"
    with pytest.raises(CostCeilingExceeded):
        ceiling.record_call(Decimal("0.03000000"), audit_row=_valid_audit_row())

    rows = _state_rows(tmp_path)
    assert rows[-1]["breach_state"] == "hard_breached"
    assert rows[-1]["accepted"] is False
    assert rows[-1]["cumulative_after_usd"] == "0.08000000"
    assert rows[-1]["attempted_cumulative_after_usd"] == "0.11000000"

    audit = tmp_path / "evidence" / "per_call_audit.jsonl"
    breach = tmp_path / "evidence" / "cost_hard_breach.jsonl"
    assert audit.is_file()
    assert breach.is_file()
    assert audit.stat().st_mode & 0o777 == 0o600
    assert breach.stat().st_mode & 0o777 == 0o600
    audit_row = json.loads(audit.read_text(encoding="utf-8").splitlines()[-1])
    assert audit_row["status"] == "error"
    assert audit_row["cost_breach_state"] == "hard_breached"
    assert audit_row["cost_breach_handling"] is None


def test_hard_breach_keeps_primary_exception_when_audit_row_is_invalid(tmp_path: Path) -> None:
    ceiling = CostCeiling(
        Decimal("0.05000000"),
        Decimal("0.10000000"),
        session_id="hard-invalid-audit",
        workspace_root=tmp_path,
    )
    invalid_audit = _valid_audit_row()
    invalid_audit.pop("intent")

    assert ceiling.record_call(Decimal("0.08000000")) == "soft_breached"
    with pytest.raises(CostCeilingExceeded) as excinfo:
        ceiling.record_call(Decimal("0.03000000"), audit_row=invalid_audit)

    assert excinfo.value.__cause__ is not None
    rows = _state_rows(tmp_path)
    assert rows[-1]["breach_state"] == "hard_breached"
    assert rows[-1]["accepted"] is False
    assert rows[-1]["cumulative_after_usd"] == "0.08000000"


def test_workspace_concurrent_record_call_is_lock_serialized(tmp_path: Path) -> None:
    try:
        ctx = multiprocessing.get_context("fork")
    except ValueError:
        pytest.skip("fork start method unavailable on this platform")

    n = 12
    session_id = "concurrent-a"
    procs = [ctx.Process(target=_concurrent_worker, args=(str(tmp_path), session_id, i)) for i in range(n)]
    for proc in procs:
        proc.start()
    for proc in procs:
        proc.join()
        assert proc.exitcode == 0

    rows = [row for row in _state_rows(tmp_path) if row["session_id"] == session_id and row["accepted"] is True]
    assert len(rows) == n
    assert rows[-1]["cumulative_after_usd"] == "0.12000000"
    ceiling = CostCeiling(Decimal("0.05000000"), Decimal("1.00000000"), session_id=session_id, workspace_root=tmp_path)
    assert ceiling.breach_state() == "soft_breached"


def test_reservation_settle_adjusts_total_and_is_single_use(tmp_path: Path) -> None:
    ceiling = CostCeiling(
        Decimal("0.05000000"),
        Decimal("0.20000000"),
        session_id="reserve-a",
        workspace_root=tmp_path,
    )
    reservation = ceiling.reserve(Decimal("0.04000000"))
    assert reservation.state == "ok"
    assert ceiling.remaining_usd() == Decimal("0.16000000")
    assert reservation.settle(Decimal("0.02000000")) == "ok"
    assert ceiling.remaining_usd() == Decimal("0.18000000")
    with pytest.raises(ValueError, match="already settled"):
        reservation.settle(Decimal("0.02000000"))


def test_reservation_hard_breach_rejected(tmp_path: Path) -> None:
    ceiling = CostCeiling(
        Decimal("0.05000000"),
        Decimal("0.10000000"),
        session_id="reserve-hard",
        workspace_root=tmp_path,
    )
    with pytest.raises(CostCeilingExceeded):
        ceiling.reserve(Decimal("0.12000000"))
    rows = _state_rows(tmp_path)
    assert rows[-1]["operation"] == "reserve"
    assert rows[-1]["accepted"] is False


def test_cost_ceiling_no_workflow_mutation_in_diff() -> None:
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
    assert not touched, f"E-2-3 must not touch .github/workflows/. Touched: {touched}"
