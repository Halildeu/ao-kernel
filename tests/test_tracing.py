"""Unit tests for ``ao_kernel.tracing`` (V5 Epic 5 E-5-3a).

Strategy:

- No-op fallback path: monkeypatch availability cache to False; verify
  every primitive degrades cleanly.
- OTEL present path: rely on ``opentelemetry.trace`` API (no SDK
  provider required). Use ``NonRecordingSpan`` + ``SpanContext`` +
  ``set_span_in_context`` for deterministic traceparent roundtrip.
- Baggage context manager: assert ``ao.session.id`` set/cleared
  symmetrically.
- Cross-trace link: validate hex shape, build OTEL Link, attribute
  pass-through.
"""

from __future__ import annotations

from typing import Any

import pytest

from ao_kernel import tracing


# ── Helper fixtures ──────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def _reset_otel_cache() -> Any:
    """Reset the lazy availability cache before + after each test."""
    tracing._reset_otel_cache_for_testing()
    yield
    tracing._reset_otel_cache_for_testing()


def _force_otel_absent(monkeypatch: pytest.MonkeyPatch) -> None:
    """Pin ``is_otel_available()`` to False for no-op path tests."""
    monkeypatch.setattr(tracing, "_OTEL_AVAILABLE", False)


# ── is_otel_available smoke ──────────────────────────────────────────


def test_is_otel_available_reflects_actual_installation() -> None:
    # In the dev environment the [otel] extra is installed; in lean
    # CI it is not. Either way, the function returns a bool.
    assert isinstance(tracing.is_otel_available(), bool)


def test_is_otel_available_caches_result() -> None:
    first = tracing.is_otel_available()
    second = tracing.is_otel_available()
    assert first is second


# ── inject / extract — no-op fallback ────────────────────────────────


def test_inject_returns_carrier_unchanged_when_otel_absent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _force_otel_absent(monkeypatch)
    carrier: dict[str, str] = {"X-Other": "value"}
    result = tracing.inject_trace_context(carrier)
    assert result is carrier
    assert result == {"X-Other": "value"}


def test_extract_returns_none_when_otel_absent(monkeypatch: pytest.MonkeyPatch) -> None:
    _force_otel_absent(monkeypatch)
    assert tracing.extract_trace_context({"traceparent": "00-1-2-01"}) is None


def test_inject_non_dict_rejected() -> None:
    with pytest.raises(TypeError, match="carrier must be dict"):
        tracing.inject_trace_context("not-a-dict")  # type: ignore[arg-type]


def test_extract_non_dict_rejected() -> None:
    with pytest.raises(TypeError, match="carrier must be dict"):
        tracing.extract_trace_context("not-a-dict")  # type: ignore[arg-type]


# ── inject — no active span (Codex 019e8360 absorb) ──────────────────


def test_inject_returns_carrier_unchanged_without_active_span() -> None:
    """W3C standard propagator behavior — when no recording span is
    active, the propagator does not fabricate a traceparent.
    """
    if not tracing.is_otel_available():
        pytest.skip("OTEL not installed; covered by absent-fallback test")
    carrier: dict[str, str] = {"X-Other": "preserve-me"}
    tracing.inject_trace_context(carrier)
    # carrier should still hold the unrelated key; traceparent may
    # exist with a zero/invalid context but Codex absorb says we do
    # not require its absence (some propagators emit a vendor-empty
    # value). Critical pin: other keys are preserved.
    assert carrier.get("X-Other") == "preserve-me"


def test_extract_returns_none_when_carrier_has_no_traceparent() -> None:
    if not tracing.is_otel_available():
        pytest.skip("OTEL not installed; covered by absent-fallback test")
    assert tracing.extract_trace_context({"X-Other": "value"}) is None


# ── inject / extract roundtrip with synthetic active span ────────────


def _make_synthetic_context(trace_id_hex: str, span_id_hex: str) -> Any:
    """Build a non-recording OTEL context with a known SpanContext."""
    from opentelemetry.trace import NonRecordingSpan, SpanContext, TraceFlags, set_span_in_context

    span_ctx = SpanContext(
        trace_id=int(trace_id_hex, 16),
        span_id=int(span_id_hex, 16),
        is_remote=False,
        trace_flags=TraceFlags(TraceFlags.SAMPLED),
    )
    span = NonRecordingSpan(span_ctx)
    return set_span_in_context(span)


