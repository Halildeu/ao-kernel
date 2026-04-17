"""Tests for PR-B2 commit 5a — cost middleware + governed_call.

Focused on the middleware core: pre_dispatch_reserve,
post_response_reconcile, and the governed_call wrapper. Integration
with 3 caller paths (client/mcp_server/intent_router) lands in
commit 5b with its own test file.
"""

from __future__ import annotations

import json
import uuid
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest

from ao_kernel.cost.catalog import PriceCatalogEntry, clear_catalog_cache
from ao_kernel.cost.errors import (
    BudgetExhaustedError,
    CostTrackingConfigError,
    LLMUsageMissingError,
    PriceCatalogNotFoundError,
)
from ao_kernel.cost.middleware import (
    post_response_reconcile,
    pre_dispatch_reserve,
)
from ao_kernel.cost.policy import CostTrackingPolicy, RoutingByCost
from ao_kernel.workflow.run_store import create_run, load_run


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


def _entry(**overrides: Any) -> PriceCatalogEntry:
    base = dict(
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
    base.update(overrides)
    return PriceCatalogEntry(**base)


def _create_run_with_cost_budget(
    ws: Path,
    *,
    cost_limit_usd: str = "10.00",
    run_id: str | None = None,
    with_granular_tokens: bool = False,
) -> str:
    """Helper: create a workflow-run with cost_usd axis (required for
    cost-active pipeline per Option A / CostTrackingConfigError).

    Returns the run_id (caller uses it directly for middleware calls).
    """
    rid = run_id or str(uuid.uuid4())
    budget: dict[str, Any] = {
        "fail_closed_on_exhaust": True,
        "cost_usd": {
            "limit": float(cost_limit_usd),
            "spent": 0.0,
            "remaining": float(cost_limit_usd),
        },
    }
    if with_granular_tokens:
        budget["tokens_input"] = {"limit": 10000, "spent": 0, "remaining": 10000}
        budget["tokens_output"] = {"limit": 5000, "spent": 0, "remaining": 5000}
    create_run(
        ws,
        run_id=rid,
        workflow_id="bug_fix_flow",
        workflow_version="1.0.0",
        intent={"kind": "inline_prompt", "payload": "test"},
        budget=budget,
        policy_refs=[
            "ao_kernel/defaults/policies/policy_worktree_profile.v1.json"
        ],
        evidence_refs=[".ao/evidence/workflows/x/events.jsonl"],
    )
    return rid


def _create_run_without_cost_axis(ws: Path) -> str:
    rid = str(uuid.uuid4())
    create_run(
        ws,
        run_id=rid,
        workflow_id="bug_fix_flow",
        workflow_version="1.0.0",
        intent={"kind": "inline_prompt", "payload": "test"},
        budget={"fail_closed_on_exhaust": True},  # no cost_usd axis
        policy_refs=[
            "ao_kernel/defaults/policies/policy_worktree_profile.v1.json"
        ],
        evidence_refs=[".ao/evidence/workflows/x/events.jsonl"],
    )
    return rid


def _ok_response(input_tokens: int, output_tokens: int) -> bytes:
    return json.dumps(
        {
            "text": "response text",
            "usage": {
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
            },
        }
    ).encode("utf-8")


def _missing_usage_response() -> bytes:
    return json.dumps({"text": "response text"}).encode("utf-8")


class TestPreDispatchReserveHappyPath:
    def test_reserves_budget_and_returns_entry(self, tmp_path: Path) -> None:
        run_id = _create_run_with_cost_budget(tmp_path)
        policy = _policy()
        messages = [{"role": "user", "content": "hello " * 100}]

        est_cost, entry = pre_dispatch_reserve(
            workspace_root=tmp_path,
            run_id=run_id,
            step_id="step-alpha",
            attempt=1,
            provider_id="anthropic",
            model="claude-3-5-sonnet",
            prompt_messages=messages,
            max_tokens=100,
            policy=policy,
        )

        assert est_cost > Decimal("0")
        assert entry.provider_id == "anthropic"
        assert entry.model == "claude-3-5-sonnet"

        # Verify budget.cost_usd.spent incremented on the run record
        record, _ = load_run(tmp_path, run_id)
        spent = record["budget"]["cost_usd"]["spent"]
        assert spent > 0
        assert float(spent) == float(est_cost)


class TestPreDispatchCatalogMiss:
    def test_unknown_model_raises(self, tmp_path: Path) -> None:
        run_id = _create_run_with_cost_budget(tmp_path)
        with pytest.raises(PriceCatalogNotFoundError) as excinfo:
            pre_dispatch_reserve(
                workspace_root=tmp_path,
                run_id=run_id,
                step_id="step",
                attempt=1,
                provider_id="ghost-provider",
                model="ghost-model",
                prompt_messages=[{"role": "user", "content": "x"}],
                max_tokens=100,
                policy=_policy(),
            )
        assert excinfo.value.provider_id == "ghost-provider"
        assert excinfo.value.model == "ghost-model"


class TestPreDispatchConfigError:
    def test_no_cost_axis_raises_config_error(self, tmp_path: Path) -> None:
        """Option A: policy.enabled=true + no cost_usd axis → fail-closed
        before transport."""
        run_id = _create_run_without_cost_axis(tmp_path)
        with pytest.raises(CostTrackingConfigError) as excinfo:
            pre_dispatch_reserve(
                workspace_root=tmp_path,
                run_id=run_id,
                step_id="step",
                attempt=1,
                provider_id="anthropic",
                model="claude-3-5-sonnet",
                prompt_messages=[{"role": "user", "content": "x"}],
                max_tokens=100,
                policy=_policy(),
            )
        assert excinfo.value.run_id == run_id


class TestPreDispatchBudgetExhausted:
    def test_estimate_exceeds_remaining_raises(self, tmp_path: Path) -> None:
        # Tiny budget — single call with any real prompt exceeds
        run_id = _create_run_with_cost_budget(
            tmp_path, cost_limit_usd="0.0001"
        )
        with pytest.raises(BudgetExhaustedError) as excinfo:
            pre_dispatch_reserve(
                workspace_root=tmp_path,
                run_id=run_id,
                step_id="step",
                attempt=1,
                provider_id="anthropic",
                model="claude-3-5-sonnet",
                prompt_messages=[
                    {"role": "user", "content": "hello " * 200}
                ],
                max_tokens=500,
                policy=_policy(),
            )
        assert excinfo.value.run_id == run_id
        # No ledger lines written — pre-dispatch guard fired
        ledger = tmp_path / ".ao" / "cost" / "spend.jsonl"
        assert not ledger.exists()


class TestPostResponseReconcileHappyPath:
    def test_reconciles_actual_and_writes_ledger(self, tmp_path: Path) -> None:
        run_id = _create_run_with_cost_budget(tmp_path)
        policy = _policy()

        # Reserve first
        est_cost, entry = pre_dispatch_reserve(
            workspace_root=tmp_path,
            run_id=run_id,
            step_id="step",
            attempt=1,
            provider_id="anthropic",
            model="claude-3-5-sonnet",
            prompt_messages=[{"role": "user", "content": "hello world"}],
            max_tokens=100,
            policy=policy,
        )

        # Reconcile with actual usage
        post_response_reconcile(
            workspace_root=tmp_path,
            run_id=run_id,
            step_id="step",
            attempt=1,
            provider_id="anthropic",
            model="claude-3-5-sonnet",
            catalog_entry=entry,
            est_cost=est_cost,
            raw_response_bytes=_ok_response(input_tokens=1000, output_tokens=500),
            policy=policy,
        )

        # Ledger line exists with actual cost
        ledger = tmp_path / ".ao" / "cost" / "spend.jsonl"
        assert ledger.is_file()
        lines = [
            json.loads(line)
            for line in ledger.read_text(encoding="utf-8").strip().splitlines()
        ]
        assert len(lines) == 1
        assert lines[0]["tokens_input"] == 1000
        assert lines[0]["tokens_output"] == 500
        assert lines[0]["usage_missing"] is False
        assert "billing_digest" in lines[0]

    def test_refund_when_actual_less_than_estimate(self, tmp_path: Path) -> None:
        """actual < estimate → delta negative → budget refunded."""
        run_id = _create_run_with_cost_budget(tmp_path)
        policy = _policy()

        est_cost, entry = pre_dispatch_reserve(
            workspace_root=tmp_path,
            run_id=run_id,
            step_id="step",
            attempt=1,
            provider_id="anthropic",
            model="claude-3-5-sonnet",
            prompt_messages=[{"role": "user", "content": "hello " * 500}],
            max_tokens=1000,
            policy=policy,
        )

        # Actual usage much lower than estimate → refund expected
        post_response_reconcile(
            workspace_root=tmp_path,
            run_id=run_id,
            step_id="step",
            attempt=1,
            provider_id="anthropic",
            model="claude-3-5-sonnet",
            catalog_entry=entry,
            est_cost=est_cost,
            raw_response_bytes=_ok_response(input_tokens=10, output_tokens=5),
            policy=policy,
        )

        record, _ = load_run(tmp_path, run_id)
        spent = Decimal(str(record["budget"]["cost_usd"]["spent"]))
        # Spent should reflect actual (small), not estimate (large)
        assert spent < est_cost


class TestPostResponseUsageMissing:
    def test_fail_closed_raises(self, tmp_path: Path) -> None:
        run_id = _create_run_with_cost_budget(tmp_path)
        policy = _policy()  # fail_closed_on_missing_usage=True default

        est_cost, entry = pre_dispatch_reserve(
            workspace_root=tmp_path,
            run_id=run_id,
            step_id="step",
            attempt=1,
            provider_id="anthropic",
            model="claude-3-5-sonnet",
            prompt_messages=[{"role": "user", "content": "hello"}],
            max_tokens=100,
            policy=policy,
        )

        with pytest.raises(LLMUsageMissingError) as excinfo:
            post_response_reconcile(
                workspace_root=tmp_path,
                run_id=run_id,
                step_id="step",
                attempt=1,
                provider_id="anthropic",
                model="claude-3-5-sonnet",
                catalog_entry=entry,
                est_cost=est_cost,
                raw_response_bytes=_missing_usage_response(),
                policy=policy,
            )

        assert "tokens_input" in excinfo.value.missing_fields
        assert "tokens_output" in excinfo.value.missing_fields

        # Audit-only ledger entry recorded BEFORE the raise
        ledger = tmp_path / ".ao" / "cost" / "spend.jsonl"
        lines = [
            json.loads(line)
            for line in ledger.read_text(encoding="utf-8").strip().splitlines()
        ]
        assert len(lines) == 1
        assert lines[0]["usage_missing"] is True
        assert lines[0]["cost_usd"] == 0.0

    def test_fail_open_warns_and_continues(
        self, tmp_path: Path, caplog
    ) -> None:
        """fail_closed_on_missing_usage=false → warn + continue."""
        run_id = _create_run_with_cost_budget(tmp_path)
        policy = _policy(fail_closed_on_missing_usage=False)

        est_cost, entry = pre_dispatch_reserve(
            workspace_root=tmp_path,
            run_id=run_id,
            step_id="step",
            attempt=1,
            provider_id="anthropic",
            model="claude-3-5-sonnet",
            prompt_messages=[{"role": "user", "content": "hello"}],
            max_tokens=100,
            policy=policy,
        )

        with caplog.at_level("WARNING"):
            # Should NOT raise
            post_response_reconcile(
                workspace_root=tmp_path,
                run_id=run_id,
                step_id="step",
                attempt=1,
                provider_id="anthropic",
                model="claude-3-5-sonnet",
                catalog_entry=entry,
                est_cost=est_cost,
                raw_response_bytes=_missing_usage_response(),
                policy=policy,
            )

        assert any(
            "missing usage" in rec.getMessage()
            for rec in caplog.records
        )


class TestEvidenceEmits:
    def test_cost_estimated_emitted(self, tmp_path: Path) -> None:
        run_id = _create_run_with_cost_budget(tmp_path)

        pre_dispatch_reserve(
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

        events_path = (
            tmp_path / ".ao" / "evidence" / "workflows" / run_id / "events.jsonl"
        )
        # Evidence file should exist and carry llm_cost_estimated event
        assert events_path.is_file()
        lines = events_path.read_text(encoding="utf-8").strip().splitlines()
        kinds = [json.loads(line).get("kind") for line in lines]
        assert "llm_cost_estimated" in kinds

    def test_spend_recorded_emitted(self, tmp_path: Path) -> None:
        run_id = _create_run_with_cost_budget(tmp_path)
        policy = _policy()

        est_cost, entry = pre_dispatch_reserve(
            workspace_root=tmp_path,
            run_id=run_id,
            step_id="step",
            attempt=1,
            provider_id="anthropic",
            model="claude-3-5-sonnet",
            prompt_messages=[{"role": "user", "content": "hi"}],
            max_tokens=100,
            policy=policy,
        )
        post_response_reconcile(
            workspace_root=tmp_path,
            run_id=run_id,
            step_id="step",
            attempt=1,
            provider_id="anthropic",
            model="claude-3-5-sonnet",
            catalog_entry=entry,
            est_cost=est_cost,
            raw_response_bytes=_ok_response(50, 20),
            policy=policy,
        )

        events_path = (
            tmp_path / ".ao" / "evidence" / "workflows" / run_id / "events.jsonl"
        )
        lines = events_path.read_text(encoding="utf-8").strip().splitlines()
        kinds = [json.loads(line).get("kind") for line in lines]
        assert "llm_spend_recorded" in kinds

    def test_usage_missing_emitted(self, tmp_path: Path) -> None:
        run_id = _create_run_with_cost_budget(tmp_path)
        policy = _policy(fail_closed_on_missing_usage=False)

        est_cost, entry = pre_dispatch_reserve(
            workspace_root=tmp_path,
            run_id=run_id,
            step_id="step",
            attempt=1,
            provider_id="anthropic",
            model="claude-3-5-sonnet",
            prompt_messages=[{"role": "user", "content": "hi"}],
            max_tokens=100,
            policy=policy,
        )
        post_response_reconcile(
            workspace_root=tmp_path,
            run_id=run_id,
            step_id="step",
            attempt=1,
            provider_id="anthropic",
            model="claude-3-5-sonnet",
            catalog_entry=entry,
            est_cost=est_cost,
            raw_response_bytes=_missing_usage_response(),
            policy=policy,
        )

        events_path = (
            tmp_path / ".ao" / "evidence" / "workflows" / run_id / "events.jsonl"
        )
        lines = events_path.read_text(encoding="utf-8").strip().splitlines()
        kinds = [json.loads(line).get("kind") for line in lines]
        assert "llm_usage_missing" in kinds


class TestEvidenceKindsRegistered:
    def test_three_new_kinds_in_emitter(self) -> None:
        from ao_kernel.executor.evidence_emitter import _KINDS

        assert "llm_cost_estimated" in _KINDS
        assert "llm_spend_recorded" in _KINDS
        assert "llm_usage_missing" in _KINDS
        # Total should be 24 (PR-B1) + 3 (PR-B2) = 27
        assert len(_KINDS) == 27


class TestGovernedCallContract:
    def test_governed_call_docstring_pins_streaming_boundary(self) -> None:
        """Regression guard: plan v5 iter-4 B2 pin — non-streaming only.

        We assert the docstring because streaming behavior is not
        exercisable at unit level without a full transport mock;
        end-to-end streaming-bypass regression lands in commit 5b
        integration tests (test_client_llm_call_stream_untouched).
        """
        from ao_kernel.llm import governed_call

        doc = (governed_call.__doc__ or "").lower()
        assert "non-streaming" in doc, (
            "governed_call docstring must explicitly state non-streaming "
            "boundary (plan v5 iter-4 B2 absorb)"
        )
        assert "stream" in doc
        assert "capability_gap" in doc
        assert "transport_error" in doc

    def test_governed_call_docstring_pins_rich_success_return(self) -> None:
        """Regression guard: plan v5 iter-4 B1 pin — success returns rich
        dict with status/normalized/resp_bytes/transport_result/elapsed_ms.
        """
        from ao_kernel.llm import governed_call

        doc = (governed_call.__doc__ or "").lower()
        for token in ("status", "normalized", "resp_bytes", "transport_result", "elapsed_ms"):
            assert token in doc, (
                f"governed_call docstring must pin rich return field {token!r}"
            )
