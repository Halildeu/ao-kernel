"""Tests for Faz 2 — context compiler + profile router."""

from __future__ import annotations

import inspect

from ao_kernel.context.context_compiler import CompiledContext, compile_context
from ao_kernel.context.agent_coordination import compile_context_sdk
from ao_kernel.context.profile_router import (
    DEFAULT_PROFILE,
    detect_profile,
    get_profile,
)


class TestProfileDetection:
    def test_startup_detected(self):
        messages = [{"role": "user", "content": "Help me setup and configure the workspace"}]
        assert detect_profile(messages) == "STARTUP"

    def test_review_detected(self):
        messages = [{"role": "user", "content": "Please review this code for quality issues"}]
        assert detect_profile(messages) == "REVIEW"

    def test_task_default(self):
        messages = [{"role": "user", "content": "Implement the new feature for authentication"}]
        assert detect_profile(messages) == "TASK_EXECUTION"

    def test_empty_messages_default(self):
        assert detect_profile([]) == DEFAULT_PROFILE

    def test_no_user_message_default(self):
        messages = [{"role": "system", "content": "You are helpful"}]
        assert detect_profile(messages) == DEFAULT_PROFILE

    def test_multiple_keyword_match(self):
        messages = [{"role": "user", "content": "audit and review the code quality standards"}]
        profile = detect_profile(messages)
        assert profile == "REVIEW"


class TestProfileConfig:
    def test_get_known_profile(self):
        cfg = get_profile("STARTUP")
        assert cfg.profile_id == "STARTUP"
        assert cfg.max_decisions == 10
        assert cfg.max_tokens == 1000

    def test_get_task_profile(self):
        cfg = get_profile("TASK_EXECUTION")
        assert cfg.max_decisions == 30
        assert cfg.max_tokens == 4000

    def test_get_unknown_returns_default(self):
        cfg = get_profile("NONEXISTENT")
        assert cfg.profile_id == "TASK_EXECUTION"

    def test_get_none_returns_default(self):
        cfg = get_profile(None)
        assert cfg.profile_id == "TASK_EXECUTION"

    def test_profiles_have_priority_prefixes(self):
        for profile_id in ("STARTUP", "TASK_EXECUTION", "REVIEW"):
            cfg = get_profile(profile_id)
            assert len(cfg.priority_prefixes) > 0


