"""CI-managed live adapter gate contract helpers.

The GP-4.1 gate is intentionally a skeleton: it emits a machine-readable
contract report but does not execute external live adapters.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal, TypedDict

SCHEMA_VERSION = "1"
PROGRAM_ID = "GP-4.1"
GATE_ID = "ci-managed-live-adapter-gate"
ADAPTER_ID = "claude-code-cli"
SUPPORT_TIER = "Beta (operator-managed)"
BLOCKED_FINDING = "live_gate_not_implemented"


CheckStatus = Literal["pass", "blocked", "skipped"]
OverallStatus = Literal["blocked"]


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


def write_live_adapter_gate_report(path: Path, report: LiveAdapterGateReport) -> None:
    """Write a canonical JSON report to ``path``."""

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")


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
