"""Tests for PR-B5 C3 helpers — coordination ``live_claims_count`` and
``run_store.list_terminal_runs``.

These helpers are consumed by
:func:`ao_kernel.metrics.derivation.derive_metrics_from_evidence`
(claim_active gauge + cancelled workflow duration). Covered here in
isolation for faster feedback and to pin the contract the derivation
test relies on.
"""

from __future__ import annotations

import json
from pathlib import Path

from ao_kernel.coordination.registry import (
    ClaimRegistry,
    live_claims_count,
)
from ao_kernel.workflow.run_store import create_run, list_terminal_runs


class TestLiveClaimsCount:
    def test_dormant_policy_returns_empty_dict(
        self, tmp_path: Path
    ) -> None:
        """Bundled default ships enabled=false; helper returns {}
        without raising. The metrics derivation treats this as "gauge
        at 0" which matches operator expectations."""
        assert live_claims_count(tmp_path) == {}

    def test_live_claims_counted_per_agent(
        self, tmp_path: Path
    ) -> None:
        """With an enabled policy override, acquire two claims for
        two agents and confirm the snapshot reports the correct
        live counts."""
        policy_path = (
            tmp_path / ".ao" / "policies" / "policy_coordination_claims.v1.json"
        )
        policy_path.parent.mkdir(parents=True, exist_ok=True)
        policy_path.write_text(
            json.dumps({
                "version": "v1",
                "enabled": True,
                "heartbeat_interval_seconds": 30,
                "expiry_seconds": 90,
                "takeover_grace_period_seconds": 15,
                "max_claims_per_agent": 5,
                "claim_resource_patterns": ["*"],
                "evidence_redaction": {"patterns": []},
            }, sort_keys=True),
            encoding="utf-8",
        )
        reg = ClaimRegistry(tmp_path)
        reg.acquire_claim("res-a", "agent-1")
        reg.acquire_claim("res-b", "agent-1")
        reg.acquire_claim("res-c", "agent-2")

        counts = live_claims_count(tmp_path)
        assert counts == {"agent-1": 2, "agent-2": 1}


class TestListTerminalRuns:
    @staticmethod
    def _make_run(ws: Path, run_id: str, state: str) -> None:
        create_run(
            ws,
            run_id=run_id,
            workflow_id="bug_fix_flow",
            workflow_version="1.0.0",
            intent={"kind": "inline_prompt", "payload": "t"},
            budget={"fail_closed_on_exhaust": True},
            policy_refs=[
                "ao_kernel/defaults/policies/policy_worktree_profile.v1.json"
            ],
            evidence_refs=[
                f".ao/evidence/workflows/{run_id}/events.jsonl"
            ],
        )
        state_path = ws / ".ao" / "runs" / run_id / "state.v1.json"
        record = json.loads(state_path.read_text(encoding="utf-8"))
        record["state"] = state
        if state in {"completed", "failed", "cancelled"}:
            record["completed_at"] = "2026-04-17T10:00:00+00:00"
        state_path.write_text(
            json.dumps(record, sort_keys=True), encoding="utf-8"
        )

    def test_empty_runs_dir_returns_empty_list(
        self, tmp_path: Path
    ) -> None:
        assert list_terminal_runs(tmp_path) == []

    def test_filters_to_terminal_states(self, tmp_path: Path) -> None:
        run_ids = [
            "00000000-0000-4000-8000-000000000001",
            "00000000-0000-4000-8000-000000000002",
            "00000000-0000-4000-8000-000000000003",
            "00000000-0000-4000-8000-000000000004",
        ]
        self._make_run(tmp_path, run_ids[0], "running")
        self._make_run(tmp_path, run_ids[1], "completed")
        self._make_run(tmp_path, run_ids[2], "failed")
        self._make_run(tmp_path, run_ids[3], "cancelled")

        terminals = list_terminal_runs(tmp_path)
        states = sorted(r["state"] for r in terminals)
        assert states == ["cancelled", "completed", "failed"]

    def test_malformed_state_file_skipped(
        self, tmp_path: Path
    ) -> None:
        """Corrupt / partially-written state files are skipped (read-
        only helper, no schema validation). This prevents the metrics
        export from aborting while a workflow is concurrently writing."""
        run_dir = tmp_path / ".ao" / "runs" / "junk"
        run_dir.mkdir(parents=True, exist_ok=True)
        (run_dir / "state.v1.json").write_text(
            "{ not valid json", encoding="utf-8"
        )
        assert list_terminal_runs(tmp_path) == []
