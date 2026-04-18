"""Policy simulation harness (PR-B4).

Public package for dry-run evaluation of proposed policy changes
against scenario fixtures. Mid-depth simulator reusing
``governance.check_policy`` + executor policy primitives under a
side-effect-free contract (no workspace writes, no evidence emits,
no subprocess spawns, no network).

See ``docs/POLICY-SIM.md`` for the operator-facing contract and
``.claude/plans/PR-B4-DRAFT-PLAN.md`` v3 for the adversarially-
reviewed design.

Public surface is built up across the commit DAG:

- **Commit 1** (this file's initial state): typed errors,
  purity contract, policy shape registry, scenario schema.
- **Commit 2**: scenario model + bundled JSON samples.
- **Commit 3**: simulator core + diff engine + loader.
- **Commit 4**: reporter + CLI handler.
- **Commit 5**: public surface + docs + integration tests.
"""

from __future__ import annotations

from ao_kernel.policy_sim.errors import (
    PolicySimError,
    PolicySimReentrantError,
    PolicySimSideEffectError,
    ProposedPolicyInvalidError,
    ReportSerializationError,
    ScenarioAdapterMissingError,
    ScenarioValidationError,
    SimulationAbortedError,
    TargetPolicyNotFoundError,
)
from ao_kernel.policy_sim.diff import (
    DiffReport,
    ScenarioDelta,
    SimulationResult,
    TransitionKind,
    ViolationDiff,
    canonical_policy_hash,
    dump_json,
)
from ao_kernel.policy_sim.loader import (
    BaselineSource,
    policy_override_context,
    validate_proposed_policy,
)
from ao_kernel.policy_sim.scenario import (
    ExpectedBaseline,
    Scenario,
    ScenarioInputs,
    ScenarioKind,
    ScenarioSet,
    load_bundled_scenarios,
    load_scenario_file,
    load_scenarios_from_dir,
)
from ao_kernel.policy_sim.simulator import simulate_policy_change


__all__ = [
    # Errors
    "PolicySimError",
    "PolicySimReentrantError",
    "PolicySimSideEffectError",
    "ProposedPolicyInvalidError",
    "ReportSerializationError",
    "ScenarioAdapterMissingError",
    "ScenarioValidationError",
    "SimulationAbortedError",
    "TargetPolicyNotFoundError",
    # Scenario model
    "ExpectedBaseline",
    "Scenario",
    "ScenarioInputs",
    "ScenarioKind",
    "ScenarioSet",
    "load_bundled_scenarios",
    "load_scenario_file",
    "load_scenarios_from_dir",
    # Simulator + diff + loader (C3)
    "BaselineSource",
    "DiffReport",
    "ScenarioDelta",
    "SimulationResult",
    "TransitionKind",
    "ViolationDiff",
    "canonical_policy_hash",
    "dump_json",
    "policy_override_context",
    "simulate_policy_change",
    "validate_proposed_policy",
]
