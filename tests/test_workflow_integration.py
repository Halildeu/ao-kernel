"""End-to-end integration tests for ``ao_kernel.workflow``.

Exercises the full module stack (state machine → budget → primitives →
schema validator → run store) against the
``tests/fixtures/workflow_bug_fix_stub.json`` fixture.

No external dependencies (no LLM, no network). The bug_fix_flow stub
represents a realistic happy-path run record after the final transition
to ``completed``; tests use it to prove the load / validate / replay
boundary and to drive a fresh ``create → transitions → completed``
sequence that stays schema-valid at every step.
"""

from __future__ import annotations

import json
import uuid
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest

from ao_kernel.workflow import (
    TERMINAL_STATES,
    TRANSITIONS,
    WorkflowBudgetExhaustedError,
    budget_from_dict,
    budget_to_dict,
    create_approval,
    create_interrupt,
    create_run,
    is_exhausted,
    load_run,
    record_spend,
    resume_approval,
    run_revision,
    update_run,
    validate_transition,
    validate_workflow_run,
)

_FIXTURE_PATH = Path(__file__).parent / "fixtures" / "workflow_bug_fix_stub.json"


def _load_fixture() -> dict[str, Any]:
    with _FIXTURE_PATH.open(encoding="utf-8") as f:
        data: dict[str, Any] = json.load(f)
    return data


class TestFixture:
    def test_fixture_validates_against_schema(self) -> None:
        fixture = _load_fixture()
        assert validate_workflow_run(fixture) is None

    def test_fixture_matches_bug_fix_flow_structure(self) -> None:
        """Fixture shape reflects a completed bug_fix_flow run."""
        fixture = _load_fixture()
        assert fixture["workflow_id"] == "bug_fix_flow"
        assert fixture["state"] == "completed"
        assert fixture["state"] in TERMINAL_STATES
        # 8 steps cover the DEMO-SCRIPT.md 11-step flow collapsed to
        # run-level orchestrator / adapter actions.
        assert len(fixture["steps"]) == 8
        assert all(s["state"] == "completed" for s in fixture["steps"])

    def test_fixture_adapters_and_policies_present(self) -> None:
        fixture = _load_fixture()
        assert set(fixture["adapter_refs"]) == {"codex-stub", "gh-cli-pr"}
        adapter_step_ids = {
            s["adapter_id"] for s in fixture["steps"] if s["actor"] == "adapter"
        }
        assert adapter_step_ids == {"codex-stub", "gh-cli-pr"}
        assert any(
            "policy_worktree_profile" in ref
            for ref in fixture["policy_refs"]
        )

    def test_state_machine_visits_from_created(self) -> None:
        """Synthesize a hand-written trace of the canonical bug-fix path
        and check every transition is legal per TRANSITIONS."""
        path = [
            "created",
            "running",
            "applying",
            "verifying",
            "completed",
        ]
        for prev, nxt in zip(path, path[1:]):
            assert nxt in TRANSITIONS[prev]
            validate_transition(prev, nxt)


