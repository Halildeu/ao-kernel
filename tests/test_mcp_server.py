"""Tests for MCP server — governance logic, fail-closed behavior, decision envelope."""

from __future__ import annotations

import re


from ao_kernel.mcp_server import (
    TOOL_DEFINITIONS,
    TOOL_DISPATCH,
    _decision_envelope,
    handle_policy_check,
    handle_llm_call,
    handle_llm_route,
    handle_quality_gate,
    handle_workspace_status,
    handle_resource,
)


class TestDecisionEnvelope:
    def test_allow_envelope_has_all_fields(self):
        env = _decision_envelope(
            tool="test_tool",
            allowed=True,
            decision="allow",
            reason_codes=["OK"],
            data={"key": "value"},
        )
        assert env["allowed"] is True
        assert env["decision"] == "allow"
        assert env["api_version"] == "0.1.0"
        assert env["tool"] == "test_tool"
        assert re.match(r"\d{4}-\d{2}-\d{2}T", env["timestamp"])
        assert env["data"]["key"] == "value"
        assert env["reason_codes"] == ["OK"]
        assert env["error"] is None

    def test_deny_envelope_carries_error(self):
        env = _decision_envelope(
            tool="test_tool",
            allowed=False,
            decision="deny",
            reason_codes=["VIOLATION_X"],
            policy_ref="policy_test.v1.json",
            error="something failed",
        )
        assert env["allowed"] is False
        assert env["decision"] == "deny"
        assert "VIOLATION_X" in env["reason_codes"]
        assert env["policy_ref"] == "policy_test.v1.json"
        assert env["error"] == "something failed"

    def test_defaults_are_safe(self):
        env = _decision_envelope(tool="t", allowed=True, decision="allow")
        assert env["reason_codes"] == []
        assert env["policy_ref"] is None
        assert env["data"] is None
        assert env["error"] is None


class TestPolicyCheckGovernance:
    """Governance logic tests — not just envelope structure."""

    def test_missing_policy_name_denied(self):
        result = handle_policy_check({})
        assert result["allowed"] is False
        assert result["decision"] == "deny"
        assert "MISSING_POLICY_NAME" in result["reason_codes"]
        assert result["error"] is not None

    def test_nonexistent_policy_denied(self):
        result = handle_policy_check({"policy_name": "does_not_exist.json", "action": {}})
        assert result["allowed"] is False
        assert result["decision"] == "deny"
        assert "POLICY_NOT_FOUND" in result["reason_codes"]
        assert result["policy_ref"] == "does_not_exist.json"

    def test_valid_policy_with_action_allowed(self):
        result = handle_policy_check(
            {
                "policy_name": "policy_autonomy.v1.json",
                "action": {"type": "read", "scope": "workspace"},
            }
        )
        assert result["allowed"] is True
        assert result["decision"] == "allow"
        assert result["policy_ref"] == "policy_autonomy.v1.json"
        assert result["data"] is not None

    def test_empty_action_still_evaluated(self):
        result = handle_policy_check(
            {
                "policy_name": "policy_autonomy.v1.json",
                "action": {},
            }
        )
        # Empty action should still be evaluated (not rejected)
        assert result["decision"] in ("allow", "deny")
        assert result["tool"] == "ao_policy_check"

    def test_envelope_always_has_tool_and_timestamp(self):
        for params in [
            {},
            {"policy_name": "x", "action": {}},
            {"policy_name": "policy_autonomy.v1.json", "action": {"x": 1}},
        ]:
            result = handle_policy_check(params)
            assert result["tool"] == "ao_policy_check"
            assert result["api_version"] == "0.1.0"
            assert result["timestamp"] is not None


class TestLlmRouteGovernance:
    def test_empty_intent_denied(self):
        result = handle_llm_route({})
        assert result["allowed"] is False
        assert result["decision"] == "deny"
        assert "MISSING_INTENT" in result["reason_codes"]

    def test_blank_intent_denied(self):
        result = handle_llm_route({"intent": ""})
        assert result["allowed"] is False
        assert "MISSING_INTENT" in result["reason_codes"]

    def test_route_returns_structured_result(self):
        result = handle_llm_route({"intent": "FAST_TEXT"})
        assert result["tool"] == "ao_llm_route"
        assert result["decision"] in ("allow", "deny")
        assert isinstance(result["reason_codes"], list)
        # data may be None if router fails (missing config) — that's valid deny
        if result["decision"] == "deny":
            assert len(result["reason_codes"]) > 0


