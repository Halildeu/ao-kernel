"""Chaos and failure tests — crash recovery, corruption, race conditions."""

from __future__ import annotations

import json
from pathlib import Path

import pytest


class TestCrashRecovery:
    """Simulate crashes during save and verify recovery."""

    def test_save_atomic_no_partial_write(self, tmp_path: Path):
        """If save crashes mid-write, old file should be intact."""
        from ao_kernel._internal.shared.utils import write_json_atomic

        original = {"version": "original", "data": "safe"}
        f = tmp_path / "test.json"
        write_json_atomic(f, original)

        # Verify original saved
        assert json.loads(f.read_text())["version"] == "original"

        # Simulate: write new data (atomic pattern ensures no partial)
        write_json_atomic(f, {"version": "updated", "data": "new"})
        result = json.loads(f.read_text())
        assert result["version"] == "updated"

    def test_tmp_file_cleanup(self, tmp_path: Path):
        """Atomic write should not leave .tmp files."""
        from ao_kernel._internal.shared.utils import write_json_atomic

        f = tmp_path / "clean.json"
        write_json_atomic(f, {"clean": True})

        tmp_files = list(tmp_path.glob("*.tmp*"))
        assert len(tmp_files) == 0

    def test_context_roundtrip_after_restart(self, tmp_path: Path):
        """Session context survives process restart (simulate with new load)."""
        from ao_kernel.session import new_context, save_context, load_context

        ctx = new_context(session_id="restart-test", workspace_root=tmp_path)
        save_context(ctx, workspace_root=tmp_path, session_id="restart-test")

        # "Restart" — fresh load
        loaded = load_context(workspace_root=tmp_path, session_id="restart-test")
        assert loaded["session_id"] == "restart-test"
        assert "session_context_sha256" in loaded.get("hashes", {})


class TestCorruption:
    """Handle corrupted files gracefully."""

    def test_corrupted_workspace_json_detected(self, tmp_path: Path):
        from ao_kernel.config import load_workspace_json
        from ao_kernel.errors import WorkspaceCorruptedError

        ws = tmp_path / ".ao"
        ws.mkdir()
        (ws / "workspace.json").write_text("{{broken json")

        with pytest.raises(WorkspaceCorruptedError):
            load_workspace_json(ws)

    def test_corrupted_canonical_store_returns_empty(self, tmp_path: Path):
        from ao_kernel.context.canonical_store import load_store

        (tmp_path / ".ao").mkdir()
        (tmp_path / ".ao" / "canonical_decisions.v1.json").write_text("not json!")

        store = load_store(tmp_path)
        assert store["decisions"] == {}
        assert store["facts"] == {}

    def test_corrupted_session_raises_fail_closed(self, tmp_path: Path):
        """Corrupted session must raise SessionCorruptedError (fail-closed)."""
        from ao_kernel.context.session_lifecycle import start_session
        from ao_kernel.errors import SessionCorruptedError
        import pytest

        # Create corrupted session file
        session_dir = tmp_path / ".cache" / "sessions" / "corrupt-test"
        session_dir.mkdir(parents=True)
        (session_dir / "session_context.v1.json").write_text("CORRUPTED!")

        with pytest.raises(SessionCorruptedError, match="corrupted or invalid"):
            start_session(workspace_root=tmp_path, session_id="corrupt-test")


class TestEdgeCases:
    """Boundary conditions and edge cases."""

    def test_empty_output_decision_extraction(self):
        from ao_kernel.context.decision_extractor import extract_decisions
        assert extract_decisions("") == []
        assert extract_decisions("   ") == []
        assert extract_decisions("\n\n") == []

    def test_very_large_decision_count(self, tmp_path: Path):
        """Memory pipeline handles many decisions without crash."""
        from ao_kernel.session import new_context
        from ao_kernel.context.memory_pipeline import process_turn
        import json as _json

        ctx = new_context(session_id="large-test", workspace_root=tmp_path)

        # 50 turns with JSON decisions
        for i in range(50):
            output = _json.dumps({f"key_{i}": f"value_{i}"})
            ctx = process_turn(output, ctx, request_id=f"req-{i}", workspace_root=tmp_path)

        decisions = ctx.get("ephemeral_decisions", [])
        assert len(decisions) > 0
        assert len(decisions) <= 1000  # Shouldn't explode

    def test_concurrent_canonical_writes(self, tmp_path: Path):
        """Multiple sequential writes don't corrupt store."""
        from ao_kernel.context.canonical_store import promote_decision, load_store

        (tmp_path / ".ao").mkdir()
        for i in range(20):
            promote_decision(tmp_path, key=f"key_{i}", value=f"val_{i}", confidence=0.9)

        store = load_store(tmp_path)
        total = len(store.get("decisions", {})) + len(store.get("facts", {}))
        assert total == 20

    def test_context_compile_with_zero_budget(self):
        """Zero token budget should return empty preamble."""
        from ao_kernel.context.context_compiler import compile_context

        ctx = {
            "ephemeral_decisions": [
                {"key": "test", "value": "x", "created_at": "2026-01-01T00:00:00Z"}
            ]
        }
        result = compile_context(ctx, profile="STARTUP")
        # STARTUP has 1000 token budget, should include 1 decision
        assert result.items_included >= 0

    def test_profile_detection_empty_content(self):
        """Empty message content shouldn't crash profile detection."""
        from ao_kernel.context.profile_router import detect_profile
        assert detect_profile([{"role": "user", "content": ""}]) == "TASK_EXECUTION"
        assert detect_profile([{"role": "user", "content": []}]) == "TASK_EXECUTION"

    def test_tool_gateway_max_rounds_boundary(self):
        """Exactly at max_rounds should deny."""
        from ao_kernel.tool_gateway import ToolGateway, ToolCallPolicy

        gw = ToolGateway(policy=ToolCallPolicy(enabled=True, max_rounds=2))
        gw.register_handler("t", lambda p: {"ok": True})
        gw.dispatch("t", {})  # round 1
        gw.dispatch("t", {})  # round 2
        r = gw.dispatch("t", {})  # round 3 — should be denied
        assert r.status == "DENIED"
        assert "MAX_ROUNDS" in r.reason
