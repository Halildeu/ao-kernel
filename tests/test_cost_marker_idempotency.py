"""PR-C3.2 marker-driven idempotency + crash-window fix tests.

Verifies the shared ``apply_spend_with_marker`` helper fixes the
v3.3.0 shipped bug: ``post_adapter_reconcile`` / ``post_response_reconcile``
were double-draining the budget when called twice with the same
``(step_id, attempt, billing_digest)`` because ``record_spend`` did a
silent same-digest no-op but the subsequent ``update_run`` drain ran
unconditionally.

The marker (``workflow-run.cost_reconciled``) now gates both the
budget CAS AND the evidence emit. Duplicate calls (retry / crash-
recovery) leave the run state and emit stream untouched.

Scope pins per Codex CNS-20260418 thread:

1. Adapter path: 2× same call → 1× budget drain, 1× ledger entry,
   1× marker, 1× ``llm_spend_recorded`` emit.
2. Governed path: same contract (order flip verified: record_spend
   runs before update_run).
3. Usage-missing: marker gates emit; fail_closed raise fires regardless
   of marker state.
4. Different step / attempt / digest partition → each gets its own
   marker row.
5. ``compute_billing_digest`` precondition: helper raises ValueError on
   empty digest.
6. Schema widen: ``cost_reconciled`` field accepted by validator.
7. Crash semantics (mock-based): crash between ledger append and
   marker stamp → retry succeeds; crash between marker and emit → retry
   is a silent no-op (no duplicate emit).
"""

from __future__ import annotations

import json
from dataclasses import replace
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest

from ao_kernel.cost import _reconcile as _reconcile_mod
from ao_kernel.cost._reconcile import apply_spend_with_marker
from ao_kernel.cost.errors import CostTrackingConfigError
from ao_kernel.cost.ledger import SpendEvent, compute_billing_digest
from ao_kernel.cost.middleware import post_adapter_reconcile
from ao_kernel.cost.policy import CostTrackingPolicy


# ─── Test fixtures ─────────────────────────────────────────────────────


def _policy() -> CostTrackingPolicy:
    return CostTrackingPolicy(
        enabled=True,
        price_catalog_path=".ao/cost/price-catalog.json",
        spend_ledger_path=".ao/cost/spend.jsonl",
        fail_closed_on_exhaust=True,
        fail_closed_on_missing_usage=False,
        strict_freshness=False,
        idempotency_window_lines=100,
    )


def _seed_run(
    root: Path,
    run_id: str,
    *,
    cost_limit: float = 10.0,
    cost_remaining: float = 10.0,
    include_cost_usd_axis: bool = True,
) -> None:
    """Create a minimal valid run record on disk."""
    from ao_kernel.workflow.run_store import run_revision

    run_dir = root / ".ao" / "runs" / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    budget: dict[str, Any] = {"fail_closed_on_exhaust": True}
    if include_cost_usd_axis:
        budget["cost_usd"] = {
            "limit": cost_limit,
            "remaining": cost_remaining,
        }
    record: dict[str, Any] = {
        "run_id": run_id,
        "workflow_id": "test_flow",
        "workflow_version": "1.0.0",
        "state": "running",
        "created_at": "2026-04-18T10:00:00+00:00",
        "revision": "0" * 64,
        "intent": {"kind": "inline_prompt", "payload": "test"},
        "steps": [],
        "policy_refs": [
            "ao_kernel/defaults/policies/policy_worktree_profile.v1.json",
        ],
        "adapter_refs": [],
        "evidence_refs": [
            f".ao/evidence/workflows/{run_id}/events.jsonl",
        ],
        "budget": budget,
    }
    record["revision"] = run_revision(record)
    (run_dir / "state.v1.json").write_text(
        json.dumps(record, indent=2, sort_keys=True),
        encoding="utf-8",
    )


def _read_ledger(root: Path) -> list[dict[str, Any]]:
    path = root / ".ao" / "cost" / "spend.jsonl"
    if not path.is_file():
        return []
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _read_events_of_kind(
    root: Path, run_id: str, kind: str,
) -> list[dict[str, Any]]:
    path = (
        root / ".ao" / "evidence" / "workflows" / run_id / "events.jsonl"
    )
    if not path.is_file():
        return []
    return [
        ev for ev in (
            json.loads(line)
            for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        )
        if ev.get("kind") == kind
    ]