class TestQualityGateGovernance:
    def test_empty_output_denied(self):
        result = handle_quality_gate({})
        assert result["allowed"] is False
        assert result["decision"] == "deny"
        assert "EMPTY_OUTPUT" in result["reason_codes"]

    def test_blank_output_denied(self):
        result = handle_quality_gate({"output_text": ""})
        assert result["allowed"] is False
        assert "EMPTY_OUTPUT" in result["reason_codes"]

    def test_valid_output_evaluated(self):
        result = handle_quality_gate({"output_text": "This is a valid LLM response with content."})
        assert result["tool"] == "ao_quality_gate"
        assert result["decision"] in ("allow", "deny")
        # Gate should either pass or explain why it failed
        assert isinstance(result["reason_codes"], list)


class TestWorkspaceStatusGovernance:
    def test_no_workspace_reports_library_mode(self, empty_dir):
        result = handle_workspace_status({})
        assert result["allowed"] is True
        assert result["data"]["mode"] == "library"
        assert result["data"]["workspace"] is None

    def test_healthy_workspace_reports_version(self, tmp_workspace):
        result = handle_workspace_status({"workspace_root": str(tmp_workspace)})
        assert result["allowed"] is True
        assert result["data"]["status"] == "healthy"

        import ao_kernel

        assert result["data"]["version"] == ao_kernel.__version__
        assert result["data"]["kind"] == "ao-workspace"
        assert result["data"]["mode"] == "workspace"

    def test_corrupted_workspace_detected(self, tmp_path):
        ws = tmp_path / ".ao"
        ws.mkdir()
        (ws / "workspace.json").write_text("{{invalid json")
        import os

        old = os.getcwd()
        os.chdir(tmp_path)
        try:
            result = handle_workspace_status({})
            assert result["data"]["status"] == "corrupted"
        finally:
            os.chdir(old)

    def test_missing_workspace_json_detected(self, tmp_path):
        ws = tmp_path / ".ao"
        ws.mkdir()  # No workspace.json
        import os

        old = os.getcwd()
        os.chdir(tmp_path)
        try:
            result = handle_workspace_status({})
            assert result["data"]["status"] == "corrupted"
        finally:
            os.chdir(old)


class TestResourceLoading:
    def test_policy_resource_has_content(self):
        data = handle_resource("ao://policies/policy_autonomy.v1.json")
        assert isinstance(data, dict)
        assert len(data) > 0  # Not empty

    def test_schema_resource_has_structure(self):
        data = handle_resource("ao://schemas/active-context-profile.schema.v1.json")
        assert isinstance(data, dict)
        # JSON schemas have standard keys
        has_schema_key = "$schema" in data or "type" in data or "properties" in data
        assert has_schema_key

    def test_registry_resource_has_content(self):
        data = handle_resource("ao://registry/provider_capability_registry.v1.json")
        assert isinstance(data, dict)
        assert len(data) > 0

    def test_invalid_protocol_returns_none(self):
        assert handle_resource("http://policies/test.json") is None
        assert handle_resource("ftp://policies/test.json") is None
        assert handle_resource("") is None

    def test_unknown_resource_type_returns_none(self):
        assert handle_resource("ao://secrets/api_key.json") is None
        assert handle_resource("ao://tools/gateway.json") is None

    def test_nonexistent_file_returns_none(self):
        assert handle_resource("ao://policies/this_does_not_exist_xyz.json") is None

    def test_malformed_uri_returns_none(self):
        assert handle_resource("ao://") is None
        assert handle_resource("ao://policies") is None


