from __future__ import annotations

import builtins
import json
import sys
import types
from io import BytesIO
from pathlib import Path
from typing import Any, Mapping

import pytest

from ao_kernel.ao_release_gate import (
    ALLOW_AUTONOMOUS_MERGE_DECISION,
    DENY_POLICY_VIOLATION_DECISION,
    diff_digest,
)
from ao_kernel.ao_release_gate_runtime import (
    CONCLUSION_MODE_ENV,
    DEFAULT_HEALTH_PATH,
    DEFAULT_WEBHOOK_PATH,
    GITHUB_APP_ID_ENV,
    GITHUB_APP_PRIVATE_KEY_ENV,
    GITHUB_APP_PRIVATE_KEY_SECRET_ID_ENV,
    GPP_STATUS_PATH_ENV,
    WEBHOOK_SECRET_ENV,
    WEBHOOK_SECRET_ID_ENV,
    CheckRunPostResult,
    GithubAppCheckRunClient,
    GithubAppConfig,
    ReleaseGateRuntimeConfigError,
    build_github_app_jwt,
    handle_ao_release_gate_webhook,
    load_conclusion_mode,
    load_github_app_config,
    load_webhook_secret,
    release_gate_runtime_wsgi_app,
)
from ao_kernel.ao_release_gate_service import AoReleaseGateCheckRunRequest
from ao_kernel.live_adapter_gate_policy_service import github_webhook_signature


def _gpp_status(*, issue: str = "https://github.com/Halildeu/ao-kernel/issues/541") -> dict[str, object]:
    return {
        "current_wp": {
            "id": "GPP-2",
            "status": "blocked",
            "issue": issue,
        },
        "support_widening_allowed": False,
        "production_platform_claim_allowed": False,
        "live_adapter_execution_allowed": False,
    }


# 40-hex placeholder used by _allow_payload() and the matching
# _review_evidence() factory so the context-binding check passes.
_ALLOW_HEAD_SHA = "abc1230000000000000000000000000000000000"
_ALLOW_REVIEWED_SLICE = "GPP-2"
_ALLOW_CHANGED_PATHS = [
    "ao_kernel/ao_release_gate_service.py",
    "ao_kernel/ao_release_gate_runtime.py",
    "tests/test_ao_release_gate_service.py",
    "tests/test_ao_release_gate_runtime.py",
    ".claude/plans/GPP-2w-AO-RELEASE-GATE-CHECK-RUN-SERVICE.md",
]


def _allow_payload() -> dict[str, object]:
    return {
        "repository": {"full_name": "Halildeu/ao-kernel"},
        "installation": {"id": 12345},
        "pull_request": {
            "number": 541,
            "base": {"ref": "main"},
            "head": {
                "ref": "codex/gpp-2w-release-gate-service",
                "sha": _ALLOW_HEAD_SHA,
                "repo": {"fork": False},
            },
        },
        "issue_url": "https://github.com/Halildeu/ao-kernel/issues/541",
        "branch_up_to_date": True,
        "event_name": "pull_request",
        "reviewed_slice": _ALLOW_REVIEWED_SLICE,
        "changed_paths": list(_ALLOW_CHANGED_PATHS),
        "allowed_path_prefixes": [
            "ao_kernel/",
            "tests/",
            ".claude/plans/",
        ],
        "required_checks": [
            {"name": "lint", "status": "completed", "conclusion": "success"},
            {"name": "test (3.13)", "status": "completed", "conclusion": "success"},
        ],
        "forbidden_secret_context_detected": False,
        "admin_bypass_requested": False,
        "pat_backed_bot_actor": False,
        "codex_or_claude_release_authority": False,
        "live_adapter_execution_requested": False,
    }


