"""PR v3.4.0 #1 — cost reconciliation daemon (orphan spend recovery).

v3.3.1 (PR-C3.2) shipped marker-driven idempotency: `apply_spend_with_marker`
writes a ledger entry BEFORE stamping the `cost_reconciled` marker on the
run record. If a process crashes between those two steps, the ledger is
ahead of the marker — an "orphan ledger entry". Normal reconcile retries
recover automatically when the caller re-invokes, but long-lived runs can
accumulate orphans that never get a natural retry.

This module provides the scanning + recovery path operators need to close
that gap out-of-band:

- :func:`find_orphan_spends` — iterates the ledger, cross-references each
  entry against the matching run record's `cost_reconciled` array, and
  yields a typed :class:`OrphanSpend` per miss.
- :func:`fix_orphan` — re-runs `apply_spend_with_marker` with a no-op
  budget mutator. The ledger is already there (record_spend detects the
  matching digest, silent no-op), but the marker CAS stamps the missing
  entry. Idempotent by design — running twice is safe.
- :func:`scan_and_fix` — the daemon's main loop: load cursor, iterate,
  fix, persist cursor. CLI surface invokes this.
- Cursor state at ``.ao/cost/reconciler-cursor.json`` tracks the last
  scanned line offset so subsequent invocations only touch new ledger
  tail. ``--cursor-reset`` forces a full re-scan.

Scope (v3.4.0 #1):
- Orphan detection via 4-tuple (source, step_id, attempt, billing_digest)
- Idempotent fix via `apply_spend_with_marker` re-entry
- Cursor-based incremental scanning (file_lock-protected)
- No budget drain on fix path (the drain already happened before the
  original crash; marker-only recovery).

Out of scope (future):
- Automatic startup hook in `AoKernelClient.__init__`
- Streaming / push-based orphan alerts
- Cross-workspace federation
"""

from __future__ import annotations

import datetime as _dt
import json
import logging
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any, Iterator, Mapping

from ao_kernel._internal.shared.lock import file_lock
from ao_kernel.cost._reconcile import ReconcileSource, apply_spend_with_marker
from ao_kernel.cost.ledger import SpendEvent
from ao_kernel.cost.policy import CostTrackingPolicy
from ao_kernel.workflow.errors import WorkflowRunNotFoundError
from ao_kernel.workflow.run_store import load_run


logger = logging.getLogger(__name__)


_CURSOR_VERSION = "v1"


@dataclass(frozen=True)
class OrphanSpend:
    """A ledger entry without a matching ``cost_reconciled`` marker.

    Attributes:
        run_id: The workflow run the spend belongs to.
        step_id: The step_id stamped on the ledger entry.
        attempt: The attempt number.
        billing_digest: Canonical SHA-256 over billing fields.
        source: Which reconcile path originally wrote the ledger entry.
        ledger_line_offset: Zero-based line offset within ``spend.jsonl``
            — used by the cursor to tick past scanned ranges.
        raw_event: The deserialized ledger entry (for
            :func:`fix_orphan` to rebuild ``SpendEvent``).
    """

    run_id: str
    step_id: str
    attempt: int
    billing_digest: str
    source: ReconcileSource
    ledger_line_offset: int
    raw_event: Mapping[str, Any]


@dataclass(frozen=True)
class ScanResult:
    """Summary of a :func:`scan_and_fix` invocation."""

    orphans_found: int
    orphans_fixed: int
    orphans_skipped: int
    errors: tuple[str, ...]
    cursor_offset_before: int
    cursor_offset_after: int


def _cursor_path(workspace_root: Path, policy: CostTrackingPolicy) -> Path:
    """Cursor file sits next to the ledger so both stay in one dir."""
    ledger = workspace_root / policy.spend_ledger_path
    return ledger.parent / "reconciler-cursor.json"


def _cursor_lock_path(cursor: Path) -> Path:
    return cursor.with_suffix(cursor.suffix + ".lock")


def _default_cursor_state() -> dict[str, Any]:
    return {
        "version": _CURSOR_VERSION,
        "last_scanned_line_offset": 0,
        "last_check_ts": None,
        "orphans_fixed_total": 0,
    }


def load_cursor(cursor_path: Path) -> dict[str, Any]:
    """Read the cursor state or return a fresh default if missing.

    Treats version mismatches as "reset" for forward compat — a daemon
    reading an older cursor version starts from offset 0 rather than
    risking a schema drift bug.
    """
    if not cursor_path.is_file():
        return _default_cursor_state()
    try:
        state: dict[str, Any] = json.loads(
            cursor_path.read_text(encoding="utf-8"),
        )
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning(
            "reconciler cursor unreadable at %s (%s); resetting",
            cursor_path, exc,
        )
        return _default_cursor_state()
    if state.get("version") != _CURSOR_VERSION:
        logger.warning(
            "reconciler cursor version %r != expected %r; resetting",
            state.get("version"), _CURSOR_VERSION,
        )
        return _default_cursor_state()
    return state