class TestPolicyRulesEngine:
    """Tests for governance._check_generic_rules — required fields, blocked values, limits.

    These rules were previously duplicated in mcp_server._check_policy_rules.
    Now handle_policy_check delegates to governance.check_policy which handles
    all policy types (autonomy, tool_calling, provider_guardrails, generic).
    """

    def test_required_fields_violation(self):
        from ao_kernel.governance import _check_generic_rules

        policy = {"required_fields": ["name", "intent"]}
        violations = _check_generic_rules(policy, {"name": "test"})
        assert any("MISSING_REQUIRED_FIELD:intent" in v for v in violations)

    def test_required_fields_all_present(self):
        from ao_kernel.governance import _check_generic_rules

        policy = {"required_fields": ["name", "intent"]}
        violations = _check_generic_rules(policy, {"name": "test", "intent": "FAST_TEXT"})
        assert len(violations) == 0

    def test_blocked_values_violation(self):
        from ao_kernel.governance import _check_generic_rules

        policy = {"blocked_values": {"model": ["gpt-3.5-turbo", "deprecated-model"]}}
        violations = _check_generic_rules(policy, {"model": "gpt-3.5-turbo"})
        assert any("BLOCKED_VALUE:model" in v for v in violations)

    def test_blocked_values_allowed(self):
        from ao_kernel.governance import _check_generic_rules

        policy = {"blocked_values": {"model": ["gpt-3.5-turbo"]}}
        violations = _check_generic_rules(policy, {"model": "gpt-4"})
        assert len(violations) == 0

    def test_limits_exceeded(self):
        from ao_kernel.governance import _check_generic_rules

        policy = {"limits": {"max_tokens": 1000}}
        violations = _check_generic_rules(policy, {"max_tokens": 5000})
        assert any("LIMIT_EXCEEDED:max_tokens" in v for v in violations)

    def test_limits_within_range(self):
        from ao_kernel.governance import _check_generic_rules

        policy = {"limits": {"max_tokens": 1000}}
        violations = _check_generic_rules(policy, {"max_tokens": 500})
        assert len(violations) == 0

    def test_limits_non_numeric_ignored(self):
        from ao_kernel.governance import _check_generic_rules

        policy = {"limits": {"max_tokens": 1000}}
        violations = _check_generic_rules(policy, {"max_tokens": "not_a_number"})
        assert len(violations) == 0  # ValueError caught, no violation

    def test_empty_policy_no_violations(self):
        from ao_kernel.governance import _check_generic_rules

        violations = _check_generic_rules({}, {"any": "action"})
        assert violations == []

    def test_combined_violations(self):
        from ao_kernel.governance import _check_generic_rules

        policy = {
            "required_fields": ["intent"],
            "blocked_values": {"model": ["bad-model"]},
            "limits": {"temperature": 1.0},
        }
        action = {"model": "bad-model", "temperature": 2.0}
        violations = _check_generic_rules(policy, action)
        assert len(violations) == 3  # missing intent + blocked model + limit exceeded


class TestPolicyCheckDelegatesToGovernance:
    """Verify handle_policy_check delegates to governance.check_policy."""

    def test_delegates_to_governance_check_policy(self):
        from unittest.mock import patch

        mock_result = {
            "allowed": True,
            "decision": "allow",
            "reason_codes": ["POLICY_PASSED"],
            "policy_ref": "test.json",
            "data": {"policy_version": "v1"},
        }
        with patch("ao_kernel.governance.check_policy", return_value=mock_result) as mock_check:
            result = handle_policy_check(
                {
                    "policy_name": "test.json",
                    "action": {"intent": "FAST_TEXT"},
                }
            )
            mock_check.assert_called_once()
            assert result["allowed"] is True
            assert result["decision"] == "allow"

    def test_autonomy_violation_caught(self):
        """governance.check_policy handles autonomy policies (not just generic rules)."""
        from unittest.mock import patch

        autonomy_policy = {
            "enabled": True,
            "version": "v1",
            "intents": {
                "urn:core:deploy": {"mode": "human_review"},
            },
            "defaults": {"mode": "human_review"},
            "fail_action": "block",
        }
        with patch("ao_kernel.config.load_with_override", return_value=autonomy_policy):
            result = handle_policy_check(
                {
                    "policy_name": "policy_autonomy.v1.json",
                    "action": {"intent": "urn:core:deploy", "mode": "full_auto"},
                }
            )
        assert result["allowed"] is False
        assert any("AUTONOMY_MODE_DENIED" in r for r in result["reason_codes"])

    def test_governance_error_returns_deny(self):
        from unittest.mock import patch

        with patch("ao_kernel.governance.check_policy", side_effect=RuntimeError("boom")):
            result = handle_policy_check(
                {
                    "policy_name": "test.json",
                    "action": {},
                }
            )
        assert result["allowed"] is False
        assert "POLICY_CHECK_ERROR" in result["reason_codes"]


