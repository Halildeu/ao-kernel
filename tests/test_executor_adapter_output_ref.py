"""PR-C1a: ExecutionResult.output_ref additive field populated on
both adapter-path (driver_managed=True + CAS) and driver-managed
callback paths.

The field is derived from Executor's local ``write_artifact(...)``
output_ref (executor.py:419-422) — NOT from InvocationResult (Codex
iter-1 B1 absorb).
"""

from __future__ import annotations

from dataclasses import fields

from ao_kernel.executor.executor import ExecutionResult


class TestExecutionResultOutputRefField:
    def test_output_ref_is_additive_field(self) -> None:
        """Regression gate: ExecutionResult has ``output_ref`` field
        with default None so existing keyword-arg constructors
        continue to work without migration."""
        field_names = {f.name for f in fields(ExecutionResult)}
        assert "output_ref" in field_names
        field = next(f for f in fields(ExecutionResult) if f.name == "output_ref")
        assert field.default is None
        assert field.type in ("str | None", "Optional[str]")

    def test_existing_constructors_default_to_none(self) -> None:
        """Callers that don't pass output_ref see None (backwards-
        compat shim)."""
        result = ExecutionResult(
            new_state="running",
            step_state="completed",
            invocation_result=None,
            evidence_event_ids=(),
            budget_after={},
        )
        assert result.output_ref is None

    def test_explicit_output_ref_populate(self) -> None:
        """When caller (Executor adapter branch) passes output_ref,
        it surfaces on the dataclass."""
        result = ExecutionResult(
            new_state="running",
            step_state="completed",
            invocation_result=None,
            evidence_event_ids=(),
            budget_after={},
            output_ref="artifacts/codex-stub_attempt1.json",
        )
        assert result.output_ref == "artifacts/codex-stub_attempt1.json"
