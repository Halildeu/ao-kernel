"""Single-step executor orchestrator.

Coordinates ``worktree_builder`` + ``policy_enforcer`` +
``adapter_invoker`` + ``evidence_emitter`` and mutates the run record
via PR-A1 ``workflow.run_store.update_run``. PR-A3 executes ONE step
per call; the multi-step driver is PR-A4.

Plan v2 (CNS-20260415-022 iter-1) invariants:

- **Primitive contract** (Q1 add). Pre-flight: resolve pinned workflow
  definition from run; assert step_def is in definition.steps; assert
  step has not already completed. Duplicate or foreign step raises
  ``ValueError``.
- **Cross-ref per-call** (Q5 B8). Each adapter-actor step re-runs
  ``validate_cross_refs`` with the CURRENT adapter registry; no cache.
  Non-empty issues raise ``WorkflowDefinitionCrossRefError``.
- **Canonical event order** (Q3 B3). The orchestrator emits events in
  declared order: ``step_started → policy_checked → (policy_denied ⇒
  abort) → adapter_invoked → adapter_returned → step_completed |
  step_failed`` before the run state CAS update.
- **Worktree cleanup** (try/finally). Created worktrees are cleaned on
  both success and exception paths.
- **Budget** (PR-A1). ``record_spend`` happens inside
  ``adapter_invoker``; exhaust raises ``WorkflowBudgetExhaustedError``
  and transitions the run to ``failed`` with
  ``error.category="budget_exhausted"``.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from ao_kernel.adapters import AdapterRegistry
from ao_kernel.executor.adapter_invoker import (
    InvocationResult,
    invoke_cli,
    invoke_http,
)
from ao_kernel.executor.errors import PolicyViolation, PolicyViolationError
from ao_kernel.executor.evidence_emitter import emit_event
from ao_kernel.executor.policy_enforcer import (
    build_sandbox,
    check_http_header_exposure,
    resolve_allowed_secrets,
)
from ao_kernel.executor.worktree_builder import (
    WorktreeHandle,
    cleanup_worktree,
    create_worktree,
)
from ao_kernel.workflow import (
    StepDefinition,
    WorkflowDefinitionCrossRefError,
    WorkflowRegistry,
    WorkflowState,
    budget_from_dict,
    budget_to_dict,
    load_run,
    update_run,
    validate_transition,
)


@dataclass(frozen=True)
class ExecutionResult:
    new_state: WorkflowState
    step_state: str
    invocation_result: InvocationResult | None
    evidence_event_ids: tuple[str, ...]
    budget_after: Mapping[str, Any]


class Executor:
    """Single-step executor primitive.

    Consumers: PR-A4 multi-step driver + FAZ-A PR-A6 demo runner.
    """

    def __init__(
        self,
        workspace_root: Path,
        *,
        workflow_registry: WorkflowRegistry,
        adapter_registry: AdapterRegistry,
        policy_loader: Mapping[str, Any] | None = None,
    ) -> None:
        self._workspace_root = workspace_root
        self._workflow_registry = workflow_registry
        self._adapter_registry = adapter_registry
        self._policy: Mapping[str, Any] = (
            policy_loader or _load_bundled_policy()
        )

    def run_step(
        self,
        run_id: str,
        step_def: StepDefinition,
        *,
        parent_env: Mapping[str, str] | None = None,
    ) -> ExecutionResult:
        parent_env = dict(parent_env or {})
        record, _ = load_run(self._workspace_root, run_id)

        # Pre-flight 1: run not terminal
        if record["state"] in {"completed", "failed", "cancelled"}:
            raise ValueError(
                f"run {run_id!r} is terminal (state={record['state']}); "
                f"cannot execute further steps"
            )

        # Pre-flight 2: resolve pinned workflow definition
        definition = self._workflow_registry.get(
            record["workflow_id"],
            version=record["workflow_version"],
        )

        # Pre-flight 3: step_def must be part of the pinned definition
        def_step_names = {s.step_name for s in definition.steps}
        if step_def.step_name not in def_step_names:
            raise ValueError(
                f"step_name={step_def.step_name!r} not in workflow "
                f"{definition.workflow_id}@{definition.workflow_version}"
            )

        # Pre-flight 4: step has not already completed
        for prior in record.get("steps", ()):
            if (
                prior.get("step_name") == step_def.step_name
                and prior.get("state") == "completed"
            ):
                raise ValueError(
                    f"step_name={step_def.step_name!r} already completed "
                    f"for run {run_id!r}"
                )

        # Pre-flight 5: for adapter steps, run cross-ref per-call (no cache)
        if step_def.actor == "adapter":
            issues = self._workflow_registry.validate_cross_refs(
                definition, self._adapter_registry
            )
            if issues:
                raise WorkflowDefinitionCrossRefError(
                    workflow_id=definition.workflow_id,
                    issues=tuple(issues),
                )

        # Dispatch per actor
        if step_def.actor == "adapter":
            return self._run_adapter_step(
                run_id=run_id,
                record=record,
                step_def=step_def,
                parent_env=parent_env,
            )
        # Non-adapter actors are PR-A4+; emit placeholder events and
        # record the step as completed.
        return self._run_placeholder_step(
            run_id=run_id,
            record=record,
            step_def=step_def,
        )

    # ------------------------------------------------------------------
    # Adapter step
    # ------------------------------------------------------------------

    def _run_adapter_step(
        self,
        *,
        run_id: str,
        record: Mapping[str, Any],
        step_def: StepDefinition,
        parent_env: Mapping[str, str],
    ) -> ExecutionResult:
        if step_def.adapter_id is None:
            raise ValueError(
                f"step_name={step_def.step_name!r} has actor=adapter but "
                f"no adapter_id"
            )
        manifest = self._adapter_registry.get(step_def.adapter_id)

        evidence_event_ids: list[str] = []

        # step_started
        started = emit_event(
            self._workspace_root,
            run_id=run_id,
            kind="step_started",
            actor="ao-kernel",
            payload={
                "step_name": step_def.step_name,
                "adapter_id": step_def.adapter_id,
                "actor": step_def.actor,
            },
            step_id=step_def.step_name,
        )
        evidence_event_ids.append(started.event_id)

        # Resolve allowed secrets + build sandbox
        resolved_secrets, secret_violations = resolve_allowed_secrets(
            self._policy, parent_env
        )
        sandbox, sandbox_violations = build_sandbox(
            policy=self._policy,
            worktree_root=self._workspace_root
            / ".ao"
            / "runs"
            / run_id
            / "worktree",
            resolved_secrets=resolved_secrets,
            parent_env=parent_env,
        )
        http_violations = check_http_header_exposure(
            policy=self._policy,
            adapter_manifest_invocation=manifest.invocation,
        )

        policy_violations: list[PolicyViolation] = [
            *secret_violations,
            *sandbox_violations,
            *http_violations,
        ]

        # policy_checked
        checked = emit_event(
            self._workspace_root,
            run_id=run_id,
            kind="policy_checked",
            actor="ao-kernel",
            payload={
                "step_name": step_def.step_name,
                "violations_count": len(policy_violations),
            },
            step_id=step_def.step_name,
        )
        evidence_event_ids.append(checked.event_id)

        if policy_violations:
            denied = emit_event(
                self._workspace_root,
                run_id=run_id,
                kind="policy_denied",
                actor="ao-kernel",
                payload={
                    "step_name": step_def.step_name,
                    "violation_kinds": [v.kind for v in policy_violations],
                },
                step_id=step_def.step_name,
            )
            evidence_event_ids.append(denied.event_id)
            return self._fail_run(
                run_id=run_id,
                record=record,
                step_def=step_def,
                evidence_event_ids=tuple(evidence_event_ids),
                error_category="policy_denied",
                error_detail=f"{len(policy_violations)} policy violation(s)",
                raise_after=PolicyViolationError(
                    violations=policy_violations
                ),
            )

        # Create worktree
        worktree_created: WorktreeHandle | None = None
        try:
            worktree_created = create_worktree(
                workspace_root=self._workspace_root,
                run_id=run_id,
                policy=self._policy,
            )

            # adapter_invoked
            invoked = emit_event(
                self._workspace_root,
                run_id=run_id,
                kind="adapter_invoked",
                actor="ao-kernel",
                payload={
                    "step_name": step_def.step_name,
                    "adapter_id": manifest.adapter_id,
                    "transport": manifest.invocation.get("transport"),
                },
                step_id=step_def.step_name,
            )
            evidence_event_ids.append(invoked.event_id)

            budget = budget_from_dict(record.get("budget", {}))
            input_envelope = {
                "task_prompt": record.get("intent", {}).get("payload", ""),
                "run_id": run_id,
            }
            transport = manifest.invocation.get("transport")
            if transport == "cli":
                invocation_result, budget_after = invoke_cli(
                    manifest=manifest,
                    input_envelope=input_envelope,
                    sandbox=sandbox,
                    worktree=worktree_created,
                    budget=budget,
                    workspace_root=self._workspace_root,
                    run_id=run_id,
                )
            else:
                invocation_result, budget_after = invoke_http(
                    manifest=manifest,
                    input_envelope=input_envelope,
                    sandbox=sandbox,
                    worktree=worktree_created,
                    budget=budget,
                    workspace_root=self._workspace_root,
                    run_id=run_id,
                )

            # adapter_returned (v2 note: actor is adapter-sourced, reported by orchestrator)
            returned = emit_event(
                self._workspace_root,
                run_id=run_id,
                kind="adapter_returned",
                actor="ao-kernel",
                payload={
                    "step_name": step_def.step_name,
                    "adapter_id": manifest.adapter_id,
                    "status": invocation_result.status,
                    "finish_reason": invocation_result.finish_reason,
                },
                step_id=step_def.step_name,
            )
            evidence_event_ids.append(returned.event_id)
        finally:
            if worktree_created is not None:
                cleanup_worktree(
                    worktree_created, workspace_root=self._workspace_root
                )

        # Map adapter status → new workflow state
        new_state, step_state = _map_invocation_to_state(
            current_state=record["state"],
            invocation_result=invocation_result,
        )

        # step_completed | step_failed
        terminal_kind = (
            "step_completed" if step_state == "completed" else "step_failed"
        )
        terminal = emit_event(
            self._workspace_root,
            run_id=run_id,
            kind=terminal_kind,
            actor="ao-kernel",
            payload={
                "step_name": step_def.step_name,
                "final_state": step_state,
            },
            step_id=step_def.step_name,
        )
        evidence_event_ids.append(terminal.event_id)

        # CAS update run
        def _mutator(current: dict[str, Any]) -> dict[str, Any]:
            validate_transition(current["state"], new_state)
            current["state"] = new_state
            steps = list(current.get("steps", []))
            step_record = {
                "step_id": step_def.step_name,
                "step_name": step_def.step_name,
                "state": step_state,
                "actor": step_def.actor,
                "adapter_id": step_def.adapter_id,
                "started_at": started.ts,
                "completed_at": terminal.ts,
                "evidence_event_ids": list(evidence_event_ids),
            }
            steps.append(step_record)
            current["steps"] = steps
            current["budget"] = budget_to_dict(budget_after)
            return current

        update_run(self._workspace_root, run_id, mutator=_mutator)

        return ExecutionResult(
            new_state=new_state,
            step_state=step_state,
            invocation_result=invocation_result,
            evidence_event_ids=tuple(evidence_event_ids),
            budget_after=budget_to_dict(budget_after),
        )

    # ------------------------------------------------------------------
    # Placeholder step (non-adapter actors)
    # ------------------------------------------------------------------

    def _run_placeholder_step(
        self,
        *,
        run_id: str,
        record: Mapping[str, Any],
        step_def: StepDefinition,
    ) -> ExecutionResult:
        evidence_event_ids: list[str] = []
        started = emit_event(
            self._workspace_root,
            run_id=run_id,
            kind="step_started",
            actor="ao-kernel",
            payload={"step_name": step_def.step_name, "actor": step_def.actor},
            step_id=step_def.step_name,
        )
        evidence_event_ids.append(started.event_id)
        completed = emit_event(
            self._workspace_root,
            run_id=run_id,
            kind="step_completed",
            actor="ao-kernel",
            payload={
                "step_name": step_def.step_name,
                "final_state": "completed",
                "note": "PR-A3 placeholder; non-adapter actors run no-op",
            },
            step_id=step_def.step_name,
        )
        evidence_event_ids.append(completed.event_id)

        new_state: WorkflowState = (
            "running" if record["state"] == "created" else record["state"]
        )
        if new_state != record["state"]:
            validate_transition(record["state"], new_state)

        def _mutator(current: dict[str, Any]) -> dict[str, Any]:
            if new_state != current["state"]:
                current["state"] = new_state
            steps = list(current.get("steps", []))
            step_record: dict[str, Any] = {
                "step_id": step_def.step_name,
                "step_name": step_def.step_name,
                "state": "completed",
                "actor": step_def.actor,
                "started_at": started.ts,
                "completed_at": completed.ts,
                "evidence_event_ids": list(evidence_event_ids),
            }
            # Schema: adapter_id is string-typed when present; omit when None.
            if step_def.adapter_id is not None:
                step_record["adapter_id"] = step_def.adapter_id
            steps.append(step_record)
            current["steps"] = steps
            return current

        update_run(self._workspace_root, run_id, mutator=_mutator)

        return ExecutionResult(
            new_state=new_state,
            step_state="completed",
            invocation_result=None,
            evidence_event_ids=tuple(evidence_event_ids),
            budget_after=record.get("budget", {}),
        )

    # ------------------------------------------------------------------
    # Failure path
    # ------------------------------------------------------------------

    def _fail_run(
        self,
        *,
        run_id: str,
        record: Mapping[str, Any],
        step_def: StepDefinition,
        evidence_event_ids: tuple[str, ...],
        error_category: str,
        error_detail: str,
        raise_after: Exception | None,
    ) -> ExecutionResult:
        # emit step_failed
        step_failed = emit_event(
            self._workspace_root,
            run_id=run_id,
            kind="step_failed",
            actor="ao-kernel",
            payload={
                "step_name": step_def.step_name,
                "final_state": "failed",
                "error_category": error_category,
                "error_detail": error_detail,
            },
            step_id=step_def.step_name,
        )
        event_ids_out = (*evidence_event_ids, step_failed.event_id)

        def _mutator(current: dict[str, Any]) -> dict[str, Any]:
            validate_transition(current["state"], "failed")
            current["state"] = "failed"
            current["error"] = {
                "code": f"STEP_{step_def.step_name.upper()}_{error_category.upper()}",
                "message": error_detail,
                "category": error_category,
            }
            steps = list(current.get("steps", []))
            steps.append({
                "step_id": step_def.step_name,
                "step_name": step_def.step_name,
                "state": "failed",
                "actor": step_def.actor,
                "adapter_id": step_def.adapter_id,
                "started_at": step_failed.ts,
                "completed_at": step_failed.ts,
                "evidence_event_ids": list(event_ids_out),
                "error": current["error"],
            })
            current["steps"] = steps
            return current

        update_run(self._workspace_root, run_id, mutator=_mutator)

        if raise_after is not None:
            raise raise_after
        return ExecutionResult(
            new_state="failed",
            step_state="failed",
            invocation_result=None,
            evidence_event_ids=event_ids_out,
            budget_after=record.get("budget", {}),
        )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _map_invocation_to_state(
    *,
    current_state: str,
    invocation_result: InvocationResult,
) -> tuple[WorkflowState, str]:
    """Translate ``InvocationResult.status`` into a workflow state.

    PR-A3 single-step; returns the NEXT workflow state to transition to.
    PR-A4 driver may override per ``on_failure`` policy.
    """
    status = invocation_result.status
    if status == "ok":
        # For an adapter step, a successful invocation implies we are
        # either proceeding to the next lifecycle stage or completing.
        # PR-A3 leaves the state at ``running`` (driver picks the next
        # explicit transition); here we transition to ``running`` from
        # ``created`` to reflect work occurred.
        if current_state == "created":
            return "running", "completed"
        return current_state, "completed"  # type: ignore[return-value]
    if status == "interrupted":
        return "interrupted", "interrupted"
    if status == "partial":
        return "running", "failed"
    if status == "declined":
        return "failed", "failed"
    # status == "failed"
    return "failed", "failed"


def _load_bundled_policy() -> Mapping[str, Any]:
    from importlib import resources

    text = (
        resources.files("ao_kernel.defaults.policies")
        .joinpath("policy_worktree_profile.v1.json")
        .read_text(encoding="utf-8")
    )
    policy: Mapping[str, Any] = json.loads(text)
    return policy


__all__ = [
    "Executor",
    "ExecutionResult",
]
