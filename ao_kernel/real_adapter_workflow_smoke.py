"""Operator workflow smokes for real-adapter certification lanes.

The helper-level smoke in :mod:`ao_kernel.real_adapter_smoke` proves the
``claude-code-cli`` manifest can invoke the external CLI. This module goes one
layer higher: it runs the bundled governed workflow variant and verifies the
runtime evidence that promotion decisions need.
"""

from __future__ import annotations

import contextlib
import copy
import io
import json
import os
import shutil
import subprocess
import tempfile
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Literal, Mapping, Sequence

from jsonschema import Draft202012Validator

from ao_kernel.adapters import AdapterRegistry
from ao_kernel.config import load_default
from ao_kernel.executor import Executor, MultiStepDriver
from ao_kernel.executor.errors import (
    AdapterInvocationFailedError,
    AdapterOutputParseError,
    PolicyViolationError,
)
from ao_kernel.init_cmd import run as init_workspace
from ao_kernel.real_adapter_smoke import ClaudeCodeSmokeReport, run_claude_code_cli_smoke
from ao_kernel.workflow import WorkflowRegistry, create_run, load_run

_WORKFLOW_ID = "governed_review_claude_code_cli"
_WORKFLOW_VERSION = "1.0.0"
_ADAPTER_ID = "claude-code-cli"
_REVIEW_STEP_NAME = "invoke_review_agent"
_REQUIRED_EVENT_KINDS = frozenset(
    {
        "step_started",
        "policy_checked",
        "adapter_invoked",
        "step_completed",
        "workflow_completed",
    }
)
_GIT_CFG = (
    "-c",
    "user.name=ao-kernel-smoke",
    "-c",
    "user.email=smoke@ao-kernel.local",
    "-c",
    "commit.gpgsign=false",
)
_READ_ONLY_PROMPT = """\
You are running an ao-kernel certification smoke for the Claude Code CLI
adapter. Treat the workspace as read-only. Do not modify files, run package
installs, create commits, or open pull requests.

Return exactly one JSON object and no Markdown fences:
{"status":"ok","review_findings":{"schema_version":"1","findings":[],"summary":"claude-code-cli governed workflow smoke completed"}}
"""


@dataclass(frozen=True)
class WorkflowSmokeCheck:
    name: str
    status: Literal["pass", "fail", "skip"]
    detail: str
    finding_code: str | None = None
    path: str | None = None
    observed: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ClaudeWorkflowSmokeReport:
    overall_status: Literal["pass", "blocked"]
    workflow_id: str
    workflow_version: str
    adapter_id: str
    run_id: str | None
    workspace_root: str | None
    final_state: str | None
    preflight_status: str | None
    checks: tuple[WorkflowSmokeCheck, ...]
    findings: tuple[str, ...]
    cleanup_requested: bool = False

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def run_claude_code_cli_workflow_smoke(
    *,
    timeout_seconds: float = 60.0,
    cleanup: bool = False,
    skip_preflight: bool = False,
    workspace_root: Path | None = None,
) -> ClaudeWorkflowSmokeReport:
    """Run the governed Claude Code workflow against a disposable workspace."""

    preflight: ClaudeCodeSmokeReport | None = None
    if not skip_preflight:
        preflight = run_claude_code_cli_smoke(timeout_seconds=timeout_seconds)
        if preflight.overall_status != "pass":
            checks: tuple[WorkflowSmokeCheck, ...] = (
                WorkflowSmokeCheck(
                    name="helper_preflight",
                    status="fail",
                    detail="claude-code-cli helper smoke did not pass",
                    finding_code="helper_preflight_blocked",
                    observed=preflight.as_dict(),
                ),
            )
            return _finalize_report(
                run_id=None,
                workspace_root=None,
                final_state=None,
                preflight_status=preflight.overall_status,
                checks=checks,
                cleanup_requested=cleanup,
            )

    owns_workspace = workspace_root is None
    root = (
        Path(tempfile.mkdtemp(prefix="ao-kernel-claude-workflow-smoke-"))
        if workspace_root is None
        else workspace_root
    ).resolve()

    try:
        _prepare_workspace(root)
        run_id = str(uuid.uuid4())
        final_state = _run_workflow(root, run_id, timeout_seconds=timeout_seconds)
        checks = verify_claude_workflow_evidence(root, run_id)
        return _finalize_report(
            run_id=run_id,
            workspace_root=root,
            final_state=final_state,
            preflight_status=preflight.overall_status if preflight else "skipped",
            checks=checks,
            cleanup_requested=cleanup,
        )
    except Exception as exc:  # noqa: BLE001 - operator smoke must summarize failures
        finding_code, detail = _classify_workflow_exception(exc)
        return _finalize_report(
            run_id=locals().get("run_id"),
            workspace_root=root,
            final_state=None,
            preflight_status=preflight.overall_status if preflight else "skipped",
            checks=(
                WorkflowSmokeCheck(
                    name="workflow_run",
                    status="fail",
                    detail=detail,
                    finding_code=finding_code,
                ),
            ),
            cleanup_requested=cleanup,
        )
    finally:
        if cleanup and owns_workspace:
            shutil.rmtree(root, ignore_errors=True)


