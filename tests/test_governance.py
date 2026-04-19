"""Tests for ao_kernel.governance facade — policy check, quality gate, fail-closed."""

from __future__ import annotations

from unittest.mock import patch

from ao_kernel.governance import (
    QualityGateResult,
    check_policy,
    evaluate_quality,
    quality_summary,
)


class TestCheckPolicy:
    def test_missing_policy_name_denied(self):
        result = check_policy("", {})
        assert result["allowed"] is False
        assert "MISSING_POLICY_NAME" in result["reason_codes"]

    def test_nonexistent_policy_denied(self):
        result = check_policy("nonexistent_xyz.json", {"action": "test"})
        assert result["allowed"] is False
        assert "POLICY_NOT_FOUND" in result["reason_codes"]

    def test_valid_policy_allowed(self):
        result = check_policy("policy_autonomy.v1.json", {"type": "read"})
        assert result["allowed"] is True
        assert result["decision"] == "allow"

    def test_disabled_policy_allowed(self):
        disabled = {"enabled": False, "version": "v1"}
        with patch("ao_kernel.config.load_with_override", return_value=disabled):
            result = check_policy("test.json", {"action": "write"})
        assert result["allowed"] is True
        assert "POLICY_DISABLED" in result["reason_codes"]

    def test_required_field_violation_denied(self):
        policy = {"enabled": True, "required_fields": ["intent", "scope"]}
        with patch("ao_kernel.config.load_with_override", return_value=policy):
            result = check_policy("strict.json", {"intent": "test"})
        assert result["allowed"] is False
        assert any("MISSING_REQUIRED_FIELD:scope" in r for r in result["reason_codes"])

    def test_blocked_value_violation_denied(self):
        policy = {"enabled": True, "blocked_values": {"model": ["dangerous-model"]}}
        with patch("ao_kernel.config.load_with_override", return_value=policy):
            result = check_policy("block.json", {"model": "dangerous-model"})
        assert result["allowed"] is False
        assert any("BLOCKED_VALUE:model" in r for r in result["reason_codes"])

    def test_limit_exceeded_denied(self):
        policy = {"enabled": True, "limits": {"max_tokens": 1000}}
        with patch("ao_kernel.config.load_with_override", return_value=policy):
            result = check_policy("limits.json", {"max_tokens": 5000})
        assert result["allowed"] is False
        assert any("LIMIT_EXCEEDED:max_tokens" in r for r in result["reason_codes"])


class TestEvaluateQuality:
    def test_empty_output_fails(self):
        results = evaluate_quality("")
        assert len(results) >= 1
        assert results[0].passed is False
        assert results[0].gate_id == "output_not_empty"

    def test_valid_output_evaluates(self):
        results = evaluate_quality("This is a valid LLM output with meaningful content.")
        assert isinstance(results, list)
        for r in results:
            assert isinstance(r, QualityGateResult)
            assert isinstance(r.passed, bool)
            assert isinstance(r.gate_id, str)

    def test_fail_closed_on_error(self):
        """If quality gate module fails, result must be DENY, not allow."""
        with patch(
            "ao_kernel._internal.orchestrator.quality_gate.run_quality_gates", side_effect=RuntimeError("broken")
        ):
            results = evaluate_quality("test output")
        assert len(results) >= 1
        assert results[0].passed is False
        assert "error" in results[0].gate_id.lower() or "error" in results[0].reason.lower()

    def test_with_workspace(self, tmp_workspace):
        results = evaluate_quality(
            "Valid output text",
            workspace_root=tmp_workspace,
        )
        assert isinstance(results, list)


class TestQualitySummary:
    def test_all_passed(self):
        results = [
            QualityGateResult(passed=True, gate_id="schema_valid", action="pass", reason=""),
            QualityGateResult(passed=True, gate_id="not_empty", action="pass", reason=""),
        ]
        summary = quality_summary(results)
        assert summary["all_passed"] is True
        assert summary["total"] == 2
        assert summary["passed"] == 2
        assert summary["failed"] == 0

    def test_some_failed(self):
        results = [
            QualityGateResult(passed=True, gate_id="schema_valid", action="pass", reason=""),
            QualityGateResult(passed=False, gate_id="consistency", action="reject", reason="contradicts"),
        ]
        summary = quality_summary(results)
        assert summary["all_passed"] is False
        assert summary["failed"] == 1
        assert summary["gates"][1]["passed"] is False

    def test_empty_results(self):
        summary = quality_summary([])
        assert summary["all_passed"] is True
        assert summary["total"] == 0


class TestMcpQualityGateFailClosed:
    """Verify MCP quality gate handler no longer silently allows on error."""

    def test_mcp_quality_gate_uses_governance_facade(self):
        from ao_kernel.mcp_server import handle_quality_gate

        result = handle_quality_gate({"output_text": "test output"})
        assert result["tool"] == "ao_quality_gate"
        # Must NOT be silent allow — must have evaluated
        assert result["decision"] in ("allow", "deny")
        assert "data" in result

    def test_mcp_quality_gate_empty_denied(self):
        from ao_kernel.mcp_server import handle_quality_gate

        result = handle_quality_gate({"output_text": ""})
        assert result["allowed"] is False
        assert "EMPTY_OUTPUT" in result["reason_codes"]


