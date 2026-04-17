"""Concurrent-writer + CAS retry exhaustion tests for cost runtime.

CNS-032 post-merge scope absorb: the single-writer ``record_spend`` paths
are covered in ``test_cost_ledger.py``. This file exercises:

- Parallel ``record_spend`` invocations across multiple threads — the
  sidecar ``file_lock`` must serialise writes so the final JSONL has
  no interleaved bytes and every distinct ``(run_id, step_id, attempt)``
  key produces exactly one line.
- Concurrent writes with IDENTICAL idempotency keys — first writer wins,
  subsequent writers no-op silently under the lock (warn-log path).
- CAS retry exhaustion — when ``update_run`` exhausts ``max_retries=3``
  inside ``pre_dispatch_reserve``, the ``WorkflowCASConflictError``
  propagates through the middleware to the caller.
"""

from __future__ import annotations

import json
import threading
import uuid
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest

from ao_kernel.cost.catalog import clear_catalog_cache
from ao_kernel.cost.ledger import SpendEvent, record_spend
from ao_kernel.cost.policy import CostTrackingPolicy, RoutingByCost
from ao_kernel.workflow.errors import WorkflowCASConflictError
from ao_kernel.workflow.run_store import create_run


@pytest.fixture(autouse=True)
def _reset_catalog_cache():
    clear_catalog_cache()
    yield
    clear_catalog_cache()


def _policy(**overrides: Any) -> CostTrackingPolicy:
    defaults = dict(
        enabled=True,
        price_catalog_path=".ao/cost/catalog.v1.json",
        spend_ledger_path=".ao/cost/spend.jsonl",
        fail_closed_on_exhaust=True,
        strict_freshness=False,
        fail_closed_on_missing_usage=True,
        idempotency_window_lines=1000,
        routing_by_cost=RoutingByCost(enabled=False),
    )
    defaults.update(overrides)
    return CostTrackingPolicy(**defaults)


def _event(
    *,
    run_id: str = "11111111-1111-4111-8111-111111111111",
    step_id: str = "step-alpha",
    attempt: int = 1,
    cost_usd: Decimal = Decimal("0.0105"),
) -> SpendEvent:
    return SpendEvent(
        run_id=run_id,
        step_id=step_id,
        attempt=attempt,
        provider_id="anthropic",
        model="claude-3-5-sonnet",
        tokens_input=1000,
        tokens_output=500,
        cost_usd=cost_usd,
        ts="2026-04-17T12:00:00+00:00",
    )


