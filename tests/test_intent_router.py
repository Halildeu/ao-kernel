"""Tests for ``ao_kernel.workflow.intent_router``.

Covers keyword / regex / combined match semantics, priority-ordered
evaluation, duplicate rule_id rejection, regex compile failure, no-match
fallback semantics (error_on_no_match / use_default / llm_fallback),
and the bundled default rules load path.
"""

from __future__ import annotations

import re
from typing import Any

import pytest

from ao_kernel.workflow import (
    ClassificationResult,
    IntentRouter,
    IntentRule,
    IntentRulesCorruptedError,
    compile_rules_from_dict,
    load_default_rules,
)


def _rule(
    *,
    rule_id: str,
    workflow_id: str = "demo_flow",
    priority: int = 100,
    match_type: str = "keyword",
    keywords: tuple[str, ...] = (),
    regex_any: tuple[re.Pattern[str], ...] = (),
    confidence: float = 0.8,
) -> IntentRule:
    return IntentRule(
        rule_id=rule_id,
        workflow_id=workflow_id,
        workflow_version=None,
        priority=priority,
        match_type=match_type,  # type: ignore[arg-type]
        keywords=keywords,
        regex_any=regex_any,
        confidence=confidence,
        description="",
    )


# ---------------------------------------------------------------------------
# Bundled rules load
# ---------------------------------------------------------------------------


class TestBundledRules:
    def test_load_default_rules_returns_rules(self) -> None:
        rules, default_wf, strategy = load_default_rules()
        assert len(rules) >= 1
        assert strategy == "error_on_no_match"
        assert default_wf is None

    def test_bundled_rules_classify_bug_fix(self) -> None:
        router = IntentRouter()
        result = router.classify("Please fix the broken authentication bug")
        assert result == ClassificationResult(
            workflow_id="bug_fix_flow",
            workflow_version=None,
            confidence=0.82,
            matched_rule_id="bug_fix_keywords",
            match_type="keyword",
        )


# ---------------------------------------------------------------------------
# Match semantics
# ---------------------------------------------------------------------------


class TestKeywordMatching:
    def test_whole_word_match(self) -> None:
        rule = _rule(rule_id="r1", keywords=("bug",))
        router = IntentRouter(rules=[rule])
        result = router.classify("We have a bug in production")
        assert result == ClassificationResult(
            workflow_id="demo_flow",
            workflow_version=None,
            confidence=0.8,
            matched_rule_id="r1",
            match_type="keyword",
        )

    def test_substring_does_not_match(self) -> None:
        rule = _rule(rule_id="r1", keywords=("bug",))
        router = IntentRouter(rules=[rule])
        # "debugger" contains "bug" but boundary chars disallow partial.
        result = router.classify("running the debugger on main")
        assert result is None

    def test_case_insensitive(self) -> None:
        rule = _rule(rule_id="r1", keywords=("BUG",))
        router = IntentRouter(rules=[rule])
        result = router.classify("tiny bug today")
        assert result == ClassificationResult(
            workflow_id="demo_flow",
            workflow_version=None,
            confidence=0.8,
            matched_rule_id="r1",
            match_type="keyword",
        )

    def test_keyword_with_dash_boundary(self) -> None:
        """Dashed keyword matches the dashed token exactly."""
        rule = _rule(rule_id="r1", keywords=("bug-fix",))
        router = IntentRouter(rules=[rule])
        result = router.classify("we filed a bug-fix yesterday")
        assert result == ClassificationResult(
            workflow_id="demo_flow",
            workflow_version=None,
            confidence=0.8,
            matched_rule_id="r1",
            match_type="keyword",
        )

    def test_keyword_with_underscore_is_part_of_word(self) -> None:
        """Underscore is `\\w`, so 'bug' does match 'bug_fix' token."""
        rule = _rule(rule_id="r1", keywords=("bug_fix",))
        router = IntentRouter(rules=[rule])
        result = router.classify("tag: bug_fix pending")
        assert result == ClassificationResult(
            workflow_id="demo_flow",
            workflow_version=None,
            confidence=0.8,
            matched_rule_id="r1",
            match_type="keyword",
        )


