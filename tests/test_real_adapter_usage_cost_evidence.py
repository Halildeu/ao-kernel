"""Drift guards for the GPP-3a real-adapter usage/cost evidence schema."""

from __future__ import annotations

import importlib.util
import json
import sys
import uuid
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
from jsonschema import Draft202012Validator, FormatChecker


_REPO_ROOT = Path(__file__).resolve().parents[1]
_SCHEMA_PATH = _REPO_ROOT / "ao_kernel" / "defaults" / "schemas" / "real-adapter-usage-cost-evidence.schema.v1.json"
_SCRIPT_PATH = _REPO_ROOT / "scripts" / "real_adapter_usage_evidence.py"


def _load_module() -> Any:
    spec = importlib.util.spec_from_file_location("real_adapter_usage_evidence", _SCRIPT_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["real_adapter_usage_evidence"] = module
    spec.loader.exec_module(module)
    return module


def _schema() -> dict[str, Any]:
    return json.loads(_SCHEMA_PATH.read_text(encoding="utf-8"))


def _validator() -> Draft202012Validator:
    return Draft202012Validator(_schema(), format_checker=FormatChecker())


def _complete_artifact(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "schema_version": "real-adapter-usage-cost-evidence.v1",
        "evidence_class": "simulated",
        "adapter_id": "anthropic-claude-3-5-sonnet",
        "model_id": "claude-3-5-sonnet-20241022",
        "run_id": "11111111-1111-4111-8111-111111111111",
        "step_id": "step-1",
        "elapsed_seconds": 1.23,
        "prompt_tokens": 100,
        "completion_tokens": 50,
        "total_cost_usd": "0.00123400",
        "currency": "USD",
        "pricing_source": {
            "source_type": "simulated_fixture",
            "source_ref": "fixture/anthropic-2026-05",
            "source_digest": None,
            "retrieved_at": None,
        },
        "unavailable_reason": None,
        "observed_at": "2026-05-25T00:00:00Z",
        "live_adapter_execution": False,
        "support_widening": False,
        "production_platform_claim": False,
        "linked_spend_ledger_events": None,
    }
    base.update(overrides)
    return base


def _unavailable_artifact(reason: str, **overrides: Any) -> dict[str, Any]:
    return _complete_artifact(
        unavailable_reason=reason,
        prompt_tokens=None,
        completion_tokens=None,
        total_cost_usd=None,
        **overrides,
    )


# ---------------------------------------------------------------------------
# Schema self-validation
# ---------------------------------------------------------------------------


def test_schema_is_a_valid_draft_2020_12_schema() -> None:
    Draft202012Validator.check_schema(_schema())


# ---------------------------------------------------------------------------
# Complete (happy) branch
# ---------------------------------------------------------------------------


def test_complete_simulated_artifact_validates() -> None:
    errors = list(_validator().iter_errors(_complete_artifact()))
    assert errors == []


def test_complete_artifact_rejects_when_prompt_tokens_null() -> None:
    artifact = _complete_artifact(prompt_tokens=None)
    errors = list(_validator().iter_errors(artifact))
    assert errors, "complete-branch artifact with null prompt_tokens must fail"


def test_complete_artifact_rejects_when_total_cost_usd_null() -> None:
    artifact = _complete_artifact(total_cost_usd=None)
    errors = list(_validator().iter_errors(artifact))
    assert errors, "complete-branch artifact with null total_cost_usd must fail"


# ---------------------------------------------------------------------------
# Unavailable branch (all three reasons)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "reason",
    ["usage_missing", "token_unavailable", "cost_unavailable"],
)
def test_unavailable_artifact_validates_for_each_reason(reason: str) -> None:
    errors = list(_validator().iter_errors(_unavailable_artifact(reason)))
    assert errors == []


def test_unavailable_artifact_rejects_when_tokens_present() -> None:
    # Non-null reason but tokens still set: must fail the oneOf.
    artifact = _complete_artifact(
        unavailable_reason="usage_missing",
        prompt_tokens=100,
        completion_tokens=50,
        total_cost_usd="0.00100000",
    )
    errors = list(_validator().iter_errors(artifact))
    assert errors, "unavailable-branch artifact with non-null usage/cost must fail"


# ---------------------------------------------------------------------------
# Guard / authority enforcement
# ---------------------------------------------------------------------------


def test_artifact_rejects_support_widening_true() -> None:
    artifact = _complete_artifact(support_widening=True)
    errors = list(_validator().iter_errors(artifact))
    assert errors, "support_widening=true must fail (const false guard)"


def test_artifact_rejects_production_platform_claim_true() -> None:
    artifact = _complete_artifact(production_platform_claim=True)
    errors = list(_validator().iter_errors(artifact))
    assert errors, "production_platform_claim=true must fail (const false guard)"


