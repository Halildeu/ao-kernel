"""Tests for PR-A4a registry operation parsing + cross-ref guards.

Scope:
- ``StepDefinition.operation`` field is parsed from workflow JSON
- ``CrossRefIssue(kind="operation_required")`` fires when
  ``actor in {ao-kernel, system}`` has no ``operation``
- ``CrossRefIssue(kind="invalid_on_failure_for_operation")`` fires
  when ``actor=ao-kernel AND operation=patch_apply AND
  on_failure=escalate_to_human``
- Schema-level conditional rejects the same combination at load time
  (defence-in-depth); loader-level guards catch it structurally
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ao_kernel.workflow.registry import (
    CrossRefIssue,
    StepDefinition,
    WorkflowRegistry,
)


class _StubAdapterRegistry:
    """Duck-typed stand-in for AdapterRegistry — mirrors test_workflow_registry."""

    def __init__(self, manifests: dict[str, frozenset[str]]) -> None:
        self._manifests = manifests

    def get(self, adapter_id: str):  # noqa: ANN001 - duck typing OK for tests
        if adapter_id not in self._manifests:
            raise KeyError(adapter_id)
        return type("_Manifest", (), {"capabilities": self._manifests[adapter_id]})()

    def missing_capabilities(self, adapter_id: str, required) -> frozenset[str]:
        caps = self._manifests[adapter_id]
        return frozenset(required) - caps


def _write_definition(workspace_root: Path, payload: dict[str, Any]) -> Path:
    dir_path = workspace_root / ".ao" / "workflows"
    dir_path.mkdir(parents=True, exist_ok=True)
    out = dir_path / f"{payload['workflow_id']}.v1.json"
    out.write_text(json.dumps(payload), encoding="utf-8")
    return out


def _base_definition(**overrides: Any) -> dict[str, Any]:
    defn = {
        "workflow_id": "ops_flow",
        "workflow_version": "1.0.0",
        "display_name": "Ops",
        "description": "Test ops flow",
        "steps": [
            {
                "step_name": "compile_ctx",
                "actor": "ao-kernel",
                "operation": "context_compile",
                "on_failure": "transition_to_failed",
            },
        ],
        "expected_adapter_refs": [],
        "default_policy_refs": [
            "ao_kernel/defaults/policies/policy_worktree_profile.v1.json"
        ],
        "created_at": "2026-04-15T00:00:00+00:00",
    }
    defn.update(overrides)
    return defn


class TestOperationParsing:
    def test_parses_operation_when_present(self, tmp_path: Path) -> None:
        _write_definition(tmp_path, _base_definition())
        reg = WorkflowRegistry()
        reg.load_workspace(tmp_path)
        defn = reg.get("ops_flow", version="1.0.0")
        assert defn.steps[0].operation == "context_compile"

    def test_operation_is_none_for_adapter_steps(self, tmp_path: Path) -> None:
        payload = _base_definition(
            steps=[
                {
                    "step_name": "call_agent",
                    "actor": "adapter",
                    "adapter_id": "codex-stub",
                    "required_capabilities": [],
                    "on_failure": "transition_to_failed",
                },
            ],
            expected_adapter_refs=["codex-stub"],
        )
        _write_definition(tmp_path, payload)
        reg = WorkflowRegistry()
        reg.load_workspace(tmp_path)
        defn = reg.get("ops_flow", version="1.0.0")
        assert defn.steps[0].operation is None

    def test_parses_ci_operations(self, tmp_path: Path) -> None:
        payload = _base_definition(
            steps=[
                {
                    "step_name": "ci_tests",
                    "actor": "system",
                    "operation": "ci_pytest",
                    "on_failure": "transition_to_failed",
                },
                {
                    "step_name": "ci_lint",
                    "actor": "system",
                    "operation": "ci_ruff",
                    "on_failure": "transition_to_failed",
                },
            ],
        )
        _write_definition(tmp_path, payload)
        reg = WorkflowRegistry()
        reg.load_workspace(tmp_path)
        defn = reg.get("ops_flow", version="1.0.0")
        assert defn.steps[0].operation == "ci_pytest"
        assert defn.steps[1].operation == "ci_ruff"


class TestSchemaRejects:
    def test_missing_operation_for_ao_kernel_is_rejected_by_schema(
        self, tmp_path: Path,
    ) -> None:
        payload = _base_definition(
            steps=[
                {
                    "step_name": "orphan",
                    "actor": "ao-kernel",
                    # operation intentionally missing
                    "on_failure": "transition_to_failed",
                },
            ],
        )
        _write_definition(tmp_path, payload)
        reg = WorkflowRegistry()
        report = reg.load_workspace(tmp_path)
        # Schema validation must reject this definition
        assert len(report.skipped) == 1
        assert report.skipped[0].reason == "schema_invalid"

    def test_operation_not_allowed_for_adapter_actor(
        self, tmp_path: Path,
    ) -> None:
        payload = _base_definition(
            steps=[
                {
                    "step_name": "call_agent",
                    "actor": "adapter",
                    "adapter_id": "codex-stub",
                    "operation": "patch_apply",  # forbidden on adapter
                    "on_failure": "transition_to_failed",
                },
            ],
            expected_adapter_refs=["codex-stub"],
        )
        _write_definition(tmp_path, payload)
        reg = WorkflowRegistry()
        report = reg.load_workspace(tmp_path)
        assert len(report.skipped) == 1
        assert report.skipped[0].reason == "schema_invalid"

    def test_patch_apply_with_escalate_to_human_rejected_by_schema(
        self, tmp_path: Path,
    ) -> None:
        payload = _base_definition(
            steps=[
                {
                    "step_name": "apply_patch",
                    "actor": "ao-kernel",
                    "operation": "patch_apply",
                    "on_failure": "escalate_to_human",  # forbidden combo
                },
            ],
        )
        _write_definition(tmp_path, payload)
        reg = WorkflowRegistry()
        report = reg.load_workspace(tmp_path)
        assert len(report.skipped) == 1
        assert report.skipped[0].reason == "schema_invalid"


class TestCrossRefGuardsAreDefenceInDepth:
    """Schema already rejects the invalid cases at load time; these tests
    construct StepDefinition directly to verify the registry-level guard
    still fires (defence-in-depth per CNS-023 MV2 answer)."""

    def _direct_definition(self, step: StepDefinition) -> Any:
        """Build a WorkflowDefinition-like object by hand."""
        from ao_kernel.workflow.registry import WorkflowDefinition

        return WorkflowDefinition(
            workflow_id="direct_flow",
            workflow_version="1.0.0",
            display_name="Direct",
            description="Direct",
            steps=(step,),
            expected_adapter_refs=(),
            default_policy_refs=(),
            required_capabilities=(),
            tags=(),
            source="workspace",
            source_path=Path("/tmp/direct.v1.json"),
        )

    def test_operation_required_fires_for_ao_kernel_without_operation(self) -> None:
        step = StepDefinition(
            step_name="orphan",
            actor="ao-kernel",
            adapter_id=None,
            required_capabilities=(),
            policy_refs=(),
            on_failure="transition_to_failed",
            timeout_seconds=None,
            human_interrupt_allowed=False,
            gate=None,
            operation=None,  # direct bypass
        )
        defn = self._direct_definition(step)
        reg = WorkflowRegistry()
        issues = reg.validate_cross_refs(defn, _StubAdapterRegistry({}))
        kinds = {i.kind for i in issues}
        assert "operation_required" in kinds
        op_issue = next(i for i in issues if i.kind == "operation_required")
        assert op_issue.step_name == "orphan"

    def test_invalid_on_failure_for_operation_fires(self) -> None:
        step = StepDefinition(
            step_name="apply_patch",
            actor="ao-kernel",
            adapter_id=None,
            required_capabilities=(),
            policy_refs=(),
            on_failure="escalate_to_human",  # forbidden for patch_apply
            timeout_seconds=None,
            human_interrupt_allowed=False,
            gate=None,
            operation="patch_apply",
        )
        defn = self._direct_definition(step)
        reg = WorkflowRegistry()
        issues = reg.validate_cross_refs(defn, _StubAdapterRegistry({}))
        kinds = {i.kind for i in issues}
        assert "invalid_on_failure_for_operation" in kinds

    def test_no_guards_fire_for_valid_ao_kernel_step(self) -> None:
        step = StepDefinition(
            step_name="apply_patch",
            actor="ao-kernel",
            adapter_id=None,
            required_capabilities=(),
            policy_refs=(),
            on_failure="retry_once",
            timeout_seconds=None,
            human_interrupt_allowed=False,
            gate=None,
            operation="patch_apply",
        )
        defn = self._direct_definition(step)
        reg = WorkflowRegistry()
        issues = reg.validate_cross_refs(defn, _StubAdapterRegistry({}))
        # Neither operation_required nor invalid_on_failure should fire
        kinds = {i.kind for i in issues}
        assert "operation_required" not in kinds
        assert "invalid_on_failure_for_operation" not in kinds

    def test_cross_ref_issue_model_exposes_optional_adapter_id(self) -> None:
        issue = CrossRefIssue(
            kind="operation_required",
            workflow_id="x",
            step_name="s",
        )
        assert issue.adapter_id is None
        assert issue.missing_capabilities == frozenset()
