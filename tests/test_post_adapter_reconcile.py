"""PR-C3: post_adapter_reconcile contract tests.

Covers the six primary contract pins:
- Dormant policy no-op
- Success path: ledger append + budget drain + llm_spend_recorded
  emit with ``source="adapter_path"``
- Usage-missing: ledger audit entry + ``llm_usage_missing`` emit
  (NOT ``llm_spend_recorded``)
- Idempotent same-digest silent no-op (second call)
- Different-digest raises ``SpendLedgerDuplicateError``
- Wire format: ``cost_actual.tokens_input/tokens_output``,
  ``cost_actual.cost_usd`` (NOT ``usage.*``); ``cached_tokens``
  intentionally NOT consumed (per contract note).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from ao_kernel.cost.errors import SpendLedgerDuplicateError
from ao_kernel.cost.middleware import post_adapter_reconcile
from ao_kernel.cost.policy import CostTrackingPolicy


def _policy(
    *, enabled: bool = True, fail_on_missing: bool = False,
) -> CostTrackingPolicy:
    """Tight policy sufficient for the adapter reconcile path."""
    return CostTrackingPolicy(
        enabled=enabled,
        price_catalog_path=".ao/cost/price-catalog.json",
        spend_ledger_path=".ao/cost/spend.jsonl",
        fail_closed_on_exhaust=True,
        fail_closed_on_missing_usage=fail_on_missing,
        strict_freshness=False,
        idempotency_window_lines=100,
    )


def _seed_run(
    root: Path,
    run_id: str,
    *,
    cost_limit: float = 10.0,
    cost_remaining: float = 10.0,
) -> None:
    """Minimal run record with a cost_usd budget axis seeded."""
    from ao_kernel.workflow.run_store import run_revision

    run_dir = root / ".ao" / "runs" / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
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
        "budget": {
            "fail_closed_on_exhaust": True,
            "cost_usd": {
                "limit": cost_limit,
                "remaining": cost_remaining,
            },
        },
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


def _read_events(root: Path, run_id: str) -> list[dict[str, Any]]:
    path = (
        root / ".ao" / "evidence" / "workflows" / run_id / "events.jsonl"
    )
    if not path.is_file():
        return []
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _read_run_budget(root: Path, run_id: str) -> dict[str, Any]:
    from ao_kernel.workflow.run_store import load_run

    record, _ = load_run(root, run_id)
    return record.get("budget") or {}


class TestDormantAndNoOp:
    def test_dormant_policy_is_no_op(self, tmp_path: Path) -> None:
        run_id = "00000000-0000-4000-8000-000000aaa001"
        _seed_run(tmp_path, run_id)
        post_adapter_reconcile(
            workspace_root=tmp_path,
            run_id=run_id,
            step_id="s1",
            attempt=1,
            provider_id="codex",
            model="stub",
            cost_actual={"tokens_input": 10, "tokens_output": 5, "cost_usd": 0.01},
            policy=_policy(enabled=False),
        )
        assert _read_ledger(tmp_path) == []
        assert _read_events(tmp_path, run_id) == []

    def test_cost_actual_none_is_no_op(self, tmp_path: Path) -> None:
        run_id = "00000000-0000-4000-8000-000000aaa002"
        _seed_run(tmp_path, run_id)
        post_adapter_reconcile(
            workspace_root=tmp_path,
            run_id=run_id,
            step_id="s1",
            attempt=1,
            provider_id="codex",
            model="stub",
            cost_actual=None,
            policy=_policy(),
        )
        assert _read_ledger(tmp_path) == []


class TestHappyPath:
    def test_happy_path_drains_budget_and_emits(
        self, tmp_path: Path,
    ) -> None:
        run_id = "00000000-0000-4000-8000-000000aaa003"
        _seed_run(tmp_path, run_id, cost_limit=10.0, cost_remaining=10.0)

        post_adapter_reconcile(
            workspace_root=tmp_path,
            run_id=run_id,
            step_id="s1",
            attempt=1,
            provider_id="codex",
            model="stub",
            cost_actual={
                "tokens_input": 100,
                "tokens_output": 50,
                "cost_usd": 0.05,
            },
            policy=_policy(),
        )

        # Ledger append: 1 entry.
        ledger = _read_ledger(tmp_path)
        assert len(ledger) == 1
        assert ledger[0]["run_id"] == run_id
        assert ledger[0]["step_id"] == "s1"
        assert ledger[0]["tokens_input"] == 100
        assert ledger[0]["tokens_output"] == 50

        # Budget drain: cost_usd.remaining = 10.0 - 0.05 = 9.95.
        budget = _read_run_budget(tmp_path, run_id)
        assert budget["cost_usd"]["remaining"] == pytest.approx(9.95)

        # Emit: llm_spend_recorded with source=adapter_path.
        events = _read_events(tmp_path, run_id)
        spend_events = [e for e in events if e.get("kind") == "llm_spend_recorded"]
        assert len(spend_events) == 1
        payload = spend_events[0]["payload"]
        assert payload["source"] == "adapter_path"
        assert payload["run_id"] == run_id
        assert payload["step_id"] == "s1"
        assert payload["attempt"] == 1
        assert payload["provider_id"] == "codex"
        assert payload["model"] == "stub"
        assert payload["tokens_input"] == 100
        assert payload["tokens_output"] == 50
        assert payload["cost_usd"] == pytest.approx(0.05)


class TestUsageMissing:
    def test_usage_missing_emits_llm_usage_missing(
        self, tmp_path: Path,
    ) -> None:
        run_id = "00000000-0000-4000-8000-000000aaa004"
        _seed_run(tmp_path, run_id)

        post_adapter_reconcile(
            workspace_root=tmp_path,
            run_id=run_id,
            step_id="s1",
            attempt=1,
            provider_id="codex",
            model="stub",
            cost_actual={"cost_usd": 0.0},  # no tokens_input / tokens_output
            policy=_policy(),
        )

        # Ledger: audit-only entry (usage_missing=true, cost_usd=0).
        ledger = _read_ledger(tmp_path)
        assert len(ledger) == 1
        assert ledger[0].get("usage_missing") is True

        # Emit: llm_usage_missing (NOT llm_spend_recorded).
        events = _read_events(tmp_path, run_id)
        usage_missing_events = [
            e for e in events if e.get("kind") == "llm_usage_missing"
        ]
        spend_events = [
            e for e in events if e.get("kind") == "llm_spend_recorded"
        ]
        assert len(usage_missing_events) == 1
        assert len(spend_events) == 0
        payload = usage_missing_events[0]["payload"]
        assert payload["source"] == "adapter_path"
        assert payload["run_id"] == run_id
        assert payload["step_id"] == "s1"
        assert payload["attempt"] == 1
        assert payload["provider_id"] == "codex"
        assert payload["model"] == "stub"
        assert set(payload["missing_fields"]) == {
            "tokens_input", "tokens_output",
        }

        # Budget NOT drained (audit-only path).
        budget = _read_run_budget(tmp_path, run_id)
        assert budget["cost_usd"]["remaining"] == pytest.approx(10.0)


class TestSpendEvidenceVendorEnrichment:
    """v3.4.0 #2: vendor_model_id propagates into `llm_spend_recorded`
    evidence payload so audit tooling has full attribution without
    having to cross-reference the ledger."""

    def test_vendor_model_id_on_llm_spend_recorded_emit(
        self, tmp_path: Path,
    ) -> None:
        run_id = "00000000-0000-4000-8000-0000e34a0001"
        _seed_run(tmp_path, run_id)
        post_adapter_reconcile(
            workspace_root=tmp_path, run_id=run_id, step_id="s1",
            attempt=1, provider_id="codex", model="stub",
            cost_actual={
                "tokens_input": 100,
                "tokens_output": 50,
                "cost_usd": 0.05,
                "vendor_model_id": "claude-3-5-sonnet-20241022",
            },
            policy=_policy(),
        )
        events = _read_events(tmp_path, run_id)
        spend_events = [e for e in events if e.get("kind") == "llm_spend_recorded"]
        assert len(spend_events) == 1
        assert spend_events[0]["payload"]["vendor_model_id"] == (
            "claude-3-5-sonnet-20241022"
        )

    def test_vendor_model_id_absent_when_adapter_omits(
        self, tmp_path: Path,
    ) -> None:
        """Adapter that doesn't populate vendor_model_id → evidence
        payload omits the key (not null)."""
        run_id = "00000000-0000-4000-8000-0000e34a0002"
        _seed_run(tmp_path, run_id)
        post_adapter_reconcile(
            workspace_root=tmp_path, run_id=run_id, step_id="s1",
            attempt=1, provider_id="codex", model="stub",
            cost_actual={
                "tokens_input": 100,
                "tokens_output": 50,
                "cost_usd": 0.05,
                # no vendor_model_id
            },
            policy=_policy(),
        )
        events = _read_events(tmp_path, run_id)
        spend_events = [e for e in events if e.get("kind") == "llm_spend_recorded"]
        assert len(spend_events) == 1
        assert "vendor_model_id" not in spend_events[0]["payload"]


class TestIdempotency:
    def test_same_digest_silent_no_op_on_second_call(
        self, tmp_path: Path,
    ) -> None:
        run_id = "00000000-0000-4000-8000-000000aaa005"
        _seed_run(tmp_path, run_id)

        cost_actual = {
            "tokens_input": 100,
            "tokens_output": 50,
            "cost_usd": 0.05,
        }
        # First call: full reconcile.
        post_adapter_reconcile(
            workspace_root=tmp_path, run_id=run_id, step_id="s1",
            attempt=1, provider_id="codex", model="stub",
            cost_actual=cost_actual, policy=_policy(),
        )
        # Second call: same (run_id, step_id, attempt) + same cost →
        # same digest → silent no-op.
        post_adapter_reconcile(
            workspace_root=tmp_path, run_id=run_id, step_id="s1",
            attempt=1, provider_id="codex", model="stub",
            cost_actual=cost_actual, policy=_policy(),
        )
        # Ledger still has exactly ONE entry.
        assert len(_read_ledger(tmp_path)) == 1
        # PR-C3.2: budget drained ONCE (the pre-fix v3.3.0 bug would
        # have drained twice — 0.05 → 9.90 remaining).
        budget = _read_run_budget(tmp_path, run_id)
        assert budget["cost_usd"]["remaining"] == pytest.approx(9.95)

    def test_different_digest_raises_duplicate(
        self, tmp_path: Path,
    ) -> None:
        run_id = "00000000-0000-4000-8000-000000aaa006"
        _seed_run(tmp_path, run_id)

        # First call with one cost value.
        post_adapter_reconcile(
            workspace_root=tmp_path, run_id=run_id, step_id="s1",
            attempt=1, provider_id="codex", model="stub",
            cost_actual={
                "tokens_input": 100, "tokens_output": 50, "cost_usd": 0.05,
            },
            policy=_policy(),
        )
        # Same (run_id, step_id, attempt) but different cost → different
        # digest → SpendLedgerDuplicateError.
        with pytest.raises(SpendLedgerDuplicateError):
            post_adapter_reconcile(
                workspace_root=tmp_path, run_id=run_id, step_id="s1",
                attempt=1, provider_id="codex", model="stub",
                cost_actual={
                    "tokens_input": 200, "tokens_output": 100, "cost_usd": 0.10,
                },
                policy=_policy(),
            )


class TestVendorModelIdAttribution:
    """PR-C3.1 adapter-path catalog attribution.

    Adapter-supplied ``cost_actual.vendor_model_id`` propagates to
    the spend ledger. Blank strings normalize to ``None``. Schema
    accepts the field optionally with ``minLength: 1``.
    """

    def test_vendor_model_id_propagates_to_ledger(
        self, tmp_path: Path,
    ) -> None:
        run_id = "00000000-0000-4000-8000-0000c31a0001"
        _seed_run(tmp_path, run_id)
        post_adapter_reconcile(
            workspace_root=tmp_path, run_id=run_id, step_id="s1",
            attempt=1, provider_id="codex", model="stub",
            cost_actual={
                "tokens_input": 100,
                "tokens_output": 50,
                "cost_usd": 0.05,
                "vendor_model_id": "claude-3-5-sonnet-20241022",
            },
            policy=_policy(),
        )
        ledger = _read_ledger(tmp_path)
        assert len(ledger) == 1
        assert ledger[0]["vendor_model_id"] == "claude-3-5-sonnet-20241022"

    def test_vendor_model_id_absent_defaults_to_none(
        self, tmp_path: Path,
    ) -> None:
        run_id = "00000000-0000-4000-8000-0000c31a0002"
        _seed_run(tmp_path, run_id)
        post_adapter_reconcile(
            workspace_root=tmp_path, run_id=run_id, step_id="s1",
            attempt=1, provider_id="codex", model="stub",
            cost_actual={
                "tokens_input": 100,
                "tokens_output": 50,
                "cost_usd": 0.05,
                # no vendor_model_id key
            },
            policy=_policy(),
        )
        ledger = _read_ledger(tmp_path)
        # omitted from ledger when None (per _event_to_dict)
        assert "vendor_model_id" not in ledger[0]

    def test_vendor_model_id_blank_string_normalized_to_none(
        self, tmp_path: Path,
    ) -> None:
        """Defensive middleware normalization — adapter bug emits empty
        string, ledger stores None (not empty)."""
        run_id = "00000000-0000-4000-8000-0000c31a0003"
        _seed_run(tmp_path, run_id)
        post_adapter_reconcile(
            workspace_root=tmp_path, run_id=run_id, step_id="s1",
            attempt=1, provider_id="codex", model="stub",
            cost_actual={
                "tokens_input": 100,
                "tokens_output": 50,
                "cost_usd": 0.05,
                "vendor_model_id": "   ",  # whitespace only → normalized
            },
            policy=_policy(),
        )
        ledger = _read_ledger(tmp_path)
        assert "vendor_model_id" not in ledger[0]

    def test_usage_missing_preserves_vendor_model_id(
        self, tmp_path: Path,
    ) -> None:
        """Adapter reports vendor but no tokens → usage_missing path
        still carries the attribution for audit."""
        run_id = "00000000-0000-4000-8000-0000c31a0004"
        _seed_run(tmp_path, run_id)
        post_adapter_reconcile(
            workspace_root=tmp_path, run_id=run_id, step_id="s1",
            attempt=1, provider_id="codex", model="stub",
            cost_actual={
                "cost_usd": 0.0,
                "vendor_model_id": "claude-3-5-sonnet-20241022",
            },
            policy=_policy(),
        )
        ledger = _read_ledger(tmp_path)
        assert ledger[0]["vendor_model_id"] == "claude-3-5-sonnet-20241022"
        assert ledger[0]["usage_missing"] is True

    def test_different_vendor_same_tokens_raises_duplicate(
        self, tmp_path: Path,
    ) -> None:
        """Digest includes vendor_model_id → same tokens/cost but
        different vendor raise SpendLedgerDuplicateError on re-reconcile."""
        run_id = "00000000-0000-4000-8000-0000c31a0005"
        _seed_run(tmp_path, run_id)
        post_adapter_reconcile(
            workspace_root=tmp_path, run_id=run_id, step_id="s1",
            attempt=1, provider_id="codex", model="stub",
            cost_actual={
                "tokens_input": 100, "tokens_output": 50, "cost_usd": 0.05,
                "vendor_model_id": "v1",
            },
            policy=_policy(),
        )
        with pytest.raises(SpendLedgerDuplicateError):
            post_adapter_reconcile(
                workspace_root=tmp_path, run_id=run_id, step_id="s1",
                attempt=1, provider_id="codex", model="stub",
                cost_actual={
                    "tokens_input": 100, "tokens_output": 50, "cost_usd": 0.05,
                    "vendor_model_id": "v2",
                },
                policy=_policy(),
            )


class TestCostRecordSchema:
    def test_cost_record_accepts_vendor_model_id(self) -> None:
        """Schema additive widen: cost_record validates with vendor_model_id."""
        from jsonschema import Draft202012Validator
        from ao_kernel.config import load_default

        schema = load_default(
            "schemas", "agent-adapter-contract.schema.v1.json",
        )
        cost_record_schema = schema["$defs"]["cost_record"]
        validator = Draft202012Validator(cost_record_schema)
        doc = {
            "tokens_input": 100,
            "tokens_output": 50,
            "cost_usd": 0.05,
            "vendor_model_id": "claude-3-5-sonnet-20241022",
        }
        errors = list(validator.iter_errors(doc))
        assert errors == []  # no validation issues

    def test_cost_record_accepts_without_vendor_model_id(self) -> None:
        """Backward-compat: cost_record valid without the new field."""
        from jsonschema import Draft202012Validator
        from ao_kernel.config import load_default

        schema = load_default(
            "schemas", "agent-adapter-contract.schema.v1.json",
        )
        cost_record_schema = schema["$defs"]["cost_record"]
        validator = Draft202012Validator(cost_record_schema)
        doc = {
            "tokens_input": 100,
            "tokens_output": 50,
            "cost_usd": 0.05,
        }
        errors = list(validator.iter_errors(doc))
        assert errors == []

    def test_cost_record_rejects_empty_vendor_model_id(self) -> None:
        """minLength:1 at contract boundary prevents empty strings
        from entering the wire."""
        from jsonschema import Draft202012Validator, ValidationError
        from ao_kernel.config import load_default

        schema = load_default(
            "schemas", "agent-adapter-contract.schema.v1.json",
        )
        cost_record_schema = schema["$defs"]["cost_record"]
        validator = Draft202012Validator(cost_record_schema)
        with pytest.raises(ValidationError):
            validator.validate({
                "tokens_input": 100,
                "tokens_output": 50,
                "cost_usd": 0.05,
                "vendor_model_id": "",  # empty → violates minLength:1
            })


class TestWireFormat:
    def test_cost_actual_wire_format_not_usage(
        self, tmp_path: Path,
    ) -> None:
        """Builder reads ``cost_actual.tokens_input/tokens_output``,
        NOT ``usage.*``. A payload with ``usage.*`` but no
        ``cost_actual.tokens_*`` must be treated as usage-missing."""
        run_id = "00000000-0000-4000-8000-000000aaa007"
        _seed_run(tmp_path, run_id)

        # usage.* fields present but cost_actual lacks tokens → usage-missing.
        post_adapter_reconcile(
            workspace_root=tmp_path, run_id=run_id, step_id="s1",
            attempt=1, provider_id="codex", model="stub",
            cost_actual={"cost_usd": 0.01},  # no tokens_input/output
            policy=_policy(),
        )
        events = _read_events(tmp_path, run_id)
        kinds = [e.get("kind") for e in events]
        assert "llm_usage_missing" in kinds
        assert "llm_spend_recorded" not in kinds
