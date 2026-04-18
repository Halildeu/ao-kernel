"""v3.4.0 #3: `cost_reconciled` marker compaction tests."""

from __future__ import annotations

import json
from dataclasses import replace
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest

from ao_kernel.cost._reconcile import apply_spend_with_marker
from ao_kernel.cost.ledger import SpendEvent, compute_billing_digest
from ao_kernel.cost.marker_compaction import (
    BulkCompactionResult,
    CompactionResult,
    compact_all_terminal_runs,
    compact_run_markers,
)
from ao_kernel.cost.policy import CostTrackingPolicy
from ao_kernel.workflow.errors import WorkflowRunNotFoundError


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


def _seed_run(
    root: Path,
    run_id: str,
    *,
    state: str = "running",
    cost_remaining: float = 10.0,
) -> None:
    from ao_kernel.workflow.run_store import run_revision

    run_dir = root / ".ao" / "runs" / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    record: dict[str, Any] = {
        "run_id": run_id,
        "workflow_id": "test_flow",
        "workflow_version": "1.0.0",
        "state": state,
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


def _stamp_markers(root: Path, run_id: str, count: int = 3) -> None:
    """Use the real helper to stamp N markers on a run record."""
    for i in range(count):
        event = SpendEvent(
            run_id=run_id,
            step_id=f"s{i}",
            attempt=1,
            provider_id="codex",
            model="stub",
            tokens_input=10,
            tokens_output=5,
            cost_usd=Decimal("0.01"),
            ts="2026-04-18T10:00:01+00:00",
        )
        event = replace(event, billing_digest=compute_billing_digest(event))
        apply_spend_with_marker(
            root, run_id, event,
            policy=_policy(), source="adapter_path",
            budget_mutator=lambda r: r,
        )


def _read_record(root: Path, run_id: str) -> dict[str, Any]:
    from ao_kernel.workflow.run_store import load_run

    record, _ = load_run(root, run_id)
    return dict(record)


# ─── 1. Happy path: terminal run compacts cleanly ──────────────────────


class TestCompactRunMarkers:
    def test_compacts_populated_markers_into_archive(
        self, tmp_path: Path,
    ) -> None:
        run_id = "00000000-0000-4000-8000-0000f34a0001"
        _seed_run(tmp_path, run_id)
        _stamp_markers(tmp_path, run_id, count=3)

        result = compact_run_markers(tmp_path, run_id)
        assert isinstance(result, CompactionResult)
        assert result.markers_archived == 3
        assert result.already_compact is False

        record = _read_record(tmp_path, run_id)
        assert record["cost_reconciled"] == []
        assert record["cost_reconciled_archive_ref"] == (
            f".ao/cost/markers-archive/{run_id}.jsonl"
        )
        assert "cost_reconciled_compacted_at" in record

        archive = tmp_path / ".ao" / "cost" / "markers-archive" / f"{run_id}.jsonl"
        assert archive.is_file()
        lines = [
            line for line in archive.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        assert len(lines) == 3

    def test_already_compact_is_noop(self, tmp_path: Path) -> None:
        """Running compact twice: second call sees empty list and
        no-ops without touching archive or run."""
        run_id = "00000000-0000-4000-8000-0000f34a0002"
        _seed_run(tmp_path, run_id)
        _stamp_markers(tmp_path, run_id, count=2)

        r1 = compact_run_markers(tmp_path, run_id)
        assert r1.markers_archived == 2
        archive = tmp_path / ".ao" / "cost" / "markers-archive" / f"{run_id}.jsonl"
        first_size = archive.stat().st_size

        r2 = compact_run_markers(tmp_path, run_id)
        assert r2.already_compact is True
        assert r2.markers_archived == 0
        # Archive untouched on second pass
        assert archive.stat().st_size == first_size

    def test_dry_run_does_not_mutate(self, tmp_path: Path) -> None:
        run_id = "00000000-0000-4000-8000-0000f34a0003"
        _seed_run(tmp_path, run_id)
        _stamp_markers(tmp_path, run_id, count=2)

        result = compact_run_markers(tmp_path, run_id, dry_run=True)
        assert result.markers_archived == 2  # reported

        # Record NOT mutated
        record = _read_record(tmp_path, run_id)
        assert len(record["cost_reconciled"]) == 2
        assert "cost_reconciled_archive_ref" not in record

        # Archive NOT created
        archive = tmp_path / ".ao" / "cost" / "markers-archive" / f"{run_id}.jsonl"
        assert not archive.is_file()

    def test_missing_run_raises(self, tmp_path: Path) -> None:
        # Valid UUID format but no on-disk record
        with pytest.raises(WorkflowRunNotFoundError):
            compact_run_markers(
                tmp_path, "00000000-0000-4000-8000-0000f34a0099",
            )


# ─── 2. Bulk compaction for terminal runs ──────────────────────────────


class TestCompactAllTerminalRuns:
    def test_only_terminal_runs_are_touched(self, tmp_path: Path) -> None:
        """completed/failed/cancelled → compacted; running → skipped."""
        for i, state in enumerate(("running", "completed", "failed")):
            rid = f"00000000-0000-4000-8000-0000f34b000{i}"
            _seed_run(tmp_path, rid, state=state)
            _stamp_markers(tmp_path, rid, count=2)

        # Compaction helper needs state to stay at the post-stamp value.
        # apply_spend_with_marker may change updated_at but not state;
        # bring the two non-running ones back to terminal after stamping.
        import json as _json
        from ao_kernel.workflow.run_store import run_revision

        for i, state in enumerate(("completed", "failed")):
            rid = f"00000000-0000-4000-8000-0000f34b000{i + 1}"
            sf = tmp_path / ".ao" / "runs" / rid / "state.v1.json"
            record = _json.loads(sf.read_text(encoding="utf-8"))
            record["state"] = state
            record["revision"] = run_revision(record)
            sf.write_text(
                _json.dumps(record, indent=2, sort_keys=True),
                encoding="utf-8",
            )

        result = compact_all_terminal_runs(tmp_path)
        assert isinstance(result, BulkCompactionResult)
        assert result.runs_scanned == 2  # only the 2 terminal ones
        assert result.runs_compacted == 2
        assert result.markers_archived_total == 4  # 2 × 2 markers

        # Running run still has markers
        rid_running = "00000000-0000-4000-8000-0000f34b0000"
        record = _read_record(tmp_path, rid_running)
        assert len(record["cost_reconciled"]) == 2

    def test_no_runs_returns_empty_result(self, tmp_path: Path) -> None:
        result = compact_all_terminal_runs(tmp_path)
        assert result.runs_scanned == 0
        assert result.runs_compacted == 0
        assert result.errors == ()

    def test_dry_run_surveys_without_mutating(self, tmp_path: Path) -> None:
        rid = "00000000-0000-4000-8000-0000f34b0010"
        _seed_run(tmp_path, rid, state="running")
        _stamp_markers(tmp_path, rid, count=3)

        # Move to terminal state
        from ao_kernel.workflow.run_store import run_revision
        sf = tmp_path / ".ao" / "runs" / rid / "state.v1.json"
        record = json.loads(sf.read_text(encoding="utf-8"))
        record["state"] = "completed"
        record["revision"] = run_revision(record)
        sf.write_text(
            json.dumps(record, indent=2, sort_keys=True),
            encoding="utf-8",
        )

        result = compact_all_terminal_runs(tmp_path, dry_run=True)
        assert result.runs_scanned == 1
        assert result.runs_compacted == 1  # reported
        assert result.markers_archived_total == 3  # reported

        # But no actual mutation
        record = _read_record(tmp_path, rid)
        assert len(record["cost_reconciled"]) == 3
