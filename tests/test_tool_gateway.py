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

    def test_from_dict_mutating_requires_confirmation_non_bool_raises(self):
        # v3.9 B1 iter-2 BLOCKER fix: strict bool, no silent coercion.
        # Regression pin for "false"/0/[] being accepted as True/False
        # (Codex post-impl review caught this gap).
        import pytest

        with pytest.raises(ValueError, match="mutating_requires_confirmation must be bool"):
            ToolCallPolicy.from_dict({"tool_permissions": {"mutating_requires_confirmation": "false"}})

    def test_from_dict_cycle_detection_enabled_non_bool_raises(self):
        # v3.9 B1 iter-2 BLOCKER fix: strict bool, no silent coercion.
        import pytest

        with pytest.raises(ValueError, match="cycle_detection.enabled must be bool"):
            ToolCallPolicy.from_dict(
                {"cycle_detection": {"enabled": 1}}  # int, not bool
            )

    # ------------------------------------------------------------------
    # v3.9 post-release M2 — legacy field bool-strict + max_tool_rounds
    # schema alignment (1 <= x <= 10). Pre-M2, these silently coerced
    # "true"/"false" strings, 0/1 ints, and other payloads. That
    # diverged from the stricter B1 field handling in the same parser.
    # ------------------------------------------------------------------

    def test_from_dict_enabled_non_bool_raises(self):
        import pytest

        with pytest.raises(ValueError, match="enabled must be bool"):
            ToolCallPolicy.from_dict({"enabled": "true"})

    def test_from_dict_allow_unknown_non_bool_raises(self):
        import pytest

        with pytest.raises(ValueError, match="allow_unknown must be bool"):
            ToolCallPolicy.from_dict({"allow_unknown": 1})  # int, not bool

    def test_from_dict_max_tool_rounds_non_int_raises(self):
        import pytest

        with pytest.raises(ValueError, match="max_tool_rounds must be int"):
            ToolCallPolicy.from_dict({"max_tool_rounds": "10"})

    def test_from_dict_max_tool_rounds_zero_raises(self):
        import pytest

        with pytest.raises(ValueError, match="max_tool_rounds must be between 1 and 10 inclusive"):
            ToolCallPolicy.from_dict({"max_tool_rounds": 0})

    def test_from_dict_max_tool_rounds_above_ten_raises(self):
        # Schema alignment: upper bound = 10 (inclusive).
        import pytest

        with pytest.raises(ValueError, match="max_tool_rounds must be between 1 and 10 inclusive"):
            ToolCallPolicy.from_dict({"max_tool_rounds": 11})

    def test_from_dict_max_tool_rounds_boundary_values_accepted(self):
        # 1 and 10 must both be accepted (inclusive bounds).
        p_lo = ToolCallPolicy.from_dict({"max_tool_rounds": 1})
        p_hi = ToolCallPolicy.from_dict({"max_tool_rounds": 10})
        assert p_lo.max_rounds == 1
        assert p_hi.max_rounds == 10


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


# =====================================================================
# v3.9 B2 — runtime enforcement, denial reasons, MCP integration.
# =====================================================================


def _noop_handler(params: dict) -> dict:
    return {"ok": True}


