#!/usr/bin/env python3
"""Run the Public Beta review demo against a disposable workspace."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
import uuid
from pathlib import Path

from jsonschema import Draft202012Validator


_GIT_CFG = [
    "-c", "user.name=ao-kernel-demo",
    "-c", "user.email=demo@ao-kernel.local",
    "-c", "commit.gpgsign=false",
]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="ao-kernel Public Beta review demo"
    )
    parser.add_argument(
        "--cleanup",
        action="store_true",
        help="Remove the temporary demo workspace after verification",
    )
    args = parser.parse_args(argv)

    workspace_root = Path(
        tempfile.mkdtemp(prefix="ao-kernel-review-demo-")
    ).resolve()
    print(f"[demo] workspace: {workspace_root}")

    try:
        _init_git_repo(workspace_root)
        _init_workspace(workspace_root)
        result = _run_demo(workspace_root)

        print(f"[demo] run_id: {result['run_id']}")
        print(f"[demo] final state: {result['final_state']}")
        print(f"[demo] review artifact: {result['artifact_path']}")
        print(f"[demo] events: {result['events_path']}")
        if args.cleanup:
            shutil.rmtree(workspace_root)
            print("[demo] workspace cleaned up")
        else:
            print("[demo] workspace kept for inspection")
        return 0
    except Exception as exc:  # noqa: BLE001 - demo script should fail loudly
        print(f"[demo] failure: {exc}", file=sys.stderr)
        if args.cleanup:
            shutil.rmtree(workspace_root, ignore_errors=True)
        return 1


def _init_git_repo(workspace_root: Path) -> None:
    (workspace_root / "README.md").write_text(
        "# ao-kernel review demo\n",
        encoding="utf-8",
    )
    subprocess.run(
        ["git", "init", "-q", "--initial-branch=main", str(workspace_root)],
        check=True,
        capture_output=True,
        text=True,
    )
    subprocess.run(
        ["git", *_GIT_CFG, "-C", str(workspace_root), "add", "."],
        check=True,
        capture_output=True,
        text=True,
    )
    subprocess.run(
        ["git", *_GIT_CFG, "-C", str(workspace_root), "commit", "-q", "-m", "initial"],
        check=True,
        capture_output=True,
        text=True,
    )


def _init_workspace(workspace_root: Path) -> None:
    proc = subprocess.run(
        [sys.executable, "-m", "ao_kernel", "init"],
        cwd=str(workspace_root),
        check=True,
        capture_output=True,
        text=True,
    )
    if proc.stdout.strip():
        print(proc.stdout.strip())


def _run_demo(workspace_root: Path) -> dict[str, str]:
    from ao_kernel.adapters import AdapterRegistry
    from ao_kernel.config import load_default
    from ao_kernel.executor import Executor, MultiStepDriver
    from ao_kernel.workflow import WorkflowRegistry, create_run, load_run

    workflow_registry = WorkflowRegistry()
    workflow_registry.load_bundled()

    adapter_registry = AdapterRegistry()
    adapter_registry.load_bundled()

    executor = Executor(
        workspace_root=workspace_root,
        workflow_registry=workflow_registry,
        adapter_registry=adapter_registry,
    )
    driver = MultiStepDriver(
        workspace_root=workspace_root,
        registry=workflow_registry,
        adapter_registry=adapter_registry,
        executor=executor,
    )

    run_id = str(uuid.uuid4())
    create_run(
        workspace_root,
        run_id=run_id,
        workflow_id="review_ai_flow",
        workflow_version="1.0.0",
        intent={
            "kind": "inline_prompt",
            "payload": "Inspect the workspace and emit review findings.",
        },
        budget={
            "fail_closed_on_exhaust": True,
            "time_seconds": {"limit": 600.0, "remaining": 600.0},
        },
        policy_refs=["ao_kernel/defaults/policies/policy_worktree_profile.v1.json"],
        evidence_refs=[f".ao/evidence/workflows/{run_id}/events.jsonl"],
        adapter_refs=["codex-stub"],
    )

    first = driver.run_workflow(run_id, "review_ai_flow", "1.0.0")
    token = first.resume_token or _read_resume_token(
        workspace_root / ".ao" / "evidence" / "workflows" / run_id / "events.jsonl"
    )
    second = driver.resume_workflow(
        run_id,
        token,
        payload={"decision": "granted", "notes": "demo auto-approval"},
    )

    if second.final_state != "completed":
        raise RuntimeError(f"unexpected final state: {second.final_state!r}")

    record, _ = load_run(workspace_root, run_id)
    review_step = next(
        step for step in record.get("steps", [])
        if step.get("step_name") == "invoke_review_agent"
    )
    refs = review_step.get("capability_output_refs") or {}
    artifact_ref = refs.get("review_findings")
    if not artifact_ref:
        raise RuntimeError("review_findings artifact was not materialized")

    artifact_path = workspace_root / ".ao" / "evidence" / "workflows" / run_id / artifact_ref
    if not artifact_path.is_file():
        raise RuntimeError(f"missing review artifact: {artifact_path}")

    payload = json.loads(artifact_path.read_text(encoding="utf-8"))
    schema = load_default("schemas", "review-findings.schema.v1.json")
    errors = list(Draft202012Validator(schema).iter_errors(payload))
    if errors:
        messages = ", ".join(error.message for error in errors[:3])
        raise RuntimeError(f"review_findings schema validation failed: {messages}")

    events_path = workspace_root / ".ao" / "evidence" / "workflows" / run_id / "events.jsonl"
    if not events_path.is_file():
        raise RuntimeError("events.jsonl was not emitted")
    if "workflow_completed" not in events_path.read_text(encoding="utf-8"):
        raise RuntimeError("workflow_completed event missing from evidence timeline")

    return {
        "artifact_path": str(artifact_path),
        "events_path": str(events_path),
        "final_state": second.final_state,
        "run_id": run_id,
    }


def _read_resume_token(events_path: Path) -> str:
    if not events_path.is_file():
        raise RuntimeError(f"missing events timeline: {events_path}")
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


if __name__ == "__main__":
    raise SystemExit(main())
