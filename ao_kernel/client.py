"""ao_kernel.client — High-level SDK client for ao-kernel.

Unified entry point that composes workspace, session, LLM, governance,
context management, and tool gateway into a single governed client.

Usage:
    from ao_kernel.client import AoKernelClient

    client = AoKernelClient("/path/to/project")
    client.start_session()
    result = client.llm_call(
        messages=[{"role": "user", "content": "What is Python?"}],
        intent="question_answering",
    )
    print(result["text"])
    client.end_session()

The client is the recommended way to use ao-kernel as a library.
All operations are policy-gated, fail-closed, and evidence-trail'ed.
"""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any


class AoKernelClient:
    """High-level governed AI orchestration client.

    Composes all ao-kernel subsystems:
        - Workspace discovery + config
        - Session context lifecycle
        - Context-aware LLM calls (route → build → execute → normalize → extract)
        - Policy-gated tool dispatch
        - Checkpoint/resume
        - Self-editing memory
        - Telemetry (OTEL when available)
    """

    def __init__(
        self,
        workspace_root: str | Path | None = None,
        *,
        session_id: str | None = None,
        auto_init: bool = False,
        provider_priority: list[str] | None = None,
    ):
        """Initialize the client.

        Args:
            workspace_root: Project root (auto-discovers .ao/ if None).
            session_id: Explicit session ID (generated if None).
            auto_init: Create .ao/ workspace if not found.
            provider_priority: LLM provider preference order.
        """
        self._workspace_root = self._resolve_workspace(workspace_root, auto_init)
        self._session_id = session_id or f"sdk-{uuid.uuid4().hex[:12]}"
        self._provider_priority = provider_priority or []
        self._context: dict[str, Any] | None = None
        self._session_active = False

    @property
    def workspace_root(self) -> Path | None:
        """Resolved workspace root, or None in library mode."""
        return self._workspace_root

    @property
    def session_id(self) -> str:
        """Current session identifier."""
        return self._session_id

    @property
    def session_active(self) -> bool:
        """Whether a session is currently running."""
        return self._session_active

    @property
    def context(self) -> dict[str, Any]:
        """Current session context. Raises if no session active."""
        if self._context is None:
            raise RuntimeError("No active session. Call start_session() first.")
        return self._context

    # ── Workspace ───────────────────────────────────────────────────

    @staticmethod
    def _resolve_workspace(
        root: str | Path | None,
        auto_init: bool,
    ) -> Path | None:
        from ao_kernel.workspace import find_root

        if root is not None:
            ws = Path(root)
            if (ws / ".ao").is_dir():
                return ws
            if auto_init:
                from ao_kernel.workspace import init
                import os
                old_cwd = os.getcwd()
                os.chdir(str(ws))
                try:
                    init()
                finally:
                    os.chdir(old_cwd)
                return ws
            return ws  # library mode — no .ao/ required
        return find_root()

    def doctor(self) -> dict[str, Any]:
        """Run workspace health check. Returns check results."""
        from ao_kernel.doctor_cmd import run as _doctor_run
        import io
        import sys
        import json

        old_stdout = sys.stdout
        sys.stdout = buf = io.StringIO()
        try:
            rc = _doctor_run(
                workspace_root_override=str(self._workspace_root) if self._workspace_root else None,
            )
        finally:
            sys.stdout = old_stdout

        output = buf.getvalue()
        try:
            parsed = json.loads(output)
        except (json.JSONDecodeError, ValueError):
            return {"exit_code": rc, "output": output}
        if not isinstance(parsed, dict):
            return {"exit_code": rc, "output": output}
        return parsed

    # ── Session Lifecycle ───────────────────────────────────────────

    def start_session(
        self,
        *,
        ttl_seconds: int = 3600,
        resume: bool = False,
    ) -> dict[str, Any]:
        """Start or resume a session.

        Args:
            ttl_seconds: Session time-to-live (default 1 hour).
            resume: If True, try to load existing session context.

        Returns session context dict.
        """
        if self._session_active:
            return self._context  # type: ignore[return-value]

        ws = self._workspace_root
        if resume and ws:
            try:
                from ao_kernel.session import load_context
                ctx = load_context(ws, session_id=self._session_id)
                if ctx and ctx.get("session_id"):
                    self._context = ctx
                    self._session_active = True
                    return self._context
            except Exception:
                pass

        if ws:
            from ao_kernel.session import new_context
            self._context = new_context(
                session_id=self._session_id,
                workspace_root=ws,
                ttl_seconds=ttl_seconds,
            )
        else:
            # Library mode: in-memory context
            self._context = {
                "session_id": self._session_id,
                "decisions": [],
                "ephemeral_decisions": [],
                "turn_count": 0,
            }

        self._session_active = True

        # Register with session lifecycle if workspace available
        if ws:
            try:
                from ao_kernel.context.session_lifecycle import start_session as _start
                _start(workspace_root=ws, session_id=self._session_id, ttl_seconds=ttl_seconds)
            except Exception:
                pass

        return self._context

    def end_session(self, *, save: bool = True) -> None:
        """End the current session.

        Args:
            save: Persist context before closing (default True).
        """
        if not self._session_active:
            return

        ws = self._workspace_root
        if save and ws and self._context:
            try:
                from ao_kernel.session import save_context
                save_context(self._context, ws, session_id=self._session_id)
            except Exception:
                pass

            try:
                from ao_kernel.context.session_lifecycle import end_session as _end
                _end(self._context, workspace_root=ws)
            except Exception:
                pass

        self._session_active = False

    # ── LLM Calls ───────────────────────────────────────────────────

    def llm_call(
        self,
        messages: list[dict[str, Any]],
        *,
        intent: str = "general",
        provider_id: str | None = None,
        model: str | None = None,
        api_key: str = "",
        base_url: str = "",
        temperature: float | None = None,
        max_tokens: int | None = None,
        stream: bool = False,
        tools: list[dict[str, Any]] | None = None,
        tool_results: list[dict[str, Any]] | None = None,
        response_format: dict[str, Any] | None = None,
        profile: str | None = None,
    ) -> dict[str, Any]:
        """Make a governed LLM call with full pipeline.

        Pipeline: route → capabilities → context inject → build → execute →
                  normalize → extract decisions → update context → telemetry

        Args:
            messages: Chat messages [{"role": ..., "content": ...}].
            intent: Routing intent (e.g., "code_generation", "review").
            provider_id: Override provider (auto-routed if None).
            model: Override model (auto-routed if None).
            api_key: Provider API key.
            base_url: Provider base URL.
            temperature: Sampling temperature.
            max_tokens: Max response tokens.
            stream: Enable streaming.
            tools: Tool definitions for tool calling.
            tool_results: Previous tool call results for decision extraction.
            response_format: Structured output format.
            profile: Context profile override.

        Returns dict with: text, usage, tool_calls, provider_id, model,
                           request_id, decisions_extracted, eval_scorecard.

        Tool-use contract:
            When tools are provided and the model returns tool_calls, the caller
            is responsible for executing them via call_tool() and passing results
            back in a subsequent llm_call(). Automatic tool-use loops are NOT
            implemented — orchestration is manual by design.
        """
        request_id = f"req-{uuid.uuid4().hex[:12]}"

        # 1. Route (normalize: router returns selected_provider/selected_model)
        if not provider_id or not model:
            route = self._route(intent)
            provider_id = provider_id or route.get("provider_id", route.get("selected_provider", "openai"))
            model = model or route.get("model", route.get("selected_model", "gpt-4"))
            base_url = base_url or route.get("base_url", "")
            api_key = api_key or route.get("api_key", "")

        if not base_url:
            base_url = self._default_base_url(provider_id)

        # 2. Capability check
        from ao_kernel.llm import check_capabilities
        cap_ok, _, missing = check_capabilities(
            provider_id=provider_id,
            model=model,
            has_tools=bool(tools),
            has_response_format=bool(response_format),
        )
        if not cap_ok and missing:
            return {
                "status": "CAPABILITY_GAP",
                "text": "",
                "missing": missing,
                "provider_id": provider_id,
                "model": model,
                "request_id": request_id,
            }

        # 3. Build request (with context injection if session active)
        ws_str = str(self._workspace_root) if self._workspace_root else None
        if self._session_active and self._context:
            from ao_kernel.llm import build_request_with_context
            req = build_request_with_context(
                provider_id=provider_id,
                model=model,
                messages=messages,
                base_url=base_url,
                api_key=api_key,
                session_context=self._context,
                workspace_root=ws_str,
                profile=profile,
                temperature=temperature,
                max_tokens=max_tokens,
                request_id=request_id,
                stream=stream,
                tools=tools,
                response_format=response_format,
            )
        else:
            from ao_kernel.llm import build_request
            req = build_request(
                provider_id=provider_id,
                model=model,
                messages=messages,
                base_url=base_url,
                api_key=api_key,
                temperature=temperature,
                max_tokens=max_tokens,
                request_id=request_id,
                tools=tools,
                response_format=response_format,
                stream=stream,
            )

        # 4. Execute (streaming or blocking)
        if stream:
            return self._execute_stream(
                req=req,
                provider_id=provider_id,
                model=model,
                request_id=request_id,
                ws_str=ws_str,
                tool_results=tool_results,
            )

        from ao_kernel.llm import execute_request
        transport_result = execute_request(
            url=req["url"],
            headers=req["headers"],
            body_bytes=req["body_bytes"],
            timeout_seconds=30.0,
            provider_id=provider_id,
            request_id=request_id,
        )

        if transport_result.get("status") != "OK":
            return {
                "status": "TRANSPORT_ERROR",
                "text": "",
                "error_code": transport_result.get("error_code", "UNKNOWN"),
                "http_status": transport_result.get("http_status"),
                "provider_id": provider_id,
                "model": model,
                "request_id": request_id,
                "elapsed_ms": transport_result.get("elapsed_ms", 0),
            }

        # 5. Normalize response
        resp_bytes = transport_result.get("resp_bytes", b"")
        from ao_kernel.llm import normalize_response, extract_usage
        normalized = normalize_response(resp_bytes, provider_id=provider_id)
        usage = extract_usage(resp_bytes)

        text = normalized.get("text", "")
        tool_calls = normalized.get("tool_calls", [])

        # 5b. Evidence (non-streaming)
        if ws_str:
            try:
                from ao_kernel._internal.prj_kernel_api.llm_post_processors import process_live_response
                process_live_response(
                    resp_bytes=resp_bytes,
                    transport_result=transport_result,
                    provider_id=provider_id,
                    model=model or "",
                    workspace_root=ws_str,
                    request_id=request_id,
                    max_output_chars=2000,
                )
            except Exception:
                pass

        # 6. Context pipeline (decision extraction + memory)
        decisions_extracted = 0
        if self._session_active and self._context and text:
            from ao_kernel.llm import process_response_with_context
            self._context = process_response_with_context(
                text,
                self._context,
                provider_id=provider_id,
                request_id=request_id,
                workspace_root=ws_str,
                tool_results=tool_results,
            )
            decisions_extracted = len(
                self._context.get("ephemeral_decisions", self._context.get("decisions", []))
            )

        # 7. Eval scorecard
        scorecard = None
        try:
            from ao_kernel._internal.orchestrator.eval_harness import run_eval_suite, eval_scorecard
            eval_results = run_eval_suite(text)
            scorecard = eval_scorecard(eval_results)
        except Exception:
            pass

        # 8. Telemetry
        try:
            from ao_kernel.telemetry import record_llm_call_duration, record_token_usage
            record_llm_call_duration(
                transport_result.get("elapsed_ms", 0),
                provider=provider_id,
                model=model,
                status="OK",
            )
            if usage:
                record_token_usage(
                    provider=provider_id,
                    input_tokens=usage.get("input_tokens", 0),
                    output_tokens=usage.get("output_tokens", 0),
                )
        except Exception:
            pass

        return {
            "status": "OK",
            "text": text,
            "tool_calls": tool_calls,
            "usage": usage,
            "provider_id": provider_id,
            "model": model,
            "request_id": request_id,
            "elapsed_ms": transport_result.get("elapsed_ms", 0),
            "decisions_extracted": decisions_extracted,
            "eval_scorecard": scorecard,
        }

    def _execute_stream(
        self,
        *,
        req: dict[str, Any],
        provider_id: str,
        model: str,
        request_id: str,
        ws_str: str | None,
        tool_results: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """Execute streaming LLM call and return aggregate result.

        Uses ao_kernel.llm.stream_request() with OK/PARTIAL/FAIL contract.
        The on_chunk callback is NOT exposed — this is a sync aggregate API.
        For chunk-level streaming, use ao_kernel.llm.stream_request() directly.
        """
        from ao_kernel.llm import stream_request

        sr = stream_request(
            url=req["url"],
            headers=req["headers"],
            body_bytes=req["body_bytes"],
            timeout_seconds=30.0,
            provider_id=provider_id,
            request_id=request_id,
            capture_events=True,
        )

        # Map StreamResult status
        if sr.status == "FAIL":
            return {
                "status": "TRANSPORT_ERROR",
                "text": "",
                "stream": True,
                "error_code": sr.error_code or "STREAM_FAIL",
                "provider_id": provider_id,
                "model": model,
                "request_id": request_id,
                "elapsed_ms": sr.elapsed_ms,
            }

        text = sr.text
        usage = sr.usage
        status = sr.status  # OK or PARTIAL

        # Reconstruct tool calls from captured stream events
        tool_calls: list[dict[str, Any]] = []
        if sr.events:
            try:
                from ao_kernel._internal.prj_kernel_api.llm_stream_normalizer import reconstruct_tool_calls
                tool_calls = reconstruct_tool_calls(sr.events, provider_id)
            except Exception:
                pass

        # Evidence (stream events + summary)
        if ws_str:
            try:
                from ao_kernel._internal.prj_kernel_api.llm_post_processors import process_stream_response
                process_stream_response(
                    stream_result=sr,
                    provider_id=provider_id,
                    model=model or "",
                    workspace_root=ws_str,
                    request_id=request_id,
                )
            except Exception:
                pass

        # Context pipeline
        decisions_extracted = 0
        if self._session_active and self._context and text:
            from ao_kernel.llm import process_response_with_context
            self._context = process_response_with_context(
                text,
                self._context,
                provider_id=provider_id,
                request_id=request_id,
                workspace_root=ws_str,
                tool_results=tool_results,
            )
            decisions_extracted = len(
                self._context.get("ephemeral_decisions", self._context.get("decisions", []))
            )

        # Telemetry
        try:
            from ao_kernel.telemetry import record_llm_call_duration, record_token_usage, record_stream_first_token
            record_llm_call_duration(sr.elapsed_ms, provider=provider_id, model=model, status=status)
            if usage:
                record_token_usage(
                    provider=provider_id,
                    input_tokens=usage.get("input_tokens", 0),
                    output_tokens=usage.get("output_tokens", 0),
                )
            if sr.first_token_ms is not None:
                record_stream_first_token(sr.first_token_ms, provider=provider_id)
        except Exception:
            pass

        return {
            "status": status,
            "text": text,
            "tool_calls": tool_calls,
            "usage": usage,
            "stream": True,
            "complete": sr.complete,
            "first_token_ms": sr.first_token_ms,
            "chunk_count": sr.chunk_count,
            "provider_id": provider_id,
            "model": model,
            "request_id": request_id,
            "elapsed_ms": sr.elapsed_ms,
            "decisions_extracted": decisions_extracted,
        }

    def _route(self, intent: str) -> dict[str, Any]:
        """Resolve provider/model for intent."""
        try:
            from ao_kernel.llm import resolve_route
            return resolve_route(
                intent=intent,
                provider_priority=self._provider_priority,
                workspace_root=str(self._workspace_root) if self._workspace_root else None,
            )
        except Exception:
            return {"provider_id": "openai", "model": "gpt-4", "base_url": ""}

    @staticmethod
    def _default_base_url(provider_id: str) -> str:
        defaults = {
            "openai": "https://api.openai.com/v1",
            "claude": "https://api.anthropic.com/v1",
            "google": "https://generativelanguage.googleapis.com/v1beta",
            "deepseek": "https://api.deepseek.com/v1",
            "qwen": "https://dashscope.aliyuncs.com/api/v1",
            "xai": "https://api.x.ai/v1",
        }
        return defaults.get(provider_id, "")

    # ── Tool Dispatch ───────────────────────────────────────────────

    def register_tool(
        self,
        name: str,
        handler: Any,
        *,
        description: str = "",
        input_schema: dict[str, Any] | None = None,
    ) -> None:
        """Register a tool for policy-gated dispatch.

        Args:
            name: Tool name.
            handler: Callable(dict) → dict.
            description: Human-readable description.
            input_schema: JSON Schema for tool input.
        """
        from ao_kernel.tool_gateway import ToolGateway, ToolSpec

        if not hasattr(self, "_gateway"):
            self._gateway = ToolGateway()

        self._gateway.register(ToolSpec(
            name=name,
            handler=handler,
            description=description,
            input_schema=input_schema or {},
        ))

    def call_tool(
        self,
        name: str,
        arguments: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Dispatch a tool call through ToolGateway.

        Policy-gated, fail-closed. Unknown/unauthorized tools are rejected.

        Returns dict with: status, result, tool_name, evidence.
        """
        if not hasattr(self, "_gateway"):
            return {
                "status": "REJECT",
                "tool_name": name,
                "reason": "NO_GATEWAY",
                "result": None,
            }

        from dataclasses import asdict
        result = self._gateway.dispatch(name, arguments or {})
        return asdict(result)

    # ── Checkpoint/Resume ───────────────────────────────────────────

    def save_checkpoint(self, session_id: str | None = None) -> dict[str, Any]:
        """Save current session as a checkpoint.

        Returns a dict with saved=True and path, or saved=False with error code.
        """
        if not self._session_active or not self._context:
            return {"saved": False, "error": "NO_ACTIVE_SESSION"}
        if not self._workspace_root:
            return {"saved": False, "error": "NO_WORKSPACE"}

        from ao_kernel.context.checkpoint import save_checkpoint
        path = save_checkpoint(
            self._context,
            workspace_root=self._workspace_root,
            session_id=session_id,
        )
        return {"saved": True, "path": path}

    def resume_checkpoint(self, session_id: str) -> dict[str, Any]:
        """Resume session from a checkpoint by session_id.

        Returns a dict with resumed=True and session_id, or resumed=False with error code.
        """
        if not self._workspace_root:
            return {"resumed": False, "error": "NO_WORKSPACE"}

        from ao_kernel.context.checkpoint import resume_checkpoint
        self._context = resume_checkpoint(
            workspace_root=self._workspace_root,
            session_id=session_id,
        )
        self._session_active = True
        self._session_id = self._context.get("session_id", self._session_id)
        return {"resumed": True, "session_id": self._session_id}

    # ── Self-editing Memory ─────────────────────────────────────────

    def remember(
        self,
        key: str,
        value: Any,
        *,
        importance: str = "normal",
    ) -> dict[str, Any]:
        """Store a memory with importance-based retention."""
        if not self._workspace_root:
            return {"stored": False, "error": "NO_WORKSPACE"}

        from ao_kernel.context.self_edit_memory import remember as _remember
        return _remember(
            self._workspace_root,
            key=key,
            value=value,
            importance=importance,
            session_id=self._session_id,
        )

    def forget(self, key: str) -> dict[str, Any]:
        """Soft-expire a memory (audit trail preserved)."""
        if not self._workspace_root:
            return {"forgotten": False, "error": "NO_WORKSPACE"}

        from ao_kernel.context.self_edit_memory import forget as _forget
        return _forget(self._workspace_root, key=key)

    def recall(self, pattern: str = "*") -> list[dict[str, Any]]:
        """Query self-stored memories. Pattern auto-prefixed with 'memory.'."""
        if not self._workspace_root:
            return []

        from ao_kernel.context.self_edit_memory import recall as _recall
        return _recall(self._workspace_root, key_pattern=pattern)

    # ── Policy ──────────────────────────────────────────────────────

    def check_policy(
        self,
        policy_name: str,
        action: dict[str, Any],
    ) -> dict[str, Any]:
        """Check an action against a named policy. Fail-closed."""
        from ao_kernel.policy import check
        ws = self._workspace_root if self._workspace_root and (self._workspace_root / ".ao").is_dir() else None
        return check(policy_name, action, workspace=ws)

    # ── Context Manager ─────────────────────────────────────────────

    def __enter__(self) -> AoKernelClient:
        """Start session on context manager entry."""
        self.start_session()
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """End session on context manager exit."""
        self.end_session(save=exc_type is None)

    # ── Repr ────────────────────────────────────────────────────────

    def __repr__(self) -> str:
        ws = self._workspace_root or "library-mode"
        status = "active" if self._session_active else "inactive"
        return f"AoKernelClient(workspace={ws}, session={self._session_id}, {status})"


__all__ = ["AoKernelClient"]
