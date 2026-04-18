"""v3.4.0 #1: reconciliation daemon + CLI tests.

Pin the 6 primary scenarios for orphan recovery:

1. No orphans → cursor ticks, 0 fixed
2. Orphan detected + fixed (marker stamped)
3. Dry-run does NOT mutate run record OR cursor
4. Corrupt ledger line → skipped, scan continues
5. Missing run record → skipped, scan continues
6. Cursor reset forces full re-scan from offset 0
"""

from __future__ import annotations

import json
from dataclasses import replace
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest

from ao_kernel.cost._reconcile import apply_spend_with_marker
from ao_kernel.cost.ledger import SpendEvent, compute_billing_digest
from ao_kernel.cost.policy import CostTrackingPolicy
from ao_kernel.cost.reconcile_daemon import (
    OrphanSpend,
    ScanResult,
    fix_orphan,
    load_cursor,
    save_cursor,
    scan_and_fix,
)


# ─── Fixtures ──────────────────────────────────────────────────────────


def _policy() -> CostTrackingPolicy:
    return CostTrackingPolicy(
        enabled=True,
        price_catalog_path=".ao/cost/price-catalog.json",
        spend_ledger_path=".ao/cost/spend.jsonl",
        fail_closed_on_exhaust=True,
        fail_closed_on_missing_usage=False,
        strict_freshness=False,
        idempotency_window_lines=100,
    )


def _seed_run(root: Path, run_id: str, *, cost_remaining: float = 10.0) -> None:
    """Create a minimal run record with cost_usd axis."""
    from ao_kernel.workflow.run_store import run_revision

    run_dir = root / ".ao" / "runs" / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    record: dict[str, Any] = {
        "run_id": run_id,
        "workflow_id": "test_flow",
        "workflow_version": "1.0.0",
        "state": "running",
        "created_at": "2026-04-18T10:00:00+00:00",
        "revision": "0" * 64,
        "intent": {"kind": "inline_prompt", "payload": "x"},
        "steps": [],
        "policy_refs": [
            "ao_kernel/defaults/policies/policy_worktree_profile.v1.json"
        ],
        "adapter_refs": [],
        "evidence_refs": [
            f".ao/evidence/workflows/{run_id}/events.jsonl",
        ],
        "budget": {
            "fail_closed_on_exhaust": True,
            "cost_usd": {"limit": 10.0, "remaining": cost_remaining},
        },
    }
    record["revision"] = run_revision(record)
    (run_dir / "state.v1.json").write_text(
        json.dumps(record, indent=2, sort_keys=True),
        encoding="utf-8",
    )


def _seed_ledger_entry(
    root: Path,
    *,
    run_id: str,
    step_id: str,
    attempt: int = 1,
    cost_usd: float = 0.05,
    billing_digest: str | None = None,
) -> str:
    """Append a raw ledger entry and return its billing_digest.

    If ``billing_digest`` is None, compute it via
    :func:`compute_billing_digest` so reconciler lookups find the entry.
    """
    event = SpendEvent(
        run_id=run_id,
        step_id=step_id,
        attempt=attempt,
        provider_id="codex",
        model="stub",
        tokens_input=100,
        tokens_output=50,
        cost_usd=Decimal(str(cost_usd)),
        ts="2026-04-18T10:00:01+00:00",
    )
    digest = billing_digest or compute_billing_digest(event)
    event = replace(event, billing_digest=digest)

    ledger_path = root / ".ao" / "cost" / "spend.jsonl"
    ledger_path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    entry = {
        "run_id": run_id,
        "step_id": step_id,
        "attempt": attempt,
        "provider_id": "codex",
        "model": "stub",
        "tokens_input": 100,
        "tokens_output": 50,
        "cost_usd": cost_usd,
        "ts": "2026-04-18T10:00:01+00:00",
        "usage_missing": False,
        "billing_digest": digest,
    }
    with ledger_path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry, sort_keys=True) + "\n")
    return digest


def _read_markers(root: Path, run_id: str) -> list[dict[str, Any]]:
    from ao_kernel.workflow.run_store import load_run

    record, _ = load_run(root, run_id)
    return list(record.get("cost_reconciled", []))


# ─── 1. No orphans, cursor ticks ───────────────────────────────────────