def _read_ledger(workspace_root: Path) -> list[dict[str, Any]]:
    ledger = workspace_root / ".ao" / "cost" / "spend.jsonl"
    if not ledger.is_file():
        return []
    return [
        json.loads(line)
        for line in ledger.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _run_threads(
    target: Any,
    args_per_thread: list[tuple[Any, ...]],
) -> list[BaseException]:
    """Spawn one thread per args tuple, join all, return any captured
    exceptions in thread-start order."""
    captured: list[BaseException | None] = [None] * len(args_per_thread)

    def _wrap(idx: int, args: tuple[Any, ...]) -> None:
        try:
            target(*args)
        except BaseException as exc:
            captured[idx] = exc

    threads = [
        threading.Thread(target=_wrap, args=(i, args))
        for i, args in enumerate(args_per_thread)
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=10.0)
        assert not t.is_alive(), f"thread {t} did not finish within 10s"
    return [e for e in captured if e is not None]


# ─── Parallel distinct keys — file_lock serialization ────────────────


class TestConcurrentDistinctKeys:
    def test_all_distinct_keys_appended(self, tmp_path: Path) -> None:
        """Five threads record distinct events in parallel. The sidecar
        lock serialises writes → the ledger contains exactly 5 lines,
        one per thread, all schema-valid JSON."""
        policy = _policy()
        events = [
            _event(step_id=f"step-{i}", attempt=1, cost_usd=Decimal("0.01"))
            for i in range(5)
        ]
        errors = _run_threads(
            lambda e: record_spend(tmp_path, e, policy=policy),
            [(e,) for e in events],
        )
        assert errors == []

        lines = _read_ledger(tmp_path)
        assert len(lines) == 5
        step_ids = {line["step_id"] for line in lines}
        assert step_ids == {f"step-{i}" for i in range(5)}

    def test_concurrent_writes_not_interleaved(self, tmp_path: Path) -> None:
        """Ten threads with distinct events. Every line must parse as a
        complete JSON object — proof that fsync + lock prevent torn
        writes."""
        policy = _policy()
        events = [
            _event(
                run_id=str(uuid.uuid4()),
                step_id=f"step-{i}",
                attempt=1,
                cost_usd=Decimal("0.005"),
            )
            for i in range(10)
        ]
        errors = _run_threads(
            lambda e: record_spend(tmp_path, e, policy=policy),
            [(e,) for e in events],
        )
        assert errors == []

        # Reading succeeds: every line is a full JSON object.
        lines = _read_ledger(tmp_path)
        assert len(lines) == 10
        for line in lines:
            assert "billing_digest" in line
            assert "run_id" in line
            assert "attempt" in line

    def test_higher_concurrency_preserves_line_count(
        self, tmp_path: Path
    ) -> None:
        """Twenty distinct events in parallel — harsher stress test for
        the lock. Line count remains exact."""
        policy = _policy()
        events = [
            _event(
                run_id=str(uuid.uuid4()),
                step_id=f"stress-{i}",
                attempt=1,
            )
            for i in range(20)
        ]
        errors = _run_threads(
            lambda e: record_spend(tmp_path, e, policy=policy),
            [(e,) for e in events],
        )
        assert errors == []
        assert len(_read_ledger(tmp_path)) == 20


# ─── Parallel identical keys — idempotency under lock ────────────────


class TestConcurrentIdenticalKeys:
    def test_same_digest_concurrent_only_one_line(
        self, tmp_path: Path
    ) -> None:
        """Five threads submit an identical event. The first writer wins
        the lock and appends; the rest scan the tail, find their key with
        the same digest, and no-op. Final count: 1."""
        policy = _policy()
        shared_event = _event()
        errors = _run_threads(
            lambda: record_spend(tmp_path, shared_event, policy=policy),
            [() for _ in range(5)],
        )
        assert errors == []

        lines = _read_ledger(tmp_path)
        assert len(lines) == 1
        assert lines[0]["run_id"] == shared_event.run_id
        assert lines[0]["step_id"] == shared_event.step_id


# ─── CAS retry exhaustion ───────────────────────────────────────────


class TestCASRetryExhaustion:
    def test_update_run_conflict_propagates_from_pre_dispatch(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Simulate a persistent CAS conflict inside update_run. The
        middleware asks for ``max_retries=3``; when the retry loop
        exhausts, ``WorkflowCASConflictError`` propagates unchanged."""
        from ao_kernel.cost import middleware

        run_id = str(uuid.uuid4())
        create_run(
            tmp_path,
            run_id=run_id,
            workflow_id="bug_fix_flow",
            workflow_version="1.0.0",
            intent={"kind": "inline_prompt", "payload": "x"},
            budget={
                "fail_closed_on_exhaust": True,
                "cost_usd": {
                    "limit": 10.0,
                    "spent": 0.0,
                    "remaining": 10.0,
                },
            },
            policy_refs=[
                "ao_kernel/defaults/policies/policy_worktree_profile.v1.json"
            ],
            evidence_refs=[".ao/evidence/workflows/x/events.jsonl"],
        )

        call_count = {"n": 0}

        def _always_conflict(*_args: Any, **_kwargs: Any) -> None:
            call_count["n"] += 1
            raise WorkflowCASConflictError(
                run_id=run_id,
                expected_revision="expected",
                actual_revision="actual",
            )

        monkeypatch.setattr(middleware, "update_run", _always_conflict)

        with pytest.raises(WorkflowCASConflictError) as excinfo:
            middleware.pre_dispatch_reserve(
                workspace_root=tmp_path,
                run_id=run_id,
                step_id="step",
                attempt=1,
                provider_id="anthropic",
                model="claude-3-5-sonnet",
                prompt_messages=[{"role": "user", "content": "hi"}],
                max_tokens=100,
                policy=_policy(),
            )

        assert excinfo.value.run_id == run_id
        # Middleware calls update_run exactly once per reserve; the
        # internal retry loop lives inside run_store.update_run. Our
        # monkeypatch simulates the post-exhaustion raise.
        assert call_count["n"] == 1

    def test_update_run_conflict_propagates_from_post_reconcile(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Same contract on the reconcile side — CAS exhaustion
        during budget reconcile raises through the middleware."""
        from ao_kernel.cost import middleware
        from ao_kernel.cost.catalog import PriceCatalogEntry

        run_id = str(uuid.uuid4())
        create_run(
            tmp_path,
            run_id=run_id,
            workflow_id="bug_fix_flow",
            workflow_version="1.0.0",
            intent={"kind": "inline_prompt", "payload": "x"},
            budget={
                "fail_closed_on_exhaust": True,
                "cost_usd": {
                    "limit": 10.0,
                    "spent": 0.0,
                    "remaining": 10.0,
                },
            },
            policy_refs=[
                "ao_kernel/defaults/policies/policy_worktree_profile.v1.json"
            ],
            evidence_refs=[".ao/evidence/workflows/x/events.jsonl"],
        )

        def _always_conflict(*_args: Any, **_kwargs: Any) -> None:
            raise WorkflowCASConflictError(
                run_id=run_id,
                expected_revision="expected",
                actual_revision="actual",
            )

        monkeypatch.setattr(middleware, "update_run", _always_conflict)

        entry = PriceCatalogEntry(
            provider_id="anthropic",
            model="claude-3-5-sonnet",
            input_cost_per_1k=0.003,
            output_cost_per_1k=0.015,
            cached_input_cost_per_1k=0.0003,
            currency="USD",
            billing_unit="per_1k_tokens",
            effective_date="2024-10-22",
            vendor_model_id="claude-3-5-sonnet-20241022",
        )
        raw = json.dumps(
            {"usage": {"input_tokens": 100, "output_tokens": 50}}
        ).encode("utf-8")

        with pytest.raises(WorkflowCASConflictError):
            middleware.post_response_reconcile(
                workspace_root=tmp_path,
                run_id=run_id,
                step_id="step",
                attempt=1,
                provider_id="anthropic",
                model="claude-3-5-sonnet",
                catalog_entry=entry,
                est_cost=Decimal("0.01"),
                raw_response_bytes=raw,
                policy=_policy(),
            )


# ─── Dormant bypass under concurrency ────────────────────────────────


class TestDormantConcurrent:
    def test_dormant_policy_no_file_under_concurrency(
        self, tmp_path: Path
    ) -> None:
        """Even with many concurrent callers, dormant policy must NOT
        create the ledger file or acquire the lock."""
        policy = _policy(enabled=False)
        errors = _run_threads(
            lambda: record_spend(tmp_path, _event(), policy=policy),
            [() for _ in range(5)],
        )
        assert errors == []
        ledger = tmp_path / ".ao" / "cost" / "spend.jsonl"
        assert not ledger.exists()