def _review_evidence() -> dict[str, object]:
    """Build a valid local-gpp-gate-evidence.v1 attestation bound to _allow_payload()."""
    return {
        "schema_version": "local-gpp-gate-evidence.v1",
        "decision": "operator_may_merge",
        "repo": "Halildeu/ao-kernel",
        "work_package": _ALLOW_REVIEWED_SLICE,
        "generated_at": "2026-04-28T00:00:00Z",
        "checks": {
            "startup_preflight_passed": True,
            "gpp_status_checked": True,
            "scope_allowed": True,
            "tests_passed": True,
            "secret_scan_passed": True,
            "reviewer_agree": True,
            "cross_provider_verified": True,
            "forbidden_actions_absent": True,
        },
        "findings": [],
        "reviewer_findings_count": 0,
        "gpp_2_status": "closed",
        "support_widening": False,
        "production_platform_claim": False,
        "live_adapter_execution": False,
        "context_binding": {
            "head_sha": _ALLOW_HEAD_SHA,
            "base_ref": "origin/main",
            "diff_digest": diff_digest(_ALLOW_CHANGED_PATHS),
            "changed_files_count": len(_ALLOW_CHANGED_PATHS),
        },
    }


def _body(payload: Mapping[str, object]) -> bytes:
    return json.dumps(payload, sort_keys=True).encode("utf-8")


def _headers(body: bytes, *, secret: str = "secret") -> dict[str, str]:
    return {
        "X-GitHub-Event": "pull_request",
        "X-GitHub-Delivery": "delivery-1",
        "X-Hub-Signature-256": github_webhook_signature(secret, body),
    }


class FakeGithubClient:
    def __init__(self) -> None:
        self.calls: list[tuple[int, AoReleaseGateCheckRunRequest]] = []

    def post_check_run(
        self,
        *,
        installation_id: int,
        check_run_request: AoReleaseGateCheckRunRequest,
    ) -> CheckRunPostResult:
        self.calls.append((installation_id, check_run_request))
        return {
            "status": "posted",
            "status_code": 201,
            "finding_code": None,
            "detail": "posted in test",
        }


def test_runtime_posts_success_check_run_for_allowed_context() -> None:
    payload = _allow_payload()
    body = _body(payload)
    github_client = FakeGithubClient()

    result = handle_ao_release_gate_webhook(
        body,
        _headers(body),
        webhook_secret="secret",
        github_client=github_client,
        gpp_status=_gpp_status(),
        review_evidence=_review_evidence(),
        generated_at="2026-04-28T00:00:00Z",
    )

    assert result["status"] == "check_run_posted"
    assert result["finding_code"] is None
    assert result["service_result"]["decision"] is not None
    assert result["service_result"]["decision"]["decision"] == ALLOW_AUTONOMOUS_MERGE_DECISION
    assert result["service_result"]["decision"]["dry_run"] is True
    assert result["service_result"]["decision"]["merge_authority_enabled"] is False
    assert github_client.calls == [(12345, result["service_result"]["check_run_request"])]
    check_run_json = result["service_result"]["check_run_request"]["json"]
    assert check_run_json is not None
    assert check_run_json["conclusion"] == "success"


def test_runtime_posts_neutral_check_run_for_denied_policy_in_shadow_mode() -> None:
    payload = _allow_payload()
    payload["admin_bypass_requested"] = True
    body = _body(payload)
    github_client = FakeGithubClient()

    result = handle_ao_release_gate_webhook(
        body,
        _headers(body),
        webhook_secret="secret",
        github_client=github_client,
        gpp_status=_gpp_status(),
        review_evidence=_review_evidence(),
    )

    assert result["status"] == "check_run_posted"
    assert result["service_result"]["conclusion_mode"] == "shadow"
    assert result["service_result"]["decision"] is not None
    assert result["service_result"]["decision"]["decision"] == DENY_POLICY_VIOLATION_DECISION
    assert github_client.calls[0][0] == 12345
    check_run_json = github_client.calls[0][1]["json"]
    assert check_run_json is not None
    # Shadow mode (default) maps deny/error to ``neutral`` so the advisory
    # check does not surface as red CI before AO-GATE-8.
    assert check_run_json["conclusion"] == "neutral"


