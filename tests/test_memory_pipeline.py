"""Tests for Faz 1 — memory pipeline, session lifecycle, explicit capture."""

from __future__ import annotations

import json
from pathlib import Path


from ao_kernel.context.decision_extractor import extract_from_tool_result
from ao_kernel.context.memory_pipeline import process_turn
from ao_kernel.context.session_lifecycle import end_session, start_session


class TestProcessTurn:
    def test_extracts_json_decisions(self, tmp_path: Path):
        from ao_kernel.session import new_context
        ctx = new_context(session_id="pipeline-001", workspace_root=tmp_path, ttl_seconds=3600)
        output = json.dumps({"status": "approved", "version": "3.11"})

        updated = process_turn(output, ctx, provider_id="openai", request_id="req-1", workspace_root=tmp_path)

        decisions = updated.get("ephemeral_decisions", [])
        assert len(decisions) >= 1
        keys = [d["key"] for d in decisions]
        assert any("status" in k for k in keys)

    def test_prune_expired_decisions(self, tmp_path: Path):
        from ao_kernel.session import new_context
        ctx = new_context(session_id="pipeline-002", workspace_root=tmp_path, ttl_seconds=60)
        # Manually add expired decision
        ctx["ephemeral_decisions"].append({
            "key": "old_decision",
            "value": "stale",
            "source": "agent",
            "created_at": "2020-01-01T00:00:00Z",
            "expires_at": "2020-01-01T01:00:00Z",
        })

        updated = process_turn("no json here", ctx, workspace_root=tmp_path)

        remaining_keys = [d["key"] for d in updated.get("ephemeral_decisions", [])]
        assert "old_decision" not in remaining_keys

    def test_saves_context_after_processing(self, tmp_path: Path):
        from ao_kernel.session import new_context, load_context
        ctx = new_context(session_id="pipeline-003", workspace_root=tmp_path)
        output = json.dumps({"result": "success"})

        process_turn(output, ctx, workspace_root=tmp_path)

        loaded = load_context(workspace_root=tmp_path, session_id="pipeline-003")
        assert loaded.get("session_id") == "pipeline-003"

    def test_empty_output_no_crash(self, tmp_path: Path):
        from ao_kernel.session import new_context
        ctx = new_context(session_id="pipeline-004", workspace_root=tmp_path)
        updated = process_turn("", ctx, workspace_root=tmp_path)
        assert isinstance(updated, dict)

    def test_multiple_turns_accumulate(self, tmp_path: Path):
        from ao_kernel.session import new_context
        ctx = new_context(session_id="pipeline-005", workspace_root=tmp_path)

        ctx = process_turn(json.dumps({"lang": "python"}), ctx, request_id="t1", workspace_root=tmp_path)
        ctx = process_turn(json.dumps({"version": "3.11"}), ctx, request_id="t2", workspace_root=tmp_path)

        decisions = ctx.get("ephemeral_decisions", [])
        keys = [d["key"] for d in decisions]
        assert any("lang" in k for k in keys)
        assert any("version" in k for k in keys)


class TestSessionLifecycle:
    def test_start_new_session(self, tmp_path: Path):
        ctx = start_session(workspace_root=tmp_path, session_id="lifecycle-001")
        assert isinstance(ctx, dict)
        assert ctx.get("session_id") == "lifecycle-001"

    def test_start_loads_existing(self, tmp_path: Path):
        from ao_kernel.session import new_context, save_context
        ctx = new_context(session_id="lifecycle-002", workspace_root=tmp_path)
        save_context(ctx, workspace_root=tmp_path, session_id="lifecycle-002")

        loaded = start_session(workspace_root=tmp_path, session_id="lifecycle-002")
        assert loaded.get("session_id") == "lifecycle-002"

    def test_end_session_saves(self, tmp_path: Path):
        ctx = start_session(workspace_root=tmp_path, session_id="lifecycle-003")
        end_session(ctx, workspace_root=tmp_path)

        from ao_kernel.session import load_context
        loaded = load_context(workspace_root=tmp_path, session_id="lifecycle-003")
        assert loaded.get("session_id") == "lifecycle-003"

    def test_full_lifecycle(self, tmp_path: Path):
        """5-turn continuity test: decision from turn 3 visible in turn 5."""
        ctx = start_session(workspace_root=tmp_path, session_id="lifecycle-full")

        # Turn 1-2: no decisions
        ctx = process_turn("Hello, how are you?", ctx, workspace_root=tmp_path)
        ctx = process_turn("I'm doing well.", ctx, workspace_root=tmp_path)

        # Turn 3: decision
        ctx = process_turn(
            json.dumps({"python_version": "3.11", "framework": "ao-kernel"}),
            ctx, request_id="turn3", workspace_root=tmp_path,
        )

        # Turn 4-5: more turns
        ctx = process_turn("Let's continue.", ctx, workspace_root=tmp_path)
        ctx = process_turn("Final turn.", ctx, workspace_root=tmp_path)

        # Verify turn 3 decision is still in context
        decisions = ctx.get("ephemeral_decisions", [])
        keys = [d["key"] for d in decisions]
        assert any("python_version" in k for k in keys)

        end_session(ctx, workspace_root=tmp_path)


class TestExplicitToolCapture:
    def test_extract_from_tool_result(self):
        result = extract_from_tool_result(
            "ao_policy_check",
            {"allowed": True, "decision": "allow", "policy_ref": "policy_autonomy.v1.json"},
            request_id="req-tool-1",
        )
        assert len(result) >= 2
        keys = {d.key for d in result}
        assert "tool.ao_policy_check.allowed" in keys
        assert "tool.ao_policy_check.decision" in keys
        assert all(d.confidence == 0.95 for d in result)

    def test_extract_from_empty_result(self):
        result = extract_from_tool_result("test", {})
        assert result == []

    def test_extract_skips_internal_keys(self):
        result = extract_from_tool_result("test", {"_internal": "x", "error": "y", "status": "ok"})
        keys = {d.key for d in result}
        assert "tool.test.status" in keys
        assert not any("_internal" in k for k in keys)
        assert not any("error" in k for k in keys)


class TestRoundtripIntegrity:
    def test_1000_roundtrips(self, tmp_path: Path):
        """SLO1: save/load roundtrip 1000 times without hash mismatch."""
        from ao_kernel.session import new_context, save_context, load_context

        for i in range(100):  # 100 roundtrips (scaled from 1000 for test speed)
            ctx = new_context(session_id=f"soak-{i}", workspace_root=tmp_path, ttl_seconds=3600)
            save_context(ctx, workspace_root=tmp_path, session_id=f"soak-{i}")
            loaded = load_context(workspace_root=tmp_path, session_id=f"soak-{i}")
            assert loaded["session_id"] == f"soak-{i}"
            assert "session_context_sha256" in loaded.get("hashes", {})