class TestNoOrphans:
    def test_no_orphans_cursor_ticks(self, tmp_path: Path) -> None:
        run_id = "00000000-0000-4000-8000-0000d34a0001"
        _seed_run(tmp_path, run_id)
        # Reconcile via the real helper so marker + ledger are both
        # stamped (non-orphan state).
        event = SpendEvent(
            run_id=run_id, step_id="s1", attempt=1,
            provider_id="codex", model="stub",
            tokens_input=100, tokens_output=50,
            cost_usd=Decimal("0.05"),
            ts="2026-04-18T10:00:01+00:00",
        )
        event = replace(event, billing_digest=compute_billing_digest(event))
        apply_spend_with_marker(
            tmp_path, run_id, event,
            policy=_policy(), source="adapter_path",
            budget_mutator=lambda r: r,
        )

        result = scan_and_fix(tmp_path, _policy())
        assert isinstance(result, ScanResult)
        assert result.orphans_found == 0
        assert result.orphans_fixed == 0
        assert result.cursor_offset_after > 0  # ledger has 1 line


# ─── 2. Orphan detected + fixed ────────────────────────────────────────


class TestOrphanDetectionAndFix:
    def test_orphan_detected_and_fixed(self, tmp_path: Path) -> None:
        """Ledger entry written without a matching marker → scan finds,
        fix stamps the marker. Budget is NOT drained (marker-only
        recovery; original crash-time drain is preserved)."""
        run_id = "00000000-0000-4000-8000-0000d34a0002"
        _seed_run(tmp_path, run_id, cost_remaining=10.0)
        _seed_ledger_entry(
            tmp_path, run_id=run_id, step_id="s1", cost_usd=0.05,
        )

        # Marker absent → orphan
        assert _read_markers(tmp_path, run_id) == []

        result = scan_and_fix(tmp_path, _policy())
        assert result.orphans_found == 1
        assert result.orphans_fixed == 1
        assert result.orphans_skipped == 0

        # Marker now stamped
        markers = _read_markers(tmp_path, run_id)
        assert len(markers) == 1
        assert markers[0]["step_id"] == "s1"
        assert markers[0]["source"] == "adapter_path"

        # Budget unchanged (recovery is marker-only)
        from ao_kernel.workflow.run_store import load_run
        record, _ = load_run(tmp_path, run_id)
        assert record["budget"]["cost_usd"]["remaining"] == pytest.approx(10.0)


# ─── 3. Dry-run does NOT mutate ────────────────────────────────────────


class TestDryRun:
    def test_dry_run_reports_but_does_not_mutate(
        self, tmp_path: Path,
    ) -> None:
        run_id = "00000000-0000-4000-8000-0000d34a0003"
        _seed_run(tmp_path, run_id)
        _seed_ledger_entry(
            tmp_path, run_id=run_id, step_id="s1", cost_usd=0.05,
        )

        result = scan_and_fix(tmp_path, _policy(), dry_run=True)
        assert result.orphans_found == 1
        assert result.orphans_fixed == 0

        # Marker NOT stamped
        assert _read_markers(tmp_path, run_id) == []
        # Cursor NOT persisted (dry-run)
        cursor_path = tmp_path / ".ao" / "cost" / "reconciler-cursor.json"
        assert not cursor_path.is_file()


# ─── 4. Corrupt ledger line ────────────────────────────────────────────


class TestCorruptLedger:
    def test_corrupt_line_skipped_scan_continues(
        self, tmp_path: Path,
    ) -> None:
        run_id = "00000000-0000-4000-8000-0000d34a0004"
        _seed_run(tmp_path, run_id)
        ledger_path = tmp_path / ".ao" / "cost" / "spend.jsonl"
        ledger_path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        # Corrupt line first, then a valid orphan entry
        ledger_path.write_text(
            "this is not json\n",
            encoding="utf-8",
        )
        _seed_ledger_entry(
            tmp_path, run_id=run_id, step_id="s1", cost_usd=0.05,
        )

        result = scan_and_fix(tmp_path, _policy())
        # Scan detects the real orphan despite the corrupt line.
        # Fix path invokes `record_spend` which fail-closes on corrupt
        # ledger (SpendLedgerCorruptedError) — the orphan is COUNTED
        # (found=1) but NOT fixed (fixed=0, error surfaced).
        assert result.orphans_found == 1
        assert result.orphans_fixed == 0
        assert any("Corrupted" in e or "corrupt" in e for e in result.errors)


# ─── 5. Missing run record ─────────────────────────────────────────────


