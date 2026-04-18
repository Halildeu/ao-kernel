"""PR-C6.1 driver-layer dry-run parity tests.

Verifies ``MultiStepDriver.dry_run_step`` wires context_pack_ref +
parent_env + step_id + attempt derivation through to
``Executor.dry_run_step`` — closing the v3.3.0 gap where executor-only
preview used a bare task-prompt envelope.

Adversarial-consulted via Codex CNS-20260418-034 (iter-1..5 AGREE).
Six semantic guards pinned:

1. Run-state guard: only ``created`` / ``running`` allowed
2. Completed-step guard: ``step_name`` at highest-attempt=completed blocks
3. Attempt validation: explicit attempt MUST equal driver-derived
4. Running-placeholder reuse: existing step_id when state=running
5. Adapter-only fidelity: non-adapter → NotImplementedError
6. Happy path: envelope + parent_env forwarded to executor
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

from ao_kernel.executor.dry_run import DryRunResult
from ao_kernel.executor.multi_step_driver import MultiStepDriver

from tests._driver_helpers import (
    build_driver,
    copy_workflow_fixture,
    install_workspace,
    seed_run,
    write_stub_adapter_manifest,
)


# ─── Shared fixture: adapter-first workflow + seeded run ───────────────


def _prepare_workspace(root: Path) -> tuple[MultiStepDriver, str]:
    install_workspace(root)
    copy_workflow_fixture(root, "adapter_plus_ci_flow")
    write_stub_adapter_manifest(root)
    driver = build_driver(root)
    run_id = seed_run(
        root,
        workflow_id="adapter_plus_ci_flow",
        workflow_version="1.0.0",
    )
    return driver, run_id


# ─── 1. Happy path: adapter step parity ────────────────────────────────


class TestAdapterDryRunHappyPath:
    def test_driver_dry_run_returns_DryRunResult(
        self, tmp_path: Path,
    ) -> None:
        driver, run_id = _prepare_workspace(tmp_path)
        result = driver.dry_run_step(run_id, "invoke_agent")
        assert isinstance(result, DryRunResult)

    def test_forwards_step_id_to_executor(self, tmp_path: Path) -> None:
        """First attempt → step_id = step_name (via _step_id_for_attempt)."""
        driver, run_id = _prepare_workspace(tmp_path)
        captured: dict[str, Any] = {}

        real_exec = driver._executor.dry_run_step

        def _spy(*a: Any, **kw: Any) -> Any:
            captured.update(kw)
            return real_exec(*a, **kw)

        with patch.object(driver._executor, "dry_run_step", side_effect=_spy):
            driver.dry_run_step(run_id, "invoke_agent")

        assert captured.get("step_id") == "invoke_agent"
        assert captured.get("driver_managed") is True
        # parent_env forwarded (empty dict OK — depends on policy)
        assert "parent_env" in captured
        # attempt derived to 1 on fresh run
        assert captured.get("attempt") == 1


# ─── 2. Run-state guard ────────────────────────────────────────────────


class TestRunStateGuard:
    def test_terminal_state_blocks_dry_run(self, tmp_path: Path) -> None:
        driver, run_id = _prepare_workspace(tmp_path)
        # Mutate record to failed state
        state_path = tmp_path / ".ao" / "runs" / run_id / "state.v1.json"
        record = json.loads(state_path.read_text(encoding="utf-8"))
        record["state"] = "failed"
        from ao_kernel.workflow.run_store import run_revision
        record["revision"] = run_revision(record)
        state_path.write_text(
            json.dumps(record, indent=2, sort_keys=True), encoding="utf-8",
        )

        with pytest.raises(ValueError, match="dry-run requires run in"):
            driver.dry_run_step(run_id, "invoke_agent")

    def test_waiting_approval_blocks_dry_run(self, tmp_path: Path) -> None:
        driver, run_id = _prepare_workspace(tmp_path)
        state_path = tmp_path / ".ao" / "runs" / run_id / "state.v1.json"
        record = json.loads(state_path.read_text(encoding="utf-8"))
        record["state"] = "waiting_approval"
        from ao_kernel.workflow.run_store import run_revision
        record["revision"] = run_revision(record)
        state_path.write_text(
            json.dumps(record, indent=2, sort_keys=True), encoding="utf-8",
        )

        with pytest.raises(ValueError, match="dry-run requires run in"):
            driver.dry_run_step(run_id, "invoke_agent")


# ─── 3. Completed-step guard ───────────────────────────────────────────


class TestCompletedStepGuard:
    def test_highest_completed_step_blocks_even_with_explicit_attempt(
        self, tmp_path: Path,
    ) -> None:
        """Even with ``attempt=2``, a step_name whose highest-attempt
        is ``completed`` blocks — the real driver would never spawn
        attempt=2 for a completed step_name."""
        driver, run_id = _prepare_workspace(tmp_path)
        state_path = tmp_path / ".ao" / "runs" / run_id / "state.v1.json"
        record = json.loads(state_path.read_text(encoding="utf-8"))
        record["steps"] = [{
            "step_name": "invoke_agent",
            "step_id": "invoke_agent",
            "attempt": 1,
            "state": "completed",
            "actor": "adapter",
            "started_at": "2026-04-18T10:00:00+00:00",
            "completed_at": "2026-04-18T10:00:01+00:00",
        }]
        from ao_kernel.workflow.run_store import run_revision
        record["revision"] = run_revision(record)
        state_path.write_text(
            json.dumps(record, indent=2, sort_keys=True), encoding="utf-8",
        )

        with pytest.raises(ValueError, match="already completed"):
            driver.dry_run_step(run_id, "invoke_agent", attempt=2)


# ─── 4. Attempt validation ─────────────────────────────────────────────


class TestAttemptValidation:
    def test_negative_attempt_raises(self, tmp_path: Path) -> None:
        driver, run_id = _prepare_workspace(tmp_path)
        with pytest.raises(ValueError, match="attempt must be >= 1"):
            driver.dry_run_step(run_id, "invoke_agent", attempt=0)

    def test_explicit_attempt_must_match_derived(
        self, tmp_path: Path,
    ) -> None:
        """On a fresh run, derived attempt is 1; passing attempt=2
        without any prior step records is a fictional path → ValueError."""
        driver, run_id = _prepare_workspace(tmp_path)
        with pytest.raises(ValueError, match="does not match driver-derived"):
            driver.dry_run_step(run_id, "invoke_agent", attempt=2)


# ─── 5. Running-placeholder reuse ──────────────────────────────────────


class TestRunningPlaceholderReuse:
    def test_running_placeholder_reuses_step_id(
        self, tmp_path: Path,
    ) -> None:
        """Mid-crash resume: record has attempt=2 state=running → dry-run
        must reuse that placeholder's step_id, not mint a new one."""
        driver, run_id = _prepare_workspace(tmp_path)
        state_path = tmp_path / ".ao" / "runs" / run_id / "state.v1.json"
        record = json.loads(state_path.read_text(encoding="utf-8"))
        placeholder_id = "invoke_agent-a2-deadbe"
        record["state"] = "running"
        record["steps"] = [
            {
                "step_name": "invoke_agent",
                "step_id": "invoke_agent",
                "attempt": 1,
                "state": "failed",
                "actor": "adapter",
                "started_at": "2026-04-18T10:00:00+00:00",
                "completed_at": "2026-04-18T10:00:01+00:00",
                "error": {
                    "category": "other",
                    "code": "SIMULATED_FAILURE",
                    "message": "simulated for test fixture",
                },
            },
            {
                "step_name": "invoke_agent",
                "step_id": placeholder_id,
                "attempt": 2,
                "state": "running",
                "actor": "adapter",
                "started_at": "2026-04-18T10:00:02+00:00",
            },
        ]
        from ao_kernel.workflow.run_store import run_revision
        record["revision"] = run_revision(record)
        state_path.write_text(
            json.dumps(record, indent=2, sort_keys=True), encoding="utf-8",
        )

        captured: dict[str, Any] = {}
        real_exec = driver._executor.dry_run_step

        def _spy(*a: Any, **kw: Any) -> Any:
            captured.update(kw)
            return real_exec(*a, **kw)

        with patch.object(driver._executor, "dry_run_step", side_effect=_spy):
            driver.dry_run_step(run_id, "invoke_agent")

        assert captured.get("step_id") == placeholder_id
        assert captured.get("attempt") == 2


