"""ao-kernel MCP server — governed runtime as Model Context Protocol service.

Exposes ao-kernel governance primitives as MCP tools and workspace content
as MCP resources. Transport-agnostic handler design (stdio first, HTTP later).

Tools (4):
    ao_policy_check    — validate an action against policy
    ao_llm_route       — resolve provider/model for an intent
    ao_quality_gate    — check output quality
    ao_workspace_status — workspace health report

Resources (3):
    ao://policies/{name}  — read-only policy JSON
    ao://schemas/{name}   — read-only schema JSON
    ao://registry/{name}  — read-only registry JSON

Design decisions (Codex CNS-20260413-004):
    - Fail-closed: policy violation → structured deny (not JSON-RPC error)
    - Evidence: automatic side-effect of tool calls (not client-initiated)
    - Decision envelope: all tools return {allowed, decision, reason_codes, ...}
    - No global state: workspace_root passed explicitly per call
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

_API_VERSION = "0.1.0"


def _find_workspace_root():
    """Find workspace root for context operations. Returns Path or None."""
    from pathlib import Path
    from ao_kernel.config import workspace_root
    ws = workspace_root()
    return Path(ws) if ws else None


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
        from ao_kernel.config import load_with_override, workspace_root as resolve_ws
        from pathlib import Path

        ws = Path(workspace_root) if workspace_root else resolve_ws()
        policy = load_with_override("policies", policy_name, workspace=ws)
    except FileNotFoundError:
        return _decision_envelope(
            tool="ao_policy_check",
            allowed=False,
            decision="deny",
            reason_codes=["POLICY_NOT_FOUND"],
            policy_ref=policy_name,
            error=f"Policy not found: {policy_name}",
        )
    except Exception as e:
        return _decision_envelope(
            tool="ao_policy_check",
            allowed=False,
            decision="deny",
            reason_codes=["POLICY_LOAD_ERROR"],
            policy_ref=policy_name,
            error=str(e)[:200],
        )

    # Basic policy validation: check if action violates any rules
    enabled = policy.get("enabled", True)
    if not enabled:
        return _decision_envelope(
            tool="ao_policy_check",
            allowed=True,
            decision="allow",
            reason_codes=["POLICY_DISABLED"],
            policy_ref=policy_name,
            data={"policy_enabled": False},
        )

    # Policy is loaded and enabled — validate action fields against policy rules
    violations = _check_policy_rules(policy, action)
    if violations:
        return _decision_envelope(
            tool="ao_policy_check",
            allowed=False,
            decision="deny",
            reason_codes=violations,
            policy_ref=policy_name,
            data={"violations": violations, "action": action},
        )

    return _decision_envelope(
        tool="ao_policy_check",
        allowed=True,
        decision="allow",
        reason_codes=["POLICY_PASSED"],
        policy_ref=policy_name,
        data={"policy_version": policy.get("version", "unknown")},
    )


def _check_policy_rules(policy: dict, action: dict) -> list[str]:
    """Check action against policy rules. Returns list of violation codes."""
    violations = []

    # Check required fields
    required = policy.get("required_fields", [])
    if isinstance(required, list):
        for field in required:
            if field not in action:
                violations.append(f"MISSING_REQUIRED_FIELD:{field}")

    # Check blocked values
    blocked = policy.get("blocked_values", {})
    if isinstance(blocked, dict):
        for field, blocked_vals in blocked.items():
            if field in action and action[field] in blocked_vals:
                violations.append(f"BLOCKED_VALUE:{field}")

    # Check max limits
    limits = policy.get("limits", {})
    if isinstance(limits, dict):
        for field, max_val in limits.items():
            if field in action:
                try:
                    if float(action[field]) > float(max_val):
                        violations.append(f"LIMIT_EXCEEDED:{field}")
                except (ValueError, TypeError):
                    pass

    return violations


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
    results = evaluate_quality(output_text, workspace_root=ws)
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


# ── MCP Server (requires `mcp` package) ────────────────────────────


TOOL_DEFINITIONS = [
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
                    "type": "array", "items": {"type": "string"},
                    "description": "Provider priority order",
                },
                "workspace_root": {"type": "string"},
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
]

TOOL_DISPATCH = {
    "ao_policy_check": handle_policy_check,
    "ao_llm_route": handle_llm_route,
    "ao_quality_gate": handle_quality_gate,
    "ao_workspace_status": handle_workspace_status,
}


def create_tool_gateway():
    """Create a ToolGateway pre-configured with MCP governance tools.

    Returns a policy-gated gateway where all 4 governance tools are registered.
    Tool calls go through: authorize → handler → result.
    """
    from ao_kernel.tool_gateway import ToolGateway, ToolCallPolicy

    # Load policy from bundled defaults
    # MCP governance tools are ALWAYS enabled (they ARE the governance layer)
    try:
        from ao_kernel.config import load_default
        tool_policy = load_default("policies", "policy_tool_calling.v1.json")
        policy = ToolCallPolicy(
            enabled=True,  # MCP governance tools always enabled
            max_rounds=int(tool_policy.get("max_tool_rounds", 10)),
        )
    except Exception:
        policy = ToolCallPolicy(enabled=True, max_rounds=10)

    gateway = ToolGateway(policy=policy)

    for td in TOOL_DEFINITIONS:
        handler = TOOL_DISPATCH.get(td["name"])
        if handler:
            gateway.register_handler(
                name=td["name"],
                handler=handler,
                description=td["description"],
                input_schema=td["inputSchema"],
            )

    return gateway


def create_mcp_server():  # pragma: no cover — requires mcp package
    """Create and configure the MCP server instance.

    Requires `mcp` package: pip install ao-kernel[mcp]
    """
    try:
        from mcp.server import Server
        from mcp.types import Resource, TextContent, Tool
    except ImportError:
        raise ImportError(
            "MCP server requires the 'mcp' package. "
            "Install with: pip install ao-kernel[mcp]"
        )

    server = Server("ao-kernel")

    @server.list_tools()
    async def list_tools():
        return [
            Tool(
                name=td["name"],
                description=td["description"],
                inputSchema=td["inputSchema"],
            )
            for td in TOOL_DEFINITIONS
        ]

    @server.call_tool()
    async def call_tool(name: str, arguments: dict):
        import time as _time
        from ao_kernel.telemetry import span as otel_span, record_mcp_tool_call, record_policy_check

        # Use ToolGateway for policy-gated dispatch (not raw TOOL_DISPATCH)
        gateway = create_tool_gateway()
        start = _time.monotonic()

        with otel_span("ao.mcp_tool_call", {"ao.mcp.tool": name}) as s:
            gw_result = gateway.dispatch(name, arguments or {})
            elapsed = (_time.monotonic() - start) * 1000.0

            if gw_result.status == "DENIED":
                deny_envelope = _decision_envelope(
                    tool=name, allowed=False, decision="deny",
                    reason_codes=[gw_result.reason],
                    error=f"ToolGateway denied: {gw_result.reason}",
                )
                s.set_attribute("ao.decision", "deny")
                record_mcp_tool_call(elapsed, tool=name, decision="deny")
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

            # Wire tool result into context pipeline
            try:
                from ao_kernel.context.decision_extractor import extract_from_tool_result
                from ao_kernel.context.canonical_store import promote_decision
                decisions = extract_from_tool_result(name, result)
                for d in decisions:
                    if d.confidence >= 0.8:
                        promote_decision(
                            _find_workspace_root(),
                            key=d.key, value=d.value, source="mcp_tool",
                            confidence=d.confidence,
                        )
            except Exception:
                pass  # Context wiring failure shouldn't block tool response

        return [TextContent(type="text", text=json.dumps(result, ensure_ascii=False))]

    @server.list_resources()
    async def list_resources():
        resources = []
        for rtype in ("policies", "schemas", "registry"):
            resources.append(Resource(
                uri=f"ao://{rtype}/",
                name=f"ao-kernel {rtype}",
                description=f"Bundled {rtype} JSON files",
                mimeType="application/json",
            ))
        return resources

    @server.read_resource()
    async def read_resource(uri: str):
        data = handle_resource(str(uri))
        if data is None:
            raise ValueError(f"Resource not found: {uri}")
        return json.dumps(data, indent=2, ensure_ascii=False)

    return server


async def serve_stdio():  # pragma: no cover — requires mcp package
    """Run MCP server over stdio transport."""
    try:
        from mcp.server.stdio import stdio_server
    except ImportError:
        raise ImportError(
            "MCP server requires the 'mcp' package. "
            "Install with: pip install ao-kernel[mcp]"
        )

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
            "MCP HTTP transport requires the 'mcp' package with HTTP support. "
            "Install with: pip install ao-kernel[mcp]"
        ) from None

    server = create_mcp_server()
    transport = StreamableHTTPServerTransport(server)

    app = Starlette(
        routes=[Mount("/mcp", app=transport.handle_request)],
    )

    config = uvicorn.Config(app, host=host, port=port, log_level="info")
    srv = uvicorn.Server(config)
    await srv.serve()