class TestAllowlistBlocklistEnforcement:
    """v3.9 B2: blocklist overrides allowlist; empty allowlist is permissive."""

    def test_blocklist_denies_with_reason_code(self):
        gw = ToolGateway(policy=ToolCallPolicy(blocked_tools=("dangerous",)))
        gw.register_handler("dangerous", _noop_handler)
        result = gw.dispatch("dangerous", {})
        assert result.status == "DENIED"
        assert result.reason_code == "BLOCKED_BY_POLICY"

    def test_blocklist_overrides_allowlist(self):
        # Even when listed in allowlist, blocklist wins.
        gw = ToolGateway(
            policy=ToolCallPolicy(
                allowed_tools=("tool_a",),
                blocked_tools=("tool_a",),
            )
        )
        gw.register_handler("tool_a", _noop_handler)
        result = gw.dispatch("tool_a", {})
        assert result.status == "DENIED"
        assert result.reason_code == "BLOCKED_BY_POLICY"

    def test_non_empty_allowlist_denies_unlisted(self):
        gw = ToolGateway(policy=ToolCallPolicy(allowed_tools=("only_this",)))
        gw.register_handler("only_this", _noop_handler)
        gw.register_handler("other_tool", _noop_handler)
        result = gw.dispatch("other_tool", {})
        assert result.status == "DENIED"
        assert result.reason_code == "NOT_IN_ALLOWLIST"

    def test_non_empty_allowlist_allows_listed(self):
        gw = ToolGateway(policy=ToolCallPolicy(allowed_tools=("only_this",)))
        gw.register_handler("only_this", _noop_handler)
        result = gw.dispatch("only_this", {})
        assert result.status == "OK"

    def test_empty_allowlist_is_permissive(self):
        # Pre-B2 behavior preserved: empty allowed_tools = allowlist
        # disabled; all registered tools permitted modulo blocklist.
        gw = ToolGateway(policy=ToolCallPolicy(allowed_tools=()))
        gw.register_handler("any_tool", _noop_handler)
        result = gw.dispatch("any_tool", {})
        assert result.status == "OK"


class TestMaxCallsPerRequestEnforcement:
    def test_per_request_cap_enforced(self):
        gw = ToolGateway(policy=ToolCallPolicy(max_calls_per_request=2, max_rounds=100))
        gw.register_handler("echo", _echo_handler)
        assert gw.dispatch("echo", {"msg": "1"}).status == "OK"
        assert gw.dispatch("echo", {"msg": "2"}).status == "OK"
        result = gw.dispatch("echo", {"msg": "3"})
        assert result.status == "DENIED"
        assert result.reason_code == "MAX_CALLS_PER_REQUEST_EXCEEDED"

    def test_reset_rounds_clears_request_count(self):
        # v3.9 B2: reset_rounds() now clears _request_call_count too.
        gw = ToolGateway(policy=ToolCallPolicy(max_calls_per_request=1, max_rounds=100))
        gw.register_handler("echo", _echo_handler)
        assert gw.dispatch("echo", {"msg": "1"}).status == "OK"
        assert gw.dispatch("echo", {"msg": "2"}).status == "DENIED"
        gw.reset_rounds()
        # After reset, the per-request cap should be fresh.
        assert gw.dispatch("echo", {"msg": "3"}).status == "OK"


class TestCycleDetection:
    def test_suffix_repeat_denied(self):
        # cycle_max_identical_calls=2 → DENY when the last 2 calls are
        # both identical to the new call.
        gw = ToolGateway(
            policy=ToolCallPolicy(
                cycle_detection_enabled=True,
                cycle_max_identical_calls=2,
                max_calls_per_request=100,
                max_rounds=100,
            )
        )
        gw.register_handler("echo", _echo_handler)
        # Two identical → second still OK (fills window).
        assert gw.dispatch("echo", {"msg": "same"}).status == "OK"
        assert gw.dispatch("echo", {"msg": "same"}).status == "OK"
        # Third identical → window is full of same key → DENY.
        result = gw.dispatch("echo", {"msg": "same"})
        assert result.status == "DENIED"
        assert result.reason_code == "CYCLE_DETECTED"

    def test_cycle_detection_disabled_allows_repeats(self):
        gw = ToolGateway(
            policy=ToolCallPolicy(
                cycle_detection_enabled=False,
                cycle_max_identical_calls=2,
                max_calls_per_request=100,
                max_rounds=100,
            )
        )
        gw.register_handler("echo", _echo_handler)
        for _ in range(5):
            assert gw.dispatch("echo", {"msg": "same"}).status == "OK"

    def test_different_params_break_cycle(self):
        # Different params → different fingerprint → no cycle.
        gw = ToolGateway(
            policy=ToolCallPolicy(
                cycle_detection_enabled=True,
                cycle_max_identical_calls=2,
                max_calls_per_request=100,
                max_rounds=100,
            )
        )
        gw.register_handler("echo", _echo_handler)
        assert gw.dispatch("echo", {"msg": "a"}).status == "OK"
        assert gw.dispatch("echo", {"msg": "a"}).status == "OK"
        # Interleave with a different call → cycle chain broken.
        assert gw.dispatch("echo", {"msg": "b"}).status == "OK"
        assert gw.dispatch("echo", {"msg": "a"}).status == "OK"

    def test_denied_attempt_not_recorded_in_history(self):
        # v3.9 B2: a denied cycle attempt must NOT append to history;
        # otherwise a single deny would feed itself indefinitely.
        gw = ToolGateway(
            policy=ToolCallPolicy(
                cycle_detection_enabled=True,
                cycle_max_identical_calls=2,
                max_calls_per_request=100,
                max_rounds=100,
            )
        )
        gw.register_handler("echo", _echo_handler)
        gw.dispatch("echo", {"x": 1})
        gw.dispatch("echo", {"x": 1})
        # Third repeated is denied.
        assert gw.dispatch("echo", {"x": 1}).status == "DENIED"
        # A different call should now succeed (not polluted by deny).
        assert gw.dispatch("echo", {"x": 2}).status == "OK"

    def test_fingerprint_handles_non_json_native_values(self):
        # v3.9 B2 Codex MEDIUM: json.dumps(default=repr) must not raise
        # on non-JSON-native values.
        class _Opaque:
            def __repr__(self):
                return "Opaque()"

        gw = ToolGateway(
            policy=ToolCallPolicy(
                cycle_detection_enabled=True,
                cycle_max_identical_calls=2,
                max_calls_per_request=100,
                max_rounds=100,
            )
        )
        gw.register_handler("echo", _echo_handler)
        # Must not raise.
        assert gw.dispatch("echo", {"obj": _Opaque()}).status == "OK"
        assert gw.dispatch("echo", {"obj": _Opaque()}).status == "OK"


