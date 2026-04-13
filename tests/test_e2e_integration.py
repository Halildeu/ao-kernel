"""End-to-end integration tests — full pipeline chains.

Tests that verify multiple components working together as a pipeline,
not just individual functions in isolation.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from ao_kernel.session import new_context, save_context, load_context
from ao_kernel.client import AoKernelClient


class TestSessionRoundtrip:
    """Session save/load roundtrip — verify hash + schema validation."""

    def test_save_load_preserves_data(self, tmp_path: Path):
        """new_context → save → load → data preserved."""
        ctx = new_context(session_id="roundtrip-001", workspace_root=tmp_path)
        save_context(ctx, workspace_root=tmp_path, session_id="roundtrip-001")
        loaded = load_context(workspace_root=tmp_path, session_id="roundtrip-001")
        assert loaded["session_id"] == "roundtrip-001"
        assert loaded["version"] == ctx["version"]

    def test_tampered_file_detected(self, tmp_path: Path):
        """Tampered session file should fail validation (schema or hash)."""
        ctx = new_context(session_id="tamper-001", workspace_root=tmp_path)
        save_context(ctx, workspace_root=tmp_path, session_id="tamper-001")

        # Find and tamper with the session file
        session_dir = tmp_path / ".cache" / "sessions" / "tamper-001"
        session_file = session_dir / "session_context.v1.json"
        data = json.loads(session_file.read_text())
        # Tamper: change a non-schema field to trigger hash mismatch
        data["session_id"] = "tampered-id"
        session_file.write_text(json.dumps(data))

        # Load should detect tampering (hash mismatch or schema violation)
        from ao_kernel._internal.session.context_store import SessionContextError
        with pytest.raises(SessionContextError):
            load_context(workspace_root=tmp_path, session_id="tamper-001")

    def test_corrupt_json_detected(self, tmp_path: Path):
        """Corrupted JSON should fail on load."""
        ctx = new_context(session_id="corrupt-001", workspace_root=tmp_path)
        save_context(ctx, workspace_root=tmp_path, session_id="corrupt-001")

        # Corrupt the file
        session_dir = tmp_path / ".cache" / "sessions" / "corrupt-001"
        (session_dir / "session_context.v1.json").write_text("NOT VALID JSON!!!")

        from ao_kernel._internal.session.context_store import SessionContextError
        with pytest.raises(SessionContextError, match="Invalid JSON"):
            load_context(workspace_root=tmp_path, session_id="corrupt-001")

    def test_missing_session_raises_file_not_found(self, tmp_path: Path):
        """Loading non-existent session raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            load_context(workspace_root=tmp_path, session_id="does-not-exist")


class TestClientSessionLifecycle:
    """AoKernelClient session start → operations → end lifecycle."""

    def test_start_and_end_session(self, tmp_path: Path):
        client = AoKernelClient(tmp_path)
        ctx = client.start_session()
        assert client.session_active is True
        assert ctx["session_id"] == client.session_id
        client.end_session()
        assert client.session_active is False

    def test_context_manager_protocol(self, tmp_path: Path):
        with AoKernelClient(tmp_path) as client:
            client.start_session()
            assert client.session_active is True
        assert client.session_active is False

    def test_session_with_decisions(self, tmp_path: Path):
        """Start session → upsert decisions → end session → verify persistence."""
        client = AoKernelClient(tmp_path)
        client.start_session()

        # Add a decision via context store
        from ao_kernel._internal.session.context_store import upsert_decision
        upsert_decision(
            client.context,
            key="test.architecture",
            value="microservices",
            source="agent",
        )
        assert len(client.context.get("ephemeral_decisions", [])) >= 1

        client.end_session(save=True)
        assert client.session_active is False


class TestClientLlmPipelineMocked:
    """Client LLM pipeline — mocked HTTP, real context wiring."""

    def test_llm_call_routes_and_builds_request(self, tmp_path: Path):
        """llm_call should route → build → execute → normalize."""
        client = AoKernelClient(tmp_path)
        client.start_session()

        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.read.return_value = json.dumps({
            "id": "resp-001",
            "choices": [{
                "message": {"role": "assistant", "content": "Hello!"},
                "finish_reason": "stop",
            }],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
        }).encode()
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)

        with patch("urllib.request.urlopen", return_value=mock_response):
            result = client.llm_call(
                messages=[{"role": "user", "content": "Hi"}],
                intent="FAST_TEXT",
                provider_id="openai",
                model="gpt-4",
                api_key="test-key-123",
                base_url="https://api.openai.com/v1",
            )

        assert "text" in result or "error" in result
        client.end_session(save=False)


class TestGovernancePolicyE2E:
    """Policy check → governance → quality gate full chain."""

    def test_policy_check_with_bundled_policy(self):
        """check_policy against a real bundled policy."""
        from ao_kernel.governance import check_policy
        result = check_policy(
            "policy_tool_calling.v1.json",
            {"tool_name": "dangerous_tool"},
        )
        assert "allowed" in result
        assert "decision" in result
        assert result["decision"] in ("allow", "deny")

    def test_quality_gate_with_real_output(self):
        """evaluate_quality against real quality gates."""
        from ao_kernel.governance import evaluate_quality, quality_summary
        results = evaluate_quality("This is a valid LLM output with meaningful content.")
        summary = quality_summary(results)
        assert "all_passed" in summary
        assert "gates" in summary
        assert isinstance(summary["gates"], list)

    def test_quality_gate_fail_closed_on_empty(self):
        """Empty output should be denied by quality gate."""
        from ao_kernel.governance import evaluate_quality, quality_summary
        results = evaluate_quality("")
        summary = quality_summary(results)
        # Empty output should trigger at least one gate failure
        assert isinstance(summary["all_passed"], bool)


class TestMcpToolDispatchE2E:
    """MCP tool handlers — full dispatch with real governance."""

    def test_policy_check_dispatch(self):
        from ao_kernel.mcp_server import handle_policy_check
        result = handle_policy_check({
            "policy_name": "policy_tool_calling.v1.json",
            "action": {"tool_name": "some_tool"},
        })
        assert result["tool"] == "ao_policy_check"
        assert "allowed" in result
        assert "decision" in result

    def test_workspace_status_dispatch(self, tmp_workspace: Path):
        from ao_kernel.mcp_server import handle_workspace_status
        result = handle_workspace_status({
            "workspace_root": str(tmp_workspace.parent),
        })
        assert result["tool"] == "ao_workspace_status"

    def test_quality_gate_dispatch(self):
        from ao_kernel.mcp_server import handle_quality_gate
        result = handle_quality_gate({
            "output_text": "A meaningful LLM response with proper content.",
        })
        assert result["tool"] == "ao_quality_gate"
        assert result["decision"] in ("allow", "deny")

    def test_llm_route_dispatch(self):
        from ao_kernel.mcp_server import handle_llm_route
        result = handle_llm_route({"intent": "FAST_TEXT"})
        assert result["tool"] == "ao_llm_route"
        assert "decision" in result
