"""`governed_bugfix` benchmark scenario (PR-B7).

Exercises `bug_fix_flow.v1.json` end-to-end under the mock
transport harness. Assertions follow `docs/BENCHMARK-SUITE.md §5.1`
with v5 scope-trim (cost_usd reconcile deferred → seed assertion
only; retry variant deferred; full mode deferred).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from ao_kernel.workflow.run_store import load_run

from tests.benchmarks.assertions import (
    assert_adapter_ok,
    assert_budget_axis_seeded,
    assert_capability_artifact,
    assert_workflow_completed,
    assert_workflow_failed,
    read_awaiting_human_token,
    resume_past_approval_gate,
)
from tests.benchmarks.fixtures import bug_envelopes
from tests.benchmarks.mock_transport import (
    _TransportError,
    mock_adapter_transport,
)


_WORKFLOW_ID = "governed_bugfix_bench"
_WORKFLOW_VERSION = "1.0.0"
_SCENARIO_ID = "governed_bugfix"


def _run_dir(workspace_root: Path, run_id: str) -> Path:
    return workspace_root / ".ao" / "evidence" / "workflows" / run_id


class TestHappyPath:
    def test_end_to_end_completes(
        self,
        workspace_root: Path,
        seeded_run,
        benchmark_driver,
        seeded_budget,
    ) -> None:
        run_id = seeded_run(_WORKFLOW_ID, version=_WORKFLOW_VERSION)
        # Bench variant exercises codex-stub only; gh-cli-pr
        # deferred to B7.1 (full bundled bug_fix_flow).
        canned = {
            (_SCENARIO_ID, "codex-stub", 1): bug_envelopes.coding_agent_happy(),
        }

        with mock_adapter_transport(canned, scenario_id=_SCENARIO_ID):
            first = benchmark_driver.run_workflow(
                run_id, _WORKFLOW_ID, _WORKFLOW_VERSION,
            )
            # `bug_fix_flow` carries an await_approval gate;
            # first run should exit awaiting_approval with a token.
            if first.resume_token is not None:
                token = first.resume_token
            else:
                token = read_awaiting_human_token(
                    _run_dir(workspace_root, run_id),
                )
            second = benchmark_driver.resume_workflow(
                run_id, token, payload={"decision": "granted"},
            )

        assert second.final_state == "completed"
        assert_workflow_completed(_run_dir(workspace_root, run_id))

        # Budget axis seeded (reconcile deferred to B7.1).
        record, _ = load_run(workspace_root, run_id)
        assert_budget_axis_seeded(record, "cost_usd", 10.0)

        # Adapter step records — only codex-stub step has
        # capability_output_refs (gh-cli-pr manifest has no
        # output_parse, v5 Codex W3 absorb).
        step_records = {
            step["step_name"]: step for step in record.get("steps", [])
        }
        coding_step = step_records.get("invoke_coding_agent")
        assert coding_step is not None, step_records
        assert_adapter_ok(coding_step)
        assert_capability_artifact(
            coding_step,
            "review_findings",
            run_dir=_run_dir(workspace_root, run_id),
        )
        assert_capability_artifact(
            coding_step,
            "commit_message",
            run_dir=_run_dir(workspace_root, run_id),
        )


class TestTransportError:
    def test_invoke_coding_agent_crash_fails_workflow(
        self,
        workspace_root: Path,
        seeded_run,
        benchmark_driver,
    ) -> None:
        run_id = seeded_run(_WORKFLOW_ID, version=_WORKFLOW_VERSION)
        canned = {
            # `_TransportError` sentinel → dispatcher raises
            # AdapterInvocationFailedError(reason="subprocess_crash")
            # → driver maps to error.category="adapter_crash".
            (_SCENARIO_ID, "codex-stub", 1): _TransportError,
        }

        with mock_adapter_transport(canned, scenario_id=_SCENARIO_ID):
            result = benchmark_driver.run_workflow(
                run_id, _WORKFLOW_ID, _WORKFLOW_VERSION,
            )

        assert result.final_state == "failed"
        assert_workflow_failed(
            _run_dir(workspace_root, run_id),
            expected_category="adapter_crash",
        )
