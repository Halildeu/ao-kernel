"""End-to-end tests for ``governed_call`` with a mocked transport.

CNS-032 post-merge scope absorb: the middleware-core tests in
``test_cost_middleware_core.py`` exercise ``pre_dispatch_reserve`` and
``post_response_reconcile`` as primitives. This file closes the gap by
driving the full cost-active ``governed_call`` pipeline — build → transport
→ normalize → reconcile → ledger → evidence — with ``execute_request``
monkeypatched to return canned bytes.

Scope:

- OK flow (cost-active) — rich success dict, budget decremented, ledger
  appended, two evidence events (``llm_cost_estimated`` +
  ``llm_spend_recorded``) emitted.
- CAPABILITY_GAP envelope — no transport call, no ledger, no evidence.
- TRANSPORT_ERROR envelope — reservation HELD per Q5 iter-1,
  ``llm_cost_estimated`` emitted but no ``llm_spend_recorded``.
- Bypass path — any of the four identity kwargs missing → transparent
  pre-B2 flow (build + transport + normalize), no cost hooks.
- Refund semantics — actual < estimate → negative delta ledger entry.
- Usage-missing — fail-closed raise AND fail-open warn branches.
"""

from __future__ import annotations

import json
import uuid
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest

from ao_kernel.cost.catalog import clear_catalog_cache
from ao_kernel.cost.errors import LLMUsageMissingError
from ao_kernel.llm import governed_call
from ao_kernel.workflow.run_store import create_run, load_run


# ─── Fixtures + helpers ──────────────────────────────────────────────


@pytest.fixture(autouse=True)
def _reset_catalog_cache():
    clear_catalog_cache()
    yield
    clear_catalog_cache()


def _write_enabled_policy(
    workspace_root: Path,
    *,
    fail_closed_on_missing_usage: bool = True,
) -> None:
    """Drop a workspace override that flips the cost policy to enabled.

    The bundled default ``policy_cost_tracking.v1.json`` ships dormant
    (``enabled=false``). ``governed_call`` short-circuits to bypass mode
    when policy is dormant, so cost-active tests need this override.
    """
    policy_dir = workspace_root / ".ao" / "policies"
    policy_dir.mkdir(parents=True, exist_ok=True)
    (policy_dir / "policy_cost_tracking.v1.json").write_text(
        json.dumps(
            {
                "version": "v1",
                "enabled": True,
                "price_catalog_path": ".ao/cost/catalog.v1.json",
                "spend_ledger_path": ".ao/cost/spend.jsonl",
                "fail_closed_on_exhaust": True,
                "strict_freshness": False,
                "fail_closed_on_missing_usage": fail_closed_on_missing_usage,
                "idempotency_window_lines": 1000,
                "routing_by_cost": {"enabled": False},
            }
        )
        + "\n",
        encoding="utf-8",
    )


def _create_run_with_cost_budget(
    workspace_root: Path,
    *,
    cost_limit_usd: float = 10.0,
) -> str:
    """Create a workflow-run with a cost_usd axis (required for
    cost-active governed_call per Option A)."""
    run_id = str(uuid.uuid4())
    create_run(
        workspace_root,
        run_id=run_id,
        workflow_id="bug_fix_flow",
        workflow_version="1.0.0",
        intent={"kind": "inline_prompt", "payload": "test"},
        budget={
            "fail_closed_on_exhaust": True,
            "cost_usd": {
                "limit": cost_limit_usd,
                "spent": 0.0,
                "remaining": cost_limit_usd,
            },
        },
        policy_refs=[
            "ao_kernel/defaults/policies/policy_worktree_profile.v1.json"
        ],
        evidence_refs=[".ao/evidence/workflows/x/events.jsonl"],
    )
    return run_id


def _ok_transport_result(
    input_tokens: int = 50,
    output_tokens: int = 20,
    *,
    http_status: int = 200,
    elapsed_ms: int = 120,
) -> dict[str, Any]:
    """Canned transport response with Anthropic-style usage payload."""
    body = {
        "text": "mock response",
        "usage": {
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
        },
    }
    return {
        "status": "OK",
        "http_status": http_status,
        "resp_bytes": json.dumps(body).encode("utf-8"),
        "elapsed_ms": elapsed_ms,
    }


