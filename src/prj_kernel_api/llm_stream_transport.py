"""Streaming HTTP transport — SSE execution with circuit breaker, guardrails, evidence.

Parallel to llm_transport.execute_http_request but yields chunks instead of buffering.
Uses stdlib urllib only. No httpx dependency.

Retry policy:
- Before first semantic event: transport errors are retried (connection, DNS, HTTP 429/503)
- After first event received: NO retry (mid-stream). Returns PARTIAL with accumulated text.

Circuit breaker:
- Checked before request (same as non-streaming)
- PARTIAL result counts as failure
"""

from __future__ import annotations

import json
import socket
import ssl
import time
from dataclasses import dataclass, field
from typing import Any, Callable
from urllib import error as url_error
from urllib import request as url_request

from src.prj_kernel_api.llm_stream import StreamEvent, iter_stream_events
from src.prj_kernel_api.llm_transport import redact_secrets, resolve_tls_context


@dataclass
class StreamResult:
    """Result of a streaming HTTP request."""

    status: str                           # OK | PARTIAL | FAIL
    complete: bool = False                # True only if stream finished normally
    text: str = ""                        # Full accumulated text
    finish_reason: str = "unknown"        # stop | stream_error | timeout | cancelled | connect_error
    usage: dict[str, int] | None = None
    elapsed_ms: int = 0
    first_token_ms: int | None = None
    chunk_count: int = 0
    error_code: str | None = None
    error_detail: str | None = None
    circuit_state: dict[str, Any] = field(default_factory=dict)
    events: list[dict[str, Any]] | None = None  # Only populated if capture_events=True


