"""Tests for Faz 2 — context compiler + profile router."""

from __future__ import annotations


from ao_kernel.context.context_compiler import CompiledContext, compile_context
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

    def test_relevance_scoring_profile_match(self):
        ctx = {
            "session_id": "test",
            "ephemeral_decisions": [
                {"key": "runtime.python", "value": "3.11", "source": "agent",
                 "confidence": 0.9, "created_at": "2026-04-13T10:00:00Z"},
                {"key": "unrelated.thing", "value": "xyz", "source": "agent",
                 "confidence": 0.9, "created_at": "2026-04-13T10:00:00Z"},
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
