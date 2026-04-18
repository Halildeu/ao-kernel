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


__all__ = [
    "PolicySimError",
    "PolicySimReentrantError",
    "PolicySimSideEffectError",
    "ProposedPolicyInvalidError",
    "ReportSerializationError",
    "ScenarioAdapterMissingError",
    "ScenarioValidationError",
    "SimulationAbortedError",
    "TargetPolicyNotFoundError",
]
