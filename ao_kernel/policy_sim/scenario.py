"""Scenario model for the policy simulation harness (PR-B4 C2).

Scenarios are JSON documents (plan v3 Q1 absorb — JSON-only v1)
describing an input pair (policy, inputs) and the expected
baseline decision. The simulator evaluates each scenario twice
per run — once under the baseline policy set, once under the
proposed policy set — and diffs the decisions.

Per-scenario ``target_policy_name`` (plan v3 bulgu 1 absorb) keeps
multi-policy ScenarioSets tractable: a single set may include
`executor_primitive` scenarios targeting
``policy_worktree_profile.v1.json`` alongside ``governance_policy``
scenarios targeting ``policy_autonomy.v1.json``, without forcing
operators to partition by policy.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal, Mapping

from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError as _JsonSchemaValidationError

from ao_kernel.config import load_default
from ao_kernel.policy_sim.errors import ScenarioValidationError


ScenarioKind = Literal["executor_primitive", "governance_policy", "combined"]


_SCENARIO_SCHEMA_CACHE: dict[str, Any] | None = None


def _scenario_schema() -> dict[str, Any]:
    global _SCENARIO_SCHEMA_CACHE
    if _SCENARIO_SCHEMA_CACHE is None:
        _SCENARIO_SCHEMA_CACHE = load_default(
            "schemas",
            "policy-sim-scenario.schema.v1.json",
        )
    return _SCENARIO_SCHEMA_CACHE


@dataclass(frozen=True)
class ExpectedBaseline:
    """Expected baseline decision + violation list for a scenario."""

    decision_expected: Literal["allow", "deny"]
    violations_expected: tuple[str, ...] = ()


@dataclass(frozen=True)
class ScenarioInputs:
    """Inputs presented to the primitive(s) a scenario exercises.

    Fields mirror ``policy-sim-scenario.schema.v1.json::inputs`` one
    to one. ``adapter_manifest_ref`` resolves against the
    pre-simulation AdapterRegistry snapshot; ``action`` is the
    string passed to ``governance.check_policy`` for
    ``governance_policy`` scenarios.
    """

    adapter_manifest_ref: str | None = None
    parent_env: Mapping[str, str] = field(default_factory=dict)
    requested_command: str | None = None
    requested_cwd: str | None = None
    action: str | None = None


@dataclass(frozen=True)
class Scenario:
    """A single policy-simulation scenario.

    ``target_policy_name`` is set for ``executor_primitive`` and
    ``governance_policy`` kinds; ``target_policy_names`` is a
    non-empty tuple for ``combined`` kind. The scenario schema
    enforces the xor via ``allOf`` branches.
    """

    scenario_id: str
    kind: ScenarioKind
    inputs: ScenarioInputs
    expected_baseline: ExpectedBaseline
    description: str = ""
    target_policy_name: str | None = None
    target_policy_names: tuple[str, ...] = ()


@dataclass(frozen=True)
class ScenarioSet:
    """An ordered collection of scenarios loaded from disk or
    bundled defaults. ``name`` / ``version`` / ``description``
    are informational only."""

    scenarios: tuple[Scenario, ...]
    name: str = "default"
    version: str = "v1"
    description: str = ""


def _from_dict(doc: Mapping[str, Any]) -> Scenario:
    inputs_raw: Mapping[str, Any] = doc.get("inputs") or {}
    inputs = ScenarioInputs(
        adapter_manifest_ref=inputs_raw.get("adapter_manifest_ref"),
        parent_env=dict(inputs_raw.get("parent_env") or {}),
        requested_command=inputs_raw.get("requested_command"),
        requested_cwd=inputs_raw.get("requested_cwd"),
        action=inputs_raw.get("action"),
    )
    expected_raw = doc["expected_baseline"]
    expected = ExpectedBaseline(
        decision_expected=expected_raw["decision_expected"],
        violations_expected=tuple(expected_raw.get("violations_expected", [])),
    )
    return Scenario(
        scenario_id=doc["scenario_id"],
        kind=doc["kind"],
        inputs=inputs,
        expected_baseline=expected,
        description=doc.get("description", ""),
        target_policy_name=doc.get("target_policy_name"),
        target_policy_names=tuple(doc.get("target_policy_names", [])),
    )


def _validate(doc: Mapping[str, Any]) -> None:
    Draft202012Validator(_scenario_schema()).validate(doc)


def _load_scenario_dict(doc: Mapping[str, Any]) -> Scenario:
    scenario_id = str(doc.get("scenario_id", "<no-id>"))
    try:
        _validate(doc)
    except _JsonSchemaValidationError as exc:
        raise ScenarioValidationError(
            scenario_id=scenario_id,
            reason=exc.message,
        ) from exc
    return _from_dict(doc)


def load_scenario_file(path: Path) -> Scenario:
    """Load + validate a single scenario file.

    v1 is JSON-only (plan v3 Q1 absorb): any non-``.json`` suffix
    raises :class:`ScenarioValidationError` without opening the
    file. YAML support is deferred to a post-B4 optional extra.
    """
    suffix = path.suffix.lower()
    if suffix != ".json":
        raise ScenarioValidationError(
            scenario_id=path.stem,
            reason=f"unsupported scenario extension {suffix!r}; v1 is JSON-only",
        )
    with path.open("r", encoding="utf-8") as fh:
        doc: Mapping[str, Any] = json.load(fh)
    return _load_scenario_dict(doc)


def load_scenarios_from_dir(directory: Path) -> tuple[Scenario, ...]:
    """Load every scenario file under ``directory`` (sorted).

    Non-JSON extensions are rejected by :func:`load_scenario_file`
    per the JSON-only invariant (plan v3 Q1 absorb). Dotfiles
    (``.DS_Store`` etc.) are silently skipped. Every remaining
    entry must therefore be a ``.json`` scenario document.
    """
    scenarios: list[Scenario] = []
    for path in sorted(directory.iterdir()):
        if not path.is_file():
            continue
        if path.name.startswith("."):
            continue
        scenarios.append(load_scenario_file(path))
    return tuple(scenarios)


def load_bundled_scenarios() -> tuple[Scenario, ...]:
    """Load the three reference scenarios shipped under
    ``ao_kernel/defaults/policies/policy_sim_scenarios/``.

    Used by the bundled-fixture regression test and by the CLI
    when no ``--scenarios`` flag is supplied.
    """
    manifest = load_default(
        "policies/policy_sim_scenarios",
        "__manifest__.v1.json",
    )
    scenarios: list[Scenario] = []
    for entry in manifest["scenarios"]:
        loaded = load_default(
            "policies/policy_sim_scenarios",
            entry,
        )
        scenarios.append(_load_scenario_dict(loaded))
    return tuple(sorted(scenarios, key=lambda s: s.scenario_id))


__all__ = [
    "ExpectedBaseline",
    "Scenario",
    "ScenarioInputs",
    "ScenarioKind",
    "ScenarioSet",
    "load_bundled_scenarios",
    "load_scenario_file",
    "load_scenarios_from_dir",
]
