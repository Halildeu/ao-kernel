"""CI-managed live adapter gate contract helpers.

The GP-4 gate is intentionally fail-closed: current helpers emit
machine-readable blocked reports/artifacts but do not execute external live
adapters.
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from importlib import resources
from pathlib import Path
from typing import Any, Literal, TypedDict, cast

from jsonschema import Draft202012Validator

SCHEMA_VERSION = "1"
PROGRAM_ID = "GP-4.1"
EVIDENCE_PROGRAM_ID = "GP-4.2"
GATE_ID = "ci-managed-live-adapter-gate"
ADAPTER_ID = "claude-code-cli"
SUPPORT_TIER = "Beta (operator-managed)"
BLOCKED_FINDING = "live_gate_not_implemented"
EVIDENCE_ARTIFACT_KIND = "live_adapter_gate_evidence"
EVIDENCE_SCHEMA_NAME = "live-adapter-gate-evidence.schema.v1.json"
CONTRACT_REPORT_ARTIFACT = "live-adapter-gate-contract.v1.json"
EVIDENCE_ARTIFACT = "live-adapter-gate-evidence.v1.json"
ENVIRONMENT_CONTRACT_PROGRAM_ID = "GP-4.3"
ENVIRONMENT_CONTRACT_ARTIFACT_KIND = "live_adapter_gate_environment_contract"
ENVIRONMENT_CONTRACT_SCHEMA_NAME = "live-adapter-gate-environment.schema.v1.json"
ENVIRONMENT_CONTRACT_ARTIFACT = "live-adapter-gate-environment-contract.v1.json"
PROTECTED_ENVIRONMENT_NAME = "ao-kernel-live-adapter-gate"
ENVIRONMENT_CONTRACT_FINDING = "live_gate_protected_environment_not_attested"
REHEARSAL_DECISION_PROGRAM_ID = "GP-4.4"
REHEARSAL_DECISION_ARTIFACT_KIND = "live_adapter_gate_rehearsal_decision"
REHEARSAL_DECISION_SCHEMA_NAME = "live-adapter-gate-rehearsal-decision.schema.v1.json"
REHEARSAL_DECISION_ARTIFACT = "live-adapter-gate-rehearsal-decision.v1.json"
REHEARSAL_DECISION_FINDING = "live_gate_rehearsal_blocked_missing_protected_prerequisites"
ATTESTATION_PROGRAM_ID = "GPP-2d"
ATTESTATION_ARTIFACT_KIND = "live_adapter_gate_prerequisite_attestation"
ATTESTATION_ARTIFACT = "live-adapter-gate-attestation.v1.json"
REQUIRED_SECRET_ID = "AO_CLAUDE_CODE_CLI_AUTH"


CheckStatus = Literal["pass", "blocked", "skipped"]
OverallStatus = Literal["blocked"]
AttestationStatus = Literal["ready", "blocked"]
EvidenceRequirementStatus = Literal["present", "blocked"]
PrerequisiteStatus = Literal["blocked", "not_attested"]


class LiveAdapterGateTrigger(TypedDict):
    """Dispatch metadata captured by the gate contract report."""

    event_name: str
    target_ref: str
    head_sha: str
    requested_by: str
    reason: str


class LiveAdapterGateCheck(TypedDict):
    """Single deterministic check emitted by the GP-4.1 skeleton."""

    name: str
    status: CheckStatus
    finding_code: str | None
    detail: str


class LiveAdapterGateReport(TypedDict):
    """Machine-readable GP-4.1 live adapter gate report."""

    schema_version: str
    program_id: str
    gate_id: str
    adapter_id: str
    support_tier: str
    overall_status: OverallStatus
    finding_code: str
    generated_at: str
    live_execution_attempted: bool
    support_widening: bool
    trigger: LiveAdapterGateTrigger
    checks: list[LiveAdapterGateCheck]
    findings: list[str]


class LiveAdapterGateSourceReport(TypedDict):
    """Digest pointer to the underlying gate contract report."""

    path: str
    schema_version: str
    sha256: str


class LiveAdapterGateEvidenceRequirement(TypedDict):
    """Single evidence slot required before support can be widened."""

    requirement_id: str
    artifact_path: str
    status: EvidenceRequirementStatus
    finding_code: str | None
    required_for_promotion: bool
    detail: str


class LiveAdapterGatePromotionDecision(TypedDict):
    """Fail-closed promotion decision encoded in the evidence artifact."""

    support_widening_allowed: bool
    production_certified: bool
    reason: str
    required_before_widening: list[str]


class LiveAdapterGateEvidenceArtifact(TypedDict):
    """Machine-readable GP-4.2 evidence artifact contract."""

    schema_version: str
    artifact_kind: str
    program_id: str
    gate_id: str
    adapter_id: str
    support_tier: str
    overall_status: OverallStatus
    finding_code: str
    generated_at: str
    live_execution_attempted: bool
    support_widening: bool
    trigger: LiveAdapterGateTrigger
    source_report: LiveAdapterGateSourceReport
    evidence_requirements: list[LiveAdapterGateEvidenceRequirement]
    promotion_decision: LiveAdapterGatePromotionDecision
    findings: list[str]


class LiveAdapterGateProtectedEnvironment(TypedDict):
    """Protected GitHub environment requirements for the future live gate."""

    name: str
    required: bool
    required_reviewers: bool
    prevent_self_review: bool
    allowed_refs: list[str]
    detail: str


class LiveAdapterGateTriggerPolicy(TypedDict):
    """Fork-safe trigger policy for future live execution."""

    allowed_events: list[str]
    forbidden_events: list[str]
    allowed_refs: list[str]
    forks_allowed: bool
    pull_request_secrets_allowed: bool
    detail: str


class LiveAdapterGateSecretRequirement(TypedDict):
    """Named secret requirement without storing a secret value."""

    secret_id: str
    required: bool
    exposure: str
    secret_value_committed: bool
    purpose: str


class LiveAdapterGateEnvironmentContract(TypedDict):
    """Machine-readable GP-4.3 protected environment contract."""

    schema_version: str
    artifact_kind: str
    program_id: str
    gate_id: str
    adapter_id: str
    support_tier: str
    overall_status: OverallStatus
    finding_code: str
    generated_at: str
    protected_environment: LiveAdapterGateProtectedEnvironment
    trigger_policy: LiveAdapterGateTriggerPolicy
    required_secrets: list[LiveAdapterGateSecretRequirement]
    live_execution_allowed: bool
    support_widening: bool
    promotion_blockers: list[str]
    findings: list[str]


class LiveAdapterGatePrerequisiteStatus(TypedDict):
    """Single prerequisite for a future protected live rehearsal."""

    prerequisite_id: str
    status: PrerequisiteStatus
    finding_code: str
    detail: str


class LiveAdapterGateRehearsalPromotionDecision(TypedDict):
    """Fail-closed GP-4.4 promotion decision."""

    support_widening_allowed: bool
    production_certified: bool
    next_gate: str
    reason: str


class LiveAdapterGateRehearsalDecision(TypedDict):
    """Machine-readable GP-4.4 protected live rehearsal decision."""

    schema_version: str
    artifact_kind: str
    program_id: str
    gate_id: str
    adapter_id: str
    support_tier: str
    overall_status: OverallStatus
    decision: str
    finding_code: str
    generated_at: str
    live_rehearsal_attempted: bool
    live_execution_allowed: bool
    support_widening: bool
    prerequisite_status: list[LiveAdapterGatePrerequisiteStatus]
    promotion_decision: LiveAdapterGateRehearsalPromotionDecision
    findings: list[str]


class LiveAdapterGateAttestationCheck(TypedDict):
    """Single metadata-only prerequisite attestation check."""

    name: str
    status: CheckStatus
    finding_code: str | None
    detail: str


class LiveAdapterGateAttestationArtifact(TypedDict):
    """Metadata-only protected live-adapter prerequisite attestation."""

    schema_version: str
    artifact_kind: str
    program_id: str
    gate_id: str
    adapter_id: str
    support_tier: str
    overall_status: AttestationStatus
    finding_code: str | None
    generated_at: str
    environment_name: str
    required_secret_id: str
    equivalent_release_gate_approved: bool
    runtime_binding_allowed: bool
    live_execution_allowed: bool
    support_widening: bool
    checks: list[LiveAdapterGateAttestationCheck]
    findings: list[str]


def utc_timestamp() -> str:
    """Return a stable UTC timestamp representation for reports."""

    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def build_live_adapter_gate_report(
    *,
    target_ref: str = "main",
    reason: str = "",
    requested_by: str = "",
    event_name: str = "workflow_dispatch",
    head_sha: str = "",
    generated_at: str | None = None,
) -> LiveAdapterGateReport:
    """Build the GP-4.1 design-only live adapter gate report.

    ``overall_status`` is deliberately ``blocked`` because this skeleton proves
    that a live gate contract exists, not that the live adapter is certified.
    """

    timestamp = generated_at or utc_timestamp()
    return {
        "schema_version": SCHEMA_VERSION,
        "program_id": PROGRAM_ID,
        "gate_id": GATE_ID,
        "adapter_id": ADAPTER_ID,
        "support_tier": SUPPORT_TIER,
        "overall_status": "blocked",
        "finding_code": BLOCKED_FINDING,
        "generated_at": timestamp,
        "live_execution_attempted": False,
        "support_widening": False,
        "trigger": {
            "event_name": event_name,
            "target_ref": target_ref,
            "head_sha": head_sha,
            "requested_by": requested_by,
            "reason": reason,
        },
        "checks": [
            {
                "name": "dispatch_scope",
                "status": "pass",
                "finding_code": None,
                "detail": "Workflow surface is manual workflow_dispatch only.",
            },
            {
                "name": "live_execution",
                "status": "blocked",
                "finding_code": BLOCKED_FINDING,
                "detail": "GP-4.1 skeleton does not execute live external adapters.",
            },
            {
                "name": "secret_access",
                "status": "skipped",
                "finding_code": "live_gate_secrets_not_configured",
                "detail": "No repository or environment secret is read by this skeleton.",
            },
            {
                "name": "support_boundary",
                "status": "pass",
                "finding_code": None,
                "detail": "No support widening is granted by this report.",
            },
        ],
        "findings": [BLOCKED_FINDING],
    }


def _canonical_json_bytes(payload: object) -> bytes:
    """Return deterministic bytes for report digests."""

    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")


def live_adapter_gate_report_sha256(report: LiveAdapterGateReport) -> str:
    """Hash the logical contract report payload, independent of pretty-printing."""

    return hashlib.sha256(_canonical_json_bytes(report)).hexdigest()


def build_live_adapter_gate_evidence_artifact(
    report: LiveAdapterGateReport,
    *,
    contract_report_path: str = CONTRACT_REPORT_ARTIFACT,
    generated_at: str | None = None,
) -> LiveAdapterGateEvidenceArtifact:
    """Build the GP-4.2 evidence artifact wrapper.

    The artifact is intentionally blocked until the protected live preflight and
    governed workflow-smoke reports are attached by a later slice.
    """

    timestamp = generated_at or report["generated_at"]
    preflight_finding = "live_gate_preflight_not_collected"
    workflow_finding = "live_gate_workflow_smoke_not_collected"
    environment_finding = "live_gate_protected_environment_not_attested"
    findings = [BLOCKED_FINDING, preflight_finding, workflow_finding, environment_finding]
    return {
        "schema_version": SCHEMA_VERSION,
        "artifact_kind": EVIDENCE_ARTIFACT_KIND,
        "program_id": EVIDENCE_PROGRAM_ID,
        "gate_id": report["gate_id"],
        "adapter_id": report["adapter_id"],
        "support_tier": report["support_tier"],
        "overall_status": report["overall_status"],
        "finding_code": report["finding_code"],
        "generated_at": timestamp,
        "live_execution_attempted": report["live_execution_attempted"],
        "support_widening": report["support_widening"],
        "trigger": report["trigger"],
        "source_report": {
            "path": contract_report_path,
            "schema_version": report["schema_version"],
            "sha256": live_adapter_gate_report_sha256(report),
        },
        "evidence_requirements": [
            {
                "requirement_id": "gate_contract_report",
                "artifact_path": contract_report_path,
                "status": "present",
                "finding_code": None,
                "required_for_promotion": True,
                "detail": "Design-only gate contract report is attached.",
            },
            {
                "requirement_id": "preflight_report",
                "artifact_path": "claude-code-cli-preflight.v1.json",
                "status": "blocked",
                "finding_code": preflight_finding,
                "required_for_promotion": True,
                "detail": "Protected live preflight report is not collected by GP-4.2.",
            },
            {
                "requirement_id": "governed_workflow_smoke_report",
                "artifact_path": "claude-code-cli-workflow-smoke.v1.json",
                "status": "blocked",
                "finding_code": workflow_finding,
                "required_for_promotion": True,
                "detail": "Protected governed workflow-smoke report is not collected by GP-4.2.",
            },
            {
                "requirement_id": "protected_environment_attestation",
                "artifact_path": "live-adapter-gate-environment.v1.json",
                "status": "blocked",
                "finding_code": environment_finding,
                "required_for_promotion": True,
                "detail": "Protected GitHub environment and project-owned identity are not attested by GP-4.2.",
            },
        ],
        "promotion_decision": {
            "support_widening_allowed": False,
            "production_certified": False,
            "reason": (
                "The manual gate emitted schema-valid blocked evidence, but no protected live "
                "adapter preflight or governed workflow-smoke evidence exists."
            ),
            "required_before_widening": [
                "project_owned_identity",
                "protected_environment",
                "preflight_report",
                "governed_workflow_smoke_report",
                "docs_parity",
            ],
        },
        "findings": findings,
    }


def build_live_adapter_gate_environment_contract(
    *,
    generated_at: str | None = None,
) -> LiveAdapterGateEnvironmentContract:
    """Build the GP-4.3 protected environment / secret contract artifact.

    The contract names the required GitHub environment and secret handles, but
    it deliberately does not prove that the environment exists and never stores
    a secret value. A later GP-4 slice must attach a real attestation before live
    execution or support widening can be considered.
    """

    return {
        "schema_version": SCHEMA_VERSION,
        "artifact_kind": ENVIRONMENT_CONTRACT_ARTIFACT_KIND,
        "program_id": ENVIRONMENT_CONTRACT_PROGRAM_ID,
        "gate_id": GATE_ID,
        "adapter_id": ADAPTER_ID,
        "support_tier": SUPPORT_TIER,
        "overall_status": "blocked",
        "finding_code": ENVIRONMENT_CONTRACT_FINDING,
        "generated_at": generated_at or utc_timestamp(),
        "protected_environment": {
            "name": PROTECTED_ENVIRONMENT_NAME,
            "required": True,
            "required_reviewers": True,
            "prevent_self_review": True,
            "allowed_refs": ["main"],
            "detail": (
                "Future live execution must run through this protected GitHub "
                "environment or an explicitly approved release-gate equivalent."
            ),
        },
        "trigger_policy": {
            "allowed_events": ["workflow_dispatch", "schedule"],
            "forbidden_events": ["pull_request", "pull_request_target", "push"],
            "allowed_refs": ["main"],
            "forks_allowed": False,
            "pull_request_secrets_allowed": False,
            "detail": (
                "Project-owned live credentials must never be exposed to fork or "
                "untrusted pull_request contexts."
            ),
        },
        "required_secrets": [
            {
                "secret_id": "AO_CLAUDE_CODE_CLI_AUTH",
                "required": True,
                "exposure": "github_environment_secret",
                "secret_value_committed": False,
                "purpose": (
                    "Project-owned Claude Code CLI auth material or equivalent "
                    "non-API-key credential required for protected live rehearsal."
                ),
            }
        ],
        "live_execution_allowed": False,
        "support_widening": False,
        "promotion_blockers": [
            "github_environment_not_attested",
            "project_owned_credential_not_verified",
            "live_preflight_not_collected",
            "governed_workflow_smoke_not_collected",
        ],
        "findings": [ENVIRONMENT_CONTRACT_FINDING],
    }


def build_live_adapter_gate_rehearsal_decision(
    *,
    generated_at: str | None = None,
) -> LiveAdapterGateRehearsalDecision:
    """Build the GP-4.4 protected live rehearsal decision artifact.

    The current decision is fail-closed: no protected environment or
    project-owned credential is attested, so no live adapter call is attempted
    and support remains unchanged.
    """

    return {
        "schema_version": SCHEMA_VERSION,
        "artifact_kind": REHEARSAL_DECISION_ARTIFACT_KIND,
        "program_id": REHEARSAL_DECISION_PROGRAM_ID,
        "gate_id": GATE_ID,
        "adapter_id": ADAPTER_ID,
        "support_tier": SUPPORT_TIER,
        "overall_status": "blocked",
        "decision": "blocked_no_rehearsal",
        "finding_code": REHEARSAL_DECISION_FINDING,
        "generated_at": generated_at or utc_timestamp(),
        "live_rehearsal_attempted": False,
        "live_execution_allowed": False,
        "support_widening": False,
        "prerequisite_status": [
            {
                "prerequisite_id": "protected_environment_attestation",
                "status": "not_attested",
                "finding_code": "live_gate_protected_environment_not_attested",
                "detail": (
                    f"Required GitHub environment {PROTECTED_ENVIRONMENT_NAME!r} "
                    "is not attested by this repository lane."
                ),
            },
            {
                "prerequisite_id": "project_owned_credential",
                "status": "not_attested",
                "finding_code": "live_gate_project_owned_credential_not_attested",
                "detail": (
                    "Required project-owned Claude Code CLI credential handle "
                    "AO_CLAUDE_CODE_CLI_AUTH is not attested by this lane."
                ),
            },
            {
                "prerequisite_id": "protected_live_preflight",
                "status": "blocked",
                "finding_code": "live_gate_preflight_not_collected",
                "detail": "Protected live preflight cannot run before environment and credential attestation.",
            },
            {
                "prerequisite_id": "governed_workflow_smoke",
                "status": "blocked",
                "finding_code": "live_gate_workflow_smoke_not_collected",
                "detail": "Governed workflow smoke cannot run before protected live preflight passes.",
            },
        ],
        "promotion_decision": {
            "support_widening_allowed": False,
            "production_certified": False,
            "next_gate": "GP-4.5",
            "reason": (
                "GP-4.4 records an explicit blocked decision because protected "
                "live rehearsal prerequisites are not attested."
            ),
        },
        "findings": [REHEARSAL_DECISION_FINDING],
    }


def _status(
    condition: bool,
    *,
    finding_code: str | None,
    pass_detail: str,
    blocked_detail: str,
) -> LiveAdapterGateAttestationCheck:
    """Build one fail-closed attestation check."""

    if condition:
        return {
            "name": "",
            "status": "pass",
            "finding_code": None,
            "detail": pass_detail,
        }
    return {
        "name": "",
        "status": "blocked",
        "finding_code": finding_code,
        "detail": blocked_detail,
    }


def _as_dict(payload: object) -> dict[str, Any]:
    """Return ``payload`` as a dictionary or an empty dictionary."""

    return payload if isinstance(payload, dict) else {}


def _as_list(payload: object) -> list[Any]:
    """Return ``payload`` as a list or an empty list."""

    return payload if isinstance(payload, list) else []


def _named_items(payload: object, *, container_key: str | None = None) -> list[dict[str, Any]]:
    """Extract named dictionaries from a GitHub API payload."""

    if container_key and isinstance(payload, dict):
        payload = payload.get(container_key, [])
    return [item for item in _as_list(payload) if isinstance(item, dict)]


def _branch_policy_names(branch_policy_payload: object) -> list[str]:
    """Return deployment branch policy names from GitHub API output."""

    return sorted(
        item["name"]
        for item in _named_items(branch_policy_payload, container_key="branch_policies")
        if isinstance(item.get("name"), str)
    )


def _secret_names(secret_payload: object) -> list[str]:
    """Return secret names without reading secret values."""

    return sorted(item["name"] for item in _named_items(secret_payload) if isinstance(item.get("name"), str))


def _collaborator_logins(collaborator_payload: object) -> list[str]:
    """Return visible collaborator logins from GitHub API output."""

    return sorted(item["login"] for item in _named_items(collaborator_payload) if isinstance(item.get("login"), str))


def _required_reviewer_rules(environment_payload: object) -> list[dict[str, Any]]:
    """Return required-reviewer environment protection rules."""

    environment = _as_dict(environment_payload)
    return [
        rule
        for rule in _as_list(environment.get("protection_rules", []))
        if isinstance(rule, dict) and rule.get("type") == "required_reviewers"
    ]


def _has_branch_policy_rule(environment_payload: object) -> bool:
    """Return whether the environment has a branch-policy protection rule."""

    environment = _as_dict(environment_payload)
    return any(
        isinstance(rule, dict) and rule.get("type") == "branch_policy"
        for rule in _as_list(environment.get("protection_rules", []))
    )


def build_live_adapter_gate_attestation(
    *,
    environment_payload: object,
    branch_policy_payload: object,
    secret_payload: object,
    collaborator_payload: object,
    environment_name: str = PROTECTED_ENVIRONMENT_NAME,
    required_secret_id: str = REQUIRED_SECRET_ID,
    actor_login: str = "",
    equivalent_release_gate_approved: bool = False,
    generated_at: str | None = None,
) -> LiveAdapterGateAttestationArtifact:
    """Build a metadata-only protected live-adapter prerequisite attestation.

    This helper consumes GitHub API metadata only. It never accepts or emits
    secret values and it never grants support widening. ``runtime_binding`` can
    only become allowed when all prerequisites are metadata-attested; live
    execution remains a separate downstream gate.
    """

    environment = _as_dict(environment_payload)
    environment_exists = environment.get("name") == environment_name
    admin_bypass_disabled = environment_exists and environment.get("can_admins_bypass") is False
    deployment_policy = _as_dict(environment.get("deployment_branch_policy"))
    custom_branch_policy = deployment_policy.get("custom_branch_policies") is True
    branch_policy_names = _branch_policy_names(branch_policy_payload)
    main_only_branch_policy = branch_policy_names == ["main"]
    branch_policy_ok = _has_branch_policy_rule(environment) and custom_branch_policy and main_only_branch_policy

    secret_present = required_secret_id in _secret_names(secret_payload)
    reviewer_rules = _required_reviewer_rules(environment)
    reviewer_gate_configured = bool(reviewer_rules)
    prevent_self_review = any(rule.get("prevent_self_review") is True for rule in reviewer_rules)
    collaborators = _collaborator_logins(collaborator_payload)
    non_self_collaborators = [login for login in collaborators if not actor_login or login != actor_login]
    non_self_reviewer_possible = len(non_self_collaborators) >= 1
    reviewer_gate_ok = (reviewer_gate_configured and prevent_self_review and non_self_reviewer_possible) or (
        equivalent_release_gate_approved
    )

    check_specs = [
        (
            "protected_environment",
            environment_exists,
            "live_gate_environment_missing",
            f"GitHub environment {environment_name!r} exists.",
            f"GitHub environment {environment_name!r} is missing.",
        ),
        (
            "admin_bypass",
            admin_bypass_disabled,
            "live_gate_admin_bypass_enabled",
            "Environment admin bypass is disabled.",
            "Environment admin bypass is not disabled.",
        ),
        (
            "deployment_branch_policy",
            branch_policy_ok,
            "live_gate_branch_policy_not_main_only",
            "Environment deployment branch policy is restricted to main.",
            f"Environment deployment branch policy is not restricted to main; observed={branch_policy_names!r}.",
        ),
        (
            "credential_handle",
            secret_present,
            "live_gate_credential_handle_missing",
            f"Environment secret handle {required_secret_id!r} is present by name.",
            f"Environment secret handle {required_secret_id!r} is missing.",
        ),
        (
            "reviewer_gate",
            reviewer_gate_ok,
            "live_gate_reviewer_gate_missing",
            "Reviewer protection or an explicitly approved equivalent release gate is present.",
            "Required reviewer protection is missing and no equivalent release gate is approved.",
        ),
        (
            "support_boundary",
            True,
            None,
            "Attestation never widens support or certifies production.",
            "",
        ),
    ]
    checks: list[LiveAdapterGateAttestationCheck] = []
    for name, condition, finding_code, pass_detail, blocked_detail in check_specs:
        check = _status(
            condition,
            finding_code=finding_code,
            pass_detail=pass_detail,
            blocked_detail=blocked_detail,
        )
        check["name"] = name
        checks.append(check)

    findings = [check["finding_code"] for check in checks if check["finding_code"]]
    overall_status: AttestationStatus = "ready" if not findings else "blocked"
    return {
        "schema_version": SCHEMA_VERSION,
        "artifact_kind": ATTESTATION_ARTIFACT_KIND,
        "program_id": ATTESTATION_PROGRAM_ID,
        "gate_id": GATE_ID,
        "adapter_id": ADAPTER_ID,
        "support_tier": SUPPORT_TIER,
        "overall_status": overall_status,
        "finding_code": None if overall_status == "ready" else findings[0],
        "generated_at": generated_at or utc_timestamp(),
        "environment_name": environment_name,
        "required_secret_id": required_secret_id,
        "equivalent_release_gate_approved": equivalent_release_gate_approved,
        "runtime_binding_allowed": overall_status == "ready",
        "live_execution_allowed": False,
        "support_widening": False,
        "checks": checks,
        "findings": findings,
    }


def load_live_adapter_gate_evidence_schema() -> dict[str, Any]:
    """Load the bundled GP-4.2 evidence artifact JSON Schema."""

    schema_path = resources.files("ao_kernel.defaults.schemas").joinpath(EVIDENCE_SCHEMA_NAME)
    return cast(dict[str, Any], json.loads(schema_path.read_text(encoding="utf-8")))


def load_live_adapter_gate_environment_schema() -> dict[str, Any]:
    """Load the bundled GP-4.3 protected environment contract JSON Schema."""

    schema_path = resources.files("ao_kernel.defaults.schemas").joinpath(ENVIRONMENT_CONTRACT_SCHEMA_NAME)
    return cast(dict[str, Any], json.loads(schema_path.read_text(encoding="utf-8")))


def load_live_adapter_gate_rehearsal_decision_schema() -> dict[str, Any]:
    """Load the bundled GP-4.4 protected live rehearsal decision JSON Schema."""

    schema_path = resources.files("ao_kernel.defaults.schemas").joinpath(REHEARSAL_DECISION_SCHEMA_NAME)
    return cast(dict[str, Any], json.loads(schema_path.read_text(encoding="utf-8")))


def validate_live_adapter_gate_evidence_artifact(artifact: object) -> None:
    """Validate a GP-4.2 evidence artifact against the bundled schema."""

    Draft202012Validator(load_live_adapter_gate_evidence_schema()).validate(artifact)


def validate_live_adapter_gate_environment_contract(contract: object) -> None:
    """Validate a GP-4.3 protected environment contract against the bundled schema."""

    Draft202012Validator(load_live_adapter_gate_environment_schema()).validate(contract)


def validate_live_adapter_gate_rehearsal_decision(decision: object) -> None:
    """Validate a GP-4.4 protected live rehearsal decision against the bundled schema."""

    Draft202012Validator(load_live_adapter_gate_rehearsal_decision_schema()).validate(decision)


def write_live_adapter_gate_report(path: Path, report: LiveAdapterGateReport) -> None:
    """Write a canonical JSON report to ``path``."""

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_live_adapter_gate_evidence_artifact(path: Path, artifact: LiveAdapterGateEvidenceArtifact) -> None:
    """Write a canonical GP-4.2 evidence artifact to ``path``."""

    validate_live_adapter_gate_evidence_artifact(artifact)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(artifact, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_live_adapter_gate_environment_contract(path: Path, contract: LiveAdapterGateEnvironmentContract) -> None:
    """Write a canonical GP-4.3 protected environment contract to ``path``."""

    validate_live_adapter_gate_environment_contract(contract)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(contract, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_live_adapter_gate_rehearsal_decision(path: Path, decision: LiveAdapterGateRehearsalDecision) -> None:
    """Write a canonical GP-4.4 protected live rehearsal decision to ``path``."""

    validate_live_adapter_gate_rehearsal_decision(decision)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(decision, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_live_adapter_gate_attestation(path: Path, artifact: LiveAdapterGateAttestationArtifact) -> None:
    """Write a metadata-only live-adapter prerequisite attestation."""

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(artifact, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def render_live_adapter_gate_text(report: LiveAdapterGateReport) -> str:
    """Render a concise operator-facing summary for logs."""

    lines = [
        f"program_id: {report['program_id']}",
        f"gate_id: {report['gate_id']}",
        f"adapter_id: {report['adapter_id']}",
        f"overall_status: {report['overall_status']}",
        f"finding_code: {report['finding_code']}",
        f"live_execution_attempted: {str(report['live_execution_attempted']).lower()}",
        f"support_widening: {str(report['support_widening']).lower()}",
        "checks:",
    ]
    for check in report["checks"]:
        suffix = f" ({check['finding_code']})" if check["finding_code"] else ""
        lines.append(f"- {check['name']}: {check['status']}{suffix}")
    return "\n".join(lines)


def render_live_adapter_gate_attestation_text(artifact: LiveAdapterGateAttestationArtifact) -> str:
    """Render a concise operator-facing attestation summary."""

    lines = [
        f"program_id: {artifact['program_id']}",
        f"gate_id: {artifact['gate_id']}",
        f"adapter_id: {artifact['adapter_id']}",
        f"overall_status: {artifact['overall_status']}",
        f"finding_code: {artifact['finding_code'] or 'none'}",
        f"runtime_binding_allowed: {str(artifact['runtime_binding_allowed']).lower()}",
        f"live_execution_allowed: {str(artifact['live_execution_allowed']).lower()}",
        f"support_widening: {str(artifact['support_widening']).lower()}",
        "checks:",
    ]
    for check in artifact["checks"]:
        suffix = f" ({check['finding_code']})" if check["finding_code"] else ""
        lines.append(f"- {check['name']}: {check['status']}{suffix}")
    return "\n".join(lines)
