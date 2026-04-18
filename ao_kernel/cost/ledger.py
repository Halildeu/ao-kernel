"""Spend ledger — append-only JSONL with canonical billing digest
idempotency (PR-B2 commit 3).

Each billable LLM invocation emits one event to ``{workspace_root}/
{policy.spend_ledger_path}`` (default ``.ao/cost/spend.jsonl``).
Events are keyed by ``(run_id, step_id, attempt)``; the writer
tail-scans the last ``policy.idempotency_window_lines`` lines before
appending and:

- No-ops silently (warn-log) when the key already exists with the
  SAME ``billing_digest`` — retry idempotency.
- Raises :class:`SpendLedgerDuplicateError` when the key already
  exists with a DIFFERENT ``billing_digest`` — caller bug (the same
  retry produced distinct billable payload).

Corrupt JSONL lines encountered during the scan raise
:class:`SpendLedgerCorruptedError` (fail-closed). Operator must
repair the ledger before cost runtime can continue.

Dormant gate lives in the caller (``cost.middleware``); ``record_spend``
itself is unconditional once policy + path have been resolved.

See ``docs/COST-MODEL.md`` §3 and PR-B2 plan v7 §2.2.
"""

from __future__ import annotations

import collections
import hashlib
import json
import logging
import os
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any

from ao_kernel._internal.shared.lock import file_lock
from ao_kernel.config import load_default
from ao_kernel.cost.errors import (
    SpendLedgerCorruptedError,
    SpendLedgerDuplicateError,
)
from ao_kernel.cost.policy import CostTrackingPolicy


logger = logging.getLogger(__name__)


_LEDGER_SCHEMA_CACHE: dict[str, Any] | None = None


def _ledger_schema() -> dict[str, Any]:
    """Load and cache ``spend-ledger.schema.v1.json``."""
    global _LEDGER_SCHEMA_CACHE
    if _LEDGER_SCHEMA_CACHE is None:
        _LEDGER_SCHEMA_CACHE = load_default(
            "schemas", "spend-ledger.schema.v1.json",
        )
    return _LEDGER_SCHEMA_CACHE


@dataclass(frozen=True)
class SpendEvent:
    """One billable LLM call event.

    Fields mirror ``spend-ledger.schema.v1.json`` one-to-one. The
    writer fills ``billing_digest`` lazily (if caller omits) via
    :func:`_compute_billing_digest` before append; operators never
    author ledger events by hand, so the redundant-author path is
    fine to not expose.

    ``cost_usd`` is stored as ``Decimal`` in-process for precision;
    the writer serializes as JSON ``number`` (float) per schema
    contract — acceptable loss since ``billing_digest`` canonicalizes
    via ``str(Decimal(...))`` for idempotency comparison.
    """

    run_id: str
    step_id: str
    attempt: int
    provider_id: str
    model: str
    tokens_input: int
    tokens_output: int
    cost_usd: Decimal
    ts: str  # ISO-8601 with timezone
    vendor_model_id: str | None = None
    cached_tokens: int | None = None
    usage_missing: bool = False
    billing_digest: str = ""  # computed by writer if empty


def compute_billing_digest(event: SpendEvent) -> str:
    """Canonical SHA-256 over billing-relevant fields (public helper).

    Callers that need the digest BEFORE :func:`record_spend` (e.g. to key
    a run-state idempotency marker — see PR-C3.2 marker-driven reconcile)
    MUST precompute via this helper and pass the :class:`SpendEvent` with
    ``billing_digest`` populated. ``record_spend`` itself will recompute
    via :func:`_compute_billing_digest` when ``billing_digest == ""``, so
    legacy callers still work.

    Decimal-stable: ``cost_usd`` is canonicalized via ``str(Decimal(...))``
    so float serialization round-trips do not break the comparison.
    """
    payload = {
        "provider_id": event.provider_id,
        "model": event.model,
        "vendor_model_id": event.vendor_model_id,
        "tokens_input": event.tokens_input,
        "tokens_output": event.tokens_output,
        "cached_tokens": event.cached_tokens,
        "cost_usd": str(Decimal(str(event.cost_usd))),
        "usage_missing": event.usage_missing,
    }
    canonical = json.dumps(
        payload,
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
    )
    return "sha256:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()


# Backward-compat alias — legacy private name retained for existing
# import sites (internal uses + test suite). PR-C3.2 promotes the
# public spelling; both resolve to the same function object.
_compute_billing_digest = compute_billing_digest


def _event_to_dict(event: SpendEvent) -> dict[str, Any]:
    """Serialize ``event`` to a schema-valid dict.

    Optional fields (``vendor_model_id``, ``cached_tokens``) are
    omitted when None to honor schema ``additionalProperties: false``
    + avoid null in the wire.
    """
    out: dict[str, Any] = {
        "run_id": event.run_id,
        "step_id": event.step_id,
        "attempt": event.attempt,
        "provider_id": event.provider_id,
        "model": event.model,
        "tokens_input": event.tokens_input,
        "tokens_output": event.tokens_output,
        "cost_usd": float(event.cost_usd),
        "ts": event.ts,
        "usage_missing": event.usage_missing,
        "billing_digest": event.billing_digest or _compute_billing_digest(event),
    }
    if event.vendor_model_id is not None:
        out["vendor_model_id"] = event.vendor_model_id
    if event.cached_tokens is not None:
        out["cached_tokens"] = event.cached_tokens
    return out


def _validate_event(doc: dict[str, Any]) -> None:
    """Validate an event dict against the ledger schema — fail-closed."""
    from jsonschema import Draft202012Validator

    Draft202012Validator(_ledger_schema()).validate(doc)


def _ledger_path(
    workspace_root: Path,
    policy: CostTrackingPolicy,
) -> Path:
    return workspace_root / policy.spend_ledger_path


