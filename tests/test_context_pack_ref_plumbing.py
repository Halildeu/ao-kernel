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


class TestEnvelopeResolverSuccessPath:
    """PR-C1a post-impl B2 absorb: resolver end-to-end success lock.

    Simulates a workflow with context_compile → adapter chain; verifies
    `_build_adapter_envelope_with_context()` reads the prior step's
    artifact JSON, extracts `context_path`, and returns envelope
    override with the absolute path bound to `context_pack_ref`.
    """

    def test_resolver_forwards_context_path_from_artifact(
        self, tmp_path: Path,
    ) -> None:
        """Unit-level resolver success path: mock the workflow registry
        so this test doesn't depend on fixture loading plumbing.
        Exercises the full chain: compile_step_names lookup → steps
        list iteration → artifact JSON read → context_path extraction →
        envelope override."""
        import json
        from unittest.mock import MagicMock

        # 1. Fake workflow_def with context_compile + adapter steps.
        fake_steps = [
            MagicMock(step_name="compile_ctx", operation="context_compile"),
            MagicMock(step_name="adapter_step", operation=None),
        ]
        fake_workflow_def = MagicMock()
        fake_workflow_def.steps = fake_steps

        # 2. Write canned context artifact + markdown as if prior
        #    context_compile step had just completed.
        run_id = "00000000-0000-4000-8000-000000ddddd1"
        run_dir = (
            tmp_path / ".ao" / "evidence" / "workflows" / run_id
        )
        artifacts_dir = run_dir / "artifacts"
        artifacts_dir.mkdir(parents=True, exist_ok=True)
        context_md_path = run_dir / "context-compile_ctx-attempt1.md"
        context_md_path.write_text(
            "# Run Context\n\nTest preamble body.\n",
            encoding="utf-8",
        )
        artifact_json_path = (
            artifacts_dir / "compile_ctx-attempt1.json"
        )
        artifact_json_path.write_text(
            json.dumps({
                "operation": "context_compile",
                "stub": False,
                "context_preamble_bytes": 27,
                "context_path": str(context_md_path),
            }),
            encoding="utf-8",
        )

        # 3. Build driver + inject mock registry.
        driver = _minimal_driver(tmp_path)
        driver._registry.get = MagicMock(return_value=fake_workflow_def)

        record = {
            "workflow_id": "ctx_plus_adapter_flow",
            "workflow_version": "1.0.0",
            "state": "running",
            "intent": {"payload": "do the adapter thing"},
            "steps": [
                {
                    "step_name": "compile_ctx",
                    "state": "completed",
                    "output_ref": "artifacts/compile_ctx-attempt1.json",
                },
            ],
        }
        step_def = _adapter_step_def()

        # 4. Resolver reads artifact JSON and builds envelope override.
        result = driver._build_adapter_envelope_with_context(
            run_id=run_id, step_def=step_def, record=record,
        )
        assert result == {
            "task_prompt": "do the adapter thing",
            "run_id": run_id,
            "context_pack_ref": str(context_md_path),
        }
        # Absolute path invariant: adapter subprocess reads from worktree
        # cwd via plain string replacement, so path must resolve regardless.
        assert Path(result["context_pack_ref"]).is_absolute()
        assert Path(result["context_pack_ref"]).is_file()