def verify_claude_workflow_evidence(
    workspace_root: Path,
    run_id: str,
) -> tuple[WorkflowSmokeCheck, ...]:
    """Verify governed workflow evidence and typed artifact materialization."""

    record, _revision = load_run(workspace_root, run_id)
    run_dir = workspace_root / ".ao" / "evidence" / "workflows" / run_id
    events_path = run_dir / "events.jsonl"
    events = _load_jsonl(events_path)

    checks: list[WorkflowSmokeCheck] = [
        _check_final_state(record),
        _check_required_events(events_path, events),
    ]
    artifact_check, artifact_path = _check_review_artifact(workspace_root, run_id, record)
    checks.append(artifact_check)
    checks.append(_check_adapter_log(run_dir / f"adapter-{_ADAPTER_ID}.jsonl"))
    if artifact_path is not None:
        checks.append(_check_schema_valid_artifact(artifact_path))
    return tuple(checks)


def render_workflow_text_report(report: ClaudeWorkflowSmokeReport) -> str:
    """Render a compact human-readable report for operators."""

    lines = [
        f"overall_status: {report.overall_status}",
        f"workflow_id: {report.workflow_id}",
        f"workflow_version: {report.workflow_version}",
        f"adapter_id: {report.adapter_id}",
        f"preflight_status: {report.preflight_status}",
    ]
    if report.run_id:
        lines.append(f"run_id: {report.run_id}")
    if report.workspace_root:
        lines.append(f"workspace_root: {report.workspace_root}")
    if report.final_state:
        lines.append(f"final_state: {report.final_state}")
    lines.append("checks:")
    for check in report.checks:
        suffix = f" ({check.path})" if check.path else ""
        lines.append(f"- {check.name}: {check.status} - {check.detail}{suffix}")
    if report.findings:
        lines.append("findings:")
        lines.extend(f"- {finding}" for finding in report.findings)
    return "\n".join(lines)


def _prepare_workspace(workspace_root: Path) -> None:
    workspace_root.mkdir(parents=True, exist_ok=True)
    (workspace_root / "README.md").write_text(
        "# ao-kernel Claude workflow smoke\n\nRead-only certification fixture.\n",
        encoding="utf-8",
    )
    src = workspace_root / "src"
    src.mkdir(exist_ok=True)
    (src / "sample.py").write_text(
        "def add(left: int, right: int) -> int:\n    return left + right\n",
        encoding="utf-8",
    )
    if not (workspace_root / ".git").exists():
        _run_git(("init", "-q", "--initial-branch=main", str(workspace_root)))
    _run_git(("-C", str(workspace_root), "add", "."))
    _run_git(("-C", str(workspace_root), "commit", "-q", "-m", "initial"))
    with contextlib.redirect_stdout(io.StringIO()):
        init_workspace(str(workspace_root))


def _run_workflow(
    workspace_root: Path,
    run_id: str,
    *,
    timeout_seconds: float,
) -> str:
    workflow_registry = WorkflowRegistry()
    workflow_registry.load_bundled()

    adapter_registry = AdapterRegistry()
    adapter_registry.load_bundled()

    policy = _operator_managed_policy()
    executor = Executor(
        workspace_root=workspace_root,
        workflow_registry=workflow_registry,
        adapter_registry=adapter_registry,
        policy_loader=policy,
    )
    driver = MultiStepDriver(
        workspace_root=workspace_root,
        registry=workflow_registry,
        adapter_registry=adapter_registry,
        executor=executor,
        policy_config=policy,
    )

    create_run(
        workspace_root,
        run_id=run_id,
        workflow_id=_WORKFLOW_ID,
        workflow_version=_WORKFLOW_VERSION,
        intent={"kind": "inline_prompt", "payload": _READ_ONLY_PROMPT},
        budget={
            "fail_closed_on_exhaust": True,
            "time_seconds": {
                "limit": timeout_seconds,
                "remaining": timeout_seconds,
            },
        },
        policy_refs=[
            "ao_kernel/defaults/policies/policy_worktree_profile.v1.json",
            "ao_kernel/defaults/policies/policy_secrets.v1.json",
        ],
        evidence_refs=[f".ao/evidence/workflows/{run_id}/events.jsonl"],
        adapter_refs=[_ADAPTER_ID],
    )

    first = driver.run_workflow(run_id, _WORKFLOW_ID, _WORKFLOW_VERSION)
    if first.final_state == "waiting_approval":
        token = first.resume_token or _read_resume_token(
            workspace_root / ".ao" / "evidence" / "workflows" / run_id / "events.jsonl"
        )
        second = driver.resume_workflow(
            run_id,
            token,
            payload={"decision": "granted", "notes": "workflow smoke auto-approval"},
        )
        return second.final_state
    return first.final_state


