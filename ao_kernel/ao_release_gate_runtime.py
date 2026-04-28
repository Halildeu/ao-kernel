"""Deployable runtime wrapper for the ao-release-gate check-run service."""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping, Protocol, TypedDict, cast

from ao_kernel.ao_release_gate_service import (
    AoReleaseGateCheckRunRequest,
    AoReleaseGateServiceResult,
    build_ao_release_gate_service_result,
)

RELEASE_GATE_RUNTIME_PROGRAM_ID = "GPP-2w"
DEFAULT_WEBHOOK_PATH = "/github/ao-release-gate"
DEFAULT_HEALTH_PATH = "/healthz"
DEFAULT_GITHUB_API_URL = "https://api.github.com"
DEFAULT_MAX_BODY_BYTES = 1024 * 1024
DEFAULT_HTTP_TIMEOUT_SECONDS = 10.0
DEFAULT_GITHUB_APP_JWT_TTL_SECONDS = 540
DEFAULT_GPP_STATUS_PATH = ".claude/plans/gpp_status.v1.json"

WEBHOOK_SECRET_ENV = "AO_RELEASE_GATE_WEBHOOK_SECRET"
GITHUB_APP_ID_ENV = "AO_GITHUB_APP_ID"
GITHUB_APP_PRIVATE_KEY_ENV = "AO_GITHUB_APP_PRIVATE_KEY_PEM"
GITHUB_APP_PRIVATE_KEY_PATH_ENV = "AO_GITHUB_APP_PRIVATE_KEY_PATH"
GITHUB_API_URL_ENV = "AO_GITHUB_API_URL"
GPP_STATUS_PATH_ENV = "AO_RELEASE_GATE_GPP_STATUS_PATH"
MAX_BODY_BYTES_ENV = "AO_RELEASE_GATE_MAX_BODY_BYTES"


class ReleaseGateRuntimeError(RuntimeError):
    """Base runtime error with a stable finding code."""

    def __init__(self, finding_code: str, detail: str) -> None:
        super().__init__(detail)
        self.finding_code = finding_code
        self.detail = detail


class ReleaseGateRuntimeConfigError(ReleaseGateRuntimeError):
    """Runtime configuration is incomplete or invalid."""


class ReleaseGateRuntimePostError(ReleaseGateRuntimeError):
    """GitHub check-run POST failed."""

    def __init__(self, finding_code: str, detail: str, *, status_code: int | None = None) -> None:
        super().__init__(finding_code, detail)
        self.status_code = status_code


class CheckRunPostResult(TypedDict):
    """Sanitized check-run POST outcome."""

    status: str
    status_code: int | None
    finding_code: str | None
    detail: str


class ReleaseGateRuntimeResult(TypedDict):
    """Combined webhook service and check-run POST result."""

    schema_version: str
    program_id: str
    status: str
    finding_code: str | None
    reason: str
    service_result: AoReleaseGateServiceResult
    check_run_post: CheckRunPostResult | None


HttpTransport = Callable[[str, str, Mapping[str, str], bytes | None, float], tuple[int, bytes]]


class GithubCheckRunClient(Protocol):
    """Minimal client interface used by the release-gate runtime."""

    def post_check_run(
        self,
        *,
        installation_id: int,
        check_run_request: AoReleaseGateCheckRunRequest,
    ) -> CheckRunPostResult:
        """Post an ao-release-gate check-run to GitHub."""


@dataclass(frozen=True)
class GithubAppConfig:
    """GitHub App authentication config loaded from runtime-only secrets."""

    app_id: str
    private_key_pem: str
    api_url: str = DEFAULT_GITHUB_API_URL


