"""AI output quality gates.

Validates provider output before allowing execution to proceed.
Gates: schema_valid, output_not_empty, consistency_check, regression_check.
"""
from __future__ import annotations

import json
import logging
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ao_kernel._internal.shared.utils import load_policy_validated

# Resource loading delegated to src.shared.resource_loader

logger = logging.getLogger(__name__)

# ── Gate metrics (in-process Counter for observability) ───────────────
# Counts per gate_id × action across the process lifetime.
# Consumed by OTEL export or metrics endpoint when available.
_gate_counters: Counter[str] = Counter()


def get_gate_metrics() -> dict[str, int]:
    """Return a snapshot of gate counters as {gate_id:action: count}."""
    return dict(_gate_counters)


@dataclass
class QualityGateResult:
    passed: bool
    gate_id: str
    action: str  # pass | retry | reject | warn | escalate | suspend
    reason: str


def _load_quality_gate_policy(workspace_root: Path | None = None) -> dict[str, Any]:
    from ao_kernel._internal.shared.resource_loader import load_resource, load_resource_path

    if workspace_root:
        ws_policy = workspace_root / "policies" / "policy_quality_gates.v1.json"
        if ws_policy.exists():
            schema_path = load_resource_path("schemas", "policy-quality-gates.schema.v1.json")
            try:
                if schema_path:
                    validated: dict[str, Any] = load_policy_validated(ws_policy, schema_path)
                    return validated
                parsed: dict[str, Any] = json.loads(ws_policy.read_text(encoding="utf-8"))
                return parsed
            except (ValueError, Exception) as exc:
                import logging
                logging.getLogger("ao_kernel").warning(
                    "quality_gate workspace policy parse failed, falling back: %s", exc
                )

    try:
        bundled: dict[str, Any] = load_resource("policies", "policy_quality_gates.v1.json")
        return bundled
    except (FileNotFoundError, Exception) as exc:
        # Fail-closed: if policy can't load, enable restrictive defaults
        import logging
        logging.getLogger("ao_kernel").warning(
            "quality_gate policy load failed, enabling restrictive defaults: %s", exc
        )
        return {"enabled": True, "gates": {
            "output_not_empty": {"enabled": True, "action": "reject"},
            "schema_valid": {"enabled": True, "action": "reject"},
        }}


def _check_output_not_empty(output: Any, gate_cfg: dict[str, Any]) -> QualityGateResult:
    min_chars = int(gate_cfg.get("min_output_chars", 10))
    if not isinstance(output, dict):
        return QualityGateResult(False, "output_not_empty", str(gate_cfg.get("on_fail", "reject")), "output is not a dict")
    text = str(output.get("text") or output.get("summary") or "")
    if len(text.strip()) < min_chars:
        return QualityGateResult(False, "output_not_empty", str(gate_cfg.get("on_fail", "reject")), f"output too short: {len(text)} chars < {min_chars}")
    return QualityGateResult(True, "output_not_empty", "pass", "")


def _check_schema_valid(output: Any, gate_cfg: dict[str, Any]) -> QualityGateResult:
    if not isinstance(output, dict):
        return QualityGateResult(False, "schema_valid", str(gate_cfg.get("on_fail", "retry")), "output is not a dict")
    return QualityGateResult(True, "schema_valid", "pass", "")


def _check_consistency(output: dict[str, Any], gate_cfg: dict[str, Any], previous_decisions: list[dict[str, Any]] | None) -> QualityGateResult:
    if not previous_decisions:
        return QualityGateResult(True, "consistency_check", "pass", "no_previous_decisions")

    # Check if output contradicts recent decisions
    for pd in previous_decisions[-5:]:  # Check last 5
        if not isinstance(pd, dict):
            continue
        # Simple contradiction: same key, opposite boolean
        if isinstance(pd.get("value"), bool) and isinstance(output.get(pd.get("key", "")), bool):
            if pd["value"] != output.get(pd["key"]):
                return QualityGateResult(False, "consistency_check", str(gate_cfg.get("on_fail", "warn")), f"contradicts decision: {pd.get('key')}")

    return QualityGateResult(True, "consistency_check", "pass", "")


def _check_regression(output: dict[str, Any], gate_cfg: dict[str, Any], previous_decisions: list[dict[str, Any]] | None) -> QualityGateResult:
    if not previous_decisions:
        return QualityGateResult(True, "regression_check", "pass", "no_history")

    # Check if any output value matches an OLD historical value (regression)
    for pd in previous_decisions:
        if not isinstance(pd, dict):
            continue
        history = pd.get("history", [])
        if not isinstance(history, list) or not history:
            continue
        current_key = str(pd.get("key") or "")
        if not current_key or current_key not in output:
            continue
        current_output_val = json.dumps(output.get(current_key), sort_keys=True, ensure_ascii=True)
        for h in history:
            if isinstance(h, dict):
                hist_val = json.dumps(h.get("value"), sort_keys=True, ensure_ascii=True)
                if hist_val == current_output_val:
                    return QualityGateResult(False, "regression_check", str(gate_cfg.get("on_fail", "escalate")), f"regression on key: {current_key}")

    return QualityGateResult(True, "regression_check", "pass", "")


def run_quality_gates(
    *,
    output: Any,
    policy: dict[str, Any] | None = None,
    previous_decisions: list[dict[str, Any]] | None = None,
    workspace_root: Path | None = None,
) -> list[QualityGateResult]:
    """Run all configured quality gates on AI output."""
    if policy is None:
        policy = _load_quality_gate_policy(workspace_root)

    if not policy.get("enabled", True):
        return [QualityGateResult(True, "all", "pass", "gates_disabled")]

    gates = policy.get("gates", {})
    results: list[QualityGateResult] = []

    gate_map = {
        "schema_valid": _check_schema_valid,
        "output_not_empty": _check_output_not_empty,
    }

    for gate_id, checker in gate_map.items():
        gate_cfg = gates.get(gate_id, {})
        if not gate_cfg.get("enabled", True):
            continue
        results.append(checker(output, gate_cfg))

    # Context-dependent gates
    if gates.get("consistency_check", {}).get("enabled", True):
        results.append(_check_consistency(output, gates.get("consistency_check", {}), previous_decisions))
    if gates.get("regression_check", {}).get("enabled", True):
        results.append(_check_regression(output, gates.get("regression_check", {}), previous_decisions))

    # Record gate metrics
    for r in results:
        key = f"{r.gate_id}:{r.action}"
        _gate_counters[key] += 1
        if not r.passed:
            logger.warning("quality_gate FAIL gate=%s action=%s reason=%s", r.gate_id, r.action, r.reason)
        else:
            logger.debug("quality_gate PASS gate=%s", r.gate_id)

    return results


def quality_gate_summary(results: list[QualityGateResult]) -> dict[str, Any]:
    """Summarize quality gate results for evidence recording."""
    return {
        "total_gates": len(results),
        "passed": sum(1 for r in results if r.passed),
        "failed": sum(1 for r in results if not r.passed),
        "actions": {r.gate_id: r.action for r in results},
        "all_passed": all(r.passed for r in results),
        "worst_action": max((r.action for r in results if not r.passed), default="pass"),
        "failures": [{"gate": r.gate_id, "action": r.action, "reason": r.reason} for r in results if not r.passed],
    }
