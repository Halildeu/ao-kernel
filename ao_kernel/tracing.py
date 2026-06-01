"""W3C trace context propagation + session correlation primitives.

V5 Epic 5 E-5-3a (Codex thread 019e8360 absorb) — sub-slice of
"distributed tracing (multi-session correlation)". This module ships
the W3C trace-context propagation primitives the cross-session
consultation lifecycle will later use (E-5-3b follow-up PR).

Scope of THIS PR (E-5-3a)
-------------------------

This module is helper-only. It does NOT yet:

- emit consultation request/response trace_context fields,
- attach trace metadata to the canonical store,
- promote any guard flag.

It only exposes primitives the consultation integration slice (E-5-3b)
will wire in. Until E-5-3b lands, the ``multi-session correlation``
end-to-end behavior is not in effect — only the primitives are
testable.

Public surface
--------------

- ``is_otel_available()``: lazy probe, no module-level side effects.
- ``inject_trace_context(carrier)``: W3C ``traceparent`` (+ optional
  ``tracestate``) inject into ``carrier`` *only when* the calling
  thread has an active recording span. Returns the same carrier dict
  for chaining. No active span → carrier is returned unchanged.
- ``extract_trace_context(carrier)``: extract OTEL ``Context`` from
  the carrier. Returns ``None`` when OTEL is absent OR the carrier
  contains no ``traceparent``.
- ``attach_context(ctx)`` / ``detach_context(token)``: token-based
  attach/detach pair. Use the ``traced_context`` context manager
  whenever possible to avoid leak.
- ``traced_context(ctx)``: context manager that attaches ``ctx`` and
  detaches at exit.
- ``session_baggage(session_id)``: context manager that sets the
  ``ao.session.id`` OTEL baggage entry for the duration of the
  block. Empty/whitespace session_id rejected with ``ValueError``.
- ``get_session_baggage()``: returns the current ``ao.session.id``
  baggage value or ``None``.
- ``get_current_trace_id()``: 32-hex ``trace_id`` of the active
  recording span, or ``None``.
- ``get_current_span_id()``: 16-hex ``span_id`` of the active
  recording span, or ``None``.
- ``make_link(trace_id_hex, span_id_hex, attributes=None)``: builds
  an OTEL ``Link`` referencing another span across traces. This is
  NOT parent-context propagation; spans with only a link still live
  in their original trace.

Design (Codex 019e8360 absorb)
------------------------------

- ``inject`` never fabricates a ``traceparent`` when no span is active
  (matches W3C standard propagator behavior).
- ``tracestate`` is optional; tests do not require it to appear.
- Baggage exposure is intentional: session_id is non-secret. If your
  workflow archives baggage to disk, treat ``ao.session.id`` as a
  routing field, not a secret.
- ``make_link`` is exposed because consultation chains may want to
  reference an existing trace from a brand-new local trace without
  collapsing both into one (e.g. async fan-out across sessions).
- The module is the SOLE facade for ``opentelemetry.{trace,context,
  propagate,baggage}`` imports in V5; no other ao_kernel module
  imports from those packages directly.
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Iterator

# Lazy availability cache. Independent of ``ao_kernel.telemetry`` to
# keep the surface minimal (Codex 019e8360 absorb — clean separation).
_OTEL_AVAILABLE: bool | None = None

# OTEL baggage key for the active ao-kernel session id.
SESSION_BAGGAGE_KEY = "ao.session.id"

# W3C traceparent shape (lowercase 32-hex trace_id, 16-hex span_id).
_TRACE_ID_HEX_LEN = 32
_SPAN_ID_HEX_LEN = 16
_HEX_CHARS = frozenset("0123456789abcdef")


def is_otel_available() -> bool:
    """Return True when ``opentelemetry`` is importable.

    Lazy probe; caches the result so repeated calls are cheap.
    """
    global _OTEL_AVAILABLE
    if _OTEL_AVAILABLE is not None:
        return _OTEL_AVAILABLE
    try:
        import opentelemetry.trace  # noqa: F401
        import opentelemetry.context  # noqa: F401
        import opentelemetry.propagate  # noqa: F401
        import opentelemetry.baggage  # noqa: F401

        _OTEL_AVAILABLE = True
    except ImportError:
        _OTEL_AVAILABLE = False
    return _OTEL_AVAILABLE


def _reset_otel_cache_for_testing() -> None:
    """Reset the lazy availability cache. ONLY for unit tests."""
    global _OTEL_AVAILABLE
    _OTEL_AVAILABLE = None


def _validate_hex(value: str, expected_len: int, field_name: str) -> None:
    if not isinstance(value, str):
        raise ValueError(f"{field_name} must be a string; got {type(value).__name__}")
    if len(value) != expected_len:
        raise ValueError(f"{field_name} must be {expected_len} hex chars; got length {len(value)}")
    # Codex 019e8360 iter-2 absorb — reject uppercase explicitly.
    # W3C traceparent is lowercase only; ``"A" * 32`` would otherwise
    # silently pass since uppercase A is not in _HEX_CHARS but lower()
    # would have masked the case rejection.
    if not set(value).issubset(_HEX_CHARS):
        raise ValueError(f"{field_name} must be lowercase hex; got {value!r}")
    # Codex 019e8360 iter-2 absorb — reject all-zero ids. A zero
    # SpanContext fails ``is_valid`` and would yield an unusable Link;
    # reject at the validation boundary so callers get a clear error.
    if int(value, 16) == 0:
        raise ValueError(f"{field_name} must not be all-zero; got {value!r}")


# ── W3C inject / extract ────────────────────────────────────────────


def inject_trace_context(carrier: dict[str, str]) -> dict[str, str]:
    """Inject the active span's W3C trace context into ``carrier``.

    When no recording span is active OR when OTEL is not installed,
    ``carrier`` is returned unchanged (Codex 019e8360 absorb —
    matches W3C standard propagator behavior).

    Args:
        carrier: dict to receive ``traceparent`` (and optionally
            ``tracestate``). Mutated in place AND returned for
            chaining. Other keys preserved.

    Returns:
        The same ``carrier`` instance.
    """
    if not isinstance(carrier, dict):
        raise TypeError(f"carrier must be dict[str, str]; got {type(carrier).__name__}")
    if not is_otel_available():
        return carrier

    from opentelemetry.propagate import inject

    inject(carrier)
    return carrier


def extract_trace_context(carrier: dict[str, str]) -> Any | None:
    """Extract OTEL ``Context`` from the W3C carrier dict.

    Returns ``None`` when OTEL is absent, when the carrier contains
    no ``traceparent`` key, OR when the extracted span context fails
    ``is_valid`` (malformed traceparent value).

    Carrier-key contract (Codex 019e8360 iter-2 absorb): this function
    accepts the **lowercase W3C JSON carrier form**, i.e. exactly the
    key ``"traceparent"`` (optionally ``"tracestate"``). HTTP header
    objects with title-case keys (e.g. ``"Traceparent"``) are NOT
    case-normalized here; callers that bridge from HTTP frameworks
    should lowercase keys before passing the carrier in. This keeps
    the contract identical to the inject side, where the default
    OTEL propagator emits lowercase keys.
    """
    if not isinstance(carrier, dict):
        raise TypeError(f"carrier must be dict[str, str]; got {type(carrier).__name__}")
    if not is_otel_available():
        return None
    if "traceparent" not in carrier:
        return None

    from opentelemetry.propagate import extract
    from opentelemetry.trace import get_current_span

    ctx = extract(carrier)
    # Codex 019e8360 iter-2 absorb — guard against malformed
    # traceparent producing a non-None but invalid context. Callers
    # use ``if ctx is not None`` and would otherwise get a false
    # positive for an unusable extracted span.
    span = get_current_span(ctx)
    span_ctx = span.get_span_context()
    if span_ctx is None or not span_ctx.is_valid:
        return None
    return ctx


# ── attach / detach + traced_context manager ────────────────────────


def attach_context(ctx: Any) -> Any:
    """Attach ``ctx`` as the current OTEL context; returns a token.

    The caller MUST eventually pass the token to ``detach_context``.
    Prefer ``traced_context(ctx)`` context manager to avoid leak.
    """
    if not is_otel_available():
        return None
    if ctx is None:
        return None

    from opentelemetry.context import attach

    return attach(ctx)


def detach_context(token: Any) -> None:
    """Detach a previously attached context."""
    if token is None or not is_otel_available():
        return

    from opentelemetry.context import detach

    detach(token)


@contextmanager
def traced_context(ctx: Any) -> Iterator[None]:
    """Attach ``ctx`` for the duration of the ``with`` block.

    Safe pairing of attach/detach (Codex 019e8360 absorb — token-less
    setters are forbidden; this manager enforces clean detach).
    """
    token = attach_context(ctx)
    try:
        yield
    finally:
        detach_context(token)


# ── Session baggage ──────────────────────────────────────────────────


@contextmanager
def session_baggage(session_id: str) -> Iterator[None]:
    """Set ``ao.session.id`` baggage for the duration of the block.

    ``session_id`` must be a non-empty, non-whitespace string. The
    baggage is non-secret; treat as a routing field, not credential.
    """
    if not isinstance(session_id, str):
        raise ValueError(f"session_id must be a string; got {type(session_id).__name__}")
    if not session_id.strip():
        raise ValueError("session_id must be non-empty, non-whitespace")
    if not is_otel_available():
        yield
        return

    from opentelemetry.baggage import set_baggage

    ctx = set_baggage(SESSION_BAGGAGE_KEY, session_id)
    with traced_context(ctx):
        yield


def get_session_baggage() -> str | None:
    """Return the current ``ao.session.id`` baggage value, or None."""
    if not is_otel_available():
        return None
    from opentelemetry.baggage import get_baggage

    value = get_baggage(SESSION_BAGGAGE_KEY)
    if value is None:
        return None
    return str(value)


# ── Current span id helpers ──────────────────────────────────────────


def _current_span_context() -> Any | None:
    """Return the current span's ``SpanContext`` or None."""
    if not is_otel_available():
        return None
    from opentelemetry.trace import get_current_span

    span = get_current_span()
    if span is None:
        return None
    span_ctx = span.get_span_context()
    if span_ctx is None or not span_ctx.is_valid:
        return None
    return span_ctx


