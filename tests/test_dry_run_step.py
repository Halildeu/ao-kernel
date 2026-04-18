"""PR-C6: Executor.dry_run_step + dry_run_execution_context tests.

Contract pins:

- Run record byte-for-byte unchanged after dry-run (read-only).
- No evidence/artifact/adapter-log files materialised.
- Policy violations surface in DryRunResult instead of raising.
- ``dry_run_execution_context`` patches six executor aliases plus
  ``update_run`` to capture-and-skip semantics.
"""

from __future__ import annotations

from pathlib import Path

from ao_kernel.executor import Executor
from ao_kernel.executor.dry_run import (
    DryRunResult,
    dry_run_execution_context,
)
from ao_kernel.workflow.registry import WorkflowRegistry
from ao_kernel.adapters import AdapterRegistry

from tests._driver_helpers import (
    copy_workflow_fixture,
    install_workspace,
    seed_run,
    write_stub_adapter_manifest,
)


def _build_executor(root: Path, workflow_name: str) -> tuple[Executor, str]:
    """Minimal executor + adapter + workflow fixture + seeded run."""
    install_workspace(root)
    copy_workflow_fixture(root, workflow_name)
    write_stub_adapter_manifest(root)
    wreg = WorkflowRegistry()
    wreg.load_workspace(root)
    areg = AdapterRegistry()
    areg.load_workspace(root)
    executor = Executor(
        workspace_root=root,
        workflow_registry=wreg,
        adapter_registry=areg,
    )
    run_id = seed_run(
        root, workflow_id=workflow_name, workflow_version="1.0.0",
    )
    return executor, run_id


class TestDryRunExecutionContext:
    def test_emit_event_captured_not_written(
        self, tmp_path: Path,
    ) -> None:
        """Mock'd emit_event records to recorder + returns a stub
        EvidenceEvent with event_id + ts attrs (executor reads both).
        No events.jsonl write happens."""
        install_workspace(tmp_path)
        run_id = "00000000-0000-4000-8000-000000aaaa01"
        with dry_run_execution_context(tmp_path, run_id) as recorder:
            from ao_kernel.executor import executor as _exec_mod

            event = _exec_mod.emit_event(
                tmp_path,
                run_id=run_id,
                kind="step_started",
                actor="ao-kernel",
                payload={"step_name": "demo"},
            )
            assert hasattr(event, "event_id")
            assert hasattr(event, "ts")
            assert event.event_id.startswith("dry-run-")

        assert len(recorder.predicted_events) == 1
        kind, payload = recorder.predicted_events[0]
        assert kind == "step_started"
        assert payload == {"step_name": "demo"}

        # No events.jsonl file materialised.
        events_path = (
            tmp_path / ".ao" / "evidence" / "workflows" / run_id
            / "events.jsonl"
        )
        assert not events_path.exists()

    def test_invoke_cli_returns_canned_tuple(
        self, tmp_path: Path,
    ) -> None:
        """Mock'd invoke_cli returns (InvocationResult, Budget) tuple;
        InvocationResult has all 10 required fields."""
        install_workspace(tmp_path)
        run_id = "00000000-0000-4000-8000-000000aaaa02"
        with dry_run_execution_context(tmp_path, run_id):
            from ao_kernel.executor import executor as _exec_mod

            result_tuple = _exec_mod.invoke_cli(
                manifest=None,
                input_envelope={},
                sandbox=None,
                worktree=None,
                budget="any-budget-sentinel",
                workspace_root=tmp_path,
                run_id=run_id,
            )
        inv_result, budget_back = result_tuple
        assert inv_result.status == "ok"
        assert inv_result.diff is None
        assert inv_result.evidence_events == ()
        assert inv_result.commands_executed == ()
        assert inv_result.error is None
        assert inv_result.finish_reason == "normal"
        assert inv_result.interrupt_token is None
        assert inv_result.cost_actual == {}
        assert inv_result.stdout_path is None
        assert inv_result.stderr_path is None
        # extracted_outputs default empty mapping
        assert dict(inv_result.extracted_outputs) == {}
        # Budget passed through unchanged
        assert budget_back == "any-budget-sentinel"

    def test_write_artifact_captured_not_written(
        self, tmp_path: Path,
    ) -> None:
        install_workspace(tmp_path)
        run_id = "00000000-0000-4000-8000-000000aaaa03"
        run_dir = (
            tmp_path / ".ao" / "evidence" / "workflows" / run_id
        )
        run_dir.mkdir(parents=True, exist_ok=True)
        with dry_run_execution_context(tmp_path, run_id) as recorder:
            from ao_kernel.executor import executor as _exec_mod

            ref, sha = _exec_mod.write_artifact(
                run_dir=run_dir,
                step_id="demo_step",
                attempt=1,
                payload={"any": "thing"},
            )
        assert ref == "artifacts/demo_step-attempt1.json"
        assert sha == "dry-run-sha256-stub"
        # Artifact directory must NOT contain any file.
        artifacts_dir = run_dir / "artifacts"
        assert (
            not artifacts_dir.exists()
            or list(artifacts_dir.iterdir()) == []
        )
        # Recorder captured the would-be ref.
        assert recorder.simulated_outputs == {
            "demo_step": "artifacts/demo_step-attempt1.json",
        }


