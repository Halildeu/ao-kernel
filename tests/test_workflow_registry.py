"""Tests for ``ao_kernel.workflow.registry``.

Covers bundled + workspace load, precedence semantics, SemVer
comparator, LoadReport taxonomy (schema_invalid, json_decode,
duplicate_workflow_key, workspace_overrides_bundled, read_error),
cross-reference validation returning structured ``CrossRefIssue``
records, and pattern-drift regression between workflow-definition
and workflow-run schemas.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from ao_kernel.workflow import (
    CrossRefIssue,
    WorkflowDefinitionNotFoundError,
    WorkflowRegistry,
)
from ao_kernel.workflow.registry import _semver_sort_key


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _minimal_definition(
    *,
    workflow_id: str = "demo_flow",
    workflow_version: str = "1.0.0",
    expected_adapter_refs: list[str] | None = None,
    steps: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    return {
        "workflow_id": workflow_id,
        "workflow_version": workflow_version,
        "display_name": "Demo",
        "description": "Demo workflow for tests.",
        "steps": steps
        or [
            {
                "step_name": "run",
                "actor": "ao-kernel",
                "on_failure": "transition_to_failed",
            }
        ],
        "expected_adapter_refs": expected_adapter_refs or [],
        "default_policy_refs": [
            "ao_kernel/defaults/policies/policy_worktree_profile.v1.json"
        ],
        "created_at": "2026-04-15T00:00:00+00:00",
    }


def _write_workspace_definition(
    workspace_root: Path,
    payload: dict[str, Any],
    *,
    filename: str | None = None,
) -> Path:
    dir_path = workspace_root / ".ao" / "workflows"
    dir_path.mkdir(parents=True, exist_ok=True)
    name = filename or f"{payload['workflow_id']}.v1.json"
    out = dir_path / name
    out.write_text(json.dumps(payload), encoding="utf-8")
    return out


class _StubAdapterRegistry:
    """Duck-typed stand-in for AdapterRegistry used by cross-ref tests."""

    def __init__(self, manifests: dict[str, frozenset[str]]) -> None:
        self._manifests = manifests

    def get(self, adapter_id: str):  # noqa: ANN001 - duck typing OK for tests
        if adapter_id not in self._manifests:
            raise KeyError(adapter_id)
        return type("_Manifest", (), {"capabilities": self._manifests[adapter_id]})()

    def missing_capabilities(
        self, adapter_id: str, required
    ) -> frozenset[str]:
        caps = self._manifests[adapter_id]
        return frozenset(required) - caps


# ---------------------------------------------------------------------------
# Bundled load
# ---------------------------------------------------------------------------


class TestBundledLoad:
    def test_bundled_loads_bug_fix_flow(self) -> None:
        reg = WorkflowRegistry()
        rpt = reg.load_bundled()
        ids = {d.workflow_id for d in rpt.loaded}
        assert "bug_fix_flow" in ids

    def test_bundled_source_marked(self) -> None:
        reg = WorkflowRegistry()
        reg.load_bundled()
        defn = reg.get("bug_fix_flow")
        assert defn.source == "bundled"


# ---------------------------------------------------------------------------
# Workspace load + precedence
# ---------------------------------------------------------------------------


class TestWorkspaceLoad:
    def test_workspace_only(self, tmp_path: Path) -> None:
        _write_workspace_definition(tmp_path, _minimal_definition())
        reg = WorkflowRegistry()
        rpt = reg.load_workspace(tmp_path)
        assert len(rpt.loaded) == 1
        assert rpt.loaded[0].source == "workspace"

    def test_missing_workspace_dir_is_empty_report(self, tmp_path: Path) -> None:
        reg = WorkflowRegistry()
        rpt = reg.load_workspace(tmp_path)
        assert rpt.loaded == ()
        assert rpt.skipped == ()

    def test_workspace_overrides_bundled_same_key(self, tmp_path: Path) -> None:
        reg = WorkflowRegistry()
        reg.load_bundled()
        _write_workspace_definition(
            tmp_path,
            _minimal_definition(
                workflow_id="bug_fix_flow", workflow_version="1.0.0"
            ),
            filename="bug_fix_flow.v1.json",
        )
        rpt = reg.load_workspace(tmp_path)
        demoted = [s for s in rpt.skipped if s.reason == "workspace_overrides_bundled"]
        assert demoted, f"expected demotion, got skipped={rpt.skipped}"
        assert reg.get("bug_fix_flow").source == "workspace"

    def test_workspace_different_version_coexists(
        self, tmp_path: Path
    ) -> None:
        """workspace 0.9.0 and bundled 1.0.0 both load; highest SemVer wins."""
        _write_workspace_definition(
            tmp_path,
            _minimal_definition(
                workflow_id="bug_fix_flow", workflow_version="0.9.0"
            ),
            filename="bug_fix_flow_0_9.v1.json",
        )
        reg = WorkflowRegistry()
        reg.load_bundled()
        reg.load_workspace(tmp_path)
        versions = {d.workflow_version for d in reg.list_workflows() if d.workflow_id == "bug_fix_flow"}
        assert versions == {"0.9.0", "1.0.0"}
        # get() defaults to highest semver
        assert reg.get("bug_fix_flow").workflow_version == "1.0.0"

    def test_duplicate_workflow_key_same_source(self, tmp_path: Path) -> None:
        dir_path = tmp_path / ".ao" / "workflows"
        dir_path.mkdir(parents=True)
        payload = _minimal_definition(workflow_id="dup_flow")
        (dir_path / "a.v1.json").write_text(json.dumps(payload), encoding="utf-8")
        (dir_path / "b.v1.json").write_text(json.dumps(payload), encoding="utf-8")
        reg = WorkflowRegistry()
        rpt = reg.load_workspace(tmp_path)
        dup_reasons = [s.reason for s in rpt.skipped if s.reason == "duplicate_workflow_key"]
        assert len(dup_reasons) == 1


# ---------------------------------------------------------------------------
# Lookup + SemVer comparator
# ---------------------------------------------------------------------------


class TestLookup:
    def test_get_raises_for_unknown_id(self) -> None:
        reg = WorkflowRegistry()
        with pytest.raises(WorkflowDefinitionNotFoundError):
            reg.get("nonexistent_flow")

    def test_get_raises_for_unknown_version(self, tmp_path: Path) -> None:
        _write_workspace_definition(tmp_path, _minimal_definition())
        reg = WorkflowRegistry()
        reg.load_workspace(tmp_path)
        with pytest.raises(WorkflowDefinitionNotFoundError):
            reg.get("demo_flow", version="9.9.9")

    def test_get_explicit_version_returns_exact(self, tmp_path: Path) -> None:
        _write_workspace_definition(
            tmp_path,
            _minimal_definition(workflow_version="1.0.0"),
            filename="demo_1_0.v1.json",
        )
        _write_workspace_definition(
            tmp_path,
            _minimal_definition(workflow_version="1.1.0"),
            filename="demo_1_1.v1.json",
        )
        reg = WorkflowRegistry()
        reg.load_workspace(tmp_path)
        assert reg.get("demo_flow", version="1.0.0").workflow_version == "1.0.0"
        assert reg.get("demo_flow", version="1.1.0").workflow_version == "1.1.0"

    def test_list_workflows_is_sorted(self, tmp_path: Path) -> None:
        _write_workspace_definition(
            tmp_path,
            _minimal_definition(workflow_version="2.0.0"),
            filename="v2.v1.json",
        )
        _write_workspace_definition(
            tmp_path,
            _minimal_definition(workflow_version="1.0.0"),
            filename="v1.v1.json",
        )
        reg = WorkflowRegistry()
        reg.load_workspace(tmp_path)
        seq = [d.workflow_version for d in reg.list_workflows()]
        # Ascending SemVer within same id.
        assert seq == ["1.0.0", "2.0.0"]


class TestSemVerComparator:
    @pytest.mark.parametrize(
        "versions,expected",
        [
            (
                ["1.0.0", "1.0.0-rc.1", "1.0.0-alpha"],
                ["1.0.0-alpha", "1.0.0-rc.1", "1.0.0"],
            ),
            (["0.9.0", "1.0.0", "1.0.1"], ["0.9.0", "1.0.0", "1.0.1"]),
            (
                ["1.0.0-alpha.1", "1.0.0-alpha.2", "1.0.0-alpha.10"],
                ["1.0.0-alpha.1", "1.0.0-alpha.2", "1.0.0-alpha.10"],
            ),
        ],
    )
    def test_sort_matches_semver_ordering(
        self, versions: list[str], expected: list[str]
    ) -> None:
        assert sorted(versions, key=_semver_sort_key) == expected


# ---------------------------------------------------------------------------
# Corrupted input
# ---------------------------------------------------------------------------


class TestCorruptedInput:
    def test_json_decode_failure_skipped(self, tmp_path: Path) -> None:
        dir_path = tmp_path / ".ao" / "workflows"
        dir_path.mkdir(parents=True)
        (dir_path / "broken.v1.json").write_text("{ not json", encoding="utf-8")
        reg = WorkflowRegistry()
        rpt = reg.load_workspace(tmp_path)
        reasons = [s.reason for s in rpt.skipped]
        assert "json_decode" in reasons

    def test_schema_invalid_missing_required(self, tmp_path: Path) -> None:
        payload = _minimal_definition()
        del payload["description"]
        _write_workspace_definition(tmp_path, payload)
        reg = WorkflowRegistry()
        rpt = reg.load_workspace(tmp_path)
        reasons = [s.reason for s in rpt.skipped]
        assert "schema_invalid" in reasons

    def test_schema_rejects_unknown_top_level_field(self, tmp_path: Path) -> None:
        payload = _minimal_definition()
        payload["surprise_field"] = "not allowed"
        _write_workspace_definition(tmp_path, payload)
        reg = WorkflowRegistry()
        rpt = reg.load_workspace(tmp_path)
        reasons = [s.reason for s in rpt.skipped]
        assert "schema_invalid" in reasons

    def test_schema_rejects_unknown_step_field(self, tmp_path: Path) -> None:
        payload = _minimal_definition()
        payload["steps"][0]["stray"] = "nope"
        _write_workspace_definition(tmp_path, payload)
        reg = WorkflowRegistry()
        rpt = reg.load_workspace(tmp_path)
        reasons = [s.reason for s in rpt.skipped]
        assert "schema_invalid" in reasons

    def test_schema_rejects_unknown_on_failure_value(self, tmp_path: Path) -> None:
        payload = _minimal_definition()
        payload["steps"][0]["on_failure"] = "retry_with_backoff"
        _write_workspace_definition(tmp_path, payload)
        reg = WorkflowRegistry()
        rpt = reg.load_workspace(tmp_path)
        reasons = [s.reason for s in rpt.skipped]
        assert "schema_invalid" in reasons

    def test_schema_requires_adapter_id_when_actor_adapter(self, tmp_path: Path) -> None:
        payload = _minimal_definition(
            steps=[
                {
                    "step_name": "run",
                    "actor": "adapter",
                    "on_failure": "transition_to_failed",
                }
            ],
            expected_adapter_refs=["some-adapter"],
        )
        _write_workspace_definition(tmp_path, payload)
        reg = WorkflowRegistry()
        rpt = reg.load_workspace(tmp_path)
        reasons = [s.reason for s in rpt.skipped]
        assert "schema_invalid" in reasons


# ---------------------------------------------------------------------------
# Cross-reference validation (structured CrossRefIssue)
# ---------------------------------------------------------------------------


class TestCrossRefValidation:
    def test_happy_path_empty_issues(self) -> None:
        reg = WorkflowRegistry()
        reg.load_bundled()
        defn = reg.get("bug_fix_flow")
        stub = _StubAdapterRegistry({
            "codex-stub": frozenset({"read_repo", "write_diff"}),
            "gh-cli-pr": frozenset({"open_pr"}),
        })
        issues = reg.validate_cross_refs(defn, stub)
        assert issues == []

    def test_missing_adapter_reported(self) -> None:
        reg = WorkflowRegistry()
        reg.load_bundled()
        defn = reg.get("bug_fix_flow")
        stub = _StubAdapterRegistry({
            # codex-stub missing
            "gh-cli-pr": frozenset({"open_pr"}),
        })
        issues = reg.validate_cross_refs(defn, stub)
        kinds = {i.kind for i in issues}
        missing_ids = {i.adapter_id for i in issues if i.kind == "missing_adapter"}
        assert "missing_adapter" in kinds
        assert "codex-stub" in missing_ids

    def test_capability_gap_reported(self) -> None:
        reg = WorkflowRegistry()
        reg.load_bundled()
        defn = reg.get("bug_fix_flow")
        stub = _StubAdapterRegistry({
            "codex-stub": frozenset({"read_repo"}),  # missing write_diff
            "gh-cli-pr": frozenset({"open_pr"}),
        })
        issues = reg.validate_cross_refs(defn, stub)
        caps_gaps = [i for i in issues if i.kind == "capability_gap"]
        assert caps_gaps, f"expected capability_gap, got {issues}"
        gap = caps_gaps[0]
        assert "write_diff" in gap.missing_capabilities

    def test_cross_ref_issue_is_immutable_dataclass(self) -> None:
        issue = CrossRefIssue(
            kind="missing_adapter",
            workflow_id="x",
            step_name=None,
            adapter_id="y",
        )
        with pytest.raises(Exception):  # frozen dataclass
            issue.adapter_id = "z"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Drift regression: workflow-definition patterns ≡ workflow-run patterns
# ---------------------------------------------------------------------------


class TestPatternDriftGuard:
    def _load_schema(self, name: str) -> dict[str, Any]:
        from importlib import resources

        text = (
            resources.files("ao_kernel.defaults.schemas")
            .joinpath(name)
            .read_text(encoding="utf-8")
        )
        return json.loads(text)

    def test_workflow_id_pattern_matches_workflow_run(self) -> None:
        run_s = self._load_schema("workflow-run.schema.v1.json")
        def_s = self._load_schema("workflow-definition.schema.v1.json")
        assert (
            run_s["properties"]["workflow_id"]["pattern"]
            == def_s["properties"]["workflow_id"]["pattern"]
        )

    def test_workflow_version_pattern_matches_workflow_run(self) -> None:
        run_s = self._load_schema("workflow-run.schema.v1.json")
        def_s = self._load_schema("workflow-definition.schema.v1.json")
        assert (
            run_s["properties"]["workflow_version"]["pattern"]
            == def_s["properties"]["workflow_version"]["pattern"]
        )

    def test_capability_enum_matches_adapter_contract(self) -> None:
        contract_s = self._load_schema("agent-adapter-contract.schema.v1.json")
        def_s = self._load_schema("workflow-definition.schema.v1.json")
        assert (
            set(contract_s["$defs"]["capability_enum"]["enum"])
            == set(def_s["$defs"]["capability_enum"]["enum"])
        )

    def test_adapter_id_pattern_matches_adapter_contract(self) -> None:
        contract_s = self._load_schema("agent-adapter-contract.schema.v1.json")
        def_s = self._load_schema("workflow-definition.schema.v1.json")
        assert (
            contract_s["properties"]["adapter_id"]["pattern"]
            == def_s["properties"]["expected_adapter_refs"]["items"]["pattern"]
        )