def execute_stream_request(
    *,
    url: str,
    headers: dict[str, str],
    body_bytes: bytes,
    timeout_seconds: float,
    provider_id: str,
    request_id: str,
    on_chunk: Callable[[StreamEvent], bool | None] | None = None,
    capture_events: bool = False,
    max_output_chars: int = 500_000,
    max_events: int = 50_000,
    idle_timeout_seconds: float = 30.0,
) -> StreamResult:
    """Execute a streaming HTTP POST request via urllib.

    Args:
        on_chunk: Called for each StreamEvent. Return False to cancel stream.
        capture_events: If True, raw events stored in result.events.
        max_output_chars: Hard limit on accumulated text length.
        max_events: Hard limit on event count.
        idle_timeout_seconds: Max seconds between events before timeout.

    Returns:
        StreamResult with accumulated text and metadata.
    """
    from src.prj_kernel_api.circuit_breaker import get_circuit_breaker

    cb = get_circuit_breaker(provider_id)
    allowed, reason = cb.allow_request()
    if not allowed:
        return StreamResult(
            status="FAIL",
            finish_reason="circuit_open",
            error_code="CIRCUIT_OPEN",
            error_detail=f"Circuit breaker {reason} for {provider_id}",
            circuit_state=cb.status_dict(),
        )

    tls_context, _ = resolve_tls_context()
    req = url_request.Request(url, data=body_bytes, headers=headers, method="POST")

    start = time.monotonic()
    first_token_time: float | None = None
    accumulated_text: list[str] = []
    total_chars = 0
    chunk_count = 0
    usage: dict[str, int] | None = None
    captured: list[dict[str, Any]] = [] if capture_events else None
    error_code: str | None = None
    error_detail: str | None = None
    finish_reason = "unknown"
    complete = False

    try:
        resp = url_request.urlopen(req, timeout=timeout_seconds, context=tls_context)

        # Validate Content-Type
        content_type = resp.headers.get("Content-Type", "")
        if "text/event-stream" not in content_type and "application/x-ndjson" not in content_type:
            body = resp.read(4096)
            return StreamResult(
                status="FAIL",
                finish_reason="invalid_content_type",
                error_code="STREAM_INVALID_CONTENT_TYPE",
                error_detail=f"Expected text/event-stream, got: {content_type}",
                text=body.decode("utf-8", errors="replace")[:500],
                elapsed_ms=_elapsed_ms(start),
                circuit_state=cb.status_dict(),
            )

        # Set socket-level idle timeout
        raw_sock = _get_raw_socket(resp)
        if raw_sock and idle_timeout_seconds:
            raw_sock.settimeout(idle_timeout_seconds)

        for event in iter_stream_events(resp, provider_id, capture_raw=capture_events):
            chunk_count += 1

            # First token timing
            if first_token_time is None and event.text:
                first_token_time = time.monotonic()

            # Capture events for evidence
            if captured is not None and event.raw is not None:
                captured.append(event.raw)

            # Stream lifecycle
            if event.event_type == "done":
                complete = True
                finish_reason = "stop"
                break

            if event.event_type == "error":
                error_code = "STREAM_PROVIDER_ERROR"
                error_detail = event.text[:400]
                finish_reason = "stream_error"
                break

            # Usage extraction
            if event.event_type == "usage" and event.raw:
                from src.prj_kernel_api.llm_stream import extract_stream_usage
                u = extract_stream_usage(event.raw, provider_id)
                if u:
                    usage = u

            # Text accumulation
            if event.text:
                accumulated_text.append(event.text)
                total_chars += len(event.text)

            # Callback — return False to cancel
            if on_chunk is not None:
                should_continue = on_chunk(event)
                if should_continue is False:
                    finish_reason = "cancelled"
                    break

            # Guardrails
            if total_chars >= max_output_chars:
                error_code = "STREAM_MAX_OUTPUT_CHARS"
                finish_reason = "stream_error"
                break
            if chunk_count >= max_events:
                error_code = "STREAM_MAX_EVENTS"
                finish_reason = "stream_error"
                break

    except url_error.HTTPError as exc:
        http_status = getattr(exc, "code", 0)
        error_code = f"STREAM_HTTP_{http_status}"
        error_detail = redact_secrets(str(exc))[:400]
        finish_reason = "connect_error"
    except socket.timeout:
        if chunk_count > 0:
            finish_reason = "timeout"
            error_code = "STREAM_IDLE_TIMEOUT"
        else:
            finish_reason = "connect_error"
            error_code = "STREAM_CONNECT_TIMEOUT"
    except (ConnectionError, OSError) as exc:
        if chunk_count > 0:
            finish_reason = "stream_error"
            error_code = "STREAM_CONNECTION_LOST"
        else:
            finish_reason = "connect_error"
            error_code = "STREAM_CONNECTION_ERROR"
        error_detail = redact_secrets(str(exc))[:400]
    except Exception as exc:
        finish_reason = "stream_error"
        error_code = "STREAM_UNEXPECTED_ERROR"
        error_detail = redact_secrets(str(exc))[:400]

    elapsed = _elapsed_ms(start)
    full_text = "".join(accumulated_text)

    # Determine status
    if complete:
        status = "OK"
    elif full_text and not complete:
        status = "PARTIAL"
    else:
        status = "FAIL"

    # Circuit breaker update
    if status == "OK":
        cb.record_success()
    else:
        cb.record_failure(Exception(f"{error_code}: {finish_reason}"))

    return StreamResult(
        status=status,
        complete=complete,
        text=full_text,
        finish_reason=finish_reason,
        usage=usage,
        elapsed_ms=elapsed,
        first_token_ms=_elapsed_ms_from(start, first_token_time) if first_token_time else None,
        chunk_count=chunk_count,
        error_code=error_code,
        error_detail=error_detail,
        circuit_state=cb.status_dict(),
        events=captured,
    )


def _elapsed_ms(start: float) -> int:
    return int(round((time.monotonic() - start) * 1000.0))


def _elapsed_ms_from(start: float, end: float) -> int:
    return int(round((end - start) * 1000.0))


def _get_raw_socket(resp) -> socket.socket | None:
    """Extract underlying socket for idle timeout setting."""
    try:
        fp = getattr(resp, "fp", None)
        raw = getattr(fp, "raw", None) if fp else None
        sock = getattr(raw, "_sock", None) if raw else None
        return sock
    except Exception:
        return None
