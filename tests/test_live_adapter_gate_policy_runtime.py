from __future__ import annotations

import builtins
import json
import sys
import types
from io import BytesIO
from typing import Any, Mapping

import pytest

from ao_kernel.live_adapter_gate_policy import EXPECTED_WORKFLOW_NAME, EXPECTED_WORKFLOW_PATH
from ao_kernel.live_adapter_gate_policy_runtime import (
    DEFAULT_HEALTH_PATH,
    DEFAULT_WEBHOOK_PATH,
    GITHUB_APP_ID_ENV,
    GITHUB_APP_PRIVATE_KEY_ENV,
    WEBHOOK_SECRET_ENV,
    CallbackPostResult,
    GithubAppConfig,
    GithubAppDeploymentReviewClient,
    PolicyRuntimeConfigError,
    build_github_app_jwt,
    handle_live_adapter_gate_policy_webhook,
    policy_runtime_wsgi_app,
)
from ao_kernel.live_adapter_gate_policy_service import (
    GITHUB_DEPLOYMENT_PROTECTION_EVENT,
    LiveAdapterGateDeploymentReviewRequest,
    github_webhook_signature,
)


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
        "installation": {"id": 12345},
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


def _body(payload: Mapping[str, object]) -> bytes:
    return json.dumps(payload, sort_keys=True).encode("utf-8")


def _headers(body: bytes, *, secret: str = "secret") -> dict[str, str]:
    return {
        "X-GitHub-Event": GITHUB_DEPLOYMENT_PROTECTION_EVENT,
        "X-GitHub-Delivery": "delivery-1",
        "X-Hub-Signature-256": github_webhook_signature(secret, body),
    }


class FakeGithubClient:
    def __init__(self) -> None:
        self.calls: list[tuple[int, LiveAdapterGateDeploymentReviewRequest]] = []

    def post_deployment_protection_review(
        self,
        *,
        installation_id: int,
        callback_request: LiveAdapterGateDeploymentReviewRequest,
    ) -> CallbackPostResult:
        self.calls.append((installation_id, callback_request))
        return {
            "status": "posted",
            "status_code": 204,
            "finding_code": None,
            "detail": "posted in test",
        }


def test_runtime_posts_approved_callback_for_verified_context() -> None:
    payload = _approved_payload()
    body = _body(payload)
    github_client = FakeGithubClient()

    result = handle_live_adapter_gate_policy_webhook(
        body,
        _headers(body),
        webhook_secret="secret",
        github_client=github_client,
        generated_at="2026-04-28T00:00:00Z",
    )

    assert result["status"] == "callback_posted"
    assert result["finding_code"] is None
    assert result["service_result"]["decision"] is not None
    assert result["service_result"]["decision"]["decision"] == "approve_contract_gate"
    assert result["service_result"]["decision"]["live_execution_allowed"] is False
    assert github_client.calls == [(12345, result["service_result"]["callback_request"])]
    callback_json = result["service_result"]["callback_request"]["json"]
    assert callback_json is not None
    assert callback_json["state"] == "approved"


def test_runtime_posts_rejected_callback_for_raw_webhook_payload() -> None:
    payload = _approved_payload()
    payload.pop("verified_context")
    body = _body(payload)
    github_client = FakeGithubClient()

    result = handle_live_adapter_gate_policy_webhook(
        body,
        _headers(body),
        webhook_secret="secret",
        github_client=github_client,
        generated_at="2026-04-28T00:00:00Z",
    )

    assert result["status"] == "callback_posted"
    assert result["service_result"]["decision"] is not None
    assert result["service_result"]["decision"]["decision"] == "reject"
    assert github_client.calls[0][0] == 12345
    callback_json = github_client.calls[0][1]["json"]
    assert callback_json is not None
    assert callback_json["state"] == "rejected"


def test_runtime_blocks_when_installation_id_is_missing() -> None:
    payload = _approved_payload()
    payload.pop("installation")
    body = _body(payload)
    github_client = FakeGithubClient()

    result = handle_live_adapter_gate_policy_webhook(
        body,
        _headers(body),
        webhook_secret="secret",
        github_client=github_client,
    )

    assert result["status"] == "blocked"
    assert result["finding_code"] == "live_gate_policy_runtime_installation_id_missing"
    assert result["callback_post"] is not None
    assert result["callback_post"]["status"] == "blocked"
    assert github_client.calls == []