def test_inject_extract_roundtrip_preserves_trace_id() -> None:
    if not tracing.is_otel_available():
        pytest.skip("OTEL not installed")

    trace_id = "0af7651916cd43dd8448eb211c80319c"
    span_id = "b7ad6b7169203331"
    ctx = _make_synthetic_context(trace_id, span_id)

    with tracing.traced_context(ctx):
        carrier: dict[str, str] = {}
        tracing.inject_trace_context(carrier)
        assert "traceparent" in carrier
        # W3C traceparent: 00-<32hex>-<16hex>-<flags>
        parts = carrier["traceparent"].split("-")
        assert len(parts) == 4
        assert parts[0] == "00"
        assert parts[1] == trace_id
        assert parts[2] == span_id

    # Round-trip — extract from another scope and verify the trace_id
    # survives the carrier serialization.
    extracted_ctx = tracing.extract_trace_context(carrier)
    assert extracted_ctx is not None
    with tracing.traced_context(extracted_ctx):
        assert tracing.get_current_trace_id() == trace_id
        assert tracing.get_current_span_id() == span_id


# ── traced_context manager — attach + detach symmetry ───────────────


def test_traced_context_attaches_and_detaches_cleanly() -> None:
    if not tracing.is_otel_available():
        pytest.skip("OTEL not installed")
    trace_id = "11111111111111111111111111111111"
    span_id = "2222222222222222"
    outer_before = tracing.get_current_trace_id()
    ctx = _make_synthetic_context(trace_id, span_id)
    with tracing.traced_context(ctx):
        assert tracing.get_current_trace_id() == trace_id
    # On exit, the context must be detached.
    assert tracing.get_current_trace_id() == outer_before


def test_traced_context_does_nothing_with_none_ctx() -> None:
    # No-op behavior when ctx is None; must not raise.
    with tracing.traced_context(None):
        assert tracing.get_current_trace_id() == tracing.get_current_trace_id()


# ── session baggage ──────────────────────────────────────────────────


def test_session_baggage_set_and_get_roundtrip() -> None:
    if not tracing.is_otel_available():
        pytest.skip("OTEL not installed")
    with tracing.session_baggage("session-abc"):
        assert tracing.get_session_baggage() == "session-abc"
    # baggage cleared after context exit
    assert tracing.get_session_baggage() is None


def test_session_baggage_rejects_empty_session_id() -> None:
    with pytest.raises(ValueError, match="non-empty"):
        with tracing.session_baggage(""):
            pass


def test_session_baggage_rejects_whitespace_session_id() -> None:
    with pytest.raises(ValueError, match="non-empty"):
        with tracing.session_baggage("   "):
            pass


def test_session_baggage_rejects_non_string() -> None:
    with pytest.raises(ValueError, match="must be a string"):
        with tracing.session_baggage(123):  # type: ignore[arg-type]
            pass


def test_session_baggage_no_op_when_otel_absent(monkeypatch: pytest.MonkeyPatch) -> None:
    _force_otel_absent(monkeypatch)
    # Must not raise even without OTEL; baggage just isn't recorded.
    with tracing.session_baggage("session-xyz"):
        assert tracing.get_session_baggage() is None
    assert tracing.get_session_baggage() is None


def test_session_baggage_key_constant() -> None:
    """Pin the OTEL baggage key — namespaced + lowercase."""
    assert tracing.SESSION_BAGGAGE_KEY == "ao.session.id"


# ── get_current_trace_id / span_id ──────────────────────────────────


def test_current_trace_id_none_outside_span(monkeypatch: pytest.MonkeyPatch) -> None:
    _force_otel_absent(monkeypatch)
    assert tracing.get_current_trace_id() is None
    assert tracing.get_current_span_id() is None


# ── make_link — cross-trace reference ───────────────────────────────


def test_make_link_validates_trace_id_hex_length() -> None:
    with pytest.raises(ValueError, match="trace_id_hex must be 32 hex"):
        tracing.make_link("abc", "b7ad6b7169203331")


def test_make_link_validates_span_id_hex_length() -> None:
    with pytest.raises(ValueError, match="span_id_hex must be 16 hex"):
        tracing.make_link("0af7651916cd43dd8448eb211c80319c", "short")


def test_make_link_validates_hex_chars() -> None:
    with pytest.raises(ValueError, match="lowercase hex"):
        tracing.make_link("g" * 32, "b7ad6b7169203331")


def test_make_link_validates_non_string() -> None:
    with pytest.raises(ValueError, match="must be a string"):
        tracing.make_link(12345, "b7ad6b7169203331")  # type: ignore[arg-type]


def test_make_link_returns_none_when_otel_absent(monkeypatch: pytest.MonkeyPatch) -> None:
    _force_otel_absent(monkeypatch)
    result = tracing.make_link("0af7651916cd43dd8448eb211c80319c", "b7ad6b7169203331")
    assert result is None


