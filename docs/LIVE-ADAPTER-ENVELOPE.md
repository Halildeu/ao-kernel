# Live Adapter Envelope (V5 Epic 2 E-2-1)

> Slice #846. Defines the governance **envelope** for a single (would-be) LLM
> provider call. This is **infrastructure only**: it describes the *shape* of a
> call record under `stub`/`dry_run` modes. It does **not** make a network call,
> does **not** flip any guard flag, and does **not** claim production readiness.

## What it is

`ao_kernel/defaults/schemas/live_adapter_envelope.schema.v1.json` is a strict
JSON Schema (Draft 2020-12) for one record describing a single LLM call as it
would pass through the governance plane. Every downstream Epic 2 slice
(per-call audit E-2-2, cost ceiling E-2-3, dry-run harness E-2-4) binds to this
envelope as the canonical call-shape.

## Fail-closed design

| Property | Pin | Why |
|---|---|---|
| `schema_version` | const `live-adapter-envelope.v1` | v2 (which adds `live`) is a separate file |
| `artifact_kind` | const `live_adapter_envelope` | artifact discriminator |
| `envelope_digest` | required, bare 64-hex | content-address that E-2-2 per-call audit records foreign-key to |
| `mode` | enum `{stub, dry_run}` | `live` is **forbidden** here; real execution is Epic 9 only |
| `live_adapter_execution` | const `false` | guard-flag pin (ADR-0002 recompute-not-trust) |
| `support_widening` / `production_platform_claim` | const `false` if present | optional affirmations, never `true` |
| `secret_boundary` | const `no_secret_material_emitted_no_token_no_credential` | affirms no secret is captured (CLAUDE.md değişmez #3) |

Strict closure (`additionalProperties:false` + `unevaluatedProperties:false`) on
**every** object means a future stray field cannot silently slip past the
invariants.

## Cost + digest discipline

- Cost fields are **decimal strings** matching `^[0-9]+\.[0-9]{8}$` (8 dp). Floats
  are rejected to avoid precision drift (BC-10 pattern). `actual_cost_usd` is the
  computed total; `*_cost_per_1k_usd` are the unit rates.
- `pricing_source_digest` carries the `sha256:` prefix; message/text/envelope
  digests are bare 64-hex. No raw prompt/response text is ever stored — only
  digests.
- Timestamps (`created_at`, `finalized_at`, `last_failure_at`) carry an explicit
  RFC3339 `pattern` in addition to `format: date-time`: `jsonschema` does not
  enforce `format` by default, so the regex is what makes a malformed timestamp
  fail-closed. The regex enforces **shape + numeric range + month/day calendar
  coupling** (February ≤ 29; 30-day months ≤ 30; rejects e.g. `2026-02-31`,
  `2026-04-31`, `2026-13-40T25:61:61Z`). It does **not** enforce leap-year
  validity (`2026-02-29` is accepted by the regex) — a pure JSON-Schema regex
  cannot do mod-4/100/400 arithmetic, so exact leap-year validity is a
  recompute-time check (the E-2-4 dry-run harness parses with `datetime`). This
  boundary is pinned by `test_timestamp_regex_boundary_is_documented`.

## Conditional invariants (`allOf`)

- `mode == "stub"` ⇒ `response.status == "stub_emitted"`
- `mode == "dry_run"` ⇒ `response.status == "dry_run_emitted"`
- `circuit_breaker.state == "CLOSED"` ⇒ `failure_count == 0` (fail-closed)

## What this slice does NOT do

- Does NOT make a real provider HTTP call (stub/dry_run only).
- Does NOT flip `live_adapter_execution` (or any guard flag) — that is the Epic 9
  PR-Xfinal operator-bound supersession PR, against a different (v2) schema.
- Does NOT define the per-call audit log (E-2-2), cost ceiling (E-2-3), or the
  dry-run harness (E-2-4) — those bind to this envelope in later slices.

## Verification

`tests/test_live_adapter_envelope.py` — 36 machine-enforced invariants: schema
health, guard-flag pins, strict closure enforced at **every** object path
(parametrized), required-field enforcement (parametrized one-field-removed),
const/enum pins, conditional `allOf` coupling, decimal/sha pattern enforcement,
RFC3339 timestamp fail-closed (regex, not format-only), and a
no-workflow-mutation guard.

## Cross-references

- Epic 2 plan: `.claude/plans/EPIC-2-LIVE-ADAPTER-EXECUTION.md` (E-2-1)
- V5 roadmap: `.claude/plans/V5-FULL-PRODUCTION-PROMOTION-ROADMAP.md` (§3 Epic 2)
- Per-call audit (next): E-2-2 `per_call_audit.schema.v1.json` (#847)