class TestMutatingConfirmation:
    def test_mutating_tool_read_only_default_denied(self):
        gw = ToolGateway(
            policy=ToolCallPolicy(
                default_permission="read_only",
                mutating_requires_confirmation=True,
            )
        )
        gw.register_handler("write_file", _noop_handler, is_mutating=True)
        result = gw.dispatch("write_file", {})
        assert result.status == "DENIED"
        assert result.reason_code == "MUTATING_REQUIRES_CONFIRMATION"

    def test_mutating_tool_allowed_when_confirm_disabled(self):
        gw = ToolGateway(
            policy=ToolCallPolicy(
                default_permission="read_only",
                mutating_requires_confirmation=False,
            )
        )
        gw.register_handler("write_file", _noop_handler, is_mutating=True)
        result = gw.dispatch("write_file", {})
        assert result.status == "OK"

    def test_non_mutating_tool_unaffected(self):
        gw = ToolGateway(
            policy=ToolCallPolicy(
                default_permission="read_only",
                mutating_requires_confirmation=True,
            )
        )
        gw.register_handler("read_file", _noop_handler, is_mutating=False)
        result = gw.dispatch("read_file", {})
        assert result.status == "OK"


class TestReasonCodePropagation:
    """v3.9 B2: reason_code is set on every DENIED path."""

    def test_policy_disabled_reason_code(self):
        gw = ToolGateway(policy=ToolCallPolicy(enabled=False))
        gw.register_handler("echo", _echo_handler)
        result = gw.dispatch("echo", {})
        assert result.status == "DENIED"
        assert result.reason_code == "POLICY_DISABLED"

    def test_tool_not_registered_reason_code(self):
        gw = ToolGateway()
        result = gw.dispatch("nonexistent", {})
        assert result.status == "DENIED"
        assert result.reason_code == "TOOL_NOT_REGISTERED"


class TestListToolsIsMutatingIntrospection:
    def test_list_tools_exposes_is_mutating(self):
        # v3.9 B2: list_tools() output includes is_mutating so MCP
        # introspection (or any client-side policy UI) can surface it.
        gw = ToolGateway()
        gw.register_handler("read_op", _noop_handler, is_mutating=False)
        gw.register_handler("write_op", _noop_handler, is_mutating=True)
        entries = {t["name"]: t for t in gw.list_tools()}
        assert entries["read_op"]["is_mutating"] is False
        assert entries["write_op"]["is_mutating"] is True
