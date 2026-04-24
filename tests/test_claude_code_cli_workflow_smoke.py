"""Contract tests for the governed Claude Code CLI workflow smoke."""

from __future__ import annotations

import json
import uuid
from pathlib import Path

from pytest import MonkeyPatch

import ao_kernel.real_adapter_workflow_smoke as workflow_smoke
from ao_kernel.executor.errors import (
    AdapterInvocationFailedError,
    AdapterOutputParseError,
    PolicyViolation,
    PolicyViolationError,
)
from ao_kernel.real_adapter_workflow_smoke import (
    _operator_managed_policy,
    run_claude_code_cli_workflow_smoke,
    verify_claude_workflow_evidence,
)
from ao_kernel.workflow import create_run, update_run

_RUN_CREATED_AT = "2026-04-24T00:00:00+00:00"


def test_operator_managed_policy_enables_live_policy_check() -> None:
    policy = _operator_managed_policy()

    assert policy["enabled"] is True
    assert policy["env_allowlist"]["inherit_from_parent"] is True
    assert "claude" in policy["command_allowlist"]["exact"]
    assert "PATH" in policy["env_allowlist"]["allowed_keys"]
    assert "HOME" in policy["env_allowlist"]["allowed_keys"]


def test_verify_claude_workflow_evidence_accepts_complete_success(
    tmp_path: Path,
) -> None:
    run_id = _seed_completed_run(tmp_path)

    checks = verify_claude_workflow_evidence(tmp_path, run_id)

    assert {check.name for check in checks} == {
        "final_state",
        "evidence_events",
        "review_findings_artifact",
        "adapter_log",
        "review_findings_schema",
    }
    assert all(check.status == "pass" for check in checks)


def test_verify_claude_workflow_evidence_rejects_missing_policy_checked(
    tmp_path: Path,
) -> None:
    run_id = _seed_completed_run(tmp_path, omit_event="policy_checked")

    checks = verify_claude_workflow_evidence(tmp_path, run_id)
    evidence = next(check for check in checks if check.name == "evidence_events")

    assert evidence.status == "fail"
    assert "policy_checked" in evidence.detail
    assert evidence.finding_code == "evidence_events_missing"