@dataclass(frozen=True)
class GithubAppCheckRunClient:
    """GitHub App client for posting ao-release-gate check-runs."""

    config: GithubAppConfig
    transport: HttpTransport | None = None
    timeout_seconds: float = DEFAULT_HTTP_TIMEOUT_SECONDS
    now_seconds: Callable[[], int] = lambda: int(time.time())

    def _transport(self) -> HttpTransport:
        return self.transport or urllib_http_transport

    def _installation_token(self, installation_id: int) -> str:
        app_jwt = build_github_app_jwt(
            app_id=self.config.app_id,
            private_key_pem=self.config.private_key_pem,
            now_seconds=self.now_seconds(),
        )
        url = f"{self.config.api_url.rstrip('/')}/app/installations/{installation_id}/access_tokens"
        status_code, body = self._transport()(
            "POST",
            url,
            {
                "Accept": "application/vnd.github+json",
                "Authorization": f"Bearer {app_jwt}",
                "Content-Type": "application/json",
                "X-GitHub-Api-Version": "2022-11-28",
            },
            b"{}",
            self.timeout_seconds,
        )
        if status_code < 200 or status_code >= 300:
            raise ReleaseGateRuntimePostError(
                "ao_release_gate_runtime_installation_token_failed",
                f"GitHub installation token request failed with HTTP {status_code}.",
                status_code=status_code,
            )
        payload = _decode_json_object(body)
        token = payload.get("token")
        if not isinstance(token, str) or not token:
            raise ReleaseGateRuntimePostError(
                "ao_release_gate_runtime_installation_token_missing",
                "GitHub installation token response did not contain a token.",
                status_code=status_code,
            )
        return token

    def post_check_run(
        self,
        *,
        installation_id: int,
        check_run_request: AoReleaseGateCheckRunRequest,
    ) -> CheckRunPostResult:
        """POST the check-run request with a GitHub App installation token."""

        check_run_url = check_run_request["url"]
        check_run_json = check_run_request["json"]
        if check_run_url is None or check_run_json is None:
            raise ReleaseGateRuntimePostError(
                "ao_release_gate_runtime_check_run_request_missing",
                "Release-gate service did not produce a check-run URL and JSON body.",
            )
        installation_token = self._installation_token(installation_id)
        request_body = json.dumps(check_run_json, sort_keys=True, separators=(",", ":")).encode("utf-8")
        headers = {
            **check_run_request["headers"],
            "Authorization": f"Bearer {installation_token}",
            "Content-Type": "application/json",
        }
        status_code, _body = self._transport()("POST", check_run_url, headers, request_body, self.timeout_seconds)
        if status_code < 200 or status_code >= 300:
            raise ReleaseGateRuntimePostError(
                "ao_release_gate_runtime_check_run_post_failed",
                f"GitHub ao-release-gate check-run POST failed with HTTP {status_code}.",
                status_code=status_code,
            )
        return {
            "status": "posted",
            "status_code": status_code,
            "finding_code": None,
            "detail": "GitHub ao-release-gate check-run was posted.",
        }


def urllib_http_transport(
    method: str,
    url: str,
    headers: Mapping[str, str],
    body: bytes | None,
    timeout_seconds: float,
) -> tuple[int, bytes]:
    """Perform one HTTP request with stdlib urllib."""

    request = urllib.request.Request(url=url, data=body, headers=dict(headers), method=method)
    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            return int(response.status), response.read()
    except urllib.error.HTTPError as exc:
        return int(exc.code), exc.read()


def build_github_app_jwt(
    *,
    app_id: str,
    private_key_pem: str,
    now_seconds: int | None = None,
    ttl_seconds: int = DEFAULT_GITHUB_APP_JWT_TTL_SECONDS,
) -> str:
    """Build a GitHub App JWT using a runtime-provided private key."""

    try:
        jwt_module = cast(Any, __import__("jwt"))
    except ImportError as exc:
        raise ReleaseGateRuntimeConfigError(
            "ao_release_gate_runtime_pyjwt_missing",
            "Install the policy-service extra so the hosted service can sign GitHub App JWTs.",
        ) from exc

    issued_at = int(time.time()) if now_seconds is None else now_seconds
    payload = {
        "iat": issued_at - 60,
        "exp": issued_at + ttl_seconds,
        "iss": app_id,
    }
    token = jwt_module.encode(payload, private_key_pem, algorithm="RS256")
    return cast(str, token)


