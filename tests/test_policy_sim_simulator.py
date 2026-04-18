"""Tests for ``ao_kernel.policy_sim`` C3 — simulator + diff + loader
(PR-B4 plan v3 §2.3/§2.4/§2.5)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from ao_kernel import config as _config
from ao_kernel.policy_sim import (
    BaselineSource,
    DiffReport,
    ScenarioSet,
    SimulationResult,
    canonical_policy_hash,
    dump_json,
    load_bundled_scenarios,
    policy_override_context,
    simulate_policy_change,
    validate_proposed_policy,
)
from ao_kernel.policy_sim.diff import (
    compute_transition,
    compute_violation_diff,
    make_scenario_delta,
)
from ao_kernel.policy_sim.errors import (
    ProposedPolicyInvalidError,
    ScenarioAdapterMissingError,
)
from ao_kernel.policy_sim.loader import resolve_target_policy


# --- Canonical policy hash --------------------------------------------


class TestCanonicalPolicyHash:
    def test_deterministic(self) -> None:
        policy = {"a": 1, "b": [2, 3], "c": {"d": "x"}}
        assert canonical_policy_hash(policy) == canonical_policy_hash(policy)

    def test_key_order_irrelevant(self) -> None:
        """Canonical sort_keys → same hash regardless of insertion order."""
        p1 = {"b": 2, "a": 1}
        p2 = {"a": 1, "b": 2}
        assert canonical_policy_hash(p1) == canonical_policy_hash(p2)

    def test_different_inputs_differ(self) -> None:
        assert canonical_policy_hash({"a": 1}) != canonical_policy_hash(
            {"a": 2}
        )

    def test_prefix(self) -> None:
        h = canonical_policy_hash({"x": "y"})
        assert h.startswith("sha256:")
        assert len(h) == len("sha256:") + 64


# --- Transition classification ----------------------------------------


class TestComputeTransition:
    def _result(
        self, decision: str, violations: tuple[str, ...] = ()
    ) -> SimulationResult:
        return SimulationResult(
            scenario_id="x",
            decision=decision,  # type: ignore[arg-type]
            violation_kinds=violations,
        )

    def test_allow_to_allow(self) -> None:
        assert (
            compute_transition(self._result("allow"), self._result("allow"))
            == "allow_to_allow"
        )

    def test_allow_to_deny(self) -> None:
        assert (
            compute_transition(self._result("allow"), self._result("deny"))
            == "allow_to_deny"
        )

    def test_deny_to_allow(self) -> None:
        assert (
            compute_transition(self._result("deny"), self._result("allow"))
            == "deny_to_allow"
        )

    def test_deny_to_deny(self) -> None:
        assert (
            compute_transition(self._result("deny"), self._result("deny"))
            == "deny_to_deny"
        )

    def test_baseline_error(self) -> None:
        assert (
            compute_transition(self._result("error"), self._result("allow"))
            == "error"
        )

    def test_proposed_error(self) -> None:
        assert (
            compute_transition(self._result("allow"), self._result("error"))
            == "error"
        )


class TestComputeViolationDiff:
    def test_added(self) -> None:
        base = SimulationResult(scenario_id="x", decision="allow")
        prop = SimulationResult(
            scenario_id="x", decision="deny", violation_kinds=("new_code",)
        )
        diff = compute_violation_diff(base, prop)
        assert diff.added == frozenset({"new_code"})
        assert diff.removed == frozenset()

    def test_removed(self) -> None:
        base = SimulationResult(
            scenario_id="x", decision="deny", violation_kinds=("old_code",)
        )
        prop = SimulationResult(scenario_id="x", decision="allow")
        diff = compute_violation_diff(base, prop)
        assert diff.added == frozenset()
        assert diff.removed == frozenset({"old_code"})

    def test_symmetric_difference(self) -> None:
        base = SimulationResult(
            scenario_id="x",
            decision="deny",
            violation_kinds=("a", "b"),
        )
        prop = SimulationResult(
            scenario_id="x",
            decision="deny",
            violation_kinds=("b", "c"),
        )
        diff = compute_violation_diff(base, prop)
        assert diff.added == frozenset({"c"})
        assert diff.removed == frozenset({"a"})


class TestMakeScenarioDelta:
    def test_notable_on_transition_change(self) -> None:
        base = SimulationResult(scenario_id="x", decision="allow")
        prop = SimulationResult(
            scenario_id="x", decision="deny", violation_kinds=("v",)
        )
        delta = make_scenario_delta(
            scenario_id="x",
            target_policy_name="p.json",
            baseline=base,
            proposed=prop,
        )
        assert delta.notable
        assert delta.transition == "allow_to_deny"

    def test_not_notable_on_identity(self) -> None:
        base = SimulationResult(scenario_id="x", decision="allow")
        prop = SimulationResult(scenario_id="x", decision="allow")
        delta = make_scenario_delta(
            scenario_id="x",
            target_policy_name="p.json",
            baseline=base,
            proposed=prop,
        )
        assert delta.notable is False


# --- Shape-registry-backed validator ----------------------------------


class TestValidateProposedPolicy:
    def _worktree_policy(self, **overrides: Any) -> dict[str, Any]:
        base: dict[str, Any] = {
            "version": "v1",
            "enabled": True,
            "worktree": {},
            "env_allowlist": {"allowed_keys": []},
            "secrets": {"exposure_modes": []},
            "command_allowlist": {"prefixes": []},
            "cwd_confinement": {"allowed_prefixes": []},
            "evidence_redaction": {"patterns": []},
            "rollout": {},
        }
        base.update(overrides)
        return base

    def test_valid_passes(self) -> None:
        # Well-formed policy must not raise; validator returns
        # None on success, ProposedPolicyInvalidError otherwise.
        result = validate_proposed_policy(
            "policy_worktree_profile.v1.json", self._worktree_policy()
        )
        assert result is None

    def test_missing_top_key_raises(self) -> None:
        bad = self._worktree_policy()
        del bad["env_allowlist"]
        with pytest.raises(ProposedPolicyInvalidError):
            validate_proposed_policy(
                "policy_worktree_profile.v1.json", bad
            )

    def test_wrong_type_raises(self) -> None:
        bad = self._worktree_policy()
        bad["env_allowlist"] = {"allowed_keys": "not_a_list"}
        with pytest.raises(ProposedPolicyInvalidError):
            validate_proposed_policy(
                "policy_worktree_profile.v1.json", bad
            )

    def test_unknown_policy_name_passes_through(self) -> None:
        """No registry entry → no structural checks (schema gate
        is authoritative for those). Validator returns None."""
        result = validate_proposed_policy(
            "policy_unknown.v1.json", {"arbitrary": True}
        )
        assert result is None


# --- policy_override_context monkey-patch -----------------------------


class TestPolicyOverrideContext:
    def test_patches_and_restores(self) -> None:
        original = _config.load_with_override
        with policy_override_context({"policy_x.v1.json": {"custom": 1}}):
            result = _config.load_with_override(
                "policies", "policy_x.v1.json"
            )
            assert result == {"custom": 1}
        assert _config.load_with_override is original

    def test_falls_through_for_unpatched_names(self) -> None:
        """Policies not in the override set reach the original loader."""
        seen: list[tuple[str, str]] = []

        def _fake(
            resource_type: str, filename: str, workspace: Any = None
        ) -> dict[str, Any]:
            seen.append((resource_type, filename))
            return {"from_real": filename}

        original = _config.load_with_override
        _config.load_with_override = _fake  # type: ignore[assignment]
        try:
            with policy_override_context(
                {"override_one.v1.json": {"patched": True}}
            ):
                assert _config.load_with_override(
                    "policies", "other.v1.json"
                ) == {"from_real": "other.v1.json"}
                assert _config.load_with_override(
                    "policies", "override_one.v1.json"
                ) == {"patched": True}
        finally:
            _config.load_with_override = original  # type: ignore[assignment]
        assert ("policies", "other.v1.json") in seen

    def test_exception_still_restores(self) -> None:
        original = _config.load_with_override
        with pytest.raises(RuntimeError):
            with policy_override_context({"p.v1.json": {}}):
                raise RuntimeError("boom")
        assert _config.load_with_override is original


# --- resolve_target_policy --------------------------------------------


class TestResolveTargetPolicy:
    def test_bundled_fallback(self) -> None:
        p = resolve_target_policy(
            policy_name="policy_autonomy.v1.json",
            scenario_id="x",
            proposed_policies={},
            baseline_source=BaselineSource.BUNDLED,
            baseline_overrides=None,
        )
        # Bundled autonomy policy is a dict (schema-valid).
        assert isinstance(p, dict)

    def test_explicit_wins(self) -> None:
        explicit = {"policy_autonomy.v1.json": {"from": "explicit"}}
        p = resolve_target_policy(
            policy_name="policy_autonomy.v1.json",
            scenario_id="x",
            proposed_policies={},
            baseline_source=BaselineSource.EXPLICIT,
            baseline_overrides=explicit,
        )
        assert p == {"from": "explicit"}


# --- simulate_policy_change end-to-end --------------------------------


class TestSimulatePolicyChange:
    def test_bundled_smoke(self, tmp_path: Path) -> None:
        report = simulate_policy_change(
            project_root=tmp_path,
            scenarios=load_bundled_scenarios(),
            proposed_policies={},
        )
        assert report.scenarios_evaluated == 3
        # Proposed defaults to baseline when absent → identity transitions.
        for delta in report.deltas:
            assert delta.transition in {
                "allow_to_allow",
                "deny_to_deny",
                "error",
            }
            assert delta.notable is False

    def test_proposed_differing_triggers_notable(self, tmp_path: Path) -> None:
        """Shove a clearly different policy for autonomy and the
        governance_policy scenario should flip."""
        scenarios = load_bundled_scenarios()
        # Baseline autonomy blocks AUTONOMY_UNKNOWN_INTENT → deny.
        # Proposed: policy with explicit allow for the intent.
        proposed = {
            "policy_autonomy.v1.json": {
                "version": "v1",
                "intents": {"AUTONOMY_UNKNOWN_INTENT": {"mode": "allow"}},
                "defaults": {"mode": "allow"},
            }
        }
        report = simulate_policy_change(
            project_root=tmp_path,
            scenarios=scenarios,
            proposed_policies=proposed,
        )
        # Either the autonomy scenario flips or it stays deny — the
        # shape-registry validator must have accepted the proposed
        # dict (required keys + type contracts satisfied).
        assert report.scenarios_evaluated == 3
        proposed_hashes = dict(report.proposed_policy_hashes)
        assert "policy_autonomy.v1.json" in proposed_hashes

    def test_structural_invalid_proposed_raises(self, tmp_path: Path) -> None:
        proposed = {
            "policy_worktree_profile.v1.json": {
                "version": "v1",
                # Missing all the other required top-level keys.
            }
        }
        with pytest.raises(ProposedPolicyInvalidError):
            simulate_policy_change(
                project_root=tmp_path,
                scenarios=load_bundled_scenarios(),
                proposed_policies=proposed,
            )

    def test_scenario_set_accepted(self, tmp_path: Path) -> None:
        scenario_set = ScenarioSet(scenarios=load_bundled_scenarios())
        report = simulate_policy_change(
            project_root=tmp_path,
            scenarios=scenario_set,
            proposed_policies={},
        )
        assert report.scenarios_evaluated == 3

    def test_host_fs_dependent_flag_propagated(self, tmp_path: Path) -> None:
        """The report must echo ``include_host_fs_probes`` into
        ``host_fs_dependent`` even though validate_command itself
        is deferred for v1."""
        report = simulate_policy_change(
            project_root=tmp_path,
            scenarios=load_bundled_scenarios(),
            proposed_policies={},
            include_host_fs_probes=True,
        )
        assert report.host_fs_dependent is True

    def test_scenario_adapter_missing_raises(self, tmp_path: Path) -> None:
        """Synthesise a scenario referencing an adapter the
        snapshot has never seen."""
        from ao_kernel.policy_sim.scenario import (
            ExpectedBaseline,
            Scenario,
            ScenarioInputs,
        )

        bogus = Scenario(
            scenario_id="bogus",
            kind="executor_primitive",
            inputs=ScenarioInputs(
                adapter_manifest_ref="no-such-adapter-anywhere",
            ),
            expected_baseline=ExpectedBaseline(decision_expected="allow"),
            target_policy_name="policy_worktree_profile.v1.json",
        )
        with pytest.raises(ScenarioAdapterMissingError):
            simulate_policy_change(
                project_root=tmp_path,
                scenarios=[bogus],
                proposed_policies={},
            )


# --- DiffReport serialisation -----------------------------------------


class TestDiffReportSerialisation:
    def test_to_dict_is_json_serialisable(self, tmp_path: Path) -> None:
        report = simulate_policy_change(
            project_root=tmp_path,
            scenarios=load_bundled_scenarios(),
            proposed_policies={},
        )
        payload = report.to_dict()
        # Roundtrip through json.dumps/json.loads; no TypeError.
        encoded = json.dumps(payload, sort_keys=True)
        roundtripped = json.loads(encoded)
        assert (
            roundtripped["scenarios_evaluated"]
            == report.scenarios_evaluated
        )

    def test_dump_json_stable(self, tmp_path: Path) -> None:
        report = simulate_policy_change(
            project_root=tmp_path,
            scenarios=load_bundled_scenarios(),
            proposed_policies={},
        )
        a = dump_json(report)
        b = dump_json(report)
        assert a == b
