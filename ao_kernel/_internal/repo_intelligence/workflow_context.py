"""Explicit repo-intelligence workflow context resolver.

This module composes product onboarding and explicit handoff validation into a
single read-only workflow context contract. It returns metadata and a visible
handoff pointer; it does not inject prompt context, write artifacts, expose MCP
tools, or call adapters.
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

from ao_kernel._internal.repo_intelligence.product_onboarding import (
    validate_repo_intelligence_product_onboarding,
)
from ao_kernel._internal.repo_intelligence.workflow_opt_in import validate_repo_intelligence_workflow_opt_in

JsonDict = dict[str, Any]

SCHEMA_VERSION = "1"
ARTIFACT_KIND = "repo_intelligence_explicit_workflow_context"
SUPPORT_TIER = "beta_explicit_read_only_workflow_context"
MODE = "visible_operator_handoff"
CONSUMER = "workflow_runtime"

_WORKFLOW_CONTEXT_FALSE_FIELDS = {
    "default_enabled": "workflow_context_default_enabled_not_false",
    "automatic_prompt_injection": "workflow_context_automatic_prompt_injection_not_false",
    "context_compiler_auto_feed": "workflow_context_context_compiler_auto_feed_not_false",
    "write_context_artifacts": "workflow_context_write_context_artifacts_not_false",
}

_SAFETY_FALSE_FIELDS = {
    "hidden_prompt_injection": "safety_hidden_prompt_injection_not_false",
    "mcp_tool_exposure": "safety_mcp_tool_exposure_not_false",
    "root_export": "safety_root_export_not_false",
    "context_compiler_auto_feed": "safety_context_compiler_auto_feed_not_false",
    "vector_writes": "safety_vector_writes_not_false",
    "artifact_writes": "safety_artifact_writes_not_false",
    "live_adapter_execution": "safety_live_adapter_execution_not_false",
    "support_widening": "safety_support_widening_not_false",
    "production_platform_claim": "safety_production_platform_claim_not_false",
}


def resolve_repo_intelligence_workflow_context(
    config: Mapping[str, Any] | None,
    *,
    project_root: Path,
) -> JsonDict:
    """Resolve explicit repo-intelligence context for a workflow.

    Disabled or absent config is a no-op. Enabled config must compose an
    accepted product onboarding contract with an accepted explicit handoff. The
    returned context is a pointer and metadata bundle only; callers must provide
    the Markdown as visible input and must not auto-feed it into prompts.
    """
    if not config or config.get("enabled") is not True:
        return {
            "status": "disabled",
            "enabled": False,
            "decision": "repo_intelligence_workflow_context_not_enabled",
        }

    findings: list[str] = []
    if _string(config.get("schema_version")) != SCHEMA_VERSION:
        findings.append("schema_version_invalid")
    if _string(config.get("artifact_kind")) != ARTIFACT_KIND:
        findings.append("artifact_kind_invalid")
    if _string(config.get("support_tier")) != SUPPORT_TIER:
        findings.append("support_tier_not_beta_explicit_read_only_workflow_context")

    product_onboarding_config = _mapping(config.get("product_onboarding"))
    workflow_opt_in_config = _mapping(config.get("workflow_opt_in"))
    workflow_context = _mapping(config.get("workflow_context"))
    safety = _mapping(config.get("safety"))

    if not product_onboarding_config:
        findings.append("product_onboarding_missing")
    if not workflow_opt_in_config:
        findings.append("workflow_opt_in_missing")
    if not workflow_context:
        findings.append("workflow_context_missing")
    if not safety:
        findings.append("safety_missing")

    if _string(workflow_context.get("mode")) != MODE:
        findings.append("workflow_context_mode_not_visible_operator_handoff")
    if _string(workflow_context.get("consumer")) != CONSUMER:
        findings.append("workflow_context_consumer_not_workflow_runtime")
    if workflow_context.get("operator_visible") is not True:
        findings.append("workflow_context_operator_visible_not_true")
    if workflow_context.get("requires_behavior_tests") is not True:
        findings.append("workflow_context_requires_behavior_tests_not_true")
    _require_false_fields(workflow_context, _WORKFLOW_CONTEXT_FALSE_FIELDS, findings)
    _require_false_fields(safety, _SAFETY_FALSE_FIELDS, findings)

    product_result = validate_repo_intelligence_product_onboarding(product_onboarding_config)
    opt_in_result = validate_repo_intelligence_workflow_opt_in(workflow_opt_in_config, project_root=project_root)

    if product_result.get("status") != "accepted":
        findings.extend(_nested_findings("product_onboarding", product_result))
    if opt_in_result.get("status") != "accepted":
        findings.extend(_nested_findings("workflow_opt_in", opt_in_result))

    if findings:
        return {
            "status": "blocked",
            "enabled": True,
            "decision": "blocked_repo_intelligence_workflow_context",
            "findings": sorted(set(findings)),
            "product_onboarding": _summary(product_result),
            "workflow_opt_in": _summary(opt_in_result),
            "support_widening": False,
            "production_platform_claim": False,
            "live_adapter_execution_allowed": False,
        }

    handoff = _mapping(opt_in_result.get("handoff"))
    return {
        "status": "accepted",
        "enabled": True,
        "decision": "accepted_repo_intelligence_workflow_context",
        "support_tier": SUPPORT_TIER,
        "context": {
            "mode": MODE,
            "consumer": CONSUMER,
            "handoff_path": handoff.get("path", ""),
            "markdown_sha256": handoff.get("markdown_sha256", ""),
            "handoff_support_tier": handoff.get("support_tier", ""),
            "operator_visible": True,
            "automatic_prompt_injection": False,
            "context_compiler_auto_feed": False,
            "write_context_artifacts": False,
        },
        "source_metadata": opt_in_result.get("source_metadata", {}),
        "product_onboarding": {
            "decision": product_result["decision"],
            "required_end_user_steps": product_result["required_end_user_steps"],
            "optional_repo_config_path": product_result["optional_repo_config_path"],
            "operator_owned_infrastructure": product_result["operator_owned_infrastructure"],
        },
        "workflow_opt_in": {
            "decision": opt_in_result["decision"],
            "handoff": opt_in_result["handoff"],
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


def _nested_findings(prefix: str, result: Mapping[str, Any]) -> list[str]:
    findings = result.get("findings")
    if isinstance(findings, list) and findings:
        return [f"{prefix}_{_string(item)}" for item in findings]
    decision = _string(result.get("decision")) or "not_accepted"
    return [f"{prefix}_{decision}"]


def _summary(result: Mapping[str, Any]) -> JsonDict:
    summary: JsonDict = {
        "status": result.get("status", "unknown"),
        "decision": result.get("decision", "unknown"),
    }
    findings = result.get("findings")
    if isinstance(findings, list):
        summary["findings"] = findings
    return summary


def _mapping(value: Any) -> Mapping[str, Any]:
    if isinstance(value, Mapping):
        return value
    return {}


def _string(value: Any) -> str:
    if isinstance(value, str):
        return value
    return ""