def load_github_app_config(env: Mapping[str, str] | None = None) -> GithubAppConfig:
    """Load GitHub App auth config from runtime environment variables."""

    source = os.environ if env is None else env
    app_id = _required_env(source, GITHUB_APP_ID_ENV)
    private_key_pem = source.get(GITHUB_APP_PRIVATE_KEY_ENV)
    private_key_path = source.get(GITHUB_APP_PRIVATE_KEY_PATH_ENV)
    if private_key_pem is None and private_key_path:
        try:
            private_key_pem = Path(private_key_path).read_text(encoding="utf-8")
        except OSError as exc:
            raise ReleaseGateRuntimeConfigError(
                "ao_release_gate_runtime_private_key_read_failed",
                f"Could not read GitHub App private key from {GITHUB_APP_PRIVATE_KEY_PATH_ENV}.",
            ) from exc
    if not private_key_pem:
        raise ReleaseGateRuntimeConfigError(
            "ao_release_gate_runtime_private_key_missing",
            f"Set {GITHUB_APP_PRIVATE_KEY_ENV} or {GITHUB_APP_PRIVATE_KEY_PATH_ENV} in the hosted service.",
        )
    return GithubAppConfig(
        app_id=app_id,
        private_key_pem=private_key_pem,
        api_url=source.get(GITHUB_API_URL_ENV, DEFAULT_GITHUB_API_URL),
    )


def load_gpp_status(env: Mapping[str, str] | None = None) -> object:
    """Load the runtime GPP status file without reading secret material."""

    source = os.environ if env is None else env
    path = Path(source.get(GPP_STATUS_PATH_ENV, DEFAULT_GPP_STATUS_PATH))
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ReleaseGateRuntimeConfigError(
            "ao_release_gate_runtime_gpp_status_unavailable",
            f"Could not load GPP status from {path}.",
        ) from exc


def handle_ao_release_gate_webhook(
    body: bytes,
    headers: Mapping[str, str],
    *,
    webhook_secret: str,
    github_client: GithubCheckRunClient,
    gpp_status: object,
    generated_at: str | None = None,
) -> ReleaseGateRuntimeResult:
    """Evaluate one GitHub webhook delivery and post the dry-run check-run."""

    service_result = build_ao_release_gate_service_result(
        body,
        headers,
        gpp_status=gpp_status,
        webhook_secret=webhook_secret,
        require_signature=True,
        generated_at=generated_at,
    )
    if not service_result["should_post_check_run"]:
        finding_code = service_result["finding_code"] or "ao_release_gate_runtime_service_blocked"
        return _runtime_result(
            status="blocked",
            finding_code=finding_code,
            reason="Release-gate service did not produce a check-run request.",
            service_result=service_result,
            check_run_post=None,
        )

    payload = _decode_json_object(body)
    installation_id = extract_installation_id(payload)
    if installation_id is None:
        check_run_post: CheckRunPostResult = {
            "status": "blocked",
            "status_code": None,
            "finding_code": "ao_release_gate_runtime_installation_id_missing",
            "detail": "Webhook payload did not include a GitHub App installation id.",
        }
        return _runtime_result(
            status="blocked",
            finding_code=check_run_post["finding_code"],
            reason="Release-gate service could not authenticate a check-run POST without an installation id.",
            service_result=service_result,
            check_run_post=check_run_post,
        )

    try:
        check_run_post = github_client.post_check_run(
            installation_id=installation_id,
            check_run_request=service_result["check_run_request"],
        )
    except ReleaseGateRuntimePostError as exc:
        check_run_post = {
            "status": "blocked",
            "status_code": exc.status_code,
            "finding_code": exc.finding_code,
            "detail": exc.detail,
        }
        return _runtime_result(
            status="blocked",
            finding_code=exc.finding_code,
            reason="Release-gate service could not post the GitHub check-run.",
            service_result=service_result,
            check_run_post=check_run_post,
        )

    return _runtime_result(
        status="check_run_posted",
        finding_code=None,
        reason="Release-gate service evaluated the webhook and posted a dry-run GitHub check-run.",
        service_result=service_result,
        check_run_post=check_run_post,
    )


def extract_installation_id(payload: Mapping[str, Any]) -> int | None:
    """Extract the GitHub App installation id from a webhook payload."""

    installation = payload.get("installation")
    candidate: object
    if isinstance(installation, Mapping):
        candidate = installation.get("id")
    else:
        candidate = None
    if candidate is None:
        candidate = payload.get("installation_id")
    if isinstance(candidate, bool):
        return None
    if isinstance(candidate, int) and candidate > 0:
        return candidate
    if isinstance(candidate, str) and candidate.isdigit():
        parsed = int(candidate)
        return parsed if parsed > 0 else None
    return None


