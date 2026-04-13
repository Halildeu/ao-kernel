"""ao_kernel.governance — Public governance facade for ao-kernel.

Consolidates policy checking, quality gate evaluation, and tool authorization
into a single import path. MCP server and other consumers should use this
module instead of importing directly from src/.

Usage:
    from ao_kernel.governance import check_policy, evaluate_quality
    from ao_kernel.governance import QualityGateResult
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class QualityGateResult:
    """Result of a single quality gate check."""

    passed: bool
    gate_id: str
    action: str  # pass | retry | reject | warn | escalate
    reason: str


def check_policy(
    policy_name: str,
    action: dict[str, Any],
    *,
    workspace: Path | None = None,
) -> dict[str, Any]:
    """Check an action against a named policy.

    Returns dict with: allowed (bool), decision, reason_codes, policy_ref, data.
    Fail-closed: if policy can't be loaded, returns deny.
    """
    from ao_kernel.config import load_with_override, workspace_root as resolve_ws

    if not policy_name:
        return {
            "allowed": False,
            "decision": "deny",
            "reason_codes": ["MISSING_POLICY_NAME"],
        }

    ws = workspace or resolve_ws()

    try:
        policy = load_with_override("policies", policy_name, workspace=ws)
    except FileNotFoundError:
        return {
            "allowed": False,
            "decision": "deny",
            "reason_codes": ["POLICY_NOT_FOUND"],
            "policy_ref": policy_name,
        }

    enabled = policy.get("enabled", True)
    if not enabled:
        return {
            "allowed": True,
            "decision": "allow",
            "reason_codes": ["POLICY_DISABLED"],
            "policy_ref": policy_name,
        }

    # Check rules
    violations = _check_rules(policy, action)
    if violations:
        return {
            "allowed": False,
            "decision": "deny",
            "reason_codes": violations,
            "policy_ref": policy_name,
        }

    return {
        "allowed": True,
        "decision": "allow",
        "reason_codes": ["POLICY_PASSED"],
        "policy_ref": policy_name,
        "data": {"policy_version": policy.get("version", "unknown")},
    }


def _check_rules(policy: dict, action: dict) -> list[str]:
    """Check action against policy rules. Supports multiple policy types.

    Policy types detected by structure:
    - autonomy: has "intents" + "defaults.mode" → check intent authorization
    - tool_calling: has "enabled" + "allowed_tools" → check tool authorization
    - guardrails: has "defaults.enabled" + "providers" → check provider access
    - generic: has "required_fields"/"blocked_values"/"limits" → field checks
    """
    violations = []

    # Type 1: Autonomy policy (intent-based)
    if "intents" in policy and isinstance(policy.get("intents"), dict):
        violations.extend(_check_autonomy(policy, action))

    # Type 2: Tool calling policy
    if "allowed_tools" in policy or "blocked_tools" in policy:
        violations.extend(_check_tool_calling(policy, action))

    # Type 3: Provider guardrails
    if "providers" in policy and isinstance(policy.get("providers"), dict):
        violations.extend(_check_provider_guardrails(policy, action))

    # Type 4: Generic rules (required_fields, blocked_values, limits)
    violations.extend(_check_generic_rules(policy, action))

    return violations


def _check_autonomy(policy: dict, action: dict) -> list[str]:
    """Check autonomy policy — intent authorization and mode enforcement."""
    violations = []
    defaults = policy.get("defaults", {})
    default_mode = defaults.get("mode", "human_review")
    intents = policy.get("intents", {})

    intent = action.get("intent", "")
    mode = action.get("mode", "")

    if intent and intent in intents:
        intent_config = intents[intent]
        allowed_mode = intent_config.get("mode", default_mode)
        if mode and mode != allowed_mode and mode == "full_auto" and allowed_mode == "human_review":
            violations.append(f"AUTONOMY_MODE_DENIED:{intent}:requested={mode},allowed={allowed_mode}")
    elif intent and intent not in intents:
        # Unknown intent — check fail_action
        fail_action = policy.get("fail_action", "block")
        if fail_action == "block":
            violations.append(f"AUTONOMY_UNKNOWN_INTENT:{intent}")

    return violations


def _check_tool_calling(policy: dict, action: dict) -> list[str]:
    """Check tool calling policy — allowed/blocked tools."""
    violations = []

    if not policy.get("enabled", False):
        tool = action.get("tool_name", action.get("tool", ""))
        if tool:
            violations.append(f"TOOL_CALLING_DISABLED:{tool}")
        return violations

    tool = action.get("tool_name", action.get("tool", ""))
    if not tool:
        return violations

    blocked = set(policy.get("blocked_tools", []))
    if tool in blocked:
        violations.append(f"TOOL_BLOCKED:{tool}")

    allowed = set(policy.get("allowed_tools", []))
    if allowed and tool not in allowed:
        violations.append(f"TOOL_NOT_ALLOWED:{tool}")
    elif not allowed:
        violations.append(f"TOOL_NO_ALLOWLIST:{tool}")

    return violations


def _check_provider_guardrails(policy: dict, action: dict) -> list[str]:
    """Check provider guardrails — provider access control."""
    violations = []
    providers = policy.get("providers", {})
    provider_id = action.get("provider_id", action.get("provider", ""))

    if provider_id and provider_id in providers:
        prov = providers[provider_id]
        if isinstance(prov, dict) and not prov.get("enabled", True):
            violations.append(f"PROVIDER_DISABLED:{provider_id}")

        model = action.get("model", "")
        if model and isinstance(prov, dict):
            allow_models = prov.get("allow_models", [])
            if allow_models and model not in allow_models and "*" not in allow_models:
                violations.append(f"MODEL_NOT_ALLOWED:{provider_id}:{model}")

    return violations


def _check_generic_rules(policy: dict, action: dict) -> list[str]:
    """Check generic policy rules — required fields, blocked values, limits."""
    violations = []

    required = policy.get("required_fields", [])
    if isinstance(required, list):
        for field in required:
            if field not in action:
                violations.append(f"MISSING_REQUIRED_FIELD:{field}")

    blocked = policy.get("blocked_values", {})
    if isinstance(blocked, dict):
        for field, blocked_vals in blocked.items():
            if field in action and action[field] in blocked_vals:
                violations.append(f"BLOCKED_VALUE:{field}")

    limits = policy.get("limits", {})
    if isinstance(limits, dict):
        for field, max_val in limits.items():
            if field in action:
                try:
                    if float(action[field]) > float(max_val):
                        violations.append(f"LIMIT_EXCEEDED:{field}")
                except (ValueError, TypeError):
                    pass

    return violations

    return violations


def evaluate_quality(
    output_text: str,
    *,
    workspace_root: Path | None = None,
    previous_decisions: list[dict[str, Any]] | None = None,
) -> list[QualityGateResult]:
    """Evaluate LLM output quality against configured gates.

    Fail-closed: if gates can't be loaded, returns a single FAIL result.
    Never silently allows — unlike the old mcp_server bypass.

    Returns list of QualityGateResult.
    """
    if not output_text:
        return [QualityGateResult(
            passed=False,
            gate_id="output_not_empty",
            action="reject",
            reason="Empty output",
        )]

    try:
        from src.orchestrator.quality_gate import run_quality_gates

        results = run_quality_gates(
            output={"text": output_text},
            workspace_root=workspace_root,
            previous_decisions=previous_decisions,
        )
        # Convert src results to facade results
        return [
            QualityGateResult(
                passed=r.passed,
                gate_id=r.gate_id,
                action=r.action,
                reason=r.reason,
            )
            for r in results
        ]
    except Exception as exc:
        # Fail-CLOSED: if quality gate can't run, DENY (not allow)
        return [QualityGateResult(
            passed=False,
            gate_id="gate_load_error",
            action="reject",
            reason=f"Quality gate failed to load: {str(exc)[:200]}",
        )]


def quality_summary(results: list[QualityGateResult]) -> dict[str, Any]:
    """Summarize quality gate results."""
    all_passed = all(r.passed for r in results)
    return {
        "all_passed": all_passed,
        "total": len(results),
        "passed": sum(1 for r in results if r.passed),
        "failed": sum(1 for r in results if not r.passed),
        "gates": [
            {"gate_id": r.gate_id, "passed": r.passed, "action": r.action, "reason": r.reason}
            for r in results
        ],
    }


__all__ = [
    "check_policy",
    "evaluate_quality",
    "quality_summary",
    "QualityGateResult",
]
