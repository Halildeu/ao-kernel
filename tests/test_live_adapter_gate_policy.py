from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from ao_kernel.live_adapter_gate_policy import (
    APPROVE_CONTRACT_GATE_DECISION,
    EXPECTED_WORKFLOW_NAME,
    EXPECTED_WORKFLOW_PATH,
    REJECT_DECISION,
    build_live_adapter_gate_policy_decision,
    render_live_adapter_gate_policy_decision_text,
    write_live_adapter_gate_policy_decision,
)


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _approved_payload() -> dict[str, object]:
    return {
        "environment": "ao-kernel-live-adapter-gate",
        "event": "workflow_dispatch",
        "sha": "abc123",
        "ref": "refs/heads/main",
        "deployment_callback_url": (
            "https://api.github.com/repos/Halildeu/ao-kernel/actions/runs/25020015357/"
            "deployment_protection_rule"
        ),
        "repository": {"full_name": "Halildeu/ao-kernel"},
        "pull_requests": [],
        "verified_context": {
            "workflow_name": EXPECTED_WORKFLOW_NAME,
            "workflow_path": EXPECTED_WORKFLOW_PATH,
            "prerequisites_ready": True,
            "attestation_overall_status": "ready",
            "live_execution_allowed": False,
            "support_widening_allowed": False,
            "production_platform_claim_allowed": False,
        },
    }


def _find_check(decision: dict[str, object], name: str) -> dict[str, object]:
    checks = decision["checks"]
    assert isinstance(checks, list)
    for check in checks:
        assert isinstance(check, dict)
        if check["name"] == name:
            return check
    raise AssertionError(f"missing check: {name}")


def test_policy_decision_approves_contract_only_when_verified_context_is_closed() -> None:
    decision = build_live_adapter_gate_policy_decision(
        _approved_payload(),
        generated_at="2026-04-28T00:00:00Z",
    )

    assert decision["schema_version"] == "1"
    assert decision["program_id"] == "GPP-2o"
    assert decision["decision"] == APPROVE_CONTRACT_GATE_DECISION
    assert decision["github_review_state"] == "approved"
    assert decision["approval_allowed"] is True
    assert decision["live_execution_allowed"] is False
    assert decision["support_widening_allowed"] is False
    assert decision["production_platform_claim_allowed"] is False
    assert decision["finding_code"] is None
    assert decision["findings"] == []
    assert decision["context"]["ref"] == "main"
    assert all(check["status"] == "pass" for check in decision["checks"])


def test_policy_decision_rejects_raw_webhook_payload_without_verified_context() -> None:
    payload = _approved_payload()
    payload.pop("verified_context")

    decision = build_live_adapter_gate_policy_decision(payload)

    assert decision["decision"] == REJECT_DECISION
    assert decision["github_review_state"] == "rejected"
    assert decision["approval_allowed"] is False
    assert "live_gate_policy_missing_workflow_identity" in decision["findings"]
    assert "live_gate_policy_prerequisites_not_ready" in decision["findings"]
    assert "live_gate_policy_live_execution_open" in decision["findings"]
    assert "live_gate_policy_support_boundary_open" in decision["findings"]


def test_policy_decision_rejects_wrong_repository() -> None:
    payload = _approved_payload()
    payload["repository"] = {"full_name": "Other/repo"}

    decision = build_live_adapter_gate_policy_decision(payload)

    assert decision["decision"] == REJECT_DECISION
    assert _find_check(decision, "repository")["finding_code"] == "live_gate_policy_wrong_repository"


def test_policy_decision_rejects_wrong_ref() -> None:
    payload = _approved_payload()
    payload["ref"] = "refs/heads/feature"

    decision = build_live_adapter_gate_policy_decision(payload)

    assert decision["decision"] == REJECT_DECISION
    assert _find_check(decision, "ref")["finding_code"] == "live_gate_policy_wrong_ref"


def test_policy_decision_rejects_missing_callback_url() -> None:
    payload = _approved_payload()
    payload.pop("deployment_callback_url")

    decision = build_live_adapter_gate_policy_decision(payload)

    assert decision["decision"] == REJECT_DECISION
    assert (
        _find_check(decision, "deployment_callback_url")["finding_code"]
        == "live_gate_policy_missing_callback_url"
    )


def test_policy_decision_rejects_live_execution_signal() -> None:
    payload = _approved_payload()
    verified_context = payload["verified_context"]
    assert isinstance(verified_context, dict)
    verified_context["live_execution_allowed"] = True

    decision = build_live_adapter_gate_policy_decision(payload)

    assert decision["decision"] == REJECT_DECISION
    assert _find_check(decision, "live_execution_boundary")["finding_code"] == "live_gate_policy_live_execution_open"


def test_policy_decision_rejects_pull_request_context() -> None:
    payload = _approved_payload()
    payload["pull_requests"] = [{"number": 1}]

    decision = build_live_adapter_gate_policy_decision(payload)

    assert decision["decision"] == REJECT_DECISION
    assert _find_check(decision, "pull_request_boundary")["finding_code"] == "live_gate_policy_pull_request_context"


def test_render_and_write_policy_decision(tmp_path: Path) -> None:
    decision = build_live_adapter_gate_policy_decision(
        _approved_payload(),
        generated_at="2026-04-28T00:00:00Z",
    )
    path = tmp_path / "decision.json"

    write_live_adapter_gate_policy_decision(path, decision)

    assert json.loads(path.read_text(encoding="utf-8")) == decision
    assert path.read_text(encoding="utf-8").endswith("\n")
    rendered = render_live_adapter_gate_policy_decision_text(decision)
    assert "decision: approve_contract_gate" in rendered
    assert "approval_allowed: true" in rendered


def test_policy_decision_cli_writes_artifact(tmp_path: Path) -> None:
    payload_path = tmp_path / "payload.json"
    decision_path = tmp_path / "decision.json"
    payload_path.write_text(json.dumps(_approved_payload()), encoding="utf-8")

    completed = subprocess.run(
        [
            sys.executable,
            "scripts/live_adapter_gate_policy_decision.py",
            "--payload",
            str(payload_path),
            "--decision-path",
            str(decision_path),
            "--output",
            "text",
        ],
        cwd=_repo_root(),
        check=True,
        capture_output=True,
        text=True,
    )

    assert "decision: approve_contract_gate" in completed.stdout
    assert json.loads(decision_path.read_text(encoding="utf-8"))["decision"] == APPROVE_CONTRACT_GATE_DECISION