def release_gate_runtime_wsgi_app(
    environ: Mapping[str, Any],
    start_response: Callable[[str, list[tuple[str, str]]], None],
) -> Iterable[bytes]:
    """WSGI entrypoint for hosted ao-release-gate webhook services."""

    method = str(environ.get("REQUEST_METHOD", "GET")).upper()
    path = str(environ.get("PATH_INFO", "/"))
    if method == "GET" and path == DEFAULT_HEALTH_PATH:
        return _wsgi_json(start_response, 200, {"status": "ok", "program_id": RELEASE_GATE_RUNTIME_PROGRAM_ID})
    if method != "POST" or path != DEFAULT_WEBHOOK_PATH:
        return _wsgi_json(start_response, 404, {"status": "not_found", "program_id": RELEASE_GATE_RUNTIME_PROGRAM_ID})

    try:
        body = _read_wsgi_body(environ)
        webhook_secret = _required_env(os.environ, WEBHOOK_SECRET_ENV)
        config = load_github_app_config(os.environ)
        gpp_status = load_gpp_status(os.environ)
        result = handle_ao_release_gate_webhook(
            body,
            _wsgi_headers(environ),
            webhook_secret=webhook_secret,
            github_client=GithubAppCheckRunClient(config),
            gpp_status=gpp_status,
        )
        return _wsgi_json(start_response, _status_code_for_runtime_result(result), _redacted_runtime_payload(result))
    except ReleaseGateRuntimeConfigError as exc:
        return _wsgi_json(
            start_response,
            503,
            {
                "status": "blocked",
                "program_id": RELEASE_GATE_RUNTIME_PROGRAM_ID,
                "finding_code": exc.finding_code,
                "reason": exc.detail,
            },
        )
    except ReleaseGateRuntimeError as exc:
        status_code = 413 if exc.finding_code == "ao_release_gate_runtime_body_too_large" else 500
        return _wsgi_json(
            start_response,
            status_code,
            {
                "status": "blocked",
                "program_id": RELEASE_GATE_RUNTIME_PROGRAM_ID,
                "finding_code": exc.finding_code,
                "reason": exc.detail,
            },
        )


application = release_gate_runtime_wsgi_app


def _decode_json_object(body: bytes) -> dict[str, Any]:
    payload = json.loads(body.decode("utf-8"))
    if not isinstance(payload, dict):
        raise ReleaseGateRuntimePostError(
            "ao_release_gate_runtime_invalid_json",
            "JSON body was not an object.",
        )
    return cast(dict[str, Any], payload)


def _required_env(env: Mapping[str, str], name: str) -> str:
    value = env.get(name)
    if value:
        return value
    raise ReleaseGateRuntimeConfigError(
        "ao_release_gate_runtime_env_missing",
        f"Set {name} in the hosted service runtime.",
    )


def _runtime_result(
    *,
    status: str,
    finding_code: str | None,
    reason: str,
    service_result: AoReleaseGateServiceResult,
    check_run_post: CheckRunPostResult | None,
) -> ReleaseGateRuntimeResult:
    return {
        "schema_version": "1",
        "program_id": RELEASE_GATE_RUNTIME_PROGRAM_ID,
        "status": status,
        "finding_code": finding_code,
        "reason": reason,
        "service_result": service_result,
        "check_run_post": check_run_post,
    }


def _status_code_for_runtime_result(result: ReleaseGateRuntimeResult) -> int:
    finding_code = result["finding_code"]
    service_findings = set(result["service_result"]["findings"])
    if result["status"] == "check_run_posted":
        return 202
    if finding_code in {
        "ao_release_gate_service_signature_invalid",
        "ao_release_gate_service_signature_secret_missing",
    } or service_findings.intersection(
        {
            "ao_release_gate_service_signature_invalid",
            "ao_release_gate_service_signature_secret_missing",
        }
    ):
        return 401
    if finding_code in {
        "ao_release_gate_service_wrong_event",
        "ao_release_gate_service_invalid_json",
        "ao_release_gate_runtime_installation_id_missing",
    } or service_findings.intersection(
        {
            "ao_release_gate_service_wrong_event",
            "ao_release_gate_service_invalid_json",
        }
    ):
        return 400
    return 502


