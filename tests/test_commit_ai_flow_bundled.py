"""Cross-reference tests for the bundled `commit_ai_flow.v1.json`
(PR-B6 commit 4).

Pins:
- Schema-valid against `workflow-definition.schema.v1.json`
- Cross-reference consistency with codex-stub manifest:
  * expected_adapter_refs ⊆ declared capabilities
  * required_capabilities ⊆ codex-stub.capabilities
  * output_parse rule exists for commit_message capability
"""

from __future__ import annotations

import json
from pathlib import Path

from jsonschema import Draft202012Validator

from ao_kernel.config import load_default


def _bundled_workflow(name: str) -> dict:
    import ao_kernel
    pkg_root = Path(ao_kernel.__file__).parent
    path = pkg_root / "defaults" / "workflows" / name
    return json.loads(path.read_text(encoding="utf-8"))


def _bundled_adapter_manifest(name: str) -> dict:
    import ao_kernel
    pkg_root = Path(ao_kernel.__file__).parent
    path = pkg_root / "defaults" / "adapters" / name
    return json.loads(path.read_text(encoding="utf-8"))


class TestCommitAiFlowSchema:
    def test_loads(self) -> None:
        flow = _bundled_workflow("commit_ai_flow.v1.json")
        assert flow["workflow_id"] == "commit_ai_flow"
        assert flow["workflow_version"] == "1.0.0"

    def test_schema_valid(self) -> None:
        schema = load_default("schemas", "workflow-definition.schema.v1.json")
        flow = _bundled_workflow("commit_ai_flow.v1.json")
        errors = list(Draft202012Validator(schema).iter_errors(flow))
        assert errors == [], (
            f"bundled commit_ai_flow.v1.json fails workflow-definition "
            f"schema: {[e.message for e in errors]}"
        )

    def test_required_top_level_fields(self) -> None:
        flow = _bundled_workflow("commit_ai_flow.v1.json")
        # Schema requires: steps (+ others per definition)
        assert "steps" in flow
        assert "default_policy_refs" in flow
        assert "created_at" in flow
        assert "expected_adapter_refs" in flow

    def test_steps_structure(self) -> None:
        flow = _bundled_workflow("commit_ai_flow.v1.json")
        steps = flow["steps"]
        assert len(steps) == 2
        # Step 0: context_compile (ao-kernel)
        assert steps[0]["step_name"] == "compile_context"
        assert steps[0]["actor"] == "ao-kernel"
        assert steps[0]["operation"] == "context_compile"
        assert steps[0]["on_failure"] == "transition_to_failed"
        # Step 1: invoke_commit_agent (adapter)
        assert steps[1]["step_name"] == "invoke_commit_agent"
        assert steps[1]["actor"] == "adapter"
        assert steps[1]["adapter_id"] == "codex-stub"
        assert "commit_message" in steps[1]["required_capabilities"]
        assert steps[1]["on_failure"] == "transition_to_failed"

    def test_on_failure_string_enum(self) -> None:
        """PR-B6 v3 iter-2 B1 absorb: on_failure MUST be a string (not
        an object)."""
        flow = _bundled_workflow("commit_ai_flow.v1.json")
        for step in flow["steps"]:
            assert isinstance(step["on_failure"], str), (
                f"step {step['step_name']!r} on_failure must be string, "
                f"got {type(step['on_failure']).__name__}"
            )
            assert step["on_failure"] in {
                "transition_to_failed",
                "retry_once",
                "escalate_to_human",
            }


class TestCrossRefWithCodexStub:
    def test_expected_adapter_refs_in_codex_stub(self) -> None:
        """Workflow's expected_adapter_refs declares codex-stub; manifest
        must cover the required capabilities."""
        flow = _bundled_workflow("commit_ai_flow.v1.json")
        manifest = _bundled_adapter_manifest("codex-stub.manifest.v1.json")

        assert manifest["adapter_id"] in flow["expected_adapter_refs"]

    def test_required_capabilities_covered_by_codex_stub(self) -> None:
        """Workflow step's required_capabilities must be a subset of
        the expected adapter's declared capabilities."""
        flow = _bundled_workflow("commit_ai_flow.v1.json")
        manifest = _bundled_adapter_manifest("codex-stub.manifest.v1.json")
        stub_caps = set(manifest["capabilities"])

        adapter_step = next(
            s for s in flow["steps"] if s["actor"] == "adapter"
        )
        step_caps = set(adapter_step["required_capabilities"])
        missing = step_caps - stub_caps
        assert missing == set(), (
            f"codex-stub missing capabilities required by "
            f"commit_ai_flow.invoke_commit_agent: {missing}"
        )

    def test_commit_message_output_parse_rule_exists(self) -> None:
        """codex-stub manifest must have an output_parse rule for
        commit_message capability (so walker extracts it from the
        envelope)."""
        manifest = _bundled_adapter_manifest("codex-stub.manifest.v1.json")
        rules = manifest["output_parse"]["rules"]
        commit_rules = [
            r for r in rules if r["capability"] == "commit_message"
        ]
        assert len(commit_rules) == 1
        rule = commit_rules[0]
        assert rule["json_path"] == "$.commit_message"
        assert rule["schema_ref"] == "commit-message.schema.v1.json"


class TestBundledVsReviewAiFlowParity:
    """Structural parity check: commit_ai_flow should mirror
    review_ai_flow's bundled pattern (except step-specific fields)."""

    def test_both_have_context_compile_first(self) -> None:
        review = _bundled_workflow("review_ai_flow.v1.json")
        commit = _bundled_workflow("commit_ai_flow.v1.json")
        assert review["steps"][0]["operation"] == "context_compile"
        assert commit["steps"][0]["operation"] == "context_compile"

    def test_both_declare_expected_adapter_refs(self) -> None:
        review = _bundled_workflow("review_ai_flow.v1.json")
        commit = _bundled_workflow("commit_ai_flow.v1.json")
        assert "expected_adapter_refs" in review
        assert "expected_adapter_refs" in commit

    def test_both_use_codex_stub(self) -> None:
        review = _bundled_workflow("review_ai_flow.v1.json")
        commit = _bundled_workflow("commit_ai_flow.v1.json")
        assert "codex-stub" in review["expected_adapter_refs"]
        assert "codex-stub" in commit["expected_adapter_refs"]