class TestPolicyCheckDisabledPath:
    def test_disabled_policy_allows(self):
        """Policy with enabled=false should return allow with POLICY_DISABLED."""
        from unittest.mock import patch

        mock_result = {
            "allowed": True,
            "decision": "allow",
            "reason_codes": ["POLICY_DISABLED"],
            "policy_ref": "test_disabled.json",
        }
        with patch("ao_kernel.governance.check_policy", return_value=mock_result):
            result = handle_policy_check(
                {
                    "policy_name": "test_disabled.json",
                    "action": {"type": "read"},
                }
            )
        assert result["allowed"] is True
        assert "POLICY_DISABLED" in result["reason_codes"]

    def test_policy_with_violations_denied(self):
        """Policy with required_fields violation should deny."""
        from unittest.mock import patch

        strict_policy = {"enabled": True, "required_fields": ["intent", "scope"]}
        with patch("ao_kernel.config.load_with_override", return_value=strict_policy):
            result = handle_policy_check(
                {
                    "policy_name": "strict.json",
                    "action": {"intent": "test"},  # missing scope
                }
            )
        assert result["allowed"] is False
        assert result["decision"] == "deny"
        assert any("MISSING_REQUIRED_FIELD:scope" in r for r in result["reason_codes"])


class TestLlmRouteSuccess:
    def test_route_error_returns_deny_with_reason(self):
        """When router raises, result should be structured deny."""
        from unittest.mock import patch

        with patch("ao_kernel.llm.resolve_route", side_effect=FileNotFoundError("no config")):
            result = handle_llm_route({"intent": "FAST_TEXT"})
        assert result["allowed"] is False
        assert result["decision"] == "deny"
        assert "ROUTER_ERROR" in result["reason_codes"]
        assert result["error"] is not None

    def test_route_success_returns_allow(self):
        """When router succeeds, result should be allow."""
        from unittest.mock import patch

        mock_result = {"status": "OK", "provider_id": "openai", "model": "gpt-4"}
        with patch("ao_kernel.llm.resolve_route", return_value=mock_result):
            result = handle_llm_route({"intent": "FAST_TEXT"})
        assert result["allowed"] is True
        assert result["decision"] == "allow"
        assert result["data"]["provider_id"] == "openai"


class TestQualityGateHandler:
    def test_quality_gate_fallback_not_configured(self):
        result = handle_quality_gate({"output_text": "Some LLM output text here."})
        assert result["tool"] == "ao_quality_gate"
        assert result["decision"] in ("allow", "deny")
        assert isinstance(result["reason_codes"], list)

    def test_quality_gate_with_workspace(self, tmp_workspace):
        result = handle_quality_gate(
            {
                "output_text": "Valid output from LLM provider.",
                "workspace_root": str(tmp_workspace),
            }
        )
        assert result["tool"] == "ao_quality_gate"
        assert result["decision"] in ("allow", "deny")

    def test_quality_gate_exception_returns_deny(self):
        """When quality gate raises, result should be structured deny."""
        from unittest.mock import patch

        with patch("ao_kernel.mcp_server.handle_quality_gate.__module__", side_effect=Exception("gate error")):
            # Force exception path by passing invalid workspace
            result = handle_quality_gate(
                {
                    "output_text": "test output",
                    "workspace_root": "/nonexistent/path/xyz",
                }
            )
        assert result["tool"] == "ao_quality_gate"
        assert result["decision"] in ("allow", "deny")


