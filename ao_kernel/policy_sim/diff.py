"""Diff engine for the policy simulation harness (PR-B4 C3).

Pairs baseline + proposed ``SimulationResult`` per scenario into
a ``ScenarioDelta`` carrying the transition kind and violation
diff. Aggregates scenario deltas into a ``DiffReport`` with
per-policy breakdown and stable, canonicalised JSON output
(plan v3 N3 / N4 absorb).

All dataclasses are frozen; ``DiffReport.to_dict`` is the one
normalisation boundary between internal Python types (``Path``,
``frozenset``, compiled regex, manifest ``source_path``) and
the JSON-serialisable surface.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Literal, Mapping


TransitionKind = Literal[
    "allow_to_allow",
    "allow_to_deny",
    "deny_to_allow",
    "deny_to_deny",
    "error",
]


_TRANSITION_LABELS: Mapping[TransitionKind, str] = {
    "allow_to_allow": "allow→allow",
    "allow_to_deny": "allow→deny",
    "deny_to_allow": "deny→allow",
    "deny_to_deny": "deny→deny",
    "error": "error",
}


@dataclass(frozen=True)
class SimulationResult:
    """One primitive pass's decision + violations.

    ``violation_kinds`` is the ordered list of violation codes
    surfaced; ``decision`` is ``"allow"`` when ``violation_kinds``
    is empty, ``"deny"`` otherwise, or ``"error"`` when the
    primitive itself raised.
    """

    scenario_id: str
    decision: Literal["allow", "deny", "error"]
    violation_kinds: tuple[str, ...] = ()
    error_detail: str = ""


@dataclass(frozen=True)
class ViolationDiff:
    """Added / removed violation codes between two ``SimulationResult``s.

    Frozensets keep the diff set-like while staying hashable for
    :class:`ScenarioDelta`; :meth:`DiffReport.to_dict` serialises
    them as sorted lists for operator-readable JSON.
    """

    added: frozenset[str]
    removed: frozenset[str]


@dataclass(frozen=True)
class ScenarioDelta:
    scenario_id: str
    target_policy_name: str
    baseline: SimulationResult
    proposed: SimulationResult
    transition: TransitionKind
    violation_diff: ViolationDiff
    notable: bool


@dataclass(frozen=True)
class DiffReport:
    baseline_policy_hashes: Mapping[str, str]
    proposed_policy_hashes: Mapping[str, str]
    scenarios_evaluated: int
    transitions: Mapping[TransitionKind, int]
    transitions_by_policy: Mapping[str, Mapping[TransitionKind, int]]
    deltas: tuple[ScenarioDelta, ...]
    emitted_at: str
    host_fs_dependent: bool = False
    host_fs_fingerprint: str | None = None

    @property
    def notable_deltas(self) -> tuple[ScenarioDelta, ...]:
        return tuple(d for d in self.deltas if d.notable)

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serialisable representation.

        Normalisation pass (plan v3 N4 absorb):
        - ``Path`` → ``str``
        - ``frozenset`` → sorted ``list``
        - compiled regex → ``.pattern``
        - manifest ``source_path`` → relative ``str``

        Output order is stable for cross-run diffs: scenario
        deltas are sorted by scenario_id; mappings expose keys in
        sorted order on serialisation (caller passes
        ``sort_keys=True``).
        """
        return {
            "schema_version": "v1",
            "emitted_at": self.emitted_at,
            "scenarios_evaluated": self.scenarios_evaluated,
            "baseline_policy_hashes": dict(self.baseline_policy_hashes),
            "proposed_policy_hashes": dict(self.proposed_policy_hashes),
            "transitions": {
                _TRANSITION_LABELS[k]: v
                for k, v in self.transitions.items()
            },
            "transitions_by_policy": {
                policy: {
                    _TRANSITION_LABELS[k]: v for k, v in counts.items()
                }
                for policy, counts in self.transitions_by_policy.items()
            },
            "host_fs_dependent": self.host_fs_dependent,
            "host_fs_fingerprint": self.host_fs_fingerprint,
            "deltas": [
                _serialise_delta(d)
                for d in sorted(self.deltas, key=lambda x: x.scenario_id)
            ],
            "notable_deltas_count": len(self.notable_deltas),
        }


def _serialise_delta(delta: ScenarioDelta) -> dict[str, Any]:
    return {
        "scenario_id": delta.scenario_id,
        "target_policy_name": delta.target_policy_name,
        "transition": _TRANSITION_LABELS[delta.transition],
        "notable": delta.notable,
        "baseline": _serialise_result(delta.baseline),
        "proposed": _serialise_result(delta.proposed),
        "violation_diff": {
            "added": sorted(delta.violation_diff.added),
            "removed": sorted(delta.violation_diff.removed),
        },
    }


