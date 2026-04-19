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
        policy = ToolCallPolicy.from_dict(
            {
                "enabled": True,
                "max_tool_rounds": 5,
                "allow_unknown": False,
            }
        )
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
    def test_create_tool_gateway_has_7_tools(self):
        from ao_kernel.mcp_server import create_tool_gateway

        gw = create_tool_gateway()
        tools = gw.list_tools()
        assert len(tools) == 7
        names = {t["name"] for t in tools}
        assert "ao_policy_check" in names
        assert "ao_llm_route" in names
        assert "ao_llm_call" in names
        assert "ao_quality_gate" in names
        assert "ao_workspace_status" in names
        assert "ao_memory_read" in names
        assert "ao_memory_write" in names

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


class TestToolCallPolicyAbsorbV39B1:
    """v3.9 B1 — contract absorb for dormant policy fields.

    Parser-only: validates that `ToolCallPolicy.from_dict()` reads the
    dormant fields from `policy_tool_calling.v1.json`. Runtime enforcement
    of these fields is B2's scope.
    """

    def test_from_dict_absorbs_all_new_fields(self):
        raw = {
            "enabled": True,
            "max_tool_rounds": 4,
            "max_tool_calls_per_request": 7,
            "allowed_tools": ["read_file", "run_tests"],
            "blocked_tools": ["shell_exec"],
            "tool_permissions": {
                "default": "mutating",
                "mutating_requires_confirmation": False,
            },
            "cycle_detection": {
                "enabled": False,
                "max_identical_calls": 3,
            },
        }
        policy = ToolCallPolicy.from_dict(raw)
        assert policy.max_calls_per_request == 7
        assert policy.allowed_tools == ("read_file", "run_tests")
        assert policy.blocked_tools == ("shell_exec",)
        assert policy.default_permission == "mutating"
        assert policy.mutating_requires_confirmation is False
        assert policy.cycle_detection_enabled is False
        assert policy.cycle_max_identical_calls == 3

    def test_from_dict_defaults_when_fields_missing(self):
        # Empty dict should yield all v3.9 B1 defaults (no KeyError).
        policy = ToolCallPolicy.from_dict({})
        assert policy.max_calls_per_request == 5
        assert policy.allowed_tools == ()
        assert policy.blocked_tools == ()
        assert policy.default_permission == "read_only"
        assert policy.mutating_requires_confirmation is True
        assert policy.cycle_detection_enabled is True
        assert policy.cycle_max_identical_calls == 2

    def test_from_dict_invalid_max_calls_type_raises(self):
        import pytest

        with pytest.raises(ValueError, match="max_tool_calls_per_request must be int"):
            ToolCallPolicy.from_dict({"max_tool_calls_per_request": "5"})

    def test_from_dict_invalid_max_calls_negative_raises(self):
        import pytest

        with pytest.raises(ValueError, match="max_tool_calls_per_request must be >= 1"):
            ToolCallPolicy.from_dict({"max_tool_calls_per_request": 0})

    def test_from_dict_invalid_default_permission_raises(self):
        import pytest

        with pytest.raises(ValueError, match="tool_permissions.default must be"):
            ToolCallPolicy.from_dict({"tool_permissions": {"default": "xyz"}})

    def test_from_dict_invalid_cycle_max_negative_raises(self):
        import pytest

        with pytest.raises(ValueError, match="cycle_detection.max_identical_calls must be >= 1"):
            ToolCallPolicy.from_dict({"cycle_detection": {"max_identical_calls": 0}})

    def test_from_dict_allowed_tools_non_string_entry_raises(self):
        import pytest

        with pytest.raises(ValueError, match="allowed_tools entries must be str"):
            ToolCallPolicy.from_dict({"allowed_tools": ["ok", 123]})

    def test_from_dict_allowed_tools_non_list_raises(self):
        import pytest

        with pytest.raises(ValueError, match="allowed_tools must be list"):
            ToolCallPolicy.from_dict({"allowed_tools": "not_a_list"})

    def test_from_dict_minimal_normalization_preserves_duplicates(self):
        # B1 normalization is intentionally minimal (list→tuple only).
        # No dedupe/sort/lowercase — that's B2's semantic layer.
        policy = ToolCallPolicy.from_dict({"allowed_tools": ["Read", "read", "Read"]})
        assert policy.allowed_tools == ("Read", "read", "Read")

    def test_from_dict_tool_permissions_non_dict_raises(self):
        import pytest

        with pytest.raises(ValueError, match="tool_permissions must be object"):
            ToolCallPolicy.from_dict({"tool_permissions": "read_only"})


class TestCreateToolGatewayPolicyAbsorbV39B1:
    """v3.9 B1 — integration-level: absorbed fields survive `create_tool_gateway()`."""

    def test_create_tool_gateway_absorbs_bundled_policy_defaults(self):
        # Bundled policy_tool_calling.v1.json should round-trip through
        # from_dict() into the gateway's policy object with B1 defaults.
        from ao_kernel.mcp_server import create_tool_gateway

        gw = create_tool_gateway()
        policy = gw.policy
        # Bundled defaults (as of v3.9): match policy_tool_calling.v1.json
        assert policy.max_calls_per_request == 5
        assert policy.allowed_tools == ()
        assert policy.blocked_tools == ()
        assert policy.default_permission == "read_only"
        assert policy.mutating_requires_confirmation is True
        assert policy.cycle_detection_enabled is True
        assert policy.cycle_max_identical_calls == 2

    def test_create_tool_gateway_invalid_policy_surfaces_value_error(self, monkeypatch):
        # v3.9 B1 Codex MEDIUM: invalid policy content MUST NOT be
        # silently swallowed by the legacy `except Exception` fallback.
        # Load-path failures keep the safe default, but a ValueError
        # from from_dict() (contract violation) surfaces to the caller.
        import pytest
        import ao_kernel.mcp_server as mcp_mod

        def _bad_loader(kind, name):
            # Returns a dict that passes load step but fails from_dict().
            return {"max_tool_calls_per_request": 0}  # violates >= 1 rule

        monkeypatch.setattr("ao_kernel.config.load_default", _bad_loader)
        with pytest.raises(ValueError, match="max_tool_calls_per_request"):
            mcp_mod.create_tool_gateway()