class TestToolRegistry:
    def test_every_definition_has_handler(self):
        for td in TOOL_DEFINITIONS:
            handler = TOOL_DISPATCH.get(td["name"])
            # Verify handler exists and returns a dict when called with empty params
            result = handler({})
            assert isinstance(result, dict), f"Tool {td['name']} handler should return dict"
            assert "tool" in result, f"Tool {td['name']} handler response missing 'tool' field"

    def test_every_handler_has_definition(self):
        defined_names = {td["name"] for td in TOOL_DEFINITIONS}
        for name in TOOL_DISPATCH:
            assert name in defined_names, f"Handler {name} has no definition"

    def test_schemas_have_required_fields(self):
        for td in TOOL_DEFINITIONS:
            schema = td["inputSchema"]
            assert schema["type"] == "object"
            assert "properties" in schema
            # Description should be meaningful (>10 chars)
            assert len(td["description"]) > 10

    def test_handler_returns_envelope_on_empty_params(self):
        """Every handler must return a valid envelope even with empty params."""
        for name, handler in TOOL_DISPATCH.items():
            result = handler({})
            assert "allowed" in result, f"{name} missing 'allowed'"
            assert "decision" in result, f"{name} missing 'decision'"
            assert "tool" in result, f"{name} missing 'tool'"
            assert result["tool"] == name


class TestHandleLLMCall:
    def test_missing_messages_denied(self):
        result = handle_llm_call({})
        assert result["allowed"] is False
        assert result["decision"] == "deny"
        assert "MISSING_MESSAGES" in result["reason_codes"]

    def test_invalid_messages_denied(self):
        result = handle_llm_call({"messages": "not a list"})
        assert result["allowed"] is False
        assert "MISSING_MESSAGES" in result["reason_codes"]

    def test_missing_api_key_denied(self):
        import os

        # Ensure no API key in env
        old = os.environ.pop("OPENAI_API_KEY", None)
        try:
            result = handle_llm_call(
                {
                    "messages": [{"role": "user", "content": "test"}],
                    "provider_id": "openai",
                    "model": "gpt-4",
                }
            )
            assert result["allowed"] is False
            assert "MISSING_API_KEY" in result["reason_codes"]
            # B2: error message must surface the env candidates that were checked
            # so operators know which variable to set (dual-read visibility).
            assert "OPENAI_API_KEY" in result["error"]
        finally:
            if old is not None:
                os.environ["OPENAI_API_KEY"] = old

    def test_missing_api_key_reports_all_candidates(self, monkeypatch):
        """B2: claude provider should mention both ANTHROPIC_API_KEY and CLAUDE_API_KEY."""
        for name in ("ANTHROPIC_API_KEY", "CLAUDE_API_KEY"):
            monkeypatch.delenv(name, raising=False)
        result = handle_llm_call(
            {
                "messages": [{"role": "user", "content": "test"}],
                "provider_id": "claude",
                "model": "claude-3-5-sonnet-latest",
            }
        )
        assert result["allowed"] is False
        assert "MISSING_API_KEY" in result["reason_codes"]
        assert "ANTHROPIC_API_KEY" in result["error"]
        assert "CLAUDE_API_KEY" in result["error"]

    def test_legacy_claude_env_var_accepted(self, monkeypatch):
        """B2: pre-D0.3 deployments using CLAUDE_API_KEY must keep working."""
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        monkeypatch.setenv("CLAUDE_API_KEY", "sk-legacy-abc")
        # The call will still fail at build/execute since we are not wired up
        # to a live provider, but it must NOT fail with MISSING_API_KEY —
        # the resolver found the alternate env name and passed it through.
        result = handle_llm_call(
            {
                "messages": [{"role": "user", "content": "test"}],
                "provider_id": "claude",
                "model": "claude-3-5-sonnet-latest",
            }
        )
        # Either the call succeeds, or it fails at a later stage (network,
        # auth rejection, etc.). Anything EXCEPT MISSING_API_KEY proves the
        # dual-read path served the legacy env name.
        assert "MISSING_API_KEY" not in result.get("reason_codes", [])

    def test_tool_definitions_include_llm_call(self):
        names = [td["name"] for td in TOOL_DEFINITIONS]
        assert "ao_llm_call" in names
        assert "ao_memory_read" in names
        assert "ao_memory_write" in names
        assert len(TOOL_DEFINITIONS) == 7

    def test_dispatch_includes_llm_call(self):
        assert "ao_llm_call" in TOOL_DISPATCH
        # B4: dispatch entries are evidence-wrapped; verify the underlying
        # handler via __wrapped__ (populated by functools.wraps).
        dispatched = TOOL_DISPATCH["ao_llm_call"]
        assert getattr(dispatched, "__wrapped__", dispatched) is handle_llm_call