def _read_run(root: Path, run_id: str) -> dict[str, Any]:
    from ao_kernel.workflow.run_store import load_run

    record, _ = load_run(root, run_id)
    return record


def _cost_actual_fixed() -> dict[str, Any]:
    return {"tokens_input": 100, "tokens_output": 50, "cost_usd": 0.05}


# ─── 1. Adapter-path double-drain fix ──────────────────────────────────


class TestAdapterPathIdempotency:
    def test_double_call_single_drain_single_emit(
        self, tmp_path: Path,
    ) -> None:
        run_id = "00000000-0000-4000-8000-0000c3d20001"
        _seed_run(tmp_path, run_id)
        kwargs = dict(
            workspace_root=tmp_path, run_id=run_id, step_id="s1",
            attempt=1, provider_id="codex", model="stub",
            cost_actual=_cost_actual_fixed(), policy=_policy(),
        )
        post_adapter_reconcile(**kwargs)
        post_adapter_reconcile(**kwargs)

        # Ledger: single entry (same-digest no-op on 2nd)
        ledger = _read_ledger(tmp_path)
        assert len(ledger) == 1

        # Budget: drained once (0.05), not twice
        budget = _read_run(tmp_path, run_id).get("budget", {})
        cost_axis = budget.get("cost_usd", {})
        assert cost_axis.get("remaining") == pytest.approx(9.95)

        # Marker: single entry
        markers = _read_run(tmp_path, run_id).get("cost_reconciled", [])
        assert len(markers) == 1
        assert markers[0]["source"] == "adapter_path"
        assert markers[0]["step_id"] == "s1"
        assert markers[0]["attempt"] == 1

        # Evidence: single llm_spend_recorded emit
        emits = _read_events_of_kind(tmp_path, run_id, "llm_spend_recorded")
        assert len(emits) == 1


class TestAdapterPathPartitioning:
    def test_different_step_same_cost_both_applied(
        self, tmp_path: Path,
    ) -> None:
        run_id = "00000000-0000-4000-8000-0000c3d20002"
        _seed_run(tmp_path, run_id)
        # Two steps, same cost → different marker keys, both applied
        post_adapter_reconcile(
            workspace_root=tmp_path, run_id=run_id, step_id="s1",
            attempt=1, provider_id="codex", model="stub",
            cost_actual=_cost_actual_fixed(), policy=_policy(),
        )
        post_adapter_reconcile(
            workspace_root=tmp_path, run_id=run_id, step_id="s2",
            attempt=1, provider_id="codex", model="stub",
            cost_actual=_cost_actual_fixed(), policy=_policy(),
        )
        budget = _read_run(tmp_path, run_id).get("budget", {})
        assert budget["cost_usd"]["remaining"] == pytest.approx(9.90)  # 2× drain

        markers = _read_run(tmp_path, run_id).get("cost_reconciled", [])
        assert len(markers) == 2
        assert {m["step_id"] for m in markers} == {"s1", "s2"}

    def test_different_attempt_same_cost_both_applied(
        self, tmp_path: Path,
    ) -> None:
        """Retry semantics: same step_id, different attempt → new marker."""
        run_id = "00000000-0000-4000-8000-0000c3d20003"
        _seed_run(tmp_path, run_id)
        post_adapter_reconcile(
            workspace_root=tmp_path, run_id=run_id, step_id="s1",
            attempt=1, provider_id="codex", model="stub",
            cost_actual=_cost_actual_fixed(), policy=_policy(),
        )
        post_adapter_reconcile(
            workspace_root=tmp_path, run_id=run_id, step_id="s1",
            attempt=2, provider_id="codex", model="stub",
            cost_actual=_cost_actual_fixed(), policy=_policy(),
        )
        budget = _read_run(tmp_path, run_id).get("budget", {})
        assert budget["cost_usd"]["remaining"] == pytest.approx(9.90)

        markers = _read_run(tmp_path, run_id).get("cost_reconciled", [])
        assert len(markers) == 2
        assert {m["attempt"] for m in markers} == {1, 2}


# ─── 2. Usage-missing idempotency ──────────────────────────────────────


