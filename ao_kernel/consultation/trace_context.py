"""Consultation trace-context sidecar helpers (V5 Epic 5 E-5-3b).

Non-authoritative correlation metadata. Records W3C trace context captured
at consultation archive time so cross-session traces can be linked at query
time via ``ao_kernel.tracing.make_link``.

Codex 019e83ee cross-AI plan-time AGREE (3 iters: REVISE/REVISE/AGREE).

Design contract:

- The sidecar JSON file (``consultation_trace_context.v1.json``) is
  written into each CNS evidence directory at archive time when an
  OTEL recording span is active. If no recording span is active, no
  sidecar is written (degrades silently).
- Sidecar writes are **idempotent first-write**: if the file exists,
  it is not overwritten. This pins the trace correlation to the first
  archive run that produced an active context.
- The sidecar is **non-authoritative correlation metadata**. It is NOT
  added to the consultation integrity manifest. Tampered or
  schema-invalid sidecars are silently ignored by the query path.
- ``make_link`` is used at query time (bounded pre-scan up to
  ``MAX_CONSULTATION_TRACE_LINKS``) to link the active query span to
  the original archive spans across traces. Invalid hex or
  schema-invalid sidecars are skipped without raising.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Codex absorb: bounded cap to keep span link payload size predictable.
MAX_CONSULTATION_TRACE_LINKS: int = 10

# Filename pinned for schema lookup + test parity.
SIDECAR_FILENAME = "consultation_trace_context.v1.json"
SCHEMA_VERSION = "consultation-trace-context.v1"


def capture_current_trace_context() -> dict[str, Any] | None:
    """Return W3C trace context for the active recording span, else None.

    Codex 019e83ee absorb (F4 + H3):
    - Returns None if OTEL is not installed (ImportError/AttributeError).
    - Returns None when no recording span is active.
    - Reads via ``ao_kernel.tracing`` facade only; no direct OTEL imports
      outside that facade.
    """
    try:
        from ao_kernel.tracing import (
            get_current_span_id,
            get_current_trace_id,
            get_session_baggage,
            inject_trace_context,
        )
    except (ImportError, AttributeError):
        return None

    trace_id = get_current_trace_id()
    span_id = get_current_span_id()
    if not trace_id or not span_id:
        return None

    carrier: dict[str, str] = {}
    inject_trace_context(carrier)
    traceparent = carrier.get("traceparent")
    if not traceparent:
        return None

    return {
        "trace_id": trace_id,
        "span_id": span_id,
        "traceparent": traceparent,
        "tracestate": carrier.get("tracestate"),
        "session_id_baggage": get_session_baggage(),
    }


def maybe_write_sidecar(cns_evidence_dir: Path, cns_id: str) -> Path | None:
    """Write the sidecar artifact for this CNS at archive time.

    Idempotent first-write: if the sidecar already exists, return its path
    without overwriting (Codex F4 H1 absorb: digest-independent, never
    overwrite).

    Returns:
        Sidecar path if the file exists after this call (either freshly
        written or pre-existing), else None when no active span context
        is available.
    """
    sidecar_path = cns_evidence_dir / SIDECAR_FILENAME
    if sidecar_path.exists():
        return sidecar_path

    ctx = capture_current_trace_context()
    if ctx is None:
        return None

    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "cns_id": cns_id,
        "captured_at_archive_time": True,
        "trace_id": ctx["trace_id"],
        "span_id": ctx["span_id"],
        "traceparent": ctx["traceparent"],
        "tracestate": ctx.get("tracestate"),
        "session_id_baggage": ctx.get("session_id_baggage"),
    }

    # Use repo's atomic JSON writer pattern (Codex H1 hardening absorb).
    try:
        from ao_kernel._internal.shared.utils import write_json_atomic

        write_json_atomic(sidecar_path, payload)
    except (ImportError, AttributeError):
        # Fallback: still atomic via tmp + replace
        tmp = sidecar_path.with_suffix(".tmp")
        tmp.write_text(json.dumps(payload, indent=2, sort_keys=True))
        tmp.replace(sidecar_path)

    return sidecar_path


def _validate_sidecar_shape(data: Any) -> bool:
    """Lightweight schema validation for the link-read path.

    Returns True only if the data has the shape required to produce a
    cross-trace link. Stricter validation lives in the JSON schema; this
    inline check is the runtime gatekeeper for the read path so the
    query never imports jsonschema in the hot path.
    """
    if not isinstance(data, dict):
        return False
    if data.get("schema_version") != SCHEMA_VERSION:
        return False
    trace_id = data.get("trace_id")
    span_id = data.get("span_id")
    if not isinstance(trace_id, str) or not isinstance(span_id, str):
        return False
    # Hex shape + non-all-zero (mirror schema invariants).
    if len(trace_id) != 32 or not all(c in "0123456789abcdef" for c in trace_id):
        return False
    if len(span_id) != 16 or not all(c in "0123456789abcdef" for c in span_id):
        return False
    if trace_id == "0" * 32 or span_id == "0" * 16:
        return False
    return True


def read_sidecar_trace_links(cns_dirs: list[Path]) -> list[Any]:
    """Build a bounded list of OTEL Links from CNS sidecar trace contexts.

    Codex F4 absorb: bounded pre-scan up to ``MAX_CONSULTATION_TRACE_LINKS``.
    Invalid / tampered / schema-invalid sidecars are silently skipped
    (preserves the mature consultation "malformed store content skip"
    tolerance pattern).

    Returns:
        List of OTEL Link objects (length <= MAX_CONSULTATION_TRACE_LINKS).
        Returns ``[]`` if OTEL is not installed or no valid sidecars found.
    """
    try:
        from ao_kernel.tracing import make_link
    except (ImportError, AttributeError):
        return []

    links: list[Any] = []
    capped = cns_dirs[:MAX_CONSULTATION_TRACE_LINKS]
    for cns_dir in capped:
        sidecar = cns_dir / SIDECAR_FILENAME
        if not sidecar.is_file():
            continue
        try:
            data = json.loads(sidecar.read_text())
        except (OSError, json.JSONDecodeError):
            continue
        if not _validate_sidecar_shape(data):
            continue
        try:
            link = make_link(data["trace_id"], data["span_id"])
        except ValueError:
            # Codex absorb: wrapper catches make_link ValueError (invalid hex);
            # make_link semantics in ao_kernel.tracing remain unchanged.
            continue
        if link is not None:
            links.append(link)
    return links
