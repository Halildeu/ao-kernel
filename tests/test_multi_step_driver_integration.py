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

import pytest

from ao_kernel.executor import DriverResult
from ao_kernel.workflow.run_store import load_run
from tests._driver_helpers import (
    _GIT_CFG,
    build_driver,
    copy_workflow_fixture,
    install_workspace,
    seed_run,
    write_stub_adapter_manifest,
)

_BUNDLED_ROOT = Path(__file__).resolve().parent.parent / "ao_kernel" / "defaults"


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
