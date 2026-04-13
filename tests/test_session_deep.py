"""Deep behavioral tests for session modules — compaction, cross-session, provider_memory, agent_context."""

from __future__ import annotations

from pathlib import Path


class TestCompactionEngine:
    def test_should_compact_empty_context_false(self):
        from ao_kernel._internal.session.compaction_engine import should_compact
        ctx = {"ephemeral_decisions": []}
        assert should_compact(ctx) is False

    def test_should_compact_respects_default_threshold(self):
        from ao_kernel._internal.session.compaction_engine import should_compact
        # Default threshold is 30; 200 decisions should trigger compaction
        ctx = {"ephemeral_decisions": [{"id": str(i)} for i in range(200)]}
        assert should_compact(ctx) is True

    def test_compact_returns_summary_dict(self, tmp_path: Path):
        from ao_kernel._internal.session.compaction_engine import compact_session_decisions
        ctx = {"session_id": "test", "ephemeral_decisions": [], "actors": {}}
        result = compact_session_decisions(ctx, workspace_root=tmp_path)
        assert result["compacted"] is False
        assert result["reason"] == "below_threshold"

    def test_compact_with_decisions(self, tmp_path: Path):
        from ao_kernel._internal.session.compaction_engine import compact_session_decisions
        decisions = [{"id": str(i), "value": f"v{i}", "created_at": "2026-01-01T00:00:00Z"} for i in range(5)]
        ctx = {"session_id": "test", "ephemeral_decisions": decisions, "actors": {}}
        result = compact_session_decisions(ctx, workspace_root=tmp_path, session_id="compact-test")
        # 5 decisions, keep_recent_count=10 → below threshold, no compaction
        assert result["compacted"] is False
        assert result["kept"] == 5

    # ── Edge case tests ──

    def test_should_compact_exact_threshold(self):
        from ao_kernel._internal.session.compaction_engine import should_compact
        # Exactly at threshold (30) → True
        ctx_at = {"ephemeral_decisions": [{"id": str(i)} for i in range(30)]}
        assert should_compact(ctx_at) is True
        # One below threshold (29) → False
        ctx_below = {"ephemeral_decisions": [{"id": str(i)} for i in range(29)]}
        assert should_compact(ctx_below) is False

    def test_compact_archive_rotation(self, tmp_path: Path):
        from ao_kernel._internal.session.compaction_engine import compact_session_decisions
        import time

        policy = {
            "enabled": True,
            "keep_recent_count": 2,
            "archive_older": True,
            "max_archive_files": 3,
        }
        # Run compaction 5 times, each with fresh decisions
        for batch in range(5):
            decisions = [
                {"key": f"d-{batch}-{i}", "value": batch, "created_at": f"2026-01-0{batch + 1}T00:00:00Z"}
                for i in range(5)
            ]
            ctx = {"session_id": "rot", "ephemeral_decisions": decisions}
            compact_session_decisions(ctx, policy=policy, workspace_root=tmp_path, session_id="rot")
            time.sleep(0.01)  # ensure unique timestamps

        archive_dir = tmp_path / ".cache" / "sessions" / "rot" / "compaction_archive"
        archive_files = list(archive_dir.glob("*.v1.json"))
        assert len(archive_files) <= 3

    def test_compact_missing_created_at(self, tmp_path: Path):
        from ao_kernel._internal.session.compaction_engine import compact_session_decisions
        # Decisions without created_at should not crash the sort
        decisions = [
            {"key": "a", "value": 1},
            {"key": "b", "value": 2, "created_at": "2026-01-01T00:00:00Z"},
            {"key": "c", "value": 3},
        ]
        ctx = {"session_id": "test", "ephemeral_decisions": decisions}
        policy = {"keep_recent_count": 1, "archive_older": True}
        result = compact_session_decisions(ctx, policy=policy, workspace_root=tmp_path, session_id="missing-ts")
        assert result["compacted"] is True
        assert result["kept"] == 1
        assert result["archived"] == 2

    def test_compact_large_decision_set(self, tmp_path: Path):
        from ao_kernel._internal.session.compaction_engine import compact_session_decisions
        decisions = [
            {"key": f"d-{i}", "value": i, "created_at": f"2026-01-01T{i:02d}:00:00Z"}
            for i in range(200)
        ]
        ctx = {"session_id": "test", "ephemeral_decisions": decisions}
        policy = {"keep_recent_count": 10, "archive_older": True}
        result = compact_session_decisions(ctx, policy=policy, workspace_root=tmp_path, session_id="large")
        assert result["compacted"] is True
        assert result["kept"] == 10
        assert result["archived"] == 190
        # Context should only have 10 decisions left
        assert len(ctx["ephemeral_decisions"]) == 10


class TestCrossSessionContext:
    def test_build_cross_session_empty_workspace(self, tmp_path: Path):
        from ao_kernel._internal.session.cross_session_context import build_cross_session_context
        result = build_cross_session_context(workspace_root=tmp_path)
        assert isinstance(result, dict)

    def test_build_hierarchical_context_no_children(self, tmp_path: Path):
        from ao_kernel._internal.session.cross_session_context import build_hierarchical_context
        result = build_hierarchical_context(
            parent_workspace_root=tmp_path,
            child_workspace_roots=[],
        )
        assert isinstance(result, dict)

    def test_extract_decision_scope_returns_tuple(self):
        from ao_kernel._internal.session.cross_session_context import extract_decision_scope
        # extract_decision_scope takes a key string, returns (scope, key) tuple
        scope_tuple = extract_decision_scope("workspace:test_key")
        assert isinstance(scope_tuple, tuple)
        assert len(scope_tuple) == 2


class TestProviderMemory:
    def test_read_missing_returns_dict(self, tmp_path: Path):
        from ao_kernel._internal.session.provider_memory import read_provider_session_state
        result = read_provider_session_state(
            workspace_root=tmp_path,
            session_id="nonexistent",
            provider="openai",
            wire_api="chat",
        )
        assert isinstance(result, dict)

    def test_persist_creates_state(self, tmp_path: Path):
        from ao_kernel._internal.session.provider_memory import persist_provider_result
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
        from ao_kernel._internal.session.provider_memory import estimate_tokens
        count = estimate_tokens("Hello world, this is a test sentence.")
        assert isinstance(count, int)
        assert count > 0

    def test_estimate_tokens_longer_more(self):
        from ao_kernel._internal.session.provider_memory import estimate_tokens
        short = estimate_tokens("Hi")
        long = estimate_tokens("This is a much longer text with many words and sentences.")
        assert long > short


class TestAgentContextVersion:
    def test_compute_version_returns_dict(self, tmp_path: Path):
        from ao_kernel._internal.session.agent_context_version import compute_agent_context_version
        result = compute_agent_context_version(workspace_root=tmp_path)
        assert isinstance(result, dict)
        assert len(result) > 0

    def test_write_and_load_roundtrip(self, tmp_path: Path):
        from ao_kernel._internal.session.agent_context_version import (
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
        from ao_kernel._internal.session.agent_context_version import (
            compute_agent_context_version,
            write_agent_context_version,
            verify_agent_context_version,
        )
        version = compute_agent_context_version(workspace_root=tmp_path)
        write_agent_context_version(workspace_root=tmp_path, record=version)
        result = verify_agent_context_version(workspace_root=tmp_path)
        assert isinstance(result, dict)