def test_simulated_evidence_class_rejects_live_adapter_execution_true() -> None:
    artifact = _complete_artifact(evidence_class="simulated", live_adapter_execution=True)
    errors = list(_validator().iter_errors(artifact))
    assert errors, "simulated + live_adapter_execution=true must fail (allOf bind)"


def test_live_evidence_class_rejects_live_adapter_execution_false() -> None:
    artifact = _complete_artifact(
        evidence_class="live",
        live_adapter_execution=False,
    )
    errors = list(_validator().iter_errors(artifact))
    assert errors, "live + live_adapter_execution=false must fail (allOf bind)"


# ---------------------------------------------------------------------------
# Format / contract details
# ---------------------------------------------------------------------------


def test_total_cost_usd_rejects_non_decimal_string() -> None:
    artifact = _complete_artifact(total_cost_usd="not-a-number")
    errors = list(_validator().iter_errors(artifact))
    assert errors


def test_run_id_must_be_uuid() -> None:
    artifact = _complete_artifact(run_id="not-a-uuid")
    errors = list(_validator().iter_errors(artifact))
    assert errors


def test_linked_spend_ledger_event_billing_digest_must_be_sha256() -> None:
    artifact = _complete_artifact(
        linked_spend_ledger_events=[
            {
                "run_id": "22222222-2222-4222-8222-222222222222",
                "step_id": "linked-step",
                "attempt": 1,
                "billing_digest": "not-a-digest",
            }
        ]
    )
    errors = list(_validator().iter_errors(artifact))
    assert errors


def test_pricing_source_requires_source_type_and_ref() -> None:
    artifact = _complete_artifact(pricing_source={"source_type": "simulated_fixture"})
    errors = list(_validator().iter_errors(artifact))
    assert errors, "pricing_source without source_ref must fail"


def test_unknown_unavailable_reason_rejected() -> None:
    artifact = _complete_artifact(
        unavailable_reason="catalog_missing",
        prompt_tokens=None,
        completion_tokens=None,
        total_cost_usd=None,
    )
    errors = list(_validator().iter_errors(artifact))
    assert errors


# ---------------------------------------------------------------------------
# Script: emit-simulated
# ---------------------------------------------------------------------------


def test_emit_simulated_complete_artifact_round_trips() -> None:
    mod = _load_module()
    artifact = mod.emit_simulated(
        adapter_id="anthropic-claude-3-5-sonnet",
        model_id="claude-3-5-sonnet-20241022",
        run_id="33333333-3333-4333-8333-333333333333",
        step_id="step-emit-1",
        elapsed_seconds=0.42,
        prompt_tokens=200,
        completion_tokens=80,
        total_cost_usd=Decimal("0.005"),
        pricing_source_type="simulated_fixture",
        pricing_source_ref="fixture/anthropic-2026-05",
        unavailable_reason=None,
    )
    assert artifact["evidence_class"] == "simulated"
    assert artifact["live_adapter_execution"] is False
    assert artifact["support_widening"] is False
    assert artifact["production_platform_claim"] is False
    assert artifact["unavailable_reason"] is None
    assert artifact["prompt_tokens"] == 200
    assert artifact["completion_tokens"] == 80
    assert artifact["total_cost_usd"] == "0.005"
    assert artifact["linked_spend_ledger_events"] is None


@pytest.mark.parametrize(
    "reason",
    ["usage_missing", "token_unavailable", "cost_unavailable"],
)
def test_emit_simulated_unavailable_path_round_trips(reason: str) -> None:
    mod = _load_module()
    artifact = mod.emit_simulated(
        adapter_id="anthropic-claude-3-5-sonnet",
        model_id="claude-3-5-sonnet-20241022",
        run_id=str(uuid.uuid4()),
        step_id=f"step-{reason}",
        elapsed_seconds=0.1,
        prompt_tokens=None,
        completion_tokens=None,
        total_cost_usd=None,
        pricing_source_type="simulated_fixture",
        pricing_source_ref="fixture/none",
        unavailable_reason=reason,
    )
    assert artifact["unavailable_reason"] == reason
    assert artifact["prompt_tokens"] is None
    assert artifact["completion_tokens"] is None
    assert artifact["total_cost_usd"] is None


def test_emit_simulated_rejects_inconsistent_unavailable_input() -> None:
    mod = _load_module()
    with pytest.raises(mod.EvidenceError):
        mod.emit_simulated(
            adapter_id="claude",
            model_id="claude-3-5-sonnet",
            run_id=str(uuid.uuid4()),
            step_id="bad",
            elapsed_seconds=0.1,
            prompt_tokens=10,
            completion_tokens=5,
            total_cost_usd=Decimal("0.001"),
            pricing_source_type="simulated_fixture",
            pricing_source_ref="x",
            unavailable_reason="usage_missing",
        )


