"""PR-C1a: context_pack_ref envelope plumbing via driver resolver.

Focus: backwards-compat defensive paths (partial records, missing
workflow fixture). Full integration testing lives in
``test_multi_step_driver.py::test_context_compile_emits_real_materialisation_payload``
which exercises the resolver end-to-end via ``simple_aokernel_flow``.
"""

from __future__ import annotations

from pathlib import Path

from ao_kernel.executor import MultiStepDriver
from ao_kernel.executor.executor import Executor
from ao_kernel.workflow.registry import WorkflowRegistry
from ao_kernel.adapters import AdapterRegistry
from ao_kernel.workflow import StepDefinition


def _minimal_driver(tmp_path: Path) -> MultiStepDriver:
    wreg = WorkflowRegistry()
    wreg.load_workspace(tmp_path)
    areg = AdapterRegistry()
    areg.load_workspace(tmp_path)
    executor = Executor(
        workspace_root=tmp_path,
        workflow_registry=wreg,
        adapter_registry=areg,
    )
    return MultiStepDriver(
        workspace_root=tmp_path,
        registry=wreg,
        adapter_registry=areg,
        executor=executor,
    )


def _adapter_step_def() -> StepDefinition:
    return StepDefinition(
        step_name="adapter_step",
        actor="adapter",
        adapter_id="codex-stub",
        required_capabilities=(),
        policy_refs=(),
        on_failure="transition_to_failed",
        timeout_seconds=60,
        human_interrupt_allowed=False,
        gate=None,
        operation=None,
    )


class TestEnvelopeResolverBackwardsCompat:
    def test_missing_workflow_id_returns_none(self, tmp_path: Path) -> None:
        """Fencing-test-style partial records (empty dict) must not
        crash the resolver; return None so executor default envelope
        applies. Regression gate for the KeyError fix."""
        driver = _minimal_driver(tmp_path)
        result = driver._build_adapter_envelope_with_context(
            run_id="00000000-0000-4000-8000-0000000aaaaa",
            step_def=_adapter_step_def(),
            record={},
        )
        assert result is None

    def test_partial_record_missing_version_returns_none(
        self, tmp_path: Path,
    ) -> None:
        """Record has workflow_id but not workflow_version (malformed
        intermediate state) → resolver returns None defensively."""
        driver = _minimal_driver(tmp_path)
        result = driver._build_adapter_envelope_with_context(
            run_id="00000000-0000-4000-8000-0000000bbbbb",
            step_def=_adapter_step_def(),
            record={"workflow_id": "some_wf", "state": "running"},
        )
        assert result is None
