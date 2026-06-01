# V5 Epic 5 E-5-3b: Consultation Tracing Integration

> **Cross-AI plan-time AGREE** — Codex thread `019e83ee` (3 iters: REVISE/REVISE/AGREE)
> **Implementer:** Anthropic Claude / **Reviewer:** OpenAI Codex
> **Risk class:** path-sensitive runtime + evidence-store-adjacent (NOT low-risk)

## 1. Scope

Integrate E-5-3a W3C trace primitives (PR #797 MERGED) into the consultation
archive/query flow + agent_coordination consumer. Spans + non-authoritative
correlation sidecar + cross-trace links.

**In scope:**
- New `consultation-trace-context.schema.v1.json` (sidecar schema; additive)
- New `ao_kernel/consultation/trace_context.py` helper module
- `archive.archive_all` top-level facade span
- `archive._archive_cns` per-CNS inner span (writes sidecar inside lock)
- `promotion.query_promoted_consultations` producer span with bounded
  cross-trace links pre-scan (cap `MAX_CONSULTATION_TRACE_LINKS = 10`)
- `agent_coordination.build_context_with_coordination` consumer wrapper span
- 29 invariant tests

**Out of scope (ZERO TOUCH per Codex F1-F7 absorb):**
- `ResolutionRecord` / `resolution.record.*` (digest immune)
- `evidence.py`, `normalize.py`, `integrity.py`, `migrate.py`, `paths.py`
- `memory_pipeline.py` (F6 — consumer boundary is agent_coordination)
- Existing schemas (`trace-meta`, `agent-consultation`, `policy-*`)
- `ao_kernel.tracing.make_link` semantics
- `.github/workflows/`, branch protection, guard flags

## 2. Codex Iter Chain

### iter-1 plan-time REVISE — 7 BLOCKER

| ID | Severity | Issue | Resolution |
|---|---|---|---|
| F1 API_NAME_DRIFT | BLOCKER | `archive.record_consultation()` doesn't exist; real API is `archive_all`/`_archive_cns`/`preload_event_identities`/`append_event` | Plan rewrites to real API |
| F2 RESOLUTION_RECORD_SOURCE_STABILITY | BLOCKER | `ResolutionRecord` is source-stable; trace metadata in record would break digest/idempotency | Sidecar OUTSIDE record; digest immune |
| F3 SCHEMA_FILE_ASSUMPTION | BLOCKER | `resolution.record.v1.json` schema doesn't exist | New `consultation-trace-context.schema.v1.json` sidecar schema; existing schemas zero-touch |
| F4 LINK_SEMANTICS | BLOCKER | parent context vs cross-trace link mixing → wrong correlation | Bounded pre-scan `read_sidecar_trace_links` → span `links=` parameter |
| F5 BAGGAGE_ATTRIBUTE_ASSUMPTION | BLOCKER | `session_baggage()` doesn't auto-write attribute | Manual `get_session_baggage()` + `ao.session.id` attribute |
| F6 MEMORY_PIPELINE_BOUNDARY | BLOCKER | `memory_pipeline.process_turn()` doesn't call consultation; handoff is in `agent_coordination` | `memory_pipeline.py` ZERO TOUCH; consumer span in `agent_coordination` |
| F7 GATE_RISK_CLASS | HIGH | PR is not low-risk — runtime + new schema | Documented as path-sensitive |

### iter-2 plan-time REVISE — 5 BLOCKER + 6 hardening

| ID | Resolution |
|---|---|
| F5 BAGGAGE_SOURCE_MISMATCH | Use `ao_kernel.tracing.get_session_baggage()` directly; no local ContextVar duplication |
| F6 SPAN_NAME_CONFLICT | producer `ao.consultation.query_promoted`; consumer wrapper `ao.consultation.query_consumer` (distinct) |
| CROSS_TRACE_LINK_TIMING | Bounded pre-scan before span open; `MAX_CONSULTATION_TRACE_LINKS = 10` cap |
| MAKE_LINK_INVALID_HEX_SEMANTICS | `make_link` raises `ValueError` for invalid hex; wrapper catches in `read_sidecar_trace_links`; `make_link` semantics unchanged |
| SIDECAR_INTEGRITY_POLICY_UNDEFINED | Sidecar is non-authoritative correlation metadata; NOT in integrity manifest; tampered sidecars silently ignored |

### iter-3 absorb AGREE + ready_for_impl:true + must_close_findings:[]

6 non-blocking hardening tweaks: atomic sidecar write, span count accuracy
(pre-scan candidate count vs hydrated result count), link filter parity,
sidecar read cap module-level export, invalid sidecar visibility (debug-only),
active span placement.

## 3. Implementation Artifacts

| File | LOC delta | Purpose |
|---|---|---|
| `ao_kernel/defaults/schemas/consultation-trace-context.schema.v1.json` | +60 (new) | Sidecar schema (Draft 2020-12 + all-zero reject + W3C regex) |
| `ao_kernel/consultation/trace_context.py` | +180 (new) | `capture_current_trace_context`, `maybe_write_sidecar`, `read_sidecar_trace_links`, `MAX_CONSULTATION_TRACE_LINKS = 10` |
| `ao_kernel/consultation/archive.py` | +25 modify | `archive_all` facade span + `_archive_cns` inner span + sidecar write inside lock |
| `ao_kernel/consultation/promotion.py` | +30 modify | `query_promoted_consultations` producer span with bounded link pre-scan |
| `ao_kernel/context/agent_coordination.py` | +12 modify | Consumer wrapper span around `query_promoted_consultations()` call |
| `tests/test_consultation_tracing.py` | +400 (new) | 29 invariants |
| `.claude/plans/EPIC-5-E5-3B-CONSULTATION-TRACING.md` | this | Plan + Codex chain |

## 4. Span Surface Table

| Span name | Module | Trigger | Attributes | Links |
|---|---|---|---|---|
| `ao.consultation.archive` | `archive.archive_all` | Top-level facade | `ao.consultation.count`, optional `ao.session.id` | — |
| `ao.consultation.archive.cns` | `archive._archive_cns` | Per-CNS inner | `ao.cns_id`, optional `ao.session.id` | — |
| `ao.consultation.query_promoted` | `promotion.query_promoted_consultations` | Producer (canonical query) | `ao.consultation.link_candidate_count`, optional `ao.session.id` | Cross-trace links from sidecars (bounded ≤ 10) |
| `ao.consultation.query_consumer` | `agent_coordination.build_context_with_coordination` | Consumer wrapper | `ao.consultation.cap`, optional `ao.session.id` | — |

**Attribute discipline (Codex H4 absorb):**
- `ao.cns_id` allowed only on per-CNS inner span (high-cardinality scope)
- All other spans use low-cardinality attributes (counts, caps, session_id)
- No PII; trace_id/span_id are 32/16-hex (non-secret routing fields)

## 5. Sidecar Contract

`<evidence_dir>/consultation_trace_context.v1.json`:

```json
{
  "schema_version": "consultation-trace-context.v1",
  "cns_id": "CNS-20260601-001",
  "captured_at_archive_time": true,
  "trace_id": "<32 hex; non-all-zero>",
  "span_id": "<16 hex; non-all-zero>",
  "traceparent": "00-<32 hex>-<16 hex>-<2 hex>",
  "tracestate": null,
  "session_id_baggage": "session-A"
}
```

**Discipline:**
- Idempotent first-write: if exists, never overwrite (digest-independent)
- Written AFTER `write_consultation_manifest()` inside the file lock
- NOT in integrity manifest (non-authoritative correlation metadata)
- Tampered / schema-invalid sidecars → silently skipped by read path
- No active recording span → no sidecar written (graceful degrade)

## 6. Test Sections (29 invariants)

| Section | Count | Focus |
|---|---|---|
| 1. Schema validity | 5 | Draft 2020-12 + additionalProperties + const pins + all-zero reject + W3C regex |
| 2. trace_context helper | 5 | Module exports + MAX_LINKS pin + capture None default + idempotent sidecar + OTEL-absent graceful |
| 3. Sidecar validation | 3 | Tampered shape skip + JSON error skip + cap respected |
| 4. Import discipline | 3 | No direct OTEL imports + baggage via facade + no local ContextVar |
| 5. Span emission (fake tracer) | 5 | archive facade + low-cardinality attrs + query_promoted producer + consumer wrapper distinct + cns inner ao.cns_id |
| 6. Sidecar discipline | 3 | NOT in integrity manifest + record digest immune + written AFTER manifest |
| 7. Memory pipeline scope | 1 | memory_pipeline.py ZERO TOUCH |
| 8. Schema file inventory | 2 | New schema added + existing schemas unchanged |
| 9. Governance | 2 | No .github/workflows + make_link unchanged |

## 7. Implementation Constraints (Codex iter-3 absorb)

- `make_link` semantics MUST remain unchanged (E-5-3a pinned)
- Direct OpenTelemetry imports OUTSIDE `ao_kernel.tracing` are forbidden
- Sidecar MUST NOT join `compute_consultation_manifest()` unless explicit
  follow-up PR migrates evidence authority
- `resolution.record.v1.json` fields ZERO TOUCH
- `.github/workflows/` + guard flags ZERO TOUCH
- Span attribute allowlist: `ao.cns_id` (inner only), `ao.consultation.count`,
  `ao.consultation.cap`, `ao.consultation.link_candidate_count`,
  `ao.status`, `ao.session.id`

## 8. Out-of-scope follow-up slices

| ID | Slice |
|---|---|
| E-5-3c | OTEL deployment runbook |
| E-5-3d | Trace collector backend (Jaeger/Zipkin) integration |
| E-5-3e | Full 9-module public-function span coverage |
| E-5-3f | Trace sampling discipline (head-based + tail-based) |
| E-5-3g | PII redaction policy (attribute filter) |
| E-5-3h | Multi-tenant trace isolation |

## 9. References

- E-5-3a W3C tracing primitives: PR #797 MERGED
- E-5-1 OTEL prod tunables: PR #791 MERGED
- HARD RULE Cross-AI Peer Review (2026-05-05, 2026-05-14)
- HARD RULE Uzun Vadeli Kalıcı Çözüm (2026-05-27)
- W3C Trace Context: https://www.w3.org/TR/trace-context/
- Codex thread `019e83ee` (3-iter REVISE/REVISE/AGREE)
