"""Tests for eval harness — 6 deterministic heuristic-based quality checks."""

from __future__ import annotations


class TestJsonConformance:
    def test_valid_json_scores_1(self):
        from ao_kernel._internal.orchestrator.eval_harness import check_json_conformance
        result = check_json_conformance('{"key": "value"}')
        assert result.score == 1.0
        assert result.passed is True

    def test_invalid_json_scores_0(self):
        from ao_kernel._internal.orchestrator.eval_harness import check_json_conformance
        result = check_json_conformance('not json at all')
        assert result.score == 0.0
        assert result.passed is False

    def test_plain_text_not_json(self):
        from ao_kernel._internal.orchestrator.eval_harness import check_json_conformance
        result = check_json_conformance('Hello world, this is plain text.')
        assert result.score == 0.0

    def test_json_array_scores_low(self):
        from ao_kernel._internal.orchestrator.eval_harness import check_json_conformance
        result = check_json_conformance('[1, 2, 3]')
        assert result.score == 0.2
        assert result.passed is False

    def test_schema_validation_pass(self):
        from ao_kernel._internal.orchestrator.eval_harness import check_json_conformance
        schema = {"type": "object", "properties": {"key": {"type": "string"}}, "required": ["key"]}
        result = check_json_conformance('{"key": "value"}', schema=schema)
        assert result.score == 1.0
        assert result.passed is True

    def test_schema_validation_fail(self):
        from ao_kernel._internal.orchestrator.eval_harness import check_json_conformance
        schema = {"type": "object", "properties": {"key": {"type": "integer"}}, "required": ["key"]}
        result = check_json_conformance('{"key": "not_an_int"}', schema=schema)
        assert result.passed is False
        assert result.score < 1.0


class TestGroundedness:
    def test_grounded_output_passes(self):
        from ao_kernel._internal.orchestrator.eval_harness import check_groundedness
        context_sources = ["The deployment uses Python 3.11 with jsonschema validation"]
        output = "Python 3.11 is used for deployment with jsonschema"
        result = check_groundedness(output, context_sources=context_sources)
        assert result.score > 0.3
        assert result.passed is True

    def test_ungrounded_output_fails(self):
        from ao_kernel._internal.orchestrator.eval_harness import check_groundedness
        context_sources = ["The system uses Python 3.11"]
        output = "Java Spring Boot handles all microservice routing with Kubernetes orchestration"
        result = check_groundedness(output, context_sources=context_sources)
        assert result.score < 0.3

    def test_empty_context_handles_gracefully(self):
        from ao_kernel._internal.orchestrator.eval_harness import check_groundedness
        result = check_groundedness("some output", context_sources=[])
        assert isinstance(result.score, float)
        assert result.passed is True


class TestCitationCompleteness:
    def test_all_refs_found(self):
        from ao_kernel._internal.orchestrator.eval_harness import check_citation_completeness
        output = "According to RFC-1234 and ISO-9001, the process is valid."
        result = check_citation_completeness(output, expected_refs=["RFC-1234", "ISO-9001"])
        assert result.score == 1.0
        assert result.passed is True

    def test_missing_refs_fails(self):
        from ao_kernel._internal.orchestrator.eval_harness import check_citation_completeness
        output = "The process follows RFC-1234 guidelines."
        result = check_citation_completeness(output, expected_refs=["RFC-1234", "ISO-9001", "NIST-800"])
        assert result.score < 1.0

    def test_no_expected_refs(self):
        from ao_kernel._internal.orchestrator.eval_harness import check_citation_completeness
        result = check_citation_completeness("any output", expected_refs=[])
        assert result.score == 1.0
        assert result.passed is True

    def test_case_insensitive_match(self):
        from ao_kernel._internal.orchestrator.eval_harness import check_citation_completeness
        output = "See rfc-1234 for details."
        result = check_citation_completeness(output, expected_refs=["RFC-1234"])
        assert result.score == 1.0


class TestToolResultConsistency:
    def test_values_reflected_in_output(self):
        from ao_kernel._internal.orchestrator.eval_harness import check_tool_result_consistency
        tool_calls = [{"name": "get_status", "arguments": {}}]
        tool_results = [{"output": {"status": "success", "count": "42"}}]
        output = "The operation was a success, returning 42 results."
        result = check_tool_result_consistency(tool_calls, tool_results, output)
        assert result.score > 0.0
        assert result.passed is True

    def test_values_missing_from_output(self):
        from ao_kernel._internal.orchestrator.eval_harness import check_tool_result_consistency
        tool_calls = [{"name": "get_status", "arguments": {}}]
        tool_results = [{"output": {"status": "error", "message": "connection_timeout"}}]
        output = "Everything worked perfectly fine."
        result = check_tool_result_consistency(tool_calls, tool_results, output)
        assert result.score < 0.5

    def test_no_tool_calls(self):
        from ao_kernel._internal.orchestrator.eval_harness import check_tool_result_consistency
        result = check_tool_result_consistency([], [], "some output")
        assert result.passed is True
        assert result.score == 1.0


