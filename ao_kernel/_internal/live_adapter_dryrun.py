"""Dry-run live-adapter evidence harness (V5 Epic 2 E-2-4).

This module builds real E-2-1/E-2-2 evidence shapes while emitting only a
deterministic stub response. It is infrastructure-only:

- no provider network call is made,
- no secret material is read or serialized,
- ``live_adapter_execution`` / ``support_widening`` /
  ``production_platform_claim`` remain false.

The runtime kill-switch is intentionally broad. It patches common network,
subprocess, shell, and native-library escape hatches while dry-run evidence is
being built. Optional third-party libraries are patched only when installed.
"""

from __future__ import annotations

import argparse
import contextlib
import datetime as dt
import hashlib
import http.client
import importlib
import json
import os
import socket
import subprocess
import sys
import threading
import urllib.request
import uuid
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path
from types import TracebackType
from typing import Any, Callable, Literal, Mapping

from jsonschema import Draft202012Validator

from ao_kernel._internal.evidence.per_call_audit import record_call as record_per_call_audit
from ao_kernel.config import load_default
from ao_kernel.cost import CostCeiling, CostCeilingExceeded

_ENVELOPE_SCHEMA = "live_adapter_envelope.schema.v1.json"
_AUDIT_SCHEMA = "per_call_audit.schema.v1.json"
_POLICY_NAME = "policy_cost_ceiling.v1.json"
_EIGHT_DP = Decimal("0.00000001")
_ZERO = Decimal("0.00000000")
_STUB_TEXT = "AO-KERNEL LIVE ADAPTER DRY-RUN STUB RESPONSE"
_SECRET_BOUNDARY = "no_secret_material_emitted_no_token_no_credential"


class DryRunKillSwitchError(RuntimeError):
    """Raised when dry-run code attempts a forbidden side effect."""


class DryRunSchemaError(ValueError):
    """Raised when generated dry-run evidence fails schema validation."""


@dataclass(frozen=True)
class DryRunResult:
    """Result returned by :func:`run_live_adapter_dryrun`."""

    envelope: dict[str, Any]
    audit_row: dict[str, Any]
    envelope_path: Path
    audit_receipt: dict[str, Any]
    cost_breach_state: str
    workspace_root: Path | None


RestoreCallback = Callable[[], None]
_KILLSWITCH_LOCK = threading.RLock()
_KILLSWITCH_ACTIVE_COUNT = 0
_KILLSWITCH_RESTORE: list[RestoreCallback] = []


def _deny(target: str) -> Callable[..., Any]:
    def _raise(*_args: Any, **_kwargs: Any) -> Any:
        raise DryRunKillSwitchError(f"network call attempted by dry-run kill-switch: {target}")

    return _raise


