"""Cost ceiling enforcement for V5 Epic 2 E-2-3.

This module is infrastructure-only. It records dry-run/stub cost totals, returns
an explicit soft-breach state, and fails closed on hard breach. It never opens a
network socket, never flips a guard flag, and never treats local evidence as a
production claim.

Two operating modes are supported:

- Library mode (``workspace_root is None``): in-memory, single-process state.
- Workspace mode: append-only ``evidence/cost_ceiling_state.jsonl`` plus a
  per-session POSIX sidecar lock, so concurrent recorders serialize the
  read-modify-write cycle.
"""

from __future__ import annotations

import datetime as _dt
import json
import os
import re
import uuid
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path
from typing import Any, Literal, Mapping, NoReturn

from ao_kernel._internal.evidence.per_call_audit import record_call as record_per_call_audit
from ao_kernel._internal.shared.lock import file_lock
from ao_kernel.config import load_default
from ao_kernel.cost.errors import CostCeilingExceeded


BreachState = Literal["ok", "soft_breached", "hard_breached"]
CallMode = Literal["stub", "dry_run", "live"]
CallStatus = Literal["ok", "error", "stub_emitted", "dry_run_emitted"]

_POLICY_NAME = "policy_cost_ceiling.v1.json"
_STATE_JSONL = "cost_ceiling_state.jsonl"
_EIGHT_DP = Decimal("0.00000001")
_ZERO = Decimal("0.00000000")


@dataclass(frozen=True)
class CostCeilingPolicy:
    """Typed policy view for the E-2-3 ceiling defaults."""

    soft_usd: Decimal
    hard_usd: Decimal
    currency: str = "USD"
    version: str = "v1"


def _iso_now() -> str:
    return _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _as_decimal(value: Decimal, *, field: str) -> Decimal:
    if not isinstance(value, Decimal):
        raise TypeError(f"{field} must be Decimal")
    if not value.is_finite():
        raise ValueError(f"{field} must be finite")
    return value


def _format_decimal(value: Decimal) -> str:
    return str(value.quantize(_EIGHT_DP, rounding=ROUND_HALF_UP))


