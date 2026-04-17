"""Tests for PR-B5 C2b — ``llm_spend_recorded.duration_ms`` additive field.

Pinpoints the B2 middleware extension without touching the broader
B2 flow (regression coverage already lives in
``test_cost_middleware_core.py``). Focus:

1. ``elapsed_ms`` kwarg forwards into the emitted
   ``llm_spend_recorded`` payload as ``duration_ms``.
2. Backward-compat: ``elapsed_ms=None`` (default) keeps the legacy
   payload shape (no ``duration_ms`` key).
3. Floats are rounded to 3 decimals (Prometheus histograms convert
   ms→s, so excess precision is lost — rounding here keeps the
   evidence event compact and deterministic).
"""

from __future__ import annotations

import json
import uuid
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest

from ao_kernel.cost.catalog import PriceCatalogEntry, clear_catalog_cache
from ao_kernel.cost.middleware import (
    post_response_reconcile,
    pre_dispatch_reserve,
)
from ao_kernel.cost.policy import CostTrackingPolicy, RoutingByCost
from ao_kernel.workflow.run_store import create_run


@pytest.fixture(autouse=True)
def _reset_catalog_cache():
    clear_catalog_cache()
    yield
    clear_catalog_cache()


def _policy() -> CostTrackingPolicy:
    return CostTrackingPolicy(
        enabled=True,
        price_catalog_path=".ao/cost/catalog.v1.json",
        spend_ledger_path=".ao/cost/spend.jsonl",
        fail_closed_on_exhaust=True,
        strict_freshness=False,
        fail_closed_on_missing_usage=True,
        idempotency_window_lines=1000,
        routing_by_cost=RoutingByCost(enabled=False),
    )


