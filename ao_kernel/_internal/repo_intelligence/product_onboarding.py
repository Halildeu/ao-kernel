"""Product onboarding guardrails for repo-intelligence workflows.

This module validates the product-facing repo-intelligence onboarding shape.
It does not install GitHub Apps, call GitHub, write repo artifacts, inject
context, expose MCP tools, or bind the live adapter.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

JsonDict = dict[str, Any]

SCHEMA_VERSION = "1"
ARTIFACT_KIND = "repo_intelligence_product_onboarding"
SUPPORT_TIER = "beta_read_only_product_onboarding"
INSTALLATION = "required"
REPOSITORY_SELECTION = "selected_repositories"
PERMISSION_BOUNDARY = "read_only_repo_intelligence"
WORKFLOW_MODE = "read_only"
WORKFLOW_ACTIVATION = "explicit_opt_in"

APPROVED_REPO_CONFIG_PATHS = frozenset(
    {
        ".ao/config.yml",
        ".ao/config.yaml",
        ".ao/repo-intelligence.yml",
        ".ao/repo-intelligence.yaml",
        ".ao/repo-intelligence.json",
    }
)

_END_USER_INFRA_FALSE_FIELDS = {
    "cloud_run_required": "end_user_cloud_run_required_not_false",
    "vault_required": "end_user_vault_required_not_false",
    "webhook_required": "end_user_webhook_required_not_false",
    "github_app_private_key_required": "end_user_github_app_private_key_required_not_false",
    "release_gate_service_required": "end_user_release_gate_service_required_not_false",
    "deployment_protection_service_required": "end_user_deployment_protection_service_required_not_false",
}

_SAFETY_FALSE_FIELDS = {
    "hidden_prompt_injection": "safety_hidden_prompt_injection_not_false",
    "mcp_tool_exposure": "safety_mcp_tool_exposure_not_false",
    "root_export_required": "safety_root_export_required_not_false",
    "context_compiler_auto_feed": "safety_context_compiler_auto_feed_not_false",
    "implicit_vector_writes": "safety_implicit_vector_writes_not_false",
    "implicit_artifact_writes": "safety_implicit_artifact_writes_not_false",
    "live_adapter_execution": "safety_live_adapter_execution_not_false",
    "support_widening": "safety_support_widening_not_false",
    "production_platform_claim": "safety_production_platform_claim_not_false",
}


def repo_intelligence_product_onboarding_template(
    *,
    repo_config_path: str = ".ao/repo-intelligence.yml",
) -> JsonDict:
    """Return the canonical product onboarding contract.

    The template is intentionally conservative: it enables only the
    read-only repo-intelligence workflow and keeps every hosted-gate,
    live-adapter, implicit-write, support-widening, and production-claim
    switch closed. CLI callers may write this as an explicit local config,
    but it is never a GitHub/Vault/webhook setup instruction.
    """

    if repo_config_path not in APPROVED_REPO_CONFIG_PATHS:
        raise ValueError(
            "repo_config_path must be one of: "
            + ", ".join(sorted(APPROVED_REPO_CONFIG_PATHS))
        )
    return {
        "schema_version": SCHEMA_VERSION,
        "artifact_kind": ARTIFACT_KIND,
        "enabled": True,
        "support_tier": SUPPORT_TIER,
        "setup": {
            "github_app": {
                "installation": INSTALLATION,
                "repository_selection": REPOSITORY_SELECTION,
                "permission_boundary": PERMISSION_BOUNDARY,
            },
            "repo_local_config": {
                "path": repo_config_path,
                "required": False,
            },
            "end_user_infrastructure": {
                field: False for field in _END_USER_INFRA_FALSE_FIELDS
            },
        },
        "workflow": {
            "mode": WORKFLOW_MODE,
            "activation": WORKFLOW_ACTIVATION,
            "default_enabled": False,
            "default_auto_feed": False,
        },
        "safety": {field: False for field in _SAFETY_FALSE_FIELDS},
    }


def validate_repo_intelligence_product_onboarding(config: Mapping[str, Any] | None) -> JsonDict:
    """Validate the repo-intelligence product onboarding contract.

    Disabled or absent config is a no-op. Enabled config is accepted only when
    the product user path is limited to GitHub App installation, explicit
    repository selection, and optional repo-local configuration.
    """
    if not config or config.get("enabled") is not True:
        return {
            "status": "disabled",
            "enabled": False,
            "decision": "repo_intelligence_product_onboarding_not_enabled",
        }

    findings: list[str] = []
    if _string(config.get("schema_version")) != SCHEMA_VERSION:
        findings.append("schema_version_invalid")
    if _string(config.get("artifact_kind")) != ARTIFACT_KIND:
        findings.append("artifact_kind_invalid")
    if _string(config.get("support_tier")) != SUPPORT_TIER:
        findings.append("support_tier_not_beta_read_only_product_onboarding")

    setup = _mapping(config.get("setup"))
    if not setup:
        findings.append("setup_missing")
    github_app = _mapping(setup.get("github_app"))
    repo_local_config = _mapping(setup.get("repo_local_config"))
    end_user_infra = _mapping(setup.get("end_user_infrastructure"))
    workflow = _mapping(config.get("workflow"))
    safety = _mapping(config.get("safety"))

    if not github_app:
        findings.append("github_app_missing")
    if _string(github_app.get("installation")) != INSTALLATION:
        findings.append("github_app_installation_not_required")
    if _string(github_app.get("repository_selection")) != REPOSITORY_SELECTION:
        findings.append("github_app_repository_selection_not_selected_repositories")
    if _string(github_app.get("permission_boundary")) != PERMISSION_BOUNDARY:
        findings.append("github_app_permission_boundary_not_read_only_repo_intelligence")

    if not repo_local_config:
        findings.append("repo_local_config_missing")
    repo_config_path = _string(repo_local_config.get("path"))
    if repo_config_path not in APPROVED_REPO_CONFIG_PATHS:
        findings.append("repo_local_config_path_not_approved")
    if repo_local_config.get("required") is not False:
        findings.append("repo_local_config_required_not_false")

    if not end_user_infra:
        findings.append("end_user_infrastructure_missing")
    _require_false_fields(end_user_infra, _END_USER_INFRA_FALSE_FIELDS, findings)

    if not workflow:
        findings.append("workflow_missing")
    if _string(workflow.get("mode")) != WORKFLOW_MODE:
        findings.append("workflow_mode_not_read_only")
    if _string(workflow.get("activation")) != WORKFLOW_ACTIVATION:
        findings.append("workflow_activation_not_explicit_opt_in")
    if workflow.get("default_enabled") is not False:
        findings.append("workflow_default_enabled_not_false")
    if workflow.get("default_auto_feed") is not False:
        findings.append("workflow_default_auto_feed_not_false")

    if not safety:
        findings.append("safety_missing")
    _require_false_fields(safety, _SAFETY_FALSE_FIELDS, findings)

    if findings:
        return {
            "status": "blocked",
            "enabled": True,
            "decision": "blocked_repo_intelligence_product_onboarding",
            "findings": sorted(set(findings)),
            "support_widening": False,
            "production_platform_claim": False,
            "live_adapter_execution_allowed": False,
        }

    return {
        "status": "accepted",
        "enabled": True,
        "decision": "accepted_repo_intelligence_product_onboarding",
        "support_tier": SUPPORT_TIER,
        "required_end_user_steps": [
            "install_github_app",
            "select_repositories",
        ],
        "optional_repo_config_path": repo_config_path,
        "operator_owned_infrastructure": [
            "deployment_protection_policy_service",
            "ao_release_gate_service",
        ],
        "end_user_infrastructure_required": {field: False for field in _END_USER_INFRA_FALSE_FIELDS},
        "workflow": {
            "mode": WORKFLOW_MODE,
            "activation": WORKFLOW_ACTIVATION,
            "default_enabled": False,
            "default_auto_feed": False,
        },
        "safety": {field: False for field in _SAFETY_FALSE_FIELDS},
        "support_widening": False,
        "production_platform_claim": False,
        "live_adapter_execution_allowed": False,
    }


def _require_false_fields(
    payload: Mapping[str, Any],
    required_false_fields: Mapping[str, str],
    findings: list[str],
) -> None:
    for field, finding in required_false_fields.items():
        if payload.get(field) is not False:
            findings.append(finding)


def _mapping(value: Any) -> Mapping[str, Any]:
    if isinstance(value, Mapping):
        return value
    return {}


def _string(value: Any) -> str:
    if isinstance(value, str):
        return value
    return ""