def get_current_trace_id() -> str | None:
    """Return the 32-hex ``trace_id`` of the active recording span."""
    span_ctx = _current_span_context()
    if span_ctx is None:
        return None
    trace_id = span_ctx.trace_id
    if trace_id == 0:
        return None
    return f"{trace_id:032x}"


def get_current_span_id() -> str | None:
    """Return the 16-hex ``span_id`` of the active recording span."""
    span_ctx = _current_span_context()
    if span_ctx is None:
        return None
    span_id = span_ctx.span_id
    if span_id == 0:
        return None
    return f"{span_id:016x}"


# ── Cross-trace Link helper ──────────────────────────────────────────


def make_link(
    trace_id_hex: str,
    span_id_hex: str,
    attributes: dict[str, Any] | None = None,
) -> Any | None:
    """Build an OTEL ``Link`` referencing another span across traces.

    NOT parent-context propagation. A span with only a link still
    lives in its original trace; the link records a cross-trace
    relationship (e.g. ``follows_from`` async fan-out).

    Returns ``None`` when OTEL is absent.

    Raises:
        ValueError: when ``trace_id_hex`` or ``span_id_hex`` is not
            lowercase hex of the expected length.
    """
    _validate_hex(trace_id_hex, _TRACE_ID_HEX_LEN, "trace_id_hex")
    _validate_hex(span_id_hex, _SPAN_ID_HEX_LEN, "span_id_hex")
    if not is_otel_available():
        return None

    from opentelemetry.trace import Link, NonRecordingSpan, SpanContext, TraceFlags

    span_ctx = SpanContext(
        trace_id=int(trace_id_hex, 16),
        span_id=int(span_id_hex, 16),
        is_remote=True,
        trace_flags=TraceFlags(TraceFlags.SAMPLED),
    )
    # NonRecordingSpan is the lightweight carrier; we only need the
    # context for the Link payload.
    _ = NonRecordingSpan(span_ctx)
    return Link(span_ctx, attributes=attributes or {})
