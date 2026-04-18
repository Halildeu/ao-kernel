"""Reporter for the policy simulation harness (PR-B4 C4).

Two output formats:

- ``json`` — canonical JSON via :func:`diff.dump_json` (stable
  cross-run, sorted keys, ensure_ascii=False, tight separators).
- ``text`` — operator-readable table + per-policy breakdown +
  notable delta bullets.

File writing uses a tmp-then-rename atomic pattern; we stay
outside the purity context (the CLI handler is the caller)
because writes are the whole point of ``--output``.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Iterable, Literal, Mapping

# `TransitionKind` annotated in the typed tuples below so mypy
# narrows `.get()` without per-call casts.
from ao_kernel.policy_sim.diff import (
    DiffReport,
    ScenarioDelta,
    TransitionKind as _TransitionKind,
    dump_json,
)


ReportFormat = Literal["json", "text"]


_KIND_LABELS_OVERALL: tuple[tuple[_TransitionKind, str], ...] = (
    ("allow_to_allow", "allow→allow"),
    ("deny_to_deny", "deny→deny"),
    ("allow_to_deny", "allow→deny  ⚠ tightening"),
    ("deny_to_allow", "deny→allow  ⚠ loosening"),
    ("error", "error"),
)

_KIND_LABELS_PER_POLICY: tuple[tuple[_TransitionKind, str], ...] = (
    ("allow_to_allow", "allow→allow"),
    ("allow_to_deny", "allow→deny"),
    ("deny_to_allow", "deny→allow"),
    ("deny_to_deny", "deny→deny"),
    ("error", "error"),
)

_TIGHTENING_KINDS: tuple[_TransitionKind, ...] = ("allow_to_deny",)


def render(report: DiffReport, fmt: ReportFormat) -> str:
    """Render ``report`` in the requested format."""
    if fmt == "json":
        return dump_json(report)
    if fmt == "text":
        return _render_text(report)
    raise ValueError(f"unsupported report format: {fmt!r}")


def _render_text(report: DiffReport) -> str:
    lines: list[str] = []
    lines.append("Policy Simulation Report")
    lines.append("=" * len(lines[0]))
    lines.append("")
    lines.extend(_render_policies_section(report))
    lines.append("")
    lines.append(f"Scenarios evaluated: {report.scenarios_evaluated}")
    lines.append(
        f"host_fs_dependent: {str(report.host_fs_dependent).lower()}"
    )
    if report.host_fs_fingerprint:
        lines.append(f"host_fs_fingerprint: {report.host_fs_fingerprint}")
    lines.append("")
    lines.extend(_render_transitions_overall(report))
    lines.append("")
    lines.extend(_render_transitions_per_policy(report))
    lines.append("")
    lines.extend(_render_notable_deltas(report))
    return "\n".join(lines).rstrip() + "\n"


def _render_policies_section(report: DiffReport) -> Iterable[str]:
    all_policies = sorted(
        set(report.baseline_policy_hashes) | set(report.proposed_policy_hashes)
    )
    yield "Policies under test:"
    for name in all_policies:
        baseline = report.baseline_policy_hashes.get(name, "<missing>")
        proposed = report.proposed_policy_hashes.get(name, "<missing>")
        changed = baseline != proposed
        marker = " CHANGED" if changed else ""
        yield f"  - {name}{marker}"
        yield f"      baseline: {baseline}"
        yield f"      proposed: {proposed}"


def _render_transitions_overall(report: DiffReport) -> Iterable[str]:
    yield "Transitions (all):"
    for kind, label in _KIND_LABELS_OVERALL:
        count = report.transitions.get(kind, 0)
        yield f"  {label}: {count}"


def _render_transitions_per_policy(report: DiffReport) -> Iterable[str]:
    yield "Transitions per policy:"
    for policy in sorted(report.transitions_by_policy):
        counts = report.transitions_by_policy[policy]
        total = sum(counts.values())
        parts = [
            f"{label}={counts.get(kind, 0)}"
            for kind, label in _KIND_LABELS_PER_POLICY
            if counts.get(kind, 0)
        ]
        summary = ", ".join(parts) if parts else "no transitions"
        yield f"  - {policy}: {total} scenario(s) ({summary})"


def _render_notable_deltas(report: DiffReport) -> Iterable[str]:
    notables = report.notable_deltas
    if not notables:
        yield "Notable deltas: none"
        return
    yield "Notable deltas:"
    for delta in sorted(notables, key=lambda d: d.scenario_id):
        yield f"  - [{delta.transition}] {delta.scenario_id} " f"({delta.target_policy_name})"
        if delta.violation_diff.added:
            yield f"      added violations: {sorted(delta.violation_diff.added)}"
        if delta.violation_diff.removed:
            yield f"      removed violations: {sorted(delta.violation_diff.removed)}"
        if delta.baseline.error_detail:
            yield f"      baseline error: {delta.baseline.error_detail}"
        if delta.proposed.error_detail:
            yield f"      proposed error: {delta.proposed.error_detail}"


def has_tightening(report: DiffReport) -> bool:
    """Return True iff the report carries at least one
    ``allow_to_deny`` transition — triggers CLI exit code 3."""
    return any(
        report.transitions.get(kind, 0) > 0
        for kind in _TIGHTENING_KINDS
    )


def write_atomic(output_path: Path, content: str) -> None:
    """Atomic write: tmp + rename, mkdir parents as needed.

    Used by the CLI after simulation has exited the purity
    context; direct writes inside the context would trip the
    guard.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = output_path.with_name(output_path.name + ".tmp")
    with tmp_path.open("w", encoding="utf-8") as fh:
        fh.write(content)
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(tmp_path, output_path)


def load_policies_from_dir(
    directory: Path,
) -> Mapping[str, Mapping[str, Any]]:
    """Load every ``*.json`` file in ``directory`` as
    ``{filename: parsed_dict}``.

    Used by the CLI to materialise ``--proposed-policies`` and
    ``--baseline-overrides`` arguments into the Mapping shapes
    ``simulate_policy_change`` expects.
    """
    mapping: dict[str, Mapping[str, Any]] = {}
    if not directory.exists():
        return mapping
    for path in sorted(directory.glob("*.json")):
        with path.open("r", encoding="utf-8") as fh:
            mapping[path.name] = json.load(fh)
    return mapping


__all__ = [
    "ReportFormat",
    "ScenarioDelta",
    "has_tightening",
    "load_policies_from_dir",
    "render",
    "write_atomic",
]
