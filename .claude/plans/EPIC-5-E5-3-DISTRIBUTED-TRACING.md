# Epic 5 E-5-3a — Distributed Tracing Primitives (W3C trace context)

**Status:** Implementing (sub-slice E-5-3a only).
**Codex thread:** `019e8360` (plan-time REVISE, sub-slice split + 10
must-close revize absorbed).
**Slice:** E-5-3a (this PR) ⊂ V5 Epic 5 E-5-3.
**Out-of-scope (E-5-3b follow-up PR):** consultation request/response
schema `trace_context` field + producer/consumer trace propagation +
canonical store trace metadata + same-trace_id roundtrip integration
tests.

## 1. Sorun

V5 Epic 5 E-5-3 plan: "Distributed tracing (multi-session
correlation)". Mevcut `ao_kernel/telemetry.py` lazy OTEL + 5 span
name'i destekliyor; ama:

- W3C trace context propagation primitive YOK
- Cross-session correlation için baggage / link API YOK
- Consultation request/response trace context taşımıyor
- Multi-session AO-MA chain'i tek distributed trace olarak görünmüyor

E-5-3 helper module + consultation integration **iki ayrı concern**.
Tek PR'da yapmak "helper" ile "lifecycle" mantığını karıştırır.

## 2. Codex iter-1 absorb (REVISE → sub-slice split)

| Konu | Codex bulgu | Absorb |
|---|---|---|
| Scope | Tek PR'da scope sızıntısı | Sub-slice split — E-5-3a (this PR) helper-only; E-5-3b consultation integration ayrı PR |
| `inject` aktif span yokken | W3C standart: traceparent fabrikasyon YOK | Test "no active span → carrier preserved" pin; aktif span altında inject pin |
| `tracestate` zorunluluğu | W3C'de opsiyonel | Test "varsa preserve" der, "her zaman var" demez |
| `set_session_baggage` API | Global setter context leak riski | Context manager `session_baggage(session_id)` + tokensız setter YOK |
| `link_to` semantic | "Tek trace" iddiası yanlış | Doc + name `make_link` cross-trace reference; parent-context propagation DEĞİL |
| Plan doc public claim | "Production-grade distributed tracing" marketing | Plan doc'ta 3 guard flag false invariant + non-claim wording |
| Baggage key | `ao_session_id` vs `ao.session.id` | `ao.session.id` (noktalı namespace; OTEL convention) |
| `link_to` `kind` parametresi | OTEL Link standart'ında YOK | Custom attribute `{"ao.link.kind": "follows_from"}` |
| Lazy import cache | `telemetry._check_otel` paylaşmak | Ayrı `_OTEL_AVAILABLE` cache (clean separation) |
| Attach/detach API | Context leak riski | Token-based + `traced_context` ContextManager |
| Test strategy | SDK provider zorunlu mu? | `NonRecordingSpan + SpanContext + set_span_in_context` deterministic roundtrip; SDK gerek YOK; `pytest.importorskip` pattern |

## 3. E-5-3a değişiklik scope

### 3a. `ao_kernel/tracing.py` (yeni; 281 satır)

Lazy OTEL import + no-op fallback. Public API:

| Symbol | Tip | Kontrat |
|---|---|---|
| `SESSION_BAGGAGE_KEY` | const | `"ao.session.id"` |
| `is_otel_available()` | function | Lazy probe + cache |
| `_reset_otel_cache_for_testing()` | function | Test-only |
| `inject_trace_context(carrier)` | function | W3C inject; no active span → carrier unchanged |
| `extract_trace_context(carrier)` | function | W3C extract → OTEL Context veya None |
| `attach_context(ctx)` | function | OTEL attach; token döner |
| `detach_context(token)` | function | OTEL detach |
| `traced_context(ctx)` | context manager | Attach/detach symmetric |
| `session_baggage(session_id)` | context manager | Set `ao.session.id`; empty reject ValueError |
| `get_session_baggage()` | function | Current `ao.session.id` veya None |
| `get_current_trace_id()` | function | 32-hex veya None |
| `get_current_span_id()` | function | 16-hex veya None |
| `make_link(trace_id_hex, span_id_hex, attributes=None)` | function | OTEL Link cross-trace; hex validate |

