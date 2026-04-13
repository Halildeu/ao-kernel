"""Tests for MCP server — governance logic, fail-closed behavior, decision envelope."""

from __future__ import annotations

import re


from ao_kernel.mcp_server import (
    TOOL_DEFINITIONS,
    TOOL_DISPATCH,
    _decision_envelope,
    handle_policy_check,
    handle_llm_route,
    handle_quality_gate,
    handle_workspace_status,
    handle_resource,
)


class TestDecisionEnvelope:
    def test_allow_envelope_has_all_fields(self):
        env = _decision_envelope(
            tool="test_tool", allowed=True, decision="allow",
            reason_codes=["OK"], data={"key": "value"},
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
            tool="test_tool", allowed=False, decision="deny",
            reason_codes=["VIOLATION_X"], policy_ref="policy_test.v1.json",
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
        result = handle_policy_check({
            "policy_name": "policy_autonomy.v1.json",
            "action": {"type": "read", "scope": "workspace"},
        })
        assert result["allowed"] is True
        assert result["decision"] == "allow"
        assert result["policy_ref"] == "policy_autonomy.v1.json"
        assert result["data"] is not None

    def test_empty_action_still_evaluated(self):
        result = handle_policy_check({
            "policy_name": "policy_autonomy.v1.json",
            "action": {},
        })
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
        assert result["data"]["version"] == "0.1.0"
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


class TestToolRegistry:
    def test_every_definition_has_handler(self):
        for td in TOOL_DEFINITIONS:
            handler = TOOL_DISPATCH.get(td["name"])
            assert handler is not None, f"Tool {td['name']} has no handler"

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
