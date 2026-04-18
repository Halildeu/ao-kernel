"""Simulator core for the policy simulation harness (PR-B4 C3).

Public entrypoint :func:`simulate_policy_change` evaluates each
scenario against the baseline policy set AND the proposed policy
set under :func:`pure_execution_context`, returning a
:class:`DiffReport` that captures transitions plus per-policy
breakdowns.

Guiding invariants (plan v3 §2.3):

- No workspace writes, no evidence emits, no subprocess spawns,
  no network — the 23-sentinel purity guard fails closed on any
  accidental side effect.
- Adapter manifest resolution happens **before** entering the
  purity context so bundled adapters do not trip the
  ``importlib.resources.as_file`` sentinel.
- Baseline and proposed policies are pinned per-scenario via
  ``target_policy_name`` (plan v3 bulgu 1 absorb); a single
  ``ScenarioSet`` can exercise multiple policies in one run.
- ``check_policy`` invocations honor ``workspace=<sentinel>`` +
  :func:`policy_override_context` monkey-patch so proposed
  policies stream through :func:`load_with_override` without
  disk I/O (plan v3 warning 2 absorb).
"""

from __future__ import annotations

import datetime as _dt
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from ao_kernel.policy_sim._purity import pure_execution_context
from ao_kernel.policy_sim.diff import (
    DiffReport,
    ScenarioDelta,
    SimulationResult,
    aggregate_transition_counts,
    canonical_policy_hash,
    make_scenario_delta,
)
from ao_kernel.policy_sim.errors import (
    PolicySimReentrantError,
    PolicySimSideEffectError,
    ScenarioAdapterMissingError,
    TargetPolicyNotFoundError,
)
from ao_kernel.policy_sim.loader import (
    BaselineSource,
    policy_override_context,
    resolve_target_policy,
    validate_proposed_policy,
)
from ao_kernel.policy_sim.scenario import Scenario, ScenarioSet


_EPHEMERAL_WORKTREE = Path("/__policy_sim_ephemeral__")
_SENTINEL_WORKSPACE = Path("/__policy_sim_workspace_sentinel__")


def _snapshot_adapters(
    project_root: Path,
) -> Mapping[str, Any]:
    """Load bundled + workspace adapter manifests ahead of the
    purity context and return a lookup-only snapshot.

    ``importlib.resources.as_file`` is patched by the purity
    guard; running this call before entering the context is the
    sanctioned workaround (plan v3 §2.1 importlib note).
    """
    from ao_kernel.adapters import AdapterRegistry

    reg = AdapterRegistry()
    reg.load_bundled()
    try:
        reg.load_workspace(project_root)
    except Exception:
        # Workspace adapters are optional — absence is not fatal.
        pass

    snapshot: dict[str, Any] = {}
    for manifest in reg.list_adapters():
        snapshot[manifest.adapter_id] = manifest
    return snapshot


def _resolve_adapter_manifest(
    scenario: Scenario,
    adapter_snapshot: Mapping[str, Any],
) -> Any | None:
    """Look up the adapter manifest referenced by ``scenario``.

    Returns ``None`` when the scenario carries no adapter ref;
    raises :class:`ScenarioAdapterMissingError` when a ref is
    set but the snapshot has no entry.
    """
    ref = scenario.inputs.adapter_manifest_ref
    if ref is None:
        return None
    if ref not in adapter_snapshot:
        raise ScenarioAdapterMissingError(
            scenario_id=scenario.scenario_id,
            adapter_ref=ref,
        )
    return adapter_snapshot[ref]