class TestRegexMatching:
    def test_regex_match(self) -> None:
        pattern = re.compile(r"^fix:", re.IGNORECASE)
        rule = _rule(
            rule_id="r1",
            match_type="regex",
            regex_any=(pattern,),
        )
        router = IntentRouter(rules=[rule])
        result = router.classify("Fix: resolve crash in worker")
        assert result == ClassificationResult(
            workflow_id="demo_flow",
            workflow_version=None,
            confidence=0.8,
            matched_rule_id="r1",
            match_type="regex",
        )

    def test_regex_miss_returns_none(self) -> None:
        pattern = re.compile(r"^fix:", re.IGNORECASE)
        rule = _rule(
            rule_id="r1",
            match_type="regex",
            regex_any=(pattern,),
        )
        router = IntentRouter(rules=[rule])
        assert router.classify("feat: add login") is None


class TestCombinedMatching:
    def test_combined_requires_both(self) -> None:
        rule = _rule(
            rule_id="r1",
            match_type="combined",
            keywords=("urgent",),
            regex_any=(re.compile(r"^fix:", re.IGNORECASE),),
        )
        router = IntentRouter(rules=[rule])
        # Both conditions met.
        assert router.classify("Fix: urgent crash in worker") == ClassificationResult(
            workflow_id="demo_flow",
            workflow_version=None,
            confidence=0.8,
            matched_rule_id="r1",
            match_type="combined",
        )
        # Keyword only — no regex match.
        assert router.classify("urgent change needed") is None
        # Regex only — no keyword match.
        assert router.classify("Fix: small typo") is None


# ---------------------------------------------------------------------------
# Priority & determinism
# ---------------------------------------------------------------------------


class TestPriority:
    def test_higher_priority_wins(self) -> None:
        low = _rule(rule_id="low", keywords=("fix",), priority=1, confidence=0.1)
        high = _rule(
            rule_id="high",
            keywords=("fix",),
            priority=10,
            workflow_id="other_flow",
            confidence=0.9,
        )
        router = IntentRouter(rules=[low, high])
        result = router.classify("please fix the crash")
        assert result == ClassificationResult(
            workflow_id="other_flow",
            workflow_version=None,
            confidence=0.9,
            matched_rule_id="high",
            match_type="keyword",
        )

    def test_duplicate_priority_match_raises(self) -> None:
        r1 = _rule(rule_id="a", keywords=("fix",), priority=5)
        r2 = _rule(rule_id="b", keywords=("fix",), priority=5)
        router = IntentRouter(rules=[r1, r2])
        with pytest.raises(IntentRulesCorruptedError) as ei:
            router.classify("fix the issue")
        assert ei.value.reason == "duplicate_priority_match"


# ---------------------------------------------------------------------------
# Fallback strategies
# ---------------------------------------------------------------------------


class TestFallback:
    def test_error_on_no_match_returns_none(self) -> None:
        rule = _rule(rule_id="r1", keywords=("fix",))
        router = IntentRouter(
            rules=[rule], fallback_strategy="error_on_no_match"
        )
        assert router.classify("unrelated text") is None

    def test_use_default_requires_non_null_default(self) -> None:
        rule = _rule(rule_id="r1", keywords=("fix",))
        with pytest.raises(ValueError, match="default_workflow_id"):
            IntentRouter(
                rules=[rule],
                fallback_strategy="use_default",
                default_workflow_id=None,
            )

    def test_use_default_returns_default_result(self) -> None:
        rule = _rule(rule_id="r1", keywords=("fix",))
        router = IntentRouter(
            rules=[rule],
            fallback_strategy="use_default",
            default_workflow_id="fallback_flow",
        )
        result = router.classify("unrelated text")
        assert result == ClassificationResult(
            workflow_id="fallback_flow",
            workflow_version=None,
            confidence=0.0,
            matched_rule_id="__default__",
            match_type="default",
        )

    def test_llm_fallback_raises_classification_error_when_llm_missing(self) -> None:
        """PR-A6: llm_fallback now tries to call LLM; without [llm]
        extra installed in test env it raises IntentClassificationError
        (not NotImplementedError)."""
        from ao_kernel.workflow.errors import IntentClassificationError

        rule = _rule(rule_id="r1", keywords=("fix",))
        router = IntentRouter(
            rules=[rule],
            fallback_strategy="llm_fallback",
        )
        with pytest.raises(IntentClassificationError):
            router.classify("unrelated text")