class TestCheckAutonomy:
    """Tests for _check_autonomy — intent authorization and mode enforcement."""

    def test_known_intent_mode_match(self):
        from ao_kernel.governance import _check_autonomy

        policy = {
            "intents": {"urn:core:deploy": {"mode": "human_review"}},
            "defaults": {"mode": "human_review"},
        }
        violations = _check_autonomy(policy, {"intent": "urn:core:deploy", "mode": "human_review"})
        assert violations == []

    def test_known_intent_mode_mismatch_denied(self):
        from ao_kernel.governance import _check_autonomy

        policy = {
            "intents": {"urn:core:deploy": {"mode": "human_review"}},
            "defaults": {"mode": "human_review"},
        }
        violations = _check_autonomy(policy, {"intent": "urn:core:deploy", "mode": "full_auto"})
        assert any("AUTONOMY_MODE_DENIED" in v for v in violations)

    def test_unknown_intent_blocked(self):
        from ao_kernel.governance import _check_autonomy

        policy = {
            "intents": {"urn:core:deploy": {"mode": "human_review"}},
            "defaults": {"mode": "human_review"},
            "fail_action": "block",
        }
        violations = _check_autonomy(policy, {"intent": "urn:core:unknown_action"})
        assert any("AUTONOMY_UNKNOWN_INTENT" in v for v in violations)

    def test_unknown_intent_allowed_when_fail_action_allow(self):
        from ao_kernel.governance import _check_autonomy

        policy = {
            "intents": {},
            "defaults": {"mode": "human_review"},
            "fail_action": "allow",
        }
        violations = _check_autonomy(policy, {"intent": "urn:core:anything"})
        assert violations == []

    def test_no_intent_field_no_violation(self):
        from ao_kernel.governance import _check_autonomy

        policy = {"intents": {}, "defaults": {"mode": "human_review"}}
        violations = _check_autonomy(policy, {"mode": "full_auto"})
        assert violations == []


class TestCheckToolCalling:
    """Tests for _check_tool_calling — allowed/blocked tools enforcement."""

    def test_disabled_blocks_all_tools(self):
        from ao_kernel.governance import _check_tool_calling

        policy = {"enabled": False}
        violations = _check_tool_calling(policy, {"tool_name": "any_tool"})
        assert any("TOOL_CALLING_DISABLED" in v for v in violations)

    def test_blocked_tool_denied(self):
        from ao_kernel.governance import _check_tool_calling

        policy = {"enabled": True, "blocked_tools": ["dangerous_tool"], "allowed_tools": []}
        violations = _check_tool_calling(policy, {"tool_name": "dangerous_tool"})
        assert any("TOOL_BLOCKED" in v for v in violations)

    def test_not_in_allowlist_denied(self):
        from ao_kernel.governance import _check_tool_calling

        policy = {"enabled": True, "allowed_tools": ["safe_tool"], "blocked_tools": []}
        violations = _check_tool_calling(policy, {"tool_name": "other_tool"})
        assert any("TOOL_NOT_ALLOWED" in v for v in violations)

    def test_in_allowlist_allowed(self):
        from ao_kernel.governance import _check_tool_calling

        policy = {"enabled": True, "allowed_tools": ["safe_tool"], "blocked_tools": []}
        violations = _check_tool_calling(policy, {"tool_name": "safe_tool"})
        assert violations == []

    def test_empty_allowlist_is_permissive(self):
        # v3.9 B2 alignment: empty allowed_tools = allowlist disabled
        # (permissive, modulo blocklist). NOT a violation. Matches
        # ToolGateway semantic. The legacy TOOL_NO_ALLOWLIST violation
        # was removed — bundled default policy ships with
        # allowed_tools=[] and would otherwise reject every call.
        from ao_kernel.governance import _check_tool_calling

        policy = {"enabled": True, "allowed_tools": [], "blocked_tools": []}
        violations = _check_tool_calling(policy, {"tool_name": "any_tool"})
        assert violations == []

    def test_empty_allowlist_blocklist_still_enforced(self):
        # v3.9 B2: blocklist always overrides allowlist, even when
        # allowlist is empty/permissive.
        from ao_kernel.governance import _check_tool_calling

        policy = {
            "enabled": True,
            "allowed_tools": [],
            "blocked_tools": ["dangerous_tool"],
        }
        violations = _check_tool_calling(policy, {"tool_name": "dangerous_tool"})
        assert any("TOOL_BLOCKED" in v for v in violations)


class TestCheckProviderGuardrails:
    """Tests for _check_provider_guardrails — provider and model access control."""

    def test_provider_disabled_denied(self):
        from ao_kernel.governance import _check_provider_guardrails

        policy = {"providers": {"openai": {"enabled": False}}}
        violations = _check_provider_guardrails(policy, {"provider_id": "openai"})
        assert any("PROVIDER_DISABLED" in v for v in violations)

    def test_model_not_in_allowlist_denied(self):
        from ao_kernel.governance import _check_provider_guardrails

        policy = {"providers": {"openai": {"enabled": True, "allow_models": ["gpt-4"]}}}
        violations = _check_provider_guardrails(policy, {"provider_id": "openai", "model": "gpt-3.5-turbo"})
        assert any("MODEL_NOT_ALLOWED" in v for v in violations)

    def test_model_in_allowlist_allowed(self):
        from ao_kernel.governance import _check_provider_guardrails

        policy = {"providers": {"openai": {"enabled": True, "allow_models": ["gpt-4"]}}}
        violations = _check_provider_guardrails(policy, {"provider_id": "openai", "model": "gpt-4"})
        assert violations == []

    def test_wildcard_model_allows_any(self):
        from ao_kernel.governance import _check_provider_guardrails

        policy = {"providers": {"openai": {"enabled": True, "allow_models": ["*"]}}}
        violations = _check_provider_guardrails(policy, {"provider_id": "openai", "model": "any-model"})
        assert violations == []