def _run_executor_primitive(
    scenario: Scenario,
    policy: Mapping[str, Any],
    adapter_manifest: Any | None,
    include_host_fs_probes: bool,
) -> SimulationResult:
    """Evaluate ``build_sandbox`` + ``resolve_allowed_secrets``
    + ``check_http_header_exposure`` for ``scenario`` against
    ``policy`` (a ``policy_worktree_profile`` dict).

    Errors from the primitives are wrapped as ``decision="error"``
    results so the diff surface can still aggregate; full
    traceback goes into ``error_detail``.
    """
    try:
        from ao_kernel.executor import policy_enforcer

        resolved_secrets, sv_violations = _safe_resolve_secrets(
            policy_enforcer,
            policy,
            dict(scenario.inputs.parent_env),
        )
        sb_violations = _safe_build_sandbox(
            policy_enforcer,
            policy,
            dict(scenario.inputs.parent_env),
            resolved_secrets,
        )
        hh_violations = _safe_check_http_header(
            policy_enforcer,
            policy,
            adapter_manifest,
        )

        violations = list(sv_violations) + list(sb_violations) + list(
            hh_violations
        )

        # validate_command integration is deferred for simulator v1
        # (plan v3 §2.3 notes it requires the full sandbox + resolved
        # args wiring). host_fs_probes=True surfaces a fingerprint
        # on the report but does not yet add violations.
        _ = include_host_fs_probes
    except (PolicySimSideEffectError, PolicySimReentrantError):
        # Purity-guard violations are structural simulator bugs —
        # propagate so the CLI returns exit code 2 instead of
        # masking them as per-scenario errors.
        raise
    except Exception as exc:
        return SimulationResult(
            scenario_id=scenario.scenario_id,
            decision="error",
            error_detail=f"{type(exc).__name__}: {exc}",
        )

    decision = "deny" if violations else "allow"
    return SimulationResult(
        scenario_id=scenario.scenario_id,
        decision=decision,
        violation_kinds=tuple(violations),
    )


def _safe_resolve_secrets(
    enforcer: Any,
    policy: Mapping[str, Any],
    parent_env: Mapping[str, str],
) -> tuple[Mapping[str, str], Sequence[str]]:
    """Call ``resolve_allowed_secrets(policy, all_env)``. Returns
    ``(resolved_secrets_dict, violation_codes)``. Empty outputs on
    any signature mismatch so the simulator keeps running."""
    fn: Callable[..., Any] = getattr(enforcer, "resolve_allowed_secrets", None)
    if fn is None:
        return ({}, ())
    try:
        resolved, violations = fn(policy, parent_env)
    except TypeError:
        return ({}, ("resolve_allowed_secrets_signature_mismatch",))
    return (resolved, _violation_codes(violations))


def _safe_build_sandbox(
    enforcer: Any,
    policy: Mapping[str, Any],
    parent_env: Mapping[str, str],
    resolved_secrets: Mapping[str, str],
) -> Sequence[str]:
    fn: Callable[..., Any] = getattr(enforcer, "build_sandbox", None)
    if fn is None:
        return ()
    try:
        _sandbox, violations = fn(
            policy=policy,
            worktree_root=_EPHEMERAL_WORKTREE,
            resolved_secrets=resolved_secrets,
            parent_env=parent_env,
        )
    except TypeError:
        return ("build_sandbox_signature_mismatch",)
    return _violation_codes(violations)


def _safe_check_http_header(
    enforcer: Any,
    policy: Mapping[str, Any],
    adapter_manifest: Any | None,
) -> Sequence[str]:
    fn: Callable[..., Any] = getattr(enforcer, "check_http_header_exposure", None)
    if fn is None or adapter_manifest is None:
        return ()
    invocation = getattr(adapter_manifest, "invocation", None)
    if not isinstance(invocation, Mapping):
        return ()
    try:
        violations = fn(
            policy=policy,
            adapter_manifest_invocation=invocation,
        )
    except TypeError:
        return ()
    return _violation_codes(violations)


def _violation_codes(violations: Any) -> tuple[str, ...]:
    """Normalise primitive violations into tuple of string codes.

    Executor primitives return violation objects in a handful of
    shapes across the codebase; the simulator's job is to
    distil them to the canonical string kind. Missing / empty
    inputs degrade to an empty tuple.
    """
    if not violations:
        return ()
    codes: list[str] = []
    for violation in violations:
        if isinstance(violation, str):
            codes.append(violation)
            continue
        kind = getattr(violation, "kind", None)
        if isinstance(kind, str):
            codes.append(kind)
            continue
        if isinstance(violation, Mapping) and isinstance(
            violation.get("kind"), str
        ):
            codes.append(violation["kind"])
            continue
        codes.append(type(violation).__name__)
    return tuple(codes)


