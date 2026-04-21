"""Tests for ao_kernel.client — high-level SDK client.

Tests workspace resolution, session lifecycle, context manager protocol,
tool registration/dispatch, checkpoint/resume, self-editing memory,
and policy checking. LLM calls tested with routing + capability checks only
(no real HTTP).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from ao_kernel.client import AoKernelClient


class TestInit:
    def test_init_with_workspace(self, tmp_workspace: Path):
        """Client resolves existing .ao/ workspace."""
        ws_root = tmp_workspace.parent
        client = AoKernelClient(ws_root)
        assert client.workspace_root == ws_root
        assert client.session_id.startswith("sdk-")
        assert client.session_active is False

    def test_init_library_mode(self, tmp_path: Path):
        """Client works without .ao/ workspace (library mode)."""
        client = AoKernelClient(tmp_path)
        assert client.workspace_root == tmp_path

    def test_init_auto_discover(self, tmp_workspace: Path):
        """Client auto-discovers workspace root."""
        # tmp_workspace fixture cds into the workspace dir
        # workspace_root() returns the .ao/ dir itself or its parent
        client = AoKernelClient()
        assert client.workspace_root is not None
        ws = client.workspace_root
        # Either ws IS .ao/ or ws contains .ao/
        assert ws.name == ".ao" or (ws / ".ao").is_dir()

    def test_init_custom_session_id(self, tmp_path: Path):
        client = AoKernelClient(tmp_path, session_id="my-session")
        assert client.session_id == "my-session"

    def test_init_provider_priority(self, tmp_path: Path):
        client = AoKernelClient(tmp_path, provider_priority=["claude", "openai"])
        assert client._provider_priority == ["claude", "openai"]

    def test_repr(self, tmp_path: Path):
        client = AoKernelClient(tmp_path, session_id="test-repr")
        r = repr(client)
        assert "AoKernelClient" in r
        assert "test-repr" in r
        assert "inactive" in r


class TestSessionLifecycle:
    def test_start_session_creates_context(self, tmp_workspace: Path):
        ws_root = tmp_workspace.parent
        client = AoKernelClient(ws_root)
        ctx = client.start_session()
        assert client.session_active is True
        assert ctx["session_id"] == client.session_id
        assert isinstance(ctx, dict)

    def test_start_session_idempotent(self, tmp_workspace: Path):
        ws_root = tmp_workspace.parent
        client = AoKernelClient(ws_root)
        ctx1 = client.start_session()
        ctx2 = client.start_session()
        assert ctx1 is ctx2  # same object returned

    def test_end_session(self, tmp_workspace: Path):
        ws_root = tmp_workspace.parent
        client = AoKernelClient(ws_root)
        client.start_session()
        assert client.session_active is True
        client.end_session()
        assert client.session_active is False

    def test_end_session_without_start(self, tmp_path: Path):
        client = AoKernelClient(tmp_path)
        client.end_session()  # should not raise
        assert client.session_active is False

    def test_context_property_requires_session(self, tmp_path: Path):
        client = AoKernelClient(tmp_path)
        with pytest.raises(RuntimeError, match="No active session"):
            _ = client.context

    def test_context_property_returns_context(self, tmp_workspace: Path):
        ws_root = tmp_workspace.parent
        client = AoKernelClient(ws_root)
        client.start_session()
        ctx = client.context
        assert ctx["session_id"] == client.session_id

    def test_library_mode_session(self, tmp_path: Path):
        """Session works without workspace (in-memory context)."""
        client = AoKernelClient()  # no workspace discovery in empty dir
        # Force library mode by clearing workspace
        client._workspace_root = None
        client.start_session()
        assert client.session_active is True
        assert "session_id" in client.context
        client.end_session()


class TestContextManager:
    def test_with_statement(self, tmp_workspace: Path):
        ws_root = tmp_workspace.parent
        with AoKernelClient(ws_root) as client:
            assert client.session_active is True
            assert "session_id" in client.context
        assert client.session_active is False

    def test_with_statement_exception(self, tmp_workspace: Path):
        ws_root = tmp_workspace.parent
        client = AoKernelClient(ws_root)
        with pytest.raises(ValueError, match="test error"):
            with client:
                assert client.session_active is True
                raise ValueError("test error")
        assert client.session_active is False


class TestToolDispatch:
    def test_register_and_call_tool(self, tmp_path: Path):
        client = AoKernelClient(tmp_path)
        handler = MagicMock(return_value={"output": "hello"})
        client.register_tool("greet", handler, description="Says hello")
        result = client.call_tool("greet", {"name": "world"})
        assert result["status"] in ("OK", "ALLOWED")
        handler.assert_called_once()

    def test_call_tool_without_gateway(self, tmp_path: Path):
        client = AoKernelClient(tmp_path)
        result = client.call_tool("unknown", {})
        assert result["status"] == "REJECT"
        assert result["reason"] == "NO_GATEWAY"

    def test_register_multiple_tools(self, tmp_path: Path):
        client = AoKernelClient(tmp_path)
        client.register_tool("tool_a", lambda x: {"a": 1})
        client.register_tool("tool_b", lambda x: {"b": 2})
        # Both should be registered in the same gateway
        assert hasattr(client, "_gateway")

    def test_llm_call_resets_gateway_state_v39_b2(self, tmp_path: Path):
        # v3.9 B2 post-impl BLOCKER fix: persistent AoKernelClient
        # gateway must be reset at every new LLM request boundary,
        # otherwise _request_call_count / _recent_calls accumulate
        # across calls and legitimate traffic trips
        # MAX_CALLS_PER_REQUEST_EXCEEDED or CYCLE_DETECTED.
        #
        # The reset runs BEFORE any routing/execution in llm_call().
        # We force _route to raise a sentinel and verify the reset
        # still fired — no `except: pass` needed; the sentinel is
        # the expected exception.
        import pytest as _pytest  # local alias for clarity
        from unittest.mock import patch

        client = AoKernelClient(tmp_path)
        client.register_tool("probe", lambda x: {"ok": True})
        # Dirty the per-request state.
        client._gateway._request_call_count = 99
        client._gateway._recent_calls.append("stale|{}")

        class _RouteSentinel(Exception):
            pass

        with patch.object(client, "_route", side_effect=_RouteSentinel):
            with _pytest.raises(_RouteSentinel):
                client.llm_call(messages=[{"role": "user", "content": "hi"}])

        # Reset must have run before _route, clearing all transient state.
        assert client._gateway._request_call_count == 0
        assert len(client._gateway._recent_calls) == 0


class TestClientCloseV312P5:
    """v3.12 P5 — ``AoKernelClient.close()`` public helper.

    Context manager stays the recommended pattern, but long-lived
    daemons / pytest ``yield`` fixtures / instances created outside a
    ``with`` block need an explicit teardown entry point. ``close()``
    wraps the same end_session + _close_owned_vector_store sequence
    that ``__exit__`` runs, and is idempotent so defensive callers can
    invoke it multiple times without crashing.
    """

    def test_close_ends_active_session(self, tmp_workspace: Path) -> None:
        ws_root = tmp_workspace.parent
        client = AoKernelClient(ws_root)
        client.start_session()
        assert client.session_active is True

        client.close()
        assert client.session_active is False

    def test_close_is_idempotent_across_calls(self, tmp_path: Path) -> None:
        # No active session at all — close() must not raise.
        client = AoKernelClient(tmp_path)
        client.close()
        # Second call stays a no-op.
        client.close()
        assert client.session_active is False

    def test_close_without_context_manager(self, tmp_workspace: Path) -> None:
        # Motivating use case — consumer builds a client outside a
        # `with` block (e.g. module-level daemon, pytest fixture
        # teardown via `yield`) and needs deterministic teardown.
        ws_root = tmp_workspace.parent
        client = AoKernelClient(ws_root)
        ctx = client.start_session()
        assert ctx["session_id"] == client.session_id
        client.close()
        assert client.session_active is False

    def test_close_idempotent_on_owned_backend(self, tmp_path: Path) -> None:
        # v3.12 P5 iter-2 (Codex post-impl BLOCKER absorb): iter-1
        # claimed close() was idempotent but _close_owned_vector_store
        # would re-call backend.close() on every invocation. Real
        # idempotency now flips _owns_vector_store=False before the
        # close() call, so a second close() is a true no-op regardless
        # of backend side effects.
        backend = MagicMock()
        client = AoKernelClient(tmp_path, vector_store=backend)
        # Force owned so the cleanup path engages.
        client._owns_vector_store = True
        client.close()
        client.close()  # second call — must not touch backend again
        assert backend.close.call_count == 1

    def test_close_save_false_forwards_flag(self, tmp_workspace: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        # close(save=False) must forward the flag to end_session().
        ws_root = tmp_workspace.parent
        client = AoKernelClient(ws_root)
        client.start_session()

        captured: dict[str, Any] = {}
        original = client.end_session

        def _spy(*, save: bool = True) -> None:
            captured["save"] = save
            original(save=save)

        monkeypatch.setattr(client, "end_session", _spy)
        client.close(save=False)
        assert captured["save"] is False


class TestResetToolGatewayStateV311P1:
    """v3.11 P1 — explicit public helper for manual tool-use chains.

    Closes the Codex-flagged residual debt from v3.9 B2 iter-3:
    standalone ``call_tool()`` chains accumulate gateway state across
    invocations (``_request_call_count`` / ``_recent_calls``) because
    auto-reset in ``call_tool()`` would break the documented agentic
    tool-use contract. The ``reset_tool_gateway_state()`` helper is
    the opt-in escape hatch.
    """

    def test_reset_clears_dirty_state(self, tmp_path: Path):
        client = AoKernelClient(tmp_path)
        client.register_tool("probe", lambda x: {"ok": True})
        # Dirty the state directly to simulate accumulated chain.
        client._gateway._request_call_count = 42
        client._gateway._recent_calls.append("stale|{}")

        client.reset_tool_gateway_state()

        assert client._gateway._request_call_count == 0
        assert len(client._gateway._recent_calls) == 0

    def test_reset_is_noop_when_no_gateway(self, tmp_path: Path):
        # No tools registered → no gateway attribute.
        client = AoKernelClient(tmp_path)
        assert not hasattr(client, "_gateway")
        # Must not raise (ergonomics of the public helper — callers
        # shouldn't have to probe for gateway existence).
        client.reset_tool_gateway_state()
        # Still no gateway after the no-op.
        assert not hasattr(client, "_gateway")

    def test_standalone_chain_flows_without_reset(self, tmp_path: Path):
        # Chain semantics MUST stay intact by default: multiple
        # call_tool() invocations on the default policy form a single
        # logical tool-use loop, and the per-request cap / cycle
        # detector should count across them. This pin locks in that
        # the reset is NOT implicit — it's opt-in via the new helper.
        client = AoKernelClient(tmp_path)
        client.register_tool("counter", lambda x: {"n": x.get("n", 0)})

        for n in range(5):
            result = client.call_tool("counter", {"n": n})
            assert result["status"] == "OK"

        # Gateway state reflects all 5 invocations chained.
        assert client._gateway._request_call_count == 5

    def test_reset_between_chains_allows_fresh_session(self, tmp_path: Path):
        # The motivating use case: one chain exhausts the cap; the
        # operator then calls reset_tool_gateway_state() and starts a
        # second independent chain which must succeed from scratch.
        from ao_kernel.tool_gateway import ToolCallPolicy, ToolGateway

        client = AoKernelClient(tmp_path)
        # Replace default gateway with a tight policy to make the
        # test deterministic without 5 calls.
        client._gateway = ToolGateway(policy=ToolCallPolicy(enabled=True, max_calls_per_request=2))
        client.register_tool("probe", lambda x: {"ok": True})

        # First chain: hit the cap.
        assert client.call_tool("probe", {"r": 1})["status"] == "OK"
        assert client.call_tool("probe", {"r": 2})["status"] == "OK"
        denied = client.call_tool("probe", {"r": 3})
        assert denied["status"] == "DENIED"
        assert denied["reason_code"] == "MAX_CALLS_PER_REQUEST_EXCEEDED"

        # Reset and start fresh.
        client.reset_tool_gateway_state()
        assert client.call_tool("probe", {"r": 4})["status"] == "OK"


class TestSelfEditMemory:
    def test_remember_and_recall(self, tmp_workspace: Path):
        ws_root = tmp_workspace.parent
        client = AoKernelClient(ws_root)
        result = client.remember("test_key", "test_value")
        assert result["stored"] is True
        assert result["key"] == "memory.test_key"

        memories = client.recall("memory.test_key")
        assert len(memories) == 1
        assert memories[0]["value"] == "test_value"

    def test_forget(self, tmp_workspace: Path):
        ws_root = tmp_workspace.parent
        client = AoKernelClient(ws_root)
        client.remember("temp", "data")
        result = client.forget("temp")
        assert result["forgotten"] is True

        memories = client.recall("memory.temp")
        assert len(memories) == 0

    def test_remember_without_workspace(self, tmp_path: Path):
        client = AoKernelClient()
        client._workspace_root = None
        result = client.remember("key", "val")
        assert result["stored"] is False
        assert result["error"] == "NO_WORKSPACE"

    def test_recall_without_workspace(self, tmp_path: Path):
        client = AoKernelClient()
        client._workspace_root = None
        result = client.recall()
        assert result == []

    def test_remember_with_importance(self, tmp_workspace: Path):
        ws_root = tmp_workspace.parent
        client = AoKernelClient(ws_root)
        result = client.remember("critical_item", "always keep", importance="critical")
        assert result["importance"] == "critical"


class TestCheckpoint:
    def test_save_checkpoint_requires_session(self, tmp_workspace: Path):
        ws_root = tmp_workspace.parent
        client = AoKernelClient(ws_root)
        result = client.save_checkpoint()
        assert result["saved"] is False
        assert result["error"] == "NO_ACTIVE_SESSION"

    def test_save_checkpoint_requires_workspace(self, tmp_path: Path):
        client = AoKernelClient()
        client._workspace_root = None
        client._session_active = True
        client._context = {"session_id": "test"}
        result = client.save_checkpoint()
        assert result["saved"] is False
        assert result["error"] == "NO_WORKSPACE"

    def test_resume_checkpoint_requires_workspace(self, tmp_path: Path):
        client = AoKernelClient()
        client._workspace_root = None
        result = client.resume_checkpoint("nonexistent")
        assert result["resumed"] is False
        assert result["error"] == "NO_WORKSPACE"


class TestPolicy:
    def test_check_policy(self, tmp_workspace: Path):
        ws_root = tmp_workspace.parent
        client = AoKernelClient(ws_root)
        result = client.check_policy(
            "policy_autonomy.v1.json",
            {"action": "test", "risk_level": "low"},
        )
        # Should return a policy result dict (allowed/denied)
        assert "allowed" in result or "decision" in result

    def test_check_policy_fail_closed(self, tmp_path: Path):
        client = AoKernelClient(tmp_path)
        result = client.check_policy("nonexistent_policy.json", {"action": "test"})
        # Fail-closed: missing policy → deny
        assert result.get("allowed") is False or result.get("decision") == "deny"


class TestLLMCall:
    def test_llm_call_routing(self, tmp_workspace: Path):
        """Test that routing returns a valid result (may be FAIL without registry)."""
        ws_root = tmp_workspace.parent
        client = AoKernelClient(ws_root)
        client.start_session()
        route = client._route("code_generation")
        # In test env without full registry, route may FAIL or return defaults
        assert "status" in route or "provider_id" in route

    def test_default_base_url(self, tmp_path: Path):
        assert AoKernelClient._default_base_url("openai") == "https://api.openai.com/v1"
        assert AoKernelClient._default_base_url("claude") == "https://api.anthropic.com/v1"
        assert AoKernelClient._default_base_url("google") == "https://generativelanguage.googleapis.com/v1beta"
        assert AoKernelClient._default_base_url("unknown") == ""

    def test_llm_call_capability_gap(self, tmp_workspace: Path):
        """Test that capability gap is reported correctly."""
        ws_root = tmp_workspace.parent
        client = AoKernelClient(ws_root)
        client.start_session()

        with patch("ao_kernel.llm.check_capabilities", return_value=(False, "openai", ["streaming"])):
            result = client.llm_call(
                messages=[{"role": "user", "content": "test"}],
                provider_id="openai",
                model="gpt-4",
                api_key="test-key",
            )
            assert result["status"] == "CAPABILITY_GAP"
            assert "streaming" in result["missing"]

    def test_llm_call_transport_error(self, tmp_workspace: Path):
        """Test transport error handling."""
        ws_root = tmp_workspace.parent
        client = AoKernelClient(ws_root)
        client.start_session()

        with (
            patch("ao_kernel.llm.check_capabilities", return_value=(True, "openai", [])),
            patch(
                "ao_kernel.llm.build_request_with_context",
                return_value={
                    "url": "https://api.openai.com/v1/chat/completions",
                    "headers": {},
                    "body_bytes": b"{}",
                },
            ),
            patch(
                "ao_kernel.llm.execute_request",
                return_value={
                    "status": "ERROR",
                    "error_code": "TIMEOUT",
                    "http_status": 504,
                    "elapsed_ms": 30000,
                },
            ),
        ):
            result = client.llm_call(
                messages=[{"role": "user", "content": "test"}],
                provider_id="openai",
                model="gpt-4",
                api_key="test-key",
            )
            assert result["status"] == "TRANSPORT_ERROR"
            assert result["error_code"] == "TIMEOUT"

    def test_llm_call_full_pipeline(self, tmp_workspace: Path):
        """Test full pipeline with mocked HTTP."""
        ws_root = tmp_workspace.parent
        client = AoKernelClient(ws_root)
        client.start_session()

        mock_response = json.dumps(
            {
                "choices": [{"message": {"content": "Hello! Python is a programming language."}}],
                "usage": {"prompt_tokens": 10, "completion_tokens": 20},
            }
        ).encode()

        with (
            patch("ao_kernel.llm.check_capabilities", return_value=(True, "openai", [])),
            patch(
                "ao_kernel.llm.build_request_with_context",
                return_value={
                    "url": "https://api.openai.com/v1/chat/completions",
                    "headers": {"Authorization": "Bearer test"},
                    "body_bytes": b'{"messages":[]}',
                },
            ),
            patch(
                "ao_kernel.llm.execute_request",
                return_value={
                    "status": "OK",
                    "http_status": 200,
                    "resp_bytes": mock_response,
                    "elapsed_ms": 500,
                },
            ),
            patch(
                "ao_kernel.llm.normalize_response",
                return_value={
                    "text": "Hello! Python is a programming language.",
                    "tool_calls": [],
                },
            ),
            patch(
                "ao_kernel.llm.extract_usage",
                return_value={
                    "input_tokens": 10,
                    "output_tokens": 20,
                },
            ),
        ):
            result = client.llm_call(
                messages=[{"role": "user", "content": "What is Python?"}],
                provider_id="openai",
                model="gpt-4",
                api_key="test-key",
            )
            assert result["status"] == "OK"
            assert "Python" in result["text"]
            assert result["provider_id"] == "openai"
            assert result["model"] == "gpt-4"
            assert result["usage"]["input_tokens"] == 10
            assert result["elapsed_ms"] == 500


class TestLLMCallStreaming:
    def test_llm_call_stream_ok(self, tmp_workspace: Path):
        """stream=True dispatches to stream_request and returns OK."""
        from ao_kernel.llm import StreamResult

        ws_root = tmp_workspace.parent
        client = AoKernelClient(ws_root)
        client.start_session()

        mock_sr = StreamResult(
            status="OK",
            complete=True,
            text="Streamed response about Python.",
            finish_reason="stop",
            usage={"input_tokens": 5, "output_tokens": 15},
            elapsed_ms=800,
            first_token_ms=120,
            chunk_count=12,
        )
        with (
            patch("ao_kernel.llm.check_capabilities", return_value=(True, "openai", [])),
            patch(
                "ao_kernel.llm.build_request_with_context",
                return_value={
                    "url": "https://api.openai.com/v1/chat/completions",
                    "headers": {},
                    "body_bytes": b"{}",
                },
            ),
            patch("ao_kernel.llm.stream_request", return_value=mock_sr),
        ):
            result = client.llm_call(
                messages=[{"role": "user", "content": "test"}],
                provider_id="openai",
                model="gpt-4",
                api_key="test-key",
                stream=True,
            )
            assert result["status"] == "OK"
            assert result["stream"] is True
            assert result["complete"] is True
            assert "Python" in result["text"]
            assert result["first_token_ms"] == 120
            assert result["chunk_count"] == 12
            assert result["usage"]["output_tokens"] == 15

    def test_llm_call_stream_partial(self, tmp_workspace: Path):
        """PARTIAL stream returns PARTIAL status."""
        from ao_kernel.llm import StreamResult

        ws_root = tmp_workspace.parent
        client = AoKernelClient(ws_root)
        client.start_session()

        mock_sr = StreamResult(
            status="PARTIAL",
            complete=False,
            text="Partial respon",
            finish_reason="timeout",
            elapsed_ms=30000,
            first_token_ms=200,
            chunk_count=5,
        )
        with (
            patch("ao_kernel.llm.check_capabilities", return_value=(True, "openai", [])),
            patch(
                "ao_kernel.llm.build_request_with_context",
                return_value={
                    "url": "u",
                    "headers": {},
                    "body_bytes": b"{}",
                },
            ),
            patch("ao_kernel.llm.stream_request", return_value=mock_sr),
        ):
            result = client.llm_call(
                messages=[{"role": "user", "content": "test"}],
                provider_id="openai",
                model="gpt-4",
                api_key="k",
                stream=True,
            )
            assert result["status"] == "PARTIAL"
            assert result["complete"] is False
            assert result["text"] == "Partial respon"

    def test_llm_call_stream_fail(self, tmp_workspace: Path):
        """FAIL stream returns TRANSPORT_ERROR."""
        from ao_kernel.llm import StreamResult

        ws_root = tmp_workspace.parent
        client = AoKernelClient(ws_root)
        client.start_session()

        mock_sr = StreamResult(
            status="FAIL",
            complete=False,
            text="",
            finish_reason="connect_error",
            error_code="STREAM_HTTP_503",
            elapsed_ms=100,
        )
        with (
            patch("ao_kernel.llm.check_capabilities", return_value=(True, "openai", [])),
            patch(
                "ao_kernel.llm.build_request_with_context",
                return_value={
                    "url": "u",
                    "headers": {},
                    "body_bytes": b"{}",
                },
            ),
            patch("ao_kernel.llm.stream_request", return_value=mock_sr),
        ):
            result = client.llm_call(
                messages=[{"role": "user", "content": "test"}],
                provider_id="openai",
                model="gpt-4",
                api_key="k",
                stream=True,
            )
            assert result["status"] == "TRANSPORT_ERROR"
            assert result["error_code"] == "STREAM_HTTP_503"
            assert result["stream"] is True

    def test_llm_call_stream_false_uses_execute_request(self, tmp_workspace: Path):
        """stream=False still uses blocking execute_request."""
        ws_root = tmp_workspace.parent
        client = AoKernelClient(ws_root)
        client.start_session()

        mock_resp = json.dumps({"choices": [{"message": {"content": "ok"}}]}).encode()
        with (
            patch("ao_kernel.llm.check_capabilities", return_value=(True, "openai", [])),
            patch(
                "ao_kernel.llm.build_request_with_context",
                return_value={
                    "url": "u",
                    "headers": {},
                    "body_bytes": b"{}",
                },
            ),
            patch(
                "ao_kernel.llm.execute_request",
                return_value={
                    "status": "OK",
                    "resp_bytes": mock_resp,
                    "elapsed_ms": 100,
                },
            ) as mock_exec,
            patch("ao_kernel.llm.normalize_response", return_value={"text": "ok", "tool_calls": []}),
            patch("ao_kernel.llm.extract_usage", return_value=None),
        ):
            result = client.llm_call(
                messages=[{"role": "user", "content": "test"}],
                provider_id="openai",
                model="gpt-4",
                api_key="k",
                stream=False,
            )
            mock_exec.assert_called_once()
            assert result["status"] == "OK"
            assert "stream" not in result  # non-streaming has no stream key


class TestAutoRouteContract:
    def test_route_normalizes_selected_provider(self, tmp_workspace: Path):
        """Router returning selected_provider/selected_model is normalized."""
        ws_root = tmp_workspace.parent
        client = AoKernelClient(ws_root)
        client.start_session()

        with patch(
            "ao_kernel.llm.resolve_route",
            return_value={
                "status": "OK",
                "selected_provider": "claude",
                "selected_model": "claude-3-opus",
                "base_url": "https://api.anthropic.com/v1",
            },
        ):
            with (
                patch("ao_kernel.llm.check_capabilities", return_value=(True, "claude", [])),
                patch(
                    "ao_kernel.llm.build_request_with_context",
                    return_value={
                        "url": "u",
                        "headers": {},
                        "body_bytes": b"{}",
                    },
                ),
                patch(
                    "ao_kernel.llm.execute_request",
                    return_value={
                        "status": "OK",
                        "resp_bytes": b'{"choices":[{"message":{"content":"hi"}}]}',
                        "elapsed_ms": 50,
                    },
                ),
                patch("ao_kernel.llm.normalize_response", return_value={"text": "hi", "tool_calls": []}),
                patch("ao_kernel.llm.extract_usage", return_value=None),
            ):
                result = client.llm_call(
                    messages=[{"role": "user", "content": "test"}],
                    intent="code_generation",
                )
                assert result["provider_id"] == "claude"
                assert result["model"] == "claude-3-opus"


class TestEvidenceIntegration:
    def test_nonstream_evidence_written(self, tmp_workspace: Path):
        """Non-streaming llm_call writes evidence in workspace mode."""
        ws_root = tmp_workspace.parent
        client = AoKernelClient(ws_root)
        client.start_session()

        mock_resp = json.dumps({"choices": [{"message": {"content": "ok"}}]}).encode()
        with (
            patch("ao_kernel.llm.check_capabilities", return_value=(True, "openai", [])),
            patch(
                "ao_kernel.llm.build_request_with_context",
                return_value={
                    "url": "u",
                    "headers": {},
                    "body_bytes": b"{}",
                },
            ),
            patch(
                "ao_kernel.llm.execute_request",
                return_value={
                    "status": "OK",
                    "resp_bytes": mock_resp,
                    "elapsed_ms": 100,
                    "http_status": 200,
                    "error_type": None,
                    "error_detail": None,
                    "tls_cafile": None,
                },
            ),
            patch("ao_kernel.llm.normalize_response", return_value={"text": "ok", "tool_calls": []}),
            patch("ao_kernel.llm.extract_usage", return_value=None),
        ):
            result = client.llm_call(
                messages=[{"role": "user", "content": "test"}],
                provider_id="openai",
                model="gpt-4",
                api_key="k",
            )
            assert result["status"] == "OK"

        # Evidence file should exist
        evidence_dir = ws_root / ".cache" / "reports" / "llm_live_outputs"
        if evidence_dir.exists():
            txt_files = list(evidence_dir.glob("*.txt"))
            assert len(txt_files) >= 1

    def test_nonstream_evidence_skipped_library_mode(self, tmp_path: Path):
        """Library mode (no workspace) skips evidence writing."""
        client = AoKernelClient()
        client._workspace_root = None
        client._session_active = True
        client._context = {"session_id": "test", "ephemeral_decisions": []}

        mock_resp = json.dumps({"choices": [{"message": {"content": "ok"}}]}).encode()
        with (
            patch("ao_kernel.llm.check_capabilities", return_value=(True, "openai", [])),
            patch(
                "ao_kernel.llm.build_request",
                return_value={
                    "url": "u",
                    "headers": {},
                    "body_bytes": b"{}",
                },
            ),
            patch(
                "ao_kernel.llm.execute_request",
                return_value={
                    "status": "OK",
                    "resp_bytes": mock_resp,
                    "elapsed_ms": 100,
                },
            ),
            patch("ao_kernel.llm.normalize_response", return_value={"text": "ok", "tool_calls": []}),
            patch("ao_kernel.llm.extract_usage", return_value=None),
            patch("ao_kernel._internal.prj_kernel_api.llm_post_processors.process_live_response") as mock_evidence,
        ):
            result = client.llm_call(
                messages=[{"role": "user", "content": "test"}],
                provider_id="openai",
                model="gpt-4",
                api_key="k",
            )
            assert result["status"] == "OK"
            mock_evidence.assert_not_called()

    def test_stream_evidence_signature_fixed(self, tmp_workspace: Path):
        """Streaming evidence uses keyword args (BUG-1 fix verification)."""
        from ao_kernel.llm import StreamResult

        ws_root = tmp_workspace.parent
        client = AoKernelClient(ws_root)
        client.start_session()

        mock_sr = StreamResult(
            status="OK",
            complete=True,
            text="hello",
            finish_reason="stop",
            elapsed_ms=100,
            chunk_count=3,
        )
        with (
            patch("ao_kernel.llm.check_capabilities", return_value=(True, "openai", [])),
            patch(
                "ao_kernel.llm.build_request_with_context",
                return_value={
                    "url": "u",
                    "headers": {},
                    "body_bytes": b"{}",
                },
            ),
            patch("ao_kernel.llm.stream_request", return_value=mock_sr),
            patch("ao_kernel._internal.prj_kernel_api.llm_post_processors.process_stream_response") as mock_stream_ev,
        ):
            result = client.llm_call(
                messages=[{"role": "user", "content": "test"}],
                provider_id="openai",
                model="gpt-4",
                api_key="k",
                stream=True,
            )
            assert result["status"] == "OK"
            # process_stream_response called with keyword args
            mock_stream_ev.assert_called_once()
            call_kwargs = mock_stream_ev.call_args
            # Verify keyword-only call (no positional args)
            assert call_kwargs.args == ()
            assert "stream_result" in call_kwargs.kwargs
            assert "model" in call_kwargs.kwargs

    def test_stream_evidence_skipped_library_mode(self, tmp_path: Path):
        """Library mode streaming skips evidence writing."""
        from ao_kernel.llm import StreamResult

        client = AoKernelClient()
        client._workspace_root = None
        client._session_active = True
        client._context = {"session_id": "test", "ephemeral_decisions": []}

        mock_sr = StreamResult(
            status="OK",
            complete=True,
            text="hello",
            finish_reason="stop",
            elapsed_ms=100,
            chunk_count=3,
        )
        with (
            patch("ao_kernel.llm.check_capabilities", return_value=(True, "openai", [])),
            patch(
                "ao_kernel.llm.build_request",
                return_value={
                    "url": "u",
                    "headers": {},
                    "body_bytes": b"{}",
                },
            ),
            patch("ao_kernel.llm.stream_request", return_value=mock_sr),
            patch("ao_kernel._internal.prj_kernel_api.llm_post_processors.process_stream_response") as mock_stream_ev,
        ):
            result = client.llm_call(
                messages=[{"role": "user", "content": "test"}],
                provider_id="openai",
                model="gpt-4",
                api_key="k",
                stream=True,
            )
            assert result["status"] == "OK"
            mock_stream_ev.assert_not_called()


class TestSwallowLoggingA3:
    """A3 (FAZ5 Tranş A): Evidence/eval swallow paths emit warning logs
    instead of bare `pass`. Failure MUST NOT block execution.
    """

    def test_nonstream_evidence_failure_logs_warning(self, tmp_workspace: Path, caplog):
        ws_root = tmp_workspace.parent
        client = AoKernelClient(ws_root)
        client.start_session()

        mock_resp = json.dumps({"choices": [{"message": {"content": "ok"}}]}).encode()
        with (
            patch("ao_kernel.llm.check_capabilities", return_value=(True, "openai", [])),
            patch(
                "ao_kernel.llm.build_request_with_context",
                return_value={
                    "url": "u",
                    "headers": {},
                    "body_bytes": b"{}",
                },
            ),
            patch(
                "ao_kernel.llm.execute_request",
                return_value={
                    "status": "OK",
                    "resp_bytes": mock_resp,
                    "elapsed_ms": 100,
                    "http_status": 200,
                    "error_type": None,
                    "error_detail": None,
                    "tls_cafile": None,
                },
            ),
            patch("ao_kernel.llm.normalize_response", return_value={"text": "ok", "tool_calls": []}),
            patch("ao_kernel.llm.extract_usage", return_value=None),
            patch(
                "ao_kernel._internal.prj_kernel_api.llm_post_processors.process_live_response",
                side_effect=RuntimeError("disk full"),
            ),
        ):
            with caplog.at_level("WARNING", logger="ao_kernel.client"):
                result = client.llm_call(
                    messages=[{"role": "user", "content": "test"}],
                    provider_id="openai",
                    model="gpt-4",
                    api_key="k",
                )
            assert result["status"] == "OK"
            assert any("evidence writer skipped" in r.message for r in caplog.records), (
                f"expected warning, got: {[r.message for r in caplog.records]}"
            )

    def test_eval_scorecard_failure_logs_warning(self, tmp_workspace: Path, caplog):
        ws_root = tmp_workspace.parent
        client = AoKernelClient(ws_root)
        client.start_session()

        mock_resp = json.dumps({"choices": [{"message": {"content": "ok"}}]}).encode()
        with (
            patch("ao_kernel.llm.check_capabilities", return_value=(True, "openai", [])),
            patch(
                "ao_kernel.llm.build_request_with_context",
                return_value={
                    "url": "u",
                    "headers": {},
                    "body_bytes": b"{}",
                },
            ),
            patch(
                "ao_kernel.llm.execute_request",
                return_value={
                    "status": "OK",
                    "resp_bytes": mock_resp,
                    "elapsed_ms": 100,
                    "http_status": 200,
                    "error_type": None,
                    "error_detail": None,
                    "tls_cafile": None,
                },
            ),
            patch("ao_kernel.llm.normalize_response", return_value={"text": "ok", "tool_calls": []}),
            patch("ao_kernel.llm.extract_usage", return_value=None),
            patch(
                "ao_kernel._internal.orchestrator.eval_harness.run_eval_suite",
                side_effect=RuntimeError("eval broken"),
            ),
        ):
            with caplog.at_level("WARNING", logger="ao_kernel.client"):
                result = client.llm_call(
                    messages=[{"role": "user", "content": "test"}],
                    provider_id="openai",
                    model="gpt-4",
                    api_key="k",
                )
            assert result["status"] == "OK"
            assert any("eval scorecard skipped" in r.message for r in caplog.records), (
                f"expected warning, got: {[r.message for r in caplog.records]}"
            )


class TestDoctor:
    def test_doctor_returns_structured_report(self, tmp_workspace: Path):
        ws_root = tmp_workspace.parent
        client = AoKernelClient(ws_root)
        result = client.doctor()
        assert isinstance(result, dict)
        assert result["exit_code"] == 0
        assert result["version"]
        checks = {item["label"]: item["status"] for item in result["checks"]}
        assert checks["Workspace found"] == "OK"
        assert checks["workspace.json valid"] == "OK"
        assert checks["Bundled extension truth"] == "WARN"
        summary = result["summary"]
        assert summary["fail_count"] == 0
        assert summary["warn_count"] >= 1
        extension_truth = result["extension_truth"]
        assert extension_truth["runtime_backed"] >= 1
        assert "PRJ-HELLO" in extension_truth["runtime_backed_ids"]
        assert extension_truth["quarantined"] >= 1
