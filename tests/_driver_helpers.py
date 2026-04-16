"""Shared helpers for MultiStepDriver tests (PR-A4b)."""

from __future__ import annotations

import json
import shutil
import subprocess
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from ao_kernel.adapters import AdapterRegistry
from ao_kernel.executor import Executor, MultiStepDriver
from ao_kernel.workflow.registry import WorkflowRegistry


_GIT_CFG = [
    "-c", "user.name=ao-kernel-driver-test",
    "-c", "user.email=driver@test.local",
    "-c", "init.defaultBranch=main",
    "-c", "commit.gpgsign=false",
]

_FIXTURE_DIR = Path(__file__).parent / "fixtures" / "workflows"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def install_workspace(root: Path) -> Path:
    """Prepare a minimal .ao workspace at ``root`` + init a git repo
    so patch primitives have somewhere to apply if called.
    """
    ao_dir = root / ".ao"
    (ao_dir / "workflows").mkdir(parents=True, exist_ok=True)
    (ao_dir / "adapters").mkdir(parents=True, exist_ok=True)
    (ao_dir / "evidence" / "workflows").mkdir(parents=True, exist_ok=True)
    (ao_dir / "runs").mkdir(parents=True, exist_ok=True)
    # Minimal git repo at root
    subprocess.run(
        ["git", "init", "-q", "--initial-branch=main", str(root)],
        check=True, capture_output=True,
    )
    (root / "README.md").write_text("# driver test\n")
    subprocess.run(
        ["git", *_GIT_CFG, "-C", str(root), "add", "."],
        check=True, capture_output=True,
    )
    subprocess.run(
        ["git", *_GIT_CFG, "-C", str(root), "commit", "-q", "-m", "initial"],
        check=True, capture_output=True,
    )
    return root


def copy_workflow_fixture(root: Path, fixture_name: str) -> Path:
    """Copy a workflow JSON fixture into the workspace so the registry finds it."""
    src = _FIXTURE_DIR / f"{fixture_name}.v1.json"
    dest_dir = root / ".ao" / "workflows"
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / src.name
    shutil.copyfile(src, dest)
    return dest


def write_stub_adapter_manifest(root: Path, adapter_id: str = "codex-stub") -> Path:
    """Install a minimal codex-stub adapter manifest under .ao/adapters/."""
    # Mirrors the shape used by tests/fixtures/adapter_manifests/codex-stub.manifest.v1.json
    manifest = {
        "adapter_id": adapter_id,
        "adapter_kind": "codex-stub",
        "version": "1.0.0",
        "capabilities": ["read_repo", "write_diff"],
        "invocation": {
            "transport": "cli",
            "command": "python3",
            "args": ["-m", "ao_kernel.fixtures.codex_stub", "--run-id", "{run_id}"],
            "env_allowlist_ref": "#/env_allowlist/allowed_keys",
            "cwd_policy": "per_run_worktree",
            "stdin_mode": "none",
            "exit_code_map": {"0": "ok"},
        },
        "input_envelope": {"task_prompt": "<stubbed>", "run_id": "<uuid>"},
        "output_envelope": {"status": "ok"},
        "policy_refs": [
            "ao_kernel/defaults/policies/policy_worktree_profile.v1.json",
        ],
        "evidence_refs": [
            f".ao/evidence/workflows/{{run_id}}/adapter-{adapter_id}.jsonl",
        ],
    }
    dest = root / ".ao" / "adapters" / f"{adapter_id}.manifest.v1.json"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return dest


def build_driver(root: Path) -> MultiStepDriver:
    """Build registry + adapter_registry + executor + driver pointing at ``root``."""
    wreg = WorkflowRegistry()
    wreg.load_workspace(root)

    areg = AdapterRegistry()
    areg.load_workspace(root)

    executor = Executor(
        workspace_root=root,
        workflow_registry=wreg,
        adapter_registry=areg,
    )

    return MultiStepDriver(
        workspace_root=root,
        registry=wreg,
        adapter_registry=areg,
        executor=executor,
    )


def seed_run(
    root: Path,
    workflow_id: str,
    workflow_version: str = "1.0.0",
    *,
    intent_payload: Mapping[str, Any] | None = None,
) -> str:
    """Write a minimal run_record with state=created; return the run_id.

    The run_record is schema-valid enough to pass load + save cycles;
    tests can then call ``driver.run_workflow(run_id, ...)``.
    """
    run_id = str(uuid.uuid4())
    run_dir = root / ".ao" / "runs" / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    # intent.payload is schema-typed as string for inline_prompt;
    # tests wanting to pass structured data use json.dumps wrapper.
    payload_str = (
        intent_payload if isinstance(intent_payload, str)
        else (json.dumps(intent_payload) if intent_payload else "driver test prompt")
    )
    from ao_kernel.workflow.run_store import run_revision
    record: dict[str, Any] = {
        "run_id": run_id,
        "workflow_id": workflow_id,
        "workflow_version": workflow_version,
        "state": "created",
        "created_at": _now_iso(),
        "revision": "0" * 64,  # placeholder; overwritten below
        "intent": {
            "kind": "inline_prompt",
            "payload": payload_str,
        },
        "steps": [],
        "policy_refs": ["ao_kernel/defaults/policies/policy_worktree_profile.v1.json"],
        "adapter_refs": [],
        "evidence_refs": [f".ao/evidence/workflows/{run_id}/events.jsonl"],
        "budget": {"fail_closed_on_exhaust": True},
    }
    record["revision"] = run_revision(record)
    state_file = run_dir / "state.v1.json"
    state_file.write_text(
        json.dumps(record, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    return run_id
