"""Tests for _internal quality gate — gate pass/fail/disabled."""

from __future__ import annotations

from ao_kernel._internal.orchestrator.quality_gate import (
    QualityGateResult,
    _check_consistency,
    _check_output_not_empty,
    _check_regression,
    _check_schema_valid,
    get_gate_metrics,
    quality_gate_summary,
    run_quality_gates,
)


class TestOutputNotEmpty:
    def test_pass_sufficient_text(self):
        r = _check_output_not_empty({"text": "This is a valid output with enough chars"}, {})
        assert r.passed is True
        assert r.gate_id == "output_not_empty"

    def test_fail_too_short(self):
        r = _check_output_not_empty({"text": "hi"}, {"min_output_chars": 10})
        assert r.passed is False
        assert "too short" in r.reason

    def test_fail_not_dict(self):
        r = _check_output_not_empty("just a string", {})
        assert r.passed is False
        assert "not a dict" in r.reason

    def test_uses_summary_field(self):
        r = _check_output_not_empty({"summary": "A long summary text here"}, {})
        assert r.passed is True


class TestSchemaValid:
    def test_pass_dict_output(self):
        r = _check_schema_valid({"key": "value"}, {})
        assert r.passed is True

    def test_fail_non_dict(self):
        r = _check_schema_valid("string output", {})
        assert r.passed is False


class TestConsistencyCheck:
    def test_pass_no_previous(self):
        r = _check_consistency({"key": True}, {}, None)
        assert r.passed is True
        assert "no_previous" in r.reason

    def test_pass_no_contradiction(self):
        prev = [{"key": "enabled", "value": True}]
        r = _check_consistency({"enabled": True}, {}, prev)
        assert r.passed is True

    def test_fail_boolean_contradiction(self):
        prev = [{"key": "enabled", "value": True}]
        r = _check_consistency({"enabled": False}, {}, prev)
        assert r.passed is False
        assert "contradicts" in r.reason


class TestRegressionCheck:
    def test_pass_no_history(self):
        r = _check_regression({}, {}, None)
        assert r.passed is True

    def test_pass_no_regression(self):
        prev = [{"key": "version", "history": [{"value": "1.0"}]}]
        r = _check_regression({"version": "2.0"}, {}, prev)
        assert r.passed is True

    def test_fail_regression_detected(self):
        prev = [{"key": "version", "history": [{"value": "1.0"}]}]
        r = _check_regression({"version": "1.0"}, {}, prev)
        assert r.passed is False
        assert "regression" in r.reason


class TestRunQualityGates:
    def test_all_pass(self):
        output = {"text": "This is a comprehensive output with enough characters"}
        results = run_quality_gates(
            output=output,
            policy={"enabled": True, "gates": {}},
        )
        assert all(r.passed for r in results)

    def test_disabled_returns_pass(self):
        results = run_quality_gates(
            output={},
            policy={"enabled": False},
        )
        assert len(results) == 1
        assert results[0].passed is True
        assert "disabled" in results[0].reason

    def test_gate_metrics_incremented(self):
        run_quality_gates(
            output={"text": "Valid output text here"},
            policy={"enabled": True, "gates": {}},
        )
        metrics = get_gate_metrics()
        assert any("pass" in k for k in metrics)


class TestQualityGateSummary:
    def test_summary_all_pass(self):
        results = [
            QualityGateResult(True, "schema_valid", "pass", ""),
            QualityGateResult(True, "output_not_empty", "pass", ""),
        ]
        s = quality_gate_summary(results)
        assert s["total_gates"] == 2
        assert s["passed"] == 2
        assert s["failed"] == 0
        assert s["all_passed"] is True

    def test_summary_with_failure(self):
        results = [
            QualityGateResult(True, "schema_valid", "pass", ""),
            QualityGateResult(False, "output_not_empty", "reject", "too short"),
        ]
        s = quality_gate_summary(results)
        assert s["all_passed"] is False
        assert s["failed"] == 1
        assert s["worst_action"] == "reject"
        assert len(s["failures"]) == 1
