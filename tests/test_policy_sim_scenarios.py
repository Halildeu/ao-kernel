"""Tests for ``ao_kernel.policy_sim.scenario`` — scenario model +
loader + bundled JSON fixtures (PR-B4 C2)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from ao_kernel.policy_sim.errors import ScenarioValidationError
from ao_kernel.policy_sim.scenario import (
    ExpectedBaseline,
    Scenario,
    ScenarioInputs,
    ScenarioSet,
    load_bundled_scenarios,
    load_scenario_file,
    load_scenarios_from_dir,
)


def _valid_scenario(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "scenario_id": "valid_scenario",
        "kind": "executor_primitive",
        "target_policy_name": "policy_worktree_profile.v1.json",
        "inputs": {
            "adapter_manifest_ref": "codex-stub",
            "parent_env": {"PATH": "/usr/bin"},
            "requested_command": None,
            "requested_cwd": None,
        },
        "expected_baseline": {
            "violations_expected": [],
            "decision_expected": "allow",
        },
    }
    base.update(overrides)
    return base


class TestBundledScenarios:
    def test_all_three_load_clean(self) -> None:
        scenarios = load_bundled_scenarios()
        ids = {s.scenario_id for s in scenarios}
        assert ids == {
            "adapter_http_with_secret",
            "autonomy_unknown_intent",
            "path_poisoned_python",
        }

    def test_targets_point_at_expected_policies(self) -> None:
        scenarios = {s.scenario_id: s for s in load_bundled_scenarios()}
        assert (
            scenarios["adapter_http_with_secret"].target_policy_name
            == "policy_worktree_profile.v1.json"
        )
        assert (
            scenarios["path_poisoned_python"].target_policy_name
            == "policy_worktree_profile.v1.json"
        )
        assert (
            scenarios["autonomy_unknown_intent"].target_policy_name
            == "policy_autonomy.v1.json"
        )

    def test_decisions_match_expected_shape(self) -> None:
        scenarios = {s.scenario_id: s for s in load_bundled_scenarios()}
        assert (
            scenarios["adapter_http_with_secret"]
            .expected_baseline.decision_expected
            == "allow"
        )
        assert (
            scenarios["path_poisoned_python"]
            .expected_baseline.decision_expected
            == "deny"
        )
        assert (
            scenarios["autonomy_unknown_intent"]
            .expected_baseline.decision_expected
            == "deny"
        )


class TestLoadScenarioFile:
    def _write(self, path: Path, doc: Any) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(doc), encoding="utf-8")

    def test_loads_valid_file(self, tmp_path: Path) -> None:
        target = tmp_path / "x.json"
        self._write(target, _valid_scenario())
        scenario = load_scenario_file(target)
        assert scenario.scenario_id == "valid_scenario"
        assert scenario.kind == "executor_primitive"
        assert scenario.target_policy_name == "policy_worktree_profile.v1.json"

    def test_rejects_non_json_extension(self, tmp_path: Path) -> None:
        target = tmp_path / "x.yaml"
        target.write_text("scenario_id: x\n", encoding="utf-8")
        with pytest.raises(ScenarioValidationError) as exc_info:
            load_scenario_file(target)
        assert "JSON-only" in exc_info.value.reason

    def test_unknown_kind_raises(self, tmp_path: Path) -> None:
        bad = _valid_scenario(kind="weirdo")
        target = tmp_path / "x.json"
        self._write(target, bad)
        with pytest.raises(ScenarioValidationError):
            load_scenario_file(target)

    def test_missing_target_policy_for_executor_primitive(
        self, tmp_path: Path
    ) -> None:
        bad = _valid_scenario()
        del bad["target_policy_name"]
        target = tmp_path / "x.json"
        self._write(target, bad)
        with pytest.raises(ScenarioValidationError):
            load_scenario_file(target)

    def test_both_target_fields_rejected(self, tmp_path: Path) -> None:
        """Schema xor: can't provide both name and names."""
        bad = _valid_scenario(
            target_policy_names=["policy_worktree_profile.v1.json"],
        )
        target = tmp_path / "x.json"
        self._write(target, bad)
        with pytest.raises(ScenarioValidationError):
            load_scenario_file(target)

    def test_combined_without_target_names_rejected(
        self, tmp_path: Path
    ) -> None:
        bad = _valid_scenario(kind="combined")
        del bad["target_policy_name"]
        target = tmp_path / "x.json"
        self._write(target, bad)
        with pytest.raises(ScenarioValidationError):
            load_scenario_file(target)

    def test_invalid_scenario_id_pattern(self, tmp_path: Path) -> None:
        bad = _valid_scenario(scenario_id="Bad-ID-With-Caps")
        target = tmp_path / "x.json"
        self._write(target, bad)
        with pytest.raises(ScenarioValidationError):
            load_scenario_file(target)

    def test_invalid_decision_expected_enum(self, tmp_path: Path) -> None:
        bad = _valid_scenario()
        bad["expected_baseline"]["decision_expected"] = "maybe"
        target = tmp_path / "x.json"
        self._write(target, bad)
        with pytest.raises(ScenarioValidationError):
            load_scenario_file(target)

    def test_additional_properties_rejected(self, tmp_path: Path) -> None:
        bad = _valid_scenario(unknown_field="extra")
        target = tmp_path / "x.json"
        self._write(target, bad)
        with pytest.raises(ScenarioValidationError):
            load_scenario_file(target)


