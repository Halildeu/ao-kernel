#!/usr/bin/env python3
"""ao-kernel governed workflow demo — Bug Fix Flow (FAZ-A PR-A6).

Runs the ``bug_fix_flow`` workflow end-to-end with:
- codex-stub deterministic adapter (no real LLM)
- Programmatic auto-approval at the governance gate
- Evidence timeline printed at the end

Usage:
    python3 examples/demo_bugfix.py [--workspace-root .]

Requirements:
    pip install ao-kernel
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="ao-kernel bug fix demo")
    parser.add_argument("--workspace-root", default=".", help="Project root with .ao/")
    args = parser.parse_args(argv)

    ws = Path(args.workspace_root).resolve()
    print(f"[demo] workspace: {ws}")

    # 1. Ensure workspace init.
    # NOTE: `ao-kernel init` has asymmetric path semantics — passing
    # `--workspace-root X` writes the workspace files *directly* under
    # X rather than `X/.ao/`. That's tracked as a v3.13.1+ fix. In the
    # demo we side-step it by chdir'ing into the target and invoking
    # `init` with no override, which uses `cwd/.ao/` as expected.
    ao_dir = ws / ".ao"
    if not ao_dir.is_dir():
        print("[demo] initializing workspace...")
        subprocess.run(
            [sys.executable, "-m", "ao_kernel.cli", "init"],
            cwd=str(ws),
            check=True,
        )

    # 2. Ensure adapter manifests
    adapters_dir = ao_dir / "adapters"
    if not adapters_dir.is_dir() or not list(adapters_dir.glob("*.manifest.v1.json")):
        print("[demo] seeding adapter manifests...")
        _seed_adapters(ws)

    # 3. Seed a run
    run_id = str(uuid.uuid4())
    print(f"[demo] run_id: {run_id}")
    _seed_run(ws, run_id)

    # 4. Build driver + run workflow
    from ao_kernel.adapters import AdapterRegistry
    from ao_kernel.executor import Executor, MultiStepDriver
    from ao_kernel.workflow.registry import WorkflowRegistry

    wreg = WorkflowRegistry()
    wreg.load_workspace(ws)

    areg = AdapterRegistry()
    areg.load_bundled()
    areg.load_workspace(ws)

    executor = Executor(
        workspace_root=ws,
        workflow_registry=wreg,
        adapter_registry=areg,
    )

    driver = MultiStepDriver(
        workspace_root=ws,
        registry=wreg,
        adapter_registry=areg,
        executor=executor,
    )

    print("[demo] running bug_fix_flow...")
    result = driver.run_workflow(run_id, "bug_fix_flow", "1.0.0")
    print(f"[demo] first result: state={result.final_state}")

    # 5. Auto-approve governance gate
    if result.final_state == "waiting_approval" and result.resume_token:
        print("[demo] auto-approving governance gate...")
        result = driver.resume_workflow(
            run_id, result.resume_token,
            payload={
                "decision": "granted",
                "notes": "demo auto-approval",
                "approval_actor": "demo-auto",
            },
        )
        print(f"[demo] post-approval: state={result.final_state}")

    # 6. Evidence timeline
    print()
    print("=" * 72)
    print("Evidence Timeline")
    print("=" * 72)
    from ao_kernel._internal.evidence.timeline import timeline
    try:
        tl = timeline(ws, run_id)
        print(tl)
    except FileNotFoundError:
        print("[demo] no evidence events found")

    # 7. Generate + verify manifest
    from ao_kernel._internal.evidence.manifest import generate_manifest, verify_manifest
    try:
        gen = generate_manifest(ws, run_id)
        print(f"\n[demo] manifest generated: {gen.manifest_path} ({len(gen.files)} files)")
        ver = verify_manifest(ws, run_id)
        if ver.all_match:
            print("[demo] manifest verification: OK")
        else:
            print(f"[demo] manifest verification: FAIL (mismatches={ver.mismatches})")
    except FileNotFoundError:
        print("[demo] no evidence directory for manifest")

    print(f"\n[demo] final state: {result.final_state}")
    print(f"[demo] steps executed: {result.steps_executed}")
    return 0 if result.final_state in ("completed", "waiting_approval") else 1


def _seed_adapters(ws: Path) -> None:
    """Copy bundled adapter manifests to .ao/adapters/."""
    from importlib import resources
    dest = ws / ".ao" / "adapters"
    dest.mkdir(parents=True, exist_ok=True)
    pkg = resources.files("ao_kernel.defaults.adapters")
    for item in pkg.iterdir():
        if item.name.endswith(".manifest.v1.json"):
            with resources.as_file(item) as src:
                (dest / item.name).write_text(src.read_text(encoding="utf-8"))


def _seed_run(ws: Path, run_id: str) -> None:
    """Create a minimal run record in state=created."""
    from ao_kernel.workflow.run_store import run_revision

    run_dir = ws / ".ao" / "runs" / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    record: dict = {
        "run_id": run_id,
        "workflow_id": "bug_fix_flow",
        "workflow_version": "1.0.0",
        "state": "created",
        "created_at": now,
        "revision": "0" * 64,
        "intent": {"kind": "inline_prompt", "payload": "fix the hello.txt typo"},
        "steps": [],
        "policy_refs": ["ao_kernel/defaults/policies/policy_worktree_profile.v1.json"],
        "adapter_refs": ["codex-stub"],
        "evidence_refs": [f".ao/evidence/workflows/{run_id}/events.jsonl"],
        "budget": {"fail_closed_on_exhaust": True},
    }
    record["revision"] = run_revision(record)

    state_file = run_dir / "state.v1.json"
    state_file.write_text(
        json.dumps(record, indent=2, sort_keys=True), encoding="utf-8",
    )


if __name__ == "__main__":
    sys.exit(main())