def _safe_session_id(session_id: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", session_id)[:120] or "default"


def _append_jsonl(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    line = (json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n").encode("utf-8")
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
    try:
        os.write(fd, line)
        try:
            os.fsync(fd)
        except OSError:
            pass
    finally:
        os.close(fd)


def _policy_from_doc(doc: Mapping[str, Any]) -> CostCeilingPolicy:
    try:
        soft = Decimal(str(doc["soft_usd"]))
        hard = Decimal(str(doc["hard_usd"]))
    except (KeyError, InvalidOperation) as exc:
        raise ValueError(f"{_POLICY_NAME} must define decimal soft_usd and hard_usd") from exc
    _validate_thresholds(soft, hard)
    currency = str(doc.get("currency", "USD"))
    if currency != "USD":
        raise ValueError("policy_cost_ceiling.v1.json currently supports currency=USD only")
    return CostCeilingPolicy(soft_usd=soft, hard_usd=hard, currency=currency, version=str(doc.get("version", "v1")))


def load_cost_ceiling_policy(*, workspace_root: Path | None = None) -> CostCeilingPolicy:
    """Load the bundled policy, optionally overridden by a workspace policy file.

    Override lookup accepts either project-root shape
    ``{root}/.ao/policies/policy_cost_ceiling.v1.json`` or workspace-dir shape
    ``{root}/policies/policy_cost_ceiling.v1.json``. This mirrors the repo's
    mixed workspace conventions without making E-2-3 depend on a live adapter.
    """
    doc: Mapping[str, Any]
    if workspace_root is not None:
        root = Path(workspace_root)
        for candidate in (
            root / ".ao" / "policies" / _POLICY_NAME,
            root / "policies" / _POLICY_NAME,
        ):
            if candidate.is_file():
                loaded = json.loads(candidate.read_text(encoding="utf-8"))
                if not isinstance(loaded, dict):
                    raise ValueError(f"{candidate} must be a JSON object")
                doc = loaded
                break
        else:
            doc = load_default("policies", _POLICY_NAME)
    else:
        doc = load_default("policies", _POLICY_NAME)
    return _policy_from_doc(doc)


def _validate_thresholds(soft_usd: Decimal, hard_usd: Decimal) -> None:
    _as_decimal(soft_usd, field="soft_usd")
    _as_decimal(hard_usd, field="hard_usd")
    if soft_usd < 0:
        raise ValueError("soft_usd must be non-negative")
    if hard_usd <= 0:
        raise ValueError("hard_usd must be positive")
    if soft_usd > hard_usd:
        raise ValueError("soft_usd must be <= hard_usd")


def _validate_non_negative_cost(cost_usd: Decimal, *, field: str = "cost_usd") -> Decimal:
    cost = _as_decimal(cost_usd, field=field)
    if cost < 0:
        raise ValueError(f"{field} must be non-negative")
    return cost.quantize(_EIGHT_DP, rounding=ROUND_HALF_UP)


def _validate_zero_cost_context(
    cost_usd: Decimal,
    *,
    mode: CallMode,
    status: CallStatus,
    input_tokens: int,
    output_tokens: int,
    price_per_1k_usd: Decimal | None,
) -> None:
    if input_tokens < 0 or output_tokens < 0:
        raise ValueError("token counts must be non-negative")
    if price_per_1k_usd is not None:
        price = _validate_non_negative_cost(price_per_1k_usd, field="price_per_1k_usd")
    else:
        price = None
    if mode == "live" and status == "ok" and cost_usd == _ZERO and (input_tokens + output_tokens) > 0 and price is not None and price > _ZERO:
        raise ValueError("zero-cost suspicious in real provider call")


@dataclass
class Reservation:
    """Pre-reservation handle returned by :meth:`CostCeiling.reserve`."""

    ceiling: "CostCeiling"
    estimated_usd: Decimal
    state: BreachState
    reservation_id: str
    settled: bool = False

    def settle(self, actual_usd: Decimal) -> BreachState:
        """Adjust the reservation to the actual cost exactly once."""
        if self.settled:
            raise ValueError("reservation already settled")
        actual = _validate_non_negative_cost(actual_usd, field="actual_usd")
        delta = actual - self.estimated_usd
        self.settled = True
        if delta == _ZERO:
            return self.ceiling.breach_state()
        return self.ceiling._record_delta(  # noqa: SLF001 - Reservation is the companion API.
            delta,
            operation="settle",
            allow_negative=True,
            reservation_id=self.reservation_id,
        )


class CostCeiling:
    """Operator-configurable soft/hard cost ceiling.

    ``record_call`` accepts a positive Decimal cost and returns ``"ok"`` or
    ``"soft_breached"``. If the attempted cumulative total would exceed the
    hard ceiling, it writes a fail-closed state row, optionally records the
    hard-breach audit row via E-2-2, and raises :class:`CostCeilingExceeded`.
    """

    def __init__(
        self,
        soft_usd: Decimal,
        hard_usd: Decimal,
        *,
        session_id: str | None = None,
        workspace_root: Path | str | None = None,
    ) -> None:
        _validate_thresholds(soft_usd, hard_usd)
        self.soft_usd = soft_usd.quantize(_EIGHT_DP, rounding=ROUND_HALF_UP)
        self.hard_usd = hard_usd.quantize(_EIGHT_DP, rounding=ROUND_HALF_UP)
        self.session_id = session_id or "default"
        self.workspace_root = None if workspace_root is None else Path(workspace_root)
        self._total = _ZERO

    @classmethod
    def from_policy(
        cls,
        *,
        workspace_root: Path | str | None = None,
        session_id: str | None = None,
    ) -> "CostCeiling":
        root = None if workspace_root is None else Path(workspace_root)
        policy = load_cost_ceiling_policy(workspace_root=root)
        return cls(policy.soft_usd, policy.hard_usd, session_id=session_id, workspace_root=root)

    def record_call(
        self,
        cost_usd: Decimal,
        *,
        mode: CallMode = "dry_run",
        status: CallStatus = "ok",
        input_tokens: int = 0,
        output_tokens: int = 0,
        price_per_1k_usd: Decimal | None = None,
        audit_row: Mapping[str, Any] | None = None,
    ) -> BreachState:
        """Record one cost and return explicit breach state.

        ``mode``/token/price arguments exist only for fail-closed validation of
        suspicious zero-cost live contexts. E-2-3 remains dry-run/stub
        infrastructure; live execution authority is not granted here.
        """
        cost = _validate_non_negative_cost(cost_usd)
        _validate_zero_cost_context(
            cost,
            mode=mode,
            status=status,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            price_per_1k_usd=price_per_1k_usd,
        )
        return self._record_delta(cost, operation="record_call", audit_row=audit_row)

    def remaining_usd(self) -> Decimal:
        total = self._current_total()
        remaining = self.hard_usd - total
        return _ZERO if remaining < _ZERO else remaining.quantize(_EIGHT_DP, rounding=ROUND_HALF_UP)

    def breach_state(self) -> BreachState:
        total = self._current_total()
        if total > self.hard_usd:
            return "hard_breached"
        if total > self.soft_usd:
            return "soft_breached"
        return "ok"

    def assert_under_hard(self) -> None:
        total = self._current_total()
        if total > self.hard_usd:
            raise CostCeilingExceeded(
                session_id=self.session_id,
                attempted_cost_usd=_ZERO,
                cumulative_before_usd=total,
                attempted_cumulative_usd=total,
                hard_usd=self.hard_usd,
                state_path=self._state_path() if self.workspace_root is not None else None,
            )

    def reserve(self, estimated_usd: Decimal) -> Reservation:
        estimate = _validate_non_negative_cost(estimated_usd, field="estimated_usd")
        reservation_id = str(uuid.uuid4())
        state = self._record_delta(estimate, operation="reserve", reservation_id=reservation_id)
        return Reservation(
            ceiling=self,
            estimated_usd=estimate,
            state=state,
            reservation_id=reservation_id,
        )

    def _record_delta(
        self,
        delta_usd: Decimal,
        *,
        operation: str,
        allow_negative: bool = False,
        audit_row: Mapping[str, Any] | None = None,
        reservation_id: str | None = None,
    ) -> BreachState:
        delta = _as_decimal(delta_usd, field="delta_usd").quantize(_EIGHT_DP, rounding=ROUND_HALF_UP)
        if delta < 0 and not allow_negative:
            raise ValueError("delta_usd must be non-negative")
        if self.workspace_root is None:
            before = self._total
            after = before + delta
            if after < _ZERO:
                raise ValueError("cost ceiling total cannot become negative")
            if after > self.hard_usd:
                self._raise_hard_breach(
                    audit_row=audit_row,
                    cost_usd=delta,
                    before=before,
                    after=after,
                    state_path=None,
                )
            self._total = after
            return "soft_breached" if after > self.soft_usd else "ok"

        lock_path = self._lock_path()
        with file_lock(lock_path):
            before = self._read_latest_accepted_total_unlocked()
            after = before + delta
            if after < _ZERO:
                raise ValueError("cost ceiling total cannot become negative")
            if after > self.hard_usd:
                self._append_state_unlocked(
                    before=before,
                    attempted_after=after,
                    delta=delta,
                    breach_state="hard_breached",
                    accepted=False,
                    operation=operation,
                    reservation_id=reservation_id,
                )
                self._raise_hard_breach(
                    audit_row=audit_row,
                    cost_usd=delta,
                    before=before,
                    after=after,
                    state_path=self._state_path(),
                )
            state: BreachState = "soft_breached" if after > self.soft_usd else "ok"
            self._append_state_unlocked(
                before=before,
                attempted_after=after,
                delta=delta,
                breach_state=state,
                accepted=True,
                operation=operation,
                reservation_id=reservation_id,
            )
            return state

    def _record_hard_breach_audit(self, audit_row: Mapping[str, Any] | None, cost_usd: Decimal) -> None:
        if audit_row is None:
            return
        row = dict(audit_row)
        row["status"] = "error"
        row["cost_breach_state"] = "hard_breached"
        row["cost_breach_handling"] = None
        row["actual_cost_usd"] = _format_decimal(cost_usd if cost_usd >= _ZERO else _ZERO)
        record_per_call_audit(row, workspace_root=self.workspace_root)

    def _raise_hard_breach(
        self,
        *,
        audit_row: Mapping[str, Any] | None,
        cost_usd: Decimal,
        before: Decimal,
        after: Decimal,
        state_path: Path | None,
    ) -> NoReturn:
        audit_error: Exception | None = None
        try:
            self._record_hard_breach_audit(audit_row, cost_usd)
        except Exception as exc:
            audit_error = exc

        failure = CostCeilingExceeded(
            session_id=self.session_id,
            attempted_cost_usd=cost_usd,
            cumulative_before_usd=before,
            attempted_cumulative_usd=after,
            hard_usd=self.hard_usd,
            state_path=state_path,
        )
        if audit_error is not None:
            raise failure from audit_error
        raise failure

    def _current_total(self) -> Decimal:
        if self.workspace_root is None:
            return self._total
        with file_lock(self._lock_path()):
            return self._read_latest_accepted_total_unlocked()

    def _state_path(self) -> Path:
        if self.workspace_root is None:
            raise ValueError("state path is only available in workspace mode")
        return Path(self.workspace_root) / "evidence" / _STATE_JSONL

    def _lock_path(self) -> Path:
        if self.workspace_root is None:
            raise ValueError("lock path is only available in workspace mode")
        return Path(self.workspace_root) / "evidence" / f"cost_ledger.{_safe_session_id(self.session_id)}.lock"

    def _read_latest_accepted_total_unlocked(self) -> Decimal:
        path = self._state_path()
        total = _ZERO
        if not path.exists():
            return total
        for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"corrupt cost ceiling state JSONL at line {line_number}") from exc
            if row.get("session_id") != self.session_id or row.get("accepted") is not True:
                continue
            total = Decimal(str(row["cumulative_after_usd"]))
        return total.quantize(_EIGHT_DP, rounding=ROUND_HALF_UP)

    def _append_state_unlocked(
        self,
        *,
        before: Decimal,
        attempted_after: Decimal,
        delta: Decimal,
        breach_state: BreachState,
        accepted: bool,
        operation: str,
        reservation_id: str | None,
    ) -> None:
        payload: dict[str, Any] = {
            "schema_version": "cost-ceiling-state.v1",
            "artifact_kind": "cost_ceiling_state",
            "session_id": self.session_id,
            "operation": operation,
            "reservation_id": reservation_id,
            "delta_usd": _format_decimal(delta),
            "cumulative_before_usd": _format_decimal(before),
            "cumulative_after_usd": _format_decimal(attempted_after if accepted else before),
            "attempted_cumulative_after_usd": _format_decimal(attempted_after),
            "soft_usd": _format_decimal(self.soft_usd),
            "hard_usd": _format_decimal(self.hard_usd),
            "breach_state": breach_state,
            "accepted": accepted,
            "live_adapter_execution": False,
            "support_widening": False,
            "production_platform_claim": False,
            "recorded_at": _iso_now(),
        }
        _append_jsonl(self._state_path(), payload)


__all__ = [
    "BreachState",
    "CallMode",
    "CallStatus",
    "CostCeiling",
    "CostCeilingPolicy",
    "Reservation",
    "load_cost_ceiling_policy",
]