# ─── 6. Non-adapter scope (inner API) ──────────────────────────────────


class TestNonAdapterScope:
    def test_system_actor_uses_sandbox_parent_env(
        self, tmp_path: Path,
    ) -> None:
        """v3.4.0 #4: `system` actors (ci-runner / patch-apply) now
        route through the driver with sandbox-style parent_env
        (allowlist MINUS secrets). Previously raised
        NotImplementedError (C6.1 adapter-only scope)."""
        driver, run_id = _prepare_workspace(tmp_path)
        captured: dict[str, Any] = {}
        real_exec = driver._executor.dry_run_step

        def _spy(*a: Any, **kw: Any) -> Any:
            captured.update(kw)
            return real_exec(*a, **kw)

        with patch.object(driver._executor, "dry_run_step", side_effect=_spy):
            driver.dry_run_step(run_id, "lint_check")

        # system actors get parent_env (may be empty dict if no
        # allowlisted env vars are set in the test environment) but
        # no input_envelope_override
        assert captured.get("input_envelope_override") is None
        assert "parent_env" in captured
        assert isinstance(captured["parent_env"], dict)
        assert captured.get("driver_managed") is True


class TestAoKernelActorScope:
    """v3.4.0 #4: `ao-kernel` actors (internal steps) route through
    the driver with empty envelope + no parent_env (in-process)."""

    def _prepare_aokernel_workspace(self, root: Path):
        install_workspace(root)
        copy_workflow_fixture(root, "simple_aokernel_flow")
        write_stub_adapter_manifest(root)
        driver = build_driver(root)
        run_id = seed_run(
            root,
            workflow_id="simple_aokernel_flow",
            workflow_version="1.0.0",
        )
        return driver, run_id

    def test_aokernel_actor_no_envelope_no_parent_env(
        self, tmp_path: Path,
    ) -> None:
        driver, run_id = self._prepare_aokernel_workspace(tmp_path)
        captured: dict[str, Any] = {}
        real_exec = driver._executor.dry_run_step

        def _spy(*a: Any, **kw: Any) -> Any:
            captured.update(kw)
            return real_exec(*a, **kw)

        with patch.object(driver._executor, "dry_run_step", side_effect=_spy):
            driver.dry_run_step(run_id, "compile_ctx")

        # ao-kernel actor: no envelope override, no parent_env
        # (in-process execution has no sandbox surface)
        assert captured.get("input_envelope_override") is None
        assert captured.get("parent_env") is None
        assert captured.get("driver_managed") is True


# ─── 7. parent_env derivation ──────────────────────────────────────────


class TestParentEnvDerivation:
    def test_parent_env_includes_allowlisted_env_vars(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """parent_env = UNION(allowlist_secret_ids, env_allowlist.allowed_keys)
        filtered to keys present in os.environ."""
        # Ensure a known env var is set and in the policy allowlist
        monkeypatch.setenv("PATH", "/usr/bin:/bin")
        driver, run_id = _prepare_workspace(tmp_path)

        captured: dict[str, Any] = {}
        real_exec = driver._executor.dry_run_step

        def _spy(*a: Any, **kw: Any) -> Any:
            captured.update(kw)
            return real_exec(*a, **kw)

        with patch.object(driver._executor, "dry_run_step", side_effect=_spy):
            driver.dry_run_step(run_id, "invoke_agent")

        parent_env = captured.get("parent_env") or {}
        # Bundled policy has PATH in env_allowlist.allowed_keys
        # (see ao_kernel/defaults/policies/policy_worktree_profile.v1.json)
        assert "PATH" in parent_env
        assert parent_env["PATH"] == os.environ["PATH"]