class TestRefusalCorrectness:
    def test_correct_refusal(self):
        from ao_kernel._internal.orchestrator.eval_harness import check_refusal_correctness
        output = "I cannot help with that request."
        result = check_refusal_correctness(output, should_refuse=True)
        assert result.passed is True

    def test_incorrect_non_refusal(self):
        from ao_kernel._internal.orchestrator.eval_harness import check_refusal_correctness
        output = "Sure, here is the information you requested about the topic."
        result = check_refusal_correctness(output, should_refuse=True)
        assert result.passed is False

    def test_correct_acceptance(self):
        from ao_kernel._internal.orchestrator.eval_harness import check_refusal_correctness
        output = "Here is the answer to your question."
        result = check_refusal_correctness(output, should_refuse=False)
        assert result.passed is True
        assert result.score == 1.0

    def test_incorrect_refusal(self):
        from ao_kernel._internal.orchestrator.eval_harness import check_refusal_correctness
        output = "I'm unable to provide that information."
        result = check_refusal_correctness(output, should_refuse=False)
        assert result.passed is False
        assert result.score == 0.3


class TestTruncationSafety:
    def test_complete_output_passes(self):
        from ao_kernel._internal.orchestrator.eval_harness import check_truncation_safety
        result = check_truncation_safety('{"key": "value"}')
        assert result.passed is True

    def test_mid_json_truncation_fails(self):
        from ao_kernel._internal.orchestrator.eval_harness import check_truncation_safety
        result = check_truncation_safety('{"key": "value", "nested": {"inner":')
        assert result.passed is False

    def test_complete_sentence_passes(self):
        from ao_kernel._internal.orchestrator.eval_harness import check_truncation_safety
        result = check_truncation_safety("This is a complete sentence.")
        assert result.passed is True

    def test_empty_output_fails(self):
        from ao_kernel._internal.orchestrator.eval_harness import check_truncation_safety
        result = check_truncation_safety("")
        assert result.passed is False
        assert result.score == 0.0

    def test_mid_sentence_truncation_long_text(self):
        from ao_kernel._internal.orchestrator.eval_harness import check_truncation_safety
        # Needs to be > 100 chars and end without sentence-ending punctuation
        text = "This is a very long sentence that keeps going and going " * 3 + "and then it just stops mid"
        result = check_truncation_safety(text)
        assert result.passed is False
        assert result.score == 0.5


class TestEvalSuite:
    def test_run_all_checks(self):
        from ao_kernel._internal.orchestrator.eval_harness import run_eval_suite
        results = run_eval_suite(
            '{"answer": "valid"}',
            context_sources=["The answer should be valid JSON."],
        )
        assert isinstance(results, list)
        assert len(results) >= 1

    def test_always_runs_truncation_and_refusal(self):
        from ao_kernel._internal.orchestrator.eval_harness import run_eval_suite
        results = run_eval_suite("Some plain text output.")
        check_ids = [r.check_id for r in results]
        assert "truncation_safety" in check_ids
        assert "refusal_correctness" in check_ids

    def test_json_check_only_when_json_like(self):
        from ao_kernel._internal.orchestrator.eval_harness import run_eval_suite
        results = run_eval_suite("Plain text, not JSON.")
        check_ids = [r.check_id for r in results]
        assert "json_conformance" not in check_ids

    def test_scorecard_aggregation(self):
        from ao_kernel._internal.orchestrator.eval_harness import run_eval_suite, eval_scorecard
        results = run_eval_suite("Some output text here.")
        scorecard = eval_scorecard(results)
        assert "avg_score" in scorecard
        assert "total_checks" in scorecard
        assert isinstance(scorecard["avg_score"], float)
        assert scorecard["total_checks"] == len(results)
        assert "passed" in scorecard
        assert "failed" in scorecard
        assert "all_passed" in scorecard

    def test_scorecard_empty_results(self):
        from ao_kernel._internal.orchestrator.eval_harness import eval_scorecard
        scorecard = eval_scorecard([])
        assert scorecard["total_checks"] == 0
        assert scorecard["avg_score"] == 0.0
        assert scorecard["all_passed"] is True