def _serialise_result(result: SimulationResult) -> dict[str, Any]:
    return {
        "decision": result.decision,
        "violation_kinds": list(result.violation_kinds),
        "error_detail": result.error_detail,
    }


def compute_transition(
    baseline: SimulationResult, proposed: SimulationResult
) -> TransitionKind:
    """Classify a (baseline, proposed) pair into a ``TransitionKind``."""
    if baseline.decision == "error" or proposed.decision == "error":
        return "error"
    mapping: Mapping[tuple[str, str], TransitionKind] = {
        ("allow", "allow"): "allow_to_allow",
        ("allow", "deny"): "allow_to_deny",
        ("deny", "allow"): "deny_to_allow",
        ("deny", "deny"): "deny_to_deny",
    }
    return mapping[(baseline.decision, proposed.decision)]


def compute_violation_diff(
    baseline: SimulationResult, proposed: SimulationResult
) -> ViolationDiff:
    base = frozenset(baseline.violation_kinds)
    prop = frozenset(proposed.violation_kinds)
    return ViolationDiff(added=prop - base, removed=base - prop)


def make_scenario_delta(
    *,
    scenario_id: str,
    target_policy_name: str,
    baseline: SimulationResult,
    proposed: SimulationResult,
) -> ScenarioDelta:
    transition = compute_transition(baseline, proposed)
    diff = compute_violation_diff(baseline, proposed)
    notable = transition not in ("allow_to_allow", "deny_to_deny") or bool(
        diff.added or diff.removed
    )
    return ScenarioDelta(
        scenario_id=scenario_id,
        target_policy_name=target_policy_name,
        baseline=baseline,
        proposed=proposed,
        transition=transition,
        violation_diff=diff,
        notable=notable,
    )


def canonical_policy_hash(policy: Mapping[str, Any]) -> str:
    """Return ``"sha256:<hex>"`` over the canonical JSON form of
    ``policy``.

    Canonicalisation matches :mod:`ao_kernel.executor.artifacts`
    (plan v3 N3 absorb): ``sort_keys=True``,
    ``ensure_ascii=False``, ``separators=(",", ":")``, UTF-8
    bytes.
    """
    canonical = json.dumps(
        policy,
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
    )
    return "sha256:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def aggregate_transition_counts(
    deltas: Iterable[ScenarioDelta],
) -> tuple[
    Mapping[TransitionKind, int], Mapping[str, Mapping[TransitionKind, int]]
]:
    """Fold per-delta transitions into aggregate + per-policy
    counters. Keys are present for every ``TransitionKind`` so
    downstream reporters don't have to guard for missing axes."""
    all_kinds: tuple[TransitionKind, ...] = (
        "allow_to_allow",
        "allow_to_deny",
        "deny_to_allow",
        "deny_to_deny",
        "error",
    )
    overall: dict[TransitionKind, int] = {k: 0 for k in all_kinds}
    by_policy: dict[str, dict[TransitionKind, int]] = {}
    for delta in deltas:
        overall[delta.transition] += 1
        bucket = by_policy.setdefault(
            delta.target_policy_name, {k: 0 for k in all_kinds}
        )
        bucket[delta.transition] += 1
    return overall, by_policy


def dump_json(report: DiffReport) -> str:
    """Canonical JSON serialisation of ``report.to_dict()``.

    Uses the same canonicalisation as :func:`canonical_policy_hash`
    so ``dump_json(report)`` is stable cross-run.
    """
    payload = report.to_dict()
    return json.dumps(
        _stringify_unknowns(payload),
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
    )


def _stringify_unknowns(value: Any) -> Any:
    """Last-resort normaliser for ``Path`` / ``re.Pattern`` /
    anything else the primary normalisation missed. Raises
    :class:`ReportSerializationError`-materialised strings rather
    than hiding drift."""
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, re.Pattern):
        return value.pattern
    if isinstance(value, frozenset):
        return sorted(value)
    if isinstance(value, Mapping):
        return {k: _stringify_unknowns(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_stringify_unknowns(v) for v in value]
    return value


__all__ = [
    "DiffReport",
    "ScenarioDelta",
    "SimulationResult",
    "TransitionKind",
    "ViolationDiff",
    "aggregate_transition_counts",
    "canonical_policy_hash",
    "compute_transition",
    "compute_violation_diff",
    "dump_json",
    "make_scenario_delta",
]


# Silence unused-import lint — ``field`` kept for future extension.
_ = field
