"""Webhook service boundary for the protected live-adapter gate policy."""

from __future__ import annotations

import hashlib
import hmac
import json
from pathlib import Path
from typing import Any, Literal, Mapping, TypedDict, cast

from ao_kernel.live_adapter_gate import PROTECTED_ENVIRONMENT_NAME, utc_timestamp
from ao_kernel.live_adapter_gate_policy import (
    GithubReviewState,
    LiveAdapterGatePolicyDecision,
    build_live_adapter_gate_policy_decision,
    render_live_adapter_gate_policy_decision_text,
)

POLICY_SERVICE_SCHEMA_VERSION = "1"
POLICY_SERVICE_PROGRAM_ID = "GPP-2p"
POLICY_SERVICE_ARTIFACT_KIND = "live_adapter_gate_policy_service_callback_request"
POLICY_SERVICE_ARTIFACT = "live-adapter-gate-policy-service-callback-request.v1.json"
GITHUB_DEPLOYMENT_PROTECTION_EVENT = "deployment_protection_rule"
GITHUB_SIGNATURE_HEADER = "x-hub-signature-256"
GITHUB_EVENT_HEADER = "x-github-event"
GITHUB_DELIVERY_HEADER = "x-github-delivery"

PolicyServiceStatus = Literal["callback_ready", "blocked"]
PolicyServiceCheckStatus = Literal["pass", "blocked", "skipped"]


class LiveAdapterGatePolicyServiceCheck(TypedDict):
    """Single service-boundary check."""

    name: str
    status: PolicyServiceCheckStatus
    finding_code: str | None
    detail: str


class LiveAdapterGateDeploymentReviewPayload(TypedDict):
    """GitHub custom deployment protection review request body."""

    environment_name: str
    state: GithubReviewState
    comment: str


class LiveAdapterGateDeploymentReviewRequest(TypedDict):
    """Network request shape for the GitHub deployment protection callback."""

    method: str
    url: str | None
    headers: dict[str, str]
    json: LiveAdapterGateDeploymentReviewPayload | None
    authorization_required: bool


class LiveAdapterGatePolicyServiceResult(TypedDict):
    """Machine-readable policy service callback artifact."""

    schema_version: str
    artifact_kind: str
    program_id: str
    generated_at: str
    status: PolicyServiceStatus
    finding_code: str | None
    reason: str
    event_name: str | None
    delivery_id: str | None
    signature_verified: bool | None
    should_post_callback: bool
    decision: LiveAdapterGatePolicyDecision | None
    callback_request: LiveAdapterGateDeploymentReviewRequest
    checks: list[LiveAdapterGatePolicyServiceCheck]
    findings: list[str]


def github_webhook_signature(secret: str, body: bytes) -> str:
    """Return the GitHub ``X-Hub-Signature-256`` value for ``body``."""

    digest = hmac.new(secret.encode("utf-8"), msg=body, digestmod=hashlib.sha256).hexdigest()
    return f"sha256={digest}"


def verify_github_webhook_signature(body: bytes, secret: str, signature_header: str | None) -> bool:
    """Verify a GitHub webhook HMAC-SHA256 signature in constant time."""

    if not secret or not signature_header:
        return False
    expected = github_webhook_signature(secret, body)
    return hmac.compare_digest(expected, signature_header)


def _header(headers: Mapping[str, str], name: str) -> str | None:
    """Return a case-insensitive header value."""

    target = name.lower()
    for key, value in headers.items():
        if key.lower() == target and value.strip():
            return value.strip()
    return None


def _pass(name: str, *, detail: str) -> LiveAdapterGatePolicyServiceCheck:
    """Build a passing service check."""

    return {"name": name, "status": "pass", "finding_code": None, "detail": detail}


def _blocked(name: str, *, finding_code: str, detail: str) -> LiveAdapterGatePolicyServiceCheck:
    """Build a blocked service check."""

    return {"name": name, "status": "blocked", "finding_code": finding_code, "detail": detail}


def _skipped(name: str, *, finding_code: str | None, detail: str) -> LiveAdapterGatePolicyServiceCheck:
    """Build a skipped service check."""

    return {"name": name, "status": "skipped", "finding_code": finding_code, "detail": detail}


def build_deployment_protection_review_payload(
    decision: LiveAdapterGatePolicyDecision,
) -> LiveAdapterGateDeploymentReviewPayload:
    """Build the GitHub custom deployment protection review JSON body."""

    environment_name = decision["context"]["environment"] or PROTECTED_ENVIRONMENT_NAME
    finding_suffix = ""
    if decision["findings"]:
        finding_suffix = " Findings: " + ", ".join(decision["findings"])
    comment = (
        f"ao-kernel live-adapter gate policy decision: {decision['decision']}. {decision['reason']}{finding_suffix}"
    )
    return {
        "environment_name": environment_name,
        "state": decision["github_review_state"],
        "comment": comment,
    }


def build_deployment_protection_review_request(
    decision: LiveAdapterGatePolicyDecision,
) -> LiveAdapterGateDeploymentReviewRequest:
    """Build the GitHub callback request shape without executing it."""

    return {
        "method": "POST",
        "url": decision["context"]["deployment_callback_url"],
        "headers": {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        },
        "json": build_deployment_protection_review_payload(decision),
        "authorization_required": True,
    }


def _empty_callback_request() -> LiveAdapterGateDeploymentReviewRequest:
    """Return an empty callback request for blocked pre-policy states."""

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


def _decode_json_body(body: bytes) -> tuple[dict[str, Any] | None, str | None]:
    """Decode a JSON object body."""

    try:
        payload = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        return None, str(exc)
    if not isinstance(payload, dict):
        return None, "webhook JSON body must be an object"
    return cast(dict[str, Any], payload), None


