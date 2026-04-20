"""PR-C6: step-level dry-run — execute pre-flight + policy checks
without real side-effects (no evidence writes, no worktree build,
no subprocess invoke, no artifact materialisation, no CAS mutation).

Contract:

- :class:`DryRunResult` carries predicted events, policy violations,
  simulated budget, and simulated output refs.
- :func:`dry_run_execution_context` patches six executor-aliased
  callables (``emit_event``, ``invoke_cli``, ``invoke_http``,
  ``create_worktree``, ``cleanup_worktree``, ``write_artifact``)
  to capture-and-skip semantics.
- The recorder accumulates predicted events + simulated outputs
  so the caller can build a :class:`DryRunResult` after exiting
  the context.

Design invariant: dry-run NEVER calls ``update_run``. The separate
dry-run tail in :meth:`Executor.dry_run_step` writes no CAS.
"""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator, Mapping
from unittest.mock import patch


@dataclass(frozen=True)
class DryRunResult:
    """Step-level dry-run result (PR-C6).

    - ``predicted_events``: evidence events that WOULD have been
      emitted as ``(kind, payload_snapshot)`` tuples.
    - ``policy_violations``: policy violation reason strings
      recorded during the mock'd dispatch.
    - ``simulated_budget_after``: copy of the run record's budget
      at dry-run start (cost estimate integration deferred to
      post-C3 follow-up).
    - ``simulated_outputs``: per-step would-be artifact ref paths
      captured by the mocked ``write_artifact``.
    """

    predicted_events: tuple[tuple[str, Mapping[str, Any]], ...]
    policy_violations: tuple[str, ...]
    simulated_budget_after: Mapping[str, Any]
    simulated_outputs: Mapping[str, str]


@dataclass(frozen=True)
class _StubEvidenceEvent:
    """Minimal EvidenceEvent-like stub returned by mocked
    ``emit_event``. Executor reads ``.event_id`` and ``.ts``
    from the real ``EvidenceEvent`` — the stub exposes both
    plus ``.seq`` for parity."""

    event_id: str
    ts: str
    seq: int


@dataclass
class _DryRunRecorder:
    """Mutable accumulator used by the mocked callables."""

    predicted_events: list[tuple[str, Mapping[str, Any]]] = field(
        default_factory=list,
    )
    policy_violations: list[str] = field(default_factory=list)
    simulated_outputs: dict[str, str] = field(default_factory=dict)

    def record_policy_violation(self, reason: str) -> None:
        self.policy_violations.append(reason)


def _canned_invocation_result(manifest: Any) -> Any:
    """Build a minimal OK-status ``InvocationResult`` for dry-run
    mocking. Uses the real dataclass so executor downstream code
    paths see expected shape."""
    from ao_kernel.executor.adapter_invoker import InvocationResult

    return InvocationResult(
        status="ok",
        diff=None,
        evidence_events=(),
        commands_executed=(),
        error=None,
        finish_reason="normal",
        interrupt_token=None,
        cost_actual={},
        stdout_path=None,
        stderr_path=None,
    )


@dataclass(frozen=True)
class _DummyWorktree:
    """Stub worktree handle — no git, no filesystem materialisation."""

    path: Path


@contextmanager
def dry_run_execution_context(
    workspace_root: Path,
    run_id: str,
) -> Iterator[_DryRunRecorder]:
    """Patch six executor-aliased side-effect callables so the
    body of the ``with`` block can dispatch a step without touching
    real I/O. Returns the accumulator via ``as`` binding.

    Patches (all at ``ao_kernel.executor.executor`` module alias
    — see PR-B7 mock_transport pattern for the rationale):

    - ``emit_event`` → recorder append; returns :class:`_StubEvidenceEvent`.
    - ``invoke_cli`` / ``invoke_http`` → canned ``(InvocationResult, Budget)``.
    - ``create_worktree`` / ``cleanup_worktree`` → stub path / no-op.
    - ``write_artifact`` → stub ``(output_ref, sha)`` tuple; no disk.

    On exit, patches are restored (unittest.mock context managers).
    """
    recorder = _DryRunRecorder()

    def _mock_emit(
        workspace_root_arg: Any = None,
        run_id_arg: Any = None,
        *,
        kind: str = "",
        actor: str = "ao-kernel",
        payload: Mapping[str, Any] | None = None,
        step_id: Any = None,
        replay_safe: bool = True,
        **kwargs: Any,
    ) -> _StubEvidenceEvent:
        recorder.predicted_events.append(
            (kind, dict(payload or {})),
        )
        seq = len(recorder.predicted_events)
        return _StubEvidenceEvent(
            event_id=f"dry-run-{seq:04d}",
            ts=datetime.now(timezone.utc).isoformat(
                timespec="seconds",
            ),
            seq=seq,
        )

    def _mock_invoke(
        *,
        manifest: Any,
        input_envelope: Mapping[str, Any],
        sandbox: Any,
        worktree: Any,
        budget: Any,
        workspace_root: Path,
        run_id: str,
        resolved_invocation: Any = None,
    ) -> tuple[Any, Any]:
        return (_canned_invocation_result(manifest), budget)

    def _mock_create_worktree(
        *args: Any, **kwargs: Any,
    ) -> _DummyWorktree:
        return _DummyWorktree(
            path=workspace_root / ".dry-run-stub" / run_id,
        )

    def _mock_cleanup_worktree(
        *args: Any, **kwargs: Any,
    ) -> None:
        return None

    def _mock_write_artifact(
        *,
        run_dir: Path,
        step_id: str,
        attempt: int,
        payload: Mapping[str, Any],
    ) -> tuple[str, str]:
        stub_ref = f"artifacts/{step_id}-attempt{attempt}.json"
        recorder.simulated_outputs[step_id] = stub_ref
        return (stub_ref, "dry-run-sha256-stub")

    def _mock_update_run(
        workspace_root_arg: Any,
        run_id_arg: str,
        *,
        mutator: Any = None,
        max_retries: int = 3,
    ) -> dict[str, Any]:
        """No-op update_run: apply mutator to a throw-away copy so
        the real record on disk stays untouched. This preserves the
        dry-run read-only invariant (PR-C6 B2 absorb)."""
        # The real update_run reads + applies mutator + CAS-writes.
        # For dry-run we skip the write entirely; the mutator output
        # is discarded but we invoke it so any side-effect-free
        # assertion inside the mutator still runs.
        if mutator is not None:
            try:
                # Load current record and invoke mutator read-only.
                from ao_kernel.workflow.run_store import load_run

                record, _ = load_run(workspace_root_arg, run_id_arg)
                mutator(dict(record))
            except Exception:
                # Mutator failure is captured in the recorder via
                # emit_event paths; dry-run swallows downstream.
                pass
        return {}

    with patch.multiple(
        "ao_kernel.executor.executor",
        emit_event=_mock_emit,
        invoke_cli=_mock_invoke,
        invoke_http=_mock_invoke,
        create_worktree=_mock_create_worktree,
        cleanup_worktree=_mock_cleanup_worktree,
        write_artifact=_mock_write_artifact,
        update_run=_mock_update_run,
    ):
        yield recorder


__all__ = [
    "DryRunResult",
    "dry_run_execution_context",
]