def _entry() -> PriceCatalogEntry:
    return PriceCatalogEntry(
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


def _create_run_with_budget(ws: Path) -> str:
    rid = str(uuid.uuid4())
    budget: dict[str, Any] = {
        "fail_closed_on_exhaust": True,
        "cost_usd": {"limit": 10.0, "spent": 0.0, "remaining": 10.0},
    }
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


def _ok_response(input_tokens: int = 100, output_tokens: int = 50) -> bytes:
    return json.dumps(
        {
            "text": "response text",
            "usage": {
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
            },
        }
    ).encode("utf-8")


def _spend_events(ws: Path, run_id: str) -> list[dict[str, Any]]:
    events_path = (
        ws / ".ao" / "evidence" / "workflows" / run_id / "events.jsonl"
    )
    lines = events_path.read_text(encoding="utf-8").strip().splitlines()
    return [
        json.loads(line)
        for line in lines
        if json.loads(line).get("kind") == "llm_spend_recorded"
    ]


class TestDurationMsPassthrough:
    def test_elapsed_ms_appears_as_duration_ms(
        self, tmp_path: Path
    ) -> None:
        """C2b canonical case: ``elapsed_ms=250.5`` threads through
        the reconcile into the emitted ``llm_spend_recorded`` payload
        as ``duration_ms=250.5``. This is the single source of truth
        PR-B5 derivation reads for ``ao_llm_call_duration_seconds``."""
        run_id = _create_run_with_budget(tmp_path)
        policy = _policy()
        pre_dispatch_reserve(
            workspace_root=tmp_path,
            run_id=run_id,
            step_id="step-alpha",
            attempt=1,
            provider_id="anthropic",
            model="claude-3-5-sonnet",
            prompt_messages=[{"role": "user", "content": "hello"}],
            max_tokens=100,
            policy=policy,
        )
        post_response_reconcile(
            workspace_root=tmp_path,
            run_id=run_id,
            step_id="step-alpha",
            attempt=1,
            provider_id="anthropic",
            model="claude-3-5-sonnet",
            catalog_entry=_entry(),
            est_cost=Decimal("0.0010"),
            raw_response_bytes=_ok_response(),
            policy=policy,
            elapsed_ms=250.5,
        )

        spends = _spend_events(tmp_path, run_id)
        assert len(spends) == 1
        payload = spends[0].get("payload", spends[0])
        assert payload["duration_ms"] == 250.5


class TestDurationMsBackwardCompat:
    def test_duration_ms_omitted_when_elapsed_ms_none(
        self, tmp_path: Path
    ) -> None:
        """Backward compat (plan v4 R13): legacy callers that don't
        pass ``elapsed_ms`` see the pre-B5 payload shape — no
        ``duration_ms`` key at all, not ``None``. The derivation
        layer uses key-presence to decide "skip this call"."""
        run_id = _create_run_with_budget(tmp_path)
        policy = _policy()
        pre_dispatch_reserve(
            workspace_root=tmp_path,
            run_id=run_id,
            step_id="step-alpha",
            attempt=1,
            provider_id="anthropic",
            model="claude-3-5-sonnet",
            prompt_messages=[{"role": "user", "content": "hello"}],
            max_tokens=100,
            policy=policy,
        )
        # Omit elapsed_ms entirely (legacy caller shape).
        post_response_reconcile(
            workspace_root=tmp_path,
            run_id=run_id,
            step_id="step-alpha",
            attempt=1,
            provider_id="anthropic",
            model="claude-3-5-sonnet",
            catalog_entry=_entry(),
            est_cost=Decimal("0.0010"),
            raw_response_bytes=_ok_response(),
            policy=policy,
        )

        spends = _spend_events(tmp_path, run_id)
        assert len(spends) == 1
        payload = spends[0].get("payload", spends[0])
        assert "duration_ms" not in payload


class TestDurationMsPrecision:
    def test_float_rounded_to_three_decimals(
        self, tmp_path: Path
    ) -> None:
        """Excess precision is rounded to 3 decimals so the emitted
        event stays compact and deterministic across runs. Prometheus
        converts ms→s anyway, so sub-microsecond detail is noise."""
        run_id = _create_run_with_budget(tmp_path)
        policy = _policy()
        pre_dispatch_reserve(
            workspace_root=tmp_path,
            run_id=run_id,
            step_id="step-alpha",
            attempt=1,
            provider_id="anthropic",
            model="claude-3-5-sonnet",
            prompt_messages=[{"role": "user", "content": "hello"}],
            max_tokens=100,
            policy=policy,
        )
        post_response_reconcile(
            workspace_root=tmp_path,
            run_id=run_id,
            step_id="step-alpha",
            attempt=1,
            provider_id="anthropic",
            model="claude-3-5-sonnet",
            catalog_entry=_entry(),
            est_cost=Decimal("0.0010"),
            raw_response_bytes=_ok_response(),
            policy=policy,
            elapsed_ms=123.4567891234,  # well past 3 decimals
        )

        spends = _spend_events(tmp_path, run_id)
        payload = spends[0].get("payload", spends[0])
        assert payload["duration_ms"] == 123.457


class TestDurationMsAbsentInUsageMissingPath:
    def test_usage_missing_event_has_no_duration_ms(
        self, tmp_path: Path
    ) -> None:
        """Plan v4 R14: the usage-missing path emits
        ``llm_usage_missing`` (not ``llm_spend_recorded``), so
        ``duration_ms`` is not relevant there. This test pins the
        absence so derivation correctly excludes usage-miss calls
        from the duration histogram."""
        from ao_kernel.cost.errors import LLMUsageMissingError

        run_id = _create_run_with_budget(tmp_path)
        policy = _policy()
        pre_dispatch_reserve(
            workspace_root=tmp_path,
            run_id=run_id,
            step_id="step-alpha",
            attempt=1,
            provider_id="anthropic",
            model="claude-3-5-sonnet",
            prompt_messages=[{"role": "user", "content": "hello"}],
            max_tokens=100,
            policy=policy,
        )
        # Missing-usage response → raises LLMUsageMissingError after
        # emitting ``llm_usage_missing`` (audit + no duration field).
        with pytest.raises(LLMUsageMissingError):
            post_response_reconcile(
                workspace_root=tmp_path,
                run_id=run_id,
                step_id="step-alpha",
                attempt=1,
                provider_id="anthropic",
                model="claude-3-5-sonnet",
                catalog_entry=_entry(),
                est_cost=Decimal("0.0010"),
                raw_response_bytes=b'{"text": "missing usage"}',
                policy=policy,
                elapsed_ms=250.5,  # passed but irrelevant
            )

        events_path = (
            tmp_path
            / ".ao"
            / "evidence"
            / "workflows"
            / run_id
            / "events.jsonl"
        )
        lines = events_path.read_text(encoding="utf-8").strip().splitlines()
        kinds = [json.loads(line).get("kind") for line in lines]
        assert "llm_usage_missing" in kinds
        # ``llm_spend_recorded`` must NOT be emitted in the missing
        # path; duration_ms has no carrier.
        assert "llm_spend_recorded" not in kinds
