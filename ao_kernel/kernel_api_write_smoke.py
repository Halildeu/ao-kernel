"""Operator smoke helper for PRJ-KERNEL-API write-side contract."""

from __future__ import annotations

import argparse
import json
import shutil
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Literal

from ao_kernel.client import AoKernelClient
from ao_kernel.real_adapter_smoke import SmokeCheck

_WRITE_CONFIRM_VALUE = "I_UNDERSTAND_SIDE_EFFECTS"
_SMOKE_REQUEST_ID = "pb93-kernel-api-write-smoke"


@dataclass(frozen=True)
class KernelApiWriteSmokeReport:
    overall_status: Literal["pass", "blocked"]
    extension_id: str
    workspace_root: str
    checks: tuple[SmokeCheck, ...]
    findings: tuple[str, ...]
    artifacts: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def run_kernel_api_write_smoke(
    *,
    workspace_root: Path | None = None,
    keep_workspace: bool = False,
) -> KernelApiWriteSmokeReport:
    """Run deterministic write-side smoke for PRJ-KERNEL-API actions."""

    managed_temp_root: Path | None = None
    if workspace_root is None:
        managed_temp_root = Path(
            tempfile.mkdtemp(prefix="ao-kernel-kernel-api-write-smoke-")
        )
        resolved_workspace = managed_temp_root
    else:
        resolved_workspace = workspace_root.expanduser().resolve()
        resolved_workspace.mkdir(parents=True, exist_ok=True)

    checks: list[SmokeCheck] = []
    artifacts: list[str] = []
    client = AoKernelClient()

    try:
        dry_run = client.call_action(
            "project_status",
            {"workspace_root": str(resolved_workspace)},
        )
        dry_result = dry_run.get("result", {})
        dry_report_rel = str(dry_result.get("report_path", ""))
        dry_report_abs = resolved_workspace / dry_report_rel if dry_report_rel else None
        dry_run_ok = (
            dry_run.get("ok") is True
            and dry_result.get("dry_run") is True
            and dry_result.get("write_applied") is False
            and (
                dry_report_abs is None
                or not dry_report_abs.exists()
            )
        )
        checks.append(
            SmokeCheck(
                name="project_status_dry_run_default",
                status="pass" if dry_run_ok else "fail",
                detail=(
                    "project_status dry-run default contract smoke gecti"
                    if dry_run_ok
                    else "project_status dry-run default contract ihlali"
                ),
                finding_code=(
                    None if dry_run_ok else "kernel_api_project_status_dry_run_contract_violation"
                ),
                observed={
                    "ok": dry_run.get("ok"),
                    "status": dry_run.get("status"),
                    "dry_run": dry_result.get("dry_run"),
                    "write_applied": dry_result.get("write_applied"),
                    "report_exists": (
                        dry_report_abs.exists() if dry_report_abs is not None else False
                    ),
                },
            )
        )

        confirm_required = client.call_action(
            "project_status",
            {
                "workspace_root": str(resolved_workspace),
                "dry_run": False,
            },
        )
        confirm_required_ok = (
            confirm_required.get("ok") is False
            and confirm_required.get("status") == "BLOCKED"
            and str(confirm_required.get("error", {}).get("code"))
            == "WRITE_CONFIRM_REQUIRED"
        )
        checks.append(
            SmokeCheck(
                name="project_status_write_requires_confirm",
                status="pass" if confirm_required_ok else "fail",
                detail=(
                    "project_status write-side confirm guard smoke gecti"
                    if confirm_required_ok
                    else "project_status write-side confirm guard ihlali"
                ),
                finding_code=(
                    None if confirm_required_ok else "kernel_api_write_confirm_guard_missing"
                ),
                observed={
                    "ok": confirm_required.get("ok"),
                    "status": confirm_required.get("status"),
                    "error_code": confirm_required.get("error", {}).get("code"),
                },
            )
        )

        write_params = {
            "workspace_root": str(resolved_workspace),
            "dry_run": False,
            "confirm_write": _WRITE_CONFIRM_VALUE,
            "request_id": _SMOKE_REQUEST_ID,
        }
        first_write = client.call_action("project_status", write_params)
        first_result = first_write.get("result", {})
        report_rel = str(first_result.get("report_path", ""))
        report_abs = resolved_workspace / report_rel if report_rel else None
        first_write_ok = (
            first_write.get("ok") is True
            and first_result.get("write_applied") is True
            and first_result.get("idempotent") is False
            and report_abs is not None
            and report_abs.exists()
        )
        checks.append(
            SmokeCheck(
                name="project_status_write_apply",
                status="pass" if first_write_ok else "fail",
                detail=(
                    "project_status write-side apply smoke gecti"
                    if first_write_ok
                    else "project_status write-side apply contract ihlali"
                ),
                finding_code=(
                    None if first_write_ok else "kernel_api_project_status_write_apply_failed"
                ),
                observed={
                    "ok": first_write.get("ok"),
                    "status": first_write.get("status"),
                    "write_applied": first_result.get("write_applied"),
                    "idempotent": first_result.get("idempotent"),
                    "report_exists": (
                        report_abs.exists() if report_abs is not None else False
                    ),
                },
            )
        )
        if report_abs is not None and report_abs.exists():
            artifacts.append(str(report_abs))

        second_write = client.call_action("project_status", write_params)
        second_result = second_write.get("result", {})
        second_write_ok = (
            second_write.get("ok") is True
            and second_result.get("write_applied") is False
            and second_result.get("idempotent") is True
        )
        checks.append(
            SmokeCheck(
                name="project_status_write_idempotent",
                status="pass" if second_write_ok else "fail",
                detail=(
                    "project_status idempotency smoke gecti"
                    if second_write_ok
                    else "project_status idempotency contract ihlali"
                ),
                finding_code=(
                    None if second_write_ok else "kernel_api_project_status_idempotency_failed"
                ),
                observed={
                    "ok": second_write.get("ok"),
                    "status": second_write.get("status"),
                    "write_applied": second_result.get("write_applied"),
                    "idempotent": second_result.get("idempotent"),
                },
            )
        )

        base_params = {
            "workspace_root": str(resolved_workspace),
            "dry_run": False,
            "confirm_write": _WRITE_CONFIRM_VALUE,
        }
        follow_first = client.call_action(
            "roadmap_follow",
            {**base_params, "roadmap_id": "A", "step_id": "s1"},
        )
        follow_conflict = client.call_action(
            "roadmap_follow",
            {**base_params, "roadmap_id": "B", "step_id": "s1"},
        )
        follow_takeover = client.call_action(
            "roadmap_follow",
            {
                **base_params,
                "roadmap_id": "B",
                "step_id": "s1",
                "allow_takeover": True,
            },
        )
        follow_takeover_result = follow_takeover.get("result", {})
        state_rel = str(follow_takeover_result.get("state_path", ""))
        state_abs = resolved_workspace / state_rel if state_rel else None
        follow_contract_ok = (
            follow_first.get("ok") is True
            and follow_conflict.get("ok") is False
            and follow_conflict.get("status") == "BLOCKED"
            and str(follow_conflict.get("error", {}).get("code")) == "ROADMAP_CONFLICT"
            and follow_takeover.get("ok") is True
            and follow_takeover_result.get("status") == "following"
            and state_abs is not None
            and state_abs.exists()
        )
        checks.append(
            SmokeCheck(
                name="roadmap_follow_conflict_takeover",
                status="pass" if follow_contract_ok else "fail",
                detail=(
                    "roadmap_follow conflict/takeover smoke gecti"
                    if follow_contract_ok
                    else "roadmap_follow conflict/takeover contract ihlali"
                ),
                finding_code=(
                    None if follow_contract_ok else "kernel_api_roadmap_follow_contract_failed"
                ),
                observed={
                    "follow_ok": follow_first.get("ok"),
                    "conflict_status": follow_conflict.get("status"),
                    "conflict_code": follow_conflict.get("error", {}).get("code"),
                    "takeover_ok": follow_takeover.get("ok"),
                    "takeover_state": follow_takeover_result.get("status"),
                    "state_exists": state_abs.exists() if state_abs is not None else False,
                },
            )
        )
        if state_abs is not None and state_abs.exists():
            artifacts.append(str(state_abs))

        finish_first = client.call_action(
            "roadmap_finish",
            {**base_params, "roadmap_id": "B", "step_id": "s1"},
        )
        finish_second = client.call_action(
            "roadmap_finish",
            {**base_params, "roadmap_id": "B", "step_id": "s1"},
        )
        finish_first_result = finish_first.get("result", {})
        finish_second_result = finish_second.get("result", {})
        finish_contract_ok = (
            finish_first.get("ok") is True
            and finish_first_result.get("status") == "finished"
            and finish_first_result.get("idempotent") is False
            and finish_second.get("ok") is True
            and finish_second_result.get("idempotent") is True
        )
        checks.append(
            SmokeCheck(
                name="roadmap_finish_idempotent",
                status="pass" if finish_contract_ok else "fail",
                detail=(
                    "roadmap_finish write+idempotency smoke gecti"
                    if finish_contract_ok
                    else "roadmap_finish write+idempotency contract ihlali"
                ),
                finding_code=(
                    None if finish_contract_ok else "kernel_api_roadmap_finish_contract_failed"
                ),
                observed={
                    "first_ok": finish_first.get("ok"),
                    "first_status": finish_first_result.get("status"),
                    "first_idempotent": finish_first_result.get("idempotent"),
                    "second_ok": finish_second.get("ok"),
                    "second_idempotent": finish_second_result.get("idempotent"),
                },
            )
        )

        audit_rel = str(finish_first_result.get("audit_path", "")) or str(
            first_result.get("audit_path", "")
        )
        audit_abs = resolved_workspace / audit_rel if audit_rel else None
        audit_actions: list[str] = []
        if audit_abs is not None and audit_abs.exists():
            artifacts.append(str(audit_abs))
            try:
                lines = [
                    line
                    for line in audit_abs.read_text(encoding="utf-8").splitlines()
                    if line.strip()
                ]
                for line in lines:
                    payload = json.loads(line)
                    action = payload.get("action")
                    if isinstance(action, str) and action:
                        audit_actions.append(action)
            except (OSError, json.JSONDecodeError):
                audit_actions = []
        audit_ok = (
            audit_abs is not None
            and audit_abs.exists()
            and {"project_status", "roadmap_follow", "roadmap_finish"}.issubset(
                set(audit_actions)
            )
        )
        checks.append(
            SmokeCheck(
                name="write_audit_artifacts",
                status="pass" if audit_ok else "fail",
                detail=(
                    "kernel_api write audit artifact smoke gecti"
                    if audit_ok
                    else "kernel_api write audit artifact kontrati ihlali"
                ),
                finding_code=(
                    None if audit_ok else "kernel_api_write_audit_missing_or_incomplete"
                ),
                observed={
                    "audit_exists": audit_abs.exists() if audit_abs is not None else False,
                    "actions": audit_actions,
                },
            )
        )
    finally:
        if managed_temp_root is not None and not keep_workspace:
            shutil.rmtree(managed_temp_root, ignore_errors=True)

    findings = tuple(
        sorted(
            {
                check.finding_code
                for check in checks
                if check.status != "pass" and check.finding_code
            }
        )
    )
    overall_status: Literal["pass", "blocked"] = "pass" if not findings else "blocked"
    return KernelApiWriteSmokeReport(
        overall_status=overall_status,
        extension_id="PRJ-KERNEL-API",
        workspace_root=str(resolved_workspace),
        checks=tuple(checks),
        findings=findings,
        artifacts=tuple(sorted(set(artifacts))),
    )


