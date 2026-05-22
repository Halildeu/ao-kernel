"""Webhook service boundary for the ao-release-gate dry-run check."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Literal, Mapping, TypedDict, cast

from ao_kernel.ao_release_gate import (
    DEFAULT_CONCLUSION_MODE,
    RELEASE_GATE_CHECK_NAME,
    AoReleaseGateDecision,
    ConclusionMode,
    build_ao_release_gate_decision,
    render_ao_release_gate_decision_text,
)
from ao_kernel.live_adapter_gate import utc_timestamp
from ao_kernel.live_adapter_gate_policy_service import (
    GITHUB_DELIVERY_HEADER,
    GITHUB_EVENT_HEADER,
    GITHUB_SIGNATURE_HEADER,
    verify_github_webhook_signature,
)

RELEASE_GATE_SERVICE_SCHEMA_VERSION = "1"
RELEASE_GATE_SERVICE_PROGRAM_ID = "GPP-2w"
RELEASE_GATE_SERVICE_ARTIFACT_KIND = "ao_release_gate_service_check_run_request"
RELEASE_GATE_SERVICE_ARTIFACT = "ao-release-gate-service-check-run-request.v1.json"
DEFAULT_GITHUB_API_URL = "https://api.github.com"
SUPPORTED_RELEASE_GATE_EVENTS = frozenset({"pull_request", "check_suite", "check_run", "workflow_run"})

ReleaseGateServiceStatus = Literal["check_run_ready", "blocked"]
ReleaseGateServiceCheckStatus = Literal["pass", "blocked", "skipped"]


class AoReleaseGateServiceCheck(TypedDict):
    """Single service-boundary check."""

    name: str
    status: ReleaseGateServiceCheckStatus
    finding_code: str | None
    detail: str


class AoReleaseGateCheckRunOutput(TypedDict):
    """GitHub check-run output block."""

    title: str
    summary: str
    text: str


class AoReleaseGateCheckRunPayload(TypedDict):
    """GitHub check-run request body."""

    name: str
    head_sha: str
    status: str
    conclusion: str
    output: AoReleaseGateCheckRunOutput


class AoReleaseGateCheckRunRequest(TypedDict):
    """Network request shape for the GitHub check-run POST."""

    method: str
    url: str | None
    headers: dict[str, str]
    json: AoReleaseGateCheckRunPayload | None
    authorization_required: bool


class AoReleaseGateServiceResult(TypedDict):
    """Machine-readable release-gate service artifact."""

    schema_version: str
    artifact_kind: str
    program_id: str
    generated_at: str
    status: ReleaseGateServiceStatus
    finding_code: str | None
    reason: str
    event_name: str | None
    delivery_id: str | None
    signature_verified: bool | None
    should_post_check_run: bool
    conclusion_mode: ConclusionMode
    decision: AoReleaseGateDecision | None
    check_run_request: AoReleaseGateCheckRunRequest
    checks: list[AoReleaseGateServiceCheck]
    findings: list[str]


def _header(headers: Mapping[str, str], name: str) -> str | None:
    """Return a case-insensitive header value."""

    target = name.lower()
    for key, value in headers.items():
        if key.lower() == target and value.strip():
            return value.strip()
    return None


def _pass(name: str, *, detail: str) -> AoReleaseGateServiceCheck:
    """Build a passing service check."""

    return {"name": name, "status": "pass", "finding_code": None, "detail": detail}


def _blocked(name: str, *, finding_code: str, detail: str) -> AoReleaseGateServiceCheck:
    """Build a blocked service check."""

    return {"name": name, "status": "blocked", "finding_code": finding_code, "detail": detail}


def _skipped(name: str, *, finding_code: str | None, detail: str) -> AoReleaseGateServiceCheck:
    """Build a skipped service check."""

    return {"name": name, "status": "skipped", "finding_code": finding_code, "detail": detail}


def _decode_json_body(body: bytes) -> tuple[dict[str, Any] | None, str | None]:
    """Decode a JSON object body."""

    try:
        payload = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        return None, str(exc)
    if not isinstance(payload, dict):
        return None, "webhook JSON body must be an object"
    return cast(dict[str, Any], payload), None


def _empty_check_run_request() -> AoReleaseGateCheckRunRequest:
    """Return an empty check-run request for blocked pre-policy states."""

    return {
        "method": "POST",
        "url": None,
        "headers": {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        },
        "json": None,
        "authorization_required": True,
    }


def build_ao_release_gate_check_run_request(
    decision: AoReleaseGateDecision,
    *,
    github_api_url: str = DEFAULT_GITHUB_API_URL,
) -> AoReleaseGateCheckRunRequest:
    """Build the GitHub check-run POST request shape without executing it."""

    repository = decision["context"]["repository"]
    head_sha = decision["context"]["head_sha"]
    if repository is None or head_sha is None:
        return _empty_check_run_request()
    check_run = decision["github_check_run"]
    return {
        "method": "POST",
        "url": f"{github_api_url.rstrip('/')}/repos/{repository}/check-runs",
        "headers": {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        },
        "json": {
            "name": RELEASE_GATE_CHECK_NAME,
            "head_sha": head_sha,
            "status": "completed",
            "conclusion": check_run["conclusion"],
            "output": {
                "title": check_run["title"],
                "summary": check_run["summary"],
                "text": check_run["text"],
            },
        },
        "authorization_required": True,
    }


def build_ao_release_gate_service_result(
    body: bytes,
    headers: Mapping[str, str],
    *,
    gpp_status: object,
    review_evidence: object = None,
    webhook_secret: str | None = None,
    require_signature: bool = True,
    generated_at: str | None = None,
    github_api_url: str = DEFAULT_GITHUB_API_URL,
    conclusion_mode: ConclusionMode = DEFAULT_CONCLUSION_MODE,
) -> AoReleaseGateServiceResult:
    """Evaluate a release-gate webhook delivery and build a check-run request.

    The function never posts to GitHub. Runtime deployment must attach a GitHub
    App installation token outside this repository and execute the returned
    request shape.

    ``conclusion_mode`` is forwarded to the core decision builder so the
    GitHub check-run conclusion stays mode-aware (``shadow`` maps deny/error
    to ``neutral``, ``enforce`` keeps the historical ``failure``).

    ``review_evidence`` is the untrusted ``local-gpp-gate-evidence.v1``
    attestation forwarded to the decision core. The HTTP-layer source of
    this evidence (PR-committed file, artifact, header) is deferred
    GPP-2C infrastructure; for now callers may pass ``None`` and accept a
    ``deny_missing_evidence`` decision from the core.
    """

    checks: list[AoReleaseGateServiceCheck] = []
    event_name = _header(headers, GITHUB_EVENT_HEADER)
    delivery_id = _header(headers, GITHUB_DELIVERY_HEADER)
    signature_header = _header(headers, GITHUB_SIGNATURE_HEADER)

    if require_signature:
        if webhook_secret is None:
            signature_verified: bool | None = False
            checks.append(
                _blocked(
                    "webhook_signature",
                    finding_code="ao_release_gate_service_signature_secret_missing",
                    detail="Webhook signature verification is required, but no webhook secret was provided.",
                )
            )
        elif verify_github_webhook_signature(body, webhook_secret, signature_header):
            signature_verified = True
            checks.append(_pass("webhook_signature", detail="GitHub webhook signature verified."))
        else:
            signature_verified = False
            checks.append(
                _blocked(
                    "webhook_signature",
                    finding_code="ao_release_gate_service_signature_invalid",
                    detail="GitHub webhook signature is missing or does not match the body.",
                )
            )
    else:
        signature_verified = None
        checks.append(
            _skipped(
                "webhook_signature",
                finding_code="ao_release_gate_service_signature_not_required",
                detail="Signature verification skipped for local fixture evaluation only.",
            )
        )

    if event_name in SUPPORTED_RELEASE_GATE_EVENTS:
        checks.append(_pass("webhook_event", detail=f"Webhook event is {event_name}."))
    else:
        checks.append(
            _blocked(
                "webhook_event",
                finding_code="ao_release_gate_service_wrong_event",
                detail="Webhook event is missing or is not supported for ao-release-gate.",
            )
        )

    payload, json_error = _decode_json_body(body)
    if payload is None:
        checks.append(
            _blocked(
                "webhook_json",
                finding_code="ao_release_gate_service_invalid_json",
                detail=f"Webhook body is not a JSON object: {json_error}",
            )
        )
    else:
        checks.append(_pass("webhook_json", detail="Webhook body decoded as a JSON object."))

    pre_policy_blockers = [
        check["finding_code"] for check in checks if check["status"] == "blocked" and check["finding_code"] is not None
    ]
    if payload is None or pre_policy_blockers:
        return {
            "schema_version": RELEASE_GATE_SERVICE_SCHEMA_VERSION,
            "artifact_kind": RELEASE_GATE_SERVICE_ARTIFACT_KIND,
            "program_id": RELEASE_GATE_SERVICE_PROGRAM_ID,
            "generated_at": generated_at or utc_timestamp(),
            "status": "blocked",
            "finding_code": "ao_release_gate_service_blocked",
            "reason": "Release-gate webhook service rejected the delivery before policy evaluation.",
            "event_name": event_name,
            "delivery_id": delivery_id,
            "signature_verified": signature_verified,
            "should_post_check_run": False,
            "conclusion_mode": conclusion_mode,
            "decision": None,
            "check_run_request": _empty_check_run_request(),
            "checks": checks,
            "findings": pre_policy_blockers,
        }

    decision = build_ao_release_gate_decision(
        payload,
        gpp_status,
        review_evidence=review_evidence,
        generated_at=generated_at,
        conclusion_mode=conclusion_mode,
    )
    check_run_request = build_ao_release_gate_check_run_request(decision, github_api_url=github_api_url)
    check_run_ready = check_run_request["url"] is not None and check_run_request["json"] is not None
    if check_run_ready:
        checks.append(_pass("check_run_request", detail="GitHub ao-release-gate check-run request is ready."))
    else:
        checks.append(
            _blocked(
                "check_run_request",
                finding_code="ao_release_gate_service_check_run_target_missing",
                detail="Release-gate decision did not include repository and head SHA for check-run posting.",
            )
        )

    findings = [
        check["finding_code"] for check in checks if check["status"] == "blocked" and check["finding_code"] is not None
    ]
    return {
        "schema_version": RELEASE_GATE_SERVICE_SCHEMA_VERSION,
        "artifact_kind": RELEASE_GATE_SERVICE_ARTIFACT_KIND,
        "program_id": RELEASE_GATE_SERVICE_PROGRAM_ID,
        "generated_at": generated_at or utc_timestamp(),
        "status": "check_run_ready" if check_run_ready else "blocked",
        "finding_code": None if check_run_ready else "ao_release_gate_service_blocked",
        "reason": (
            "ao-release-gate check-run request is ready; caller must attach GitHub App auth and POST it."
            if check_run_ready
            else "ao-release-gate check-run request is not ready."
        ),
        "event_name": event_name,
        "delivery_id": delivery_id,
        "signature_verified": signature_verified,
        "should_post_check_run": check_run_ready,
        "conclusion_mode": conclusion_mode,
        "decision": decision,
        "check_run_request": check_run_request,
        "checks": checks,
        "findings": findings,
    }


def render_ao_release_gate_service_text(result: AoReleaseGateServiceResult) -> str:
    """Render a compact human-readable release-gate service result."""

    lines = [
        f"status: {result['status']}",
        f"event_name: {result['event_name'] or '<missing>'}",
        f"delivery_id: {result['delivery_id'] or '<missing>'}",
        f"signature_verified: {result['signature_verified']}",
        f"should_post_check_run: {str(result['should_post_check_run']).lower()}",
        f"conclusion_mode: {result['conclusion_mode']}",
        f"check_run_url: {result['check_run_request']['url'] or '<missing>'}",
    ]
    if result["decision"] is not None:
        lines.append(render_ao_release_gate_decision_text(result["decision"]))
    lines.append("service_checks:")
    for check in result["checks"]:
        finding = f" ({check['finding_code']})" if check["finding_code"] else ""
        lines.append(f"- {check['name']}: {check['status']}{finding}")
    if result["findings"]:
        lines.append("service_findings:")
        lines.extend(f"- {finding}" for finding in result["findings"])
    return "\n".join(lines)


def write_ao_release_gate_service_result(path: Path, result: AoReleaseGateServiceResult) -> None:
    """Write a release-gate service artifact as canonical pretty JSON."""

    path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