def test_emit_simulated_rejects_missing_usage_in_complete_branch() -> None:
    mod = _load_module()
    with pytest.raises(mod.EvidenceError):
        mod.emit_simulated(
            adapter_id="claude",
            model_id="claude-3-5-sonnet",
            run_id=str(uuid.uuid4()),
            step_id="bad",
            elapsed_seconds=0.1,
            prompt_tokens=None,
            completion_tokens=None,
            total_cost_usd=None,
            pricing_source_type="simulated_fixture",
            pricing_source_ref="x",
            unavailable_reason=None,
        )


# ---------------------------------------------------------------------------
# Script: from-ledger-event
# ---------------------------------------------------------------------------


def test_from_ledger_event_complete_event_maps_to_complete_evidence() -> None:
    mod = _load_module()
    event = {
        "run_id": "44444444-4444-4444-8444-444444444444",
        "step_id": "spend-step-1",
        "provider_id": "anthropic",
        "model": "claude-3-5-sonnet",
        "tokens_input": 1000,
        "tokens_output": 250,
        "cost_usd": 0.0125,
        "ts": "2026-05-25T00:00:00Z",
        "attempt": 1,
        "billing_digest": "sha256:" + "a" * 64,
    }
    artifact = mod.from_ledger_event(event, adapter_id="anthropic-claude-3-5-sonnet")
    assert artifact["unavailable_reason"] is None
    assert artifact["prompt_tokens"] == 1000
    assert artifact["completion_tokens"] == 250
    assert artifact["total_cost_usd"] == "0.0125"
    assert artifact["linked_spend_ledger_events"] is not None
    assert len(artifact["linked_spend_ledger_events"]) == 1
    linked = artifact["linked_spend_ledger_events"][0]
    assert linked["billing_digest"] == "sha256:" + "a" * 64
    assert linked["attempt"] == 1


def test_from_ledger_event_usage_missing_maps_to_unavailable_evidence() -> None:
    mod = _load_module()
    event = {
        "run_id": "55555555-5555-4555-8555-555555555555",
        "step_id": "spend-step-2",
        "provider_id": "anthropic",
        "model": "claude-3-5-sonnet",
        "tokens_input": 0,
        "tokens_output": 0,
        "cost_usd": 0.0,
        "ts": "2026-05-25T00:00:00Z",
        "attempt": 1,
        "usage_missing": True,
        "billing_digest": "sha256:" + "b" * 64,
    }
    artifact = mod.from_ledger_event(event, adapter_id="anthropic-claude-3-5-sonnet")
    assert artifact["unavailable_reason"] == "usage_missing"
    assert artifact["prompt_tokens"] is None
    assert artifact["completion_tokens"] is None
    assert artifact["total_cost_usd"] is None
    assert artifact["linked_spend_ledger_events"] is not None
    assert artifact["linked_spend_ledger_events"][0]["billing_digest"].startswith("sha256:")


# ---------------------------------------------------------------------------
# Script: validate
# ---------------------------------------------------------------------------


def test_validate_accepts_complete_artifact() -> None:
    mod = _load_module()
    mod.validate_evidence(_complete_artifact())


def test_validate_rejects_inconsistent_artifact_with_evidence_error() -> None:
    mod = _load_module()
    artifact = _complete_artifact(
        unavailable_reason="usage_missing",
        prompt_tokens=100,
        completion_tokens=50,
        total_cost_usd="0.001",
    )
    with pytest.raises(mod.EvidenceError):
        mod.validate_evidence(artifact)


# ---------------------------------------------------------------------------
# CLI smoke
# ---------------------------------------------------------------------------


def test_cli_emit_simulated_writes_schema_valid_artifact(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    mod = _load_module()
    output = tmp_path / "evidence.json"
    rc = mod.main(
        [
            "emit-simulated",
            "--adapter-id",
            "anthropic-claude-3-5-sonnet",
            "--model-id",
            "claude-3-5-sonnet-20241022",
            "--step-id",
            "cli-step-1",
            "--elapsed-seconds",
            "0.5",
            "--prompt-tokens",
            "10",
            "--completion-tokens",
            "5",
            "--total-cost-usd",
            "0.00005",
            "--pricing-source-type",
            "simulated_fixture",
            "--pricing-source-ref",
            "fixture/test",
            "--output",
            str(output),
        ]
    )
    assert rc == 0
    payload = json.loads(output.read_text(encoding="utf-8"))
    _validator().validate(payload)


def test_cli_validate_returns_zero_for_valid_artifact(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    mod = _load_module()
    artifact = _complete_artifact()
    path = tmp_path / "evidence.json"
    path.write_text(json.dumps(artifact), encoding="utf-8")
    rc = mod.main(["validate", "--artifact-path", str(path)])
    assert rc == 0


def test_cli_validate_returns_two_for_invalid_artifact(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    mod = _load_module()
    artifact = _complete_artifact(support_widening=True)
    path = tmp_path / "evidence.json"
    path.write_text(json.dumps(artifact), encoding="utf-8")
    rc = mod.main(["validate", "--artifact-path", str(path)])
    assert rc == 2
