from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from ao_kernel.live_adapter_gate_policy import EXPECTED_WORKFLOW_NAME, EXPECTED_WORKFLOW_PATH
from ao_kernel.live_adapter_gate_policy_service import (
    GITHUB_DEPLOYMENT_PROTECTION_EVENT,
    build_live_adapter_gate_policy_service_result,
    github_webhook_signature,
    verify_github_webhook_signature,
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


def _body(payload: dict[str, object]) -> bytes:
    return json.dumps(payload, sort_keys=True).encode("utf-8")


def _headers(body: bytes, *, secret: str = "secret", event: str = GITHUB_DEPLOYMENT_PROTECTION_EVENT) -> dict[str, str]:
    return {
        "X-GitHub-Event": event,
        "X-GitHub-Delivery": "delivery-1",
        "X-Hub-Signature-256": github_webhook_signature(secret, body),
    }


def test_signature_matches_github_docs_vector() -> None:
    body = b"Hello, World!"
    secret = "It's a Secret to Everybody"
    expected = "sha256=757107ea0eb2509fc211221cce984b8a37570b6d7586c22c46f4379c8b043e17"

    assert github_webhook_signature(secret, body) == expected
    assert verify_github_webhook_signature(body, secret, expected) is True
    assert verify_github_webhook_signature(body, "wrong", expected) is False


def test_service_blocks_missing_required_signature() -> None:
    body = _body(_approved_payload())

    result = build_live_adapter_gate_policy_service_result(
        body,
        {"X-GitHub-Event": GITHUB_DEPLOYMENT_PROTECTION_EVENT},
        webhook_secret="secret",
    )

    assert result["status"] == "blocked"
    assert result["should_post_callback"] is False
    assert result["decision"] is None
    assert "live_gate_policy_service_signature_invalid" in result["findings"]


def test_service_blocks_wrong_event_before_policy_evaluation() -> None:
    body = _body(_approved_payload())

    result = build_live_adapter_gate_policy_service_result(
        body,
        _headers(body, event="push"),
        webhook_secret="secret",
    )

    assert result["status"] == "blocked"
    assert result["should_post_callback"] is False
    assert result["decision"] is None
    assert "live_gate_policy_service_wrong_event" in result["findings"]


def test_service_blocks_malformed_json_before_policy_evaluation() -> None:
    body = b"{not-json"

    result = build_live_adapter_gate_policy_service_result(
        body,
        _headers(body),
        webhook_secret="secret",
    )

    assert result["status"] == "blocked"
    assert result["should_post_callback"] is False
    assert result["decision"] is None
    assert "live_gate_policy_service_invalid_json" in result["findings"]


def test_service_builds_rejected_callback_for_raw_webhook_payload() -> None:
    payload = _approved_payload()
    payload.pop("verified_context")
    body = _body(payload)

    result = build_live_adapter_gate_policy_service_result(
        body,
        _headers(body),
        webhook_secret="secret",
        generated_at="2026-04-28T00:00:00Z",
    )

    assert result["status"] == "callback_ready"
    assert result["should_post_callback"] is True
    assert result["signature_verified"] is True
    assert result["decision"] is not None
    assert result["decision"]["decision"] == "reject"
    assert result["callback_request"]["method"] == "POST"
    assert result["callback_request"]["url"] == payload["deployment_callback_url"]
    assert result["callback_request"]["json"] == {
        "environment_name": "ao-kernel-live-adapter-gate",
        "state": "rejected",
        "comment": (
            "ao-kernel live-adapter gate policy decision: reject. "
            "Deployment-protection policy rejected the request fail-closed. "
            "Findings: live_gate_policy_missing_workflow_identity, "
            "live_gate_policy_prerequisites_not_ready, live_gate_policy_live_execution_open, "
            "live_gate_policy_support_boundary_open"
        ),
    }
    assert result["callback_request"]["authorization_required"] is True


def test_service_builds_approved_callback_for_verified_closed_context() -> None:
    payload = _approved_payload()
    body = _body(payload)

    result = build_live_adapter_gate_policy_service_result(
        body,
        _headers(body),
        webhook_secret="secret",
        generated_at="2026-04-28T00:00:00Z",
    )

    assert result["status"] == "callback_ready"
    assert result["should_post_callback"] is True
    assert result["decision"] is not None
    assert result["decision"]["decision"] == "approve_contract_gate"
    assert result["decision"]["live_execution_allowed"] is False
    assert result["decision"]["support_widening_allowed"] is False
    assert result["decision"]["production_platform_claim_allowed"] is False
    assert result["callback_request"]["json"] is not None
    assert result["callback_request"]["json"]["state"] == "approved"
    assert result["callback_request"]["json"]["environment_name"] == "ao-kernel-live-adapter-gate"


def test_service_cli_writes_callback_artifact_for_unsigned_fixture(tmp_path: Path) -> None:
    payload_path = tmp_path / "payload.json"
    artifact_path = tmp_path / "service.json"
    payload_path.write_text(json.dumps(_approved_payload(), sort_keys=True), encoding="utf-8")

    completed = subprocess.run(
        [
            sys.executable,
            "scripts/live_adapter_gate_policy_service_smoke.py",
            "--payload",
            str(payload_path),
            "--artifact-path",
            str(artifact_path),
            "--allow-unsigned-fixture",
            "--output",
            "text",
        ],
        cwd=_repo_root(),
        check=True,
        capture_output=True,
        text=True,
    )

    artifact = json.loads(artifact_path.read_text(encoding="utf-8"))
    assert "status: callback_ready" in completed.stdout
    assert artifact["status"] == "callback_ready"
    assert artifact["signature_verified"] is None
    assert artifact["callback_request"]["json"]["state"] == "approved"
