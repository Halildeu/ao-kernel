"""Tests for AoKernelClient agent-coordination SDK methods (B5e, CNS-009).

Verifies:
  - Wrapper delegation (same semantics as module-level helpers)
  - session_id auto-threaded into canonical provenance
  - Below-threshold decisions land in the client's active session context
  - Library-mode (no workspace) raises a clear error instead of silent failure
  - compile_context_sdk works without issuing an LLM call
  - finalize_session uses the single-primitive path (no double promotion)
"""

from __future__ import annotations

import pytest

from ao_kernel.client import AoKernelClient


@pytest.fixture
def ws_client(tmp_path):
    client = AoKernelClient(workspace_root=str(tmp_path), auto_init=True)
    return client


class TestRecordDecisionWrapper:
    def test_auto_promote_writes_canonical(self, ws_client):
        result = ws_client.record_decision(
            "release.version", "2.3.0", confidence=0.9,
        )
        assert result["promoted"] is True
        assert result["destination"] == "canonical"
        items = ws_client.query_memory(key_pattern="release.*")
        assert len(items) == 1

    def test_session_id_threads_into_provenance(self, ws_client):
        ws_client.record_decision(
            "plan.ok", True, confidence=0.95,
        )
        items = ws_client.query_memory()
        assert items[0]["promoted_from"] == ws_client.session_id

    def test_below_threshold_uses_active_session(self, ws_client):
        """Starting a session then calling record_decision with low confidence
        must land in ephemeral storage — no silent canonical write."""
        ws_client.start_session()
        result = ws_client.record_decision(
            "scratch.note", "tentative", confidence=0.3,
        )
        assert result["destination"] == "session"
        assert result["promoted"] is False
        assert ws_client.query_memory(key_pattern="scratch.*") == []
        assert any(
            d["key"] == "scratch.note"
            for d in ws_client.context["ephemeral_decisions"]
        )

    def test_below_threshold_without_session_drops(self, ws_client):
        result = ws_client.record_decision(
            "lost.note", "dropped", confidence=0.3,
        )
        assert result["destination"] == "dropped"
        assert result["recorded"] is False


class TestRevisionWrappers:
    def test_get_revision_is_64_char(self, ws_client):
        rev = ws_client.get_revision()
        assert len(rev) == 64

    def test_has_changed_detects_write(self, ws_client):
        rev0 = ws_client.get_revision()
        assert ws_client.has_changed(rev0) is False
        ws_client.record_decision("k", "v", confidence=0.9)
        assert ws_client.has_changed(rev0) is True

    def test_read_with_revision_surface(self, ws_client):
        ws_client.record_decision("a.b", 1, confidence=0.9)
        out = ws_client.read_with_revision(key_pattern="a.*")
        assert out["count"] == 1
        assert len(out["revision"]) == 64


class TestCompileContextWithoutLLMCall:
    def test_compile_without_session(self, ws_client):
        ws_client.record_decision("rule.x", "y", confidence=0.9)
        result = ws_client.compile_context_sdk(profile="TASK_EXECUTION")
        assert result["profile_id"] == "TASK_EXECUTION"
        assert result["items_included"] >= 1

    def test_compile_uses_active_session_context(self, ws_client):
        ws_client.start_session()
        # Ephemeral decision through a session record call.
        ws_client.record_decision("draft.x", "tentative", confidence=0.3)
        # session_context omitted -> client passes its own
        result = ws_client.compile_context_sdk(profile="TASK_EXECUTION")
        assert "draft.x" in result["preamble"] or result["items_included"] >= 1


class TestFinalizeSession:
    def test_finalize_auto_promote_flag_respected(self, ws_client):
        """Regression: finalize_session(auto_promote=False) must not promote."""
        ws_client.start_session()
        import json
        from ao_kernel.context.memory_pipeline import process_turn
        process_turn(
            json.dumps({"plan.status": "ready"}),
            ws_client.context,
            request_id="r",
            workspace_root=ws_client.workspace_root,
        )
        before = ws_client.query_memory()
        summary = ws_client.finalize_session(auto_promote=False)
        after = ws_client.query_memory()
        assert summary["finalized"] is True
        assert len(after) == len(before)
        assert ws_client.session_active is False

    def test_finalize_raises_without_active_session(self, ws_client):
        with pytest.raises(RuntimeError, match="No active session"):
            ws_client.finalize_session()


class TestLibraryModeGuard:
    """Library mode (no workspace) must refuse memory ops with a clear error."""

    @pytest.fixture
    def library_client(self, tmp_path, monkeypatch):
        # Move CWD somewhere without a .ao/ so find_root() returns None.
        isolated = tmp_path / "no-workspace"
        isolated.mkdir()
        monkeypatch.chdir(isolated)
        client = AoKernelClient()
        assert client.workspace_root is None, "sanity: expected library mode"
        return client

    def test_record_decision_requires_workspace(self, library_client):
        with pytest.raises(RuntimeError, match="requires a workspace"):
            library_client.record_decision("k", "v", confidence=0.9)

    def test_query_memory_requires_workspace(self, library_client):
        with pytest.raises(RuntimeError, match="requires a workspace"):
            library_client.query_memory()

    def test_get_revision_requires_workspace(self, library_client):
        with pytest.raises(RuntimeError, match="requires a workspace"):
            library_client.get_revision()
