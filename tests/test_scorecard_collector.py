"""v3.5 D3: scorecard collector + pytest plugin tests (11 pins)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from ao_kernel._internal.scorecard.collector import (
    DEFAULT_OUTPUT_FILENAME,
    BenchmarkResult,
    PrimarySidecar,
    ScorecardCollectorError,
    ScorecardRegistry,
    build_result,
    build_scorecard,
    finalize_session,
    resolve_output_path,
)


def _write_events(run_dir: Path, events: list[dict]) -> None:
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "events.jsonl").write_text(
        "\n".join(json.dumps(event) for event in events) + "\n",
        encoding="utf-8",
    )


def _write_run_state(path: Path, cost_limit: float, remaining: float) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "budget": {
                    "cost_usd": {"limit": cost_limit, "remaining": remaining},
                },
            }
        ),
        encoding="utf-8",
    )


def _write_review_findings(path: Path, score: float | None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload: dict = {"findings": [], "summary": "ok"}
    if score is not None:
        payload["score"] = score
    path.write_text(json.dumps(payload), encoding="utf-8")


class TestBuildResult:
    def test_happy_path_extraction(self, tmp_path: Path) -> None:
        events = [
            {"kind": "workflow_started", "ts": "2026-04-18T10:00:00+00:00"},
            {"kind": "step_completed", "ts": "2026-04-18T10:00:01+00:00"},
            {"kind": "workflow_completed", "ts": "2026-04-18T10:00:02+00:00"},
        ]
        _write_events(tmp_path / "run", events)
        state = tmp_path / "state.json"
        _write_run_state(state, 10.0, 9.5)
        findings = tmp_path / "review.json"
        _write_review_findings(findings, 0.88)

        sidecar = PrimarySidecar(
            scenario_id="governed_review",
            run_dir=tmp_path / "run",
            run_state_path=state,
            review_findings_path=findings,
        )
        result = build_result(sidecar)
        assert result.scenario == "governed_review"
        assert result.status == "pass"
        assert result.workflow_completed is True
        assert result.duration_ms == 2000
        assert result.cost_consumed_usd == pytest.approx(0.5)
        assert result.cost_source == "mock_shim"
        assert result.review_score == pytest.approx(0.88)

    def test_missing_workflow_completed_is_fail(self, tmp_path: Path) -> None:
        events = [
            {"kind": "workflow_started", "ts": "2026-04-18T10:00:00+00:00"},
        ]
        _write_events(tmp_path / "run", events)
        sidecar = PrimarySidecar(
            scenario_id="governed_bugfix",
            run_dir=tmp_path / "run",
        )
        result = build_result(sidecar)
        assert result.workflow_completed is False
        assert result.status == "fail"

    def test_workflow_failed_event_forces_fail(self, tmp_path: Path) -> None:
        events = [
            {"kind": "workflow_completed", "ts": "2026-04-18T10:00:00+00:00"},
            {"kind": "workflow_failed", "ts": "2026-04-18T10:00:01+00:00"},
        ]
        _write_events(tmp_path / "run", events)
        sidecar = PrimarySidecar(
            scenario_id="governed_bugfix",
            run_dir=tmp_path / "run",
        )
        result = build_result(sidecar)
        assert result.status == "fail"

    def test_missing_budget_gives_null_cost(self, tmp_path: Path) -> None:
        events = [{"kind": "workflow_completed", "ts": "2026-04-18T10:00:00+00:00"}]
        _write_events(tmp_path / "run", events)
        sidecar = PrimarySidecar(
            scenario_id="governed_bugfix",
            run_dir=tmp_path / "run",
            run_state_path=tmp_path / "missing.json",
        )
        result = build_result(sidecar)
        assert result.cost_consumed_usd is None
        assert result.cost_source is None

    def test_missing_review_findings_gives_null_score(self, tmp_path: Path) -> None:
        events = [{"kind": "workflow_completed", "ts": "2026-04-18T10:00:00+00:00"}]
        _write_events(tmp_path / "run", events)
        sidecar = PrimarySidecar(
            scenario_id="governed_review",
            run_dir=tmp_path / "run",
            review_findings_path=tmp_path / "missing.json",
        )
        result = build_result(sidecar)
        assert result.review_score is None

    def test_empty_run_dir(self, tmp_path: Path) -> None:
        (tmp_path / "empty").mkdir()
        sidecar = PrimarySidecar(
            scenario_id="governed_bugfix",
            run_dir=tmp_path / "empty",
        )
        result = build_result(sidecar)
        assert result.workflow_completed is False
        assert result.status == "fail"
        assert result.duration_ms is None


class TestBuildScorecard:
    def test_scorecard_sorted_by_scenario(self, tmp_path: Path) -> None:
        results = [
            BenchmarkResult("governed_review", "pass", True, 50, 0.01, "mock_shim", 0.8),
            BenchmarkResult("governed_bugfix", "pass", True, 75, 0.005, "mock_shim", None),
        ]
        scorecard = build_scorecard(results)
        assert scorecard["benchmarks"][0]["scenario"] == "governed_bugfix"
        assert scorecard["benchmarks"][1]["scenario"] == "governed_review"
        assert scorecard["schema_version"] == "v1"
        assert "git_sha" in scorecard
        assert "generated_at" in scorecard

    def test_cost_source_always_populated_when_cost_present(self) -> None:
        """Canonical marker pin #2: cost_source='mock_shim' v1."""
        results = [
            BenchmarkResult("s", "pass", True, 10, 0.01, "mock_shim", None),
        ]
        scorecard = build_scorecard(results)
        assert scorecard["benchmarks"][0]["cost_source"] == "mock_shim"


