"""Tests for ao_kernel.tool_gateway — policy-gated tool dispatch."""

from __future__ import annotations

from ao_kernel.tool_gateway import (
    ToolCallPolicy,
    ToolGateway,
    ToolSpec,
)


def _echo_handler(params: dict) -> dict:
    return {"echo": params.get("msg", "")}


def _error_handler(params: dict) -> dict:
    raise RuntimeError("Intentional handler error")


class TestToolGatewayAuthorization:
    def test_registered_tool_authorized(self):
        gw = ToolGateway()
        gw.register_handler("echo", _echo_handler)
        allowed, reason = gw.authorize("echo")
        assert allowed is True
        assert reason == "AUTHORIZED"

    def test_unregistered_tool_denied(self):
        gw = ToolGateway()
        allowed, reason = gw.authorize("nonexistent")
        assert allowed is False
        assert reason == "TOOL_NOT_REGISTERED"

    def test_disabled_policy_denies_all(self):
        gw = ToolGateway(policy=ToolCallPolicy(enabled=False))
        gw.register_handler("echo", _echo_handler)
        allowed, reason = gw.authorize("echo")
        assert allowed is False
        assert reason == "POLICY_DISABLED"

    def test_disallowed_tool_denied(self):
        gw = ToolGateway()
        gw.register(ToolSpec(name="blocked", handler=_echo_handler, allowed=False))
        allowed, reason = gw.authorize("blocked")
        assert allowed is False
        assert reason == "TOOL_NOT_ALLOWED"

    def test_max_rounds_enforced(self):
        gw = ToolGateway(policy=ToolCallPolicy(max_rounds=2))
        gw.register_handler("echo", _echo_handler)
        gw.dispatch("echo", {"msg": "1"})
        gw.dispatch("echo", {"msg": "2"})
        allowed, reason = gw.authorize("echo")
        assert allowed is False
        assert reason == "MAX_ROUNDS_EXCEEDED"

    def test_reset_rounds(self):
        gw = ToolGateway(policy=ToolCallPolicy(max_rounds=1))
        gw.register_handler("echo", _echo_handler)
        gw.dispatch("echo", {"msg": "1"})
        gw.reset_rounds()
        allowed, _ = gw.authorize("echo")
        assert allowed is True


class TestToolGatewayDispatch:
    def test_successful_dispatch(self):
        gw = ToolGateway()
        gw.register_handler("echo", _echo_handler)
        result = gw.dispatch("echo", {"msg": "hello"})
        assert result.status == "OK"
        assert result.tool_name == "echo"
        assert result.output["echo"] == "hello"
        assert result.round_number == 1

    def test_dispatch_increments_rounds(self):
        gw = ToolGateway()
        gw.register_handler("echo", _echo_handler)
        r1 = gw.dispatch("echo", {"msg": "1"})
        r2 = gw.dispatch("echo", {"msg": "2"})
        assert r1.round_number == 1
        assert r2.round_number == 2

    def test_dispatch_unregistered_denied(self):
        gw = ToolGateway()
        result = gw.dispatch("ghost_tool", {})
        assert result.status == "DENIED"
        assert "NOT_REGISTERED" in result.reason

    def test_dispatch_handler_error(self):
        gw = ToolGateway()
        gw.register_handler("broken", _error_handler)
        result = gw.dispatch("broken", {})
        assert result.status == "ERROR"
        assert "Intentional handler error" in result.reason

    def test_dispatch_denied_tool_not_allowed(self):
        gw = ToolGateway()
        gw.register(ToolSpec(name="locked", handler=_echo_handler, allowed=False))
        result = gw.dispatch("locked", {})
        assert result.status == "DENIED"
        assert "NOT_ALLOWED" in result.reason


class TestToolCallPolicy:
    def test_default_policy(self):
        policy = ToolCallPolicy()
        assert policy.enabled is True
        assert policy.max_rounds == 10
        assert policy.allow_unknown is False

    def test_from_dict(self):
        policy = ToolCallPolicy.from_dict({
            "enabled": True,
            "max_tool_rounds": 5,
            "allow_unknown": False,
        })
        assert policy.max_rounds == 5

    def test_from_dict_defaults(self):
        policy = ToolCallPolicy.from_dict({})
        assert policy.enabled is True
        assert policy.max_rounds == 10


class TestToolGatewayRegistry:
    def test_list_tools_empty(self):
        gw = ToolGateway()
        assert gw.list_tools() == []

    def test_list_tools_after_register(self):
        gw = ToolGateway()
        gw.register_handler("echo", _echo_handler, description="Echo tool")
        gw.register_handler("add", lambda p: {"sum": 1}, description="Add tool")
        tools = gw.list_tools()
        assert len(tools) == 2
        names = {t["name"] for t in tools}
        assert "echo" in names
        assert "add" in names

    def test_register_overwrites(self):
        gw = ToolGateway()
        gw.register_handler("echo", _echo_handler, description="v1")
        gw.register_handler("echo", _echo_handler, description="v2")
        tools = gw.list_tools()
        assert len(tools) == 1
        assert tools[0]["description"] == "v2"


class TestMcpToolGatewayIntegration:
    def test_create_tool_gateway_has_4_tools(self):
        from ao_kernel.mcp_server import create_tool_gateway
        gw = create_tool_gateway()
        tools = gw.list_tools()
        assert len(tools) == 4
        names = {t["name"] for t in tools}
        assert "ao_policy_check" in names
        assert "ao_llm_route" in names
        assert "ao_quality_gate" in names
        assert "ao_workspace_status" in names

    def test_gateway_dispatch_policy_check(self):
        from ao_kernel.mcp_server import create_tool_gateway
        gw = create_tool_gateway()
        result = gw.dispatch("ao_policy_check", {})
        assert result.status == "OK"
        # Handler returns envelope with allowed=False for empty params
        assert result.output["allowed"] is False
        assert "MISSING_POLICY_NAME" in result.output["reason_codes"]

    def test_gateway_dispatch_workspace_status(self, empty_dir):
        from ao_kernel.mcp_server import create_tool_gateway
        gw = create_tool_gateway()
        result = gw.dispatch("ao_workspace_status", {})
        assert result.status == "OK"
        assert result.output["data"]["mode"] == "library"

    def test_gateway_rejects_unknown_tool(self):
        from ao_kernel.mcp_server import create_tool_gateway
        gw = create_tool_gateway()
        result = gw.dispatch("nonexistent_tool", {})
        assert result.status == "DENIED"