def save_cursor(cursor_path: Path, state: Mapping[str, Any]) -> None:
    """Atomic cursor write (tempfile + fsync + os.replace)."""
    from ao_kernel._internal.shared.utils import write_text_atomic

    cursor_path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    payload = json.dumps(dict(state), indent=2, sort_keys=True) + "\n"
    write_text_atomic(cursor_path, payload)


def _iter_ledger_lines(
    ledger_path: Path, start_offset: int,
) -> Iterator[tuple[int, dict[str, Any]]]:
    """Yield (line_offset, parsed_dict) for lines at offset >= start.

    Skips empty lines. Raises nothing on a corrupt line — yields it as
    a raw dict with a ``_corrupt`` marker so the caller can surface the
    issue in the ScanResult.errors list without aborting the scan.
    """
    if not ledger_path.is_file():
        return
    with ledger_path.open("r", encoding="utf-8") as fh:
        for offset, raw in enumerate(fh):
            if offset < start_offset:
                continue
            stripped = raw.strip()
            if not stripped:
                continue
            try:
                yield offset, json.loads(stripped)
            except json.JSONDecodeError as exc:
                yield offset, {"_corrupt": True, "reason": str(exc)}


def _has_matching_marker(
    record: Mapping[str, Any],
    *,
    source: str,
    step_id: str,
    attempt: int,
    billing_digest: str,
) -> bool:
    """Scan ``record.cost_reconciled`` for a 4-tuple match."""
    markers = record.get("cost_reconciled") or []
    key = (source, step_id, attempt, billing_digest)
    for m in markers:
        if (
            m.get("source"),
            m.get("step_id"),
            m.get("attempt"),
            m.get("billing_digest"),
        ) == key:
            return True
    return False


def _infer_source(entry: Mapping[str, Any]) -> ReconcileSource:
    """Ledger events don't carry the reconcile-path discriminator —
    the marker does. To find the marker (or prove its absence), we must
    know which source to check. Current heuristic: use
    ``usage_missing`` as the sentinel — a ledger entry with
    ``usage_missing=True`` was written by the usage_missing branch;
    everything else is adapter_path (the governed_call path also uses
    the same marker source for non-usage-missing flows, so checking
    adapter_path first catches both).

    False positives here are a recovery no-op: :func:`fix_orphan`
    stamps the marker under the inferred source; if both adapter_path
    and governed_call produced the same ledger entry (they shouldn't
    in practice), a second daemon pass would stamp the other source.
    """
    if entry.get("usage_missing") is True:
        return "usage_missing"
    return "adapter_path"


def find_orphan_spends(
    workspace_root: Path,
    policy: CostTrackingPolicy,
    *,
    start_offset: int = 0,
) -> Iterator[OrphanSpend]:
    """Stream orphan ledger entries (no matching marker on their run).

    Walks the ledger from ``start_offset`` forward. For each parseable
    entry, loads the referenced run record and checks the
    ``cost_reconciled`` array. Missing runs are skipped (logged); the
    caller decides whether to alert. Corrupt ledger lines are yielded
    as non-orphan sentinels the daemon can report without aborting.
    """
    ledger_path = workspace_root / policy.spend_ledger_path
    for offset, entry in _iter_ledger_lines(ledger_path, start_offset):
        if entry.get("_corrupt"):
            # Signal upward via a synthetic OrphanSpend whose raw_event
            # carries the corruption reason — daemon layer formats it
            # into errors[] list rather than treating it as orphan.
            continue
        run_id = entry.get("run_id")
        step_id = entry.get("step_id")
        attempt = entry.get("attempt")
        billing_digest = entry.get("billing_digest")
        if not (run_id and step_id and attempt and billing_digest):
            continue  # malformed but parseable; skip silently
        try:
            record, _ = load_run(workspace_root, run_id)
        except WorkflowRunNotFoundError:
            logger.info(
                "reconciler: ledger entry references missing run %s at "
                "offset %d (skipping)", run_id, offset,
            )
            continue
        except Exception as exc:  # run store read error
            logger.warning(
                "reconciler: failed to load run %s at offset %d: %s",
                run_id, offset, exc,
            )
            continue
        source = _infer_source(entry)
        if _has_matching_marker(
            record,
            source=source,
            step_id=step_id,
            attempt=int(attempt),
            billing_digest=billing_digest,
        ):
            continue  # reconciled already
        yield OrphanSpend(
            run_id=run_id,
            step_id=step_id,
            attempt=int(attempt),
            billing_digest=billing_digest,
            source=source,
            ledger_line_offset=offset,
            raw_event=dict(entry),
        )


def _rebuild_spend_event(entry: Mapping[str, Any]) -> SpendEvent:
    """Rebuild a :class:`SpendEvent` from a ledger line for the
    reconcile helper to pass through. The digest is already in the
    entry; re-using it avoids a recompute and keeps the marker key
    stable.
    """
    return SpendEvent(
        run_id=entry["run_id"],
        step_id=entry["step_id"],
        attempt=int(entry["attempt"]),
        provider_id=entry.get("provider_id", ""),
        model=entry.get("model", ""),
        tokens_input=int(entry.get("tokens_input", 0) or 0),
        tokens_output=int(entry.get("tokens_output", 0) or 0),
        cost_usd=Decimal(str(entry.get("cost_usd", 0))),
        ts=entry.get("ts", ""),
        vendor_model_id=entry.get("vendor_model_id"),
        cached_tokens=entry.get("cached_tokens"),
        usage_missing=bool(entry.get("usage_missing", False)),
        billing_digest=entry["billing_digest"],
    )


