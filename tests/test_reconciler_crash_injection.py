"""v3.4.0 #7: subprocess crash-kill harness + reconciler recovery pin.

Mock-based idempotency tests (test_cost_marker_idempotency,
test_reconcile_daemon) cover the exception-handling branches. This
file adds a single end-to-end pin that a REAL OS-level crash between
ledger append and marker CAS leaves the ledger intact on disk and
the reconciler daemon successfully recovers. Catches issues that
only surface when the interpreter halts without running finalizers
(unflushed buffers, fsync gaps, open-file leaks).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ao_kernel.cost.policy import CostTrackingPolicy
from ao_kernel.cost.reconcile_daemon import scan_and_fix

from tests._subprocess_crash_helper import run_crash_scenario


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


def _seed_run(root: Path, run_id: str) -> None:
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
            "ao_kernel/defaults/policies/policy_worktree_profile.v1.json",
        ],
        "adapter_refs": [],
        "evidence_refs": [
            f".ao/evidence/workflows/{run_id}/events.jsonl",
        ],
        "budget": {
            "fail_closed_on_exhaust": True,
            "cost_usd": {"limit": 10.0, "remaining": 10.0},
        },
    }
    record["revision"] = run_revision(record)
    (run_dir / "state.v1.json").write_text(
        json.dumps(record, indent=2, sort_keys=True),
        encoding="utf-8",
    )


class TestReconcilerRealCrashRecovery:
    def test_crash_between_ledger_append_and_marker_survives(
        self, tmp_path: Path,
    ) -> None:
        """Child process writes a ledger entry, fsyncs it, then
        ``os._exit(77)`` BEFORE the marker CAS runs. Parent process
        then runs the reconciler and verifies:

        1. Ledger entry survived the crash (durability)
        2. `cost_reconciled` marker was absent (mid-write terminate)
        3. Daemon detects the orphan and stamps the marker
        4. Second daemon pass is a no-op (idempotent recovery)
        """
        run_id = "00000000-0000-4000-8000-0000c7a50001"
        _seed_run(tmp_path, run_id)

        # Child script: write ledger line then os._exit(77) — this
        # simulates a crash DURING `apply_spend_with_marker` where
        # the ledger append completed but the marker CAS has not
        # started yet. We call `record_spend` (which fsyncs) so the
        # entry is guaranteed on disk, then kill the process.
        script = """
            from decimal import Decimal
            from pathlib import Path
            from ao_kernel.cost.ledger import (
                SpendEvent, compute_billing_digest, record_spend,
            )
            from ao_kernel.cost.policy import CostTrackingPolicy
            from dataclasses import replace

            root = Path(workspace_root)
            policy = CostTrackingPolicy(
                enabled=True,
                price_catalog_path=".ao/cost/price-catalog.json",
                spend_ledger_path=".ao/cost/spend.jsonl",
                fail_closed_on_exhaust=True,
                fail_closed_on_missing_usage=False,
                strict_freshness=False,
                idempotency_window_lines=100,
            )
            event = SpendEvent(
                run_id="00000000-0000-4000-8000-0000c7a50001",
                step_id="crashed-step",
                attempt=1,
                provider_id="codex",
                model="stub",
                tokens_input=100,
                tokens_output=50,
                cost_usd=Decimal("0.05"),
                ts="2026-04-18T10:00:01+00:00",
            )
            event = replace(event, billing_digest=compute_billing_digest(event))
            record_spend(root, event, policy=policy)
            # Mid-flight crash: ledger written + fsynced, marker NOT stamped.
            os._exit(77)
        """

        run_crash_scenario(script=script, workspace_root=tmp_path)

        # Post-crash assertions (parent process): ledger survived,
        # marker absent.
        ledger_path = tmp_path / ".ao" / "cost" / "spend.jsonl"
        assert ledger_path.is_file(), "ledger did not survive the crash"
        lines = [
            line for line in ledger_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        assert len(lines) == 1
        entry = json.loads(lines[0])
        assert entry["step_id"] == "crashed-step"

        from ao_kernel.workflow.run_store import load_run
        record, _ = load_run(tmp_path, run_id)
        assert record.get("cost_reconciled", []) == []

        # Reconciler recovers
        result = scan_and_fix(tmp_path, _policy())
        assert result.orphans_found == 1
        assert result.orphans_fixed == 1

        # Second pass: idempotent no-op
        result2 = scan_and_fix(tmp_path, _policy())
        assert result2.orphans_found == 0
        assert result2.orphans_fixed == 0

        # Marker now present
        record_after, _ = load_run(tmp_path, run_id)
        markers = record_after.get("cost_reconciled", [])
        assert len(markers) == 1
        assert markers[0]["step_id"] == "crashed-step"
