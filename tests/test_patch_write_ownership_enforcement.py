from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

import pytest

from ao_kernel.coordination import (
    ClaimRegistry,
    acquire_path_write_claims,
    release_path_write_claims,
)
from ao_kernel.executor.multi_step_driver import _StepFailed
from ao_kernel.workflow.registry import StepDefinition
from tests._driver_helpers import _GIT_CFG, build_driver, install_workspace
from tests._patch_helpers import make_patch_from_changes


def _write_coordination_policy(workspace_root: Path, *, enabled: bool) -> None:
    policy_dir = workspace_root / ".ao" / "policies"
    policy_dir.mkdir(parents=True, exist_ok=True)
    doc = {
        "version": "v1",
        "enabled": enabled,
        "heartbeat_interval_seconds": 30,
        "expiry_seconds": 90,
        "takeover_grace_period_seconds": 15,
        "max_claims_per_agent": 5,
        "claim_resource_patterns": ["*"],
        "evidence_redaction": {"patterns": []},
    }
    (policy_dir / "policy_coordination_claims.v1.json").write_text(
        json.dumps(doc, indent=2, sort_keys=True),
        encoding="utf-8",
    )


def _install_patch_target_repo(workspace_root: Path) -> None:
    src_dir = workspace_root / "src"
    src_dir.mkdir(parents=True, exist_ok=True)
    (src_dir / "foo.py").write_text("x = 1\n", encoding="utf-8")
    subprocess.run(
        ["git", *_GIT_CFG, "-C", str(workspace_root), "add", "."],
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", *_GIT_CFG, "-C", str(workspace_root), "commit", "-q", "-m", "patch target"],
        check=True,
        capture_output=True,
    )


def _patch_step() -> StepDefinition:
    return StepDefinition(
        step_name="apply_patch",
        actor="ao-kernel",
        adapter_id=None,
        required_capabilities=(),
        policy_refs=(),
        on_failure="transition_to_failed",
        timeout_seconds=None,
        human_interrupt_allowed=False,
        gate=None,
        operation="patch_apply",
    )