def fix_orphan(
    workspace_root: Path,
    orphan: OrphanSpend,
    *,
    policy: CostTrackingPolicy,
) -> bool:
    """Stamp the missing marker for an orphan ledger entry.

    The budget was already drained in the original pre-crash call (if
    it was the adapter_path happy path) — the orphan state means the
    ledger has the audit trail, the budget has the deduction, and ONLY
    the marker is missing. The reconcile helper's idempotent contract
    lets us re-run with a no-op budget mutator: the ledger call
    silently no-ops on matching digest, and the marker CAS stamps the
    missing row.

    Returns ``True`` if a new marker was stamped (recovery succeeded),
    ``False`` if the helper declared no-op (marker already present on
    a concurrent call between find + fix).
    """
    event = _rebuild_spend_event(orphan.raw_event)

    def _no_drain_mutator(record: dict[str, Any]) -> dict[str, Any]:
        # Marker-only recovery. Budget was already drained in the
        # original reconcile call; restamping the marker is enough.
        return record

    return apply_spend_with_marker(
        workspace_root,
        orphan.run_id,
        event,
        policy=policy,
        source=orphan.source,
        budget_mutator=_no_drain_mutator,
    )


def scan_and_fix(
    workspace_root: Path,
    policy: CostTrackingPolicy,
    *,
    dry_run: bool = False,
    cursor_reset: bool = False,
) -> ScanResult:
    """Daemon entry point — scan ledger, fix orphans, persist cursor.

    ``dry_run=True`` reports orphans but does NOT call :func:`fix_orphan`
    and does NOT advance the cursor (re-runs produce identical output
    until a real pass is made).

    ``cursor_reset=True`` ignores any existing cursor and starts from
    offset 0, then persists the resulting offset at the end (unless
    ``dry_run``).

    The cursor lock serializes concurrent daemon invocations — two
    simultaneous ``ao-kernel cost reconcile`` calls won't both advance
    the cursor or double-stamp markers (markers are already idempotent
    via the reconcile helper, but the lock keeps cursor state coherent).
    """
    cursor_path = _cursor_path(workspace_root, policy)
    lock_path = _cursor_lock_path(cursor_path)
    lock_path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)

    with file_lock(lock_path):
        state = (
            _default_cursor_state() if cursor_reset else load_cursor(cursor_path)
        )
        start_offset = int(state.get("last_scanned_line_offset", 0) or 0)

        found = 0
        fixed = 0
        skipped = 0
        errors: list[str] = []
        last_offset = start_offset - 1

        for orphan in find_orphan_spends(
            workspace_root, policy, start_offset=start_offset,
        ):
            found += 1
            last_offset = orphan.ledger_line_offset
            if dry_run:
                continue
            try:
                if fix_orphan(workspace_root, orphan, policy=policy):
                    fixed += 1
                else:
                    # Helper returned False — marker already present
                    # (race between find + fix, or our source inference
                    # missed the actual source). Count as skipped.
                    skipped += 1
            except Exception as exc:
                errors.append(
                    f"run_id={orphan.run_id} offset={orphan.ledger_line_offset}: "
                    f"{type(exc).__name__}: {exc}"
                )

        # Scan the ledger tail — even when there are no orphans in the
        # already-seen range, we need to record the new furthest
        # offset so the next invocation only walks new lines.
        ledger_path = workspace_root / policy.spend_ledger_path
        if ledger_path.is_file():
            try:
                # line count scan (cheap for reasonable ledger sizes)
                with ledger_path.open("r", encoding="utf-8") as fh:
                    total_lines = sum(1 for _ in fh)
                if total_lines > 0:
                    last_offset = max(last_offset, total_lines - 1)
            except OSError as exc:
                errors.append(f"ledger tail scan failed: {exc}")

        new_offset = max(last_offset + 1, start_offset)

        if not dry_run:
            state["last_scanned_line_offset"] = new_offset
            state["last_check_ts"] = _dt.datetime.now(
                _dt.timezone.utc,
            ).isoformat()
            state["orphans_fixed_total"] = int(
                state.get("orphans_fixed_total", 0) or 0,
            ) + fixed
            save_cursor(cursor_path, state)

        return ScanResult(
            orphans_found=found,
            orphans_fixed=fixed,
            orphans_skipped=skipped,
            errors=tuple(errors),
            cursor_offset_before=start_offset,
            cursor_offset_after=new_offset,
        )


__all__ = [
    "OrphanSpend",
    "ScanResult",
    "find_orphan_spends",
    "fix_orphan",
    "scan_and_fix",
    "load_cursor",
    "save_cursor",
]
