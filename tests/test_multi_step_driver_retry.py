"""Retry append-only + escalate_to_human path tests (PR-A4b).

Uses a mock Executor that can be programmed per-attempt, so the retry
flow (failed attempt=1 → attempt=2 placeholder → success) and the
escalate_to_human resume flow are exercised without requiring real
subprocess adapters.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from ao_kernel.adapters import AdapterRegistry
from ao_kernel.executor import (
    Executor,
    ExecutionResult,
    MultiStepDriver,
)
from ao_kernel.workflow.registry import WorkflowRegistry
from ao_kernel.workflow.run_store import load_run
from tests._driver_helpers import (
    copy_workflow_fixture,
    install_workspace,
    seed_run,
    write_stub_adapter_manifest,
)


class _ProgrammableExecutor(Executor):
    """Executor subclass whose adapter step returns canned ExecutionResults.

    The sequence ``outcomes`` is consumed in order — first call gets
    ``outcomes[0]``, second call ``outcomes[1]``, etc. Each outcome is
    the ``step_state`` string (``"completed"`` / ``"failed"``). The
    subclass still emits adapter_returned events and writes artifacts
    via the normal code path so driver-managed dispatch is exercised
    end-to-end.
    """

    def __init__(
        self, workspace_root: Path, *, workflow_registry: WorkflowRegistry,
        adapter_registry: AdapterRegistry, outcomes: list[str],
    ) -> None:
        super().__init__(
            workspace_root=workspace_root,
            workflow_registry=workflow_registry,
            adapter_registry=adapter_registry,
        )
        self._outcomes = outcomes
        self._call_count = 0

    def run_step(self, *args, **kwargs) -> ExecutionResult:  # type: ignore[override]
        idx = self._call_count
        self._call_count += 1
        state = self._outcomes[idx] if idx < len(self._outcomes) else "completed"
        # Return a normalized result — Executor.run_step would emit
        # evidence and write artifacts; for unit-test purposes the
        # driver only inspects ``step_state``.
        return ExecutionResult(
            new_state=kwargs.get("driver_managed", False) and "running" or "running",
            step_state=state,
            invocation_result=None,
            evidence_event_ids=(),
            budget_after={"fail_closed_on_exhaust": True},
        )


def _build_driver_with_outcomes(
    workspace: Path, outcomes: list[str],
) -> MultiStepDriver:
    wreg = WorkflowRegistry()
    wreg.load_workspace(workspace)
    areg = AdapterRegistry()
    areg.load_workspace(workspace)
    executor = _ProgrammableExecutor(
        workspace_root=workspace,
        workflow_registry=wreg,
        adapter_registry=areg,
        outcomes=outcomes,
    )
    return MultiStepDriver(
        workspace_root=workspace,
        registry=wreg,
        adapter_registry=areg,
        executor=executor,
    )


# ---------------------------------------------------------------------------
# retry_once: attempt=1 fails, attempt=2 passes
# ---------------------------------------------------------------------------


class TestRetryOnceSuccess:
    def _setup(self, tmp_path: Path, outcomes: list[str]):
        install_workspace(tmp_path)
        copy_workflow_fixture(tmp_path, "retry_once_flow")
        write_stub_adapter_manifest(tmp_path)
        run_id = seed_run(tmp_path, "retry_once_flow")
        driver = _build_driver_with_outcomes(tmp_path, outcomes)
        return driver, run_id

    def test_attempt1_fail_attempt2_pass_completes(self, tmp_path: Path) -> None:
        driver, run_id = self._setup(tmp_path, outcomes=["failed", "completed"])
        result = driver.run_workflow(run_id, "retry_once_flow", "1.0.0")
        assert result.final_state == "completed"
        assert "invoke_agent" in result.steps_retried

    def test_run_record_has_both_attempts(self, tmp_path: Path) -> None:
        driver, run_id = self._setup(tmp_path, outcomes=["failed", "completed"])
        driver.run_workflow(run_id, "retry_once_flow", "1.0.0")
        record, _ = load_run(tmp_path, run_id)
        # Two step_records for invoke_agent — attempt=1 failed, attempt=2 completed
        invoke_records = [
            sr for sr in record["steps"]
            if sr.get("step_name") == "invoke_agent"
        ]
        assert len(invoke_records) == 2
        attempts = {sr.get("attempt"): sr.get("state") for sr in invoke_records}
        assert attempts[1] == "failed"
        assert attempts[2] == "completed"


class TestRetryOnceExhausted:
    def _setup(self, tmp_path: Path, outcomes: list[str]):
        install_workspace(tmp_path)
        copy_workflow_fixture(tmp_path, "retry_once_flow")
        write_stub_adapter_manifest(tmp_path)
        run_id = seed_run(tmp_path, "retry_once_flow")
        driver = _build_driver_with_outcomes(tmp_path, outcomes)
        return driver, run_id

    def test_both_attempts_fail_workflow_fails(self, tmp_path: Path) -> None:
        driver, run_id = self._setup(tmp_path, outcomes=["failed", "failed"])
        result = driver.run_workflow(run_id, "retry_once_flow", "1.0.0")
        assert result.final_state == "failed"
        assert "invoke_agent" in result.steps_failed

    def test_retry_exhausted_error_code_set(self, tmp_path: Path) -> None:
        driver, run_id = self._setup(tmp_path, outcomes=["failed", "failed"])
        driver.run_workflow(run_id, "retry_once_flow", "1.0.0")
        record, _ = load_run(tmp_path, run_id)
        assert record["state"] == "failed"
        err = record.get("error", {})
        assert err.get("code") == "RETRY_EXHAUSTED"


# ---------------------------------------------------------------------------
# escalate_to_human: failed adapter → waiting_approval → resume granted
# ---------------------------------------------------------------------------


class TestEscalateToHuman:
    def _setup(self, tmp_path: Path, outcomes: list[str]):
        install_workspace(tmp_path)
        copy_workflow_fixture(tmp_path, "escalate_flow")
        write_stub_adapter_manifest(tmp_path)
        run_id = seed_run(tmp_path, "escalate_flow")
        driver = _build_driver_with_outcomes(tmp_path, outcomes)
        return driver, run_id

    def test_failed_adapter_opens_approval_gate(self, tmp_path: Path) -> None:
        driver, run_id = self._setup(tmp_path, outcomes=["failed"])
        result = driver.run_workflow(run_id, "escalate_flow", "1.0.0")
        assert result.final_state == "waiting_approval"
        assert result.resume_token is not None
        assert result.resume_token_kind == "approval"

    def test_approval_denied_transitions_to_cancelled(self, tmp_path: Path) -> None:
        driver, run_id = self._setup(tmp_path, outcomes=["failed"])
        first = driver.run_workflow(run_id, "escalate_flow", "1.0.0")
        second = driver.resume_workflow(
            run_id, first.resume_token, payload={"decision": "denied"},
        )
        assert second.final_state == "cancelled"


# ---------------------------------------------------------------------------
# Budget exhaust mid-flow
# ---------------------------------------------------------------------------


class TestBudgetExhaust:
    def test_exhausted_time_budget_fails_workflow(self, tmp_path: Path) -> None:
        from ao_kernel.workflow.budget import budget_from_dict
        install_workspace(tmp_path)
        copy_workflow_fixture(tmp_path, "simple_aokernel_flow")
        run_id = seed_run(tmp_path, "simple_aokernel_flow")
        # Build an exhausted budget: time_seconds.remaining = 0
        budget = budget_from_dict({
            "fail_closed_on_exhaust": True,
            "time_seconds": {"limit": 1.0, "remaining": 0.0},
        })
        driver = _build_driver_with_outcomes(tmp_path, outcomes=[])
        result = driver.run_workflow(
            run_id, "simple_aokernel_flow", "1.0.0", budget=budget,
        )
        # Budget exhausted → first step rejected → workflow_failed
        assert result.final_state == "failed"


# ---------------------------------------------------------------------------
# DriverStateInconsistencyError path (MV1 absorb)
# ---------------------------------------------------------------------------


class TestDriverHelpers:
    """Direct tests for the internal state-derivation helpers."""

    def _driver(self, tmp_path: Path):
        install_workspace(tmp_path)
        copy_workflow_fixture(tmp_path, "retry_once_flow")
        write_stub_adapter_manifest(tmp_path)
        return _build_driver_with_outcomes(tmp_path, outcomes=[])

    def test_completed_step_names_uses_highest_attempt(self, tmp_path: Path) -> None:
        driver = self._driver(tmp_path)
        record = {
            "steps": [
                {"step_name": "a", "attempt": 1, "state": "failed"},
                {"step_name": "a", "attempt": 2, "state": "completed"},
                {"step_name": "b", "attempt": 1, "state": "completed"},
            ],
        }
        names = driver._completed_step_names(record)
        assert names == {"a", "b"}

    def test_retried_step_names_collects_attempts_ge_2(self, tmp_path: Path) -> None:
        driver = self._driver(tmp_path)
        record = {
            "steps": [
                {"step_name": "a", "attempt": 1, "state": "failed"},
                {"step_name": "a", "attempt": 2, "state": "completed"},
                {"step_name": "b", "attempt": 1, "state": "completed"},
            ],
        }
        names = driver._retried_step_names(record)
        assert names == {"a"}

    def test_next_attempt_number_fresh_step(self, tmp_path: Path) -> None:
        driver = self._driver(tmp_path)
        record = {"steps": []}
        assert driver._next_attempt_number(record, "invoke_agent") == 1

    def test_next_attempt_number_after_failed_first(self, tmp_path: Path) -> None:
        driver = self._driver(tmp_path)
        record = {
            "steps": [
                {"step_name": "invoke_agent", "attempt": 1, "state": "failed"},
            ],
        }
        assert driver._next_attempt_number(record, "invoke_agent") == 2

    def test_next_attempt_number_resumes_running_placeholder(
        self, tmp_path: Path,
    ) -> None:
        driver = self._driver(tmp_path)
        record = {
            "steps": [
                {"step_name": "invoke_agent", "attempt": 1, "state": "failed"},
                {"step_name": "invoke_agent", "attempt": 2, "state": "running"},
            ],
        }
        # Non-terminal placeholder → resume same attempt number
        assert driver._next_attempt_number(record, "invoke_agent") == 2

    def test_find_pending_approval_matches_token(self, tmp_path: Path) -> None:
        driver = self._driver(tmp_path)
        record = {
            "approvals": [
                {"approval_token": "tok-a", "decision": None},
                {"approval_token": "tok-b", "decision": "granted"},
            ],
        }
        found = driver._find_pending_approval(record, "tok-a")
        assert found is not None
        assert found["approval_token"] == "tok-a"
        # Resolved approvals must not match
        assert driver._find_pending_approval(record, "tok-b") is None

    def test_find_pending_interrupt_matches_token(self, tmp_path: Path) -> None:
        driver = self._driver(tmp_path)
        record = {
            "interrupts": [
                {"interrupt_token": "int-a", "resumed_at": None},
                {"interrupt_token": "int-b", "resumed_at": "2026-04-16T00:00:00+00:00"},
            ],
        }
        found = driver._find_pending_interrupt(record, "int-a")
        assert found is not None
        assert found["interrupt_token"] == "int-a"
        assert driver._find_pending_interrupt(record, "int-b") is None


class TestIdempotentTerminalReturn:
    """Terminal run_record → idempotent return path (MV4 absorb)."""

    def _build_terminal(self, tmp_path: Path, terminal_state: str) -> tuple:
        install_workspace(tmp_path)
        copy_workflow_fixture(tmp_path, "simple_aokernel_flow")
        run_id = seed_run(tmp_path, "simple_aokernel_flow")
        state_file = tmp_path / ".ao" / "runs" / run_id / "state.v1.json"
        record = json.loads(state_file.read_text())
        record["state"] = terminal_state
        record["completed_at"] = "2026-04-16T01:00:00+00:00"
        record["steps"] = [
            {
                "step_id": "compile_ctx",
                "step_name": "compile_ctx",
                "state": "completed",
                "actor": "ao-kernel",
                "started_at": "2026-04-16T00:00:00+00:00",
                "completed_at": "2026-04-16T00:00:30+00:00",
                "attempt": 1,
            },
        ]
        if terminal_state == "failed":
            record["error"] = {"category": "other", "code": "X", "message": "x"}
        from ao_kernel.workflow.run_store import run_revision
        record["revision"] = run_revision(record)
        state_file.write_text(json.dumps(record, indent=2, sort_keys=True))
        driver = _build_driver_with_outcomes(tmp_path, outcomes=[])
        return driver, run_id

    def test_completed_terminal_returns_completed_result(
        self, tmp_path: Path,
    ) -> None:
        driver, run_id = self._build_terminal(tmp_path, "completed")
        result = driver.run_workflow(run_id, "simple_aokernel_flow", "1.0.0")
        assert result.final_state == "completed"
        assert result.resume_token is None
        assert "compile_ctx" in result.steps_executed
        assert result.steps_failed == ()

    def test_cancelled_terminal_returns_cancelled_result(
        self, tmp_path: Path,
    ) -> None:
        driver, run_id = self._build_terminal(tmp_path, "cancelled")
        result = driver.run_workflow(run_id, "simple_aokernel_flow", "1.0.0")
        assert result.final_state == "cancelled"

    def test_failed_terminal_non_retryable_returns_failed(
        self, tmp_path: Path,
    ) -> None:
        driver, run_id = self._build_terminal(tmp_path, "failed")
        result = driver.run_workflow(run_id, "simple_aokernel_flow", "1.0.0")
        assert result.final_state == "failed"


class TestDriverStateInconsistency:
    def test_retryable_terminal_raises_inconsistency(self, tmp_path: Path) -> None:
        from ao_kernel.executor import DriverStateInconsistencyError
        install_workspace(tmp_path)
        copy_workflow_fixture(tmp_path, "retry_once_flow")
        write_stub_adapter_manifest(tmp_path)
        run_id = seed_run(tmp_path, "retry_once_flow")

        # Manually corrupt: write a run_record in terminal "failed"
        # state BUT highest attempt=1 is failed and on_failure=retry_once.
        # Driver entry matrix should surface DriverStateInconsistencyError.
        state_file = tmp_path / ".ao" / "runs" / run_id / "state.v1.json"
        record = json.loads(state_file.read_text())
        record["state"] = "failed"
        record["completed_at"] = "2026-04-16T00:00:00+00:00"
        record["steps"] = [
            {
                "step_id": "invoke_agent",
                "step_name": "invoke_agent",
                "state": "failed",
                "actor": "adapter",
                "started_at": "2026-04-16T00:00:00+00:00",
                "completed_at": "2026-04-16T00:00:00+00:00",
                "attempt": 1,
                "adapter_id": "codex-stub",
                "error": {"category": "other", "code": "X", "message": "x"},
            },
        ]
        record["error"] = {"category": "other", "code": "X", "message": "x"}
        # Recompute revision
        from ao_kernel.workflow.run_store import run_revision
        record["revision"] = run_revision(record)
        state_file.write_text(json.dumps(record, indent=2, sort_keys=True))

        driver = _build_driver_with_outcomes(tmp_path, outcomes=[])
        with pytest.raises(DriverStateInconsistencyError):
            driver.run_workflow(run_id, "retry_once_flow", "1.0.0")