class TestLoadScenariosFromDir:
    def test_loads_sorted(self, tmp_path: Path) -> None:
        for sid in ("zebra", "alpha", "mango"):
            doc = _valid_scenario(scenario_id=sid)
            (tmp_path / f"{sid}.json").write_text(
                json.dumps(doc), encoding="utf-8"
            )
        scenarios = load_scenarios_from_dir(tmp_path)
        assert [s.scenario_id for s in scenarios] == ["alpha", "mango", "zebra"]

    def test_empty_dir_returns_empty(self, tmp_path: Path) -> None:
        assert load_scenarios_from_dir(tmp_path) == ()


class TestScenarioModel:
    def test_frozen_dataclasses(self) -> None:
        inputs = ScenarioInputs(adapter_manifest_ref="codex-stub")
        with pytest.raises(Exception):  # FrozenInstanceError
            inputs.adapter_manifest_ref = "other"  # type: ignore[misc]

        expected = ExpectedBaseline(decision_expected="allow")
        with pytest.raises(Exception):
            expected.decision_expected = "deny"  # type: ignore[misc]

        scenario = Scenario(
            scenario_id="x",
            kind="executor_primitive",
            inputs=inputs,
            expected_baseline=expected,
        )
        with pytest.raises(Exception):
            scenario.scenario_id = "y"  # type: ignore[misc]

        scenario_set = ScenarioSet(scenarios=(scenario,))
        assert scenario_set.name == "default"
        assert scenario_set.version == "v1"
        with pytest.raises(Exception):
            scenario_set.name = "other"  # type: ignore[misc]

    def test_default_governance_policy_action_optional(
        self, tmp_path: Path
    ) -> None:
        """governance_policy scenarios can omit adapter_manifest_ref
        (set to null) and still validate."""
        doc = _valid_scenario(
            scenario_id="gov_no_adapter",
            kind="governance_policy",
            target_policy_name="policy_autonomy.v1.json",
            inputs={
                "adapter_manifest_ref": None,
                "parent_env": {},
                "requested_command": None,
                "requested_cwd": None,
                "action": "SOME_ACTION",
            },
            expected_baseline={
                "violations_expected": [],
                "decision_expected": "allow",
            },
        )
        target = tmp_path / "x.json"
        target.write_text(json.dumps(doc), encoding="utf-8")
        scenario = load_scenario_file(target)
        assert scenario.inputs.adapter_manifest_ref is None
        assert scenario.inputs.action == "SOME_ACTION"
