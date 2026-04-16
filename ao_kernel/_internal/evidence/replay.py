"""Evidence replay engine (PR-A5).

Walks the event stream and infers run-level state transitions.
Does NOT re-execute — read-only analysis. Reports
``state_source: event|inferred|synthetic`` per transition (B3 absorb).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal


_EVENT_STATE_MAP: dict[str, str] = {
    "workflow_started": "running",
    "workflow_completed": "completed",
    "workflow_failed": "failed",
    "approval_requested": "waiting_approval",
    "approval_granted": "running",
    "approval_denied": "cancelled",
}

_INFERRED_STATE_MAP: dict[str, str] = {
    "diff_applied": "applying",
    "test_executed": "verifying",
    "diff_previewed": "running",  # pre-apply; state stays running
}


@dataclass
class StateTransition:
    seq: int
    event_kind: str
    from_state: str
    to_state: str
    state_source: Literal["event", "inferred", "synthetic"]
    replay_safe: bool
    stored_replay_safe: bool
    note: str = ""


@dataclass
class ReplayReport:
    run_id: str
    mode: str
    transitions: list[StateTransition] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    final_inferred_state: str = "unknown"


# Effective replay_safe taxonomy (B2 absorb — authoritative, not stored value)
_NON_REPLAY_SAFE_KINDS = frozenset({
    "adapter_invoked", "adapter_returned",
    "approval_granted", "approval_denied",
    "pr_opened",
})


def replay(
    workspace_root: Path,
    run_id: str,
    *,
    mode: str = "inspect",
) -> ReplayReport:
    """Walk the event stream and produce a replay report.

    ``mode="inspect"``: annotate each event with replay_safe + state trace.
    ``mode="dry-run"``: full state machine walk with warnings for
    illegal/unexpected transitions.
    """
    events_path = (
        workspace_root / ".ao" / "evidence" / "workflows" / run_id / "events.jsonl"
    )
    if not events_path.exists():
        raise FileNotFoundError(f"events not found: {events_path}")

    events = _parse_sorted(events_path)
    report = ReplayReport(run_id=run_id, mode=mode)
    current_state = "created"

    for evt in events:
        kind = evt.get("kind", "")
        seq = evt.get("seq", 0)
        stored_safe = evt.get("replay_safe", True)
        effective_safe = kind not in _NON_REPLAY_SAFE_KINDS

        # Determine target state
        target = _EVENT_STATE_MAP.get(kind)
        source: Literal["event", "inferred", "synthetic"] = "event"
        if target is None:
            target = _INFERRED_STATE_MAP.get(kind)
            source = "inferred" if target else "synthetic"

        if target is None:
            # No state implication — step_started, step_completed etc.
            # Record for inspect but don't transition.
            if mode == "inspect":
                report.transitions.append(StateTransition(
                    seq=seq, event_kind=kind,
                    from_state=current_state, to_state=current_state,
                    state_source="synthetic",
                    replay_safe=effective_safe,
                    stored_replay_safe=stored_safe,
                    note="no state transition",
                ))
            continue

        # Check legality; insert synthetic chain if needed (I4-B3)
        from ao_kernel.workflow.state_machine import allowed_next
        try:
            legal = target in allowed_next(current_state)
        except ValueError:
            legal = False

        if not legal and current_state != target:
            # Attempt synthetic chain (e.g., running → applying → verifying → completed)
            chain = _synthetic_chain(current_state, target)
            if chain:
                for intermediate in chain:
                    report.transitions.append(StateTransition(
                        seq=seq, event_kind=kind,
                        from_state=current_state, to_state=intermediate,
                        state_source="synthetic",
                        replay_safe=effective_safe,
                        stored_replay_safe=stored_safe,
                        note="synthetic intermediate",
                    ))
                    current_state = intermediate
                legal = True  # chain resolved the gap
            else:
                report.warnings.append(
                    f"seq={seq}: illegal transition {current_state!r} → {target!r} "
                    f"(event={kind}, source={source})"
                )

        report.transitions.append(StateTransition(
            seq=seq, event_kind=kind,
            from_state=current_state, to_state=target,
            state_source=source,
            replay_safe=effective_safe,
            stored_replay_safe=stored_safe,
            note="illegal" if not legal and current_state != target else "",
        ))
        current_state = target

    report.final_inferred_state = current_state
    return report


def format_replay_report(report: ReplayReport) -> str:
    """Human-readable replay report."""
    lines = [
        f"Replay report for run {report.run_id} (mode={report.mode})",
        f"Final inferred state: {report.final_inferred_state}",
        f"Transitions: {len(report.transitions)}",
        f"Warnings: {len(report.warnings)}",
        "",
    ]
    for t in report.transitions:
        safe_marker = "R" if t.replay_safe else "N"
        stored_marker = "R" if t.stored_replay_safe else "N"
        mismatch = " MISMATCH" if t.replay_safe != t.stored_replay_safe else ""
        lines.append(
            f"  seq={t.seq:>3} {t.event_kind:24} "
            f"{t.from_state:20} → {t.to_state:20} "
            f"[{t.state_source:9}] safe={safe_marker}/stored={stored_marker}{mismatch}"
            f"{' ⚠ ' + t.note if t.note else ''}"
        )
    if report.warnings:
        lines.append("")
        lines.append("Warnings:")
        for w in report.warnings:
            lines.append(f"  ⚠ {w}")
    return "\n".join(lines)


_SYNTHETIC_CHAINS: dict[tuple[str, str], list[str]] = {
    ("running", "completed"): ["applying", "verifying"],
    ("running", "verifying"): ["applying"],
    ("applying", "completed"): ["verifying"],
}


def _synthetic_chain(current: str, target: str) -> list[str]:
    """Return intermediate states for a synthetic transition chain.

    Returns empty list if no known chain exists. Used to bridge the
    gap between the driver's CAS chain (which may skip evidence events
    for intermediate states) and the state machine's transition table.
    """
    return list(_SYNTHETIC_CHAINS.get((current, target), []))


def _parse_sorted(path: Path) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        events.append(json.loads(line))
    events.sort(key=lambda e: e.get("seq", 0))
    return events