def test_runtime_posts_failure_check_run_for_denied_policy_in_enforce_mode() -> None:
    payload = _allow_payload()
    payload["admin_bypass_requested"] = True
    body = _body(payload)
    github_client = FakeGithubClient()

    result = handle_ao_release_gate_webhook(
        body,
        _headers(body),
        webhook_secret="secret",
        github_client=github_client,
        gpp_status=_gpp_status(),
        review_evidence=_review_evidence(),
        conclusion_mode="enforce",
    )

    assert result["status"] == "check_run_posted"
    assert result["service_result"]["conclusion_mode"] == "enforce"
    assert result["service_result"]["decision"] is not None
    assert result["service_result"]["decision"]["decision"] == DENY_POLICY_VIOLATION_DECISION
    assert github_client.calls[0][0] == 12345
    check_run_json = github_client.calls[0][1]["json"]
    assert check_run_json is not None
    # Enforce mode restores the historical ``failure`` mapping required
    # before AO-GATE-8 makes the check a required branch protection gate.
    assert check_run_json["conclusion"] == "failure"


def test_runtime_blocks_when_installation_id_is_missing() -> None:
    payload = _allow_payload()
    payload.pop("installation")
    body = _body(payload)
    github_client = FakeGithubClient()

    result = handle_ao_release_gate_webhook(
        body,
        _headers(body),
        webhook_secret="secret",
        github_client=github_client,
        gpp_status=_gpp_status(),
    )

    assert result["status"] == "blocked"
    assert result["finding_code"] == "ao_release_gate_runtime_installation_id_missing"
    assert result["check_run_post"] is not None
    assert result["check_run_post"]["status"] == "blocked"
    assert github_client.calls == []


