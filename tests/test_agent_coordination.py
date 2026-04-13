"""Tests for Faz 4 — multi-agent coordination + SDK hooks."""

from __future__ import annotations

from pathlib import Path

from ao_kernel.context.agent_coordination import (
    check_stale,
    compile_context_sdk,
    finalize_session_sdk,
    get_revision,
    query_memory,
    read_with_revision,
    record_decision,
)


class TestRevisionTracking:
    def test_revision_returns_hash(self, tmp_path: Path):
        rev = get_revision(tmp_path)
        assert isinstance(rev, str)
        assert len(rev) == 16

    def test_revision_changes_on_write(self, tmp_path: Path):
        rev1 = get_revision(tmp_path)
        record_decision(tmp_path, key="test.key", value="v1")
        rev2 = get_revision(tmp_path)
        assert rev1 != rev2

    def test_check_stale_detects_change(self, tmp_path: Path):
        rev = get_revision(tmp_path)
        assert check_stale(tmp_path, last_revision=rev) is False

        record_decision(tmp_path, key="new.key", value="new_value")
        assert check_stale(tmp_path, last_revision=rev) is True

    def test_read_with_revision(self, tmp_path: Path):
        record_decision(tmp_path, key="runtime.python", value="3.11")
        result = read_with_revision(tmp_path, key_pattern="runtime.*")
        assert "revision" in result
        assert result["count"] == 1
        assert result["items"][0]["key"] == "runtime.python"


class TestSDKRecordDecision:
    def test_record_and_auto_promote(self, tmp_path: Path):
        result = record_decision(
            tmp_path,
            key="arch.pattern",
            value="microservices",
            confidence=0.9,
        )
        assert result["recorded"] is True
        assert result["promoted"] is True

        items = query_memory(tmp_path, key_pattern="arch.*")
        assert len(items) == 1

    def test_record_below_threshold_not_promoted(self, tmp_path: Path):
        result = record_decision(
            tmp_path,
            key="maybe.thing",
            value="uncertain",
            confidence=0.3,
        )
        assert result["recorded"] is True
        assert result["promoted"] is False

    def test_record_without_auto_promote(self, tmp_path: Path):
        result = record_decision(
            tmp_path,
            key="manual.only",
            value="test",
            confidence=0.9,
            auto_promote=False,
        )
        assert result["promoted"] is False


class TestSDKCompileContext:
    def test_compile_with_canonical(self, tmp_path: Path):
        record_decision(tmp_path, key="runtime.lang", value="python", confidence=0.9)
        result = compile_context_sdk(tmp_path, profile="TASK_EXECUTION")
        assert "preamble" in result
        assert result["items_included"] >= 1
        assert result["profile_id"] == "TASK_EXECUTION"

    def test_compile_empty_workspace(self, tmp_path: Path):
        result = compile_context_sdk(tmp_path)
        assert result["items_included"] == 0
        assert result["preamble"] == ""


class TestSDKFinalizeSession:
    def test_finalize_promotes_decisions(self, tmp_path: Path):
        from ao_kernel.context.session_lifecycle import start_session
        from ao_kernel.context.memory_pipeline import process_turn
        import json

        ctx = start_session(workspace_root=tmp_path, session_id="finalize-test")
        ctx = process_turn(
            json.dumps({"status": "approved", "version": "2.0"}),
            ctx,
            request_id="fin-req",
            workspace_root=tmp_path,
        )

        result = finalize_session_sdk(tmp_path, ctx, promote_threshold=0.5)
        assert result["finalized"] is True
        assert result["promoted_count"] >= 0


class TestSDKQueryMemory:
    def test_query_all(self, tmp_path: Path):
        record_decision(tmp_path, key="a.b", value=1, confidence=0.9)
        record_decision(tmp_path, key="c.d", value=2, confidence=0.9)
        items = query_memory(tmp_path)
        assert len(items) == 2

    def test_query_pattern(self, tmp_path: Path):
        record_decision(tmp_path, key="runtime.x", value=1, confidence=0.9)
        record_decision(tmp_path, key="arch.y", value=2, confidence=0.9)
        items = query_memory(tmp_path, key_pattern="runtime.*")
        assert len(items) == 1
        assert items[0]["key"] == "runtime.x"


class TestMultiAgentScenario:
    def test_two_agents_same_store(self, tmp_path: Path):
        """Simulate: Agent A writes, Agent B reads same canonical store."""
        # Agent A writes
        record_decision(tmp_path, key="plan.approved", value=True, confidence=0.95, source="claude")
        get_revision(tmp_path)  # Agent A's revision after write

        # Agent B reads
        result_b = read_with_revision(tmp_path)
        assert result_b["count"] == 1
        assert result_b["items"][0]["value"] is True

        # Agent B's revision matches
        assert check_stale(tmp_path, last_revision=result_b["revision"]) is False

        # Agent A writes again
        record_decision(tmp_path, key="deploy.ready", value=True, confidence=0.9, source="claude")

        # Agent B detects stale
        assert check_stale(tmp_path, last_revision=result_b["revision"]) is True

        # Agent B refreshes
        result_b2 = read_with_revision(tmp_path)
        assert result_b2["count"] == 2
