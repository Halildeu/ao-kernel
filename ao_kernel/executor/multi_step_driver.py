"""Multi-step workflow driver (PR-A4b).

Iterates ``workflow_definition.steps`` with actor/operation dispatch,
handles ``on_failure`` (transition_to_failed / retry_once /
escalate_to_human), honours pre-step ``gate`` governance, owns
per-step CAS + run-level state transitions, and surfaces
``DriverResult`` for happy / waiting-approval / interrupted / terminal
outcomes.

**Ownership contract (CNS-024 iter-1 B1 absorb):** Executor.run_step
runs with ``driver_managed=True`` — it emits evidence + writes
artifact + normalizes InvocationResult but does NOT append
step_record or transition run state. The driver does all CAS
mutations here. Default Executor mode (``driver_managed=False``)
preserves A3 single-step behaviour for backward compat.

**Retry append-only (CNS-024 iter-1 B3 absorb):** failure →
driver appends ``state=failed`` terminal record for the attempt;
on_failure=retry_once then appends a fresh-``step_id`` placeholder
with ``state=running`` + ``attempt=2``; Executor invocation runs
against the placeholder; success/failure updates the placeholder.
Crash-safety: absent attempt=2 placeholder + failed attempt=1 +
on_failure=retry_once → driver resume creates the placeholder and
invokes (retry NOT consumed).

**Error category mapping (CNS-024 iter-1 B4 absorb):** schema-legal
``error.category`` enum + machine ``error.code`` + human
``error.message`` + evidence payload ``reason`` separate. 8-row
mapping table in :func:`_failure_error_record`.

**Approval idempotency decision-only (CNS-024 iter-1 B5 absorb):**
``resume_workflow`` routes approval tokens to
``primitives.resume_approval`` with ``decision`` only; ``notes``
(if provided) is emitted as redacted metadata in ``approval_granted``
/ ``approval_denied`` event payloads, NOT hashed into the token
idempotency key, NOT persisted to schema.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal, Mapping

from ao_kernel.adapters import AdapterRegistry
from ao_kernel.executor.artifacts import write_artifact
from ao_kernel.executor.errors import PolicyViolationError
from ao_kernel.executor.evidence_emitter import emit_event
from ao_kernel.executor.executor import Executor
from ao_kernel.executor.policy_enforcer import (
    SandboxedEnvironment,
    build_sandbox,
    resolve_allowed_secrets,
)

# NOTE: ao_kernel.ci and ao_kernel.patch are imported lazily inside the
# dispatch helpers below. Eager import would form a cycle through
# ao_kernel.executor.__init__ (which re-exports MultiStepDriver).
from ao_kernel.workflow import (
    Budget,
    StepDefinition,
    WorkflowCASConflictError,
    WorkflowRegistry,
    WorkflowTokenInvalidError,
    budget_from_dict,
    is_exhausted,
    load_run,
    update_run,
    validate_transition,
)


__all__ = [
    "DriverBudgetExhaustedError",
    "DriverResult",
    "DriverStateConflictError",
    "DriverStateInconsistencyError",
    "DriverTokenRequiredError",
    "MultiStepDriver",
    "WorkflowStateCorruptedError",
]


@dataclass(frozen=True)
class DriverResult:
    """Outcome of a ``run_workflow`` or ``resume_workflow`` call."""

    run_id: str
    final_state: Literal[
        "running",
        "waiting_approval",
        "interrupted",
        "completed",
        "failed",
        "cancelled",
    ]
    steps_executed: tuple[str, ...]
    steps_failed: tuple[str, ...]
    steps_retried: tuple[str, ...]
    resume_token: str | None
    resume_token_kind: Literal["approval", "interrupt"] | None
    budget_consumed: Mapping[str, Any] | None
    duration_seconds: float


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class DriverStateConflictError(Exception):
    """Two CAS retries failed; concurrent writer detected."""


class DriverBudgetExhaustedError(Exception):
    """Budget axis went negative mid-step."""


class DriverTokenRequiredError(Exception):
    """Run is in waiting_approval / interrupted; resume_workflow needed."""

    def __init__(self, run_id: str, state: str, hint: str = "") -> None:
        super().__init__(
            f"run {run_id!r} is {state!r}; {hint or 'use resume_workflow'}"
        )
        self.run_id = run_id
        self.state = state


class DriverStateInconsistencyError(Exception):
    """Terminal run state but retry is still available; data corruption."""

    def __init__(
        self, *, run_state: str, terminal_step_ok: bool, reason: str = ""
    ) -> None:
        super().__init__(
            f"run_state={run_state!r}, terminal_step_ok={terminal_step_ok}: "
            f"{reason}"
        )
        self.run_state = run_state
        self.terminal_step_ok = terminal_step_ok
        self.reason = reason


class WorkflowStateCorruptedError(Exception):
    """Run state is not one of the 9 legal workflow states."""


class _StepFailed(Exception):
    """Internal signal from the _run_*_step helpers."""

    def __init__(self, *, reason: str, attempt: int, category: str = "other", code: str = "") -> None:
        super().__init__(f"{category}/{code}: {reason}")
        self.reason = reason
        self.attempt = attempt
        self.category = category
        self.code = code


# ---------------------------------------------------------------------------
# MultiStepDriver
# ---------------------------------------------------------------------------


class MultiStepDriver:
    """Orchestrates a workflow_definition.steps sequence under governance.

    Usage:

        driver = MultiStepDriver(
            workspace_root=ws,
            registry=workflow_registry,
            adapter_registry=adapter_registry,
            executor=executor,
            policy_config=policy,
        )
        result = driver.run_workflow(run_id, "bug_fix_flow", "1.0.0")
        if result.final_state == "waiting_approval":
            ...  # human decides
            result = driver.resume_workflow(
                run_id, result.resume_token,
                payload={"decision": "granted", "notes": "LGTM"},
            )
    """

    def __init__(
        self,
        workspace_root: Path,
        *,
        registry: WorkflowRegistry,
        adapter_registry: AdapterRegistry,
        executor: Executor,
        policy_config: Mapping[str, Any] | None = None,
    ) -> None:
        self._workspace_root = workspace_root
        self._registry = registry
        self._adapter_registry = adapter_registry
        self._executor = executor
        self._policy: Mapping[str, Any] = policy_config or {}

    # ------------------------------------------------------------------
    # Public: run_workflow
    # ------------------------------------------------------------------

    def run_workflow(
        self,
        run_id: str,
        workflow_id: str,
        workflow_version: str,
        *,
        budget: Budget | None = None,
        context_preamble: str | None = None,
    ) -> DriverResult:
        """Run the pinned workflow to completion / next gate / interrupt.

        Entry matrix (CNS-024 B2):
        - ``created`` → start + emit workflow_started + main loop
        - ``running`` → resume from derived position (no re-emit)
        - ``waiting_approval`` / ``interrupted`` → DriverTokenRequiredError
        - ``completed``/``failed``/``cancelled`` → idempotent return OR
          DriverStateInconsistencyError if retry is still available
        """
        start = time.monotonic()
        definition = self._registry.get(workflow_id, version=workflow_version)
        record, _ = load_run(self._workspace_root, run_id)

        state = record["state"]
        if state == "created":
            record = self._cas_state_transition(
                run_id, record, "running",
                extra={"started_at": _now_iso()},
            )
            self._emit(
                run_id, "workflow_started",
                {"workflow_id": workflow_id, "workflow_version": workflow_version},
            )
        elif state == "running":
            # Resume — no workflow_started re-emit (PR-A5 replay tolerates gap)
            pass
        elif state in ("waiting_approval", "interrupted"):
            raise DriverTokenRequiredError(run_id, state)
        elif state in ("completed", "failed", "cancelled"):
            if self._is_retryable_terminal(record, definition):
                raise DriverStateInconsistencyError(
                    run_state=state, terminal_step_ok=False,
                    reason="terminal but retry still available",
                )
            return self._idempotent_terminal_result(run_id, record, state, start)
        else:
            raise WorkflowStateCorruptedError(
                f"run {run_id!r} has unknown state {state!r}"
            )

        # Workflow-level cross-ref (invariant #24) — early fail, no step runs
        issues = self._registry.validate_cross_refs(definition, self._adapter_registry)
        if issues:
            return self._transition_to_failed(
                run_id, record, start,
                category="other", code="CROSS_REF",
                message=f"cross-ref issues: {len(issues)}",
                failed_step=None,
            )

        return self._main_loop(
            run_id, record, definition, budget, context_preamble, start,
        )

    # ------------------------------------------------------------------
    # Public: resume_workflow
    # ------------------------------------------------------------------

    def resume_workflow(
        self,
        run_id: str,
        resume_token: str,
        payload: Mapping[str, Any] | None = None,
    ) -> DriverResult:
        """Resume a waiting_approval / interrupted run with a token.

        Approval tokens: payload = ``{"decision": "granted"|"denied",
        "notes": str | None}``. Idempotency key is decision-only (B5);
        notes are emitted as redacted metadata.

        Interrupt tokens: payload contract follows PR-A1
        ``resume_interrupt`` (full payload hash idempotency at the
        primitive layer).
        """
        record, _ = load_run(self._workspace_root, run_id)

        # Match token against pending approvals first
        pending_approval = self._find_pending_approval(record, resume_token)
        if pending_approval is not None:
            return self._resume_approval(
                run_id, record, pending_approval, payload or {},
            )

        # Match interrupt
        pending_interrupt = self._find_pending_interrupt(record, resume_token)
        if pending_interrupt is not None:
            return self._resume_interrupt(
                run_id, record, pending_interrupt, payload or {},
            )

        raise WorkflowTokenInvalidError(
            run_id=run_id,
            token_kind="approval",
            token_value=resume_token,
            reason="token_mismatch",
        )

    # ------------------------------------------------------------------
    # Main loop
    # ------------------------------------------------------------------

    def _main_loop(
        self,
        run_id: str,
        record: Mapping[str, Any],
        definition: Any,  # WorkflowDefinition
        budget: Budget | None,
        context_preamble: str | None,
        start: float,
    ) -> DriverResult:
        completed = self._completed_step_names(record)
        retried = self._retried_step_names(record)
        mutable_record: dict[str, Any] = dict(record)

        for step_def in definition.steps:
            if step_def.step_name in completed:
                continue

            # Budget gate (invariant #23)
            if budget is not None:
                exhausted, axis = is_exhausted(budget)
                if exhausted:
                    return self._transition_to_failed(
                        run_id, mutable_record, start,
                        category="budget_exhausted",
                        code="BUDGET_EXHAUSTED",
                        message=f"budget axis {axis} exhausted",
                        failed_step=step_def.step_name,
                        steps_executed=completed,
                        steps_retried=retried,
                    )

            # Pre-step governance gate
            if step_def.gate is not None:
                return self._open_governance_gate(
                    run_id, mutable_record, step_def, start,
                    completed=completed, retried=retried,
                )

            # Dispatch
            try:
                attempt = self._next_attempt_number(mutable_record, step_def.step_name)
                step_id = self._step_id_for_attempt(step_def.step_name, attempt)

                # PR-B6 v4 §2.2: capability_output_refs populated only by
                # adapter path (driver-owned materialization). Other
                # dispatch paths default to empty map.
                capability_output_refs: dict[str, str] = {}
                if step_def.actor == "adapter":
                    (
                        mutable_record,
                        exec_result,
                        capability_output_refs,
                    ) = self._run_adapter_step(
                        run_id, mutable_record, step_def,
                        attempt=attempt, step_id=step_id,
                        context_preamble=context_preamble,
                    )
                elif step_def.actor == "ao-kernel":
                    mutable_record, exec_result = self._run_aokernel_step(
                        run_id, mutable_record, step_def,
                        attempt=attempt, step_id=step_id,
                    )
                elif step_def.actor == "system":
                    mutable_record, exec_result = self._run_system_step(
                        run_id, mutable_record, step_def,
                        attempt=attempt, step_id=step_id,
                    )
                elif step_def.actor == "human":
                    return self._run_human_gate(
                        run_id, mutable_record, step_def, start,
                        completed=completed, retried=retried,
                    )
                else:
                    raise WorkflowStateCorruptedError(
                        f"unknown actor {step_def.actor!r}"
                    )
            except _StepFailed as sf:
                return self._handle_step_failure(
                    run_id, mutable_record, step_def, sf, budget, start,
                    completed=completed, retried=retried,
                )

            # Step succeeded — record completion.
            # PR-B6 v4 §2.2: capability_output_refs threaded into the
            # completion helper so step_record persists the per-capability
            # artifact map. Empty for non-adapter paths (default).
            mutable_record = self._record_step_completion(
                run_id, mutable_record, step_def, exec_result,
                attempt=attempt, step_id=step_id,
                capability_output_refs=capability_output_refs,
            )
            completed.add(step_def.step_name)

        # All steps done
        return self._transition_to_completed(
            run_id, mutable_record, start,
            completed=completed, retried=retried,
            budget_consumed=mutable_record.get("budget"),
        )

    # ------------------------------------------------------------------
    # Step dispatch helpers
    # ------------------------------------------------------------------

    def _run_adapter_step(
        self,
        run_id: str,
        record: Mapping[str, Any],
        step_def: StepDefinition,
        *,
        attempt: int,
        step_id: str,
        context_preamble: str | None,
        fencing_token: int | None = None,
        fencing_resource_id: str | None = None,
    ) -> tuple[dict[str, Any], Any, dict[str, str]]:
        """Delegate to Executor.run_step(driver_managed=True) + materialize
        per-capability artifacts.

        PR-B1 fencing integration: ``fencing_token`` + ``fencing_resource_id``
        forward to executor's entry check; :class:`ClaimStaleFencingError`
        → driver-owned ``_StepFailed(category="other", code="STALE_FENCING")``.

        PR-B6 v4 §2.2 absorb: after a successful ``exec_result`` (but
        BEFORE record completion), iterate ``invocation_result.extracted_outputs``
        and write one typed artifact per capability via
        :func:`write_capability_artifact`. Returns a third element —
        ``capability_output_refs: map<capability, run-relative path>``
        — that the driver's completion helpers persist on ``step_record``.

        New exception translations (PR-B6 v4 iter-2 B2 absorb):
        - :class:`AdapterInvocationFailedError` (transport layer):
          * reason ∈ {``timeout``, ``http_timeout``} → ``timeout``
          * reason == ``subprocess_crash`` → ``adapter_crash``
          * other → ``invocation_failed``
        - :class:`AdapterOutputParseError` (walker layer):
          * → ``output_parse_failed``
        - Capability artifact write failure:
          * → ``output_parse_failed`` + ``code="CAPABILITY_ARTIFACT_WRITE_FAILED"``
        """
        # Import locally to avoid pulling the coordination package into
        # the driver's import graph when callers do not enable it.
        from ao_kernel.coordination.errors import ClaimStaleFencingError
        from ao_kernel.executor.artifacts import write_capability_artifact
        from ao_kernel.executor.errors import (
            AdapterInvocationFailedError,
            AdapterOutputParseError,
        )

        # PR-C1a: resolve context_pack_ref from prior context_compile step's
        # artifact; None → Executor default envelope (backwards-compat).
        envelope_override = self._build_adapter_envelope_with_context(
            run_id, step_def, record,
        )

        try:
            exec_result = self._executor.run_step(
                run_id=run_id,
                step_def=step_def,
                parent_env={},
                attempt=attempt,
                driver_managed=True,
                step_id=step_id,
                fencing_token=fencing_token,
                fencing_resource_id=fencing_resource_id,
                input_envelope_override=envelope_override,
            )
        except PolicyViolationError as exc:
            raise _StepFailed(
                reason=f"policy_violation: {exc}",
                attempt=attempt,
                category="other",
                code="POLICY_VIOLATION",
            ) from exc
        except ClaimStaleFencingError as exc:
            # PR-B1 W1v5: executor emits nothing on stale-fencing; the
            # driver owns the step_failed emission + step_record CAS
            # transition (PR-A4b error handler contract).
            raise _StepFailed(
                reason=(
                    f"stale fencing: resource_id={exc.resource_id} "
                    f"supplied_token={exc.supplied_token} "
                    f"live_token={exc.live_token}"
                ),
                attempt=attempt,
                category="other",
                code="STALE_FENCING",
            ) from exc
        except AdapterInvocationFailedError as exc:
            # PR-B6 v4 iter-2 B2 absorb (Codex semantic pin):
            # - timeout/http_timeout → category=timeout
            # - subprocess_crash → category=adapter_crash
            # - other transport-layer → category=invocation_failed
            if exc.reason in ("timeout", "http_timeout"):
                category = "timeout"
            elif exc.reason == "subprocess_crash":
                category = "adapter_crash"
            else:
                category = "invocation_failed"
            raise _StepFailed(
                reason=f"adapter invocation failed: {exc!s}",
                attempt=attempt,
                category=category,
                code=exc.reason.upper() if exc.reason else "INVOCATION_FAILED",
            ) from exc
        except AdapterOutputParseError as exc:
            # PR-B6 v4 §2.2: walker layer parse failure.
            raise _StepFailed(
                reason=f"output_parse walker failed: {exc!s}",
                attempt=attempt,
                category="output_parse_failed",
                code="OUTPUT_PARSE_FAILED",
            ) from exc

        if exec_result.step_state != "completed":
            raise _StepFailed(
                reason=f"adapter_status={exec_result.step_state}",
                attempt=attempt,
                category="other",
                code="ADAPTER_FAILED",
            )

        # PR-B6 v4 §2.2 absorb: driver-owned per-capability artifact
        # materialization. Runs AFTER exec_result.step_state == "completed"
        # but BEFORE completion record is written so any artifact-write
        # failure fails-closed via _StepFailed (output_parse_failed
        # category).
        capability_output_refs: dict[str, str] = {}
        run_dir = (
            self._workspace_root / ".ao" / "evidence" / "workflows" / run_id
        )
        invocation_result = getattr(exec_result, "invocation_result", None)
        extracted = (
            getattr(invocation_result, "extracted_outputs", None)
            if invocation_result is not None
            else None
        )
        if extracted:
            for capability, payload in extracted.items():
                try:
                    cap_ref, _cap_sha = write_capability_artifact(
                        run_dir=run_dir,
                        step_id=step_id,
                        attempt=attempt,
                        capability=capability,
                        payload=payload,
                    )
                    capability_output_refs[capability] = cap_ref
                except Exception as exc:
                    # Fail-closed: artifact write must not be silently
                    # dropped. _LEGAL_CATEGORIES includes
                    # output_parse_failed (parity sync).
                    raise _StepFailed(
                        reason=(
                            f"capability artifact write failed for "
                            f"{capability!r}: {exc!s}"
                        ),
                        attempt=attempt,
                        category="output_parse_failed",
                        code="CAPABILITY_ARTIFACT_WRITE_FAILED",
                    ) from exc

        # Refresh record so completion update sees the latest CAS state
        refreshed, _ = load_run(self._workspace_root, run_id)
        return dict(refreshed), exec_result, capability_output_refs

    def _build_adapter_envelope_with_context(
        self,
        run_id: str,
        step_def: StepDefinition,
        record: Mapping[str, Any],
    ) -> dict[str, Any] | None:
        """Resolve context_pack_ref from most recent completed
        context_compile step's artifact JSON.

        Returns envelope override dict with absolute context_pack_ref
        OR ``None`` if no prior context is available (caller falls
        back to Executor's default envelope — backwards-compat for
        workflows without context_compile steps).
        """
        import json as _json

        workflow_id = record.get("workflow_id")
        workflow_version = record.get("workflow_version")
        if not workflow_id or not workflow_version:
            # Partial / malformed record (e.g. fencing-test fixtures).
            # Fall back silently so executor's default envelope applies.
            return None

        workflow_def = self._registry.get(
            workflow_id,
            version=workflow_version,
        )
        compile_step_names = {
            sd.step_name for sd in workflow_def.steps
            if sd.operation == "context_compile"
        }
        if not compile_step_names:
            return None

        compile_record = None
        for prior in reversed(record.get("steps", [])):
            if (
                prior.get("step_name") in compile_step_names
                and prior.get("state") == "completed"
                and prior.get("output_ref")
            ):
                compile_record = prior
                break
        if compile_record is None:
            return None

        run_dir = (
            self._workspace_root / ".ao" / "evidence" / "workflows" / run_id
        )
        artifact_path = run_dir / compile_record["output_ref"]
        if not artifact_path.is_file():
            return None

        try:
            artifact = _json.loads(artifact_path.read_text(encoding="utf-8"))
        except (OSError, _json.JSONDecodeError):
            return None
        context_path = artifact.get("context_path")
        if not context_path:
            return None

        return {
            "task_prompt": record.get("intent", {}).get("payload", ""),
            "run_id": run_id,
            "context_pack_ref": context_path,
        }

    def _run_aokernel_step(
        self,
        run_id: str,
        record: Mapping[str, Any],
        step_def: StepDefinition,
        *,
        attempt: int,
        step_id: str,
    ) -> tuple[dict[str, Any], Any]:
        """Dispatch ao-kernel operations (context_compile, patch_*)."""
        op = step_def.operation
        run_dir = self._workspace_root / ".ao" / "evidence" / "workflows" / run_id
        self._emit(run_id, "step_started",
            {"step_name": step_def.step_name, "actor": "ao-kernel",
             "operation": op, "attempt": attempt},
            step_id=step_id)

        if op == "context_compile":
            # PR-C1a: real materialisation replacing A4b stub. Uses
            # existing compile_context() pipeline; writes markdown to
            # evidence dir with absolute path for adapter subprocess.
            from ao_kernel.context.context_compiler import compile_context
            from ao_kernel.context.canonical_store import query as _canonical_query
            from ao_kernel._internal.shared.utils import write_text_atomic
            import json as _json

            # MVP: session_context = {} (workflow-run schema top-level
            # değişmez; session bridge ayrı PR'a bırakılır).
            session_context: dict[str, Any] = {}

            # Canonical: query (workspace_root: Path) returns list; wrap
            # as dict keyed by 'key' field (CanonicalDecision.key) so
            # compile_context().canonical_decisions .items() works.
            # Corrupt store → degrade silently to empty (mirror the
            # agent_coordination.py:208-214 tolerance pattern so run
            # state doesn't escape with a raw exception).
            try:
                canonical_list = _canonical_query(self._workspace_root)
            except Exception:  # noqa: BLE001
                canonical_list = []
            canonical = {
                item.get("key", f"_idx_{idx}"): item
                for idx, item in enumerate(canonical_list)
            }

            # Workspace facts: direct JSON read; corrupt file → {}
            facts_path = (
                self._workspace_root / ".cache" / "index"
                / "workspace_facts.v1.json"
            )
            facts: dict[str, Any] = {}
            if facts_path.is_file():
                try:
                    facts = _json.loads(facts_path.read_text())
                except (OSError, _json.JSONDecodeError):
                    facts = {}

            compiled = compile_context(
                session_context,
                canonical_decisions=canonical,
                workspace_facts=facts,
                profile="TASK_EXECUTION",
            )

            # Absolute path for adapter subprocess (C1a B3 absorb).
            context_path = (
                run_dir / f"context-{step_id}-attempt{attempt}.md"
            )
            write_text_atomic(context_path, compiled.preamble)

            payload = {
                "operation": "context_compile",
                "stub": False,
                "context_preamble_bytes": len(
                    compiled.preamble.encode("utf-8")
                ),
                "context_path": str(context_path),
                "total_tokens": compiled.total_tokens,
                "items_included": compiled.items_included,
                "items_excluded": compiled.items_excluded,
                "profile_id": compiled.profile_id,
            }
            output_ref, output_sha256 = write_artifact(
                run_dir=run_dir, step_id=step_id, attempt=attempt, payload=payload,
            )
            return dict(record), {
                "step_state": "completed",
                "output_ref": output_ref,
                "output_sha256": output_sha256,
                "operation": op,
                # PR-C1a propagate to _record_step_completion
                "context_preamble_bytes": len(
                    compiled.preamble.encode("utf-8")
                ),
                "context_path": str(context_path),
            }

        if op in ("patch_preview", "patch_apply", "patch_rollback"):
            return self._run_patch_step(
                run_id, record, step_def, attempt=attempt, step_id=step_id,
                run_dir=run_dir,
            )

        raise _StepFailed(
            reason=f"unsupported_operation_{op}",
            attempt=attempt,
            category="other",
            code="UNSUPPORTED_OPERATION",
        )

    def _run_system_step(
        self,
        run_id: str,
        record: Mapping[str, Any],
        step_def: StepDefinition,
        *,
        attempt: int,
        step_id: str,
    ) -> tuple[dict[str, Any], Any]:
        """Dispatch system operations (ci_*)."""
        from ao_kernel.ci import run_pytest, run_ruff  # lazy to avoid cycle
        from ao_kernel.ci.errors import CIRunnerNotFoundError  # lazy
        op = step_def.operation
        run_dir = self._workspace_root / ".ao" / "evidence" / "workflows" / run_id
        self._emit(run_id, "step_started",
            {"step_name": step_def.step_name, "actor": "system",
             "operation": op, "attempt": attempt},
            step_id=step_id)

        if op == "ci_mypy":
            # W7 absorb: reject explicitly; don't fall through to run_all
            raise _StepFailed(
                reason="ci_mypy runner not implemented",
                attempt=attempt,
                category="other",
                code="UNSUPPORTED_OPERATION",
            )

        if op not in ("ci_pytest", "ci_ruff"):
            raise _StepFailed(
                reason=f"unsupported_operation_{op}",
                attempt=attempt,
                category="other",
                code="UNSUPPORTED_OPERATION",
            )

        # Build sandbox from policy + resolve secrets
        sandbox = self._build_sandbox(run_id)
        worktree = self._workspace_root / ".ao" / "runs" / run_id / "worktree"
        if not worktree.exists():
            worktree = self._workspace_root  # fallback to workspace root

        try:
            if op == "ci_pytest":
                result = run_pytest(worktree, sandbox)
            else:
                result = run_ruff(worktree, sandbox)
        except CIRunnerNotFoundError as exc:
            raise _StepFailed(
                reason=f"runner_not_allowed: {exc}",
                attempt=attempt,
                category="ci_failed",
                code="CI_RUNNER_NOT_FOUND",
            ) from exc

        # test_executed event (per 18-kind taxonomy)
        self._emit(run_id, "test_executed",
            {"step_name": step_def.step_name, "check_name": result.check_name,
             "status": result.status, "exit_code": result.exit_code,
             "attempt": attempt},
            step_id=step_id)

        # Persist artifact
        artifact = {
            "check_name": result.check_name,
            "command": list(result.command),
            "status": result.status,
            "exit_code": result.exit_code,
            "duration_seconds": result.duration_seconds,
            "stdout_tail": result.stdout_tail,
            "stderr_tail": result.stderr_tail,
        }
        output_ref, output_sha256 = write_artifact(
            run_dir=run_dir, step_id=step_id, attempt=attempt, payload=artifact,
        )

        if result.status != "pass":
            raise _StepFailed(
                reason=f"ci_{result.check_name}_{result.status}",
                attempt=attempt,
                category="ci_failed",
                code="CI_CHECK_FAILED",
            )

        return dict(record), {
            "step_state": "completed",
            "output_ref": output_ref,
            "output_sha256": output_sha256,
            "operation": op,
        }

    def _run_patch_step(
        self,
        run_id: str,
        record: Mapping[str, Any],
        step_def: StepDefinition,
        *,
        attempt: int,
        step_id: str,
        run_dir: Path,
    ) -> tuple[dict[str, Any], Any]:
        """Dispatch patch_preview / patch_apply / patch_rollback."""
        from ao_kernel.patch import (  # lazy to avoid cycle through executor
            apply_patch, preview_diff, rollback_patch, PatchError,
        )
        op = step_def.operation
        sandbox = self._build_sandbox(run_id)
        worktree = self._workspace_root / ".ao" / "runs" / run_id / "worktree"
        if not worktree.exists():
            worktree = self._workspace_root

        # A4b stub: patch primitives need patch_content sourced from a
        # prior adapter's output_ref. For now, empty content signals
        # this is a demo-tier flow; tests supply content via fixture.
        patch_content = _load_pending_patch_content(record, step_def.step_name)

        try:
            if op == "patch_preview":
                preview = preview_diff(worktree, patch_content, sandbox)
                self._emit(run_id, "diff_previewed",
                    {"step_name": step_def.step_name, "patch_id": preview.patch_id,
                     "files_changed": list(preview.files_changed), "attempt": attempt},
                    step_id=step_id)
                artifact = {
                    "operation": op, "patch_id": preview.patch_id,
                    "files_changed": list(preview.files_changed),
                    "lines_added": preview.lines_added,
                    "lines_removed": preview.lines_removed,
                }
            elif op == "patch_apply":
                apply_result = apply_patch(
                    worktree, patch_content, sandbox, run_dir,
                )
                self._emit(run_id, "diff_applied",
                    {"step_name": step_def.step_name,
                     "patch_id": apply_result.patch_id,
                     "applied_sha": apply_result.applied_sha,
                     "attempt": attempt},
                    step_id=step_id)
                artifact = {
                    "operation": op, "patch_id": apply_result.patch_id,
                    "reverse_diff_id": apply_result.reverse_diff_id,
                    "files_changed": list(apply_result.files_changed),
                    "applied_sha": apply_result.applied_sha,
                }
            else:  # patch_rollback
                reverse_diff_id = step_def.step_name  # test fixture convention
                rb_result = rollback_patch(
                    worktree, reverse_diff_id, sandbox, run_dir,
                )
                if rb_result.rolled_back:
                    self._emit(run_id, "diff_rolled_back",
                        {"step_name": step_def.step_name,
                         "patch_id": rb_result.patch_id, "attempt": attempt},
                        step_id=step_id)
                artifact = {
                    "operation": op, "patch_id": rb_result.patch_id,
                    "rolled_back": rb_result.rolled_back,
                    "idempotent_skip": rb_result.idempotent_skip,
                    "files_reverted": list(rb_result.files_reverted),
                }
        except PatchError as exc:
            raise _StepFailed(
                reason=f"patch_{op}_{type(exc).__name__}",
                attempt=attempt,
                category="apply_conflict" if "Conflict" in type(exc).__name__ else "other",
                code="PATCH_APPLY_CONFLICT" if "Conflict" in type(exc).__name__ else "PATCH_ERROR",
            ) from exc
        except PolicyViolationError as exc:
            raise _StepFailed(
                reason=f"policy_violation: {exc}",
                attempt=attempt,
                category="other",
                code="POLICY_VIOLATION",
            ) from exc

        output_ref, output_sha256 = write_artifact(
            run_dir=run_dir, step_id=step_id, attempt=attempt, payload=artifact,
        )
        return dict(record), {
            "step_state": "completed",
            "output_ref": output_ref,
            "output_sha256": output_sha256,
            "operation": op,
        }

    def _run_human_gate(
        self,
        run_id: str,
        record: Mapping[str, Any],
        step_def: StepDefinition,
        start: float,
        *,
        completed: set[str],
        retried: set[str],
    ) -> DriverResult:
        """Pure human step acts like a pre-step gate."""
        return self._open_governance_gate(
            run_id, record, step_def, start,
            completed=completed, retried=retried,
        )

    # ------------------------------------------------------------------
    # Governance / approval gate
    # ------------------------------------------------------------------

    def _open_governance_gate(
        self,
        run_id: str,
        record: Mapping[str, Any],
        step_def: StepDefinition,
        start: float,
        *,
        completed: set[str],
        retried: set[str],
    ) -> DriverResult:
        from ao_kernel.workflow.primitives import create_approval

        approval = create_approval(
            gate=step_def.gate or "pre_step",
            actor="human",
            payload={"step_name": step_def.step_name},
        )
        approval_dict = {
            "approval_id": approval.approval_id,
            "approval_token": approval.approval_token,
            "gate": approval.gate,
            "actor": approval.actor,
            "requested_at": approval.requested_at,
            "payload": dict(approval.payload),
            # decision + responded_at left unset until resume
        }
        new_record = self._cas_state_transition(
            run_id, record, "waiting_approval",
            extra={
                "approvals": list(record.get("approvals", [])) + [approval_dict],
            },
        )
        self._emit(run_id, "approval_requested",
            {"step_name": step_def.step_name,
             "gate": step_def.gate or "pre_step",
             "approval_id": approval.approval_id},
            step_id=step_def.step_name)
        return DriverResult(
            run_id=run_id,
            final_state="waiting_approval",
            steps_executed=tuple(sorted(completed)),
            steps_failed=(),
            steps_retried=tuple(sorted(retried)),
            resume_token=approval.approval_token,
            resume_token_kind="approval",
            budget_consumed=new_record.get("budget"),
            duration_seconds=time.monotonic() - start,
        )

    def _resume_approval(
        self,
        run_id: str,
        record: Mapping[str, Any],
        approval_dict: Mapping[str, Any],
        payload: Mapping[str, Any],
    ) -> DriverResult:
        from ao_kernel.workflow.primitives import Approval, resume_approval

        decision = payload.get("decision")
        if decision not in ("granted", "denied"):
            raise WorkflowTokenInvalidError(
                run_id=run_id, token_kind="approval",
                token_value=approval_dict["approval_token"],
                reason="resumed_with_different_payload",
            )
        notes = payload.get("notes")
        approval = Approval(
            approval_id=approval_dict["approval_id"],
            approval_token=approval_dict["approval_token"],
            gate=approval_dict["gate"],
            actor=approval_dict["actor"],
            requested_at=approval_dict["requested_at"],
            payload=dict(approval_dict.get("payload", {})),
            decision=approval_dict.get("decision"),
            responded_at=approval_dict.get("responded_at"),
        )
        resumed = resume_approval(
            approval, token=approval_dict["approval_token"],
            decision=decision, run_id=run_id,
        )

        kind = "approval_granted" if decision == "granted" else "approval_denied"
        evt_payload = {
            "approval_id": resumed.approval_id,
            "decision": decision,
        }
        if notes:
            evt_payload["notes"] = notes  # redacted metadata, not idempotency input
        pending_step = approval_dict.get("payload", {}).get("step_name")
        self._emit(run_id, kind, evt_payload, step_id=pending_step)

        if decision == "denied":
            # Cancel path
            new_record = self._cas_state_transition(
                run_id, record, "cancelled",
                extra={"completed_at": _now_iso()},
            )
            return DriverResult(
                run_id=run_id,
                final_state="cancelled",
                steps_executed=tuple(sorted(self._completed_step_names(record))),
                steps_failed=(),
                steps_retried=tuple(sorted(self._retried_step_names(record))),
                resume_token=None,
                resume_token_kind=None,
                budget_consumed=new_record.get("budget"),
                duration_seconds=0.0,
            )

        # Granted — mark the gated step as completed (so main_loop skips
        # the governance gate next iteration) and return to running.
        pending_step = approval_dict.get("payload", {}).get("step_name")

        def _mutator(cur: dict[str, Any]) -> dict[str, Any]:
            validate_transition(cur["state"], "running")
            cur["state"] = "running"
            approvals = list(cur.get("approvals", []))
            for i, a in enumerate(approvals):
                if a.get("approval_token") == approval_dict["approval_token"]:
                    approvals[i] = {**a, "decision": decision,
                                     "responded_at": resumed.responded_at}
                    break
            cur["approvals"] = approvals
            # Append a completed step_record for the approved step so
            # main_loop skips it on re-entry.
            if pending_step:
                steps = list(cur.get("steps", []))
                already_completed = any(
                    sr.get("step_name") == pending_step
                    and sr.get("state") == "completed"
                    for sr in steps
                )
                if not already_completed:
                    steps.append({
                        "step_id": pending_step,
                        "step_name": pending_step,
                        "state": "completed",
                        "actor": "human",
                        "started_at": _now_iso(),
                        "completed_at": _now_iso(),
                        "attempt": 1,
                    })
                    cur["steps"] = steps
            return cur
        new_record = self._cas_mutate(run_id, _mutator)

        # Re-enter main loop
        definition = self._registry.get(
            new_record["workflow_id"], version=new_record["workflow_version"],
        )
        budget = (
            budget_from_dict(new_record["budget"])
            if new_record.get("budget") else None
        )
        return self._main_loop(
            run_id, new_record, definition, budget, None, time.monotonic(),
        )

    def _resume_interrupt(
        self,
        run_id: str,
        record: Mapping[str, Any],
        interrupt_dict: Mapping[str, Any],
        payload: Mapping[str, Any],
    ) -> DriverResult:
        # Minimal MVP: transition to running, re-enter main loop.
        def _mutator(cur: dict[str, Any]) -> dict[str, Any]:
            validate_transition(cur["state"], "running")
            cur["state"] = "running"
            return cur
        new_record = self._cas_mutate(run_id, _mutator)
        definition = self._registry.get(
            new_record["workflow_id"], version=new_record["workflow_version"],
        )
        budget = (
            budget_from_dict(new_record["budget"])
            if new_record.get("budget") else None
        )
        return self._main_loop(
            run_id, new_record, definition, budget, None, time.monotonic(),
        )

    # ------------------------------------------------------------------
    # Failure handling
    # ------------------------------------------------------------------

    def _handle_step_failure(
        self,
        run_id: str,
        record: Mapping[str, Any],
        step_def: StepDefinition,
        failure: _StepFailed,
        budget: Budget | None,
        start: float,
        *,
        completed: set[str],
        retried: set[str],
    ) -> DriverResult:
        on_failure = step_def.on_failure
        self._emit(run_id, "step_failed",
            {"step_name": step_def.step_name, "reason": failure.reason,
             "attempt": failure.attempt, "code": failure.code},
            step_id=self._step_id_for_attempt(step_def.step_name, failure.attempt))

        # CAS: append terminal failed attempt step_record
        record = self._append_failed_attempt_record(
            run_id, record, step_def,
            attempt=failure.attempt, reason=failure.reason,
        )

        if on_failure == "transition_to_failed":
            return self._transition_to_failed(
                run_id, record, start,
                category=failure.category, code=failure.code,
                message=failure.reason,
                failed_step=step_def.step_name,
                steps_executed=completed,
                steps_failed={step_def.step_name},
                steps_retried=retried,
            )

        if on_failure == "retry_once":
            if failure.attempt >= 2:
                return self._transition_to_failed(
                    run_id, record, start,
                    category="other", code="RETRY_EXHAUSTED",
                    message=f"attempt=2 failed: {failure.reason}",
                    failed_step=step_def.step_name,
                    steps_executed=completed,
                    steps_failed={step_def.step_name},
                    steps_retried=retried | {step_def.step_name},
                )
            # Append placeholder attempt=2 + invoke
            retried = retried | {step_def.step_name}
            placeholder_step_id = self._step_id_for_attempt(
                step_def.step_name, attempt=2,
            )
            record = self._append_attempt_placeholder(
                run_id, record, step_def,
                step_id=placeholder_step_id, attempt=2,
            )
            # PR-B6 v4 §2.2: retry-success capability_output_refs map
            # (populated by adapter path; empty for others).
            capability_output_refs: dict[str, str] = {}
            try:
                if step_def.actor == "adapter":
                    (
                        record,
                        exec_result,
                        capability_output_refs,
                    ) = self._run_adapter_step(
                        run_id, record, step_def, attempt=2,
                        step_id=placeholder_step_id, context_preamble=None,
                    )
                elif step_def.actor == "ao-kernel":
                    record, exec_result = self._run_aokernel_step(
                        run_id, record, step_def, attempt=2,
                        step_id=placeholder_step_id,
                    )
                elif step_def.actor == "system":
                    record, exec_result = self._run_system_step(
                        run_id, record, step_def, attempt=2,
                        step_id=placeholder_step_id,
                    )
                else:
                    raise _StepFailed(
                        reason=f"retry_on_actor_{step_def.actor}",
                        attempt=2, category="other", code="UNSUPPORTED_OPERATION",
                    )
            except _StepFailed as sf2:
                record = self._update_placeholder_to_failed(
                    run_id, record, placeholder_step_id, reason=sf2.reason,
                )
                return self._transition_to_failed(
                    run_id, record, start,
                    category="other", code="RETRY_EXHAUSTED",
                    message=f"attempt=2 failed: {sf2.reason}",
                    failed_step=step_def.step_name,
                    steps_executed=completed,
                    steps_failed={step_def.step_name},
                    steps_retried=retried,
                )
            record = self._update_placeholder_to_completed(
                run_id, record, placeholder_step_id, exec_result, attempt=2,
                capability_output_refs=capability_output_refs,
            )
            completed.add(step_def.step_name)

            # Continue main loop from next step
            definition = self._registry.get(
                record["workflow_id"], version=record["workflow_version"],
            )
            return self._continue_after_retry(
                run_id, record, definition, step_def, budget, start,
                completed=completed, retried=retried,
            )

        if on_failure == "escalate_to_human":
            from ao_kernel.workflow.primitives import create_approval
            approval = create_approval(
                gate="custom",  # escalate_to_human uses the custom gate slot
                actor="human",
                payload={"step_name": step_def.step_name, "reason": failure.reason},
            )
            approval_dict = {
                "approval_id": approval.approval_id,
                "approval_token": approval.approval_token,
                "gate": approval.gate,
                "actor": approval.actor,
                "requested_at": approval.requested_at,
                "payload": dict(approval.payload),
            }
            new_record = self._cas_state_transition(
                run_id, record, "waiting_approval",
                extra={
                    "approvals": list(record.get("approvals", [])) + [approval_dict],
                },
            )
            self._emit(run_id, "approval_requested",
                {"step_name": step_def.step_name,
                 "escalation": True,
                 "failure_reason": failure.reason,
                 "approval_id": approval.approval_id},
                step_id=step_def.step_name)
            return DriverResult(
                run_id=run_id,
                final_state="waiting_approval",
                steps_executed=tuple(sorted(completed)),
                steps_failed=(),
                steps_retried=tuple(sorted(retried)),
                resume_token=approval.approval_token,
                resume_token_kind="approval",
                budget_consumed=new_record.get("budget"),
                duration_seconds=time.monotonic() - start,
            )

        raise WorkflowStateCorruptedError(
            f"unknown on_failure {on_failure!r}"
        )

    def _continue_after_retry(
        self,
        run_id: str,
        record: Mapping[str, Any],
        definition: Any,
        last_step: StepDefinition,
        budget: Budget | None,
        start: float,
        *,
        completed: set[str],
        retried: set[str],
    ) -> DriverResult:
        """After a successful retry, advance through remaining steps."""
        return self._main_loop(
            run_id, record, definition, budget, None, start,
        )

    # ------------------------------------------------------------------
    # CAS helpers
    # ------------------------------------------------------------------

    def _cas_mutate(
        self,
        run_id: str,
        mutator: Any,
        *,
        max_retries: int = 1,
    ) -> dict[str, Any]:
        """Mutate the run record under CAS with bounded 1 retry."""
        attempts = 0
        while True:
            attempts += 1
            try:
                updated, _revision = update_run(
                    self._workspace_root, run_id, mutator=mutator,
                )
                return dict(updated)
            except WorkflowCASConflictError:
                if attempts > max_retries:
                    raise DriverStateConflictError(
                        f"CAS conflict on run {run_id!r} after "
                        f"{max_retries} retry"
                    )
                continue

    def _cas_state_transition(
        self,
        run_id: str,
        record: Mapping[str, Any],
        new_state: str,
        *,
        extra: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        extra = dict(extra or {})

        def _mutator(cur: dict[str, Any]) -> dict[str, Any]:
            validate_transition(cur["state"], new_state)
            cur["state"] = new_state
            for k, v in extra.items():
                cur[k] = v
            return cur
        return self._cas_mutate(run_id, _mutator)

    def _append_failed_attempt_record(
        self,
        run_id: str,
        record: Mapping[str, Any],
        step_def: StepDefinition,
        *,
        attempt: int,
        reason: str,
    ) -> dict[str, Any]:
        step_id = self._step_id_for_attempt(step_def.step_name, attempt)
        now = _now_iso()

        def _mutator(cur: dict[str, Any]) -> dict[str, Any]:
            steps = list(cur.get("steps", []))
            # If a placeholder record for this step_id already exists
            # (e.g. attempt=2 placeholder that failed), update it.
            for i, sr in enumerate(steps):
                if sr.get("step_id") == step_id and sr.get("attempt") == attempt:
                    steps[i] = {
                        **sr,
                        "state": "failed",
                        "completed_at": now,
                        "error": {"category": "other", "code": "STEP_FAILED",
                                  "message": reason},
                    }
                    cur["steps"] = steps
                    return cur
            # Otherwise append terminal failed record
            entry: dict[str, Any] = {
                "step_id": step_id,
                "step_name": step_def.step_name,
                "state": "failed",
                "actor": step_def.actor,
                "started_at": now,
                "completed_at": now,
                "attempt": attempt,
                "error": {"category": "other", "code": "STEP_FAILED",
                          "message": reason},
            }
            if step_def.adapter_id:
                entry["adapter_id"] = step_def.adapter_id
            steps.append(entry)
            cur["steps"] = steps
            return cur
        return self._cas_mutate(run_id, _mutator)

    def _append_attempt_placeholder(
        self,
        run_id: str,
        record: Mapping[str, Any],
        step_def: StepDefinition,
        *,
        step_id: str,
        attempt: int,
    ) -> dict[str, Any]:
        now = _now_iso()

        def _mutator(cur: dict[str, Any]) -> dict[str, Any]:
            steps = list(cur.get("steps", []))
            steps.append({
                "step_id": step_id,
                "step_name": step_def.step_name,
                "state": "running",
                "actor": step_def.actor,
                "started_at": now,
                "attempt": attempt,
                **({"adapter_id": step_def.adapter_id} if step_def.adapter_id else {}),
            })
            cur["steps"] = steps
            return cur
        return self._cas_mutate(run_id, _mutator)

    def _update_placeholder_to_completed(
        self,
        run_id: str,
        record: Mapping[str, Any],
        step_id: str,
        exec_result: Any,
        *,
        attempt: int,
        capability_output_refs: Mapping[str, str] | None = None,
    ) -> dict[str, Any]:
        """PR-B6 v4 §2.2 absorb: retry-success path for per-capability
        artifact refs. ``capability_output_refs`` is threaded from
        ``_run_adapter_step`` retry return tuple and persisted on the
        step_record, ensuring the map does not silently drop on
        attempt=2 success."""
        now = _now_iso()
        output_ref = getattr(exec_result, "output_ref", None)
        if output_ref is None and isinstance(exec_result, Mapping):
            output_ref = exec_result.get("output_ref")

        def _mutator(cur: dict[str, Any]) -> dict[str, Any]:
            steps = list(cur.get("steps", []))
            for i, sr in enumerate(steps):
                if sr.get("step_id") == step_id:
                    updated = dict(sr)
                    updated["state"] = "completed"
                    updated["completed_at"] = now
                    if output_ref:
                        updated["output_ref"] = output_ref
                    if capability_output_refs:
                        updated["capability_output_refs"] = dict(
                            capability_output_refs
                        )
                    steps[i] = updated
                    break
            cur["steps"] = steps
            return cur
        return self._cas_mutate(run_id, _mutator)

    def _update_placeholder_to_failed(
        self,
        run_id: str,
        record: Mapping[str, Any],
        step_id: str,
        *,
        reason: str,
    ) -> dict[str, Any]:
        now = _now_iso()

        def _mutator(cur: dict[str, Any]) -> dict[str, Any]:
            steps = list(cur.get("steps", []))
            for i, sr in enumerate(steps):
                if sr.get("step_id") == step_id:
                    updated = dict(sr)
                    updated["state"] = "failed"
                    updated["completed_at"] = now
                    updated["error"] = {"category": "other", "code": "RETRY_FAILED",
                                         "message": reason}
                    steps[i] = updated
                    break
            cur["steps"] = steps
            return cur
        return self._cas_mutate(run_id, _mutator)

    def _record_step_completion(
        self,
        run_id: str,
        record: Mapping[str, Any],
        step_def: StepDefinition,
        exec_result: Any,
        *,
        attempt: int,
        step_id: str,
        capability_output_refs: Mapping[str, str] | None = None,
    ) -> dict[str, Any]:
        """Append or update a step_record for a successful step.

        PR-B6 v4 §2.2 absorb: ``capability_output_refs`` (optional) maps
        capability name → run-relative artifact path for each per-capability
        typed artifact written by the driver (only the adapter dispatch
        path populates this; other actors pass the default empty/None).
        When non-empty, persisted on ``step_record["capability_output_refs"]``.
        """
        now = _now_iso()
        # Emit step_completed for ao-kernel / system dispatches (adapter
        # path already emits step_completed via Executor.run_step when
        # driver_managed=True propagates a completed status).
        if step_def.actor in ("ao-kernel", "system"):
            is_context_compile = (
                isinstance(exec_result, Mapping)
                and exec_result.get("operation") == "context_compile"
            )
            payload: dict[str, Any] = {
                "step_name": step_def.step_name,
                "final_state": "completed",
                "attempt": attempt,
            }
            if is_context_compile and isinstance(exec_result, Mapping):
                # PR-C1a: context_compile real materialisation — read
                # actual values from handler return dict. Empty fixture
                # yields bytes=0 (no canonical + no facts + no session);
                # stub=False regardless since handler wrote markdown.
                payload["stub"] = False
                payload["operation"] = "context_compile"
                payload["context_preamble_bytes"] = exec_result.get(
                    "context_preamble_bytes", 0
                )
                ctx_path = exec_result.get("context_path")
                if ctx_path is not None:
                    payload["context_path"] = ctx_path
            self._emit(run_id, "step_completed", payload, step_id=step_id)

        output_ref = None
        if isinstance(exec_result, Mapping):
            output_ref = exec_result.get("output_ref")
        elif hasattr(exec_result, "output_ref"):
            output_ref = getattr(exec_result, "output_ref", None)

        def _mutator(cur: dict[str, Any]) -> dict[str, Any]:
            steps = list(cur.get("steps", []))
            # Check if a placeholder exists (retry attempt=2 path)
            for i, sr in enumerate(steps):
                if sr.get("step_id") == step_id and sr.get("state") == "running":
                    updated = dict(sr)
                    updated["state"] = "completed"
                    updated["completed_at"] = now
                    if output_ref:
                        updated["output_ref"] = output_ref
                    if capability_output_refs:
                        updated["capability_output_refs"] = dict(
                            capability_output_refs
                        )
                    steps[i] = updated
                    cur["steps"] = steps
                    return cur
            # Append new terminal completed record (first attempt + ao-kernel/system)
            # For adapter steps in driver_managed=True path, Executor
            # emits step_completed but does NOT persist the step_record;
            # driver must persist here.
            record_entry: dict[str, Any] = {
                "step_id": step_id,
                "step_name": step_def.step_name,
                "state": "completed",
                "actor": step_def.actor,
                "started_at": now,
                "completed_at": now,
                "attempt": attempt,
            }
            if step_def.adapter_id:
                record_entry["adapter_id"] = step_def.adapter_id
            if output_ref:
                record_entry["output_ref"] = output_ref
            if capability_output_refs:
                # PR-B6 v4 §2.2: persist per-capability artifact refs when
                # the adapter dispatch populated them. Empty map absent
                # (schema additionalProperties: false respected).
                record_entry["capability_output_refs"] = dict(
                    capability_output_refs
                )
            steps.append(record_entry)
            cur["steps"] = steps
            return cur
        return self._cas_mutate(run_id, _mutator)

    # ------------------------------------------------------------------
    # Terminal transitions
    # ------------------------------------------------------------------

    def _transition_to_failed(
        self,
        run_id: str,
        record: Mapping[str, Any],
        start: float,
        *,
        category: str,
        code: str,
        message: str,
        failed_step: str | None = None,
        steps_executed: set[str] | None = None,
        steps_failed: set[str] | None = None,
        steps_retried: set[str] | None = None,
    ) -> DriverResult:
        completed = steps_executed or self._completed_step_names(record)
        failed_set = steps_failed or set()
        retried = steps_retried or set()

        def _mutator(cur: dict[str, Any]) -> dict[str, Any]:
            validate_transition(cur["state"], "failed")
            cur["state"] = "failed"
            cur["completed_at"] = _now_iso()
            cur["error"] = {
                "category": _legal_error_category(category),
                "code": code,
                "message": message,
            }
            return cur
        new_record = self._cas_mutate(run_id, _mutator)

        self._emit(run_id, "workflow_failed",
            {"category": _legal_error_category(category), "code": code,
             "reason": message, "failed_step": failed_step})

        return DriverResult(
            run_id=run_id,
            final_state="failed",
            steps_executed=tuple(sorted(completed)),
            steps_failed=tuple(sorted(failed_set | ({failed_step} if failed_step else set()))),
            steps_retried=tuple(sorted(retried)),
            resume_token=None,
            resume_token_kind=None,
            budget_consumed=new_record.get("budget"),
            duration_seconds=time.monotonic() - start,
        )

    def _transition_to_completed(
        self,
        run_id: str,
        record: Mapping[str, Any],
        start: float,
        *,
        completed: set[str],
        retried: set[str],
        budget_consumed: Any,
    ) -> DriverResult:
        # The 9-state machine only legalises `verifying -> completed`.
        # If the dispatched steps never visited applying/verifying (e.g.
        # a flow of only context_compile / adapter invocations), walk a
        # synthetic transition chain to reach `completed` without
        # violating the state machine contract. CAS bookkeeping only;
        # no spurious evidence events emitted.
        cur_state = record["state"]
        chain: list[str] = []
        if cur_state == "running":
            chain = ["applying", "verifying", "completed"]
        elif cur_state == "applying":
            chain = ["verifying", "completed"]
        elif cur_state == "verifying":
            chain = ["completed"]
        else:
            chain = ["completed"]

        new_record: dict[str, Any] = dict(record)
        for idx, next_state in enumerate(chain):
            extras: Mapping[str, Any] = (
                {"completed_at": _now_iso()}
                if next_state == "completed" else {}
            )
            new_record = self._cas_state_transition(
                run_id, new_record, next_state, extra=extras,
            )
        self._emit(run_id, "workflow_completed",
            {"steps_executed": sorted(completed)})
        return DriverResult(
            run_id=run_id,
            final_state="completed",
            steps_executed=tuple(sorted(completed)),
            steps_failed=(),
            steps_retried=tuple(sorted(retried)),
            resume_token=None,
            resume_token_kind=None,
            budget_consumed=new_record.get("budget"),
            duration_seconds=time.monotonic() - start,
        )

    def _idempotent_terminal_result(
        self,
        run_id: str,
        record: Mapping[str, Any],
        state: str,
        start: float,
    ) -> DriverResult:
        """Reconstruct DriverResult for a run already in terminal state."""
        completed = self._completed_step_names(record)
        retried = self._retried_step_names(record)
        failed_names = set()
        for sr in record.get("steps", ()):
            if sr.get("state") == "failed":
                failed_names.add(sr.get("step_name"))
        return DriverResult(
            run_id=run_id,
            final_state=state,  # type: ignore[arg-type]
            steps_executed=tuple(sorted(completed)),
            steps_failed=tuple(sorted(n for n in failed_names if n)),
            steps_retried=tuple(sorted(retried)),
            resume_token=None,
            resume_token_kind=None,
            budget_consumed=record.get("budget"),
            duration_seconds=0.0,
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _completed_step_names(self, record: Mapping[str, Any]) -> set[str]:
        """step_name's whose highest-attempt step_record.state == completed."""
        by_name: dict[str, dict[str, Any]] = {}
        for sr in record.get("steps", ()):
            name = sr.get("step_name")
            if not name:
                continue
            prior = by_name.get(name)
            if prior is None or sr.get("attempt", 1) > prior.get("attempt", 1):
                by_name[name] = sr
        return {n for n, sr in by_name.items() if sr.get("state") == "completed"}

    def _retried_step_names(self, record: Mapping[str, Any]) -> set[str]:
        """step_name's with any attempt >= 2."""
        names = set()
        for sr in record.get("steps", ()):
            if (sr.get("attempt") or 1) >= 2:
                names.add(sr.get("step_name"))
        return {n for n in names if n}

    def _is_retryable_terminal(
        self, record: Mapping[str, Any], definition: Any,
    ) -> bool:
        """MV1 invariant: highest-attempt failed + on_failure=retry_once + attempt<2."""
        if record["state"] != "failed":
            return False
        by_name_def = {s.step_name: s for s in definition.steps}
        by_name_attempts: dict[str, list[dict[str, Any]]] = {}
        for sr in record.get("steps", ()):
            n = sr.get("step_name")
            if not n:
                continue
            by_name_attempts.setdefault(n, []).append(sr)
        for name, entries in by_name_attempts.items():
            step_def = by_name_def.get(name)
            if step_def is None or step_def.on_failure != "retry_once":
                continue
            highest = max(entries, key=lambda e: e.get("attempt", 1))
            if highest.get("state") == "failed" and highest.get("attempt", 1) < 2:
                return True
        return False

    def _next_attempt_number(
        self, record: Mapping[str, Any], step_name: str,
    ) -> int:
        """Find the next attempt number or resume a non-terminal placeholder."""
        highest = 0
        for sr in record.get("steps", ()):
            if sr.get("step_name") == step_name:
                highest = max(highest, sr.get("attempt", 1))
        # If highest is a non-terminal placeholder (state=running), the
        # caller is resuming it — return the same attempt number.
        # Otherwise the next attempt is highest + 1 (or 1 if nothing yet).
        if highest == 0:
            return 1
        for sr in record.get("steps", ()):
            if (sr.get("step_name") == step_name
                and sr.get("attempt", 1) == highest
                and sr.get("state") == "running"):
                return highest  # resume placeholder, don't increment
        return highest + 1

    def _step_id_for_attempt(self, step_name: str, attempt: int) -> str:
        if attempt <= 1:
            return step_name
        # Append short unique suffix so step_id is fresh and schema-unique
        return f"{step_name}-a{attempt}-{uuid.uuid4().hex[:6]}"

    def _find_pending_approval(
        self, record: Mapping[str, Any], token: str,
    ) -> Mapping[str, Any] | None:
        for a in record.get("approvals", ()):
            if a.get("approval_token") == token and not a.get("decision"):
                return dict(a)
        return None

    def _find_pending_interrupt(
        self, record: Mapping[str, Any], token: str,
    ) -> Mapping[str, Any] | None:
        for i in record.get("interrupts", ()):
            if i.get("interrupt_token") == token and not i.get("resumed_at"):
                return dict(i)
        return None

    def _build_sandbox(self, run_id: str) -> SandboxedEnvironment:
        worktree = self._workspace_root / ".ao" / "runs" / run_id / "worktree"
        if not worktree.exists():
            worktree = self._workspace_root
        resolved_secrets, _ = resolve_allowed_secrets(self._policy, {})
        sandbox, _violations = build_sandbox(
            policy=self._policy,
            worktree_root=worktree,
            resolved_secrets=resolved_secrets,
            parent_env={},
        )
        return sandbox

    def _emit(
        self,
        run_id: str,
        kind: str,
        payload: Mapping[str, Any],
        *,
        step_id: str | None = None,
        actor: str = "ao-kernel",
        replay_safe: bool = True,
    ) -> None:
        # B2 absorb: approval_granted/denied are non-deterministic
        if kind in ("approval_granted", "approval_denied"):
            replay_safe = False
        try:
            emit_event(
                self._workspace_root,
                run_id=run_id, kind=kind, actor=actor,
                payload=dict(payload), step_id=step_id,
                replay_safe=replay_safe,
            )
        except Exception:  # noqa: BLE001 - evidence write is best-effort side-channel
            # Evidence emission failure must not block the main flow
            # (CLAUDE.md §2 fail-open side-channel invariant)
            pass