def test_github_app_client_posts_check_run_without_returning_secret_material(monkeypatch: pytest.MonkeyPatch) -> None:
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
        return 201, b"{}"

    client = GithubAppCheckRunClient(
        GithubAppConfig(app_id="3522435", private_key_pem="private-key"),
        transport=transport,
        now_seconds=lambda: 1000,
    )
    check_run_request: AoReleaseGateCheckRunRequest = {
        "method": "POST",
        "url": "https://api.github.com/repos/Halildeu/ao-kernel/check-runs",
        "headers": {"Accept": "application/vnd.github+json"},
        "json": {
            "name": "ao-release-gate",
            "head_sha": "abc123",
            "status": "completed",
            "conclusion": "success",
            "output": {
                "title": "ao-release-gate: allow_autonomous_merge",
                "summary": "allowed",
                "text": "All release-gate checks passed.",
            },
        },
        "authorization_required": True,
    }

    result = client.post_check_run(installation_id=12345, check_run_request=check_run_request)

    assert jwt_payloads == [{"iat": 940, "exp": 1540, "iss": "3522435"}]
    assert calls[0][0] == "POST"
    assert calls[0][2]["Authorization"] == "Bearer app-jwt"
    assert calls[1][0] == "POST"
    assert calls[1][1] == check_run_request["url"]
    assert calls[1][2]["Authorization"] == "Bearer installation-token"
    assert result == {
        "status": "posted",
        "status_code": 201,
        "finding_code": None,
        "detail": "GitHub ao-release-gate check-run was posted.",
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

    with pytest.raises(ReleaseGateRuntimeConfigError) as exc_info:
        build_github_app_jwt(app_id="1", private_key_pem="private-key", now_seconds=1000)

    assert "policy-service extra" in str(exc_info.value)


def test_runtime_loads_release_gate_secrets_from_internal_vault_stub(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    vault_path = tmp_path / ".secrets" / "vault.json"
    vault_path.parent.mkdir()
    vault_path.write_text(
        json.dumps(
            {
                "gpp2/release-gate/webhook-secret": " release-secret-from-vault ",
                "gpp2/github/private-key-pem": " private-key-from-vault ",
            },
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("SECRETS_PROVIDER", "vault_stub")
    env = {
        GITHUB_APP_ID_ENV: "3522435",
        WEBHOOK_SECRET_ID_ENV: "gpp2/release-gate/webhook-secret",
        GITHUB_APP_PRIVATE_KEY_SECRET_ID_ENV: "gpp2/github/private-key-pem",
    }

    assert load_webhook_secret(env) == "release-secret-from-vault"
    config = load_github_app_config(env)
    assert config.app_id == "3522435"
    assert config.private_key_pem == "private-key-from-vault"


def test_runtime_reports_missing_release_gate_vault_secret_without_echoing_secret_id(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    (tmp_path / ".secrets").mkdir()
    (tmp_path / ".secrets" / "vault.json").write_text("{}", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("SECRETS_PROVIDER", "vault_stub")

    with pytest.raises(ReleaseGateRuntimeConfigError) as exc_info:
        load_webhook_secret({WEBHOOK_SECRET_ID_ENV: "gpp2/release/missing-secret"})

    assert exc_info.value.finding_code == "ao_release_gate_runtime_webhook_secret_missing"
    assert "gpp2/release/missing-secret" not in str(exc_info.value)


def test_load_conclusion_mode_default_shadow() -> None:
    # No env var set → shadow default keeps the historical hosted
    # behavior unchanged for operators who have not opted into enforce.
    assert load_conclusion_mode({}) == "shadow"


def test_load_conclusion_mode_enforce() -> None:
    assert load_conclusion_mode({CONCLUSION_MODE_ENV: "enforce"}) == "enforce"
    # Whitespace is tolerated so operators who paste-with-padding still
    # get the intended mode rather than a config error.
    assert load_conclusion_mode({CONCLUSION_MODE_ENV: " enforce "}) == "enforce"


def test_load_conclusion_mode_empty_falls_back_to_default() -> None:
    # Empty / whitespace-only values fall back to shadow rather than
    # erroring; this mirrors how the compose default expands when no
    # operator override is provided.
    assert load_conclusion_mode({CONCLUSION_MODE_ENV: ""}) == "shadow"
    assert load_conclusion_mode({CONCLUSION_MODE_ENV: "   "}) == "shadow"


def test_load_conclusion_mode_invalid_raises_config_error() -> None:
    with pytest.raises(ReleaseGateRuntimeConfigError) as exc_info:
        load_conclusion_mode({CONCLUSION_MODE_ENV: "wat"})

    assert exc_info.value.finding_code == "ao_release_gate_runtime_invalid_conclusion_mode"
    # The detail must mention the expected values so an operator typo is
    # easy to fix without echoing secret material.
    assert "shadow" in str(exc_info.value)
    assert "enforce" in str(exc_info.value)


def test_wsgi_health_endpoint() -> None:
    status, payload = _call_wsgi("GET", DEFAULT_HEALTH_PATH, b"", {})

    assert status == "200 OK"
    assert payload == {"program_id": "GPP-2w", "status": "ok"}


def test_wsgi_rejects_bad_signature_without_secret_echo(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    status_path = tmp_path / "gpp_status.json"
    status_path.write_text(json.dumps(_gpp_status(), sort_keys=True), encoding="utf-8")
    monkeypatch.setenv(WEBHOOK_SECRET_ENV, "secret")
    monkeypatch.setenv(GITHUB_APP_ID_ENV, "3522435")
    monkeypatch.setenv(GITHUB_APP_PRIVATE_KEY_ENV, "private-key")
    monkeypatch.setenv(GPP_STATUS_PATH_ENV, str(status_path))
    body = _body(_allow_payload())
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

    chunks = list(release_gate_runtime_wsgi_app(environ, start_response))
    response_body = b"".join(chunks)
    return str(captured["status"]), json.loads(response_body.decode("utf-8"))
