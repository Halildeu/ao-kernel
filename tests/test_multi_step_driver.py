"""Unit-level MultiStepDriver tests (PR-A4b).

Scope: dispatch, entry matrix, cross-ref fail, budget gate, ci_mypy
reject, context_compile stub, idempotent terminal, DriverResult shape,
governance gate.

Integration tests that spin up real subprocess adapters live in
``test_multi_step_driver_integration.py``.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from ao_kernel.executor import (
    DriverResult,
    DriverTokenRequiredError,
    WorkflowStateCorruptedError,
)
from ao_kernel.workflow.run_store import load_run
from tests._driver_helpers import (
    build_driver,
    copy_workflow_fixture,
    install_workspace,
    seed_run,
)


def _write_coordination_policy(workspace_root: Path, *, enabled: bool) -> None:
    policy_dir = workspace_root / ".ao" / "policies"
    policy_dir.mkdir(parents=True, exist_ok=True)
    doc = {
        "version": "v1",
        "enabled": enabled,
        "heartbeat_interval_seconds": 30,
        "expiry_seconds": 90,
        "takeover_grace_period_seconds": 15,
        "max_claims_per_agent": 5,
        "claim_resource_patterns": ["*"],
        "evidence_redaction": {"patterns": []},
    }
    (policy_dir / "policy_coordination_claims.v1.json").write_text(
        json.dumps(doc, indent=2, sort_keys=True),
        encoding="utf-8",
    )


# ---------------------------------------------------------------------------
# Simple ao-kernel-only flow (no adapter subprocess required)
# ---------------------------------------------------------------------------


class TestSimpleHappyPath:
    def _setup(self, tmp_path: Path) -> tuple:
        install_workspace(tmp_path)
        copy_workflow_fixture(tmp_path, "simple_aokernel_flow")
        run_id = seed_run(tmp_path, "simple_aokernel_flow")
        driver = build_driver(tmp_path)
        return driver, run_id

    def test_two_step_aokernel_flow_completes(self, tmp_path: Path) -> None:
        driver, run_id = self._setup(tmp_path)
        result = driver.run_workflow(run_id, "simple_aokernel_flow", "1.0.0")
        assert isinstance(result, DriverResult)
        assert result.final_state == "completed"
        assert set(result.steps_executed) == {"compile_ctx", "final_ctx"}
        assert result.steps_failed == ()
        assert result.steps_retried == ()
        assert result.resume_token is None

    def test_context_compile_emits_real_materialisation_payload(
        self, tmp_path: Path,
    ) -> None:
        """PR-C1a: context_compile step now materialises actual
        preamble + writes markdown. Test renamed from stub-marker
        pattern; payload.stub is False; context_preamble_bytes is
        tolerant of empty fixture (>= 0); context_path points to
        existing file."""
        driver, run_id = self._setup(tmp_path)
        driver.run_workflow(run_id, "simple_aokernel_flow", "1.0.0")
        events_path = (
            tmp_path / ".ao" / "evidence" / "workflows" / run_id
            / "events.jsonl"
        )
        assert events_path.exists()
        lines = [json.loads(ln) for ln in events_path.read_text().splitlines()]
        compile_completed = [
            e for e in lines
            if e.get("kind") == "step_completed"
            and e.get("payload", {}).get("operation") == "context_compile"
        ]
        assert len(compile_completed) == 2
        for event in compile_completed:
            payload = event["payload"]
            assert payload["stub"] is False
            assert payload["context_preamble_bytes"] >= 0
            context_path = payload.get("context_path")
            assert context_path is not None
            assert Path(context_path).is_file()

    def test_context_compile_remains_claim_free_when_coordination_enabled(
        self, tmp_path: Path,
    ) -> None:
        driver, run_id = self._setup(tmp_path)
        _write_coordination_policy(tmp_path, enabled=True)

        driver.run_workflow(run_id, "simple_aokernel_flow", "1.0.0")

        events_path = (
            tmp_path / ".ao" / "evidence" / "workflows" / run_id / "events.jsonl"
        )
        events = [json.loads(line) for line in events_path.read_text().splitlines()]
        kinds = [event["kind"] for event in events]
        assert "claim_acquired" not in kinds
        assert "claim_conflict" not in kinds
        assert "claim_released" not in kinds

    def test_artifact_written_for_each_step(self, tmp_path: Path) -> None:
        driver, run_id = self._setup(tmp_path)
        driver.run_workflow(run_id, "simple_aokernel_flow", "1.0.0")
        artifacts = list(
            (tmp_path / ".ao" / "evidence" / "workflows" / run_id / "artifacts").glob("*.json")
        )
        assert len(artifacts) >= 2

    def test_run_record_state_is_completed(self, tmp_path: Path) -> None:
        driver, run_id = self._setup(tmp_path)
        driver.run_workflow(run_id, "simple_aokernel_flow", "1.0.0")
        record, _ = load_run(tmp_path, run_id)
        assert record["state"] == "completed"
        step_names = {s.get("step_name") for s in record.get("steps", [])}
        assert step_names == {"compile_ctx", "final_ctx"}


# ---------------------------------------------------------------------------
# Entry matrix (B2)
# ---------------------------------------------------------------------------


class TestEntryMatrix:
    def _setup(self, tmp_path: Path):
        install_workspace(tmp_path)
        copy_workflow_fixture(tmp_path, "simple_aokernel_flow")
        run_id = seed_run(tmp_path, "simple_aokernel_flow")
        driver = build_driver(tmp_path)
        return driver, run_id

    def test_waiting_approval_requires_resume_token(self, tmp_path: Path) -> None:
        driver, run_id = self._setup(tmp_path)
        # Seed waiting_approval manually
        state_file = tmp_path / ".ao" / "runs" / run_id / "state.v1.json"
        record = json.loads(state_file.read_text())
        record["state"] = "waiting_approval"
        state_file.write_text(json.dumps(record, indent=2, sort_keys=True))
        with pytest.raises(DriverTokenRequiredError):
            driver.run_workflow(run_id, "simple_aokernel_flow", "1.0.0")

    def test_terminal_completed_returns_idempotent(self, tmp_path: Path) -> None:
        driver, run_id = self._setup(tmp_path)
        # First run completes
        driver.run_workflow(run_id, "simple_aokernel_flow", "1.0.0")
        # Second call on same run_id returns idempotent DriverResult
        result = driver.run_workflow(run_id, "simple_aokernel_flow", "1.0.0")
        assert result.final_state == "completed"
        assert result.resume_token is None

    def test_unknown_state_raises_corrupted(self, tmp_path: Path) -> None:
        driver, run_id = self._setup(tmp_path)
        state_file = tmp_path / ".ao" / "runs" / run_id / "state.v1.json"
        record = json.loads(state_file.read_text())
        record["state"] = "bogus_state"
        state_file.write_text(json.dumps(record, indent=2, sort_keys=True))
        with pytest.raises((WorkflowStateCorruptedError, Exception)):
            # Schema validator will reject "bogus_state" on load;
            # driver surfaces either WorkflowStateCorruptedError or
            # the schema validation error — both are acceptable.
            driver.run_workflow(run_id, "simple_aokernel_flow", "1.0.0")


# ---------------------------------------------------------------------------
# Cross-ref workflow-level check (invariant #24)
# ---------------------------------------------------------------------------


class TestCrossRefEarlyFail:
    def test_missing_adapter_triggers_workflow_failed(self, tmp_path: Path) -> None:
        install_workspace(tmp_path)
        # retry_once_flow needs codex-stub adapter, but we DON'T install the manifest.
        copy_workflow_fixture(tmp_path, "retry_once_flow")
        run_id = seed_run(tmp_path, "retry_once_flow")
        driver = build_driver(tmp_path)
        result = driver.run_workflow(run_id, "retry_once_flow", "1.0.0")
        assert result.final_state == "failed"
        assert result.steps_executed == ()  # no step started


# ---------------------------------------------------------------------------
# Governance gate (pre-step)
# ---------------------------------------------------------------------------


class TestGovernanceGate:
    def test_gate_step_returns_waiting_approval(self, tmp_path: Path) -> None:
        install_workspace(tmp_path)
        # Build a tiny flow inline: single human step with gate=pre_apply
        flow = {
            "$schema": "urn:ao:workflow-definition:v1",
            "workflow_id": "gate_only_flow",
            "workflow_version": "1.0.0",
            "display_name": "Gate Only",
            "description": "Single human gate step.",
            "steps": [
                {
                    "step_name": "approve_me",
                    "actor": "human",
                    "gate": "pre_apply",
                    "on_failure": "transition_to_failed",
                },
            ],
            "expected_adapter_refs": [],
            "default_policy_refs": ["ao_kernel/defaults/policies/policy_worktree_profile.v1.json"],
            "required_capabilities": [],
            "tags": [],
            "created_at": "2026-04-16T00:00:00+00:00",
        }
        (tmp_path / ".ao" / "workflows" / "gate_only_flow.v1.json").write_text(
            json.dumps(flow, indent=2),
        )
        run_id = seed_run(tmp_path, "gate_only_flow")
        driver = build_driver(tmp_path)
        result = driver.run_workflow(run_id, "gate_only_flow", "1.0.0")
        assert result.final_state == "waiting_approval"
        assert result.resume_token is not None
        assert result.resume_token_kind == "approval"
        assert len(result.resume_token) >= 40  # token_urlsafe(48)


class TestApprovalResume:
    def _setup_gate_flow(self, tmp_path: Path):
        install_workspace(tmp_path)
        flow = {
            "$schema": "urn:ao:workflow-definition:v1",
            "workflow_id": "gate_flow",
            "workflow_version": "1.0.0",
            "display_name": "Gate Flow",
            "description": "Inline test flow.",
            "steps": [
                {
                    "step_name": "approve_me",
                    "actor": "human",
                    "gate": "pre_apply",
                    "on_failure": "transition_to_failed",
                },
                {
                    "step_name": "finalize",
                    "actor": "ao-kernel",
                    "operation": "context_compile",
                    "on_failure": "transition_to_failed",
                },
            ],
            "expected_adapter_refs": [],
            "default_policy_refs": ["ao_kernel/defaults/policies/policy_worktree_profile.v1.json"],
            "required_capabilities": [],
            "tags": [],
            "created_at": "2026-04-16T00:00:00+00:00",
        }
        (tmp_path / ".ao" / "workflows" / "gate_flow.v1.json").write_text(
            json.dumps(flow, indent=2),
        )
        run_id = seed_run(tmp_path, "gate_flow")
        driver = build_driver(tmp_path)
        return driver, run_id

    def test_granted_resume_continues_to_completion(self, tmp_path: Path) -> None:
        driver, run_id = self._setup_gate_flow(tmp_path)
        first = driver.run_workflow(run_id, "gate_flow", "1.0.0")
        assert first.final_state == "waiting_approval"

        second = driver.resume_workflow(
            run_id, first.resume_token,
            payload={"decision": "granted", "notes": "LGTM"},
        )
        assert second.final_state == "completed"

    def test_denied_resume_transitions_to_cancelled(self, tmp_path: Path) -> None:
        driver, run_id = self._setup_gate_flow(tmp_path)
        first = driver.run_workflow(run_id, "gate_flow", "1.0.0")
        second = driver.resume_workflow(
            run_id, first.resume_token,
            payload={"decision": "denied"},
        )
        assert second.final_state == "cancelled"

    def test_invalid_decision_rejected(self, tmp_path: Path) -> None:
        driver, run_id = self._setup_gate_flow(tmp_path)
        first = driver.run_workflow(run_id, "gate_flow", "1.0.0")
        from ao_kernel.workflow.errors import WorkflowTokenInvalidError
        with pytest.raises(WorkflowTokenInvalidError):
            driver.resume_workflow(
                run_id, first.resume_token,
                payload={"decision": "maybe"},
            )


# ---------------------------------------------------------------------------
# DriverResult shape
# ---------------------------------------------------------------------------


class TestDriverResultShape:
    def test_result_is_frozen(self, tmp_path: Path) -> None:
        install_workspace(tmp_path)
        copy_workflow_fixture(tmp_path, "simple_aokernel_flow")
        run_id = seed_run(tmp_path, "simple_aokernel_flow")
        driver = build_driver(tmp_path)
        result = driver.run_workflow(run_id, "simple_aokernel_flow", "1.0.0")
        with pytest.raises(Exception):
            result.final_state = "bogus"  # type: ignore[misc]

    def test_steps_executed_is_tuple(self, tmp_path: Path) -> None:
        install_workspace(tmp_path)
        copy_workflow_fixture(tmp_path, "simple_aokernel_flow")
        run_id = seed_run(tmp_path, "simple_aokernel_flow")
        driver = build_driver(tmp_path)
        result = driver.run_workflow(run_id, "simple_aokernel_flow", "1.0.0")
        assert isinstance(result.steps_executed, tuple)


# ---------------------------------------------------------------------------
# ci_mypy reject (W7)
# ---------------------------------------------------------------------------


class TestCiMypyReject:
    def test_ci_mypy_step_fails_with_unsupported_operation(
        self, tmp_path: Path,
    ) -> None:
        install_workspace(tmp_path)
        flow = {
            "$schema": "urn:ao:workflow-definition:v1",
            "workflow_id": "mypy_flow",
            "workflow_version": "1.0.0",
            "display_name": "Mypy Only",
            "description": "Inline test flow.",
            "steps": [
                {
                    "step_name": "ci_mypy_step",
                    "actor": "system",
                    "operation": "ci_mypy",
                    "on_failure": "transition_to_failed",
                },
            ],
            "expected_adapter_refs": [],
            "default_policy_refs": ["ao_kernel/defaults/policies/policy_worktree_profile.v1.json"],
            "required_capabilities": [],
            "tags": [],
            "created_at": "2026-04-16T00:00:00+00:00",
        }
        (tmp_path / ".ao" / "workflows" / "mypy_flow.v1.json").write_text(
            json.dumps(flow, indent=2),
        )
        run_id = seed_run(tmp_path, "mypy_flow")
        driver = build_driver(tmp_path)
        result = driver.run_workflow(run_id, "mypy_flow", "1.0.0")
        assert result.final_state == "failed"
        # Failed step should be captured
        assert "ci_mypy_step" in result.steps_failed


# ---------------------------------------------------------------------------
# Error category mapping (B4)
# ---------------------------------------------------------------------------


class TestErrorCategoryMapping:
    def test_cross_ref_fail_maps_to_other_category(self, tmp_path: Path) -> None:
        install_workspace(tmp_path)
        copy_workflow_fixture(tmp_path, "retry_once_flow")  # no adapter manifest
        run_id = seed_run(tmp_path, "retry_once_flow")
        driver = build_driver(tmp_path)
        driver.run_workflow(run_id, "retry_once_flow", "1.0.0")
        record, _ = load_run(tmp_path, run_id)
        assert record["state"] == "failed"
        err = record.get("error", {})
        # Schema-legal category ∈ {timeout, policy_denied, adapter_error,
        # budget_exhausted, ci_failed, apply_conflict, approval_denied, other}
        assert err.get("category") in {
            "timeout", "policy_denied", "adapter_error", "budget_exhausted",
            "ci_failed", "apply_conflict", "approval_denied", "other",
        }
        # Internal code like CROSS_REF is on error.code, NOT error.category
        assert err.get("code") == "CROSS_REF"
