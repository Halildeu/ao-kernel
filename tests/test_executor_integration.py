"""End-to-end integration tests for PR-A3 executor.

Exercises: intent → registry → adapter registry → cross-ref →
Executor.run_step → worktree → policy enforcement → adapter
invocation → evidence events → run record CAS update.

Uses the bundled ``codex-stub`` adapter (via
``ao_kernel.fixtures.codex_stub``) for deterministic subprocess paths.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import uuid
from pathlib import Path

import pytest

from ao_kernel.adapters import AdapterRegistry
from ao_kernel.executor import Executor
from ao_kernel.executor.adapter_invoker import _invocation_from_envelope
from ao_kernel.workflow import WorkflowRegistry, create_run, load_run
from tests.benchmarks.fixtures import bug_envelopes


_FIXTURE_SRC = Path(__file__).parent / "fixtures" / "adapter_manifests"


def _init_git_repo(root: Path) -> None:
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    subprocess.run(
        ["git", "-C", str(root), "config", "user.email", "t@e"], check=True
    )
    subprocess.run(
        ["git", "-C", str(root), "config", "user.name", "t"], check=True
    )
    (root / "seed.txt").write_text("seed\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(root), "add", "seed.txt"], check=True)
    subprocess.run(
        ["git", "-C", str(root), "commit", "-q", "-m", "seed"], check=True
    )


def _bundled_policy_with_overrides() -> dict:
    """Bundled worktree policy with enabled=True + http/env/paths that let
    the codex_stub subprocess actually run."""
    with open(
        "ao_kernel/defaults/policies/policy_worktree_profile.v1.json",
        encoding="utf-8",
    ) as f:
        policy = json.load(f)
    policy = dict(policy)
    # Enable policy + allow the test's Python invocation
    policy["enabled"] = True
    env_spec = dict(policy["env_allowlist"])
    env_spec["explicit_additions"] = {
        "PATH": "/usr/bin:/usr/local/bin:/opt/homebrew/bin",
        "PYTHONPATH": os.getcwd(),
    }
    policy["env_allowlist"] = env_spec
    return policy


def _copy_adapter(workspace_root: Path, fixture_name: str) -> None:
    adapters_dir = workspace_root / ".ao" / "adapters"
    adapters_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(_FIXTURE_SRC / fixture_name, adapters_dir / fixture_name)


def _create_run_record(workspace_root: Path, run_id: str) -> None:
    create_run(
        workspace_root,
        run_id=run_id,
        workflow_id="bug_fix_flow",
        workflow_version="1.0.0",
        intent={"kind": "inline_prompt", "payload": "fix the crash"},
        budget={
            "time_seconds": {"limit": 120.0, "spent": 0.0, "remaining": 120.0},
            "fail_closed_on_exhaust": True,
        },
        policy_refs=[
            "ao_kernel/defaults/policies/policy_worktree_profile.v1.json"
        ],
        evidence_refs=[f".ao/evidence/workflows/{run_id}/events.jsonl"],
        adapter_refs=["codex-stub"],
    )


class TestIntegrationHappy:
    def test_adapter_step_end_to_end(self, tmp_path: Path) -> None:
        """Full cycle: create_run → Executor.run_step → evidence +
        run state updated, worktree cleaned."""
        _init_git_repo(tmp_path)
        _copy_adapter(tmp_path, "codex-stub.manifest.v1.json")
        _copy_adapter(tmp_path, "gh-cli-pr.manifest.v1.json")

        wf_reg = WorkflowRegistry()
        wf_reg.load_bundled()
        ad_reg = AdapterRegistry()
        ad_reg.load_workspace(tmp_path)

        rid = str(uuid.uuid4())
        _create_run_record(tmp_path, rid)

        definition = wf_reg.get("bug_fix_flow")
        # Pick the adapter step from the bundled workflow.
        adapter_step = next(s for s in definition.steps if s.actor == "adapter")

        executor = Executor(
            tmp_path,
            workflow_registry=wf_reg,
            adapter_registry=ad_reg,
            policy_loader=_bundled_policy_with_overrides(),
        )
        result = executor.run_step(rid, adapter_step, parent_env={})
        assert result.step_state == "completed"
        assert result.invocation_result is not None
        assert result.invocation_result.status == "ok"

        # Run record reflects the step
        record, _ = load_run(tmp_path, rid)
        assert record["steps"][0]["state"] == "completed"
        assert record["steps"][0]["step_name"] == adapter_step.step_name

        # Worktree cleaned
        worktree_path = tmp_path / ".ao" / "runs" / rid / "worktree"
        assert not worktree_path.exists()

    def test_bundled_codex_stub_allows_localized_python_executable_override(
        self, tmp_path: Path
    ) -> None:
        """Bundled ``{python_executable}`` stays runnable under a
        restrictive command policy, but only for that resolved path."""

        _init_git_repo(tmp_path)

        wf_reg = WorkflowRegistry()
        wf_reg.load_bundled()
        ad_reg = AdapterRegistry()
        ad_reg.load_bundled()

        rid = str(uuid.uuid4())
        _create_run_record(tmp_path, rid)

        definition = wf_reg.get("bug_fix_flow")
        adapter_step = next(s for s in definition.steps if s.actor == "adapter")

        policy = _bundled_policy_with_overrides()
        policy["command_allowlist"] = {"exact": ["git"], "prefixes": []}
        policy["rollout"] = {"mode_default": "block", "promote_to_block_on": []}

        executor = Executor(
            tmp_path,
            workflow_registry=wf_reg,
            adapter_registry=ad_reg,
            policy_loader=policy,
        )
        result = executor.run_step(rid, adapter_step, parent_env={})
        assert result.step_state == "completed"
        assert result.invocation_result is not None
        assert result.invocation_result.status == "ok"

        events_path = (
            tmp_path / ".ao" / "evidence" / "workflows" / rid / "events.jsonl"
        )
        events = [
            json.loads(line)
            for line in events_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        checked = next(e for e in events if e.get("kind") == "policy_checked")
        assert checked["payload"]["violations_count"] == 0
        assert checked["payload"]["violation_kinds"] == []

    def test_open_pr_step_persists_pr_metadata_and_emits_event(
        self, tmp_path: Path
    ) -> None:
        _init_git_repo(tmp_path)

        wf_reg = WorkflowRegistry()
        wf_reg.load_bundled()
        ad_reg = AdapterRegistry()
        ad_reg.load_bundled()

        rid = str(uuid.uuid4())
        _create_run_record(tmp_path, rid)

        definition = wf_reg.get("bug_fix_flow")
        open_pr_step = next(s for s in definition.steps if s.step_name == "open_pr")

        executor = Executor(
            tmp_path,
            workflow_registry=wf_reg,
            adapter_registry=ad_reg,
            policy_loader=_bundled_policy_with_overrides(),
        )

        from ao_kernel.executor import executor as executor_module

        original_invoke_cli = executor_module.invoke_cli

        def _dispatch_cli(
            *,
            manifest,
            input_envelope,
            sandbox,
            worktree,
            budget,
            workspace_root,
            run_id,
            resolved_invocation=None,
        ):
            if manifest.adapter_id != "gh-cli-pr":
                return original_invoke_cli(
                    manifest=manifest,
                    input_envelope=input_envelope,
                    sandbox=sandbox,
                    worktree=worktree,
                    budget=budget,
                    workspace_root=workspace_root,
                    run_id=run_id,
                    resolved_invocation=resolved_invocation,
                )

            log_path = (
                workspace_root
                / ".ao"
                / "evidence"
                / "workflows"
                / run_id
                / "adapter-gh-cli-pr.stdout.log"
            )
            log_path.parent.mkdir(parents=True, exist_ok=True)
            log_path.write_text(json.dumps({"_mock": True}), encoding="utf-8")
            envelope = bug_envelopes.open_pr_happy()
            result = _invocation_from_envelope(
                envelope,
                log_path=log_path,
                elapsed=float(envelope["cost_actual"]["time_seconds"]),
                command="benchmark-mock[gh-cli-pr]",
                manifest=manifest,
            )
            return result, budget

        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(executor_module, "invoke_cli", _dispatch_cli)
            result = executor.run_step(rid, open_pr_step, parent_env={})

        assert result.step_state == "completed"
        assert result.invocation_result is not None
        assert result.invocation_result.pr_url == "https://github.example/ao-kernel/pull/999"
        assert result.invocation_result.pr_number == 999

        record, _ = load_run(tmp_path, rid)
        step = record["steps"][0]
        artifact = json.loads(
            (
                tmp_path
                / ".ao"
                / "evidence"
                / "workflows"
                / rid
                / step["output_ref"]
            ).read_text(encoding="utf-8")
        )
        assert artifact["pr_url"].endswith("/pull/999")
        assert artifact["pr_number"] == 999

        events_path = (
            tmp_path / ".ao" / "evidence" / "workflows" / rid / "events.jsonl"
        )
        events = [
            json.loads(line)
            for line in events_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        returned = next(event for event in events if event.get("kind") == "adapter_returned")
        pr_opened = next(event for event in events if event.get("kind") == "pr_opened")
        assert returned["payload"]["pr_url"].endswith("/pull/999")
        assert returned["payload"]["pr_number"] == 999
        assert pr_opened["payload"]["pr_url"].endswith("/pull/999")
        assert pr_opened["payload"]["pr_number"] == 999


class TestIntegrationPolicyDenied:
    def test_missing_adapter_manifest_raises_cross_ref(
        self, tmp_path: Path
    ) -> None:
        """No adapter manifests shipped → validate_cross_refs returns
        non-empty → Executor.run_step raises."""
        from ao_kernel.workflow import WorkflowDefinitionCrossRefError

        _init_git_repo(tmp_path)
        # NO adapter manifests copied.

        wf_reg = WorkflowRegistry()
        wf_reg.load_bundled()
        ad_reg = AdapterRegistry()
        ad_reg.load_workspace(tmp_path)

        rid = str(uuid.uuid4())
        _create_run_record(tmp_path, rid)

        definition = wf_reg.get("bug_fix_flow")
        adapter_step = next(s for s in definition.steps if s.actor == "adapter")

        executor = Executor(
            tmp_path,
            workflow_registry=wf_reg,
            adapter_registry=ad_reg,
            policy_loader=_bundled_policy_with_overrides(),
        )
        with pytest.raises(WorkflowDefinitionCrossRefError):
            executor.run_step(rid, adapter_step, parent_env={})


class TestIntegrationPrimitiveContract:
    def test_foreign_step_rejected(self, tmp_path: Path) -> None:
        from ao_kernel.workflow import StepDefinition

        _init_git_repo(tmp_path)
        _copy_adapter(tmp_path, "codex-stub.manifest.v1.json")
        _copy_adapter(tmp_path, "gh-cli-pr.manifest.v1.json")

        wf_reg = WorkflowRegistry()
        wf_reg.load_bundled()
        ad_reg = AdapterRegistry()
        ad_reg.load_workspace(tmp_path)

        rid = str(uuid.uuid4())
        _create_run_record(tmp_path, rid)

        foreign_step = StepDefinition(
            step_name="foreign_step_name_not_in_flow",
            actor="ao-kernel",
            adapter_id=None,
            required_capabilities=(),
            policy_refs=(),
            on_failure="transition_to_failed",
            timeout_seconds=None,
            human_interrupt_allowed=False,
            gate=None,
        )

        executor = Executor(
            tmp_path,
            workflow_registry=wf_reg,
            adapter_registry=ad_reg,
            policy_loader=_bundled_policy_with_overrides(),
        )
        with pytest.raises(ValueError, match="not in workflow"):
            executor.run_step(rid, foreign_step, parent_env={})

    def test_duplicate_completed_step_rejected(self, tmp_path: Path) -> None:
        _init_git_repo(tmp_path)
        _copy_adapter(tmp_path, "codex-stub.manifest.v1.json")
        _copy_adapter(tmp_path, "gh-cli-pr.manifest.v1.json")

        wf_reg = WorkflowRegistry()
        wf_reg.load_bundled()
        ad_reg = AdapterRegistry()
        ad_reg.load_workspace(tmp_path)

        rid = str(uuid.uuid4())
        _create_run_record(tmp_path, rid)

        definition = wf_reg.get("bug_fix_flow")
        adapter_step = next(s for s in definition.steps if s.actor == "adapter")

        executor = Executor(
            tmp_path,
            workflow_registry=wf_reg,
            adapter_registry=ad_reg,
            policy_loader=_bundled_policy_with_overrides(),
        )
        executor.run_step(rid, adapter_step, parent_env={})
        # Second call on same step should refuse (already completed).
        with pytest.raises(ValueError, match="already completed"):
            executor.run_step(rid, adapter_step, parent_env={})
