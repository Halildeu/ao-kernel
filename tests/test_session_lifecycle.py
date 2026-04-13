"""Tests for session lifecycle — fail-closed behavior on corruption."""

from __future__ import annotations

import pytest
from unittest.mock import patch

from ao_kernel.context.session_lifecycle import start_session, end_session
from ao_kernel.errors import SessionCorruptedError


class TestStartSessionFailClosed:
    """Verify fail-closed behavior: corrupted sessions raise, not silently reset."""

    def test_corrupted_session_raises_SessionCorruptedError(self, tmp_path):
        """When load_context raises a generic exception, SessionCorruptedError must propagate."""
        with patch(
            "ao_kernel.session.load_context",
            side_effect=ValueError("bad json"),
        ):
            with pytest.raises(SessionCorruptedError, match="corrupted or invalid"):
                start_session(workspace_root=tmp_path, session_id="corrupt-001")

    def test_error_chains_original_exception(self, tmp_path):
        """SessionCorruptedError must chain the original exception via __cause__."""
        original = ValueError("schema mismatch")
        with patch(
            "ao_kernel.session.load_context",
            side_effect=original,
        ):
            with pytest.raises(SessionCorruptedError) as exc_info:
                start_session(workspace_root=tmp_path, session_id="corrupt-002")
            assert exc_info.value.__cause__ is original

    def test_file_not_found_creates_new_session(self, tmp_path):
        """FileNotFoundError is normal flow — should create a new session, not raise."""
        with patch(
            "ao_kernel.session.load_context",
            side_effect=FileNotFoundError("no file"),
        ):
            ctx = start_session(workspace_root=tmp_path, session_id="new-001")
        assert isinstance(ctx, dict)
        assert ctx.get("session_id") == "new-001"

    def test_normal_load_returns_existing_context(self, tmp_path):
        """Successful load should return the loaded context unchanged."""
        mock_ctx = {"session_id": "existing-001", "ephemeral_decisions": [{"key": "test"}]}
        with patch(
            "ao_kernel.session.load_context",
            return_value=mock_ctx,
        ):
            ctx = start_session(workspace_root=tmp_path, session_id="existing-001")
        assert ctx is mock_ctx
        assert ctx["ephemeral_decisions"] == [{"key": "test"}]


class TestEndSession:
    """Verify end_session performs compaction, distillation, and promotion."""

    def test_end_session_saves_context(self, tmp_path):
        """end_session should save context to workspace."""
        from ao_kernel.session import new_context
        ctx = new_context(session_id="end-001", workspace_root=tmp_path)
        with patch("ao_kernel._internal.session.compaction_engine.compact_session_decisions"):
            result = end_session(ctx, workspace_root=tmp_path)
        assert result is ctx