def _prime_adapter_artifact(
    workspace_root: Path,
    run_id: str,
    *,
    patch: str,
) -> str:
    run_dir = workspace_root / ".ao" / "evidence" / "workflows" / run_id
    artifacts_dir = run_dir / "artifacts"
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    output_ref = "artifacts/invoke_agent-attempt1.json"
    (run_dir / output_ref).write_text(
        json.dumps({"diff": patch}, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    return output_ref


def _record_with_adapter_output(run_id: str, output_ref: str) -> dict[str, object]:
    return {
        "run_id": run_id,
        "state": "running",
        "steps": [
            {
                "step_id": "invoke_agent",
                "step_name": "invoke_agent",
                "state": "completed",
                "actor": "adapter",
                "adapter_id": "fixture-agent",
                "output_ref": output_ref,
            }
        ],
    }


def _events(workspace_root: Path, run_id: str) -> list[dict[str, Any]]:
    events_path = (
        workspace_root / ".ao" / "evidence" / "workflows" / run_id / "events.jsonl"
    )
    return [json.loads(line) for line in events_path.read_text(encoding="utf-8").splitlines()]


class TestPatchWriteOwnershipEnforcement:
    def test_patch_apply_skips_claims_when_coordination_disabled(
        self, tmp_path: Path,
    ) -> None:
        install_workspace(tmp_path)
        _install_patch_target_repo(tmp_path)
        _write_coordination_policy(tmp_path, enabled=False)
        patch = make_patch_from_changes(tmp_path, {"src/foo.py": "x = 2\n"})
        run_id = "00000000-0000-4000-8000-000000000701"
        output_ref = _prime_adapter_artifact(tmp_path, run_id, patch=patch)
        driver = build_driver(tmp_path)

        _record, result = driver._run_aokernel_step(
            run_id,
            _record_with_adapter_output(run_id, output_ref),
            _patch_step(),
            attempt=1,
            step_id="apply_patch",
        )

        assert result["step_state"] == "completed"
        assert (tmp_path / "src" / "foo.py").read_text(encoding="utf-8") == "x = 2\n"
        kinds = [event["kind"] for event in _events(tmp_path, run_id)]
        assert kinds == ["step_started", "diff_applied"]
        diff_applied = next(event for event in _events(tmp_path, run_id) if event["kind"] == "diff_applied")
        assert "write_claim_areas" not in diff_applied["payload"]

    def test_patch_apply_acquires_and_releases_write_claims(
        self, tmp_path: Path,
    ) -> None:
        install_workspace(tmp_path)
        _install_patch_target_repo(tmp_path)
        patch = make_patch_from_changes(tmp_path, {"src/foo.py": "x = 2\n"})
        _write_coordination_policy(tmp_path, enabled=True)
        run_id = "00000000-0000-4000-8000-000000000702"
        output_ref = _prime_adapter_artifact(tmp_path, run_id, patch=patch)
        driver = build_driver(tmp_path)

        _record, result = driver._run_aokernel_step(
            run_id,
            _record_with_adapter_output(run_id, output_ref),
            _patch_step(),
            attempt=1,
            step_id="apply_patch",
        )

        assert result["step_state"] == "completed"
        assert (tmp_path / "src" / "foo.py").read_text(encoding="utf-8") == "x = 2\n"

        events = _events(tmp_path, run_id)
        kinds = [event["kind"] for event in events]
        assert kinds == [
            "step_started",
            "claim_acquired",
            "diff_applied",
            "claim_released",
        ]

        diff_applied = next(event for event in events if event["kind"] == "diff_applied")
        assert diff_applied["payload"]["write_claim_areas"] == ["src"]
        assert len(diff_applied["payload"]["write_claim_resource_ids"]) == 1

        run_dir = tmp_path / ".ao" / "evidence" / "workflows" / run_id
        artifact = json.loads(
            (run_dir / result["output_ref"]).read_text(encoding="utf-8")
        )
        assert artifact["write_claim_areas"] == ["src"]

        registry = ClaimRegistry(tmp_path)
        assert registry.list_agent_claims(f"workflow-run:{run_id}") == []

    def test_patch_apply_conflict_surfaces_as_step_failed_signal(
        self, tmp_path: Path,
    ) -> None:
        install_workspace(tmp_path)
        _install_patch_target_repo(tmp_path)
        patch = make_patch_from_changes(tmp_path, {"src/foo.py": "x = 2\n"})
        _write_coordination_policy(tmp_path, enabled=True)
        run_id = "00000000-0000-4000-8000-000000000703"
        output_ref = _prime_adapter_artifact(tmp_path, run_id, patch=patch)
        driver = build_driver(tmp_path)
        registry = ClaimRegistry(tmp_path)
        blocked = acquire_path_write_claims(
            registry,
            tmp_path,
            owner_agent_id="agent-existing",
            paths=["src/foo.py"],
        )

        with pytest.raises(_StepFailed) as excinfo:
            driver._run_aokernel_step(
                run_id,
                _record_with_adapter_output(run_id, output_ref),
                _patch_step(),
                attempt=1,
                step_id="apply_patch",
            )

        assert excinfo.value.code == "WRITE_OWNERSHIP_CONFLICT"
        assert "ClaimConflictError" in excinfo.value.reason
        assert (tmp_path / "src" / "foo.py").read_text(encoding="utf-8") == "x = 1\n"

        events = _events(tmp_path, run_id)
        kinds = [event["kind"] for event in events]
        assert kinds == ["step_started", "claim_conflict"]

        remaining = registry.list_agent_claims("agent-existing")
        assert [claim.resource_id for claim in remaining] == [
            blocked.leases[0].scope.resource_id
        ]
        release_path_write_claims(registry, blocked)