def _run_governance_policy(
    scenario: Scenario,
    target_policy_name: str,
) -> SimulationResult:
    """Evaluate ``governance.check_policy`` against the current
    (patched) policy source using the scenario's ``action``.

    The caller wraps this in :func:`policy_override_context` so
    that either baseline or proposed dicts flow through the
    loader.
    """
    from ao_kernel import governance

    action_str = scenario.inputs.action or ""
    action_dict: dict[str, Any] = (
        {"intent": action_str} if action_str else {}
    )
    try:
        result = governance.check_policy(
            target_policy_name,
            action_dict,
            workspace=_SENTINEL_WORKSPACE,
        )
    except (PolicySimSideEffectError, PolicySimReentrantError):
        # See _run_executor_primitive — propagate purity-guard
        # violations so the CLI can return exit code 2.
        raise
    except Exception as exc:
        return SimulationResult(
            scenario_id=scenario.scenario_id,
            decision="error",
            error_detail=f"{type(exc).__name__}: {exc}",
        )

    allowed = _extract_allowed_flag(result)
    violations = _extract_reason_codes(result)
    decision = "allow" if allowed else "deny"
    return SimulationResult(
        scenario_id=scenario.scenario_id,
        decision=decision,
        violation_kinds=violations,
    )


def _extract_allowed_flag(result: Any) -> bool:
    if isinstance(result, Mapping):
        if "allowed" in result:
            return bool(result["allowed"])
        if "decision" in result:
            return result["decision"] == "allow"
    return bool(result)


def _extract_reason_codes(result: Any) -> tuple[str, ...]:
    if not isinstance(result, Mapping):
        return ()
    codes_raw = result.get("reason_codes") or result.get("violations") or ()
    if isinstance(codes_raw, str):
        return (codes_raw,)
    codes: list[str] = []
    for code in codes_raw:
        if isinstance(code, str):
            codes.append(code)
    return tuple(codes)


def _evaluate_scenario(
    scenario: Scenario,
    *,
    target_policy_name: str,
    policy: Mapping[str, Any],
    adapter_manifest: Any | None,
    include_host_fs_probes: bool,
    active_policy_map: Mapping[str, Mapping[str, Any]],
) -> SimulationResult:
    """Dispatch a scenario to the right primitive path.

    ``active_policy_map`` is the full overlay (baseline or
    proposed) currently in effect; it's passed through to
    :func:`policy_override_context` so ``check_policy`` reads it
    from memory.
    """
    if scenario.kind == "executor_primitive":
        return _run_executor_primitive(
            scenario, policy, adapter_manifest, include_host_fs_probes
        )
    if scenario.kind == "governance_policy":
        with policy_override_context(active_policy_map):
            return _run_governance_policy(scenario, target_policy_name)

    # kind == "combined": distribute targets across the two
    # primitive kinds. Convention (plan v3 §2.3): names containing
    # 'worktree' → executor primitive target; any other name →
    # governance_policy target. Aggregate violations union.
    exec_target, gov_target = _split_combined_targets(scenario)
    exec_policy = (
        active_policy_map.get(exec_target, policy) if exec_target else None
    )
    exec_result = (
        _run_executor_primitive(
            scenario,
            exec_policy,
            adapter_manifest,
            include_host_fs_probes,
        )
        if exec_policy is not None
        else None
    )
    if gov_target:
        with policy_override_context(active_policy_map):
            gov_result = _run_governance_policy(scenario, gov_target)
    else:
        gov_result = None

    results = [r for r in (exec_result, gov_result) if r is not None]
    combined_violations: tuple[str, ...] = ()
    error_details = []
    any_error = False
    for r in results:
        combined_violations = combined_violations + tuple(r.violation_kinds)
        if r.decision == "error":
            any_error = True
            if r.error_detail:
                error_details.append(r.error_detail)
    if not results:
        decision = "error"
    elif any_error:
        decision = "error"
    elif combined_violations:
        decision = "deny"
    else:
        decision = "allow"
    return SimulationResult(
        scenario_id=scenario.scenario_id,
        decision=decision,  # type: ignore[arg-type]
        violation_kinds=combined_violations,
        error_detail="; ".join(error_details),
    )


def _split_combined_targets(scenario: Scenario) -> tuple[str, str]:
    """Distribute a ``combined`` scenario's ``target_policy_names``
    across the executor and governance primitive targets.

    Convention: names containing ``"worktree"`` route to the
    executor primitive; all other names route to
    ``governance.check_policy``. Missing side returns an empty
    string so ``_evaluate_scenario`` knows to skip that primitive.
    """
    exec_t = ""
    gov_t = ""
    for name in scenario.target_policy_names:
        if "worktree" in name:
            exec_t = name
        else:
            gov_t = name
    return exec_t, gov_t