Sole facade rule: bu repo'da `opentelemetry.{trace,context,
propagate,baggage}` import'ları **yalnız** `ao_kernel.tracing` veya
`ao_kernel.telemetry` üzerinden geçer.

### 3b. `ao_kernel/telemetry.py` extension

`span()` signature `(name, attributes=None, links=None)` —
backward-compat. `links` `None` default; OTEL `start_as_current_span`
`links=` parameter'a pass-through.

### 3c. `tests/test_tracing.py` (yeni; 25 test)

Test grupları:
- is_otel_available smoke (2)
- inject/extract no-op fallback (4)
- inject no active span behavior (2)
- inject/extract roundtrip with synthetic span context (1)
- traced_context attach/detach symmetry (2)
- session baggage roundtrip + reject empty/whitespace/non-string (5)
- session baggage no-op when OTEL absent (1)
- session baggage key constant (1)
- current trace/span id None outside span (1)
- make_link validation + no-op + Link object (6)

OTEL absent path: `monkeypatch.setattr(tracing, "_OTEL_AVAILABLE", False)`.
OTEL present path: `NonRecordingSpan` + `SpanContext` +
`set_span_in_context` (SDK provider gerek YOK).

### 3d. Plan doc — this file.

## 4. Out-of-scope (E-5-3b follow-up PR)

| Konu | E-5-3b'de |
|---|---|
| Consultation request/response schema `trace_context` field (optional) | Schema additionalProperties:false; ek properties pinli |
| Producer trace context inject — request writer | Active span'tan inject carrier'a |
| Consumer trace context extract — response reader | Carrier'dan extract + child span parent context |
| Implementation stage span correlation | Request/response context altında child span |
| Archive/normalization trace metadata preservation | Canonical store trace metadata; release authority değil |
| Integration test: same trace_id across request → response → impl | E2E roundtrip pin |

## 5. Risk + Mitigation

| Risk | Mitigation |
|---|---|
| Context leak (token-less setter) | API tasarımında YASAK; `traced_context` + `session_baggage` context manager |
| W3C drift (traceparent format) | Hex validation + `_TRACE_ID_HEX_LEN`/`_SPAN_ID_HEX_LEN` const pin |
| Generator tool / spec version drift | `SESSION_BAGGAGE_KEY` const + test pin |
| OTEL absent durumda exception | Lazy import + no-op fallback + test "no raise" |
| Marketing claim (production-grade) | Plan doc explicit invariant; doc'ta "primitives only" qualifier |
| Cross-trace ambiguity (`link` vs `parent`) | `make_link` docstring: "NOT parent-context propagation" |
| Baggage size limits | E-5-3a sadece session_id (small string); E-5-3b'de büyük field pin'lenmeli |

## 6. Acceptance

- ✅ `pytest tests/test_tracing.py -x` → 25 pass local
- ✅ `ruff check ao_kernel/tracing.py ao_kernel/telemetry.py tests/test_tracing.py` clean
- ✅ `mypy ao_kernel/tracing.py ao_kernel/telemetry.py --ignore-missing-imports` clean
- ✅ Plan doc — this file
- ⏳ Cross-AI post-impl review (Codex thread `019e8360` reply ile yeni iter)
- ⏳ CI green (PR taksonomi extension already merged; gate should pass with reviewer evidence)
- ⏳ Squash merge audit trail: Implementer Anthropic Claude / Reviewer OpenAI Codex

## 7. Public claim discipline

> Per Codex 019e8360 absorb — plan doc does NOT make marketing
> claims, does NOT promote guard flags, and explicitly records:

- `support_widening_allowed=false`
- `production_platform_claim_allowed=false`
- `live_adapter_execution_allowed=false`

> E-5-3a adds W3C trace-context propagation primitives and records no
> support widening, no production platform claim, and no live adapter
> execution authority. Multi-session correlation end-to-end behavior
> is NOT yet in effect — only the primitives are testable. E-5-3b
> ships the consultation integration.

## 8. Bağlantı

- V5 Epic 5 plan: `V5-FULL-PRODUCTION-PROMOTION-ROADMAP.md` §3 (Epic
  5 Observability).
- Predecessor: Epic 5 E-5-1 OTEL prod tunables (PR #791, merged).
- HARD RULE — Cross-AI Peer Review: implementer Anthropic Claude;
  reviewer OpenAI Codex (thread `019e8360`).
- HARD RULE — Uzun Vadeli Kalıcı Çözüm: API tasarımında context
  leak risk (token-less setter) yasak; W3C standart davranışına
  uyum; OTEL Link semantic ayrımı (parent vs link).
- HARD RULE — Continuous Autonomous Mode: bu turun 6. PR'ı (793 ✓ +
  794/795/796 pipeline + 764 unblock + bu E-5-3a) — cross-AI peer
  reviewed sequential.