def test_workflow_smoke_classifies_output_parse_fail_closed(
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(workflow_smoke, "_prepare_workspace", lambda root: None)

    def _fail_output_parse(
        workspace_root: Path,
        run_id: str,
        *,
        timeout_seconds: float,
    ) -> str:
        raise AdapterOutputParseError(
            raw_excerpt="not-json",
            detail="stdout neither a valid JSON output_envelope",
        )

    monkeypatch.setattr(workflow_smoke, "_run_workflow", _fail_output_parse)

    report = run_claude_code_cli_workflow_smoke(
        skip_preflight=True,
        workspace_root=tmp_path,
    )

    assert report.overall_status == "blocked"
    assert report.findings == ("output_parse_failed",)
    assert report.checks[0].name == "workflow_run"
    assert report.checks[0].finding_code == "output_parse_failed"
    assert "fail-closed" in report.checks[0].detail


def test_workflow_smoke_classifies_policy_denial_before_promotion(
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(workflow_smoke, "_prepare_workspace", lambda root: None)

    def _fail_policy(
        workspace_root: Path,
        run_id: str,
        *,
        timeout_seconds: float,
    ) -> str:
        violation = PolicyViolation(
            kind="command_not_allowlisted",
            detail="claude denied by test policy",
            policy_ref="ao_kernel/defaults/policies/policy_worktree_profile.v1.json",
            field_path="command_allowlist",
        )
        raise PolicyViolationError(violations=[violation])

    monkeypatch.setattr(workflow_smoke, "_run_workflow", _fail_policy)

    report = run_claude_code_cli_workflow_smoke(
        skip_preflight=True,
        workspace_root=tmp_path,
    )

    assert report.overall_status == "blocked"
    assert report.findings == ("policy_denied",)
    assert report.checks[0].finding_code == "policy_denied"
    assert "command_not_allowlisted" in report.checks[0].detail


def test_workflow_smoke_classifies_adapter_non_zero_exit(
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(workflow_smoke, "_prepare_workspace", lambda root: None)

    def _fail_non_zero(
        workspace_root: Path,
        run_id: str,
        *,
        timeout_seconds: float,
    ) -> str:
        raise AdapterInvocationFailedError(
            reason="non_zero_exit",
            detail="claude exited 1",
        )

    monkeypatch.setattr(workflow_smoke, "_run_workflow", _fail_non_zero)

    report = run_claude_code_cli_workflow_smoke(
        skip_preflight=True,
        workspace_root=tmp_path,
    )

    assert report.overall_status == "blocked"
    assert report.findings == ("adapter_non_zero_exit",)
    assert report.checks[0].finding_code == "adapter_non_zero_exit"


def test_workflow_smoke_classifies_adapter_timeout(
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(workflow_smoke, "_prepare_workspace", lambda root: None)

    def _fail_timeout(
        workspace_root: Path,
        run_id: str,
        *,
        timeout_seconds: float,
    ) -> str:
        raise AdapterInvocationFailedError(
            reason="timeout",
            detail=f"claude exceeded {timeout_seconds}s",
        )

    monkeypatch.setattr(workflow_smoke, "_run_workflow", _fail_timeout)

    report = run_claude_code_cli_workflow_smoke(
        skip_preflight=True,
        workspace_root=tmp_path,
        timeout_seconds=1.0,
    )

    assert report.overall_status == "blocked"
    assert report.findings == ("adapter_timeout",)
    assert report.checks[0].finding_code == "adapter_timeout"
    assert "fail-closed" in report.checks[0].detail


def _seed_completed_run(tmp_path: Path, *, omit_event: str | None = None) -> str:
    run_id = str(uuid.uuid4())
    create_run(
        tmp_path,
        run_id=run_id,
        workflow_id="governed_review_claude_code_cli",
        workflow_version="1.0.0",
        intent={"kind": "inline_prompt", "payload": "review"},
        budget={
            "fail_closed_on_exhaust": True,
            "time_seconds": {"limit": 60.0, "remaining": 60.0},
        },
        policy_refs=["ao_kernel/defaults/policies/policy_worktree_profile.v1.json"],
        evidence_refs=[f".ao/evidence/workflows/{run_id}/events.jsonl"],
        adapter_refs=["claude-code-cli"],
    )
    run_dir = tmp_path / ".ao" / "evidence" / "workflows" / run_id
    artifact_rel = "artifacts/review-findings.json"
    artifact_path = run_dir / artifact_rel
    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    artifact_path.write_text(
        json.dumps(
            {
                "schema_version": "1",
                "findings": [],
                "summary": "synthetic smoke success",
            }
        ),
        encoding="utf-8",
    )
    (run_dir / "adapter-claude-code-cli.jsonl").write_text(
        json.dumps(
            {
                "adapter_id": "claude-code-cli",
                "stdout": "{}",
                "stderr": "",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    event_kinds = [
        "step_started",
        "policy_checked",
        "adapter_invoked",
        "step_completed",
        "workflow_completed",
    ]
    (run_dir / "events.jsonl").write_text(
        "\n".join(
            json.dumps({"kind": kind})
            for kind in event_kinds
            if kind != omit_event
        )
        + "\n",
        encoding="utf-8",
    )

    def _complete(record: dict[str, object]) -> dict[str, object]:
        record["state"] = "completed"
        record["completed_at"] = _RUN_CREATED_AT
        record["steps"] = [
            {
                "step_id": "invoke_review_agent",
                "step_name": "invoke_review_agent",
                "state": "completed",
                "actor": "adapter",
                "started_at": _RUN_CREATED_AT,
                "completed_at": _RUN_CREATED_AT,
                "adapter_id": "claude-code-cli",
                "capability_output_refs": {"review_findings": artifact_rel},
            }
        ]
        return record

    update_run(tmp_path, run_id, mutator=_complete)
    return run_id