class TestFinalizeSession:
    def test_happy_path_writes_file(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        registry = ScorecardRegistry()
        events = [{"kind": "workflow_completed", "ts": "2026-04-18T10:00:00+00:00"}]
        _write_events(tmp_path / "rg", events)
        registry.record(PrimarySidecar("governed_bugfix", tmp_path / "rg"))
        events2 = [{"kind": "workflow_completed", "ts": "2026-04-18T10:00:00+00:00"}]
        _write_events(tmp_path / "rv", events2)
        registry.record(PrimarySidecar("governed_review", tmp_path / "rv"))

        out = tmp_path / "scorecard.json"
        written = finalize_session(registry, out)
        assert written == out
        payload = json.loads(out.read_text())
        assert [entry["scenario"] for entry in payload["benchmarks"]] == [
            "governed_bugfix",
            "governed_review",
        ]

    def test_duplicate_primary_marker_fails_session(self, tmp_path: Path) -> None:
        """Canonical marker pin #1: duplicate → session-fail diagnostic."""
        registry = ScorecardRegistry()
        _write_events(tmp_path / "a", [{"kind": "workflow_completed"}])
        _write_events(tmp_path / "b", [{"kind": "workflow_completed"}])
        registry.record(PrimarySidecar("governed_review", tmp_path / "a"))
        registry.record(PrimarySidecar("governed_review", tmp_path / "b"))
        with pytest.raises(ScorecardCollectorError, match="Duplicate"):
            finalize_session(registry, tmp_path / "out.json")
        assert not (tmp_path / "out.json").exists()

    def test_zero_primary_fails_when_expected_non_empty(
        self,
        tmp_path: Path,
    ) -> None:
        """AGREE iter-2 tighten #3 — missing primary also fail-closed."""
        registry = ScorecardRegistry()
        with pytest.raises(ScorecardCollectorError, match="Zero"):
            finalize_session(
                registry,
                tmp_path / "out.json",
                expected_scenarios=frozenset({"governed_review"}),
            )

    def test_zero_primary_noop_when_expected_empty(self, tmp_path: Path) -> None:
        """Empty expected-set → no-op, no scorecard produced."""
        registry = ScorecardRegistry()
        result = finalize_session(
            registry,
            tmp_path / "out.json",
            expected_scenarios=frozenset(),
        )
        assert result is None
        assert not (tmp_path / "out.json").exists()


class TestOutputPath:
    def test_env_var_override(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        target = tmp_path / "custom" / "card.json"
        monkeypatch.setenv("AO_SCORECARD_OUTPUT", str(target))
        assert resolve_output_path() == target

    def test_default_path(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.delenv("AO_SCORECARD_OUTPUT", raising=False)
        assert resolve_output_path(tmp_path) == tmp_path / DEFAULT_OUTPUT_FILENAME