class TestMissingRun:
    def test_orphan_for_missing_run_is_skipped(
        self, tmp_path: Path,
    ) -> None:
        """Ledger references a run that doesn't exist (e.g. cleaned
        up) → scan skips without error."""
        # Seed ledger without the corresponding run record
        (tmp_path / ".ao" / "cost").mkdir(parents=True, exist_ok=True)
        _seed_ledger_entry(
            tmp_path, run_id="missing-run-id", step_id="s1", cost_usd=0.05,
        )

        result = scan_and_fix(tmp_path, _policy())
        assert result.orphans_found == 0  # run missing → not counted
        assert result.errors == ()  # silent skip


# ─── 6. Cursor reset ───────────────────────────────────────────────────


class TestCursorReset:
    def test_cursor_reset_forces_full_rescan(self, tmp_path: Path) -> None:
        run_id = "00000000-0000-4000-8000-0000d34a0006"
        _seed_run(tmp_path, run_id)
        _seed_ledger_entry(
            tmp_path, run_id=run_id, step_id="s1", cost_usd=0.05,
        )

        # First pass: orphan found + fixed, cursor ticks
        r1 = scan_and_fix(tmp_path, _policy())
        assert r1.orphans_fixed == 1
        offset_after_first = r1.cursor_offset_after

        # Second pass: no new orphans, cursor preserved
        r2 = scan_and_fix(tmp_path, _policy())
        assert r2.orphans_found == 0
        assert r2.cursor_offset_before == offset_after_first

        # Third pass with cursor_reset: scans from 0, still no orphans
        # (they were already fixed) but cursor_before=0.
        r3 = scan_and_fix(tmp_path, _policy(), cursor_reset=True)
        assert r3.cursor_offset_before == 0
        assert r3.orphans_found == 0  # all markers already present
        assert r3.cursor_offset_after > 0


# ─── 7. Cursor load/save roundtrip ─────────────────────────────────────


class TestCursorRoundtrip:
    def test_load_cursor_default_when_missing(self, tmp_path: Path) -> None:
        cursor = tmp_path / "does-not-exist.json"
        state = load_cursor(cursor)
        assert state["version"] == "v1"
        assert state["last_scanned_line_offset"] == 0

    def test_load_cursor_version_mismatch_resets(
        self, tmp_path: Path,
    ) -> None:
        cursor = tmp_path / "cursor.json"
        cursor.write_text(
            json.dumps({"version": "v0-ancient", "last_scanned_line_offset": 999}),
            encoding="utf-8",
        )
        state = load_cursor(cursor)
        assert state["version"] == "v1"
        assert state["last_scanned_line_offset"] == 0

    def test_save_and_load_roundtrip(self, tmp_path: Path) -> None:
        cursor = tmp_path / "cursor.json"
        save_cursor(cursor, {
            "version": "v1",
            "last_scanned_line_offset": 42,
            "last_check_ts": "2026-04-18T10:00:00+00:00",
            "orphans_fixed_total": 7,
        })
        state = load_cursor(cursor)
        assert state["last_scanned_line_offset"] == 42
        assert state["orphans_fixed_total"] == 7


# ─── 8. fix_orphan idempotency ─────────────────────────────────────────


class TestFixOrphanIdempotency:
    def test_fix_orphan_idempotent(self, tmp_path: Path) -> None:
        run_id = "00000000-0000-4000-8000-0000d34a0008"
        _seed_run(tmp_path, run_id)
        digest = _seed_ledger_entry(
            tmp_path, run_id=run_id, step_id="s1", cost_usd=0.05,
        )
        orphan = OrphanSpend(
            run_id=run_id,
            step_id="s1",
            attempt=1,
            billing_digest=digest,
            source="adapter_path",
            ledger_line_offset=0,
            raw_event={
                "run_id": run_id,
                "step_id": "s1",
                "attempt": 1,
                "provider_id": "codex",
                "model": "stub",
                "tokens_input": 100,
                "tokens_output": 50,
                "cost_usd": 0.05,
                "ts": "2026-04-18T10:00:01+00:00",
                "usage_missing": False,
                "billing_digest": digest,
            },
        )

        # First fix stamps the marker
        assert fix_orphan(tmp_path, orphan, policy=_policy()) is True
        # Second fix returns False (marker already present)
        assert fix_orphan(tmp_path, orphan, policy=_policy()) is False

        # Ledger still has only 1 entry (record_spend silent no-op)
        ledger = tmp_path / ".ao" / "cost" / "spend.jsonl"
        lines = [
            line for line in ledger.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        assert len(lines) == 1
