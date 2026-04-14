"""Tests for Faz 4 — multi-agent coordination + SDK hooks (updated for CNS-009).

Contract changes from previous revision (all per CNS-20260414-009 consensus):
    - get_revision returns a full 64-char SHA-256 hex digest (opaque token).
    - record_decision(auto_promote=False) no longer silently writes a
      short-TTL canonical entry — it either writes to the supplied session
      context (ephemeral) or reports destination="dropped" when no context
      is provided.
    - finalize_session_sdk delegates to session_lifecycle.end_session and
      does NOT double-promote.
"""

from __future__ import annotations

from pathlib import Path

from ao_kernel.context.agent_coordination import (
    check_stale,
    compile_context_sdk,
    finalize_session_sdk,
    get_revision,
    has_changed,
    query_memory,
    read_with_revision,
    record_decision,
)


class TestRevisionTracking:
    def test_revision_returns_opaque_hash(self, tmp_path: Path):
        rev = get_revision(tmp_path)
        assert isinstance(rev, str)
        # Full SHA-256 hex digest; callers must treat as opaque.
        assert len(rev) == 64

    def test_revision_changes_on_write(self, tmp_path: Path):
        rev1 = get_revision(tmp_path)
        record_decision(tmp_path, key="test.key", value="v1", confidence=0.9)
        rev2 = get_revision(tmp_path)
        assert rev1 != rev2

    def test_check_stale_detects_change(self, tmp_path: Path):
        rev = get_revision(tmp_path)
        assert check_stale(tmp_path, last_revision=rev) is False

        record_decision(tmp_path, key="new.key", value="new_value", confidence=0.9)
        assert check_stale(tmp_path, last_revision=rev) is True

    def test_has_changed_is_new_name_for_check_stale(self, tmp_path: Path):
        rev = get_revision(tmp_path)
        assert has_changed(tmp_path, last_revision=rev) is False
        record_decision(tmp_path, key="k", value="v", confidence=0.9)
        assert has_changed(tmp_path, last_revision=rev) is True

    def test_read_with_revision(self, tmp_path: Path):
        record_decision(tmp_path, key="runtime.python", value="3.11", confidence=0.9)
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
        assert result["destination"] == "canonical"

        items = query_memory(tmp_path, key_pattern="arch.*")
        assert len(items) == 1

    def test_below_threshold_no_context_drops(self, tmp_path: Path):
        """CNS-009 blocking fix: below-threshold records without a session
        context must NOT silently write to canonical (old fresh_days=7 path)."""
        result = record_decision(
            tmp_path,
            key="maybe.thing",
            value="uncertain",
            confidence=0.3,
        )
        assert result["promoted"] is False
        assert result["recorded"] is False
        assert result["destination"] == "dropped"
        # Canonical store must be empty — no silent short-TTL write.
        assert query_memory(tmp_path, key_pattern="maybe.*") == []

    def test_below_threshold_with_context_writes_session(self, tmp_path: Path):
        """When caller supplies a context dict, ephemeral storage works."""
        ctx: dict = {"ephemeral_decisions": [], "session_id": "sess-x"}
        result = record_decision(
            tmp_path,
            key="ephemeral.key",
            value="scratch",
            confidence=0.3,
            context=ctx,
        )
        assert result["recorded"] is True
        assert result["promoted"] is False
        assert result["destination"] == "session"
        assert any(d["key"] == "ephemeral.key" for d in ctx["ephemeral_decisions"])
        # Canonical store still empty.
        assert query_memory(tmp_path, key_pattern="ephemeral.*") == []

    def test_auto_promote_false_does_not_canonicalize(self, tmp_path: Path):
        ctx: dict = {"ephemeral_decisions": [], "session_id": "sess-y"}
        result = record_decision(
            tmp_path,
            key="manual.only",
            value="test",
            confidence=0.95,
            auto_promote=False,
            context=ctx,
        )
        assert result["promoted"] is False
        assert result["destination"] == "session"
        assert query_memory(tmp_path, key_pattern="manual.*") == []


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
    def test_finalize_promotes_once(self, tmp_path: Path):
        """CNS-009 blocking fix: finalize must not double-promote."""
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

        before_items = {i["key"] for i in query_memory(tmp_path)}
        result = finalize_session_sdk(tmp_path, ctx, promote_threshold=0.5)
        after_items = {i["key"] for i in query_memory(tmp_path)}
        assert result["finalized"] is True
        # Promoted count equals the actual canonical delta (no double-count).
        assert result["promoted_count"] == len(after_items - before_items)

    def test_finalize_auto_promote_false_respects_flag(self, tmp_path: Path):
        """Regression guard: finalize(auto_promote=False) must actually skip promotion.

        Previously end_session always promoted at 0.7, then
        finalize_session_sdk promoted again — the flag was silently ignored.
        """
        from ao_kernel.context.session_lifecycle import start_session
        from ao_kernel.context.memory_pipeline import process_turn
        import json

        ctx = start_session(workspace_root=tmp_path, session_id="no-promote")
        ctx = process_turn(
            json.dumps({"goal": "ship-v2"}),
            ctx,
            request_id="np-req",
            workspace_root=tmp_path,
        )
        before = query_memory(tmp_path)
        finalize_session_sdk(tmp_path, ctx, auto_promote=False)
        after = query_memory(tmp_path)
        assert len(after) == len(before)


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
        record_decision(
            tmp_path, key="plan.approved", value=True,
            confidence=0.95, source="claude",
        )
        result_b = read_with_revision(tmp_path)
        assert result_b["count"] == 1
        assert result_b["items"][0]["value"] is True
        assert check_stale(tmp_path, last_revision=result_b["revision"]) is False

        record_decision(
            tmp_path, key="deploy.ready", value=True,
            confidence=0.9, source="claude",
        )
        assert check_stale(tmp_path, last_revision=result_b["revision"]) is True

        result_b2 = read_with_revision(tmp_path)
        assert result_b2["count"] == 2
        assert result_b2["revision"] != result_b["revision"]
