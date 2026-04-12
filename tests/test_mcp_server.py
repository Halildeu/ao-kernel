"""Tests for MCP server — tool handlers, resources, decision envelope."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

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
    def test_allow_envelope(self):
        env = _decision_envelope(
            tool="test_tool", allowed=True, decision="allow",
            reason_codes=["OK"], data={"key": "value"},
        )
        assert env["allowed"] is True
        assert env["decision"] == "allow"
        assert env["api_version"] == "0.1.0"
        assert env["tool"] == "test_tool"
        assert env["timestamp"]
        assert env["data"]["key"] == "value"

    def test_deny_envelope(self):
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

    def test_default_reason_codes_empty(self):
        env = _decision_envelope(tool="t", allowed=True, decision="allow")
        assert env["reason_codes"] == []


class TestPolicyCheck:
    def test_missing_policy_name(self):
        result = handle_policy_check({})
        assert result["allowed"] is False
        assert "MISSING_POLICY_NAME" in result["reason_codes"]

    def test_policy_not_found(self):
        result = handle_policy_check({"policy_name": "nonexistent_policy.json", "action": {}})
        assert result["allowed"] is False
        assert "POLICY_NOT_FOUND" in result["reason_codes"]

    def test_valid_policy_allow(self):
        result = handle_policy_check({
            "policy_name": "policy_autonomy.v1.json",
            "action": {"type": "read"},
        })
        assert result["allowed"] is True
        assert result["decision"] == "allow"

    def test_envelope_structure(self):
        result = handle_policy_check({
            "policy_name": "policy_autonomy.v1.json",
            "action": {},
        })
        assert "api_version" in result
        assert "timestamp" in result
        assert "tool" in result
        assert result["tool"] == "ao_policy_check"


class TestLlmRoute:
    def test_missing_intent(self):
        result = handle_llm_route({})
        assert result["allowed"] is False
        assert "MISSING_INTENT" in result["reason_codes"]

    def test_route_with_intent(self):
        result = handle_llm_route({"intent": "FAST_TEXT"})
        # Router may fail without full config, but should return structured deny
        assert "decision" in result
        assert result["tool"] == "ao_llm_route"


class TestQualityGate:
    def test_empty_output(self):
        result = handle_quality_gate({})
        assert result["allowed"] is False
        assert "EMPTY_OUTPUT" in result["reason_codes"]

    def test_with_output(self):
        result = handle_quality_gate({"output_text": "Hello, this is a valid output."})
        assert "decision" in result
        assert result["tool"] == "ao_quality_gate"


class TestWorkspaceStatus:
    def test_no_workspace_library_mode(self, empty_dir):
        result = handle_workspace_status({})
        assert result["allowed"] is True
        assert result["data"]["mode"] == "library"

    def test_with_workspace(self, tmp_workspace):
        result = handle_workspace_status({"workspace_root": str(tmp_workspace)})
        assert result["allowed"] is True
        assert result["data"]["status"] == "healthy"
        assert result["data"]["version"] == "0.1.0"

    def test_corrupted_workspace(self, tmp_path):
        ws = tmp_path / ".ao"
        ws.mkdir()
        (ws / "workspace.json").write_text("not json")
        import os
        old = os.getcwd()
        os.chdir(tmp_path)
        try:
            result = handle_workspace_status({})
            assert result["data"]["status"] == "corrupted"
        finally:
            os.chdir(old)


class TestResources:
    def test_load_policy_resource(self):
        data = handle_resource("ao://policies/policy_autonomy.v1.json")
        assert isinstance(data, dict)

    def test_load_schema_resource(self):
        data = handle_resource("ao://schemas/active-context-profile.schema.v1.json")
        assert isinstance(data, dict)

    def test_load_registry_resource(self):
        data = handle_resource("ao://registry/provider_capability_registry.v1.json")
        assert isinstance(data, dict)

    def test_invalid_uri(self):
        assert handle_resource("http://invalid") is None

    def test_unknown_resource_type(self):
        assert handle_resource("ao://unknown/file.json") is None

    def test_nonexistent_file(self):
        assert handle_resource("ao://policies/nonexistent.json") is None


class TestToolDefinitions:
    def test_all_tools_have_handlers(self):
        for td in TOOL_DEFINITIONS:
            assert td["name"] in TOOL_DISPATCH

    def test_tool_count(self):
        assert len(TOOL_DEFINITIONS) == 4
        assert len(TOOL_DISPATCH) == 4

    def test_tool_schemas_valid(self):
        for td in TOOL_DEFINITIONS:
            assert "name" in td
            assert "description" in td
            assert "inputSchema" in td
            schema = td["inputSchema"]
            assert schema["type"] == "object"