def test_make_link_returns_link_object_when_otel_available() -> None:
    if not tracing.is_otel_available():
        pytest.skip("OTEL not installed")
    from opentelemetry.trace import Link

    link = tracing.make_link(
        "0af7651916cd43dd8448eb211c80319c",
        "b7ad6b7169203331",
        attributes={"ao.link.kind": "follows_from"},
    )
    assert isinstance(link, Link)
    # Link should carry the supplied attributes verbatim.
    assert link.attributes is not None
    assert link.attributes.get("ao.link.kind") == "follows_from"
    # Context should reflect the requested trace_id / span_id.
    assert link.context.trace_id == int("0af7651916cd43dd8448eb211c80319c", 16)
    assert link.context.span_id == int("b7ad6b7169203331", 16)


def test_make_link_accepts_empty_attributes() -> None:
    if not tracing.is_otel_available():
        pytest.skip("OTEL not installed")
    link = tracing.make_link(
        "0af7651916cd43dd8448eb211c80319c",
        "b7ad6b7169203331",
    )
    assert link is not None
    # Codex 019e8360 iter-2 absorb — Link context must be remote and
    # valid (cross-trace SpanContext convention).
    assert link.context.is_remote is True
    assert link.context.is_valid is True


# ── Codex 019e8360 iter-2 absorb — extra invariants ─────────────────


def test_make_link_rejects_uppercase_hex() -> None:
    """W3C traceparent is lowercase only. Uppercase A-F must reject."""
    with pytest.raises(ValueError, match="lowercase hex"):
        tracing.make_link("A" * 32, "b7ad6b7169203331")
    with pytest.raises(ValueError, match="lowercase hex"):
        tracing.make_link("0af7651916cd43dd8448eb211c80319c", "B" * 16)


def test_make_link_rejects_all_zero_trace_id() -> None:
    """All-zero trace_id fails is_valid in OTEL; reject at validation."""
    with pytest.raises(ValueError, match="must not be all-zero"):
        tracing.make_link("0" * 32, "b7ad6b7169203331")


def test_make_link_rejects_all_zero_span_id() -> None:
    """All-zero span_id fails is_valid in OTEL; reject at validation."""
    with pytest.raises(ValueError, match="must not be all-zero"):
        tracing.make_link("0af7651916cd43dd8448eb211c80319c", "0" * 16)


def test_extract_returns_none_for_malformed_traceparent() -> None:
    """Codex 019e8360 iter-2 absorb — invalid traceparent value used
    to silently pass through extract(); we now guard against the
    resulting invalid span context."""
    if not tracing.is_otel_available():
        pytest.skip("OTEL not installed")
    # Random non-W3C string in the traceparent slot
    assert tracing.extract_trace_context({"traceparent": "not-a-valid-traceparent"}) is None
    # Wrong version byte
    assert (
        tracing.extract_trace_context({"traceparent": "ff-0af7651916cd43dd8448eb211c80319c-b7ad6b7169203331-01"})
        is None
    )
    # All-zero ids
    assert (
        tracing.extract_trace_context({"traceparent": "00-00000000000000000000000000000000-b7ad6b7169203331-01"})
        is None
    )


def test_extract_ignores_title_case_traceparent_per_contract() -> None:
    """Carrier-key contract is lowercase W3C JSON form. Title-case
    'Traceparent' must NOT be extracted (Codex 019e8360 iter-2
    absorb — caller must lowercase HTTP headers first)."""
    if not tracing.is_otel_available():
        pytest.skip("OTEL not installed")
    # Title-case key is ignored by this surface
    assert (
        tracing.extract_trace_context({"Traceparent": "00-0af7651916cd43dd8448eb211c80319c-b7ad6b7169203331-01"})
        is None
    )


def test_inject_does_not_fabricate_traceparent_without_active_span() -> None:
    """Codex 019e8360 iter-2 absorb — when no recording span is
    active, the default OTEL propagator MUST NOT add a traceparent
    key to the carrier. Previous test only asserted unrelated keys
    were preserved; this one pins the must-close invariant directly."""
    if not tracing.is_otel_available():
        pytest.skip("OTEL not installed")
    carrier: dict[str, str] = {}
    tracing.inject_trace_context(carrier)
    assert "traceparent" not in carrier, "default propagator must not fabricate traceparent when no active span"


def test_attach_context_with_none_returns_none() -> None:
    """attach_context(None) returns None (no token); detach_context(None) is a no-op."""
    assert tracing.attach_context(None) is None
    # detach with None token must not raise
    tracing.detach_context(None)
