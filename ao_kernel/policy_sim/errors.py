"""Typed error hierarchy for the policy simulation harness (PR-B4).

Each subclass carries the structured fields operators need to
distinguish root causes from the exception type alone. See
``docs/POLICY-SIM.md`` and PR-B4 plan v3 §2.7 for the full
semantic contract.
"""

from __future__ import annotations


class PolicySimError(Exception):
    """Base class for all policy-simulation runtime errors."""


class PolicySimSideEffectError(PolicySimError):
    """Raised when a simulation step triggers a forbidden side
    effect (evidence emit, worktree creation, subprocess spawn,
    filesystem write, network I/O, tempfile creation, or
    importlib resource extraction).

    The ``sentinel_name`` field identifies which guarded attribute
    was touched; ``context`` carries a short description of the
    call site (helpful for operator diagnosis).
    """

    def __init__(self, sentinel_name: str, context: str = "") -> None:
        self.sentinel_name = sentinel_name
        self.context = context
        suffix = f" ({context})" if context else ""
        super().__init__(
            f"policy-sim side-effect sentinel tripped: "
            f"{sentinel_name!r}{suffix}"
        )


class PolicySimReentrantError(PolicySimError):
    """Raised when ``pure_execution_context`` is entered while
    another instance is already active on the same thread.

    Nested entries cannot restore the outer context's patched
    sentinels on exit without leaking state, so the guard
    fail-closes rather than silently partial-restoring.
    """

    def __init__(self) -> None:
        super().__init__(
            "pure_execution_context is not re-entrant; nested "
            "entry would leak sentinel state on exit"
        )


class ScenarioValidationError(PolicySimError):
    """Raised when a scenario document fails schema validation.

    The ``scenario_id`` field echoes the offending scenario's id
    (or a synthetic fallback when the id itself is absent);
    ``reason`` carries the underlying validator message.
    """

    def __init__(self, scenario_id: str, reason: str) -> None:
        self.scenario_id = scenario_id
        self.reason = reason
        super().__init__(
            f"scenario {scenario_id!r} failed validation: {reason}"
        )


class ScenarioAdapterMissingError(PolicySimError):
    """Raised when a scenario references an ``adapter_manifest_ref``
    that is absent from the pre-simulation adapter registry
    snapshot (neither bundled nor workspace override)."""

    def __init__(self, scenario_id: str, adapter_ref: str) -> None:
        self.scenario_id = scenario_id
        self.adapter_ref = adapter_ref
        super().__init__(
            f"scenario {scenario_id!r} references unknown adapter "
            f"{adapter_ref!r}; load_bundled() + load_workspace() "
            f"produced no matching manifest"
        )


class TargetPolicyNotFoundError(PolicySimError):
    """Raised when a scenario's ``target_policy_name`` is not
    present in ``proposed_policies`` nor ``baseline_overrides``
    nor in the bundled defaults.

    The per-scenario routing model (plan v3 bulgu 1 absorb) means
    each scenario names the policy it evaluates; this error
    surfaces configuration drift early rather than deep inside
    the loader.
    """

    def __init__(self, scenario_id: str, policy_name: str) -> None:
        self.scenario_id = scenario_id
        self.policy_name = policy_name
        super().__init__(
            f"scenario {scenario_id!r} targets policy "
            f"{policy_name!r} which is not available in "
            f"proposed_policies, baseline_overrides, or bundled "
            f"defaults"
        )


class ProposedPolicyInvalidError(PolicySimError):
    """Raised when a proposed policy dict fails the structural
    shape checks mirrored from the consuming primitive (per the
    ``_policy_shape_registry``).

    The ``violations`` field is a sequence of structured records
    (``(path, expected, observed)`` tuples rendered as strings)
    so operators see every violation in one pass.
    """

    def __init__(
        self,
        policy_name: str,
        violations: tuple[str, ...],
    ) -> None:
        self.policy_name = policy_name
        self.violations = violations
        joined = "; ".join(violations) if violations else "(no detail)"
        super().__init__(
            f"proposed policy {policy_name!r} failed structural "
            f"shape checks: {joined}"
        )


class SimulationAbortedError(PolicySimError):
    """Aggregate wrapper raised when per-scenario evaluation
    produced one or more unrecoverable errors the harness chose
    to surface in one exception rather than bubbling them
    individually.

    ``causes`` is the ordered list of underlying exceptions; the
    first is set as ``__cause__`` so ``raise ... from ...``
    semantics still work for drill-down.
    """

    def __init__(
        self,
        scenario_ids: tuple[str, ...],
        causes: tuple[BaseException, ...],
    ) -> None:
        self.scenario_ids = scenario_ids
        self.causes = causes
        super().__init__(
            f"simulation aborted on scenarios {list(scenario_ids)!r}: "
            f"{len(causes)} underlying error(s)"
        )
        if causes:
            self.__cause__ = causes[0]


class ReportSerializationError(PolicySimError):
    """Raised when the reporter cannot JSON-encode a value
    produced by the simulator (typically a ``Path``, ``Decimal``,
    regex pattern, or frozenset that escaped
    ``DiffReport.to_dict`` normalisation).

    Surfaces with the offending type name + an operator-readable
    hint pointing at the normalisation contract.
    """

    def __init__(self, field_path: str, value_type: str) -> None:
        self.field_path = field_path
        self.value_type = value_type
        super().__init__(
            f"report field {field_path!r} holds non-JSON "
            f"serialisable type {value_type!r}; extend "
            f"DiffReport.to_dict normalisation"
        )


__all__ = [
    "PolicySimError",
    "PolicySimSideEffectError",
    "PolicySimReentrantError",
    "ScenarioValidationError",
    "ScenarioAdapterMissingError",
    "TargetPolicyNotFoundError",
    "ProposedPolicyInvalidError",
    "SimulationAbortedError",
    "ReportSerializationError",
]
