"""Tests for PR-B2 commit 5b — entrypoint plumbing.

3 callers route through governed_call:
  - AoKernelClient.llm_call (non-streaming branch)
  - mcp_server.handle_llm_call
  - workflow.intent_router._llm_classify

This file focuses on:
  - Envelope preservation (CAPABILITY_GAP / TRANSPORT_ERROR stay as-is)
  - MCP tool schema widening (ao_run_id / ao_step_id / ao_attempt
    optional params declared)
  - intent_router bypass-only contract (no cost identity passes through)
  - Streaming stays on existing _execute_stream path (v5 iter-4 B2)

End-to-end cost-active integration (with mocked transport) is covered
implicitly by the middleware-core tests in commit 5a; this file pins
the wiring.
"""

from __future__ import annotations

from ao_kernel.mcp_server import TOOL_DEFINITIONS


def _find_tool_spec(name: str) -> dict:
    for spec in TOOL_DEFINITIONS:
        if spec.get("name") == name:
            return spec
    raise AssertionError(f"tool spec {name!r} not in TOOL_DEFINITIONS")


class TestMcpToolSchemaWiden:
    def test_ao_llm_call_declares_cost_identity_params(self) -> None:
        spec = _find_tool_spec("ao_llm_call")
        props = spec["inputSchema"]["properties"]
        # PR-B2 v5 iter-4 MCP widen: three optional params.
        assert "ao_run_id" in props
        assert "ao_step_id" in props
        assert "ao_attempt" in props
        # Schema types match the middleware contract.
        assert props["ao_run_id"]["type"] == "string"
        assert props["ao_step_id"]["type"] == "string"
        assert props["ao_attempt"]["type"] == "integer"
        assert props["ao_attempt"].get("minimum") == 1
        # They remain optional (not in required).
        required = spec["inputSchema"].get("required", [])
        assert "ao_run_id" not in required
        assert "ao_step_id" not in required
        assert "ao_attempt" not in required


class TestIntentRouterBypassContract:
    def test_llm_classify_passes_all_bypass_kwargs(self) -> None:
        """intent_router._llm_classify calls governed_call with ALL cost
        + context kwargs explicitly set to None (bypass-only).

        Inspect the source to guard against drift; an implementation
        that starts threading session_context or run_id through would
        violate the v7 §10 position 13 pin.
        """
        import inspect

        from ao_kernel.workflow.intent_router import IntentRouter

        source = inspect.getsource(IntentRouter._llm_classify)
        # The governed_call invocation must explicitly set each of
        # these to None (bypass-only).
        assert "session_context=None" in source
        assert "workspace_root_str=None" in source
        assert "profile=None" in source
        assert "embedding_config=None" in source
        assert "vector_store=None" in source
        assert "workspace_root=None" in source
        assert "run_id=None" in source
        assert "step_id=None" in source
        assert "attempt=None" in source
        # Uses governed_call (not the pre-B2 three-call sequence).
        assert "governed_call" in source

    def test_llm_classify_error_mapping_preserved(self) -> None:
        """Source-level guard: four IntentClassificationError reason
        values are still raised (llm_extra_missing, no_available_workflows,
        llm_transport_error, llm_invalid_response). PR-A6 B4 contract
        preserved."""
        import inspect

        from ao_kernel.workflow.intent_router import IntentRouter

        source = inspect.getsource(IntentRouter._llm_classify)
        assert 'reason="llm_extra_missing"' in source
        assert 'reason="no_available_workflows"' in source
        assert 'reason="llm_transport_error"' in source
        assert 'reason="llm_invalid_response"' in source


class TestClientLlmCallSignature:
    def test_llm_call_accepts_cost_identity_kwargs(self) -> None:
        """AoKernelClient.llm_call signature widened with run_id,
        step_id, attempt optional kwargs (v5 iter-4 B2 opt-in path)."""
        import inspect

        from ao_kernel.client import AoKernelClient

        sig = inspect.signature(AoKernelClient.llm_call)
        assert "run_id" in sig.parameters
        assert "step_id" in sig.parameters
        assert "attempt" in sig.parameters
        # All three default to None.
        assert sig.parameters["run_id"].default is None
        assert sig.parameters["step_id"].default is None
        assert sig.parameters["attempt"].default is None

    def test_llm_call_nonstream_delegates_to_governed_call(self) -> None:
        """Non-streaming branch threads kwargs into governed_call.

        Source-level guard: the implementation calls governed_call and
        passes workspace_root, run_id, step_id, attempt through.
        """
        import inspect

        from ao_kernel.client import AoKernelClient

        source = inspect.getsource(AoKernelClient.llm_call)
        assert "governed_call" in source
        # Cost identity threading.
        assert "run_id=run_id" in source
        assert "step_id=step_id" in source
        assert "attempt=attempt" in source
        # Context injection wired via session_context kwarg.
        assert "session_context=" in source

    def test_stream_branch_untouched(self) -> None:
        """Streaming path stays on build + _execute_stream — not
        governed_call. Regression guard: plan v5 iter-4 B2 pin.

        Structural check: the ``if stream:`` branch dispatches
        ``_execute_stream`` and returns; the governed_call invocation
        (``result = governed_call(``) executes only on the stream=False
        path and must therefore appear AFTER the stream branch's
        return statement in source order.
        """
        import inspect

        from ao_kernel.client import AoKernelClient

        source = inspect.getsource(AoKernelClient.llm_call)
        assert "_execute_stream" in source
        stream_pos = source.find("if stream")
        stream_return_pos = source.find("return self._execute_stream", stream_pos)
        # Match the actual invocation pattern (not the docstring mention).
        governed_invocation_pos = source.find("result = governed_call(")
        assert stream_pos != -1
        assert stream_return_pos != -1
        assert governed_invocation_pos != -1
        # stream check returns before the governed_call invocation.
        assert stream_return_pos < governed_invocation_pos


class TestMcpHandleLlmCall:
    def test_reads_ao_identity_params(self) -> None:
        """mcp_server.handle_llm_call reads optional ao_run_id / ao_step_id
        / ao_attempt from params and threads them to governed_call."""
        import inspect

        from ao_kernel.mcp_server import handle_llm_call

        source = inspect.getsource(handle_llm_call)
        assert 'params.get("ao_run_id")' in source
        assert 'params.get("ao_step_id")' in source
        assert 'params.get("ao_attempt")' in source
        assert "governed_call" in source

    def test_capability_gap_returns_deny_envelope(self) -> None:
        """Source-level pin: governed_call CAPABILITY_GAP result is
        mapped to a decision=deny envelope with CAPABILITY_GAP reason
        code (preserves mcp_server pre-B2 contract)."""
        import inspect

        from ao_kernel.mcp_server import handle_llm_call

        source = inspect.getsource(handle_llm_call)
        assert '"CAPABILITY_GAP"' in source
        assert '"TRANSPORT_ERROR"' in source

    def test_session_context_not_threaded(self) -> None:
        """MCP is the thin-executor surface; session context DOES NOT
        flow through (pre-B2 behavior preserved)."""
        import inspect

        from ao_kernel.mcp_server import handle_llm_call

        source = inspect.getsource(handle_llm_call)
        # governed_call invocation must pass session_context=None.
        assert "session_context=None" in source
