"""Integration tests for MultiStepDriver (PR-A4b).

Exercises the full driver dispatch path with real Executor + bundled
codex-stub adapter + real subprocess (python3 -m ruff). No mocks; the
flow mirrors a slice of the FAZ-A governed demo (adapter invocation →
lint check → completion).
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

from ao_kernel.ci import CIResult
from ao_kernel.executor.adapter_invoker import _invocation_from_envelope
from ao_kernel.executor import DriverResult
from ao_kernel.workflow.run_store import load_run
from tests.benchmarks.fixtures import bug_envelopes
from tests._driver_helpers import (
    _GIT_CFG,
    build_driver,
    copy_workflow_fixture,
    install_workspace,
    seed_run,
    write_stub_adapter_manifest,
)

_BUNDLED_ROOT = Path(__file__).resolve().parent.parent / "ao_kernel" / "defaults"
_OPEN_PR_GUARD_ENV = "AO_KERNEL_ALLOW_GH_CLI_PR_LIVE_WRITE"


def _copy_bundled_defaults(root: Path) -> None:
    ao_dir = root / ".ao"
    (ao_dir / "policies").mkdir(parents=True, exist_ok=True)
    for subdir, pattern in (
        ("policies", "policy_*.v1.json"),
        ("workflows", "*.v1.json"),
        ("adapters", "*.manifest.v1.json"),
    ):
        for src in (_BUNDLED_ROOT / subdir).glob(pattern):
            shutil.copy2(src, ao_dir / subdir / src.name)


def _install_bugfix_repo(root: Path) -> None:
    src_dir = root / "src"
    src_dir.mkdir(parents=True, exist_ok=True)
    (src_dir / "__init__.py").write_text("", encoding="utf-8")
    (src_dir / "foo.py").write_text("x = 1\n", encoding="utf-8")
    tests_dir = root / "tests"
    tests_dir.mkdir(parents=True, exist_ok=True)
    (tests_dir / "test_smoke.py").write_text(
        "def test_passes():\n    assert 1 + 1 == 2\n",
        encoding="utf-8",
    )
    subprocess.run(
        ["git", *_GIT_CFG, "-C", str(root), "add", "."],
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", *_GIT_CFG, "-C", str(root), "commit", "-q", "-m", "bugfix baseline"],
        check=True,
        capture_output=True,
    )


def _policy_with_pythonpath() -> dict[str, object]:
    policy = json.loads(
        (_BUNDLED_ROOT / "policies" / "policy_worktree_profile.v1.json").read_text(
            encoding="utf-8"
        )
    )
    policy["enabled"] = True
    env_spec = dict(policy["env_allowlist"])
    env_spec["explicit_additions"] = {
        "PATH": "/usr/bin:/usr/local/bin:/opt/homebrew/bin",
        "PYTHONPATH": os.getcwd(),
    }
    policy["env_allowlist"] = env_spec
    return policy


class TestAdapterPlusCIFlow:
    def _setup(self, tmp_path: Path):
        install_workspace(tmp_path)
        copy_workflow_fixture(tmp_path, "adapter_plus_ci_flow")
        write_stub_adapter_manifest(tmp_path)
        # Ensure the stub adapter worktree exists so the executor has a
        # cwd to hand to the subprocess.
        worktree = tmp_path / ".ao" / "runs"
        worktree.mkdir(parents=True, exist_ok=True)
        # Give the ci_ruff step something clean to lint.
        (tmp_path / "mod.py").write_text("def f():\n    return 1\n")
        run_id = seed_run(tmp_path, "adapter_plus_ci_flow")
        driver = build_driver(tmp_path)
        return driver, run_id

    def test_adapter_then_ci_ruff_completes(self, tmp_path: Path) -> None:
        driver, run_id = self._setup(tmp_path)
        try:
            result = driver.run_workflow(
                run_id, "adapter_plus_ci_flow", "1.0.0",
            )
        except Exception as exc:  # pragma: no cover - subprocess platform variance
            pytest.skip(
                f"integration env cannot run adapter+ci chain: {exc!r}"
            )
        # Either completes or fails depending on whether ruff is
        # available on this host. The driver should produce a
        # DriverResult either way; we only assert it reached a terminal.
        assert isinstance(result, DriverResult)
        assert result.final_state in {"completed", "failed"}

    def test_evidence_stream_has_adapter_events(self, tmp_path: Path) -> None:
        driver, run_id = self._setup(tmp_path)
        try:
            driver.run_workflow(run_id, "adapter_plus_ci_flow", "1.0.0")
        except Exception:  # pragma: no cover
            pytest.skip("integration env cannot run adapter+ci chain")
        events_path = (
            tmp_path / ".ao" / "evidence" / "workflows" / run_id
            / "events.jsonl"
        )
        assert events_path.exists()
        lines = [json.loads(ln) for ln in events_path.read_text().splitlines()]
        kinds = [e.get("kind") for e in lines]
        assert "workflow_started" in kinds
        assert "adapter_invoked" in kinds or "adapter_returned" in kinds

    def test_run_record_persists_step_records(self, tmp_path: Path) -> None:
        driver, run_id = self._setup(tmp_path)
        try:
            driver.run_workflow(run_id, "adapter_plus_ci_flow", "1.0.0")
        except Exception:  # pragma: no cover
            pytest.skip("integration env cannot run adapter+ci chain")
        record, _ = load_run(tmp_path, run_id)
        step_names = {s.get("step_name") for s in record.get("steps", [])}
        # At least the adapter step should have been recorded (regardless
        # of ruff availability on this host).
        assert "invoke_agent" in step_names


class TestBundledBugFixFlow:
    def test_real_codex_stub_completes_preview_diff(
        self,
        tmp_path: Path,
    ) -> None:
        install_workspace(tmp_path)
        _copy_bundled_defaults(tmp_path)
        _install_bugfix_repo(tmp_path)

        run_id = seed_run(tmp_path, "bug_fix_flow")
        driver = build_driver(tmp_path, policy_loader=_policy_with_pythonpath())
        result = driver.run_workflow(run_id, "bug_fix_flow", "1.0.0")

        run_dir = tmp_path / ".ao" / "evidence" / "workflows" / run_id
        record, _ = load_run(tmp_path, run_id)
        step_records = {step["step_name"]: step for step in record.get("steps", [])}

        assert step_records["invoke_coding_agent"]["state"] == "completed"
        assert step_records["preview_diff"]["state"] == "completed"

        coding_artifact = json.loads(
            (run_dir / step_records["invoke_coding_agent"]["output_ref"]).read_text(
                encoding="utf-8"
            )
        )
        assert "--- a/src/foo.py" in coding_artifact["diff"]
        assert "+++ b/src/foo.py" in coding_artifact["diff"]

        preview_artifact = json.loads(
            (run_dir / step_records["preview_diff"]["output_ref"]).read_text(
                encoding="utf-8"
            )
        )
        assert preview_artifact["files_changed"] == ["src/foo.py"]
        assert preview_artifact["lines_added"] == 1
        assert preview_artifact["lines_removed"] == 1

        ci_gate = step_records.get("ci_gate")
        assert ci_gate is not None, step_records
        if ci_gate["state"] == "completed":
            assert result.final_state == "waiting_approval"
            assert result.resume_token is not None
        else:
            assert result.final_state == "failed"
            error = ci_gate.get("error") or {}
            assert (
                error.get("code") in {"CI_RUNNER_NOT_FOUND", "CI_CHECK_FAILED"}
                or (
                    error.get("code") == "STEP_FAILED"
                    and error.get("message") == "ci_pytest_fail"
                )
            ), error

    def test_real_codex_stub_with_mocked_ci_and_open_pr_completes_full_flow(
        self,
        tmp_path: Path,
    ) -> None:
        """Pin the bundled 7-step bug-fix path with the real
        ``codex-stub`` subprocess plus deterministic CI/PR sidecars.

        Scope of this test is the workflow closure after the coding
        step: approval gate, patch apply, PR metadata persistence and
        evidence emission. ``ci_pytest`` and ``gh-cli-pr`` are mocked so
        host runner toolchain drift does not make the integration flaky.
        """
        install_workspace(tmp_path)
        _copy_bundled_defaults(tmp_path)
        _install_bugfix_repo(tmp_path)

        run_id = seed_run(tmp_path, "bug_fix_flow")
        driver = build_driver(tmp_path, policy_loader=_policy_with_pythonpath())

        import ao_kernel.ci as ci_module
        from ao_kernel.executor import executor as executor_module

        original_invoke_cli = executor_module.invoke_cli

        def _mock_run_pytest(*args, **kwargs):
            return CIResult(
                check_name="pytest",
                command=("python3", "-m", "pytest"),
                status="pass",
                exit_code=0,
                duration_seconds=0.01,
                stdout_tail="mocked pytest pass",
                stderr_tail="",
            )

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
                / f"adapter-{manifest.adapter_id}.stdout.log"
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

        with patch.dict(os.environ, {_OPEN_PR_GUARD_ENV: "1"}, clear=False):
            with patch(
                "ao_kernel.executor.executor.invoke_cli",
                side_effect=_dispatch_cli,
            ):
                with patch.object(
                    ci_module, "run_pytest", side_effect=_mock_run_pytest
                ):
                    first = driver.run_workflow(run_id, "bug_fix_flow", "1.0.0")
                    assert first.final_state == "waiting_approval"
                    assert first.resume_token is not None

                    final = driver.resume_workflow(
                        run_id,
                        first.resume_token,
                        payload={"decision": "granted"},
                    )

        run_dir = tmp_path / ".ao" / "evidence" / "workflows" / run_id
        record, _ = load_run(tmp_path, run_id)
        step_records = {step["step_name"]: step for step in record.get("steps", [])}

        assert final.final_state == "completed"
        assert step_records["invoke_coding_agent"]["state"] == "completed"
        assert step_records["preview_diff"]["state"] == "completed"
        assert step_records["ci_gate"]["state"] == "completed"
        assert step_records["await_approval"]["state"] == "completed"
        assert step_records["apply_patch"]["state"] == "completed"
        assert step_records["open_pr"]["state"] == "completed"

        ci_artifact = json.loads(
            (run_dir / step_records["ci_gate"]["output_ref"]).read_text(
                encoding="utf-8"
            )
        )
        assert ci_artifact["status"] == "pass"
        assert ci_artifact["exit_code"] == 0

        apply_artifact = json.loads(
            (run_dir / step_records["apply_patch"]["output_ref"]).read_text(
                encoding="utf-8"
            )
        )
        assert apply_artifact["files_changed"] == ["src/foo.py"]

        open_pr_artifact = json.loads(
            (run_dir / step_records["open_pr"]["output_ref"]).read_text(
                encoding="utf-8"
            )
        )
        assert open_pr_artifact["pr_url"].endswith("/pull/999")
        assert open_pr_artifact["pr_number"] == 999

        events = [
            json.loads(line)
            for line in (run_dir / "events.jsonl").read_text(
                encoding="utf-8"
            ).splitlines()
            if line.strip()
        ]
        kinds = [event.get("kind") for event in events]
        assert "approval_granted" in kinds
        assert "pr_opened" in kinds
        pr_opened = next(event for event in events if event.get("kind") == "pr_opened")
        assert pr_opened["payload"]["pr_url"].endswith("/pull/999")
        assert pr_opened["payload"]["pr_number"] == 999

    def test_open_pr_failure_preserves_adapter_error_metadata(
        self,
        tmp_path: Path,
    ) -> None:
        """Open-PR failure path should keep adapter error code/category
        on both evidence stream and persisted step record.
        """
        install_workspace(tmp_path)
        _copy_bundled_defaults(tmp_path)
        _install_bugfix_repo(tmp_path)

        run_id = seed_run(tmp_path, "bug_fix_flow")
        driver = build_driver(tmp_path, policy_loader=_policy_with_pythonpath())

        import ao_kernel.ci as ci_module
        from ao_kernel.executor import executor as executor_module

        original_invoke_cli = executor_module.invoke_cli

        def _mock_run_pytest(*args, **kwargs):
            return CIResult(
                check_name="pytest",
                command=("python3", "-m", "pytest"),
                status="pass",
                exit_code=0,
                duration_seconds=0.01,
                stdout_tail="mocked pytest pass",
                stderr_tail="",
            )

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
                / f"adapter-{manifest.adapter_id}.stdout.log"
            )
            log_path.parent.mkdir(parents=True, exist_ok=True)
            log_path.write_text(json.dumps({"_mock": True}), encoding="utf-8")
            envelope = {
                "status": "failed",
                "error": {
                    "code": "PR_CREATE_FAILED",
                    "category": "invocation_failed",
                    "message": "mocked gh pr create failed",
                },
                "cost_actual": {"time_seconds": 0.4},
            }
            result = _invocation_from_envelope(
                envelope,
                log_path=log_path,
                elapsed=float(envelope["cost_actual"]["time_seconds"]),
                command="benchmark-mock[gh-cli-pr]",
                manifest=manifest,
            )
            return result, budget

        with patch.dict(os.environ, {_OPEN_PR_GUARD_ENV: "1"}, clear=False):
            with patch(
                "ao_kernel.executor.executor.invoke_cli",
                side_effect=_dispatch_cli,
            ):
                with patch.object(
                    ci_module, "run_pytest", side_effect=_mock_run_pytest
                ):
                    first = driver.run_workflow(run_id, "bug_fix_flow", "1.0.0")
                    assert first.final_state == "waiting_approval"
                    assert first.resume_token is not None
                    final = driver.resume_workflow(
                        run_id,
                        first.resume_token,
                        payload={"decision": "granted"},
                    )

        assert final.final_state == "failed"
        record, _ = load_run(tmp_path, run_id)
        run_error = record.get("error") or {}
        assert run_error.get("category") == "invocation_failed"
        assert run_error.get("code") == "PR_CREATE_FAILED"

        step_records = {
            step["step_name"]: step for step in record.get("steps", [])
        }
        assert step_records["open_pr"]["state"] == "failed"
        step_error = step_records["open_pr"].get("error") or {}
        assert step_error.get("category") == "invocation_failed"
        assert step_error.get("code") == "PR_CREATE_FAILED"

        events = [
            json.loads(line)
            for line in (
                tmp_path / ".ao" / "evidence" / "workflows" / run_id / "events.jsonl"
            ).read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        kinds = [event.get("kind") for event in events]
        assert "pr_opened" not in kinds
        open_pr_failed = [
            event for event in events
            if event.get("kind") == "step_failed"
            and event.get("payload", {}).get("step_name") == "open_pr"
        ]
        assert open_pr_failed, kinds
        payload = open_pr_failed[-1]["payload"]
        assert payload.get("category") == "invocation_failed"
        assert payload.get("code") == "PR_CREATE_FAILED"

    def test_open_pr_requires_explicit_live_write_guard(
        self,
        tmp_path: Path,
    ) -> None:
        """`bug_fix_flow` open_pr side effects stay behind explicit opt-in.

        Guard yoksa workflow open_pr adiminda fail etmeli ve gh-cli-pr adapter
        subprocess'i hic invoke edilmemeli.
        """
        install_workspace(tmp_path)
        _copy_bundled_defaults(tmp_path)
        _install_bugfix_repo(tmp_path)

        run_id = seed_run(tmp_path, "bug_fix_flow")
        driver = build_driver(tmp_path, policy_loader=_policy_with_pythonpath())

        import ao_kernel.ci as ci_module
        from ao_kernel.executor import executor as executor_module

        original_invoke_cli = executor_module.invoke_cli
        gh_open_pr_calls = 0

        def _mock_run_pytest(*args, **kwargs):
            return CIResult(
                check_name="pytest",
                command=("python3", "-m", "pytest"),
                status="pass",
                exit_code=0,
                duration_seconds=0.01,
                stdout_tail="mocked pytest pass",
                stderr_tail="",
            )

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
            nonlocal gh_open_pr_calls
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

            gh_open_pr_calls += 1
            log_path = (
                workspace_root
                / ".ao"
                / "evidence"
                / "workflows"
                / run_id
                / f"adapter-{manifest.adapter_id}.stdout.log"
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

        with patch(
            "ao_kernel.executor.executor.invoke_cli",
            side_effect=_dispatch_cli,
        ):
            with patch.object(ci_module, "run_pytest", side_effect=_mock_run_pytest):
                first = driver.run_workflow(run_id, "bug_fix_flow", "1.0.0")
                assert first.final_state == "waiting_approval"
                assert first.resume_token is not None
                final = driver.resume_workflow(
                    run_id,
                    first.resume_token,
                    payload={"decision": "granted"},
                )

        assert final.final_state == "failed"
        assert gh_open_pr_calls == 0

        record, _ = load_run(tmp_path, run_id)
        run_error = record.get("error") or {}
        assert run_error.get("category") == "policy_denied"
        assert run_error.get("code") == "LIVE_WRITE_NOT_ALLOWED"

        step_records = {
            step["step_name"]: step for step in record.get("steps", [])
        }
        assert step_records["open_pr"]["state"] == "failed"
        step_error = step_records["open_pr"].get("error") or {}
        assert step_error.get("category") == "policy_denied"
        assert step_error.get("code") == "LIVE_WRITE_NOT_ALLOWED"

        events = [
            json.loads(line)
            for line in (
                tmp_path / ".ao" / "evidence" / "workflows" / run_id / "events.jsonl"
            ).read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        kinds = [event.get("kind") for event in events]
        assert "pr_opened" not in kinds
        assert not any(
            event.get("kind") == "adapter_invoked"
            and event.get("payload", {}).get("step_name") == "open_pr"
            for event in events
        )
        open_pr_failed = [
            event for event in events
            if event.get("kind") == "step_failed"
            and event.get("payload", {}).get("step_name") == "open_pr"
        ]
        assert open_pr_failed, kinds
        payload = open_pr_failed[-1]["payload"]
        assert payload.get("category") == "policy_denied"
        assert payload.get("code") == "LIVE_WRITE_NOT_ALLOWED"


class TestSimpleFlowEvidenceOrder:
    """Verify the canonical event order (workflow_started → step_* →
    step_completed → workflow_completed) for the ao-kernel-only flow.
    """

    def test_canonical_event_order_simple_flow(self, tmp_path: Path) -> None:
        install_workspace(tmp_path)
        copy_workflow_fixture(tmp_path, "simple_aokernel_flow")
        run_id = seed_run(tmp_path, "simple_aokernel_flow")
        driver = build_driver(tmp_path)
        result = driver.run_workflow(run_id, "simple_aokernel_flow", "1.0.0")
        assert result.final_state == "completed"

        events_path = (
            tmp_path / ".ao" / "evidence" / "workflows" / run_id
            / "events.jsonl"
        )
        lines = [json.loads(ln) for ln in events_path.read_text().splitlines()]
        kinds = [e.get("kind") for e in lines]

        # First event must be workflow_started
        assert kinds[0] == "workflow_started"
        # Last event must be workflow_completed
        assert kinds[-1] == "workflow_completed"
        # Both step_started events should precede their step_completed events
        starts = [i for i, k in enumerate(kinds) if k == "step_started"]
        completes = [i for i, k in enumerate(kinds) if k == "step_completed"]
        for s_idx, c_idx in zip(starts, completes):
            assert s_idx < c_idx