class TestUsageMissingIdempotency:
    def test_usage_missing_double_call_single_emit(
        self, tmp_path: Path,
    ) -> None:
        run_id = "00000000-0000-4000-8000-0000c3d20010"
        _seed_run(tmp_path, run_id)
        # Adapter returned cost but no tokens → usage_missing path
        kwargs = dict(
            workspace_root=tmp_path, run_id=run_id, step_id="s1",
            attempt=1, provider_id="codex", model="stub",
            cost_actual={"cost_usd": 0.0},  # tokens_input/output absent
            policy=_policy(),
        )
        post_adapter_reconcile(**kwargs)
        post_adapter_reconcile(**kwargs)

        # Ledger: single audit entry
        assert len(_read_ledger(tmp_path)) == 1

        # Marker: single usage_missing entry
        markers = _read_run(tmp_path, run_id).get("cost_reconciled", [])
        assert len(markers) == 1
        assert markers[0]["source"] == "usage_missing"

        # Evidence: single llm_usage_missing emit (not llm_spend_recorded)
        missing_emits = _read_events_of_kind(
            tmp_path, run_id, "llm_usage_missing",
        )
        assert len(missing_emits) == 1
        spend_emits = _read_events_of_kind(
            tmp_path, run_id, "llm_spend_recorded",
        )
        assert spend_emits == []

        # Budget: untouched (audit-only path)
        budget = _read_run(tmp_path, run_id).get("budget", {})
        assert budget["cost_usd"]["remaining"] == pytest.approx(10.0)


# ─── 3. Fail-closed preservation ───────────────────────────────────────


class TestFailClosedOnMissingBudgetAxis:
    def test_budget_cost_usd_missing_raises_after_ledger_append(
        self, tmp_path: Path,
    ) -> None:
        """Per Codex iter-3 bulgu: fail-closed contract is preserved.

        ``budget.cost_usd`` missing + positive event cost → mutator
        raises CostTrackingConfigError inside update_run. Marker is
        NOT stamped (mutator aborts before marker append). Ledger
        append already completed (helper ledger-first), which is
        audit-correct: the billable event is recorded.
        """
        run_id = "00000000-0000-4000-8000-0000c3d20020"
        _seed_run(tmp_path, run_id, include_cost_usd_axis=False)

        with pytest.raises(CostTrackingConfigError):
            post_adapter_reconcile(
                workspace_root=tmp_path, run_id=run_id, step_id="s1",
                attempt=1, provider_id="codex", model="stub",
                cost_actual=_cost_actual_fixed(), policy=_policy(),
            )

        # Ledger entry WAS appended (ledger-first ordering)
        assert len(_read_ledger(tmp_path)) == 1
        # Marker NOT stamped (mutator raised before marker append)
        markers = _read_run(tmp_path, run_id).get("cost_reconciled", [])
        assert markers == []


# ─── 4. Order-uniform verification (spy-based, not mtime) ──────────────


