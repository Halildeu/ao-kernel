"""Fail-closed deployment protection policy decision helpers.

This module is intentionally side-effect free. It evaluates a GitHub
``deployment_protection_rule`` webhook payload plus service-enriched verified
context and returns the decision a deployment-protection service can use when
calling GitHub's review callback.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Literal, TypedDict, cast
from urllib.parse import urlparse

from ao_kernel.live_adapter_gate import (
    ADAPTER_ID,
    GATE_ID,
    PROTECTED_ENVIRONMENT_NAME,
    REQUIRED_DEPLOYMENT_PROTECTION_APP_SLUG,
    SUPPORT_TIER,
    utc_timestamp,
)

POLICY_DECISION_SCHEMA_VERSION = "1"
POLICY_DECISION_PROGRAM_ID = "GPP-2o"
POLICY_DECISION_ARTIFACT_KIND = "live_adapter_gate_policy_decision"
POLICY_DECISION_ARTIFACT = "live-adapter-gate-policy-decision.v1.json"
EXPECTED_REPOSITORY = "Halildeu/ao-kernel"
EXPECTED_REF = "main"
EXPECTED_TRIGGER_EVENT = "workflow_dispatch"
EXPECTED_WORKFLOW_NAME = "Live Adapter Gate"
EXPECTED_WORKFLOW_PATH = ".github/workflows/live-adapter-gate.yml"
APPROVE_CONTRACT_GATE_DECISION = "approve_contract_gate"
REJECT_DECISION = "reject"
POLICY_REJECT_FINDING = "live_gate_policy_rejected"

PolicyCheckStatus = Literal["pass", "blocked"]
PolicyDecisionValue = Literal["approve_contract_gate", "reject"]
GithubReviewState = Literal["approved", "rejected"]


class LiveAdapterGatePolicyCheck(TypedDict):
    """Single deterministic policy-service input check."""

    name: str
    status: PolicyCheckStatus
    finding_code: str | None
    detail: str


class LiveAdapterGatePolicyContext(TypedDict):
    """Extracted deployment-protection policy context."""

    repository: str | None
    environment: str | None
    event: str | None
    ref: str | None
    sha: str | None
    deployment_callback_url: str | None
    workflow_name: str | None
    workflow_path: str | None
    prerequisites_ready: bool | None
    attestation_overall_status: str | None
    live_execution_allowed: bool | None
    support_widening_allowed: bool | None
    production_platform_claim_allowed: bool | None
    pull_request_count: int | None


class LiveAdapterGatePolicyDecision(TypedDict):
    """Machine-readable deployment-protection policy decision."""

    schema_version: str
    artifact_kind: str
    program_id: str
    gate_id: str
    adapter_id: str
    support_tier: str
    generated_at: str
    app_slug: str
    decision: PolicyDecisionValue
    github_review_state: GithubReviewState
    approval_allowed: bool
    live_execution_allowed: bool
    support_widening_allowed: bool
    production_platform_claim_allowed: bool
    finding_code: str | None
    reason: str
    context: LiveAdapterGatePolicyContext
    checks: list[LiveAdapterGatePolicyCheck]
    findings: list[str]


def _as_dict(payload: object) -> dict[str, Any]:
    """Return ``payload`` as a dictionary or an empty dictionary."""

    if isinstance(payload, dict):
        return cast(dict[str, Any], payload)
    return {}


def _as_list(payload: object) -> list[Any]:
    """Return ``payload`` as a list or an empty list."""

    if isinstance(payload, list):
        return payload
    return []


def _string(value: object) -> str | None:
    """Return a non-empty string value."""

    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def _bool(value: object) -> bool | None:
    """Return a boolean value without coercing strings."""

    if isinstance(value, bool):
        return value
    return None


def _normalize_ref(value: str | None) -> str | None:
    """Normalize refs/heads/main to main."""

    if value is None:
        return None
    if value.startswith("refs/heads/"):
        return value.removeprefix("refs/heads/")
    return value


def _first_string(*values: object) -> str | None:
    """Return the first non-empty string."""

    for value in values:
        candidate = _string(value)
        if candidate is not None:
            return candidate
    return None


def _first_bool(*values: object) -> bool | None:
    """Return the first explicit boolean."""

    for value in values:
        candidate = _bool(value)
        if candidate is not None:
            return candidate
    return None


def _callback_url_is_usable(url: str | None) -> bool:
    """Return whether GitHub supplied a plausible review callback URL."""

    if url is None:
        return False
    parsed = urlparse(url)
    return parsed.scheme == "https" and bool(parsed.netloc) and bool(parsed.path)


def _workflow_matches(name: str | None, path: str | None) -> bool:
    """Return whether the enriched context identifies the approved workflow."""

    return name == EXPECTED_WORKFLOW_NAME or path == EXPECTED_WORKFLOW_PATH


def _pass(
    name: str,
    *,
    detail: str,
) -> LiveAdapterGatePolicyCheck:
    """Build a passing policy check."""

    return {
        "name": name,
        "status": "pass",
        "finding_code": None,
        "detail": detail,
    }


def _blocked(
    name: str,
    *,
    finding_code: str,
    detail: str,
) -> LiveAdapterGatePolicyCheck:
    """Build a blocked policy check."""

    return {
        "name": name,
        "status": "blocked",
        "finding_code": finding_code,
        "detail": detail,
    }


def _check(
    name: str,
    condition: bool,
    *,
    finding_code: str,
    pass_detail: str,
    blocked_detail: str,
) -> LiveAdapterGatePolicyCheck:
    """Build one fail-closed check."""

    if condition:
        return _pass(name, detail=pass_detail)
    return _blocked(name, finding_code=finding_code, detail=blocked_detail)


def _verified_context(payload: dict[str, Any]) -> dict[str, Any]:
    """Return service-enriched verified context if present."""

    candidates = (
        payload.get("verified_context"),
        payload.get("ao_kernel_policy_context"),
        payload.get("gpp"),
        _as_dict(payload.get("ao_kernel")).get("policy_context"),
    )
    for candidate in candidates:
        context = _as_dict(candidate)
        if context:
            return context
    return {}


def extract_live_adapter_gate_policy_context(payload: object) -> LiveAdapterGatePolicyContext:
    """Extract the policy decision context from a webhook-shaped payload."""

    root = _as_dict(payload)
    repository = _as_dict(root.get("repository"))
    deployment = _as_dict(root.get("deployment"))
    workflow = _as_dict(root.get("workflow"))
    workflow_run = _as_dict(root.get("workflow_run"))
    verified = _verified_context(root)
    environment_value = root.get("environment")
    environment = _first_string(
        environment_value if isinstance(environment_value, str) else None,
        _as_dict(environment_value).get("name"),
        deployment.get("environment"),
        verified.get("environment"),
    )
    ref = _normalize_ref(
        _first_string(
            root.get("ref"),
            deployment.get("ref"),
            workflow_run.get("head_branch"),
            verified.get("ref"),
        )
    )
    pull_requests = _as_list(root.get("pull_requests"))
    return {
        "repository": _first_string(repository.get("full_name"), root.get("repository_full_name"), verified.get("repository")),
        "environment": environment,
        "event": _first_string(root.get("event"), workflow_run.get("event"), verified.get("event")),
        "ref": ref,
        "sha": _first_string(root.get("sha"), deployment.get("sha"), workflow_run.get("head_sha"), verified.get("sha")),
        "deployment_callback_url": _first_string(
            root.get("deployment_callback_url"),
            root.get("callback_url"),
            _as_dict(root.get("deployment_protection_rule")).get("url"),
            verified.get("deployment_callback_url"),
        ),
        "workflow_name": _first_string(workflow.get("name"), workflow_run.get("name"), verified.get("workflow_name")),
        "workflow_path": _first_string(workflow.get("path"), workflow_run.get("path"), verified.get("workflow_path")),
        "prerequisites_ready": _first_bool(
            verified.get("prerequisites_ready"),
            verified.get("protected_prerequisites_ready"),
        ),
        "attestation_overall_status": _first_string(
            verified.get("attestation_overall_status"),
            _as_dict(verified.get("attestation")).get("overall_status"),
        ),
        "live_execution_allowed": _first_bool(
            verified.get("live_execution_allowed"),
            verified.get("live_adapter_execution_allowed"),
        ),
        "support_widening_allowed": _first_bool(
            verified.get("support_widening_allowed"),
            verified.get("support_widening"),
        ),
        "production_platform_claim_allowed": _first_bool(
            verified.get("production_platform_claim_allowed"),
            verified.get("production_platform_claim"),
        ),
        "pull_request_count": len(pull_requests) if "pull_requests" in root else None,
    }


def build_live_adapter_gate_policy_decision(
    payload: object,
    *,
    generated_at: str | None = None,
) -> LiveAdapterGatePolicyDecision:
    """Build a fail-closed deployment-protection policy decision.

    Raw GitHub webhook fields are not enough for approval. The service must
    enrich the payload with verified GPP context proving the workflow identity,
    ready prerequisite attestation, and closed support/live-execution boundary.
    """

    context = extract_live_adapter_gate_policy_context(payload)
    prerequisites_ready = (
        context["prerequisites_ready"] is True or context["attestation_overall_status"] == "ready"
    )
    live_execution_closed = context["live_execution_allowed"] is False
    support_boundary_closed = (
        context["support_widening_allowed"] is False
        and context["production_platform_claim_allowed"] is False
    )
    checks = [
        _check(
            "repository",
            context["repository"] == EXPECTED_REPOSITORY,
            finding_code="live_gate_policy_wrong_repository",
            pass_detail=f"Repository is {EXPECTED_REPOSITORY}.",
            blocked_detail="Repository is missing or is not the approved repository.",
        ),
        _check(
            "environment",
            context["environment"] == PROTECTED_ENVIRONMENT_NAME,
            finding_code="live_gate_policy_wrong_environment",
            pass_detail=f"Environment is {PROTECTED_ENVIRONMENT_NAME}.",
            blocked_detail="Environment is missing or is not the protected live-adapter gate environment.",
        ),
        _check(
            "trigger_event",
            context["event"] == EXPECTED_TRIGGER_EVENT,
            finding_code="live_gate_policy_wrong_event",
            pass_detail=f"Trigger event is {EXPECTED_TRIGGER_EVENT}.",
            blocked_detail="Trigger event is missing or is not workflow_dispatch.",
        ),
        _check(
            "ref",
            context["ref"] == EXPECTED_REF,
            finding_code="live_gate_policy_wrong_ref",
            pass_detail=f"Ref is {EXPECTED_REF}.",
            blocked_detail="Ref is missing or is not the protected main ref.",
        ),
        _check(
            "sha",
            context["sha"] is not None,
            finding_code="live_gate_policy_missing_sha",
            pass_detail="Commit SHA is present.",
            blocked_detail="Commit SHA is missing.",
        ),
        _check(
            "deployment_callback_url",
            _callback_url_is_usable(context["deployment_callback_url"]),
            finding_code="live_gate_policy_missing_callback_url",
            pass_detail="Deployment protection review callback URL is present.",
            blocked_detail="Deployment protection review callback URL is missing or unusable.",
        ),
        _check(
            "workflow_identity",
            _workflow_matches(context["workflow_name"], context["workflow_path"]),
            finding_code="live_gate_policy_missing_workflow_identity",
            pass_detail="Verified context identifies the approved live-adapter gate workflow.",
            blocked_detail="Verified context does not identify the approved live-adapter gate workflow.",
        ),
        _check(
            "pull_request_boundary",
            context["pull_request_count"] in (0, None),
            finding_code="live_gate_policy_pull_request_context",
            pass_detail="No pull_request context is attached to the deployment-protection payload.",
            blocked_detail="Pull request context is attached; protected live credentials must stay away from PR paths.",
        ),
        _check(
            "protected_prerequisites",
            prerequisites_ready,
            finding_code="live_gate_policy_prerequisites_not_ready",
            pass_detail="Verified protected prerequisite attestation is ready.",
            blocked_detail="Verified protected prerequisite attestation is missing or not ready.",
        ),
        _check(
            "live_execution_boundary",
            live_execution_closed,
            finding_code="live_gate_policy_live_execution_open",
            pass_detail="Verified context keeps live adapter execution disabled.",
            blocked_detail="Verified context does not explicitly keep live adapter execution disabled.",
        ),
        _check(
            "support_boundary",
            support_boundary_closed,
            finding_code="live_gate_policy_support_boundary_open",
            pass_detail="Verified context keeps support widening and production platform claim closed.",
            blocked_detail="Verified context does not explicitly keep support widening and production platform claim closed.",
        ),
    ]
    findings = [check["finding_code"] for check in checks if check["finding_code"] is not None]
    approval_allowed = not findings
    decision = cast(PolicyDecisionValue, APPROVE_CONTRACT_GATE_DECISION if approval_allowed else REJECT_DECISION)
    review_state: GithubReviewState = "approved" if approval_allowed else "rejected"
    return {
        "schema_version": POLICY_DECISION_SCHEMA_VERSION,
        "artifact_kind": POLICY_DECISION_ARTIFACT_KIND,
        "program_id": POLICY_DECISION_PROGRAM_ID,
        "gate_id": GATE_ID,
        "adapter_id": ADAPTER_ID,
        "support_tier": SUPPORT_TIER,
        "generated_at": generated_at or utc_timestamp(),
        "app_slug": REQUIRED_DEPLOYMENT_PROTECTION_APP_SLUG,
        "decision": decision,
        "github_review_state": review_state,
        "approval_allowed": approval_allowed,
        "live_execution_allowed": False,
        "support_widening_allowed": False,
        "production_platform_claim_allowed": False,
        "finding_code": None if approval_allowed else POLICY_REJECT_FINDING,
        "reason": (
            "Contract-only protected gate may proceed; live adapter execution, support widening, "
            "and production platform claim remain disabled."
            if approval_allowed
            else "Deployment-protection policy rejected the request fail-closed."
        ),
        "context": context,
        "checks": checks,
        "findings": findings,
    }


def render_live_adapter_gate_policy_decision_text(decision: LiveAdapterGatePolicyDecision) -> str:
    """Render a compact human-readable policy decision."""

    context = decision["context"]
    lines = [
        f"decision: {decision['decision']}",
        f"github_review_state: {decision['github_review_state']}",
        f"approval_allowed: {str(decision['approval_allowed']).lower()}",
        f"live_execution_allowed: {str(decision['live_execution_allowed']).lower()}",
        f"support_widening_allowed: {str(decision['support_widening_allowed']).lower()}",
        f"production_platform_claim_allowed: {str(decision['production_platform_claim_allowed']).lower()}",
        f"repository: {context['repository'] or '<missing>'}",
        f"environment: {context['environment'] or '<missing>'}",
        f"ref: {context['ref'] or '<missing>'}",
        f"sha: {context['sha'] or '<missing>'}",
        f"workflow: {context['workflow_name'] or context['workflow_path'] or '<missing>'}",
        "checks:",
    ]
    for check in decision["checks"]:
        finding = f" ({check['finding_code']})" if check["finding_code"] else ""
        lines.append(f"- {check['name']}: {check['status']}{finding}")
    if decision["findings"]:
        lines.append("findings:")
        lines.extend(f"- {finding}" for finding in decision["findings"])
    return "\n".join(lines)


def write_live_adapter_gate_policy_decision(
    path: Path,
    decision: LiveAdapterGatePolicyDecision,
) -> None:
    """Write a policy decision artifact as canonical pretty JSON."""

    path.write_text(json.dumps(decision, indent=2, sort_keys=True) + "\n", encoding="utf-8")