class TestContextCompiler:
    def _make_context_with_decisions(self, n: int, prefix: str = "llm.") -> dict:
        return {
            "session_id": "test",
            "ephemeral_decisions": [
                {
                    "key": f"{prefix}key_{i}",
                    "value": f"value_{i}",
                    "source": "agent",
                    "confidence": 0.8,
                    "created_at": "2026-04-13T10:00:00Z",
                }
                for i in range(n)
            ],
        }

    def test_compile_basic(self):
        ctx = self._make_context_with_decisions(5)
        result = compile_context(ctx, profile="TASK_EXECUTION")
        assert isinstance(result, CompiledContext)
        assert result.items_included > 0
        assert result.profile_id == "TASK_EXECUTION"
        assert len(result.preamble) > 0

    def test_compile_auto_detect_profile(self):
        ctx = self._make_context_with_decisions(5)
        messages = [{"role": "user", "content": "Setup my workspace"}]
        result = compile_context(ctx, messages=messages)
        assert result.profile_id == "STARTUP"

    def test_budget_enforcement(self):
        ctx = self._make_context_with_decisions(100)
        result = compile_context(ctx, profile="STARTUP")  # max_decisions=10
        assert result.items_included <= 10
        assert result.items_excluded > 0

    def test_token_budget_enforcement(self):
        ctx = self._make_context_with_decisions(50, prefix="runtime.")
        result = compile_context(ctx, profile="STARTUP")  # max_tokens=1000
        assert result.total_tokens <= 1000

    def test_token_budget_exclusion_reason_recorded(self):
        # HYG-CONTEXT-COMPILER: drive the token-budget exclusion branch
        # (context_compiler L154-156) specifically — a few LARGE-value
        # decisions exceed max_tokens before max_decisions is reached, so the
        # excluded item carries the "token budget" selection reason (not the
        # "max_decisions" reason). Discriminating assertion on selection_log.
        big_value = "x" * 8000  # ~2000 token_estimate -> blows the 1000 budget fast
        ctx = {
            "session_id": "test",
            "ephemeral_decisions": [
                {
                    "key": f"runtime.big_{i}",
                    "value": big_value,
                    "source": "agent",
                    "confidence": 0.9,
                    "created_at": "2026-04-13T10:00:00Z",
                }
                for i in range(3)  # 3 items: well under STARTUP max_decisions (10)
            ],
        }
        result = compile_context(ctx, profile="STARTUP")  # max_tokens=1000
        assert result.total_tokens <= 1000
        token_budget_exclusions = [entry for entry in result.selection_log if "token budget" in entry.get("reason", "")]
        # At least one item excluded specifically by the token-budget branch,
        # before the max_decisions cap could trigger (only 3 items).
        assert token_budget_exclusions
        assert result.items_excluded >= 1

    def test_relevance_scoring_profile_match(self):
        ctx = {
            "session_id": "test",
            "ephemeral_decisions": [
                {
                    "key": "runtime.python",
                    "value": "3.11",
                    "source": "agent",
                    "confidence": 0.9,
                    "created_at": "2026-04-13T10:00:00Z",
                },
                {
                    "key": "unrelated.thing",
                    "value": "xyz",
                    "source": "agent",
                    "confidence": 0.9,
                    "created_at": "2026-04-13T10:00:00Z",
                },
            ],
        }
        result = compile_context(ctx, profile="TASK_EXECUTION")
        # runtime.* should score higher than unrelated.*
        log = result.selection_log
        runtime_item = next(i for i in log if i["key"] == "runtime.python")
        unrelated_item = next(i for i in log if i["key"] == "unrelated.thing")
        assert runtime_item["score"] > unrelated_item["score"]

    def test_selection_log_has_reasons(self):
        ctx = self._make_context_with_decisions(3)
        result = compile_context(ctx, profile="TASK_EXECUTION")
        assert len(result.selection_log) == 3
        for entry in result.selection_log:
            assert "key" in entry
            assert "score" in entry
            assert "included" in entry
            assert "reason" in entry

    def test_empty_context_returns_empty_preamble(self):
        ctx = {"session_id": "test", "ephemeral_decisions": []}
        result = compile_context(ctx, profile="TASK_EXECUTION")
        assert result.preamble == ""
        assert result.items_included == 0

    def test_with_workspace_facts(self):
        ctx = self._make_context_with_decisions(2)
        facts = {
            "facts": {
                "runtime.python": {"value": "3.11", "confidence": 0.95},
                "team.name": {"value": "platform", "confidence": 0.7},
            }
        }
        result = compile_context(ctx, workspace_facts=facts, profile="TASK_EXECUTION")
        assert result.items_included >= 3  # 2 session + at least 1 fact
        assert "Workspace Facts" in result.preamble

    def test_with_canonical_decisions(self):
        ctx = self._make_context_with_decisions(1)
        canonical = {
            "architecture.pattern": {"value": "microservices", "confidence": 0.9},
        }
        result = compile_context(ctx, canonical_decisions=canonical, profile="TASK_EXECUTION")
        assert any(e["lane"] == "canonical" for e in result.selection_log)

    def test_preamble_includes_profile_header(self):
        ctx = self._make_context_with_decisions(3)
        result = compile_context(ctx, profile="REVIEW")
        assert "[Context Profile: REVIEW]" in result.preamble

    def test_different_profiles_different_results(self):
        ctx = self._make_context_with_decisions(20, prefix="runtime.")
        startup = compile_context(ctx, profile="STARTUP")
        task = compile_context(ctx, profile="TASK_EXECUTION")
        assert startup.items_included < task.items_included  # STARTUP has lower max

    def test_compile_context_has_no_repo_intelligence_auto_feed_parameter(self):
        parameter_names = set(inspect.signature(compile_context).parameters)

        assert "repo_intelligence_context" not in parameter_names
        assert "repo_query_context" not in parameter_names
        assert "context_compiler_feed" not in parameter_names

    def test_compile_context_sdk_has_no_repo_intelligence_auto_feed_parameter(self):
        parameter_names = set(inspect.signature(compile_context_sdk).parameters)

        assert "repo_intelligence_context" not in parameter_names
        assert "repo_query_context" not in parameter_names
        assert "context_compiler_feed" not in parameter_names

    def test_repo_intelligence_context_payload_is_not_compiled_from_session_root(self):
        ctx = {
            "session_id": "test",
            "repo_intelligence_context": {
                "enabled": True,
                "source": "explicit_handoff_file",
                "content": "repo-intelligence hidden payload must not be rendered",
            },
            "repo_query_context": {
                "content": "repo query hidden payload must not be rendered",
            },
            "context_compiler_feed": {
                "enabled": True,
            },
            "ephemeral_decisions": [],
        }

        result = compile_context(ctx, profile="TASK_EXECUTION")

        assert result.preamble == ""
        assert result.items_included == 0
        assert result.items_excluded == 0
        assert result.selection_log == []