class DryRunKillSwitches:
    """Context manager that blocks network/subprocess bypass paths."""

    def __init__(self) -> None:
        self._entered = False

    def __enter__(self) -> "DryRunKillSwitches":
        global _KILLSWITCH_ACTIVE_COUNT
        with _KILLSWITCH_LOCK:
            if _KILLSWITCH_ACTIVE_COUNT == 0:
                _KILLSWITCH_RESTORE.clear()
                try:
                    self._install()
                except BaseException:
                    self._restore_all()
                    raise
            _KILLSWITCH_ACTIVE_COUNT += 1
            self._entered = True
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        global _KILLSWITCH_ACTIVE_COUNT
        del exc_type, exc, tb
        with _KILLSWITCH_LOCK:
            if not self._entered:
                return
            self._entered = False
            _KILLSWITCH_ACTIVE_COUNT -= 1
            if _KILLSWITCH_ACTIVE_COUNT == 0:
                self._restore_all()

    @staticmethod
    def _restore_all() -> None:
        while _KILLSWITCH_RESTORE:
            restore = _KILLSWITCH_RESTORE.pop()
            restore()

    def _patch_attr(self, obj: Any, name: str, value: Any) -> None:
        sentinel = object()
        original = getattr(obj, name, sentinel)
        setattr(obj, name, value)

        def _restore() -> None:
            if original is sentinel:
                with contextlib.suppress(AttributeError):
                    delattr(obj, name)
            else:
                setattr(obj, name, original)

        _KILLSWITCH_RESTORE.append(_restore)

    def _patch_optional(self, module_name: str, patcher: Callable[[Any], None]) -> None:
        with contextlib.suppress(ImportError):
            patcher(importlib.import_module(module_name))

    def _install(self) -> None:
        self._patch_socket()
        self._patch_subprocess()
        self._patch_os_exec()
        self._patch_http_stdlib()
        self._patch_optional_http_clients()
        self._patch_native_libs()

    def _patch_socket(self) -> None:
        # Patch the class method first so pre-captured ``socket.socket`` aliases
        # are still blocked; then replace the module-level constructor too.
        self._patch_attr(socket.socket, "connect", _deny("socket.socket.connect"))
        self._patch_attr(socket, "socket", _deny("socket.socket"))
        self._patch_attr(socket, "create_connection", _deny("socket.create_connection"))

    def _patch_subprocess(self) -> None:
        self._patch_attr(subprocess.Popen, "__init__", _deny("subprocess.Popen"))
        for name in ("run", "call", "check_output", "check_call"):
            self._patch_attr(subprocess, name, _deny(f"subprocess.{name}"))

    def _patch_os_exec(self) -> None:
        for name in (
            "system",
            "popen",
            "spawnl",
            "spawnle",
            "spawnlp",
            "spawnlpe",
            "spawnv",
            "spawnve",
            "spawnvp",
            "spawnvpe",
            "execl",
            "execle",
            "execlp",
            "execlpe",
            "execv",
            "execve",
            "execvp",
            "execvpe",
        ):
            if hasattr(os, name):
                self._patch_attr(os, name, _deny(f"os.{name}"))

    def _patch_http_stdlib(self) -> None:
        self._patch_attr(urllib.request, "urlopen", _deny("urllib.request.urlopen"))
        self._patch_attr(http.client.HTTPConnection, "request", _deny("http.client.HTTPConnection.request"))
        self._patch_attr(http.client.HTTPSConnection, "request", _deny("http.client.HTTPSConnection.request"))

    def _patch_optional_http_clients(self) -> None:
        def _httpx(httpx: Any) -> None:
            self._patch_attr(httpx.Client, "send", _deny("httpx.Client.send"))
            self._patch_attr(httpx.AsyncClient, "send", _deny("httpx.AsyncClient.send"))
            self._patch_attr(httpx, "stream", _deny("httpx.stream"))

        def _urllib3(urllib3: Any) -> None:
            pool = urllib3.connectionpool.HTTPConnectionPool
            self._patch_attr(pool, "_make_request", _deny("urllib3.HTTPConnectionPool._make_request"))

        def _requests(requests: Any) -> None:
            self._patch_attr(requests.api, "request", _deny("requests.api.request"))

        def _aiohttp(aiohttp: Any) -> None:
            self._patch_attr(aiohttp.ClientSession, "_request", _deny("aiohttp.ClientSession._request"))

        self._patch_optional("httpx", _httpx)
        self._patch_optional("urllib3", _urllib3)
        self._patch_optional("requests", _requests)
        self._patch_optional("aiohttp", _aiohttp)

    def _patch_native_libs(self) -> None:
        def _ctypes(ctypes: Any) -> None:
            self._patch_attr(ctypes, "CDLL", _deny("ctypes.CDLL"))

        def _cffi(cffi: Any) -> None:
            self._patch_attr(cffi, "FFI", _deny("cffi.FFI"))

        self._patch_optional("ctypes", _ctypes)
        self._patch_optional("cffi", _cffi)


def install_dry_run_killswitches() -> DryRunKillSwitches:
    """Return a context manager that blocks dry-run side effects."""

    return DryRunKillSwitches()


def _iso_now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _canonical_bytes(payload: Mapping[str, Any]) -> bytes:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _sha256_text(payload: str) -> str:
    return _sha256_bytes(payload.encode("utf-8"))


def _format_decimal(value: Decimal) -> str:
    return format(value.quantize(_EIGHT_DP, rounding=ROUND_HALF_UP), "f")


def _parse_decimal(value: str, *, field: str) -> Decimal:
    try:
        parsed = Decimal(value)
    except InvalidOperation as exc:
        raise ValueError(f"{field} must be a decimal string") from exc
    if not parsed.is_finite() or parsed < _ZERO:
        raise ValueError(f"{field} must be a finite non-negative decimal string")
    return parsed.quantize(_EIGHT_DP, rounding=ROUND_HALF_UP)


def _schema_validator(schema_name: str) -> Draft202012Validator:
    return Draft202012Validator(load_default("schemas", schema_name))


def _validate_payload(payload: dict[str, Any], *, schema_name: str) -> None:
    errors = sorted(_schema_validator(schema_name).iter_errors(payload), key=lambda err: list(err.absolute_path))
    if errors:
        joined = "; ".join(f"{'/'.join(str(p) for p in err.absolute_path) or '<root>'}: {err.message}" for err in errors)
        raise DryRunSchemaError(f"{schema_name} validation failed: {joined}")


def _pricing_source_digest() -> str:
    policy = load_default("policies", _POLICY_NAME)
    return "sha256:" + _sha256_bytes(_canonical_bytes(policy))


def _compute_envelope_digest(envelope: Mapping[str, Any]) -> str:
    unsigned = dict(envelope)
    unsigned.pop("envelope_digest", None)
    return _sha256_bytes(_canonical_bytes(unsigned))