def _policy_for_scenario(scenario: Scenario) -> str:
    """Return the single ``target_policy_name`` used to look up
    the policy dict. ``combined`` scenarios fall back to the
    first entry in ``target_policy_names``."""
    if scenario.target_policy_name is not None:
        return scenario.target_policy_name
    if scenario.target_policy_names:
        return scenario.target_policy_names[0]
    raise TargetPolicyNotFoundError(
        scenario_id=scenario.scenario_id,
        policy_name="<unspecified>",
    )


def simulate_policy_change(
    *,
    project_root: Path,
    scenarios: ScenarioSet | Sequence[Scenario],
    proposed_policies: Mapping[str, Mapping[str, Any]],
    baseline_source: BaselineSource = BaselineSource.BUNDLED,
    baseline_overrides: Mapping[str, Mapping[str, Any]] | None = None,
    include_host_fs_probes: bool = False,
) -> DiffReport:
    """Evaluate each scenario twice (baseline + proposed) under
    the purity contract and return a ``DiffReport``.

    See the module docstring and plan v3 §2.3 for the full
    contract. ``proposed_policies`` is validated against the
    shape registry before simulation begins; structurally-broken
    proposed policies raise :class:`ProposedPolicyInvalidError`
    before any scenario runs.
    """
    # Structural shape validation runs OUTSIDE the purity context
    # because it emits no I/O and we want fail-fast errors.
    for name, policy in proposed_policies.items():
        validate_proposed_policy(name, policy)

    if isinstance(scenarios, ScenarioSet):
        scenario_list = list(scenarios.scenarios)
    else:
        scenario_list = list(scenarios)

    adapter_snapshot = _snapshot_adapters(project_root)

    # Pre-resolve baseline + proposed policy dicts for every
    # scenario so we can hash + pass through on the hot path.
    baseline_map: dict[str, Mapping[str, Any]] = {}
    proposed_map: dict[str, Mapping[str, Any]] = {}
    adapter_manifests: dict[str, Any | None] = {}

    for scenario in scenario_list:
        policy_name = _policy_for_scenario(scenario)
        adapter_manifests[scenario.scenario_id] = _resolve_adapter_manifest(
            scenario, adapter_snapshot
        )
        if policy_name not in baseline_map:
            baseline_map[policy_name] = resolve_target_policy(
                policy_name=policy_name,
                scenario_id=scenario.scenario_id,
                project_root=project_root,
                proposed_policies=proposed_policies,
                baseline_source=baseline_source,
                baseline_overrides=baseline_overrides,
            )
        if policy_name not in proposed_map:
            proposed_map[policy_name] = dict(
                proposed_policies.get(policy_name)
                or baseline_map[policy_name]
            )

    deltas: list[ScenarioDelta] = []
    with pure_execution_context():
        for scenario in scenario_list:
            policy_name = _policy_for_scenario(scenario)
            baseline_policy = baseline_map[policy_name]
            proposed_policy = proposed_map[policy_name]

            baseline_result = _evaluate_scenario(
                scenario,
                target_policy_name=policy_name,
                policy=baseline_policy,
                adapter_manifest=adapter_manifests[scenario.scenario_id],
                include_host_fs_probes=include_host_fs_probes,
                active_policy_map=baseline_map,
            )
            proposed_result = _evaluate_scenario(
                scenario,
                target_policy_name=policy_name,
                policy=proposed_policy,
                adapter_manifest=adapter_manifests[scenario.scenario_id],
                include_host_fs_probes=include_host_fs_probes,
                active_policy_map=proposed_map,
            )
            deltas.append(
                make_scenario_delta(
                    scenario_id=scenario.scenario_id,
                    target_policy_name=policy_name,
                    baseline=baseline_result,
                    proposed=proposed_result,
                )
            )

    overall, by_policy = aggregate_transition_counts(deltas)
    baseline_hashes = {
        name: canonical_policy_hash(policy)
        for name, policy in baseline_map.items()
    }
    proposed_hashes = {
        name: canonical_policy_hash(policy)
        for name, policy in proposed_map.items()
    }

    return DiffReport(
        baseline_policy_hashes=baseline_hashes,
        proposed_policy_hashes=proposed_hashes,
        scenarios_evaluated=len(deltas),
        transitions=overall,
        transitions_by_policy=by_policy,
        deltas=tuple(deltas),
        emitted_at=_dt.datetime.now(tz=_dt.timezone.utc).isoformat(),
        host_fs_dependent=include_host_fs_probes,
    )


__all__ = [
    "simulate_policy_change",
]
