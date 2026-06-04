"""V5 Epic 2 E-2-4 dry-run harness invariants."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

import pytest
from jsonschema import Draft202012Validator

from ao_kernel._internal.live_adapter_dryrun import (
    _compute_envelope_digest,
    build_dry_run_envelope,
    build_per_call_audit_row,
    main,
    run_live_adapter_dryrun,
)
from ao_kernel.config import load_default

_REPO_ROOT = Path(__file__).resolve().parents[1]


def _validates(payload: dict[str, Any], schema_name: str) -> bool:
    return not list(Draft202012Validator(load_default("schemas", schema_name)).iter_errors(payload))


def test_build_dry_run_envelope_is_strict_schema_valid_and_digest_bound() -> None:
    envelope = build_dry_run_envelope(provider_id="openai", model="gpt-4o-mini", intent="FAST_TEXT")

    assert _validates(envelope, "live_adapter_envelope.schema.v1.json")
    assert envelope["mode"] == "dry_run"
    assert envelope["response"]["status"] == "dry_run_emitted"
    assert envelope["live_adapter_execution"] is False
    assert envelope["support_widening"] is False
    assert envelope["production_platform_claim"] is False
    assert envelope["cost"]["actual_cost_usd"] == "0.00000000"
    assert envelope["envelope_digest"] == _compute_envelope_digest(envelope)


def test_build_per_call_audit_row_binds_to_envelope_digest() -> None:
    envelope = build_dry_run_envelope(provider_id="openai", model="gpt-4o-mini", intent="FAST_TEXT")
    audit = build_per_call_audit_row(envelope, cost_breach_state="not_applicable")

    assert _validates(audit, "per_call_audit.schema.v1.json")
    assert audit["envelope_digest"] == envelope["envelope_digest"]
    assert audit["status"] == "dry_run_emitted"
    assert audit["cost_breach_state"] == "not_applicable"
    assert audit["live_adapter_execution"] is False


def test_run_live_adapter_dryrun_writes_envelope_and_workspace_audit(tmp_path: Path) -> None:
    output = tmp_path / "evidence" / "dryrun.envelope.v1.json"
    result = run_live_adapter_dryrun(
        provider_id="openai",
        model="gpt-4o-mini",
        intent="FAST_TEXT",
        output=output,
        prompt="hello",
    )

    envelope = json.loads(output.read_text(encoding="utf-8"))
    audit_rows = [json.loads(line) for line in (tmp_path / "evidence" / "per_call_audit.jsonl").read_text().splitlines()]
    assert result.workspace_root == tmp_path
    assert _validates(envelope, "live_adapter_envelope.schema.v1.json")
    assert len(audit_rows) == 1
    assert audit_rows[0]["envelope_digest"] == envelope["envelope_digest"]
    assert audit_rows[0]["cost_breach_state"] == "not_applicable"
    assert output.stat().st_mode & 0o777 == 0o600
    assert not list(output.parent.glob(".dryrun.envelope.v1.json.*.tmp"))


def test_run_live_adapter_dryrun_library_mode_when_output_not_under_evidence(tmp_path: Path) -> None:
    output = tmp_path / "dryrun.envelope.v1.json"
    result = run_live_adapter_dryrun(
        provider_id="anthropic",
        model="claude-3-5-sonnet",
        intent="FAST_TEXT",
        output=output,
    )

    assert output.is_file()
    assert result.workspace_root is None
    assert result.audit_receipt == {"persisted": False, "mode": "library", "paths": []}
    assert not (tmp_path / "evidence").exists()


def test_cli_returns_zero_and_prints_no_secret_or_live_claim(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    output = tmp_path / "evidence" / "dryrun.envelope.v1.json"

    rc = main(
        [
            "--provider",
            "openai",
            "--model",
            "gpt-4o-mini",
            "--intent",
            "FAST_TEXT",
            "--prompt",
            "not serialized",
            "--output",
            str(output),
        ]
    )

    captured = capsys.readouterr()
    assert rc == 0
    assert "not serialized" not in captured.out
    assert "live_adapter_execution" in captured.out
    assert json.loads(output.read_text(encoding="utf-8"))["live_adapter_execution"] is False


def test_cli_returns_two_on_cost_ceiling_hard_breach(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    policies = tmp_path / "policies"
    policies.mkdir()
    (policies / "policy_cost_ceiling.v1.json").write_text(
        json.dumps({"version": "v1", "currency": "USD", "soft_usd": "0.00000001", "hard_usd": "0.00000002"}),
        encoding="utf-8",
    )
    output = tmp_path / "evidence" / "dryrun.envelope.v1.json"

    rc = main(
        [
            "--provider",
            "openai",
            "--model",
            "gpt-4o-mini",
            "--intent",
            "FAST_TEXT",
            "--output",
            str(output),
            "--workspace-root",
            str(tmp_path),
            "--dry-run-cost-usd",
            "0.00000003",
        ]
    )

    captured = capsys.readouterr()
    assert rc == 2
    assert "cost ceiling breached" in captured.err
    assert not output.exists()
    assert (tmp_path / "evidence" / "cost_hard_breach.jsonl").is_file()


def test_script_cli_subprocess_smoke(tmp_path: Path) -> None:
    output = tmp_path / "evidence" / "dryrun.envelope.v1.json"
    proc = subprocess.run(
        [
            "python3",
            "scripts/run_live_adapter_dryrun.py",
            "--provider",
            "openai",
            "--model",
            "gpt-4o-mini",
            "--intent",
            "FAST_TEXT",
            "--output",
            str(output),
        ],
        cwd=_REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert proc.returncode == 0, proc.stderr
    assert output.is_file()
    assert json.loads(output.read_text(encoding="utf-8"))["response"]["status"] == "dry_run_emitted"