class TestDryRunStepReadOnly:
    def test_returns_dry_run_result_with_adapter_step(
        self, tmp_path: Path,
    ) -> None:
        executor, run_id = _build_executor(
            tmp_path, "adapter_plus_ci_flow",
        )
        definition = executor._workflow_registry.get(
            "adapter_plus_ci_flow", version="1.0.0",
        )
        step_def = next(
            s for s in definition.steps
            if s.step_name == "invoke_agent"
        )
        result = executor.dry_run_step(run_id, step_def)
        assert isinstance(result, DryRunResult)
        # At minimum step_started emitted before adapter invocation.
        kinds = [kind for kind, _ in result.predicted_events]
        assert "step_started" in kinds

    def test_run_record_not_mutated(self, tmp_path: Path) -> None:
        """Read-only invariant: full state.v1.json byte-for-byte
        unchanged after dry_run_step."""
        executor, run_id = _build_executor(
            tmp_path, "simple_aokernel_flow",
        )
        state_path = (
            tmp_path / ".ao" / "runs" / run_id / "state.v1.json"
        )
        before = state_path.read_bytes()

        definition = executor._workflow_registry.get(
            "simple_aokernel_flow", version="1.0.0",
        )
        step_def = definition.steps[0]
        executor.dry_run_step(run_id, step_def)

        after = state_path.read_bytes()
        assert before == after, (
            "state.v1.json bytes must not change during dry-run"
        )

    def test_no_evidence_file_written(self, tmp_path: Path) -> None:
        executor, run_id = _build_executor(
            tmp_path, "simple_aokernel_flow",
        )
        definition = executor._workflow_registry.get(
            "simple_aokernel_flow", version="1.0.0",
        )
        step_def = definition.steps[0]
        executor.dry_run_step(run_id, step_def)
        events_path = (
            tmp_path / ".ao" / "evidence" / "workflows" / run_id
            / "events.jsonl"
        )
        assert not events_path.exists()

    def test_no_artifact_directory_materialised(
        self, tmp_path: Path,
    ) -> None:
        executor, run_id = _build_executor(
            tmp_path, "adapter_plus_ci_flow",
        )
        definition = executor._workflow_registry.get(
            "adapter_plus_ci_flow", version="1.0.0",
        )
        step_def = next(
            s for s in definition.steps
            if s.step_name == "invoke_agent"
        )
        executor.dry_run_step(run_id, step_def)
        artifacts_dir = (
            tmp_path / ".ao" / "evidence" / "workflows" / run_id
            / "artifacts"
        )
        assert (
            not artifacts_dir.exists()
            or list(artifacts_dir.iterdir()) == []
        )

    def test_no_adapter_log_written(self, tmp_path: Path) -> None:
        """PR-C6 v3 W3 absorb: adapter-<id>.jsonl not created
        during dry-run (invoke_cli path fully mocked)."""
        executor, run_id = _build_executor(
            tmp_path, "adapter_plus_ci_flow",
        )
        definition = executor._workflow_registry.get(
            "adapter_plus_ci_flow", version="1.0.0",
        )
        step_def = next(
            s for s in definition.steps
            if s.step_name == "invoke_agent"
        )
        executor.dry_run_step(run_id, step_def)
        adapter_log = (
            tmp_path / ".ao" / "evidence" / "workflows" / run_id
            / "adapter-codex-stub.jsonl"
        )
        assert not adapter_log.exists()
