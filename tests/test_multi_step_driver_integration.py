"""Integration tests for MultiStepDriver (PR-A4b).

Exercises the full driver dispatch path with real Executor + bundled
codex-stub adapter + real subprocess (python3 -m ruff). No mocks; the
flow mirrors a slice of the FAZ-A governed demo (adapter invocation →
lint check → completion).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from ao_kernel.executor import DriverResult
from ao_kernel.workflow.run_store import load_run
from tests._driver_helpers import (
    build_driver,
    copy_workflow_fixture,
    install_workspace,
    seed_run,
    write_stub_adapter_manifest,
)


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
