"""CLI handler for ``ao-kernel policy-sim run`` (PR-B4 C4).

Plan v3 §2.8 exit codes:

- ``0`` — success, no tightening transitions
- ``1`` — user error (bad scenario file, missing adapter,
  structurally invalid proposed policy, target policy absent)
- ``2`` — internal error (purity violation, reentrancy, other
  simulator abort)
- ``3`` — success with warning (≥1 allow→deny transition)
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Literal, Mapping, Sequence, cast

from ao_kernel.policy_sim.errors import (
    PolicySimReentrantError,
    PolicySimSideEffectError,
    ProposedPolicyInvalidError,
    ScenarioAdapterMissingError,
    ScenarioValidationError,
    SimulationAbortedError,
    TargetPolicyNotFoundError,
)
from ao_kernel.policy_sim.loader import BaselineSource
from ao_kernel.policy_sim.report import (
    has_tightening,
    load_policies_from_dir,
    render,
    write_atomic,
)
from ao_kernel.policy_sim.scenario import (
    Scenario,
    load_bundled_scenarios,
    load_scenario_file,
    load_scenarios_from_dir,
)
from ao_kernel.policy_sim.simulator import simulate_policy_change


_EXIT_OK = 0
_EXIT_USER_ERROR = 1
_EXIT_INTERNAL = 2
_EXIT_TIGHTENING = 3


def cmd_policy_sim_run(args: argparse.Namespace) -> int:
    try:
        scenarios = _resolve_scenarios(args.scenarios)
    except (ScenarioValidationError, FileNotFoundError) as exc:
        print(f"scenario load failed: {exc}", file=sys.stderr)
        return _EXIT_USER_ERROR

    # PR-C5: exactly one of --proposed-policies | --proposed-patches
    # is supplied (parser enforces the mutex). Handler branches once.
    proposed: Mapping[str, Mapping[str, Any]] | None = None
    proposed_patches: Mapping[str, Mapping[str, Any]] | None = None
    if getattr(args, "proposed_policies", None) is not None:
        try:
            proposed = load_policies_from_dir(Path(args.proposed_policies))
        except json.JSONDecodeError as exc:
            print(
                f"invalid JSON in --proposed-policies: {exc}",
                file=sys.stderr,
            )
            return _EXIT_USER_ERROR
    elif getattr(args, "proposed_patches", None) is not None:
        from ao_kernel.policy_sim.merge_patch import (
            load_policy_patches_from_dir,
        )

        try:
            proposed_patches = load_policy_patches_from_dir(
                Path(args.proposed_patches)
            )
        except (FileNotFoundError, json.JSONDecodeError, TypeError) as exc:
            print(
                f"invalid patches directory: {exc}",
                file=sys.stderr,
            )
            return _EXIT_USER_ERROR

    baseline_source_value = getattr(args, "baseline_source", "bundled")
    try:
        baseline_source = BaselineSource(baseline_source_value)
    except ValueError:
        print(
            f"unknown --baseline-source {baseline_source_value!r}; "
            f"expected one of: bundled, workspace_override, explicit",
            file=sys.stderr,
        )
        return _EXIT_USER_ERROR

    baseline_overrides = None
    if (
        baseline_source is BaselineSource.EXPLICIT
        and getattr(args, "baseline_overrides", None)
    ):
        try:
            baseline_overrides = load_policies_from_dir(
                Path(args.baseline_overrides)
            )
        except json.JSONDecodeError as exc:
            print(
                f"invalid JSON in --baseline-overrides: {exc}",
                file=sys.stderr,
            )
            return _EXIT_USER_ERROR

    project_root = Path(args.project_root or Path.cwd()).resolve()

    try:
        report = simulate_policy_change(
            project_root=project_root,
            scenarios=scenarios,
            proposed_policies=proposed,
            proposed_policy_patches=proposed_patches,
            baseline_source=baseline_source,
            baseline_overrides=baseline_overrides,
            include_host_fs_probes=bool(
                getattr(args, "enable_host_fs_probes", False)
            ),
        )
    except (
        ProposedPolicyInvalidError,
        ScenarioAdapterMissingError,
        TargetPolicyNotFoundError,
    ) as exc:
        print(f"simulation input error: {exc}", file=sys.stderr)
        return _EXIT_USER_ERROR
    except (
        PolicySimSideEffectError,
        PolicySimReentrantError,
        SimulationAbortedError,
    ) as exc:
        print(f"simulation aborted: {exc}", file=sys.stderr)
        return _EXIT_INTERNAL

    fmt_raw = getattr(args, "format", "json")
    fmt = cast(Literal["json", "text"], fmt_raw)
    rendered = render(report, fmt)

    output_path = getattr(args, "output", None)
    if output_path:
        write_atomic(Path(output_path), rendered)
    else:
        sys.stdout.write(rendered)
        if not rendered.endswith("\n"):
            sys.stdout.write("\n")

    if has_tightening(report):
        return _EXIT_TIGHTENING
    return _EXIT_OK


def _resolve_scenarios(spec: str | None) -> Sequence[Scenario]:
    """Turn the ``--scenarios`` argument into a scenario list.

    - ``None`` → bundled fixtures (``load_bundled_scenarios``).
    - Directory path → load every ``*.json`` file inside.
    - File path → load that single file.
    """
    if not spec:
        return load_bundled_scenarios()
    path = Path(spec)
    if path.is_dir():
        return load_scenarios_from_dir(path)
    if path.is_file():
        return (load_scenario_file(path),)
    raise FileNotFoundError(f"scenarios path not found: {spec!r}")


__all__ = ["cmd_policy_sim_run"]