def _operator_managed_policy() -> dict[str, Any]:
    policy = copy.deepcopy(load_default("policies", "policy_worktree_profile.v1.json"))
    policy["enabled"] = True

    env_allowlist = dict(policy.get("env_allowlist", {}))
    env_allowlist["inherit_from_parent"] = True
    allowed_keys = set(env_allowlist.get("allowed_keys", ()))
    allowed_keys.update({"PATH", "HOME", "USER", "LANG", "LC_ALL", "TZ", "SHELL", "TMPDIR"})
    env_allowlist["allowed_keys"] = sorted(allowed_keys)
    policy["env_allowlist"] = env_allowlist

    command_allowlist = dict(policy.get("command_allowlist", {}))
    exact = set(command_allowlist.get("exact", ()))
    exact.add("claude")
    command_allowlist["exact"] = sorted(exact)

    prefixes = list(command_allowlist.get("prefixes", ()))
    claude_path = shutil.which("claude", path=os.environ.get("PATH", ""))
    if claude_path:
        claude_prefix = str(Path(claude_path).resolve().parent) + "/"
        if claude_prefix not in prefixes:
            prefixes.append(claude_prefix)
    command_allowlist["prefixes"] = prefixes
    policy["command_allowlist"] = command_allowlist
    return policy


def _run_git(args: Sequence[str]) -> None:
    subprocess.run(
        ["git", *_GIT_CFG, *args],
        check=True,
        capture_output=True,
        text=True,
    )