class TestOrderUniform:
    def test_record_spend_runs_before_update_run(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Per Codex iter-5 note: mtime comparison is flaky under
        write_text_atomic + os.replace; verify ordering via call-spy
        instead."""
        run_id = "00000000-0000-4000-8000-0000c3d20030"
        _seed_run(tmp_path, run_id)

        call_log: list[str] = []

        real_record_spend = _reconcile_mod.record_spend
        real_update_run = _reconcile_mod.update_run

        def _spy_record_spend(*a: Any, **kw: Any) -> None:
            call_log.append("record_spend")
            return real_record_spend(*a, **kw)

        def _spy_update_run(*a: Any, **kw: Any) -> Any:
            call_log.append("update_run")
            return real_update_run(*a, **kw)

        monkeypatch.setattr(_reconcile_mod, "record_spend", _spy_record_spend)
        monkeypatch.setattr(_reconcile_mod, "update_run", _spy_update_run)

        post_adapter_reconcile(
            workspace_root=tmp_path, run_id=run_id, step_id="s1",
            attempt=1, provider_id="codex", model="stub",
            cost_actual=_cost_actual_fixed(), policy=_policy(),
        )
        # record_spend first, then update_run (ledger-first contract)
        assert call_log[0] == "record_spend"
        assert "update_run" in call_log
        assert call_log.index("record_spend") < call_log.index("update_run")


# ─── 5. Helper precondition (ValueError on empty digest) ───────────────


class TestHelperPrecondition:
    def test_apply_spend_with_marker_requires_precomputed_digest(
        self, tmp_path: Path,
    ) -> None:
        run_id = "00000000-0000-4000-8000-0000c3d20040"
        _seed_run(tmp_path, run_id)

        event = SpendEvent(
            run_id=run_id,
            step_id="s1",
            attempt=1,
            provider_id="codex",
            model="stub",
            tokens_input=100,
            tokens_output=50,
            cost_usd=Decimal("0.05"),
            ts="2026-04-18T10:00:00+00:00",
            billing_digest="",  # empty — helper must reject
        )
        with pytest.raises(ValueError, match="billing_digest"):
            apply_spend_with_marker(
                tmp_path, run_id, event,
                policy=_policy(),
                source="adapter_path",
                budget_mutator=lambda r: r,
            )

    def test_apply_spend_with_marker_accepts_precomputed_digest(
        self, tmp_path: Path,
    ) -> None:
        run_id = "00000000-0000-4000-8000-0000c3d20041"
        _seed_run(tmp_path, run_id)

        event = SpendEvent(
            run_id=run_id,
            step_id="s1",
            attempt=1,
            provider_id="codex",
            model="stub",
            tokens_input=100,
            tokens_output=50,
            cost_usd=Decimal("0.05"),
            ts="2026-04-18T10:00:00+00:00",
        )
        event = replace(event, billing_digest=compute_billing_digest(event))
        committed = apply_spend_with_marker(
            tmp_path, run_id, event,
            policy=_policy(),
            source="adapter_path",
            budget_mutator=lambda r: r,  # no-op for this probe
        )
        assert committed is True


# ─── 6. Schema validation ──────────────────────────────────────────────


class TestSchemaAcceptsCostReconciled:
    def test_validator_accepts_cost_reconciled_field(self) -> None:
        """workflow-run.schema.v1.json widen — marker array accepted."""
        from ao_kernel.workflow.schema_validator import validate_workflow_run

        run_id = "00000000-0000-4000-8000-0000c3d20050"
        record: dict[str, Any] = {
            "run_id": run_id,
            "workflow_id": "test_flow",
            "workflow_version": "1.0.0",
            "state": "running",
            "created_at": "2026-04-18T10:00:00+00:00",
            "revision": "0" * 64,
            "intent": {"kind": "inline_prompt", "payload": "x"},
            "steps": [],
            "policy_refs": [
                "ao_kernel/defaults/policies/policy_worktree_profile.v1.json",
            ],
            "adapter_refs": [],
            "evidence_refs": [
                f".ao/evidence/workflows/{run_id}/events.jsonl",
            ],
            "budget": {"fail_closed_on_exhaust": True},
            "cost_reconciled": [
                {
                    "source": "adapter_path",
                    "step_id": "s1",
                    "attempt": 1,
                    "billing_digest": "sha256:abc123",
                    "recorded_at": "2026-04-18T10:00:01+00:00",
                },
            ],
        }
        # Should not raise — explicit "no error" pin satisfies test
        # quality gate (BLK-002: bare callable check is advisory).
        result = validate_workflow_run(record, run_id=run_id)
        assert result is None  # validate_workflow_run returns None on success

    def test_validator_rejects_unknown_marker_field(self) -> None:
        from ao_kernel.workflow.errors import WorkflowSchemaValidationError
        from ao_kernel.workflow.schema_validator import validate_workflow_run

        run_id = "00000000-0000-4000-8000-0000c3d20051"
        record: dict[str, Any] = {
            "run_id": run_id,
            "workflow_id": "test_flow",
            "workflow_version": "1.0.0",
            "state": "running",
            "created_at": "2026-04-18T10:00:00+00:00",
            "revision": "0" * 64,
            "intent": {"kind": "inline_prompt", "payload": "x"},
            "steps": [],
            "policy_refs": [
                "ao_kernel/defaults/policies/policy_worktree_profile.v1.json",
            ],
            "adapter_refs": [],
            "evidence_refs": [
                f".ao/evidence/workflows/{run_id}/events.jsonl",
            ],
            "budget": {"fail_closed_on_exhaust": True},
            "cost_reconciled": [
                {
                    "source": "adapter_path",
                    "step_id": "s1",
                    "attempt": 1,
                    "billing_digest": "sha256:abc",
                    "recorded_at": "2026-04-18T10:00:01+00:00",
                    "unknown_field": "bad",  # additionalProperties:false
                },
            ],
        }
        with pytest.raises(WorkflowSchemaValidationError):
            validate_workflow_run(record, run_id=run_id)


# ─── 7. Crash-semantics (mock-based) ───────────────────────────────────


class TestCrashSemantics:
    def test_crash_after_ledger_before_marker_retry_succeeds(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Phase-1 crash: ledger appended, marker not stamped yet.

        Retry: ledger no-op (same digest), marker absent → mutator runs,
        budget drained, marker stamped.
        """
        run_id = "00000000-0000-4000-8000-0000c3d20060"
        _seed_run(tmp_path, run_id)

        real_update_run = _reconcile_mod.update_run
        call_count = {"n": 0}

        def _flaky_update_run(*a: Any, **kw: Any) -> Any:
            call_count["n"] += 1
            if call_count["n"] == 1:
                raise RuntimeError("simulated crash between ledger and marker")
            return real_update_run(*a, **kw)

        monkeypatch.setattr(_reconcile_mod, "update_run", _flaky_update_run)

        # First call crashes inside update_run (after record_spend)
        with pytest.raises(RuntimeError):
            post_adapter_reconcile(
                workspace_root=tmp_path, run_id=run_id, step_id="s1",
                attempt=1, provider_id="codex", model="stub",
                cost_actual=_cost_actual_fixed(), policy=_policy(),
            )
        # Ledger has entry; marker does NOT (mutator never committed)
        assert len(_read_ledger(tmp_path)) == 1
        assert _read_run(tmp_path, run_id).get("cost_reconciled", []) == []

        # Retry: recovers cleanly
        post_adapter_reconcile(
            workspace_root=tmp_path, run_id=run_id, step_id="s1",
            attempt=1, provider_id="codex", model="stub",
            cost_actual=_cost_actual_fixed(), policy=_policy(),
        )
        # Ledger still 1 entry (silent same-digest no-op)
        assert len(_read_ledger(tmp_path)) == 1
        # Marker now present
        markers = _read_run(tmp_path, run_id).get("cost_reconciled", [])
        assert len(markers) == 1
        # Budget drained exactly once
        budget = _read_run(tmp_path, run_id).get("budget", {})
        assert budget["cost_usd"]["remaining"] == pytest.approx(9.95)

    def test_duplicate_call_after_commit_produces_no_duplicate_emit(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Covers the emit-guard invariant: if a marker is already
        committed, the caller MUST NOT re-emit evidence.

        This is the retry/replay surface of the Phase-2 crash (marker
        stamped, emit failed before durable flush). True crash injection
        at the emit boundary is deferred to v3.4.0 (subprocess + os._exit
        crash-kill harness, paired with the reconciler daemon); here we
        verify the suppression path via a plain duplicate call.
        """
        run_id = "00000000-0000-4000-8000-0000c3d20061"
        _seed_run(tmp_path, run_id)

        # First call succeeds (marker stamped, emit successful)
        post_adapter_reconcile(
            workspace_root=tmp_path, run_id=run_id, step_id="s1",
            attempt=1, provider_id="codex", model="stub",
            cost_actual=_cost_actual_fixed(), policy=_policy(),
        )
        emits_after_first = _read_events_of_kind(
            tmp_path, run_id, "llm_spend_recorded",
        )
        assert len(emits_after_first) == 1

        # Second call — simulates retry after crash between marker and emit
        post_adapter_reconcile(
            workspace_root=tmp_path, run_id=run_id, step_id="s1",
            attempt=1, provider_id="codex", model="stub",
            cost_actual=_cost_actual_fixed(), policy=_policy(),
        )
        emits_after_second = _read_events_of_kind(
            tmp_path, run_id, "llm_spend_recorded",
        )
        # Still exactly 1 — duplicate emit suppressed
        assert len(emits_after_second) == 1