# ---------------------------------------------------------------------------
# Module helpers
# ---------------------------------------------------------------------------


# PR-B6 v4 iter-2 B4 absorb: `_LEGAL_CATEGORIES` is the runtime source
# of truth for driver-side error category coercion and MUST stay
# byte-identical with `workflow-run.schema.v1.json::error.category.enum`.
# Prior drift (pre-B6): runtime had `adapter_error` which schema did
# NOT carry; schema had `invocation_failed`, `output_parse_failed`,
# `adapter_crash` which runtime did NOT carry. `_legal_error_category`
# fallback to "other" masked the drift for drivers emitting new
# categories. Parity is now required + test-enforced.
_LEGAL_CATEGORIES = {
    "timeout",
    "invocation_failed",        # transport-layer adapter fail
    "output_parse_failed",      # walker fail or capability artifact write fail
    "policy_denied",
    "budget_exhausted",
    "adapter_crash",            # subprocess crash
    "approval_denied",
    "ci_failed",
    "apply_conflict",
    "other",
}


def _legal_error_category(requested: str) -> str:
    """Map a driver-side category to the schema-legal enum (B4 absorb)."""
    return requested if requested in _LEGAL_CATEGORIES else "other"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _load_pending_patch_content(
    record: Mapping[str, Any], step_name: str,
) -> str:
    """MVP: test fixtures supply patch content via record.intent.payload.patches[step_name].

    Production wiring (PR-A6) will sequence this from the prior
    adapter's output_ref — A4b scope limits integration to fixtures.
    """
    intent_payload = record.get("intent", {}).get("payload", {})
    if isinstance(intent_payload, Mapping):
        patches = intent_payload.get("patches", {}) or {}
        content = patches.get(step_name) if isinstance(patches, Mapping) else None
        if isinstance(content, str):
            return content
    return ""