class TestRecencyScore:
    """HYG-CONTEXT-COMPILER: _recency_score branches (context_compiler
    L335-351), previously uncovered. Timestamps are computed relative to now
    so the age buckets are deterministic.
    """

    def test_empty_timestamp_returns_default(self):
        from ao_kernel.context.context_compiler import _recency_score

        assert _recency_score("") == 0.3

    def test_malformed_timestamp_returns_default(self):
        from ao_kernel.context.context_compiler import _recency_score

        assert _recency_score("not-a-timestamp") == 0.3

    def test_under_one_hour_is_top(self):
        from datetime import datetime, timedelta, timezone

        from ao_kernel.context.context_compiler import _recency_score

        ts = (datetime.now(timezone.utc) - timedelta(minutes=30)).isoformat()
        assert _recency_score(ts) == 1.0

    def test_under_one_day(self):
        from datetime import datetime, timedelta, timezone

        from ao_kernel.context.context_compiler import _recency_score

        ts = (datetime.now(timezone.utc) - timedelta(hours=12)).isoformat()
        assert _recency_score(ts) == 0.8

    def test_under_one_week(self):
        from datetime import datetime, timedelta, timezone

        from ao_kernel.context.context_compiler import _recency_score

        ts = (datetime.now(timezone.utc) - timedelta(days=3)).isoformat()
        assert _recency_score(ts) == 0.5

    def test_older_than_a_week_is_low(self):
        from datetime import datetime, timedelta, timezone

        from ao_kernel.context.context_compiler import _recency_score

        ts = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
        assert _recency_score(ts) == 0.2


class TestSemanticReranking:
    """HYG-CONTEXT-COMPILER: _apply_semantic_reranking (context_compiler
    L354-436). semantic_search is monkeypatched to a deterministic stub so no
    provider/network is involved; assertions are made in the test body (not in
    the stub) because the function's broad except would swallow them. The
    fail-open except branch (L438-439) is intentionally left uncovered as a
    defensive, non-critical path.
    """

    def _items(self):
        from ao_kernel.context.context_compiler import ContextItem

        return [
            ContextItem("a", "alpha", "session", 0.5, "", included=True, token_estimate=5),
            ContextItem("b", "beta", "session", 0.6, "", included=True, token_estimate=5),
        ]

    def test_rerank_blends_and_resorts(self, monkeypatch):
        from ao_kernel.context import context_compiler as cc
        from ao_kernel.context.profile_router import get_profile

        # Stub semantic_search: 'a' is highly similar, 'b' not at all.
        def fake_search(query, decisions, **kwargs):
            return [{"key": "a", "_similarity": 1.0}]

        monkeypatch.setattr("ao_kernel.context.semantic_retrieval.semantic_search", fake_search)
        items = self._items()
        cc._apply_semantic_reranking(
            items,
            [{"role": "user", "content": "find alpha"}],
            get_profile("TASK_EXECUTION"),
            enable_override=True,
        )
        # 'a' got the semantic blend (0.5*0.7 + 1.0*0.3 = 0.65) > 'b' (unchanged 0.6)
        by_key = {it.key: it.relevance_score for it in items}
        assert round(by_key["a"], 4) == 0.65
        assert items[0].key == "a"  # re-sorted to front

    def test_rerank_multimodal_content_list_query(self, monkeypatch):
        from ao_kernel.context import context_compiler as cc
        from ao_kernel.context.profile_router import get_profile

        captured = {}

        def fake_search(query, decisions, **kwargs):
            captured["query"] = query
            return []

        monkeypatch.setattr("ao_kernel.context.semantic_retrieval.semantic_search", fake_search)
        # Multimodal content as a list of parts (L393-398 join branch)
        cc._apply_semantic_reranking(
            self._items(),
            [{"role": "user", "content": [{"text": "hello"}, {"text": "world"}]}],
            get_profile("TASK_EXECUTION"),
            enable_override=True,
        )
        assert captured["query"] == "hello world"

    def test_rerank_disabled_is_noop(self, monkeypatch):
        from ao_kernel.context import context_compiler as cc
        from ao_kernel.context.profile_router import get_profile

        def fail_if_called(*a, **k):
            raise AssertionError("semantic_search must not be called when disabled")

        monkeypatch.setattr("ao_kernel.context.semantic_retrieval.semantic_search", fail_if_called)
        items = self._items()
        before = [it.relevance_score for it in items]
        cc._apply_semantic_reranking(
            items,
            [{"role": "user", "content": "x"}],
            get_profile("TASK_EXECUTION"),
            enable_override=False,
        )
        assert [it.relevance_score for it in items] == before
