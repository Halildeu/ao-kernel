#!/usr/bin/env python3
"""Print the current AO-MA-SPM phase/slice + next allowed action for operators.

This is a PURE-READ tracking surface over ``.claude/plans/ao_ma_status.v1.json``
(AO-MA-11E-1). It does NOT shell out, call the network, touch GitHub, or
mutate anything. ``ao_ma_status.v1.json`` is a *derived tracking index*, not a
governance authority: it never overrides the master plan, plan-consensus
bundles, plan approvals, the computed risk class, or the release authority.

The script loads + schema-validates the status file, runs a pure local
consistency (drift) comparator, and prints an operator-facing summary plus the
machine-readable next allowed action. A drift or schema failure exits non-zero
(fail-closed): per ``drift_policy.on_status_or_mirror_drift`` the right
operator response is to halt autonomy and escalate, not to proceed.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

_REPO_ROOT = Path(__file__).resolve().parents[1]
_DEFAULT_STATUS_PATH = _REPO_ROOT / ".claude" / "plans" / "ao_ma_status.v1.json"
_SCHEMA_PATH = _REPO_ROOT / "ao_kernel" / "defaults" / "schemas" / "ao-ma-status.schema.v1.json"

_GUARD_FLAGS = (
    "support_widening_allowed",
    "production_platform_claim_allowed",
    "live_adapter_execution_allowed",
)


class AoMaStatusError(RuntimeError):
    """Raised when the status file is missing, malformed, schema-invalid, or drifted."""


def load_status(path: Path) -> dict[str, Any]:
    """Load + schema-validate the AO-MA status payload (fail-closed)."""

    if not path.exists():
        raise AoMaStatusError(f"AO-MA status file not found: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise AoMaStatusError(f"failed to read AO-MA status file {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise AoMaStatusError("AO-MA status payload must be a JSON object")
    try:
        schema = json.loads(_SCHEMA_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise AoMaStatusError(f"failed to load AO-MA status schema: {exc}") from exc
    errors = sorted(Draft202012Validator(schema).iter_errors(payload), key=lambda e: list(e.absolute_path))
    if errors:
        first = errors[0]
        raise AoMaStatusError(
            f"AO-MA status failed schema at {list(first.absolute_path)}: {first.message} ({len(errors)} error(s) total)"
        )
    return payload


def _sha256_of_file(path: Path) -> str | None:
    """Return 'sha256:<hex>' of a file, or None if it cannot be read."""

    try:
        return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        return None


def check_drift(payload: dict[str, Any], *, repo_root: Path | None = None) -> list[str]:
    """Pure local consistency comparator. Returns a list of drift findings.

    This is the 11E-1 (local) drift core: it compares the derived index
    against itself (and, when ``repo_root`` is given, against the on-disk
    master plan + anchor artifact hashes it claims to derive from) for
    internal consistency. The GitHub mirror comparator (projected payload vs
    GitHub state) is AO-MA-11E-2. Findings here mean the derived index is
    inconsistent and must be repaired before it can be trusted; per
    ``drift_policy`` the operator response is to halt autonomy and escalate.

    ``repo_root`` defaults to the script's repo root; pass an explicit root in
    tests to point at a fixture tree. Hash checks are skipped (not failed) for
    referenced files that do not exist under ``repo_root`` so the comparator
    stays a pure local digest check rather than a presence requirement.
    """

    if repo_root is None:
        repo_root = _REPO_ROOT
    findings: list[str] = []

    # Guard flags must be literal False (schema pins const; defensive recheck).
    for flag in _GUARD_FLAGS:
        if payload.get(flag) is not False:
            findings.append(f"{flag} must be literal False (derived index cannot widen scope)")

    # master_plan_ref must match the on-disk master plan bytes (stale-status guard).
    mp_ref = payload["master_plan_ref"]
    mp_path = repo_root / mp_ref["path"]
    actual_mp_sha = _sha256_of_file(mp_path)
    if actual_mp_sha is not None and actual_mp_sha != mp_ref["sha256"]:
        findings.append(
            f"master_plan_ref.sha256 {mp_ref['sha256']} != on-disk {mp_ref['path']} {actual_mp_sha} (stale status)"
        )

    phases = payload["phases"]
    slices = payload["slices"]
    phase_ids = {p["phase_id"] for p in phases}

    # Duplicate slice_id guard (uniqueItems on objects does not catch same-id rows).
    seen_slice_ids: set[str] = set()
    for sl in slices:
        sid = sl["slice_id"]
        if sid in seen_slice_ids:
            findings.append(f"duplicate slice_id {sid}")
        seen_slice_ids.add(sid)
    slice_ids = seen_slice_ids

    # Cross-ref: every phase.slice_ids entry must exist in slices[] and vice versa.
    declared_slice_ids: set[str] = set()
    for phase in phases:
        for sid in phase["slice_ids"]:
            declared_slice_ids.add(sid)
            if sid not in slice_ids:
                findings.append(f"phase {phase['phase_id']} references unknown slice {sid}")
    for sl in slices:
        if sl["slice_id"] not in declared_slice_ids:
            findings.append(f"slice {sl['slice_id']} is not listed under any phase.slice_ids")
        if sl["phase_id"] not in phase_ids:
            findings.append(f"slice {sl['slice_id']} references unknown phase {sl['phase_id']}")
        if sl["anchor"]["phase_id"] != sl["phase_id"] or sl["anchor"]["slice_id"] != sl["slice_id"]:
            findings.append(f"slice {sl['slice_id']} anchor phase/slice id mismatch")
        # Anchor artifact hash must match the on-disk artifact bytes it claims to derive from.
        art = sl["anchor"]["ao_authority_artifact"]
        art_sha = sl["anchor"]["artifact_sha256"]
        if art is not None and art_sha is not None:
            actual = _sha256_of_file(repo_root / art)
            if actual is not None and actual != art_sha:
                findings.append(f"slice {sl['slice_id']} anchor artifact_sha256 != on-disk {art} ({actual})")

    # current_phase / current_slice must exist, and the current slice must
    # belong to the current phase.
    slices_by_id = {s["slice_id"]: s for s in slices}
    if payload["current_phase"] not in phase_ids:
        findings.append(f"current_phase {payload['current_phase']} not present in phases")
    cur_slice = slices_by_id.get(payload["current_slice"])
    if cur_slice is None:
        findings.append(f"current_slice {payload['current_slice']} not present in slices")
    elif cur_slice["phase_id"] != payload["current_phase"]:
        findings.append(
            f"current_slice {payload['current_slice']} belongs to {cur_slice['phase_id']}, "
            f"not current_phase {payload['current_phase']}"
        )

    # State-machine binding: merged / in_review slices must carry consensus +
    # (when decided) a consistent approval. 'agreed'/'approved' schema-level
    # already require evidence (if/then); here we bind those states to the
    # slice lifecycle so a merged slice cannot sit on a not_started consensus.
    for sl in slices:
        if sl["status"] in ("in_review", "merged"):
            if sl["consensus_ref"]["state"] != "agreed":
                findings.append(f"{sl['status']} slice {sl['slice_id']} must have consensus_ref.state=agreed")
        if sl["status"] == "merged":
            if sl["approval_ref"]["state"] == "approved" and sl["approval_ref"].get("decision") != "approved":
                findings.append(f"slice {sl['slice_id']} approval state=approved but decision != approved")
            # high/critical merged slices must carry a PR audit ref (cross-AI / supersession lane).
            if sl["risk_class"] in ("high", "critical") and not sl.get("pr_refs"):
                findings.append(f"merged {sl['risk_class']} slice {sl['slice_id']} has no pr_refs (audit gap)")

    # phase.status=done requires every owned slice to be merged.
    for phase in phases:
        if phase["status"] == "done":
            unmerged = [sid for sid in phase["slice_ids"] if slices_by_id.get(sid, {}).get("status") != "merged"]
            if unmerged:
                findings.append(f"phase {phase['phase_id']} is done but slices not merged: {unmerged}")

    # progress_estimates.slices: merged_count, total_count, percent recomputed.
    merged_actual = sum(1 for s in slices if s["status"] == "merged")
    total_actual = len(slices)
    slice_pe = payload["progress_estimates"]["slices"]
    if slice_pe["merged_count"] != merged_actual:
        findings.append(f"progress_estimates.slices.merged_count {slice_pe['merged_count']} != actual {merged_actual}")
    if slice_pe["total_count"] != total_actual:
        findings.append(f"progress_estimates.slices.total_count {slice_pe['total_count']} != actual {total_actual}")
    expected_slice_pct = round(merged_actual * 100 / total_actual) if total_actual else 0
    if slice_pe["percent"] != expected_slice_pct:
        findings.append(f"progress_estimates.slices.percent {slice_pe['percent']} != recomputed {expected_slice_pct}")

    # progress_estimates.phases: done_count + percent recomputed.
    done_actual = sum(1 for p in phases if p["status"] == "done")
    total_phases = len(phases)
    phase_pe = payload["progress_estimates"]["phases"]
    if phase_pe["done_count"] != done_actual:
        findings.append(f"progress_estimates.phases.done_count {phase_pe['done_count']} != actual {done_actual}")
    if phase_pe["total_count"] != total_phases:
        findings.append(f"progress_estimates.phases.total_count {phase_pe['total_count']} != actual {total_phases}")
    expected_phase_pct = round(done_actual * 100 / total_phases) if total_phases else 0
    if phase_pe["percent"] != expected_phase_pct:
        findings.append(f"progress_estimates.phases.percent {phase_pe['percent']} != recomputed {expected_phase_pct}")

    return findings


def next_action(payload: dict[str, Any]) -> str:
    """Return the first machine-readable next allowed action (or a default)."""

    actions = payload["next_allowed_actions"]
    return actions[0] if actions else "no next action recorded; consult the master plan"


def render_text(payload: dict[str, Any], drift: list[str]) -> str:
    """Render a concise operator-facing status report."""

    pe = payload["progress_estimates"]
    ph = pe["phases"]
    sl = pe["slices"]
    lines = [
        f"Program: {payload['program_title']}",
        f"Status role: {payload['status_role']} (NOT an authority)",
        f"Authority ref: {payload['authority_ref']}",
        f"Master plan: {payload['master_plan_ref']['path']} @ {payload['master_plan_ref']['commit_sha'][:7]}",
        f"Current phase: {payload['current_phase']}",
        f"Current slice: {payload['current_slice']}",
        "",
        f"Phases: {ph['done_count']}/{ph['total_count']} done ({ph['percent']}%; next {ph['next_phase_id'] or 'none'})",
        f"Slices: {sl['merged_count']}/{sl['total_count']} merged ({sl['percent']}%)",
        "",
        "Guard flags (all must be false):",
        f"- support_widening_allowed: {str(payload['support_widening_allowed']).lower()}",
        f"- production_platform_claim_allowed: {str(payload['production_platform_claim_allowed']).lower()}",
        f"- live_adapter_execution_allowed: {str(payload['live_adapter_execution_allowed']).lower()}",
        f"GitHub mirror: {payload['github_mirror']['sync_state']} (authority={str(payload['github_mirror']['authority']).lower()})",
        "",
        "Slices:",
    ]
    for s in payload["slices"]:
        lines.append(
            f"- {s['slice_id']} [{s['status']}] risk={s['risk_class']} "
            f"consensus={s['consensus_ref']['state']} approval={s['approval_ref']['state']} :: {s['title']}"
        )
    lines.extend(["", f"Next allowed action: {next_action(payload)}"])
    if drift:
        lines.extend(["", "DRIFT DETECTED (halt autonomy + escalate):"])
        lines.extend(f"- {d}" for d in drift)
    else:
        lines.extend(["", "Drift: none (derived index internally consistent)"])
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Print AO-MA-SPM tracking status + next allowed action.")
    parser.add_argument(
        "--status",
        type=Path,
        default=_DEFAULT_STATUS_PATH,
        help="Path to ao_ma_status.v1.json (default: repo .claude/plans/).",
    )
    parser.add_argument("--format", choices=["text", "json"], default="text", help="Output format.")
    parser.add_argument(
        "--next-only",
        action="store_true",
        help="Print only the next allowed action string.",
    )
    args = parser.parse_args(argv)

    try:
        payload = load_status(args.status)
    except AoMaStatusError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    drift = check_drift(payload)

    if args.next_only:
        print(next_action(payload))
        return 1 if drift else 0

    if args.format == "json":
        print(json.dumps({"next_allowed_action": next_action(payload), "drift": drift}, indent=2))
    else:
        print(render_text(payload, drift), end="")

    # Fail-closed: drift means the derived index cannot be trusted; exit non-zero.
    return 1 if drift else 0


if __name__ == "__main__":
    raise SystemExit(main())