def _load_jsonl(path: Path) -> tuple[Mapping[str, Any], ...]:
    if not path.is_file():
        return ()
    events: list[Mapping[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        events.append(json.loads(line))
    return tuple(events)


def _check_final_state(record: Mapping[str, Any]) -> WorkflowSmokeCheck:
    final_state = record.get("state")
    status: Literal["pass", "fail"] = "pass" if final_state == "completed" else "fail"
    return WorkflowSmokeCheck(
        name="final_state",
        status=status,
        detail=f"workflow state is {final_state!r}",
        observed={"state": final_state},
    )


def _check_required_events(
    events_path: Path,
    events: Sequence[Mapping[str, Any]],
) -> WorkflowSmokeCheck:
    observed = {str(event.get("kind")) for event in events}
    missing = sorted(_REQUIRED_EVENT_KINDS - observed)
    status: Literal["pass", "fail"] = "pass" if not missing else "fail"
    return WorkflowSmokeCheck(
        name="evidence_events",
        status=status,
        detail="required event kinds present" if not missing else f"missing: {missing}",
        finding_code="evidence_events_missing" if missing else None,
        path=str(events_path),
        observed={"required": sorted(_REQUIRED_EVENT_KINDS), "seen": sorted(observed)},
    )


def _check_review_artifact(
    workspace_root: Path,
    run_id: str,
    record: Mapping[str, Any],
) -> tuple[WorkflowSmokeCheck, Path | None]:
    review_step = next(
        (
            step for step in record.get("steps", ())
            if step.get("step_name") == _REVIEW_STEP_NAME
        ),
        None,
    )
    if not isinstance(review_step, Mapping):
        return (
            WorkflowSmokeCheck(
                name="review_findings_artifact",
                status="fail",
                detail=f"{_REVIEW_STEP_NAME!r} step record missing",
                finding_code="review_step_missing",
            ),
            None,
        )
    refs = review_step.get("capability_output_refs") or {}
    artifact_ref = refs.get("review_findings") if isinstance(refs, Mapping) else None
    if not isinstance(artifact_ref, str) or not artifact_ref:
        return (
            WorkflowSmokeCheck(
                name="review_findings_artifact",
                status="fail",
                detail="review_findings capability output ref missing",
                finding_code="review_findings_artifact_missing",
            ),
            None,
        )
    artifact_path = (
        workspace_root / ".ao" / "evidence" / "workflows" / run_id / artifact_ref
    )
    status: Literal["pass", "fail"] = "pass" if artifact_path.is_file() else "fail"
    return (
        WorkflowSmokeCheck(
            name="review_findings_artifact",
            status=status,
            detail="artifact materialized" if status == "pass" else "artifact file missing",
            finding_code=None if status == "pass" else "review_findings_artifact_missing",
            path=str(artifact_path),
            observed={"artifact_ref": artifact_ref},
        ),
        artifact_path if artifact_path.is_file() else None,
    )


def _check_schema_valid_artifact(artifact_path: Path) -> WorkflowSmokeCheck:
    payload = json.loads(artifact_path.read_text(encoding="utf-8"))
    schema = load_default("schemas", "review-findings.schema.v1.json")
    errors = list(Draft202012Validator(schema).iter_errors(payload))
    status: Literal["pass", "fail"] = "pass" if not errors else "fail"
    return WorkflowSmokeCheck(
        name="review_findings_schema",
        status=status,
        detail=(
            "review_findings schema-valid"
            if not errors
            else "; ".join(error.message for error in errors[:3])
        ),
        finding_code=None if not errors else "review_findings_schema_invalid",
        path=str(artifact_path),
    )


def _check_adapter_log(adapter_log_path: Path) -> WorkflowSmokeCheck:
    records = _load_jsonl(adapter_log_path)
    status: Literal["pass", "fail"] = "pass" if records else "fail"
    redaction_leaks = [
        token
        for record in records
        for token in ("sk-ant-", "ghp_", "Bearer ")
        if token in json.dumps(record)
    ]
    if redaction_leaks:
        status = "fail"
    return WorkflowSmokeCheck(
        name="adapter_log",
        status=status,
        detail=(
            "redacted adapter log present"
            if status == "pass"
            else "adapter log missing or contains unredacted secret-like token"
        ),
        finding_code=None if status == "pass" else "adapter_log_missing_or_unredacted",
        path=str(adapter_log_path),
        observed={"records": len(records), "redaction_leaks": redaction_leaks},
    )


def _finalize_report(
    *,
    run_id: str | None,
    workspace_root: Path | None,
    final_state: str | None,
    preflight_status: str | None,
    checks: Sequence[WorkflowSmokeCheck],
    cleanup_requested: bool,
) -> ClaudeWorkflowSmokeReport:
    findings = tuple(
        check.finding_code or f"{check.name}: {check.detail}"
        for check in checks
        if check.status == "fail"
    )
    overall_status: Literal["pass", "blocked"] = (
        "pass" if checks and all(check.status == "pass" for check in checks) else "blocked"
    )
    return ClaudeWorkflowSmokeReport(
        overall_status=overall_status,
        workflow_id=_WORKFLOW_ID,
        workflow_version=_WORKFLOW_VERSION,
        adapter_id=_ADAPTER_ID,
        run_id=run_id,
        workspace_root=str(workspace_root) if workspace_root else None,
        final_state=final_state,
        preflight_status=preflight_status,
        checks=tuple(checks),
        findings=findings,
        cleanup_requested=cleanup_requested,
    )


def _classify_workflow_exception(exc: Exception) -> tuple[str, str]:
    if isinstance(exc, AdapterOutputParseError):
        return (
            "output_parse_failed",
            f"workflow fail-closed on adapter output parse: {exc.detail}",
        )
    if isinstance(exc, PolicyViolationError):
        kinds = [violation.kind for violation in exc.violations]
        return (
            "policy_denied",
            f"workflow fail-closed on policy denial: {kinds}",
        )
    if isinstance(exc, AdapterInvocationFailedError):
        return (
            f"adapter_{exc.reason}",
            f"workflow fail-closed on adapter invocation failure: {exc.reason}",
        )
    return "workflow_run_failed", f"{type(exc).__name__}: {exc}"


def _read_resume_token(events_path: Path) -> str:
    for line in reversed(events_path.read_text(encoding="utf-8").splitlines()):
        if not line.strip():
            continue
        event = json.loads(line)
        if event.get("kind") not in {
            "human_gate_awaited",
            "workflow_awaiting_human",
            "step_awaiting_human",
        }:
            continue
        token = event.get("resume_token") or event.get("token")
        if isinstance(token, str) and token:
            return token
    raise RuntimeError("resume token not found in evidence timeline")


__all__ = [
    "ClaudeWorkflowSmokeReport",
    "WorkflowSmokeCheck",
    "render_workflow_text_report",
    "run_claude_code_cli_workflow_smoke",
    "verify_claude_workflow_evidence",
]
