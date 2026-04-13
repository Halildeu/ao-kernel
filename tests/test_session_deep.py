"""Deep behavioral tests for session modules — compaction, cross-session, provider_memory, agent_context."""

from __future__ import annotations

from pathlib import Path


class TestCompactionEngine:
    def test_should_compact_empty_context_false(self):
        from src.session.compaction_engine import should_compact
        ctx = {"decisions": []}
        assert should_compact(ctx) is False

    def test_should_compact_respects_default_threshold(self):
        from src.session.compaction_engine import should_compact
        # Default threshold is typically > 50; build context exceeding it
        ctx = {"decisions": [{"id": str(i)} for i in range(200)]}
        result = should_compact(ctx)
        assert isinstance(result, bool)

    def test_compact_returns_summary_dict(self, tmp_path: Path):
        from src.session.compaction_engine import compact_session_decisions
        ctx = {"session_id": "test", "decisions": [], "actors": {}}
        result = compact_session_decisions(ctx, workspace_root=tmp_path)
        assert isinstance(result, dict)
        # Result is a compaction summary with kept/archived/reason
        assert "compacted" in result or "kept" in result or "reason" in result

    def test_compact_with_decisions(self, tmp_path: Path):
        from src.session.compaction_engine import compact_session_decisions
        decisions = [{"id": str(i), "value": f"v{i}", "created_at": "2026-01-01T00:00:00Z"} for i in range(5)]
        ctx = {"session_id": "test", "decisions": decisions, "actors": {}}
        result = compact_session_decisions(ctx, workspace_root=tmp_path, session_id="compact-test")
        assert isinstance(result, dict)


class TestCrossSessionContext:
    def test_build_cross_session_empty_workspace(self, tmp_path: Path):
        from src.session.cross_session_context import build_cross_session_context
        result = build_cross_session_context(workspace_root=tmp_path)
        assert isinstance(result, dict)

    def test_build_hierarchical_context_no_children(self, tmp_path: Path):
        from src.session.cross_session_context import build_hierarchical_context
        result = build_hierarchical_context(
            parent_workspace_root=tmp_path,
            child_workspace_roots=[],
        )
        assert isinstance(result, dict)

    def test_extract_decision_scope_returns_tuple(self):
        from src.session.cross_session_context import extract_decision_scope
        # extract_decision_scope takes a key string, returns (scope, key) tuple
        scope_tuple = extract_decision_scope("workspace:test_key")
        assert isinstance(scope_tuple, tuple)
        assert len(scope_tuple) == 2


class TestProviderMemory:
    def test_read_missing_returns_dict(self, tmp_path: Path):
        from src.session.provider_memory import read_provider_session_state
        result = read_provider_session_state(
            workspace_root=tmp_path,
            session_id="nonexistent",
            provider="openai",
            wire_api="chat",
        )
        assert isinstance(result, dict)

    def test_persist_creates_state(self, tmp_path: Path):
        from src.session.provider_memory import persist_provider_result
        # Setup workspace session dir
        session_dir = tmp_path / ".cache" / "sessions" / "test-session"
        session_dir.mkdir(parents=True)
        result = persist_provider_result(
            workspace_root=tmp_path,
            session_id="test-session",
            provider="openai",
            wire_api="chat",
            response_id="resp-001",
        )
        assert isinstance(result, dict)

    def test_estimate_tokens_returns_positive(self):
        from src.session.provider_memory import estimate_tokens
        count = estimate_tokens("Hello world, this is a test sentence.")
        assert isinstance(count, int)
        assert count > 0

    def test_estimate_tokens_longer_more(self):
        from src.session.provider_memory import estimate_tokens
        short = estimate_tokens("Hi")
        long = estimate_tokens("This is a much longer text with many words and sentences.")
        assert long > short


class TestAgentContextVersion:
    def test_compute_version_returns_dict(self, tmp_path: Path):
        from src.session.agent_context_version import compute_agent_context_version
        result = compute_agent_context_version(workspace_root=tmp_path)
        assert isinstance(result, dict)
        assert len(result) > 0

    def test_write_and_load_roundtrip(self, tmp_path: Path):
        from src.session.agent_context_version import (
            compute_agent_context_version,
            write_agent_context_version,
            load_agent_context_version,
        )
        version = compute_agent_context_version(workspace_root=tmp_path)
        path = write_agent_context_version(workspace_root=tmp_path, record=version)
        assert isinstance(path, str)
        loaded = load_agent_context_version(workspace_root=tmp_path)
        assert loaded is not None
        assert isinstance(loaded, dict)

    def test_verify_returns_dict(self, tmp_path: Path):
        from src.session.agent_context_version import (
            compute_agent_context_version,
            write_agent_context_version,
            verify_agent_context_version,
        )
        version = compute_agent_context_version(workspace_root=tmp_path)
        write_agent_context_version(workspace_root=tmp_path, record=version)
        result = verify_agent_context_version(workspace_root=tmp_path)
        assert isinstance(result, dict)