def test_github_app_client_posts_callback_without_returning_secret_material(monkeypatch: pytest.MonkeyPatch) -> None:
    jwt_module = types.ModuleType("jwt")
    jwt_payloads: list[dict[str, object]] = []

    def encode(payload: dict[str, object], private_key: str, *, algorithm: str) -> str:
        jwt_payloads.append(payload)
        assert private_key == "private-key"
        assert algorithm == "RS256"
        return "app-jwt"

    jwt_module.encode = encode  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "jwt", jwt_module)
    calls: list[tuple[str, str, dict[str, str], bytes | None, float]] = []

    def transport(
        method: str,
        url: str,
        headers: Mapping[str, str],
        body: bytes | None,
        timeout_seconds: float,
    ) -> tuple[int, bytes]:
        calls.append((method, url, dict(headers), body, timeout_seconds))
        if url.endswith("/access_tokens"):
            return 201, b'{"token":"installation-token"}'
        return 204, b""

    client = GithubAppDeploymentReviewClient(
        GithubAppConfig(app_id="3522435", private_key_pem="private-key"),
        transport=transport,
        now_seconds=lambda: 1000,
    )
    callback_request: LiveAdapterGateDeploymentReviewRequest = {
        "method": "POST",
        "url": "https://api.github.com/repos/Halildeu/ao-kernel/actions/runs/1/deployment_protection_rule",
        "headers": {"Accept": "application/vnd.github+json"},
        "json": {
            "environment_name": "ao-kernel-live-adapter-gate",
            "state": "rejected",
            "comment": "reject",
        },
        "authorization_required": True,
    }

    result = client.post_deployment_protection_review(installation_id=12345, callback_request=callback_request)

    assert jwt_payloads == [{"iat": 940, "exp": 1540, "iss": "3522435"}]
    assert calls[0][0] == "POST"
    assert calls[0][2]["Authorization"] == "Bearer app-jwt"
    assert calls[1][0] == "POST"
    assert calls[1][1] == callback_request["url"]
    assert calls[1][2]["Authorization"] == "Bearer installation-token"
    assert result == {
        "status": "posted",
        "status_code": 204,
        "finding_code": None,
        "detail": "GitHub deployment protection callback review was posted.",
    }
    assert "installation-token" not in json.dumps(result)
    assert "private-key" not in json.dumps(result)


def test_build_github_app_jwt_reports_missing_optional_dependency(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delitem(sys.modules, "jwt", raising=False)
    original_import = builtins.__import__

    def missing_jwt_import(name: str, *args: Any, **kwargs: Any) -> object:
        if name == "jwt":
            raise ImportError("missing jwt")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", missing_jwt_import)

    with pytest.raises(PolicyRuntimeConfigError) as exc_info:
        build_github_app_jwt(app_id="1", private_key_pem="private-key", now_seconds=1000)

    assert "policy-service extra" in str(exc_info.value)


def test_wsgi_health_endpoint() -> None:
    status, payload = _call_wsgi("GET", DEFAULT_HEALTH_PATH, b"", {})

    assert status == "200 OK"
    assert payload == {"program_id": "GPP-2q", "status": "ok"}


def test_wsgi_rejects_bad_signature_without_secret_echo(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(WEBHOOK_SECRET_ENV, "secret")
    monkeypatch.setenv(GITHUB_APP_ID_ENV, "3522435")
    monkeypatch.setenv(GITHUB_APP_PRIVATE_KEY_ENV, "private-key")
    body = _body(_approved_payload())
    headers = _headers(body)
    headers["X-Hub-Signature-256"] = "sha256=bad"

    status, payload = _call_wsgi("POST", DEFAULT_WEBHOOK_PATH, body, headers)

    assert status == "401 Unauthorized"
    assert payload["status"] == "blocked"
    assert payload["signature_verified"] is False
    assert "secret" not in json.dumps(payload)
    assert "private-key" not in json.dumps(payload)


def _call_wsgi(
    method: str,
    path: str,
    body: bytes,
    headers: Mapping[str, str],
) -> tuple[str, dict[str, object]]:
    environ: dict[str, object] = {
        "REQUEST_METHOD": method,
        "PATH_INFO": path,
        "wsgi.input": BytesIO(body),
        "CONTENT_LENGTH": str(len(body)),
    }
    for key, value in headers.items():
        environ[f"HTTP_{key.upper().replace('-', '_')}"] = value
    captured: dict[str, object] = {}

    def start_response(status: str, response_headers: list[tuple[str, str]]) -> None:
        captured["status"] = status
        captured["headers"] = response_headers

    chunks = list(policy_runtime_wsgi_app(environ, start_response))
    response_body = b"".join(chunks)
    return str(captured["status"]), json.loads(response_body.decode("utf-8"))
