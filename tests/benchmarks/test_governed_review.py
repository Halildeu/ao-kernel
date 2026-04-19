"""`governed_review` benchmark scenario (PR-B7).

Exercises `review_ai_flow.v1.json` end-to-end. The canned happy
envelope carries BOTH `review_findings` and `commit_message`
payloads because `codex-stub` manifest declares both as
`output_parse` rules; missing-payload negative variant pins the
real walker's `AdapterOutputParseError` path (→
`error.category="output_parse_failed"`).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from ao_kernel.workflow.run_store import load_run

from tests.benchmarks.assertions import (
    assert_adapter_ok,
    assert_capability_artifact,
    assert_cost_consumed,
    assert_review_score,
    assert_workflow_completed,
    assert_workflow_failed,
    read_awaiting_human_token,
)
from tests.benchmarks.fixtures import review_envelopes
from tests.benchmarks.mock_transport import mock_adapter_transport


_WORKFLOW_ID = "review_ai_flow"
_WORKFLOW_VERSION = "1.0.0"
_SCENARIO_ID = "governed_review"
_REVIEW_SCHEMA = (
    Path(__file__).resolve().parents[2] / "ao_kernel" / "defaults" / "schemas" / "review-findings.schema.v1.json"
)
_EXPECTED_MIN_SCORE = 0.5


def _run_dir(workspace_root: Path, run_id: str) -> Path:
    return workspace_root / ".ao" / "evidence" / "workflows" / run_id


class TestHappyPath:
    @pytest.mark.scorecard_primary
    def test_review_findings_flow_completes(
        self,
        workspace_root: Path,
        seeded_run,
        benchmark_driver,
        benchmark_primary_sidecar,
    ) -> None:
        run_id = seeded_run(_WORKFLOW_ID, version=_WORKFLOW_VERSION)
        canned = {
            (_SCENARIO_ID, "codex-stub", 1): review_envelopes.review_agent_happy(
                score=0.85,
            ),
        }

        with mock_adapter_transport(canned, scenario_id=_SCENARIO_ID):
            first = benchmark_driver.run_workflow(
                run_id,
                _WORKFLOW_ID,
                _WORKFLOW_VERSION,
            )
            # `review_ai_flow` ends on await_acknowledgement; flow
            # should pause with a resume_token.
            if first.resume_token is not None:
                token = first.resume_token
            else:
                token = read_awaiting_human_token(
                    _run_dir(workspace_root, run_id),
                )
            second = benchmark_driver.resume_workflow(
                run_id,
                token,
                payload={"decision": "granted"},
            )

        assert second.final_state == "completed"
        run_dir = _run_dir(workspace_root, run_id)
        assert_workflow_completed(run_dir)

        record, _ = load_run(workspace_root, run_id)
        step_records = {step["step_name"]: step for step in record.get("steps", [])}
        review_step = step_records["invoke_review_agent"]
        assert_adapter_ok(review_step)

        artifact = assert_capability_artifact(
            review_step,
            "review_findings",
            run_dir=run_dir,
            schema_path=_REVIEW_SCHEMA,
        )
        assert_review_score(artifact, expected_min_score=_EXPECTED_MIN_SCORE)

        # Scorecard primary sidecar — publishes run_dir + the concrete
        # `review_findings` artefact path so the collector can extract
        # `review_score` without rescanning capability_output_refs.
        # `run_state_path` points at the canonical state file for
        # `cost_consumed_usd` extraction.
        refs = review_step.get("capability_output_refs") or {}
        findings_ref = refs.get("review_findings")
        findings_path = run_dir / findings_ref if findings_ref else None
        benchmark_primary_sidecar(
            _SCENARIO_ID,
            run_dir,
            run_state_path=workspace_root / ".ao" / "runs" / run_id / "state.v1.json",
            review_findings_path=findings_path,
        )

    @pytest.mark.parametrize(
        "score,min_threshold,should_pass",
        [
            (0.9, 0.8, True),
            (0.4, 0.5, False),
        ],
    )
    def test_score_threshold_parametrised(
        self,
        workspace_root: Path,
        seeded_run,
        benchmark_driver,
        score: float,
        min_threshold: float,
        should_pass: bool,
    ) -> None:
        run_id = seeded_run(_WORKFLOW_ID, version=_WORKFLOW_VERSION)
        canned = {
            (_SCENARIO_ID, "codex-stub", 1): review_envelopes.review_agent_happy(
                score=score,
            ),
        }

        with mock_adapter_transport(canned, scenario_id=_SCENARIO_ID):
            first = benchmark_driver.run_workflow(
                run_id,
                _WORKFLOW_ID,
                _WORKFLOW_VERSION,
            )
            token = first.resume_token or read_awaiting_human_token(
                _run_dir(workspace_root, run_id),
            )
            benchmark_driver.resume_workflow(
                run_id,
                token,
                payload={"decision": "granted"},
            )

        record, _ = load_run(workspace_root, run_id)
        review_step = next(step for step in record["steps"] if step["step_name"] == "invoke_review_agent")
        artifact = assert_capability_artifact(
            review_step,
            "review_findings",
            run_dir=_run_dir(workspace_root, run_id),
        )
        if should_pass:
            assert_review_score(artifact, expected_min_score=min_threshold)
        else:
            with pytest.raises(AssertionError, match="below threshold"):
                assert_review_score(artifact, expected_min_score=min_threshold)


class TestCostReconcile:
    """PR-B7.1: verify the benchmark-only cost shim drains the
    `cost_usd` axis. The real adapter transport path does not
    reconcile cost_usd (FAZ-C PR-C3); this test pins the
    benchmark-layer contract instead."""

    def test_cost_usd_drained_after_happy_review(
        self,
        workspace_root: Path,
        seeded_run,
        benchmark_driver,
    ) -> None:
        run_id = seeded_run(_WORKFLOW_ID, version=_WORKFLOW_VERSION)
        canned = {
            (_SCENARIO_ID, "codex-stub", 1): review_envelopes.review_agent_happy(
                score=0.85,
            ),
        }

        with mock_adapter_transport(canned, scenario_id=_SCENARIO_ID):
            first = benchmark_driver.run_workflow(
                run_id,
                _WORKFLOW_ID,
                _WORKFLOW_VERSION,
            )
            token = first.resume_token or read_awaiting_human_token(
                _run_dir(workspace_root, run_id),
            )
            benchmark_driver.resume_workflow(
                run_id,
                token,
                payload={"decision": "granted"},
            )

        record, _ = load_run(workspace_root, run_id)
        consumed = assert_cost_consumed(record, "cost_usd", min_consumed=0.0)
        # The envelope reports 0.12 USD; the shim should drain by
        # exactly that amount (no other adapter call for this
        # scenario).
        assert abs(consumed - 0.12) < 1e-9, f"unexpected cost_usd consumption: {consumed}"


class TestMissingPayload:
    def test_missing_review_findings_fails_workflow(
        self,
        workspace_root: Path,
        seeded_run,
        benchmark_driver,
    ) -> None:
        run_id = seeded_run(_WORKFLOW_ID, version=_WORKFLOW_VERSION)
        canned = {
            (_SCENARIO_ID, "codex-stub", 1): review_envelopes.review_agent_missing_payload(),
        }

        with mock_adapter_transport(canned, scenario_id=_SCENARIO_ID):
            result = benchmark_driver.run_workflow(
                run_id,
                _WORKFLOW_ID,
                _WORKFLOW_VERSION,
            )

        assert result.final_state == "failed"
        assert_workflow_failed(
            _run_dir(workspace_root, run_id),
            expected_category="output_parse_failed",
        )