# ---------------------------------------------------------------------------
# compile_rules_from_dict / load-time invariants
# ---------------------------------------------------------------------------


class TestCompileInvariants:
    def test_duplicate_rule_id_rejected(self) -> None:
        payload = {
            "rules": [
                {
                    "rule_id": "dup",
                    "workflow_id": "wf_demo",
                    "priority": 1,
                    "match_type": "keyword",
                    "keywords": ["x"],
                    "confidence": 0.5,
                },
                {
                    "rule_id": "dup",
                    "workflow_id": "wf_demo",
                    "priority": 2,
                    "match_type": "keyword",
                    "keywords": ["y"],
                    "confidence": 0.5,
                },
            ],
            "default_workflow_id": None,
            "fallback_strategy": "error_on_no_match",
        }
        with pytest.raises(IntentRulesCorruptedError) as ei:
            compile_rules_from_dict(payload)
        assert ei.value.reason == "duplicate_rule_id"

    def test_regex_compile_failure_rejected(self) -> None:
        payload = {
            "rules": [
                {
                    "rule_id": "r",
                    "workflow_id": "wf_demo",
                    "priority": 1,
                    "match_type": "regex",
                    "regex_any": ["(unterminated"],
                    "confidence": 0.5,
                }
            ],
            "default_workflow_id": None,
            "fallback_strategy": "error_on_no_match",
        }
        with pytest.raises(IntentRulesCorruptedError) as ei:
            compile_rules_from_dict(payload)
        assert ei.value.reason == "regex_compile"

    def test_schema_invalid_missing_keywords_for_keyword_type(self) -> None:
        payload: dict[str, Any] = {
            "rules": [
                {
                    "rule_id": "r",
                    "workflow_id": "wf_demo",
                    "priority": 1,
                    "match_type": "keyword",
                    "confidence": 0.5,
                }
            ],
            "default_workflow_id": None,
            "fallback_strategy": "error_on_no_match",
        }
        with pytest.raises(IntentRulesCorruptedError) as ei:
            compile_rules_from_dict(payload)
        assert ei.value.reason == "schema_invalid"

    def test_schema_enforces_use_default_requires_default_id(self) -> None:
        payload: dict[str, Any] = {
            "rules": [
                {
                    "rule_id": "r",
                    "workflow_id": "wf_demo",
                    "priority": 1,
                    "match_type": "keyword",
                    "keywords": ["x"],
                    "confidence": 0.5,
                }
            ],
            "default_workflow_id": None,
            "fallback_strategy": "use_default",
        }
        with pytest.raises(IntentRulesCorruptedError) as ei:
            compile_rules_from_dict(payload)
        assert ei.value.reason == "schema_invalid"

    def test_optional_workflow_version_captured(self) -> None:
        payload = {
            "rules": [
                {
                    "rule_id": "r",
                    "workflow_id": "wf_demo",
                    "workflow_version": "1.2.3",
                    "priority": 1,
                    "match_type": "keyword",
                    "keywords": ["x"],
                    "confidence": 0.5,
                }
            ],
            "default_workflow_id": None,
            "fallback_strategy": "error_on_no_match",
        }
        rules, _, _ = compile_rules_from_dict(payload)
        assert rules[0].workflow_version == "1.2.3"


class TestClassificationResultShape:
    def test_result_fields_populated(self) -> None:
        rule = _rule(rule_id="r1", keywords=("fix",))
        router = IntentRouter(rules=[rule])
        result = router.classify("fix bug")
        assert isinstance(result, ClassificationResult)
        assert result.matched_rule_id == "r1"
        assert result.confidence == 0.8
        assert result.match_type == "keyword"