def render_text_report(report: KernelApiWriteSmokeReport) -> str:
    """Render a concise operator-facing text report."""

    lines = [
        f"overall_status: {report.overall_status}",
        f"extension_id: {report.extension_id}",
        f"workspace_root: {report.workspace_root}",
        "checks:",
    ]
    for check in report.checks:
        lines.append(f"- {check.name}: {check.status} - {check.detail}")
        if check.finding_code:
            lines.append(f"  finding_code: {check.finding_code}")
    if report.artifacts:
        lines.append("artifacts:")
        for artifact in report.artifacts:
            lines.append(f"- {artifact}")
    else:
        lines.append("artifacts: <none>")
    if report.findings:
        lines.append(f"findings: {', '.join(report.findings)}")
    else:
        lines.append("findings: <none>")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="kernel_api_write_smoke",
        description=(
            "Run PRJ-KERNEL-API write-side smoke checks "
            "(dry-run/confirm/idempotency/conflict/takeover/audit)."
        ),
    )
    parser.add_argument(
        "--output",
        choices=("text", "json"),
        default="text",
        help="Render mode for the smoke report.",
    )
    parser.add_argument(
        "--workspace-root",
        help=(
            "Optional workspace root to keep artifacts. "
            "By default a disposable temp workspace is used."
        ),
    )
    parser.add_argument(
        "--keep-workspace",
        action="store_true",
        help="When using disposable temp workspace, keep it for inspection.",
    )
    args = parser.parse_args(argv)

    report = run_kernel_api_write_smoke(
        workspace_root=Path(args.workspace_root).expanduser()
        if args.workspace_root
        else None,
        keep_workspace=args.keep_workspace,
    )
    if args.output == "json":
        print(json.dumps(report.as_dict(), indent=2, sort_keys=True))
    else:
        print(render_text_report(report))
    return 0 if report.overall_status == "pass" else 1
