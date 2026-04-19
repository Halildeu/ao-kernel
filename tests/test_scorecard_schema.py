"""v3.5 D3: scorecard schema conformance tests (3 pins)."""

from __future__ import annotations

import pytest
from jsonschema import Draft202012Validator

from ao_kernel.config import load_default


@pytest.fixture
def scorecard_schema() -> dict:
    return load_default("schemas", "scorecard.schema.v1.json")


@pytest.fixture
def valid_scorecard() -> dict:
    return {
        "schema_version": "v1",
        "generated_at": "2026-04-18T10:00:00Z",
        "git_sha": "abc1234",
        "pr_number": None,
        "benchmarks": [
            {
                "scenario": "governed_bugfix",
                "status": "pass",
                "workflow_completed": True,
                "duration_ms": 120,
                "cost_consumed_usd": 0.01,
                "cost_source": "mock_shim",
                "review_score": None,
            },
        ],
    }


class TestScorecardSchema:
    def test_valid_scorecard_accepted(
        self,
        scorecard_schema: dict,
        valid_scorecard: dict,
    ) -> None:
        errors = list(
            Draft202012Validator(scorecard_schema).iter_errors(valid_scorecard),
        )
        assert errors == [], [err.message for err in errors]

    def test_unknown_top_level_key_rejected(
        self,
        scorecard_schema: dict,
        valid_scorecard: dict,
    ) -> None:
        valid_scorecard["unexpected_field"] = "nope"
        with pytest.raises(Exception):
            Draft202012Validator(scorecard_schema).validate(valid_scorecard)

    def test_benchmark_entry_forward_extensible(
        self,
        scorecard_schema: dict,
        valid_scorecard: dict,
    ) -> None:
        """benchmark_result has additionalProperties: true so future
        axes (e.g. memory_rss_kib) land without a schema bump."""
        valid_scorecard["benchmarks"][0]["future_axis"] = 42
        errors = list(
            Draft202012Validator(scorecard_schema).iter_errors(valid_scorecard),
        )
        assert errors == [], [err.message for err in errors]


class TestPolicySchema:
    def test_bundled_policy_matches_policy_schema(self) -> None:
        policy = load_default("policies", "policy_scorecard.v1.json")
        schema = load_default("schemas", "policy-scorecard.schema.v1.json")
        errors = list(Draft202012Validator(schema).iter_errors(policy))
        assert errors == [], [err.message for err in errors]