def build_live_adapter_gate_policy_service_result(
    body: bytes,
    headers: Mapping[str, str],
    *,
    webhook_secret: str | None = None,
    require_signature: bool = True,
    generated_at: str | None = None,
) -> LiveAdapterGatePolicyServiceResult:
    """Evaluate a webhook delivery and build a callback request artifact.

    The function never posts to GitHub. Runtime deployment must attach a GitHub
    App token outside this repository and execute the returned request shape.
    """

    checks: list[LiveAdapterGatePolicyServiceCheck] = []
    event_name = _header(headers, GITHUB_EVENT_HEADER)
    delivery_id = _header(headers, GITHUB_DELIVERY_HEADER)
    signature_header = _header(headers, GITHUB_SIGNATURE_HEADER)

    if require_signature:
        if webhook_secret is None:
            signature_verified: bool | None = False
            checks.append(
                _blocked(
                    "webhook_signature",
                    finding_code="live_gate_policy_service_signature_secret_missing",
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
                    finding_code="live_gate_policy_service_signature_invalid",
                    detail="GitHub webhook signature is missing or does not match the body.",
                )
            )
    else:
        signature_verified = None
        checks.append(
            _skipped(
                "webhook_signature",
                finding_code="live_gate_policy_service_signature_not_required",
                detail="Signature verification skipped for local fixture evaluation only.",
            )
        )

    event_ok = event_name == GITHUB_DEPLOYMENT_PROTECTION_EVENT
    if event_ok:
        checks.append(_pass("webhook_event", detail=f"Webhook event is {GITHUB_DEPLOYMENT_PROTECTION_EVENT}."))
    else:
        checks.append(
            _blocked(
                "webhook_event",
                finding_code="live_gate_policy_service_wrong_event",
                detail="Webhook event is missing or is not deployment_protection_rule.",
            )
        )

    payload, json_error = _decode_json_body(body)
    if payload is None:
        checks.append(
            _blocked(
                "webhook_json",
                finding_code="live_gate_policy_service_invalid_json",
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
            "schema_version": POLICY_SERVICE_SCHEMA_VERSION,
            "artifact_kind": POLICY_SERVICE_ARTIFACT_KIND,
            "program_id": POLICY_SERVICE_PROGRAM_ID,
            "generated_at": generated_at or utc_timestamp(),
            "status": "blocked",
            "finding_code": "live_gate_policy_service_blocked",
            "reason": "Deployment-protection webhook service rejected the delivery before policy evaluation.",
            "event_name": event_name,
            "delivery_id": delivery_id,
            "signature_verified": signature_verified,
            "should_post_callback": False,
            "decision": None,
            "callback_request": _empty_callback_request(),
            "checks": checks,
            "findings": pre_policy_blockers,
        }

    decision = build_live_adapter_gate_policy_decision(payload, generated_at=generated_at)
    callback_request = build_deployment_protection_review_request(decision)
    callback_ready = callback_request["url"] is not None
    if callback_ready:
        checks.append(_pass("callback_request", detail="GitHub deployment protection callback request is ready."))
    else:
        checks.append(
            _blocked(
                "callback_request",
                finding_code="live_gate_policy_service_missing_callback_url",
                detail="Policy decision did not include a usable deployment callback URL.",
            )
        )

    findings = [
        check["finding_code"] for check in checks if check["status"] == "blocked" and check["finding_code"] is not None
    ]
    return {
        "schema_version": POLICY_SERVICE_SCHEMA_VERSION,
        "artifact_kind": POLICY_SERVICE_ARTIFACT_KIND,
        "program_id": POLICY_SERVICE_PROGRAM_ID,
        "generated_at": generated_at or utc_timestamp(),
        "status": "callback_ready" if callback_ready else "blocked",
        "finding_code": None if callback_ready else "live_gate_policy_service_blocked",
        "reason": (
            "Deployment-protection callback request is ready; caller must attach GitHub App auth and POST it."
            if callback_ready
            else "Deployment-protection callback request is not ready."
        ),
        "event_name": event_name,
        "delivery_id": delivery_id,
        "signature_verified": signature_verified,
        "should_post_callback": callback_ready,
        "decision": decision,
        "callback_request": callback_request,
        "checks": checks,
        "findings": findings,
    }


def render_live_adapter_gate_policy_service_text(result: LiveAdapterGatePolicyServiceResult) -> str:
    """Render a compact human-readable policy service result."""

    lines = [
        f"status: {result['status']}",
        f"event_name: {result['event_name'] or '<missing>'}",
        f"delivery_id: {result['delivery_id'] or '<missing>'}",
        f"signature_verified: {result['signature_verified']}",
        f"should_post_callback: {str(result['should_post_callback']).lower()}",
        f"callback_url: {result['callback_request']['url'] or '<missing>'}",
    ]
    if result["decision"] is not None:
        lines.append(render_live_adapter_gate_policy_decision_text(result["decision"]))
    lines.append("service_checks:")
    for check in result["checks"]:
        finding = f" ({check['finding_code']})" if check["finding_code"] else ""
        lines.append(f"- {check['name']}: {check['status']}{finding}")
    if result["findings"]:
        lines.append("service_findings:")
        lines.extend(f"- {finding}" for finding in result["findings"])
    return "\n".join(lines)


def write_live_adapter_gate_policy_service_result(
    path: Path,
    result: LiveAdapterGatePolicyServiceResult,
) -> None:
    """Write a policy service callback artifact as canonical pretty JSON."""

    path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
