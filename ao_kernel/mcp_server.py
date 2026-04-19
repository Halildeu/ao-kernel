"""ao-kernel MCP server — governed runtime as Model Context Protocol service.

Exposes ao-kernel governance primitives as MCP tools and workspace content
as MCP resources. Transport-agnostic handler design (stdio first, HTTP later).

Tools (7):
    ao_policy_check    — validate an action against policy
    ao_llm_route       — resolve provider/model for an intent
    ao_llm_call        — governed LLM call — thin executor (route, build, execute, normalize)
    ao_quality_gate    — check output quality
    ao_workspace_status — workspace health report
    ao_memory_read     — read canonical decisions + workspace facts (policy-gated, fail-closed)
    ao_memory_write    — promote a decision to the canonical store (policy-gated, fail-closed, server-side fixed confidence)

Resources (3):
    ao://policies/{name}  — read-only policy JSON
    ao://schemas/{name}   — read-only schema JSON
    ao://registry/{name}  — read-only registry JSON

Design decisions (Codex CNS-20260413-004): fail-closed policy
violations (structured deny, not JSON-RPC error); automatic evidence
side-effect; uniform decision envelope; no global state (workspace_root
passed explicitly per call).
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_API_VERSION = "0.1.0"


def _find_workspace_root() -> Path | None:
    """Return the project root (directory that CONTAINS ``.ao/``).

    Thin shim over :func:`ao_kernel.workspace.project_root`. Per
    CNS-20260414-010 consensus the project-root semantic is the single
    source of truth across MCP, evidence, and tool-gateway code paths;
    the helper centralizes the ``.ao`` -> parent normalization that used
    to be sprinkled across this module.
    """
    from ao_kernel.workspace import project_root

    return project_root()


# ── Decision Envelope ───────────────────────────────────────────────


def _decision_envelope(
    *,
    tool: str,
    allowed: bool,
    decision: str,
    reason_codes: list[str] | None = None,
    policy_ref: str | None = None,
    data: dict[str, Any] | None = None,
    error: str | None = None,
) -> dict[str, Any]:
    """Standard response envelope for all MCP tools."""
    return {
        "api_version": _API_VERSION,
        "tool": tool,
        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "allowed": allowed,
        "decision": decision,
        "reason_codes": reason_codes or [],
        "policy_ref": policy_ref,
        "data": data,
        "error": error,
    }


# ── Tool Handlers ───────────────────────────────────────────────────


def handle_policy_check(params: dict[str, Any]) -> dict[str, Any]:
    """Check an action against a named policy.

    Delegates to governance.check_policy() which handles all policy types:
    autonomy, tool_calling, provider_guardrails, and generic rules.

    Params:
        policy_name: str — policy file name (e.g., "policy_autonomy.v1.json")
        action: dict — the action to validate
        workspace_root: str | None — explicit workspace path
    """
    policy_name = params.get("policy_name", "")
    action = params.get("action", {})
    workspace_root = params.get("workspace_root")

    if not policy_name:
        return _decision_envelope(
            tool="ao_policy_check",
            allowed=False,
            decision="deny",
            reason_codes=["MISSING_POLICY_NAME"],
            error="policy_name parameter is required",
        )

    try:
        from ao_kernel.governance import check_policy
        from pathlib import Path

        ws = Path(workspace_root) if workspace_root else None
        result = check_policy(policy_name, action, workspace=ws)
    except Exception as e:
        return _decision_envelope(
            tool="ao_policy_check",
            allowed=False,
            decision="deny",
            reason_codes=["POLICY_CHECK_ERROR"],
            policy_ref=policy_name,
            error=str(e)[:200],
        )

    return _decision_envelope(
        tool="ao_policy_check",
        allowed=result.get("allowed", False),
        decision=result.get("decision", "deny"),
        reason_codes=result.get("reason_codes", []),
        policy_ref=result.get("policy_ref", policy_name),
        data=result.get("data"),
    )


def handle_llm_route(params: dict[str, Any]) -> dict[str, Any]:
    """Resolve provider/model for an intent.

    Params:
        intent: str — the LLM intent class
        perspective: str | None — optional perspective
        provider_priority: list[str] | None
        workspace_root: str | None
    """
    intent = params.get("intent", "")
    if not intent:
        return _decision_envelope(
            tool="ao_llm_route",
            allowed=False,
            decision="deny",
            reason_codes=["MISSING_INTENT"],
            error="intent parameter is required",
        )

    try:
        from ao_kernel.llm import resolve_route

        result = resolve_route(
            intent=intent,
            perspective=params.get("perspective"),
            provider_priority=params.get("provider_priority"),
            workspace_root=params.get("workspace_root"),
        )

        status = result.get("status", "FAIL")
        return _decision_envelope(
            tool="ao_llm_route",
            allowed=status == "OK",
            decision="allow" if status == "OK" else "deny",
            reason_codes=[result.get("reason", status)],
            data=result,
        )
    except Exception as e:
        return _decision_envelope(
            tool="ao_llm_route",
            allowed=False,
            decision="deny",
            reason_codes=["ROUTER_ERROR"],
            error=str(e)[:200],
        )


def handle_quality_gate(params: dict[str, Any]) -> dict[str, Any]:
    """Check output quality against quality gate policy.

    Params:
        output_text: str — the LLM output to evaluate
        workspace_root: str | None
        previous_decisions: list[dict] | None — for consistency/regression checks
            (auto-loaded from canonical store if omitted and workspace available)

    Fail-closed: if quality gate can't run, returns DENY (never silent allow).
    """
    output_text = params.get("output_text", "")
    if not output_text:
        return _decision_envelope(
            tool="ao_quality_gate",
            allowed=False,
            decision="deny",
            reason_codes=["EMPTY_OUTPUT"],
            error="output_text parameter is required",
        )

    from ao_kernel.governance import evaluate_quality, quality_summary
    from pathlib import Path

    ws = Path(params["workspace_root"]) if params.get("workspace_root") else None

    # Load previous decisions for consistency/regression checks
    previous_decisions = params.get("previous_decisions")
    if previous_decisions is None and ws:
        try:
            from ao_kernel.context.canonical_store import query as query_canonical

            previous_decisions = query_canonical(ws)
        except Exception:
            previous_decisions = None

    results = evaluate_quality(
        output_text,
        workspace_root=ws,
        previous_decisions=previous_decisions,
    )
    summary = quality_summary(results)

    return _decision_envelope(
        tool="ao_quality_gate",
        allowed=summary["all_passed"],
        decision="allow" if summary["all_passed"] else "deny",
        reason_codes=[g["gate_id"] for g in summary["gates"] if not g["passed"]],
        data=summary,
    )


def handle_workspace_status(params: dict[str, Any]) -> dict[str, Any]:
    """Get workspace health status.

    Params:
        workspace_root: str | None
    """
    try:
        from ao_kernel.config import workspace_root as resolve_ws, load_workspace_json
        from pathlib import Path

        ws_override = params.get("workspace_root")
        ws = Path(ws_override) if ws_override else resolve_ws()

        if ws is None:
            return _decision_envelope(
                tool="ao_workspace_status",
                allowed=True,
                decision="allow",
                reason_codes=["NO_WORKSPACE"],
                data={"mode": "library", "workspace": None},
            )

        try:
            ws_data = load_workspace_json(ws)
            status = "healthy"
        except Exception:
            ws_data = {}
            status = "corrupted"

        return _decision_envelope(
            tool="ao_workspace_status",
            allowed=True,
            decision="allow",
            reason_codes=[status.upper()],
            data={
                "mode": "workspace",
                "workspace": str(ws),
                "status": status,
                "version": ws_data.get("version"),
                "kind": ws_data.get("kind"),
            },
        )
    except Exception as e:
        return _decision_envelope(
            tool="ao_workspace_status",
            allowed=False,
            decision="deny",
            reason_codes=["STATUS_ERROR"],
            error=str(e)[:200],
        )


# ── Resource Handlers ───────────────────────────────────────────────


def handle_resource(uri: str) -> dict[str, Any] | None:
    """Load a resource by ao:// URI.

    Supported:
        ao://policies/{name}
        ao://schemas/{name}
        ao://registry/{name}
    """
    if not uri.startswith("ao://"):
        return None

    path = uri[5:]  # Remove "ao://"
    parts = path.split("/", 1)
    if len(parts) != 2:
        return None

    resource_type, name = parts
    if resource_type not in ("policies", "schemas", "registry"):
        return None

    try:
        from ao_kernel.config import load_default

        return load_default(resource_type, name)
    except Exception:
        return None


def handle_llm_call(params: dict[str, Any]) -> dict[str, Any]:
    """Execute a governed LLM call — thin executor (route, build, execute, normalize).

    NOTE: This is NOT the full AoKernelClient pipeline. Context injection, eval
    harness, quality gates, and telemetry are NOT included. For the full governed
    pipeline, use AoKernelClient.llm_call() instead.

    Params:
        messages: list[dict] — chat messages (required)
        intent: str — routing intent (default: "general")
        provider_id: str | None — override provider
        model: str | None — override model
        temperature: float | None
        max_tokens: int | None
        workspace_root: str | None

    API keys are resolved from environment variables or workspace secrets.
    They are NEVER accepted as MCP parameters (security boundary).
    """
    messages = params.get("messages")
    if not messages or not isinstance(messages, list):
        return _decision_envelope(
            tool="ao_llm_call",
            allowed=False,
            decision="deny",
            reason_codes=["MISSING_MESSAGES"],
            error="messages parameter is required and must be a list",
        )

    intent = params.get("intent", "general")
    provider_id = params.get("provider_id")
    model = params.get("model")
    temperature = params.get("temperature")
    max_tokens = params.get("max_tokens")
    ws = params.get("workspace_root")
    # PR-B2 v5 iter-4 absorb: optional cost identity params. When all
    # three present AND workspace_root points at a workspace with cost
    # policy.enabled=true, the call runs through the cost pipeline.
    ao_run_id = params.get("ao_run_id")
    ao_step_id = params.get("ao_step_id")
    ao_attempt = params.get("ao_attempt")

    # Route if provider/model not specified
    if not provider_id or not model:
        from ao_kernel.llm import resolve_route

        # PR-C4.1: opportunistic budget snapshot load for budget-aware
        # cross-class downgrade. Fail-silently (warn-log) — cost-route
        # is an optional path, not on the MCP thin-executor happy path.
        budget_snap = None
        if ao_run_id is not None and ws is not None:
            try:
                from pathlib import Path as _Path
                from ao_kernel.workflow.budget import budget_from_dict
                from ao_kernel.workflow.run_store import load_run

                record, _ = load_run(_Path(ws), ao_run_id)
                budget_dict = record.get("budget")
                if budget_dict:
                    budget_snap = budget_from_dict(budget_dict)
            except Exception as exc:
                import logging as _logging

                _logging.getLogger(__name__).warning(
                    "C4.1 MCP budget snapshot load failed (run=%s): %s; no-downgrade fallback",
                    ao_run_id,
                    exc,
                )

        # PR-C4.1: auto-route wrapped in try so router-side config
        # errors (malformed resolver rules, missing class registry,
        # etc) surface through the MCP decision envelope instead of
        # bubbling as a raw exception — parity with handle_llm_route.
        try:
            route = resolve_route(
                intent=intent,
                workspace_root=ws,
                cross_class_downgrade=budget_snap is not None,
                budget_remaining=budget_snap,
            )
        except Exception as exc:
            return _decision_envelope(
                tool="ao_llm_call",
                allowed=False,
                decision="error",
                reason_codes=["ROUTE_ERROR"],
                error=f"resolve_route failed: {exc}",
            )
        provider_id = provider_id or route.get("provider_id", route.get("selected_provider", "openai"))
        model = model or route.get("model", route.get("selected_model", "gpt-4"))

        # PR-C4.1: evidence emit on budget-triggered downgrade.
        # Fail-open wrap — evidence I/O issue must not cascade.
        if route.get("downgrade_applied") and ws is not None and ao_run_id is not None:
            try:
                import datetime as _dt
                from pathlib import Path as _Path

                from ao_kernel.executor.evidence_emitter import emit_event

                emit_event(
                    _Path(ws),
                    run_id=ao_run_id,
                    kind="route_cross_class_downgrade",
                    actor="ao-kernel",
                    payload={
                        "intent": intent,
                        "original_class": route.get("original_class"),
                        "downgraded_class": route.get("downgraded_class"),
                        "selected_class": route.get("selected_class"),
                        "matched_rule_index": route.get("matched_rule_index"),
                        "threshold_usd": route.get("threshold_usd"),
                        "budget_remaining_usd": route.get(
                            "budget_remaining_usd",
                        ),
                        "provider_id": provider_id,
                        "model": model,
                        "ts": _dt.datetime.now(
                            _dt.timezone.utc,
                        ).isoformat(),
                    },
                )
            except Exception as exc:
                import logging as _logging

                _logging.getLogger(__name__).warning(
                    "route_cross_class_downgrade emit failed (fail-open): %s",
                    exc,
                )

    # Resolve API key via dual-read (factory > env fallback, D11/D0.3).
    # Never accept api_key as a tool parameter — it stays an env/secret concern.
    from ao_kernel._internal.secrets.api_key_resolver import (
        env_names_for,
        resolve_api_key,
    )

    api_key = resolve_api_key(provider_id)
    if not api_key:
        env_candidates = env_names_for(provider_id)
        env_hint = " or ".join(env_candidates)
        return _decision_envelope(
            tool="ao_llm_call",
            allowed=False,
            decision="deny",
            reason_codes=["MISSING_API_KEY"],
            error=f"API key not found (checked: {env_hint}).",
        )

    # Build + execute
    import uuid

    request_id = f"mcp-{uuid.uuid4().hex[:12]}"

    try:
        from pathlib import Path
        from ao_kernel.llm import governed_call

        base_url_map = {
            "openai": "https://api.openai.com/v1",
            "claude": "https://api.anthropic.com/v1",
            "google": "https://generativelanguage.googleapis.com/v1beta",
            "deepseek": "https://api.deepseek.com/v1",
            "qwen": "https://dashscope.aliyuncs.com/api/v1",
            "xai": "https://api.x.ai/v1",
        }

        # PR-B2 v5 iter-4 B1 absorb: route through governed_call so cost
        # hooks and context injection compose uniformly. MCP stays a
        # "thin executor" — no session context passed (MCP callers do not
        # maintain ao-kernel session state); cost opt-in via ao_* params.
        ws_path: Path | None = Path(ws) if ws else None
        result = governed_call(
            messages=messages,
            provider_id=provider_id,
            model=model,
            api_key=api_key,
            base_url=base_url_map.get(provider_id, ""),
            request_id=request_id,
            temperature=temperature,
            max_tokens=max_tokens,
            # Context injection NOT applicable in the MCP thin-executor
            # surface (MCP callers manage their own context out-of-band).
            session_context=None,
            workspace_root_str=str(ws_path) if ws_path else None,
            profile=None,
            embedding_config=None,
            vector_store=None,
            # Cost identity kwargs (v5 iter-4 B2 absorb). All four
            # (ws + run_id + step_id + attempt) required for cost-active;
            # any missing → transparent bypass.
            workspace_root=ws_path,
            run_id=ao_run_id,
            step_id=ao_step_id,
            attempt=ao_attempt,
        )

        # Envelope pass-through for error statuses — preserves mcp_server
        # pre-B2 decision envelope contract.
        status = result.get("status")
        if status == "CAPABILITY_GAP":
            return _decision_envelope(
                tool="ao_llm_call",
                allowed=False,
                decision="deny",
                reason_codes=["CAPABILITY_GAP"],
                data={
                    "missing": result.get("missing", []),
                    "provider_id": provider_id,
                    "model": model,
                    "request_id": request_id,
                },
            )
        if status == "TRANSPORT_ERROR":
            return _decision_envelope(
                tool="ao_llm_call",
                allowed=True,
                decision="error",
                reason_codes=["TRANSPORT_ERROR"],
                data={
                    "error_code": result.get("error_code", "UNKNOWN"),
                    "http_status": result.get("http_status"),
                    "elapsed_ms": result.get("elapsed_ms", 0),
                    "request_id": request_id,
                },
            )

        # Status == "OK" — unwrap rich dict and build executed envelope.
        normalized = result.get("normalized") or {}
        return _decision_envelope(
            tool="ao_llm_call",
            allowed=True,
            decision="executed",
            data={
                "text": normalized.get("text", ""),
                "tool_calls": normalized.get("tool_calls", []),
                "provider_id": provider_id,
                "model": model,
                "request_id": request_id,
                "elapsed_ms": result.get("elapsed_ms", 0),
                "api_key_present": True,
            },
        )
    except Exception as exc:
        return _decision_envelope(
            tool="ao_llm_call",
            allowed=True,
            decision="error",
            reason_codes=["EXECUTION_ERROR"],
            error=str(exc)[:200],
            data={"request_id": request_id},
        )


# ── MCP Server (requires `mcp` package) ────────────────────────────


TOOL_DEFINITIONS: list[dict[str, Any]] = [
    {
        "name": "ao_policy_check",
        "description": "Validate an action against an ao-kernel policy. Returns allow/deny decision.",
        "inputSchema": {
            "type": "object",
            "required": ["policy_name", "action"],
            "properties": {
                "policy_name": {"type": "string", "description": "Policy file name"},
                "action": {"type": "object", "description": "Action to validate"},
                "workspace_root": {"type": "string", "description": "Workspace path (optional)"},
            },
        },
    },
    {
        "name": "ao_llm_route",
        "description": "Resolve the best provider/model for an LLM intent. Deterministic routing.",
        "inputSchema": {
            "type": "object",
            "required": ["intent"],
            "properties": {
                "intent": {"type": "string", "description": "LLM intent class"},
                "perspective": {"type": "string", "description": "Optional perspective"},
                "provider_priority": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Provider priority order",
                },
                "workspace_root": {"type": "string"},
            },
        },
    },
    {
        "name": "ao_llm_call",
        "description": "Execute a governed LLM call — thin executor (route, build, execute, normalize). No context injection, eval, or quality gate. API keys from env vars.",
        "inputSchema": {
            "type": "object",
            "required": ["messages"],
            "properties": {
                "messages": {
                    "type": "array",
                    "items": {"type": "object"},
                    "description": "Chat messages [{role, content}]",
                },
                "intent": {"type": "string", "description": "Routing intent (default: general)"},
                "provider_id": {"type": "string", "description": "Override provider"},
                "model": {"type": "string", "description": "Override model"},
                "temperature": {"type": "number"},
                "max_tokens": {"type": "integer"},
                "workspace_root": {"type": "string"},
                "ao_run_id": {
                    "type": "string",
                    "description": "PR-B2 cost identity: workflow run UUIDv4. Optional; required together with ao_step_id and ao_attempt to activate cost tracking (policy.enabled must also be true on the workspace).",
                },
                "ao_step_id": {
                    "type": "string",
                    "description": "PR-B2 cost identity: step id within the run. Optional; see ao_run_id.",
                },
                "ao_attempt": {
                    "type": "integer",
                    "minimum": 1,
                    "description": "PR-B2 cost identity: retry attempt number (≥1). Forms the ledger idempotency key with (ao_run_id, ao_step_id). Optional.",
                },
            },
        },
    },
    {
        "name": "ao_quality_gate",
        "description": "Check LLM output quality against configured gates. Fail-closed.",
        "inputSchema": {
            "type": "object",
            "required": ["output_text"],
            "properties": {
                "output_text": {"type": "string", "description": "LLM output to evaluate"},
                "gate_id": {"type": "string", "description": "Specific gate (default: all)"},
                "workspace_root": {"type": "string"},
                "previous_decisions": {
                    "type": "array",
                    "items": {"type": "object"},
                    "description": "Previous decisions for consistency/regression checks (auto-loaded from workspace if omitted)",
                },
            },
        },
    },
    {
        "name": "ao_workspace_status",
        "description": "Get ao-kernel workspace health status and configuration.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "workspace_root": {"type": "string"},
            },
        },
    },
    {
        "name": "ao_memory_read",
        "description": "Read canonical decisions and workspace facts. Policy-gated, fail-closed, read-only. v3.6 E3: supports `max_results` (default 50, hard cap 200) + `offset` pagination; response `data` adds `total` + `next_offset` alongside existing `items` + `count`.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "workspace_root": {"type": "string", "description": "Project root containing .ao/ (optional override)"},
                "pattern": {"type": "string", "description": "Glob pattern for key match (fnmatch)", "default": "*"},
                "category": {"type": "string", "description": "Optional category filter"},
                "max_results": {
                    "type": "integer",
                    "description": "Maximum entries to return in this page (default 50, hard capped at 200).",
                    "default": 50,
                    "minimum": 1,
                    "maximum": 200,
                },
                "offset": {
                    "type": "integer",
                    "description": "Pagination cursor (0-based offset into the post-policy filtered result set).",
                    "default": 0,
                    "minimum": 0,
                },
            },
            "additionalProperties": False,
        },
    },
    {
        "name": "ao_memory_write",
        "description": "Promote a decision to canonical memory. Policy-gated, fail-closed, rate-limited; server-side fixed confidence (caller-supplied confidence ignored).",
        "inputSchema": {
            "type": "object",
            "required": ["key", "value"],
            "properties": {
                "workspace_root": {"type": "string", "description": "Project root containing .ao/ (optional override)"},
                "key": {
                    "type": "string",
                    "description": "Canonical decision key (must match one of allowed_key_prefixes)",
                },
                "value": {"description": "Decision value (any JSON-serializable type; subject to max_value_bytes)"},
                "source": {
                    "type": "string",
                    "description": "Source tag (must start with an allowed_source_prefix)",
                    "default": "mcp:tool_write",
                },
            },
            "additionalProperties": False,
        },
    },
]


def _with_evidence(tool_name: str, handler: Any) -> Any:
    """Wrap a raw handler so every dispatched call records a JSONL event.

    Direct handler imports (tests, SDK smoke code) bypass the wrapper and
    therefore stay silent — evidence is only emitted when a tool is invoked
    through TOOL_DISPATCH or the ToolGateway, i.e. on the real MCP path.
    Evidence write failures never propagate (fail-open, §2 invariant #2).
    """
    import functools
    import time

    @functools.wraps(handler)
    def wrapped(params: dict[str, Any]) -> dict[str, Any]:
        start = time.monotonic()
        envelope: dict[str, Any] = handler(params)
        duration_ms = int((time.monotonic() - start) * 1000)
        try:
            from ao_kernel._internal.evidence.mcp_event_log import record_mcp_event
            from ao_kernel._internal.mcp.memory_tools import _resolve_workspace_for_call

            # Param-aware resolution roots evidence in the same workspace
            # the handler targeted (CNS-011 B1).
            ws = _resolve_workspace_for_call(params, fallback=_find_workspace_root)
            record_mcp_event(
                ws,
                tool_name,
                envelope,
                params=params if isinstance(params, dict) else None,
                duration_ms=duration_ms,
            )
        except Exception:  # noqa: BLE001 — evidence is side-channel
            pass
        return envelope

    return wrapped


def _lazy_memory_handler(fn_name: str) -> Any:
    """Factory: defers importing memory_tools until first call."""

    def proxy(params: dict[str, Any]) -> dict[str, Any]:
        from ao_kernel._internal.mcp import memory_tools

        return getattr(memory_tools, fn_name)(params)  # type: ignore[no-any-return]

    proxy.__name__ = fn_name
    return proxy


TOOL_DISPATCH = {
    "ao_policy_check": _with_evidence("ao_policy_check", handle_policy_check),
    "ao_llm_route": _with_evidence("ao_llm_route", handle_llm_route),
    "ao_llm_call": _with_evidence("ao_llm_call", handle_llm_call),
    "ao_quality_gate": _with_evidence("ao_quality_gate", handle_quality_gate),
    "ao_workspace_status": _with_evidence("ao_workspace_status", handle_workspace_status),
    "ao_memory_read": _with_evidence("ao_memory_read", _lazy_memory_handler("handle_memory_read")),
    "ao_memory_write": _with_evidence("ao_memory_write", _lazy_memory_handler("handle_memory_write")),
}


def create_tool_gateway() -> Any:
    """Create a ToolGateway pre-configured with MCP tools.

    Returns a policy-gated gateway where all 7 tools are registered.
    Tool calls go through: authorize → handler → result.
    """
    from ao_kernel.tool_gateway import ToolGateway, ToolCallPolicy

    # Load policy from bundled defaults via from_dict()
    # MCP governance tools are ALWAYS enabled (they ARE the governance layer)
    #
    # v3.9 B1: narrow the fallback scope — only policy LOAD/READ failures
    # fall back to a safe default policy. ValueError from from_dict() is a
    # real contract violation (invalid absorbed field) and MUST surface so
    # the operator notices; silent fallback here would defeat the whole
    # point of the B1 absorb.
    try:
        from ao_kernel.config import load_default

        tool_policy = load_default("policies", "policy_tool_calling.v1.json")
    except Exception:
        # Bundled policy missing / unreadable — safe runtime default.
        tool_policy = None

    if tool_policy is None:
        policy = ToolCallPolicy(enabled=True, max_rounds=10)
    else:
        # from_dict() ValueError intentionally propagates — invalid policy
        # is a fail-closed contract issue, not a "swallow and continue" case.
        policy = ToolCallPolicy.from_dict(tool_policy)
        policy.enabled = True  # MCP governance tools always enabled (override)

    gateway = ToolGateway(policy=policy)

    # v3.9 B2: ao_memory_write is the only governance tool that mutates
    # workspace state (canonical store). Flag it so the permission gate
    # enforces the mutating-confirm contract when a policy tightens
    # default_permission + mutating_requires_confirmation.
    _MUTATING_TOOLS = {"ao_memory_write"}

    for td in TOOL_DEFINITIONS:
        handler = TOOL_DISPATCH.get(td["name"])
        if handler:
            gateway.register_handler(
                name=td["name"],
                handler=handler,
                description=td["description"],
                input_schema=td["inputSchema"],
                is_mutating=td["name"] in _MUTATING_TOOLS,
            )

    return gateway


def create_mcp_server() -> Any:  # pragma: no cover — requires mcp package
    """Create and configure the MCP server instance.

    Requires `mcp` package: pip install ao-kernel[mcp]
    """
    try:
        from mcp.server import Server
        from mcp.types import Resource, TextContent, Tool
    except ImportError:
        raise ImportError("MCP server requires the 'mcp' package. Install with: pip install ao-kernel[mcp]")

    server = Server("ao-kernel")

    @server.list_tools()  # type: ignore[no-untyped-call,untyped-decorator]
    async def list_tools() -> list[Any]:
        return [
            Tool(
                name=td["name"],
                description=td["description"],
                inputSchema=td["inputSchema"],
            )
            for td in TOOL_DEFINITIONS
        ]

    @server.call_tool()  # type: ignore[untyped-decorator]
    async def call_tool(name: str, arguments: dict[str, Any]) -> list[Any]:
        import time as _time
        from ao_kernel.telemetry import span as otel_span, record_mcp_tool_call, record_policy_check

        # Use ToolGateway for policy-gated dispatch (not raw TOOL_DISPATCH)
        gateway = create_tool_gateway()
        start = _time.monotonic()

        with otel_span("ao.mcp_tool_call", {"ao.mcp.tool": name}) as s:
            gw_result = gateway.dispatch(name, arguments or {})
            elapsed = (_time.monotonic() - start) * 1000.0

            if gw_result.status == "DENIED":
                # v3.9 B2: prefer the machine-readable reason_code over
                # the free-form reason string. Fall back to reason when
                # reason_code is empty (e.g. from callers built against
                # pre-B2 ToolCallResult shape).
                reason_code = gw_result.reason_code or gw_result.reason
                deny_envelope = _decision_envelope(
                    tool=name,
                    allowed=False,
                    decision="deny",
                    reason_codes=[reason_code],
                    error=f"ToolGateway denied: {reason_code}",
                )
                s.set_attribute("ao.decision", "deny")
                s.set_attribute("ao.policy.reason_code", reason_code)
                record_mcp_tool_call(elapsed, tool=name, decision="deny")
                # v3.9 B2: audit every denial through the existing MCP
                # event log (workspace mode). Library mode is no-op.
                # Use the same param-aware resolver as the success path
                # (_with_evidence wrapper) to avoid `.ao/.ao/evidence/...`
                # nesting when `config.workspace_root()` already points
                # at `.ao/` instead of the project root.
                try:
                    from ao_kernel._internal.evidence.mcp_event_log import (
                        record_mcp_event as _rec_mcp,
                    )
                    from ao_kernel._internal.mcp.memory_tools import (
                        _resolve_workspace_for_call,
                    )

                    _ws = _resolve_workspace_for_call(arguments or {}, fallback=_find_workspace_root)
                    _rec_mcp(
                        _ws,
                        name,
                        deny_envelope,
                        params=arguments or {},
                        duration_ms=int(elapsed),
                        extra={"policy_denied": True, "reason_code": reason_code},
                    )
                except Exception:
                    # Audit is fail-open side-channel; never block the
                    # governance path on a write failure.
                    pass
                return [TextContent(type="text", text=json.dumps(deny_envelope, ensure_ascii=False))]

            result = gw_result.output or {"error": gw_result.reason}
            decision = result.get("decision", "unknown")
            s.set_attribute("ao.decision", decision)
            s.set_attribute("ao.allowed", result.get("allowed", False))
            record_mcp_tool_call(elapsed, tool=name, decision=decision)

            if name == "ao_policy_check":
                record_policy_check(
                    policy=result.get("policy_ref", "unknown"),
                    decision=decision,
                )

            # Wire tool result into context pipeline via the
            # implicit-promotion side-channel. Helper encapsulates
            # param-aware workspace, skip list, workspace-aware policy
            # threshold, and fail-open semantics
            # (CNS-20260414-012 B1).
            try:
                from ao_kernel._internal.mcp.memory_tools import (
                    _resolve_workspace_for_call,
                    run_implicit_promote,
                )

                ws_root = _resolve_workspace_for_call(
                    arguments or {},
                    fallback=_find_workspace_root,
                )
                run_implicit_promote(name, result, ws_root)
            except Exception:
                pass  # Context wiring failure shouldn't block tool response

        return [TextContent(type="text", text=json.dumps(result, ensure_ascii=False))]

    @server.list_resources()  # type: ignore[no-untyped-call,untyped-decorator]
    async def list_resources() -> list[Any]:
        resources = []
        for rtype in ("policies", "schemas", "registry"):
            resources.append(
                Resource(
                    uri=f"ao://{rtype}/",  # type: ignore[arg-type]
                    name=f"ao-kernel {rtype}",
                    description=f"Bundled {rtype} JSON files",
                    mimeType="application/json",
                )
            )
        return resources

    @server.read_resource()  # type: ignore[no-untyped-call,untyped-decorator]
    async def read_resource(uri: str) -> str:
        data = handle_resource(str(uri))
        if data is None:
            raise ValueError(f"Resource not found: {uri}")
        return json.dumps(data, indent=2, ensure_ascii=False)

    return server


async def serve_stdio() -> None:  # pragma: no cover — requires mcp package
    """Run MCP server over stdio transport."""
    try:
        from mcp.server.stdio import stdio_server
    except ImportError:
        raise ImportError("MCP server requires the 'mcp' package. Install with: pip install ao-kernel[mcp]")

    server = create_mcp_server()
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


async def serve_http(  # pragma: no cover — requires mcp package
    host: str = "127.0.0.1",
    port: int = 8080,
) -> None:
    """Run MCP server over Streamable HTTP transport.

    Requires `mcp` package with HTTP support: pip install ao-kernel[mcp]

    Args:
        host: Bind address (default: 127.0.0.1 for local only)
        port: Listen port (default: 8080)
    """
    try:
        from mcp.server.streamable_http import StreamableHTTPServerTransport
        from starlette.applications import Starlette
        from starlette.routing import Mount
        import uvicorn
    except ImportError:
        raise ImportError(
            "MCP HTTP transport requires starlette and uvicorn. Install with: pip install ao-kernel[mcp-http]"
        ) from None

    server = create_mcp_server()
    transport = StreamableHTTPServerTransport(server)

    app = Starlette(
        routes=[Mount("/mcp", app=transport.handle_request)],
    )

    config = uvicorn.Config(app, host=host, port=port, log_level="info")
    srv = uvicorn.Server(config)
    await srv.serve()
