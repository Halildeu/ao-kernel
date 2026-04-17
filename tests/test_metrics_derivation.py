"""Tests for ``ao_kernel.metrics.derivation`` — PR-B5 C3.

Covers the events.jsonl → metric population pipeline: LLM spend with
``duration_ms`` (canonical source), usage-missing counter, policy
check outcome derivation, workflow started/terminal pairing,
cancelled-from-state branch (plan v4 Q3 A), claim takeover counter,
and fail-closed behaviour on corrupt JSONL.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from ao_kernel.metrics.derivation import (
    DerivationStats,
    derive_metrics_from_evidence,
)
from ao_kernel.metrics.errors import EvidenceSourceCorruptedError
from ao_kernel.metrics.policy import (
    LabelsAdvanced,
    MetricsPolicy,
    load_metrics_policy,
)
from ao_kernel.metrics.registry import build_registry


prometheus_client = pytest.importorskip("prometheus_client")


def _write_events(ws: Path, run_id: str, events: list[dict[str, Any]]) -> None:
    path = ws / ".ao" / "evidence" / "workflows" / run_id / "events.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(json.dumps(e, sort_keys=True) for e in events) + "\n",
        encoding="utf-8",
    )


def _bundled_policy(ws: Path) -> MetricsPolicy:
    return load_metrics_policy(ws)


def _build(policy: MetricsPolicy, *, include_llm: bool = True):
    built = build_registry(policy, include_llm_metrics=include_llm)
    assert built is not None
    return built


def _sample_values(family: Any) -> list[tuple[dict[str, str], float]]:
    """Extract (labels, value) pairs from a prometheus metric family.

    Skips the ``_created`` timestamp samples prometheus_client adds
    alongside every counter/histogram (those carry the registry start
    epoch which drowns out the actual counts in tests).
    """
    samples: list[tuple[dict[str, str], float]] = []
    for metric in family.collect():
        for sample in metric.samples:
            if sample.name.endswith("_created"):
                continue
            samples.append((dict(sample.labels), sample.value))
    return samples


class TestLLMSpendDerivation:
    def test_duration_ms_populates_histogram(
        self, tmp_path: Path
    ) -> None:
        """`llm_spend_recorded.duration_ms` is the canonical source
        for `ao_llm_call_duration_seconds` (plan v4 iter-2 fix)."""
        _write_events(
            tmp_path,
            "run-alpha",
            [
                {
                    "kind": "llm_spend_recorded",
                    "seq": 1,
                    "ts": "2026-04-17T10:00:00+00:00",
                    "payload": {
                        "provider_id": "anthropic",
                        "model": "claude-3-5",
                        "tokens_input": 100,
                        "tokens_output": 50,
                        "cached_tokens": 0,
                        "cost_usd": 0.003,
                        "duration_ms": 250.5,
                    },
                },
            ],
        )
        policy = _bundled_policy(tmp_path)
        built = _build(policy)
        stats = derive_metrics_from_evidence(tmp_path, built, policy)

        assert stats.llm_spend_counted == 1
        assert stats.duration_ms_missing == 0
        # Histogram sum sample records the observation (250.5 ms →
        # 0.2505 s). We find the `_sum` sample specifically rather
        # than scanning values because histogram samples include
        # bucket counters at every boundary.
        sum_samples = [
            (labels, value)
            for labels, value in _sample_values(built.llm_call_duration)
            if labels == {"provider": "anthropic"}
        ]
        # One of the samples with those labels should match the
        # observed duration (histogram `_sum`).
        assert any(
            v == pytest.approx(0.2505) for _, v in sum_samples
        )

    def test_tokens_counter_three_directions(
        self, tmp_path: Path
    ) -> None:
        """`tokens_input/tokens_output/cached_tokens` → direction
        label with three series."""
        _write_events(
            tmp_path,
            "run-alpha",
            [
                {
                    "kind": "llm_spend_recorded",
                    "ts": "2026-04-17T10:00:00+00:00",
                    "payload": {
                        "provider_id": "openai",
                        "model": "gpt-4o",
                        "tokens_input": 100,
                        "tokens_output": 40,
                        "cached_tokens": 20,
                        "cost_usd": 0.02,
                        "duration_ms": 800.0,
                    },
                },
            ],
        )
        policy = _bundled_policy(tmp_path)
        built = _build(policy)
        derive_metrics_from_evidence(tmp_path, built, policy)

        values = {
            labels["direction"]: value
            for labels, value in _sample_values(built.llm_tokens_used)
            if labels.get("provider") == "openai"
            and "direction" in labels
            and labels.get("direction") in {"input", "output", "cached"}
        }
        assert values == {"input": 100.0, "output": 40.0, "cached": 20.0}

    def test_cost_counter_accumulates(self, tmp_path: Path) -> None:
        _write_events(
            tmp_path,
            "run-alpha",
            [
                {
                    "kind": "llm_spend_recorded",
                    "ts": "2026-04-17T10:00:00+00:00",
                    "payload": {
                        "provider_id": "anthropic",
                        "tokens_input": 10,
                        "tokens_output": 5,
                        "cost_usd": 0.001,
                        "duration_ms": 100.0,
                    },
                },
                {
                    "kind": "llm_spend_recorded",
                    "ts": "2026-04-17T10:01:00+00:00",
                    "payload": {
                        "provider_id": "anthropic",
                        "tokens_input": 10,
                        "tokens_output": 5,
                        "cost_usd": 0.002,
                        "duration_ms": 100.0,
                    },
                },
            ],
        )
        policy = _bundled_policy(tmp_path)
        built = _build(policy)
        derive_metrics_from_evidence(tmp_path, built, policy)

        samples = _sample_values(built.llm_cost_usd)
        anthropic_total = next(
            v for labels, v in samples
            if labels == {"provider": "anthropic"}
        )
        assert anthropic_total == pytest.approx(0.003)

    def test_missing_duration_ms_skips_histogram(
        self, tmp_path: Path
    ) -> None:
        """Plan v4 R13: pre-B5 events without ``duration_ms`` are
        counted for tokens/cost but skipped for the duration
        histogram. Stats.duration_ms_missing surfaces the count."""
        _write_events(
            tmp_path,
            "run-beta",
            [
                {
                    "kind": "llm_spend_recorded",
                    "ts": "2026-04-17T10:00:00+00:00",
                    "payload": {
                        "provider_id": "anthropic",
                        "tokens_input": 1,
                        "tokens_output": 1,
                        "cost_usd": 0.0001,
                        # duration_ms absent
                    },
                },
            ],
        )
        policy = _bundled_policy(tmp_path)
        built = _build(policy)
        stats = derive_metrics_from_evidence(tmp_path, built, policy)

        assert stats.duration_ms_missing == 1
        # No observations recorded → all histogram buckets remain 0.
        samples = _sample_values(built.llm_call_duration)
        observed = [v for labels, v in samples if labels == {"provider": "anthropic"}]
        assert all(v == 0 for v in observed) or observed == []


class TestUsageMissingCounter:
    def test_llm_usage_missing_event_increments(
        self, tmp_path: Path
    ) -> None:
        _write_events(
            tmp_path,
            "run-gamma",
            [
                {
                    "kind": "llm_usage_missing",
                    "ts": "2026-04-17T10:00:00+00:00",
                    "payload": {
                        "provider_id": "anthropic",
                        "model": "claude-3-5",
                        "missing_fields": ["tokens_input"],
                    },
                },
            ],
        )
        policy = _bundled_policy(tmp_path)
        built = _build(policy)
        stats = derive_metrics_from_evidence(tmp_path, built, policy)

        assert stats.llm_usage_missing_counted == 1
        samples = _sample_values(built.llm_usage_missing)
        assert any(
            labels == {"provider": "anthropic"} and v == 1.0
            for labels, v in samples
        )


class TestPolicyCheckOutcome:
    def test_zero_violations_is_allow(self, tmp_path: Path) -> None:
        _write_events(
            tmp_path,
            "run-delta",
            [
                {
                    "kind": "policy_checked",
                    "ts": "2026-04-17T10:00:00+00:00",
                    "payload": {"violations_count": 0},
                },
                {
                    "kind": "policy_checked",
                    "ts": "2026-04-17T10:01:00+00:00",
                    "payload": {"violations_count": 2},
                },
            ],
        )
        policy = _bundled_policy(tmp_path)
        built = _build(policy)
        derive_metrics_from_evidence(tmp_path, built, policy)

        samples = dict(
            (labels["outcome"], value)
            for labels, value in _sample_values(built.policy_check)
            if "outcome" in labels
        )
        assert samples == {"allow": 1.0, "deny": 1.0}


class TestClaimTakeoverCounter:
    def test_takeover_event_increments(self, tmp_path: Path) -> None:
        _write_events(
            tmp_path,
            "run-epsilon",
            [
                {
                    "kind": "claim_takeover",
                    "ts": "2026-04-17T10:00:00+00:00",
                    "payload": {"resource_id": "res-1"},
                },
            ],
        )
        policy = _bundled_policy(tmp_path)
        built = _build(policy)
        stats = derive_metrics_from_evidence(tmp_path, built, policy)

        assert stats.claim_takeovers_counted == 1
        samples = _sample_values(built.claim_takeover)
        assert any(v == 1.0 for _, v in samples)


class TestWorkflowDuration:
    def test_started_completed_pair_records_duration(
        self, tmp_path: Path
    ) -> None:
        run_id = "00000000-0000-4000-8000-000000000001"
        _write_events(
            tmp_path,
            run_id,
            [
                {
                    "kind": "workflow_started",
                    "ts": "2026-04-17T10:00:00+00:00",
                    "payload": {"run_id": run_id},
                },
                {
                    "kind": "workflow_completed",
                    "ts": "2026-04-17T10:00:30+00:00",
                    "payload": {"run_id": run_id},
                },
            ],
        )
        policy = _bundled_policy(tmp_path)
        built = _build(policy)
        stats = derive_metrics_from_evidence(tmp_path, built, policy)

        assert stats.workflow_terminals_counted == 1
        samples = _sample_values(built.workflow_duration)
        # Histogram sum for completed ≈ 30 seconds.
        assert any(
            labels.get("final_state") == "completed"
            and v == pytest.approx(30.0)
            for labels, v in samples
        )

    def test_cancelled_from_state_completed_at(
        self, tmp_path: Path
    ) -> None:
        """Plan v4 Q3 A: cancelled runs are read from
        state.v1.json.completed_at because no terminal event exists."""
        from ao_kernel.workflow.run_store import create_run

        run_id = "00000000-0000-4000-8000-000000000002"
        create_run(
            tmp_path,
            run_id=run_id,
            workflow_id="bug_fix_flow",
            workflow_version="1.0.0",
            intent={"kind": "inline_prompt", "payload": "t"},
            budget={"fail_closed_on_exhaust": True},
            policy_refs=[
                "ao_kernel/defaults/policies/policy_worktree_profile.v1.json"
            ],
            evidence_refs=[
                f".ao/evidence/workflows/{run_id}/events.jsonl"
            ],
        )
        # Directly mutate state to cancelled with completed_at for
        # this derivation test (production code transitions via
        # runtime; here we pin the derivation branch).
        state_path = tmp_path / ".ao" / "runs" / run_id / "state.v1.json"
        record = json.loads(state_path.read_text(encoding="utf-8"))
        record["state"] = "cancelled"
        record["completed_at"] = "2026-04-17T10:00:00+00:00"
        record["created_at"] = "2026-04-17T09:58:00+00:00"
        # Recompute revision not needed for derivation (list_terminal_runs
        # does raw JSON read without schema validation).
        state_path.write_text(
            json.dumps(record, sort_keys=True), encoding="utf-8"
        )

        policy = _bundled_policy(tmp_path)
        built = _build(policy)
        stats = derive_metrics_from_evidence(tmp_path, built, policy)

        assert stats.cancelled_from_state == 1
        samples = _sample_values(built.workflow_duration)
        assert any(
            labels.get("final_state") == "cancelled"
            and v == pytest.approx(120.0)  # 2 minutes
            for labels, v in samples
        )


class TestFailClosedOnCorruptJSONL:
    def test_corrupt_events_jsonl_raises(self, tmp_path: Path) -> None:
        events_path = (
            tmp_path / ".ao" / "evidence" / "workflows" / "run-x" / "events.jsonl"
        )
        events_path.parent.mkdir(parents=True, exist_ok=True)
        events_path.write_text(
            '{"kind": "policy_checked"}\n{ not valid json\n',
            encoding="utf-8",
        )

        policy = _bundled_policy(tmp_path)
        built = _build(policy)
        with pytest.raises(EvidenceSourceCorruptedError):
            derive_metrics_from_evidence(tmp_path, built, policy)


class TestEmptyWorkspace:
    def test_no_evidence_dir_returns_empty_stats(
        self, tmp_path: Path
    ) -> None:
        """Missing `.ao/evidence/workflows/` → zero scans, no raise.
        Dormant-parity behaviour per plan v4 §2.3."""
        policy = _bundled_policy(tmp_path)
        built = _build(policy)
        stats = derive_metrics_from_evidence(tmp_path, built, policy)
        assert stats == DerivationStats()


class TestAdvancedLabels:
    def test_model_label_appears_when_allowlisted(
        self, tmp_path: Path
    ) -> None:
        _write_events(
            tmp_path,
            "run-zeta",
            [
                {
                    "kind": "llm_spend_recorded",
                    "ts": "2026-04-17T10:00:00+00:00",
                    "payload": {
                        "provider_id": "anthropic",
                        "model": "claude-3-5-sonnet",
                        "tokens_input": 10,
                        "tokens_output": 5,
                        "cost_usd": 0.001,
                        "duration_ms": 100.0,
                    },
                },
            ],
        )
        policy = MetricsPolicy(
            enabled=True,
            labels_advanced=LabelsAdvanced(
                enabled=True,
                allowlist=("model",),
            ),
        )
        built = _build(policy)
        derive_metrics_from_evidence(tmp_path, built, policy)

        samples = _sample_values(built.llm_cost_usd)
        assert any(
            labels.get("model") == "claude-3-5-sonnet"
            and labels.get("provider") == "anthropic"
            for labels, _ in samples
        )


class TestCostDisjunction:
    def test_llm_spend_events_ignored_when_llm_families_absent(
        self, tmp_path: Path
    ) -> None:
        """With `include_llm_metrics=False` (cost dormant), the
        registry has `llm_cost_usd=None`; spend events are parsed
        but produce no samples."""
        _write_events(
            tmp_path,
            "run-eta",
            [
                {
                    "kind": "llm_spend_recorded",
                    "ts": "2026-04-17T10:00:00+00:00",
                    "payload": {
                        "provider_id": "anthropic",
                        "tokens_input": 10,
                        "tokens_output": 5,
                        "cost_usd": 0.001,
                        "duration_ms": 100.0,
                    },
                },
            ],
        )
        policy = _bundled_policy(tmp_path)
        built = build_registry(policy, include_llm_metrics=False)
        assert built is not None
        stats = derive_metrics_from_evidence(tmp_path, built, policy)

        # Stats counter still increments only when spend counted
        # (returns False in cost-disjunction branch → stats = 0).
        assert stats.llm_spend_counted == 0
        # Textfile output confirms absence (other tests cover this).
