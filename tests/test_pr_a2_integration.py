"""End-to-end integration tests for PR-A2 wiring.

Exercises the full resolution chain:

    intent_text → IntentRouter.classify → WorkflowRegistry.get →
    WorkflowRegistry.validate_cross_refs(definition, AdapterRegistry)

Fail-closed acceptance (plan v2 B2): when ``validate_cross_refs``
returns a non-empty list, the integration test raises so a downstream
PR-A3 executor following the same pattern would block execution.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from ao_kernel.adapters import AdapterRegistry
from ao_kernel.workflow import (
    CrossRefIssue,
    IntentRouter,
    WorkflowDefinitionCrossRefError,
    WorkflowRegistry,
)


_FIXTURE_SRC = Path(__file__).parent / "fixtures" / "adapter_manifests"


def _copy_adapters(dest_workspace: Path, names: list[str]) -> None:
    adapters_dir = dest_workspace / ".ao" / "adapters"
    adapters_dir.mkdir(parents=True, exist_ok=True)
    for name in names:
        shutil.copy2(_FIXTURE_SRC / name, adapters_dir / name)


def _resolve(
    workspace_root: Path,
    intent_text: str,
) -> tuple[object, list[CrossRefIssue]]:
    """Run the intent → registry → cross-ref pipeline.

    Returns ``(definition, issues)``. Raises nothing; callers decide
    whether to treat issues as a failure.
    """
    router = IntentRouter()
    classification = router.classify(intent_text)
    assert classification is not None, "intent must classify for this test"

    wf_reg = WorkflowRegistry()
    wf_reg.load_bundled()
    wf_reg.load_workspace(workspace_root)
    definition = wf_reg.get(
        classification.workflow_id,
        version=classification.workflow_version,
    )

    adapter_reg = AdapterRegistry()
    adapter_reg.load_workspace(workspace_root)

    issues = wf_reg.validate_cross_refs(definition, adapter_reg)
    return definition, issues


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


class TestHappyPath:
    def test_bug_fix_intent_resolves_to_definition_and_passes_cross_ref(
        self, tmp_path: Path
    ) -> None:
        _copy_adapters(
            tmp_path,
            [
                "codex-stub.manifest.v1.json",
                "gh-cli-pr.manifest.v1.json",
            ],
        )
        definition, issues = _resolve(
            tmp_path, "Please fix the broken login bug in production"
        )
        assert definition.workflow_id == "bug_fix_flow"
        assert issues == []

    def test_classification_confidence_propagates(self, tmp_path: Path) -> None:
        _copy_adapters(
            tmp_path,
            [
                "codex-stub.manifest.v1.json",
                "gh-cli-pr.manifest.v1.json",
            ],
        )
        router = IntentRouter()
        classification = router.classify("bug report: defect in queue")
        assert classification is not None
        assert 0 <= classification.confidence <= 1

    def test_no_adapters_shipped_surfaces_missing_adapter_issues(
        self, tmp_path: Path
    ) -> None:
        # Zero adapters in workspace; bundled workflow expects codex-stub + gh-cli-pr.
        _, issues = _resolve(tmp_path, "please fix the crash")
        kinds = {i.kind for i in issues}
        assert kinds == {"missing_adapter"}
        missing_ids = {i.adapter_id for i in issues if i.kind == "missing_adapter"}
        # Two top-level adapter refs (one per expected_adapter_ref) + per-step
        # adapter references; both should be missing.
        assert {"codex-stub", "gh-cli-pr"}.issubset(missing_ids)


# ---------------------------------------------------------------------------
# Fail-closed acceptance
# ---------------------------------------------------------------------------


class TestFailClosedAcceptance:
    def test_integration_raises_aggregated_cross_ref_error(
        self, tmp_path: Path
    ) -> None:
        """Demonstrates the pattern PR-A3 executor will adopt: when
        cross-ref validation returns a non-empty issue list, the caller
        raises a ``WorkflowDefinitionCrossRefError`` carrying the full
        issue tuple for audit.
        """
        _copy_adapters(
            tmp_path,
            [
                "codex-stub.manifest.v1.json",
                # gh-cli-pr missing on purpose.
            ],
        )
        definition, issues = _resolve(tmp_path, "please fix the crash")
        assert issues, "setup should produce cross-ref issues"
        with pytest.raises(WorkflowDefinitionCrossRefError) as ei:
            raise WorkflowDefinitionCrossRefError(
                workflow_id=definition.workflow_id,
                issues=tuple(issues),
            )
        assert ei.value.workflow_id == "bug_fix_flow"
        assert len(ei.value.issues) == len(issues)

    def test_partial_capability_gap_surfaces_structured(
        self, tmp_path: Path
    ) -> None:
        """Ship a manifest declaring an adapter but missing some
        capabilities the workflow requires; integration test observes
        a ``capability_gap`` CrossRefIssue.
        """
        # Hand-build a codex-stub manifest with a deliberately reduced
        # capability set (only read_repo, missing write_diff).
        adapters_dir = tmp_path / ".ao" / "adapters"
        adapters_dir.mkdir(parents=True)
        (adapters_dir / "codex-stub.manifest.v1.json").write_text(
            """
            {
              "adapter_id": "codex-stub",
              "adapter_kind": "codex-stub",
              "version": "0.1.0",
              "capabilities": ["read_repo"],
              "invocation": {
                "transport": "cli",
                "command": "true",
                "args": [],
                "env_allowlist_ref": "#/env_allowlist/allowed_keys",
                "cwd_policy": "per_run_worktree",
                "stdin_mode": "none"
              },
              "input_envelope": {
                "task_prompt": "x",
                "run_id": "00000000-0000-4000-8000-000000000005"
              },
              "output_envelope": {"status": "ok"},
              "policy_refs": [
                "ao_kernel/defaults/policies/policy_worktree_profile.v1.json"
              ],
              "evidence_refs": [
                ".ao/evidence/workflows/x/adapter-codex-stub.jsonl"
              ]
            }
            """.strip(),
            encoding="utf-8",
        )
        shutil.copy2(
            _FIXTURE_SRC / "gh-cli-pr.manifest.v1.json",
            adapters_dir / "gh-cli-pr.manifest.v1.json",
        )
        _, issues = _resolve(tmp_path, "please fix the crash")
        caps_gaps = [i for i in issues if i.kind == "capability_gap"]
        assert caps_gaps, f"expected capability_gap, got {issues}"
        assert any(
            "write_diff" in g.missing_capabilities for g in caps_gaps
        )


# ---------------------------------------------------------------------------
# No-match scenario
# ---------------------------------------------------------------------------


class TestNoMatch:
    def test_unrelated_intent_returns_none_from_router(
        self, tmp_path: Path
    ) -> None:
        router = IntentRouter()
        result = router.classify("Completely unrelated philosophical musings")
        assert result is None
