"""Contract tests for the governed Claude Code CLI workflow smoke."""

from __future__ import annotations

import json
import uuid
from pathlib import Path

from ao_kernel.real_adapter_workflow_smoke import (
    _operator_managed_policy,
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