def _missing_usage_transport_result() -> dict[str, Any]:
    return {
        "status": "OK",
        "http_status": 200,
        "resp_bytes": json.dumps({"text": "mock response"}).encode("utf-8"),
        "elapsed_ms": 100,
    }


def _error_transport_result() -> dict[str, Any]:
    return {
        "status": "ERROR",
        "http_status": 504,
        "error_code": "TIMEOUT",
        "elapsed_ms": 30000,
    }


def _read_ledger_lines(workspace_root: Path) -> list[dict[str, Any]]:
    ledger = workspace_root / ".ao" / "cost" / "spend.jsonl"
    if not ledger.is_file():
        return []
    return [
        json.loads(line)
        for line in ledger.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _read_evidence_kinds(workspace_root: Path, run_id: str) -> list[str]:
    events_path = (
        workspace_root
        / ".ao"
        / "evidence"
        / "workflows"
        / run_id
        / "events.jsonl"
    )
    if not events_path.is_file():
        return []
    return [
        json.loads(line).get("kind", "")
        for line in events_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _base_call_kwargs() -> dict[str, Any]:
    return dict(
        messages=[{"role": "user", "content": "hello world"}],
        provider_id="anthropic",
        model="claude-3-5-sonnet",
        api_key="test-key",
        base_url="https://api.anthropic.test/v1",
        request_id="req-e2e-1",
    )


# ─── CAPABILITY_GAP envelope ─────────────────────────────────────────


class TestCapabilityGapEnvelope:
    def test_missing_capability_returns_envelope_no_transport(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """check_capabilities → (False, _, ['streaming']) → envelope with
        status=CAPABILITY_GAP. Transport MUST NOT be called."""
        call_count = {"transport": 0}

        def _fail_if_called(**_kwargs: Any) -> dict[str, Any]:
            call_count["transport"] += 1
            raise AssertionError(
                "execute_request must not be called after CAPABILITY_GAP"
            )

        monkeypatch.setattr(
            "ao_kernel.llm.check_capabilities",
            lambda **_: (False, "anthropic", ["streaming"]),
        )
        monkeypatch.setattr("ao_kernel.llm.execute_request", _fail_if_called)

        result = governed_call(**_base_call_kwargs())

        assert result["status"] == "CAPABILITY_GAP"
        assert result["missing"] == ["streaming"]
        assert result["text"] == ""
        assert result["provider_id"] == "anthropic"
        assert result["model"] == "claude-3-5-sonnet"
        assert result["request_id"] == "req-e2e-1"
        assert call_count["transport"] == 0

    def test_capability_gap_cost_active_no_ledger_no_evidence(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Cost-active wiring + capability gap → bail before reserve.
        No ledger lines, no evidence emits, budget untouched."""
        _write_enabled_policy(tmp_path)
        run_id = _create_run_with_cost_budget(tmp_path)

        monkeypatch.setattr(
            "ao_kernel.llm.check_capabilities",
            lambda **_: (False, "anthropic", ["vision"]),
        )

        result = governed_call(
            **_base_call_kwargs(),
            workspace_root=tmp_path,
            run_id=run_id,
            step_id="step-A",
            attempt=1,
        )

        assert result["status"] == "CAPABILITY_GAP"
        assert _read_ledger_lines(tmp_path) == []
        assert _read_evidence_kinds(tmp_path, run_id) == []
        record, _ = load_run(tmp_path, run_id)
        assert record["budget"]["cost_usd"]["spent"] == 0.0


# ─── TRANSPORT_ERROR envelope ────────────────────────────────────────


class TestTransportErrorEnvelope:
    def test_transport_error_returns_envelope(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(
            "ao_kernel.llm.check_capabilities",
            lambda **_: (True, "anthropic", []),
        )
        monkeypatch.setattr(
            "ao_kernel.llm.execute_request",
            lambda **_: _error_transport_result(),
        )

        result = governed_call(**_base_call_kwargs())

        assert result["status"] == "TRANSPORT_ERROR"
        assert result["error_code"] == "TIMEOUT"
        assert result["http_status"] == 504
        assert result["text"] == ""
        assert result["provider_id"] == "anthropic"
        assert result["model"] == "claude-3-5-sonnet"
        assert result["request_id"] == "req-e2e-1"
        assert result["elapsed_ms"] == 30000

    def test_transport_error_cost_active_reservation_held(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Transport error post-reserve: reservation HELD (Q5 iter-1),
        ledger EMPTY (no llm_spend_recorded), ``llm_cost_estimated``
        DID emit during pre_dispatch_reserve."""
        _write_enabled_policy(tmp_path)
        run_id = _create_run_with_cost_budget(tmp_path)

        monkeypatch.setattr(
            "ao_kernel.llm.check_capabilities",
            lambda **_: (True, "anthropic", []),
        )
        monkeypatch.setattr(
            "ao_kernel.llm.execute_request",
            lambda **_: _error_transport_result(),
        )

        result = governed_call(
            **_base_call_kwargs(),
            workspace_root=tmp_path,
            run_id=run_id,
            step_id="step-A",
            attempt=1,
        )

        assert result["status"] == "TRANSPORT_ERROR"
        assert _read_ledger_lines(tmp_path) == []
        record, _ = load_run(tmp_path, run_id)
        assert record["budget"]["cost_usd"]["spent"] > 0.0

        kinds = _read_evidence_kinds(tmp_path, run_id)
        assert "llm_cost_estimated" in kinds
        assert "llm_spend_recorded" not in kinds


# ─── OK flow (cost-active) ───────────────────────────────────────────


class TestOkCostActive:
    def test_full_cost_active_flow_rich_success_dict(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _write_enabled_policy(tmp_path)
        run_id = _create_run_with_cost_budget(tmp_path)

        monkeypatch.setattr(
            "ao_kernel.llm.check_capabilities",
            lambda **_: (True, "anthropic", []),
        )
        monkeypatch.setattr(
            "ao_kernel.llm.execute_request",
            lambda **_: _ok_transport_result(
                input_tokens=1000, output_tokens=500, elapsed_ms=420
            ),
        )

        result = governed_call(
            **_base_call_kwargs(),
            workspace_root=tmp_path,
            run_id=run_id,
            step_id="step-A",
            attempt=1,
        )

        assert result["status"] == "OK"
        assert "normalized" in result
        assert "resp_bytes" in result
        assert "transport_result" in result
        assert result["elapsed_ms"] == 420
        assert result["request_id"] == "req-e2e-1"
        assert isinstance(result["resp_bytes"], bytes)
        assert isinstance(result["normalized"], dict)
        assert result["normalized"].get("usage") is not None

    def test_full_cost_active_flow_ledger_appended(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _write_enabled_policy(tmp_path)
        run_id = _create_run_with_cost_budget(tmp_path)

        monkeypatch.setattr(
            "ao_kernel.llm.check_capabilities",
            lambda **_: (True, "anthropic", []),
        )
        monkeypatch.setattr(
            "ao_kernel.llm.execute_request",
            lambda **_: _ok_transport_result(
                input_tokens=1000, output_tokens=500
            ),
        )

        governed_call(
            **_base_call_kwargs(),
            workspace_root=tmp_path,
            run_id=run_id,
            step_id="step-A",
            attempt=1,
        )

        lines = _read_ledger_lines(tmp_path)
        assert len(lines) == 1
        entry = lines[0]
        assert entry["run_id"] == run_id
        assert entry["step_id"] == "step-A"
        assert entry["attempt"] == 1
        assert entry["tokens_input"] == 1000
        assert entry["tokens_output"] == 500
        assert entry["usage_missing"] is False
        assert entry["billing_digest"].startswith("sha256:")
        assert entry["cost_usd"] > 0

    def test_full_cost_active_flow_budget_decremented(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _write_enabled_policy(tmp_path)
        run_id = _create_run_with_cost_budget(tmp_path, cost_limit_usd=10.0)

        monkeypatch.setattr(
            "ao_kernel.llm.check_capabilities",
            lambda **_: (True, "anthropic", []),
        )
        monkeypatch.setattr(
            "ao_kernel.llm.execute_request",
            lambda **_: _ok_transport_result(
                input_tokens=1000, output_tokens=500
            ),
        )

        governed_call(
            **_base_call_kwargs(),
            workspace_root=tmp_path,
            run_id=run_id,
            step_id="step-A",
            attempt=1,
        )

        record, _ = load_run(tmp_path, run_id)
        spent = Decimal(str(record["budget"]["cost_usd"]["spent"]))
        # 1000 input tokens * $0.003/1k + 500 output tokens * $0.015/1k
        # = $0.003 + $0.0075 = $0.0105
        assert spent == Decimal("0.0105")
        remaining = Decimal(str(record["budget"]["cost_usd"]["remaining"]))
        assert remaining == Decimal("10.0") - spent

    def test_full_cost_active_flow_two_evidence_events(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """PR-B2 additive kinds — pre-dispatch + post-response both fire."""
        _write_enabled_policy(tmp_path)
        run_id = _create_run_with_cost_budget(tmp_path)

        monkeypatch.setattr(
            "ao_kernel.llm.check_capabilities",
            lambda **_: (True, "anthropic", []),
        )
        monkeypatch.setattr(
            "ao_kernel.llm.execute_request",
            lambda **_: _ok_transport_result(),
        )

        governed_call(
            **_base_call_kwargs(),
            workspace_root=tmp_path,
            run_id=run_id,
            step_id="step-A",
            attempt=1,
        )

        kinds = _read_evidence_kinds(tmp_path, run_id)
        assert "llm_cost_estimated" in kinds
        assert "llm_spend_recorded" in kinds
        # usage_missing must NOT emit on the happy path.
        assert "llm_usage_missing" not in kinds


# ─── Refund semantics ────────────────────────────────────────────────


class TestRefundSemantics:
    def test_actual_less_than_estimate_refunds_budget(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Reserve reservation is later adjusted down when actual usage
        lands below estimate. Ledger records ACTUAL (not estimate)."""
        _write_enabled_policy(tmp_path)
        run_id = _create_run_with_cost_budget(tmp_path, cost_limit_usd=100.0)

        monkeypatch.setattr(
            "ao_kernel.llm.check_capabilities",
            lambda **_: (True, "anthropic", []),
        )
        # Huge max_tokens → large estimate, but actual usage is tiny.
        monkeypatch.setattr(
            "ao_kernel.llm.execute_request",
            lambda **_: _ok_transport_result(input_tokens=10, output_tokens=5),
        )

        kwargs = dict(_base_call_kwargs(), max_tokens=2000)
        kwargs["messages"] = [{"role": "user", "content": "hello " * 500}]

        governed_call(
            **kwargs,
            workspace_root=tmp_path,
            run_id=run_id,
            step_id="step-A",
            attempt=1,
        )

        record, _ = load_run(tmp_path, run_id)
        spent = Decimal(str(record["budget"]["cost_usd"]["spent"]))
        # actual = 10 * 0.003/1k + 5 * 0.015/1k = 0.00003 + 0.000075 = 0.000105
        expected_actual = Decimal("0.000105")
        assert spent == expected_actual, (
            f"spent={spent} should reconcile to ACTUAL cost, not estimate"
        )

        lines = _read_ledger_lines(tmp_path)
        assert len(lines) == 1
        # Cost in ledger tracks actual (float rounding tolerated)
        assert abs(lines[0]["cost_usd"] - float(expected_actual)) < 1e-9


# ─── Usage-missing ───────────────────────────────────────────────────


class TestUsageMissing:
    def test_fail_closed_raises_llm_usage_missing_error(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Cost-active + usage missing + fail_closed=true → raise.
        Audit-only ledger entry is still recorded BEFORE the raise."""
        _write_enabled_policy(tmp_path, fail_closed_on_missing_usage=True)
        run_id = _create_run_with_cost_budget(tmp_path)

        monkeypatch.setattr(
            "ao_kernel.llm.check_capabilities",
            lambda **_: (True, "anthropic", []),
        )
        monkeypatch.setattr(
            "ao_kernel.llm.execute_request",
            lambda **_: _missing_usage_transport_result(),
        )

        with pytest.raises(LLMUsageMissingError) as excinfo:
            governed_call(
                **_base_call_kwargs(),
                workspace_root=tmp_path,
                run_id=run_id,
                step_id="step-A",
                attempt=1,
            )

        assert "tokens_input" in excinfo.value.missing_fields
        assert "tokens_output" in excinfo.value.missing_fields

        lines = _read_ledger_lines(tmp_path)
        assert len(lines) == 1
        assert lines[0]["usage_missing"] is True
        assert lines[0]["cost_usd"] == 0.0

        kinds = _read_evidence_kinds(tmp_path, run_id)
        assert "llm_usage_missing" in kinds
        assert "llm_cost_estimated" in kinds
        assert "llm_spend_recorded" not in kinds

    def test_fail_open_warns_and_returns_ok(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _write_enabled_policy(tmp_path, fail_closed_on_missing_usage=False)
        run_id = _create_run_with_cost_budget(tmp_path)

        monkeypatch.setattr(
            "ao_kernel.llm.check_capabilities",
            lambda **_: (True, "anthropic", []),
        )
        monkeypatch.setattr(
            "ao_kernel.llm.execute_request",
            lambda **_: _missing_usage_transport_result(),
        )

        # Does NOT raise — warn-log path.
        result = governed_call(
            **_base_call_kwargs(),
            workspace_root=tmp_path,
            run_id=run_id,
            step_id="step-A",
            attempt=1,
        )

        assert result["status"] == "OK"
        lines = _read_ledger_lines(tmp_path)
        assert len(lines) == 1
        assert lines[0]["usage_missing"] is True


# ─── Bypass path ─────────────────────────────────────────────────────


class TestBypassPath:
    def test_no_identity_kwargs_bypasses_cost_runtime(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """All cost-identity kwargs None → transparent pre-B2 flow:
        no ledger write, no evidence emit, no policy load. Success
        return is still the rich dict shape."""
        monkeypatch.setattr(
            "ao_kernel.llm.check_capabilities",
            lambda **_: (True, "anthropic", []),
        )
        monkeypatch.setattr(
            "ao_kernel.llm.execute_request",
            lambda **_: _ok_transport_result(),
        )

        result = governed_call(**_base_call_kwargs())

        assert result["status"] == "OK"
        assert "normalized" in result
        assert _read_ledger_lines(tmp_path) == []

    def test_dormant_policy_bypasses_cost_runtime(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """All identity kwargs present but bundled policy is dormant →
        bypass. No override written → bundled default (enabled=false)
        is loaded."""
        run_id = _create_run_with_cost_budget(tmp_path)

        monkeypatch.setattr(
            "ao_kernel.llm.check_capabilities",
            lambda **_: (True, "anthropic", []),
        )
        monkeypatch.setattr(
            "ao_kernel.llm.execute_request",
            lambda **_: _ok_transport_result(),
        )

        result = governed_call(
            **_base_call_kwargs(),
            workspace_root=tmp_path,
            run_id=run_id,
            step_id="step-A",
            attempt=1,
        )

        assert result["status"] == "OK"
        # Dormant policy → no ledger, no evidence, budget untouched.
        assert _read_ledger_lines(tmp_path) == []
        assert _read_evidence_kinds(tmp_path, run_id) == []
        record, _ = load_run(tmp_path, run_id)
        assert record["budget"]["cost_usd"]["spent"] == 0.0