def _ledger_lock_path(ledger_path: Path) -> Path:
    return ledger_path.with_suffix(ledger_path.suffix + ".lock")


def _scan_tail(
    ledger_path: Path,
    window_lines: int,
) -> list[dict[str, Any]]:
    """Read the last ``window_lines`` of the ledger and parse.

    Raises :class:`SpendLedgerCorruptedError` on any unparseable line.
    Missing ledger file → empty list (first-write case).
    """
    if not ledger_path.is_file():
        return []
    # Bounded scan: collections.deque(maxlen=N) keeps the last N lines
    # as we iterate — memory bounded even for huge ledgers. For the
    # 1000-line default this is trivial; for 100_000 (policy cap) it
    # still fits in a single-pass read.
    tail: collections.deque[tuple[int, str]] = collections.deque(
        maxlen=window_lines,
    )
    with ledger_path.open("r", encoding="utf-8") as fh:
        for lineno, raw in enumerate(fh, start=1):
            stripped = raw.strip()
            if not stripped:
                continue  # tolerate trailing newline
            tail.append((lineno, stripped))
    parsed: list[dict[str, Any]] = []
    for lineno, line in tail:
        try:
            obj = json.loads(line)
        except json.JSONDecodeError as exc:
            raise SpendLedgerCorruptedError(
                ledger_path=str(ledger_path),
                line_number=lineno,
                reason=f"JSON decode error: {exc}",
            ) from exc
        if not isinstance(obj, dict):
            raise SpendLedgerCorruptedError(
                ledger_path=str(ledger_path),
                line_number=lineno,
                reason=f"line is not a JSON object (got {type(obj).__name__})",
            )
        parsed.append(obj)
    return parsed


def _find_duplicate(
    window: list[dict[str, Any]],
    run_id: str,
    step_id: str,
    attempt: int,
) -> dict[str, Any] | None:
    """Return the matching existing event dict or None."""
    for entry in window:
        if (
            entry.get("run_id") == run_id
            and entry.get("step_id") == step_id
            and entry.get("attempt") == attempt
        ):
            return entry
    return None


def _append_with_fsync(ledger_path: Path, line: str) -> None:
    """Append a single ``line\\n`` to the ledger with fsync.

    We use lock + append + fsync rather than tmp+rename because JSONL
    append-only does not benefit from rename atomicity — the write
    serialization anchor is the file_lock wrapping the call site.
    """
    with ledger_path.open("a", encoding="utf-8") as fh:
        fh.write(line + "\n")
        fh.flush()
        os.fsync(fh.fileno())


def record_spend(
    workspace_root: Path,
    event: SpendEvent,
    *,
    policy: CostTrackingPolicy,
) -> None:
    """Append a spend event with idempotent duplicate protection.

    Short-circuits with a silent no-op when ``policy.enabled=false``
    (dormant gate at the writer as well as the middleware — defensive
    redundancy; the caller should already have filtered, but this
    keeps the contract robust against wire bugs).

    Idempotency:

    - Compute ``billing_digest`` if not pre-filled.
    - Acquire ``{ledger_path}.lock`` (POSIX fcntl via the shared helper).
    - Scan the last ``policy.idempotency_window_lines`` entries.
    - If ``(run_id, step_id, attempt)`` found:
      - same ``billing_digest`` → WARN log, return (no-op).
      - different ``billing_digest`` → :class:`SpendLedgerDuplicateError`.
    - Else: validate schema, canonicalize line, append + fsync.

    Corrupt ledger line encountered during scan →
    :class:`SpendLedgerCorruptedError` (fail-closed).
    """
    if not policy.enabled:
        return  # dormant silent no-op

    ledger_path = _ledger_path(workspace_root, policy)
    ledger_path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)

    # Pre-compute digest so we can compare against existing lines without
    # re-serializing them.
    digest = event.billing_digest or _compute_billing_digest(event)
    if event.billing_digest == "":
        # Inject back into the event for downstream uses (e.g. evidence
        # emit payload). Since SpendEvent is frozen, we rebuild.
        event = SpendEvent(
            run_id=event.run_id,
            step_id=event.step_id,
            attempt=event.attempt,
            provider_id=event.provider_id,
            model=event.model,
            tokens_input=event.tokens_input,
            tokens_output=event.tokens_output,
            cost_usd=event.cost_usd,
            ts=event.ts,
            vendor_model_id=event.vendor_model_id,
            cached_tokens=event.cached_tokens,
            usage_missing=event.usage_missing,
            billing_digest=digest,
        )

    lock_path = _ledger_lock_path(ledger_path)
    lock_path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)

    with file_lock(lock_path):
        window = _scan_tail(ledger_path, policy.idempotency_window_lines)
        existing = _find_duplicate(
            window, event.run_id, event.step_id, event.attempt,
        )
        if existing is not None:
            existing_digest = str(existing.get("billing_digest", ""))
            if existing_digest == digest:
                logger.warning(
                    "spend ledger idempotent no-op: "
                    "(run_id=%s, step_id=%s, attempt=%d) already recorded "
                    "with matching digest %s",
                    event.run_id,
                    event.step_id,
                    event.attempt,
                    digest,
                )
                return
            raise SpendLedgerDuplicateError(
                run_id=event.run_id,
                step_id=event.step_id,
                attempt=event.attempt,
                existing_digest=existing_digest,
                new_digest=digest,
            )

        doc = _event_to_dict(event)
        _validate_event(doc)
        line = json.dumps(
            doc,
            sort_keys=True,
            ensure_ascii=False,
            separators=(",", ":"),
        )
        _append_with_fsync(ledger_path, line)


__all__ = [
    "SpendEvent",
    "record_spend",
]