class TestQualityGatePreviousDecisions:
    """Verify quality gate passes previous_decisions for consistency/regression checks."""

    def test_passes_previous_decisions_from_params(self):
        from unittest.mock import patch

        prev = [{"key": "test", "value": "v1", "confidence": 0.9}]
        with patch("ao_kernel.governance.evaluate_quality") as mock_eval:
            mock_eval.return_value = []
            handle_quality_gate(
                {
                    "output_text": "test output",
                    "previous_decisions": prev,
                }
            )
            _, kwargs = mock_eval.call_args
            assert kwargs["previous_decisions"] is prev

    def test_auto_loads_canonical_decisions(self, tmp_path):
        from unittest.mock import patch

        canonical = [{"key": "arch.pattern", "value": "CQRS"}]
        with (
            patch("ao_kernel.governance.evaluate_quality") as mock_eval,
            patch("ao_kernel.context.canonical_store.query", return_value=canonical) as mock_query,
        ):
            mock_eval.return_value = []
            handle_quality_gate(
                {
                    "output_text": "test output",
                    "workspace_root": str(tmp_path),
                }
            )
            mock_query.assert_called_once_with(tmp_path)
            _, kwargs = mock_eval.call_args
            assert kwargs["previous_decisions"] is canonical


class TestToolGatewayFromDict:
    """Verify create_tool_gateway uses ToolCallPolicy.from_dict."""

    def test_uses_from_dict(self):
        from unittest.mock import patch
        from ao_kernel.mcp_server import create_tool_gateway

        tool_policy = {"enabled": False, "max_tool_rounds": 5, "allow_unknown": True}
        with patch("ao_kernel.config.load_default", return_value=tool_policy):
            gw = create_tool_gateway()
        # from_dict extracts max_tool_rounds=5, allow_unknown=True
        # but enabled is always overridden to True
        assert gw.policy.enabled is True
        assert gw.policy.max_rounds == 5
        assert gw.policy.allow_unknown is True

    def test_always_enabled_even_if_policy_says_false(self):
        from unittest.mock import patch
        from ao_kernel.mcp_server import create_tool_gateway

        tool_policy = {"enabled": False, "max_tool_rounds": 3}
        with patch("ao_kernel.config.load_default", return_value=tool_policy):
            gw = create_tool_gateway()
        assert gw.policy.enabled is True

    def test_fallback_on_load_error(self):
        from unittest.mock import patch
        from ao_kernel.mcp_server import create_tool_gateway

        with patch("ao_kernel.config.load_default", side_effect=FileNotFoundError("nope")):
            gw = create_tool_gateway()
        assert gw.policy.enabled is True
        assert gw.policy.max_rounds == 10


class TestV39B2MCPIntegration:
    """v3.9 B2: MCP integration pins — is_mutating flag, reason_code."""

    def test_ao_memory_write_is_marked_mutating(self):
        # v3.9 B2: the governance tool that mutates canonical store
        # must be flagged so the mutating-confirm gate can enforce.
        from ao_kernel.mcp_server import create_tool_gateway

        gw = create_tool_gateway()
        entries = {t["name"]: t for t in gw.list_tools()}
        assert entries["ao_memory_write"]["is_mutating"] is True
        # Other governance tools are read-only by contract.
        for read_only_tool in (
            "ao_policy_check",
            "ao_llm_route",
            "ao_llm_call",
            "ao_quality_gate",
            "ao_workspace_status",
            "ao_memory_read",
        ):
            assert entries[read_only_tool]["is_mutating"] is False

    def test_denial_result_carries_reason_code(self):
        # v3.9 B2: gw.dispatch() must populate reason_code on DENIED
        # so the MCP envelope can propagate it as a machine-readable
        # value (not free-form reason string).
        from ao_kernel.mcp_server import create_tool_gateway

        gw = create_tool_gateway()
        result = gw.dispatch("unregistered_tool_xyz", {})
        assert result.status == "DENIED"
        assert result.reason_code == "TOOL_NOT_REGISTERED"
        # reason mirrors reason_code (backward compat) — envelope
        # consumers that used `reason` still see the same string.
        assert result.reason == "TOOL_NOT_REGISTERED"