def _redacted_runtime_payload(result: ReleaseGateRuntimeResult) -> dict[str, object]:
    service_result = result["service_result"]
    decision = service_result["decision"]
    return {
        "schema_version": result["schema_version"],
        "program_id": result["program_id"],
        "status": result["status"],
        "finding_code": result["finding_code"],
        "reason": result["reason"],
        "event_name": service_result["event_name"],
        "delivery_id": service_result["delivery_id"],
        "signature_verified": service_result["signature_verified"],
        "should_post_check_run": service_result["should_post_check_run"],
        "release_gate_decision": decision["decision"] if decision is not None else None,
        "dry_run": decision["dry_run"] if decision is not None else None,
        "merge_authority_enabled": decision["merge_authority_enabled"] if decision is not None else None,
        "check_run_conclusion": (
            decision["github_check_run"]["conclusion"] if decision is not None else None
        ),
        "check_run_post": result["check_run_post"],
        "findings": service_result["findings"],
    }


def _wsgi_headers(environ: Mapping[str, Any]) -> dict[str, str]:
    headers: dict[str, str] = {}
    for key, value in environ.items():
        if not key.startswith("HTTP_") or not isinstance(value, str):
            continue
        header_name = key.removeprefix("HTTP_").replace("_", "-")
        headers[header_name] = value
    if isinstance(environ.get("CONTENT_TYPE"), str):
        headers["Content-Type"] = cast(str, environ["CONTENT_TYPE"])
    return headers


def _read_wsgi_body(environ: Mapping[str, Any]) -> bytes:
    max_body_bytes = _positive_int_env(os.environ, MAX_BODY_BYTES_ENV, DEFAULT_MAX_BODY_BYTES)
    content_length = _content_length(environ)
    if content_length > max_body_bytes:
        raise ReleaseGateRuntimeError(
            "ao_release_gate_runtime_body_too_large",
            f"Webhook body exceeds configured limit of {max_body_bytes} bytes.",
        )
    body_stream = environ.get("wsgi.input")
    read = getattr(body_stream, "read", None)
    if not callable(read):
        raise ReleaseGateRuntimeError(
            "ao_release_gate_runtime_body_stream_missing",
            "WSGI input stream is missing.",
        )
    reader = cast(Callable[[int], bytes], read)
    return reader(content_length)


def _content_length(environ: Mapping[str, Any]) -> int:
    value = environ.get("CONTENT_LENGTH")
    if not isinstance(value, str) or not value:
        return 0
    try:
        parsed = int(value)
    except ValueError as exc:
        raise ReleaseGateRuntimeError(
            "ao_release_gate_runtime_invalid_content_length",
            "CONTENT_LENGTH is not an integer.",
        ) from exc
    if parsed < 0:
        raise ReleaseGateRuntimeError(
            "ao_release_gate_runtime_invalid_content_length",
            "CONTENT_LENGTH cannot be negative.",
        )
    return parsed


def _positive_int_env(env: Mapping[str, str], name: str, default: int) -> int:
    value = env.get(name)
    if value is None:
        return default
    try:
        parsed = int(value)
    except ValueError as exc:
        raise ReleaseGateRuntimeConfigError(
            "ao_release_gate_runtime_invalid_integer_env",
            f"{name} must be an integer.",
        ) from exc
    if parsed <= 0:
        raise ReleaseGateRuntimeConfigError(
            "ao_release_gate_runtime_invalid_integer_env",
            f"{name} must be positive.",
        )
    return parsed


def _wsgi_json(
    start_response: Callable[[str, list[tuple[str, str]]], None],
    status_code: int,
    payload: Mapping[str, object],
) -> Iterable[bytes]:
    body = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    reason = {
        200: "OK",
        202: "Accepted",
        400: "Bad Request",
        401: "Unauthorized",
        404: "Not Found",
        413: "Payload Too Large",
        500: "Internal Server Error",
        502: "Bad Gateway",
        503: "Service Unavailable",
    }.get(status_code, "Status")
    start_response(
        f"{status_code} {reason}",
        [
            ("Content-Type", "application/json"),
            ("Content-Length", str(len(body))),
        ],
    )
    return [body]