def build_dry_run_envelope(
    *,
    provider_id: str,
    model: str,
    intent: str,
    request_id: str | None = None,
    prompt: str = "",
    max_tokens: int = 256,
    temperature: float = 0.0,
    cost_usd: Decimal = _ZERO,
) -> dict[str, Any]:
    """Build and validate one E-2-1 dry-run envelope."""

    request_uuid = request_id or str(uuid.uuid4())
    now = _iso_now()
    cost = _format_decimal(cost_usd)
    input_tokens = 0
    output_tokens = 0
    envelope: dict[str, Any] = {
        "schema_version": "live-adapter-envelope.v1",
        "artifact_kind": "live_adapter_envelope",
        "envelope_digest": "0" * 64,
        "mode": "dry_run",
        "live_adapter_execution": False,
        "support_widening": False,
        "production_platform_claim": False,
        "request": {
            "provider_id": provider_id,
            "model": model,
            "request_id": request_uuid,
            "intent": intent,
            "messages_digest": _sha256_text(prompt),
            "params": {"temperature": temperature, "max_tokens": max_tokens},
        },
        "response": {
            "text_digest": _sha256_text(_STUB_TEXT),
            "usage": {
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "total_tokens": input_tokens + output_tokens,
            },
            "latency_ms": 0.0,
            "status": "dry_run_emitted",
        },
        "cost": {
            "currency": "USD",
            "input_cost_per_1k_usd": "0.00000000",
            "output_cost_per_1k_usd": "0.00000000",
            "actual_cost_usd": cost,
            "pricing_source_digest": _pricing_source_digest(),
        },
        "circuit_breaker": {"state": "CLOSED", "failure_count": 0, "last_failure_at": None},
        "secret_boundary": _SECRET_BOUNDARY,
        "timestamps": {"created_at": now, "finalized_at": now},
    }
    envelope["envelope_digest"] = _compute_envelope_digest(envelope)
    _validate_payload(envelope, schema_name=_ENVELOPE_SCHEMA)
    return envelope


def build_per_call_audit_row(envelope: Mapping[str, Any], *, cost_breach_state: str) -> dict[str, Any]:
    """Build and validate the E-2-2 audit row bound to ``envelope``."""

    response = envelope["response"]
    request = envelope["request"]
    cost = envelope["cost"]
    row: dict[str, Any] = {
        "schema_version": "per-call-audit.v1",
        "artifact_kind": "per_call_audit",
        "envelope_digest": envelope["envelope_digest"],
        "provider_id": request["provider_id"],
        "model": request["model"],
        "request_id": request["request_id"],
        "intent": request["intent"],
        "input_tokens": response["usage"]["input_tokens"],
        "output_tokens": response["usage"]["output_tokens"],
        "total_tokens": response["usage"]["total_tokens"],
        "actual_cost_usd": cost["actual_cost_usd"],
        "latency_ms": int(response["latency_ms"]),
        "status": response["status"],
        "cost_breach_state": cost_breach_state,
        "live_adapter_execution": False,
        "support_widening": False,
        "production_platform_claim": False,
        "recorded_at": envelope["timestamps"]["finalized_at"],
    }
    if cost_breach_state == "soft_breached":
        row["cost_breach_handling"] = {
            "decision": "deferred",
            "decided_by": "policy_default",
            "decided_at": envelope["timestamps"]["finalized_at"],
        }
    elif cost_breach_state == "hard_breached":
        row["status"] = "error"
        row["cost_breach_handling"] = None
    _validate_payload(row, schema_name=_AUDIT_SCHEMA)
    return row


def _infer_workspace_root(output: Path, workspace_root: Path | None) -> Path | None:
    if workspace_root is not None:
        return workspace_root
    parent = output.parent
    if parent.name == "evidence":
        return parent.parent
    return None


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    rendered = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    tmp_path = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        fd = os.open(tmp_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write(rendered)
                handle.flush()
                os.fsync(handle.fileno())
        except BaseException:
            with contextlib.suppress(OSError):
                os.close(fd)
            raise
        os.replace(tmp_path, path)
        with contextlib.suppress(OSError):
            directory_fd = os.open(path.parent, os.O_RDONLY)
            try:
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)
    finally:
        with contextlib.suppress(FileNotFoundError):
            tmp_path.unlink()
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass


def run_live_adapter_dryrun(
    *,
    provider_id: str,
    model: str,
    intent: str,
    output: Path,
    prompt: str = "",
    workspace_root: Path | None = None,
    dry_run_cost_usd: Decimal = _ZERO,
    session_id: str = "e-2-4-dry-run",
    max_tokens: int = 256,
    temperature: float = 0.0,
) -> DryRunResult:
    """Run the dry-run harness and write one envelope artifact."""

    output_path = Path(output)
    resolved_workspace = _infer_workspace_root(output_path, workspace_root)
    with install_dry_run_killswitches():
        envelope = build_dry_run_envelope(
            provider_id=provider_id,
            model=model,
            intent=intent,
            prompt=prompt,
            max_tokens=max_tokens,
            temperature=temperature,
            cost_usd=dry_run_cost_usd,
        )
        state: Literal["ok", "soft_breached", "hard_breached", "not_applicable"]
        if dry_run_cost_usd == _ZERO:
            state = "not_applicable"
        else:
            provisional_row = build_per_call_audit_row(envelope, cost_breach_state="ok")
            state = CostCeiling.from_policy(workspace_root=resolved_workspace, session_id=session_id).record_call(
                dry_run_cost_usd,
                mode="dry_run",
                status="dry_run_emitted",
                audit_row=provisional_row,
            )
        audit_row = build_per_call_audit_row(envelope, cost_breach_state=state)
        audit_receipt = record_per_call_audit(audit_row, workspace_root=resolved_workspace)
        _write_json(output_path, envelope)
    return DryRunResult(
        envelope=envelope,
        audit_row=audit_row,
        envelope_path=output_path,
        audit_receipt=audit_receipt,
        cost_breach_state=state,
        workspace_root=resolved_workspace,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Emit a no-network live-adapter dry-run envelope.")
    parser.add_argument("--provider", required=True, dest="provider_id", help="Provider id to record in the envelope.")
    parser.add_argument("--model", required=True, help="Model id to record in the envelope.")
    parser.add_argument("--intent", required=True, help="Intent label to record in the envelope.")
    parser.add_argument("--output", required=True, type=Path, help="Envelope artifact output path.")
    parser.add_argument("--prompt", default="", help="Prompt text to digest; never serialized verbatim.")
    parser.add_argument("--workspace-root", type=Path, default=None, help="Optional workspace root for JSONL evidence.")
    parser.add_argument("--session-id", default="e-2-4-dry-run", help="Cost ceiling session id.")
    parser.add_argument("--max-tokens", type=int, default=256, help="Dry-run request max_tokens metadata.")
    parser.add_argument("--temperature", type=float, default=0.0, help="Dry-run request temperature metadata.")
    parser.add_argument(
        "--dry-run-cost-usd",
        default="0.00000000",
        help="Decimal-string simulated dry-run cost; defaults to zero.",
    )
    parser.add_argument("--output-format", choices=("json", "text"), default="json", help="Stdout format.")
    return parser


def _render_text(result: DryRunResult) -> str:
    workspace = str(result.workspace_root) if result.workspace_root is not None else "library"
    return "\n".join(
        [
            "live-adapter dry-run: ok",
            f"envelope: {result.envelope_path}",
            f"envelope_digest: {result.envelope['envelope_digest']}",
            f"cost_breach_state: {result.cost_breach_state}",
            f"workspace: {workspace}",
            "live_adapter_execution: false",
            "support_widening: false",
            "production_platform_claim: false",
        ]
    )


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        cost = _parse_decimal(args.dry_run_cost_usd, field="dry_run_cost_usd")
        result = run_live_adapter_dryrun(
            provider_id=args.provider_id,
            model=args.model,
            intent=args.intent,
            output=args.output,
            prompt=args.prompt,
            workspace_root=args.workspace_root,
            dry_run_cost_usd=cost,
            session_id=args.session_id,
            max_tokens=args.max_tokens,
            temperature=args.temperature,
        )
    except CostCeilingExceeded as exc:
        print(f"cost ceiling breached: {exc}", file=sys.stderr)
        return 2
    except (DryRunKillSwitchError, DryRunSchemaError, ValueError, OSError) as exc:
        print(f"live-adapter dry-run failed: {exc}", file=sys.stderr)
        return 1

    if args.output_format == "json":
        print(
            json.dumps(
                {
                    "status": "ok",
                    "envelope_path": str(result.envelope_path),
                    "envelope_digest": result.envelope["envelope_digest"],
                    "audit_receipt": result.audit_receipt,
                    "cost_breach_state": result.cost_breach_state,
                    "workspace_root": str(result.workspace_root) if result.workspace_root is not None else None,
                    "live_adapter_execution": False,
                    "support_widening": False,
                    "production_platform_claim": False,
                },
                indent=2,
                sort_keys=True,
            )
        )
    else:
        print(_render_text(result))
    return 0


__all__ = [
    "DryRunKillSwitchError",
    "DryRunKillSwitches",
    "DryRunResult",
    "DryRunSchemaError",
    "build_dry_run_envelope",
    "build_per_call_audit_row",
    "install_dry_run_killswitches",
    "main",
    "run_live_adapter_dryrun",
]
