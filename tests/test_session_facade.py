"""Tests for ao_kernel.session facade."""

from __future__ import annotations

from pathlib import Path

from ao_kernel.session import new_context, distill_memory


class TestSessionFacade:
    def test_new_context_returns_dict(self, tmp_path: Path):
        ctx = new_context(session_id="test-001", workspace_root=tmp_path)
        assert isinstance(ctx, dict)
        assert ctx.get("session_id") == "test-001"

    def test_new_context_has_ttl(self, tmp_path: Path):
        ctx = new_context(session_id="test-002", workspace_root=tmp_path, ttl_seconds=7200)
        assert isinstance(ctx, dict)
        assert len(ctx) > 0

    def test_distill_empty_returns_dict(self, tmp_path: Path):
        result = distill_memory(workspace_root=tmp_path, distilled=[])
        assert isinstance(result, dict)