class TestLifecycle:
    def test_create_transitions_budget_complete(self, tmp_path: Path) -> None:
        """End-to-end: create → running → verifying → completed with budget tracking."""
        run_id = str(uuid.uuid4())
        rec, _rev = create_run(
            tmp_path,
            run_id=run_id,
            workflow_id="bug_fix_flow",
            workflow_version="1.0.0",
            intent={"kind": "inline_prompt", "payload": "integration"},
            budget={
                "tokens": {"limit": 1000, "spent": 0, "remaining": 1000},
                "cost_usd": {"limit": 1.00, "spent": 0.0, "remaining": 1.00},
                "fail_closed_on_exhaust": True,
            },
            policy_refs=[
                "ao_kernel/defaults/policies/policy_worktree_profile.v1.json"
            ],
            evidence_refs=[
                f".ao/evidence/workflows/{run_id}/events.jsonl"
            ],
            adapter_refs=["codex-stub"],
        )
        assert rec["state"] == "created"

        # created -> running
        def _to_running(r: dict[str, Any]) -> dict[str, Any]:
            validate_transition(r["state"], "running")
            r["state"] = "running"
            r["started_at"] = "2026-04-15T12:01:00+03:00"
            return r

        rec, _ = update_run(tmp_path, run_id, mutator=_to_running)
        assert rec["state"] == "running"

        # running -> applying (skipping interrupt/approval for brevity)
        def _to_applying(r: dict[str, Any]) -> dict[str, Any]:
            validate_transition(r["state"], "applying")
            # Spend some budget along the way
            budget = budget_from_dict(r["budget"])
            budget = record_spend(
                budget, tokens=250, cost_usd=Decimal("0.15"), run_id=run_id
            )
            r["budget"] = budget_to_dict(budget)
            r["state"] = "applying"
            return r

        rec, _ = update_run(tmp_path, run_id, mutator=_to_applying)
        assert rec["state"] == "applying"
        assert rec["budget"]["tokens"]["spent"] == 250

        # applying -> verifying -> completed
        def _to_verifying(r: dict[str, Any]) -> dict[str, Any]:
            validate_transition(r["state"], "verifying")
            r["state"] = "verifying"
            return r

        rec, _ = update_run(tmp_path, run_id, mutator=_to_verifying)

        def _to_completed(r: dict[str, Any]) -> dict[str, Any]:
            validate_transition(r["state"], "completed")
            r["state"] = "completed"
            r["completed_at"] = "2026-04-15T12:05:00+03:00"
            return r

        rec, _ = update_run(tmp_path, run_id, mutator=_to_completed)
        assert rec["state"] == "completed"

        # Round-trip through load_run; revision stable.
        rec2, rev2 = load_run(tmp_path, run_id)
        assert rec2["state"] == "completed"
        assert run_revision(rec2) == rev2

    def test_budget_exhaustion_prevents_further_spend(self, tmp_path: Path) -> None:
        run_id = str(uuid.uuid4())
        rec, _ = create_run(
            tmp_path,
            run_id=run_id,
            workflow_id="bug_fix_flow",
            workflow_version="1.0.0",
            intent={"kind": "inline_prompt", "payload": "x"},
            budget={
                "tokens": {"limit": 10, "spent": 0, "remaining": 10},
                "fail_closed_on_exhaust": True,
            },
            policy_refs=[
                "ao_kernel/defaults/policies/policy_worktree_profile.v1.json"
            ],
            evidence_refs=[f".ao/evidence/workflows/{run_id}/events.jsonl"],
        )

        def _spend_all(r: dict[str, Any]) -> dict[str, Any]:
            budget = budget_from_dict(r["budget"])
            budget = record_spend(budget, tokens=10, run_id=run_id)
            r["budget"] = budget_to_dict(budget)
            return r

        rec, _ = update_run(tmp_path, run_id, mutator=_spend_all)
        assert is_exhausted(budget_from_dict(rec["budget"])) == (True, "tokens")

        # Next positive spend raises mid-mutation; record is unchanged.
        def _over_spend(r: dict[str, Any]) -> dict[str, Any]:
            budget = budget_from_dict(r["budget"])
            budget = record_spend(budget, tokens=1, run_id=run_id)
            r["budget"] = budget_to_dict(budget)
            return r

        with pytest.raises(WorkflowBudgetExhaustedError):
            update_run(tmp_path, run_id, mutator=_over_spend)

        # Record still reflects the exhausted budget, not over-spent.
        rec2, _ = load_run(tmp_path, run_id)
        assert rec2["budget"]["tokens"]["remaining"] == 0
        assert rec2["budget"]["tokens"]["spent"] == 10


class TestPrimitivesInContext:
    def test_interrupt_and_approval_tokens_distinct(self) -> None:
        ir = create_interrupt("codex-stub", {"q": "continue?"})
        ap = create_approval(gate="pre_apply", actor="halildeu")
        assert ir.interrupt_token != ap.approval_token

    def test_approval_resume_updates_decision_in_run(self, tmp_path: Path) -> None:
        run_id = str(uuid.uuid4())
        _, _ = create_run(
            tmp_path,
            run_id=run_id,
            workflow_id="bug_fix_flow",
            workflow_version="1.0.0",
            intent={"kind": "inline_prompt", "payload": "x"},
            budget={"fail_closed_on_exhaust": True},
            policy_refs=[
                "ao_kernel/defaults/policies/policy_worktree_profile.v1.json"
            ],
            evidence_refs=[f".ao/evidence/workflows/{run_id}/events.jsonl"],
        )
        approval = create_approval(gate="pre_apply", actor="halildeu")
        granted = resume_approval(
            approval, token=approval.approval_token, decision="granted"
        )
        assert granted.decision == "granted"
        # Persist the approval as part of the run (schema approvals list).
        def _attach(r: dict[str, Any]) -> dict[str, Any]:
            r.setdefault("approvals", [])
            r["approvals"].append(
                {
                    "approval_id": granted.approval_id,
                    "approval_token": granted.approval_token,
                    "gate": granted.gate,
                    "requested_at": granted.requested_at,
                    "responded_at": granted.responded_at,
                    "decision": granted.decision,
                    "actor": granted.actor,
                    "payload": dict(granted.payload),
                }
            )
            return r

        rec, _ = update_run(tmp_path, run_id, mutator=_attach)
        assert len(rec["approvals"]) == 1
        assert rec["approvals"][0]["decision"] == "granted"
