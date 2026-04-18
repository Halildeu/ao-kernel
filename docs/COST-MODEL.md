# Cost Model — Price Catalog, Spend Ledger, Cost-Aware Routing

**Status:** FAZ-B PR-B0 contract pin (docs skeleton). Runtime implementation: PR-B2 (catalog + ledger), PR-B3 (cost-aware routing).

## 1. Overview

Cost tracking in ao-kernel has three collaborating contracts:

1. **Price catalog** — a versioned, checksum-verified snapshot of provider/model unit prices. Bundled starter ships with ao-kernel; operators override at workspace scope.
2. **Spend ledger** — append-only JSONL log of every billable LLM call, keyed by run/step, carrying provider, model, tokens, and USD cost.
3. **Budget axes** — extended [`Budget`](../ao_kernel/workflow/budget.py) (PR-A1) with granular token axes (`tokens_input` / `tokens_output`) in addition to the existing `cost_usd` / `tokens` / `time_seconds` axes; fail-closed pre-invocation check.

Cost-aware model routing (PR-B3) reads the catalog to re-order the target intent class's eligible provider set ascending by price-catalog cost before the router iterates — operators opt into cost-aware selection without changing any code. Full contract in §6.

All behaviour described here is dormant until `policy_cost_tracking.v1.json::enabled: true`; defaults are operator-facing, not automatic.

## 2. Price Catalog

### 2.1 Object Shape

```json
{
  "catalog_version": "1",
  "generated_at": "2026-04-16T00:00:00+00:00",
  "source": "bundled",
  "stale_after": "2026-07-16T00:00:00+00:00",
  "checksum": "sha256:<64-hex>",
  "entries": [
    {
      "provider_id": "anthropic",
      "vendor_model_id": "claude-3-5-sonnet-20241022",
      "model": "claude-3-5-sonnet",
      "input_cost_per_1k": 0.003,
      "output_cost_per_1k": 0.015,
      "cached_input_cost_per_1k": 0.0003,
      "currency": "USD",
      "billing_unit": "per_1k_tokens",
      "effective_date": "2026-04-16"
    }
  ]
}
```

Top-level keys are all required; `entries[*]` is `additionalProperties: false`. Validation against [`price-catalog.schema.v1.json`](../ao_kernel/defaults/schemas/price-catalog.schema.v1.json) at load time.

### 2.2 Field Semantics

- **`source`** (enum: `bundled | vendor_api | manual`) — Where this catalog came from. Controls `vendor_model_id` conditional requirement (§2.3).
- **`checksum`** (`sha256:<hex>`) — SHA-256 of the `entries[]` array serialised as canonical JSON (`sort_keys=True, ensure_ascii=False, separators=(",",":")`). Loader recomputes and compares; mismatch yields `PriceCatalogChecksumError`. Protects against in-place edits that skip version bump.
- **`generated_at`** — ISO 8601 timestamp the catalog was produced.
- **`stale_after`** — ISO 8601 timestamp after which the catalog is considered stale. **Required** per `price-catalog.schema.v1.json` v1; authored explicitly in every catalog (no loader-inferred default). Stale handling: default `warn`-level log via `policy_cost_tracking.strict_freshness=false`; opt-in fail-closed via `strict_freshness=true`. The bundled starter catalog ships with `stale_after = generated_at + 90 days` as a convention, but operators authoring manual catalogs must set this field themselves.
- **`vendor_model_id`** vs **`model`** — `vendor_model_id` is the vendor's canonical identifier used for billing and audit (e.g., `claude-3-5-sonnet-20241022`); `model` is the short routing key that `llm.resolve_route()` matches against (`claude-3-5-sonnet`). Routing and billing stay decoupled.
- **`currency`** (v1 enum: `USD` only) — Non-USD currencies deferred to FAZ-E (enterprise residency + multi-currency).
- **`billing_unit`** (v1 enum: `per_1k_tokens` only) — Per-request and per-image billing deferred to FAZ-D+.
- **`region`** — Not present in v1. Regional pricing differentiation is FAZ-E enterprise scope; v1 assumes global pricing per `(provider_id, model)`.
- **`effective_date`** — ISO 8601 date the entry's prices took effect at the vendor.

### 2.3 `vendor_model_id` Conditional (B0 contract)

`vendor_model_id` is **required** only when the catalog's top-level `source` is `vendor_api`; for `bundled` and `manual` sources it is optional. The rationale: manual catalog curation (spreadsheet → JSON) would be painfully brittle if every hand-edited entry had to carry a vendor-specific identifier that operators do not always know; vendor-scraped catalogs, on the other hand, have the identifier by construction and must preserve it for audit.

Encoded as JSON Schema `if/then` on the top-level `source` value, applied uniformly to all `entries[*]`.

### 2.4 Stale Policy

- **Default (`strict_freshness: false`)** — loader emits a `warn`-level message when `now > stale_after` but otherwise returns the catalog; routing and validation still function.
- **Opt-in (`policy_cost_tracking.strict_freshness: true`)** — stale catalog raises `PriceCatalogStaleError`; fail-closed.

### 2.5 Versioning

Full snapshot replacement, NOT append-only. Each new catalog version is a complete replacement; operators bump `catalog_version` and recompute `checksum`. The bundled starter catalog ships as version `1`.

### 2.6 Bundled Path

`ao_kernel/defaults/catalogs/price-catalog.v1.json` (PR-B0 commit 3). Discoverable via [`config.load_default("catalogs", "price-catalog.v1.json")`](../ao_kernel/config.py) — new `catalogs` kind is a plural member of the existing kinds family (`policies`, `schemas`, `registry`, `extensions`, `operations`). Full-filename convention matches existing `load_default` usage.

## 3. Spend Ledger

Append-only JSONL under `{project_root}/.ao/cost/spend.jsonl`. Each line is a schema-valid event:

```json
{
  "run_id": "uuid-v4",
  "step_id": "...",
  "provider_id": "anthropic",
  "vendor_model_id": "claude-3-5-sonnet-20241022",
  "model": "claude-3-5-sonnet",
  "tokens_input": 1234,
  "tokens_output": 456,
  "cached_tokens": 200,
  "cost_usd": 0.009876,
  "ts": "2026-04-16T14:23:45.678+00:00"
}
```

Schema: [`spend-ledger.schema.v1.json`](../ao_kernel/defaults/schemas/spend-ledger.schema.v1.json), `additionalProperties: false`.

## 4. Budget Extension (PR-A1 + B2)

Existing [`Budget`](../ao_kernel/workflow/budget.py) axes: `tokens`, `time_seconds`, `cost_usd`. B2 adds granular token axes:

- `tokens_input` — prompt tokens
- `tokens_output` — completion tokens

Granularity lets policies distinguish "too much prompt context" from "runaway generation". Either axis exhausting triggers `BudgetExhaustedError(category=budget_exhausted)` per PR-A1 fail-closed primitive.

## 5. Cost Cap Fail-Closed

PR-B2 runtime checks the remaining budget against the catalog-estimated cost of an invocation **before** dispatching to the adapter. If the estimate exceeds the remaining budget, the call is blocked and `BudgetExhaustedError` is raised. No partial charges, no silent downgrade.

Estimation formula (deterministic, per-invocation):

```
estimated_cost = (est_tokens_input  * input_cost_per_1k  / 1000)
               + (est_tokens_output * output_cost_per_1k / 1000)
```

## 6. Cost-Aware Routing (PR-B3)

When operators opt in, the LLM router (`resolve_route`) sorts the eligible provider set for the target intent class ascending by price-catalog cost before iterating. The dormant default preserves pre-B3 `llm_resolver_rules.fallback_order_by_class` order unchanged.

### 6.1 Activation

Three fields in `policy_cost_tracking.v1.json::routing_by_cost`:

| Field | Default | Meaning |
|---|---|---|
| `enabled` | `false` | Master switch for the cost-aware branch. |
| `priority` | `"provider_priority"` | Selection strategy. `"lowest_cost"` triggers the sort-by-price path; `"provider_priority"` preserves pre-B3 behavior. |
| `fail_closed_on_catalog_missing` | `true` | When active mode + catalog load failure: `true` raises `RoutingCatalogMissingError`; `false` warn-logs + falls back to `provider_priority`. |

Gate: the cost-aware path engages only when all three of `policy_cost_tracking.enabled=true`, `routing_by_cost.enabled=true`, and `routing_by_cost.priority="lowest_cost"` hold simultaneously.

### 6.2 Selection Semantics — Tek Semantik (Plan v5 §2.4)

> If at least one provider in `provider_order` has a catalog cost entry, sort ascending and **drop unknowns**. If no provider has a catalog entry, **fall back** to the original `provider_order` without elimination.

Exhaustive matrix:

| Condition | Resulting order |
|---|---|
| Explicit `provider_priority` caller arg | Caller-supplied (cost bypass — caller intent wins) |
| `policy.enabled=false` | Pre-B3 fallback order |
| `routing_by_cost.enabled=false` | Pre-B3 fallback order |
| `priority="provider_priority"` | Pre-B3 fallback order |
| `priority="lowest_cost"` + catalog OK + ≥1 known-cost provider | Ascending cost; unknowns DROPPED |
| `priority="lowest_cost"` + catalog OK + all unknown | Original order (fallback, no elimination) |
| Catalog load fails + `fail_closed_on_catalog_missing=true` | `RoutingCatalogMissingError` raised |
| Catalog load fails + `fail_closed_on_catalog_missing=false` | Warn-log + provider_priority fallback |

### 6.3 Cost Metric

Routing decisions use a simple input+output per-1k average:

```
routing_cost_per_1k = (input_cost_per_1k + output_cost_per_1k) / 2
```

`cached_input_cost_per_1k` is **deliberately ignored** at routing time — cache hits are a per-call property, not a per-model property. Billing continues to use actual token counts via `compute_cost` (which honors the cached-rate path).

### 6.4 Provider Namespace Alias

The router uses short provider names (`claude`, `openai`, `google`, `deepseek`, `qwen`, `xai`); the catalog uses vendor names. Lookups go through a fixed alias map:

| Router | Catalog |
|---|---|
| `claude` | `anthropic` |
| `openai` | `openai` |
| `google` | `google` |
| `deepseek` | `deepseek` (no bundled entries) |
| `qwen` | `qwen` (no bundled entries) |
| `xai` | `xai` (no bundled entries) |

Providers without a bundled catalog entry flow through the unknown bucket and are handled by the drop-or-fallback branch above. **Model aliasing is out of scope for v1**; uncovered (provider, model) pairs resolve to unknown. FAZ-C revisits this.

### 6.5 Loader Fail-Closed Contract

The router does **not** swallow `load_cost_policy` exceptions:

- Missing workspace override → bundled dormant fallback (no raise).
- Malformed override (invalid JSON) → `json.JSONDecodeError` propagates.
- Schema-invalid override → `jsonschema.ValidationError` propagates.

This matches the `cost/policy.py::_validate` + `load_cost_policy` fail-closed contract (the loader validates before returning and raises on any schema or JSON error) and `llm.py::resolve_route`'s "Fail-closed" docstring.

For catalog loading the router uses a narrower wrapper: failures in strict mode raise `RoutingCatalogMissingError` (preserving the underlying cause as `__cause__` — `PriceCatalogChecksumError`, `PriceCatalogStaleError`, `JSONDecodeError`, `ValidationError`, etc.) so operators can drill down to the specific remediation.

### 6.6 Known Limit — Catalog Cache Key

The catalog loader caches by `workspace_root.resolve()` only. Swapping `policy_cost_tracking.price_catalog_path` mid-run does not invalidate the 300-second cache. Operators who rotate catalog files should either bump `workspace_root` or wait for cache expiry. FAZ-C scope.

## 7. Runtime — PR-B2 Integration (shipped)

### 7.1 `llm.governed_call` wrapper

B2 introduces `ao_kernel.llm.governed_call(messages, *, ...)` — a **non-streaming** composition wrapper around `build_request` + `execute_request` + `normalize_response` with optional cost governance.

Activation gate: cost pipeline engages only when **all four** kwargs are set AND `policy.enabled=true`:
- `workspace_root: Path`
- `run_id: str`
- `step_id: str`
- `attempt: int`

Any missing kwarg → transparent bypass (pre-B2 behavior).

Return contract (plan v5 iter-4 B1):
- On `CAPABILITY_GAP`: envelope `{status, missing, provider_id, model, request_id, text=""}` — caller envelope-ready.
- On `TRANSPORT_ERROR`: envelope `{status, error_code, http_status, elapsed_ms, ...}` — caller envelope-ready.
- On `OK`: rich dict `{status="OK", normalized, resp_bytes, transport_result, elapsed_ms, request_id}` — caller unwraps and runs its own post-call pipeline (decision extraction, eval scorecard, telemetry).

Cost-layer errors **raise** (not envelope): `BudgetExhaustedError`, `CostTrackingConfigError`, `PriceCatalogNotFoundError`, `LLMUsageMissingError`.

### 7.2 Identity threading — 3 caller entrypoints

| Caller | Identity source | Cost activation |
|---|---|---|
| `AoKernelClient.llm_call(run_id=, step_id=, attempt=)` | SDK user passes explicitly | opt-in (3 kwargs optional, default None → bypass) |
| `mcp_server.handle_llm_call(params={"ao_run_id", "ao_step_id", "ao_attempt"})` | MCP tool params (optional) | opt-in |
| `workflow.intent_router._llm_classify` | — | **bypass-only** (standalone classifier, not a workflow-run budget anchor) |

### 7.3 18-step pipeline (pre-dispatch → reconcile)

1. Capability check → envelope on gap.
2. Cost gate (identity + policy.enabled).
3. Build (context-aware if `session_context`; plain otherwise). `build_request_with_context` returns `injected_messages` additive field.
4. `pre_dispatch_reserve`: catalog lookup → `estimate_cost` over `effective_messages` → emit `llm_cost_estimated` → CAS-reserve budget (update_run max_retries=3).
5. Transport.
6. Transport error → envelope (reservation HOLDS per plan Q5 iter-1 — no refund on failure).
7. Normalize.
8. `post_response_reconcile`: `extract_usage_strict` → on usage gap, `record_spend(usage_missing=true)` + emit `llm_usage_missing` + optional raise. Success path: `compute_cost(actual)` → CAS-reconcile (delta = actual − estimate) → `record_spend` with `billing_digest` → emit `llm_spend_recorded`.
9. Return rich dict.

### 7.4 Evidence taxonomy

3 additive kinds emitted by cost runtime (24 → 27):
- `llm_cost_estimated` — pre-dispatch estimate, always emitted before transport.
- `llm_spend_recorded` — post-response actual, emitted after ledger append.
- `llm_usage_missing` — adapter response missing tokens_input/output; audit-only ledger entry precedes the raise when fail-closed.

Emits are **fail-open** (wrapper swallows + warn-logs); ledger writes are **fail-closed** (raise on failure).

**PR-C4 reservation (27 → 28)**: `route_cross_class_downgrade` is added to the `_KINDS` frozenset but **not emitted** by cost runtime or the route layer in this release. The kind is reserved for the C4.1 follow-up PR, which wires the runtime consumer (threshold schema widen + `soft_degrade.rules` directional filter). Total shipped emit kinds stay at **3** for cost runtime.

## 8. Identity Threading — `(run_id, step_id, attempt)`

The ledger idempotency key is `(run_id, step_id, attempt)`. Retry semantics:

- Same key + same `billing_digest` → silent no-op with warn log (operator-visible but non-raising).
- Same key + different `billing_digest` → `SpendLedgerDuplicateError` (caller bug: the retry produced a distinct billable payload).
- Distinct `attempt` for the same `(run_id, step_id)` → separate ledger lines (normal retry path).

The `attempt` field aligns with `step_record.attempt` from PR-A1 (already append-only per retry). Workflow drivers thread all three identity values; SDK users do so when they want cost tracking for arbitrary calls.

## 9. Streaming — Deferred to FAZ-C

`governed_call` is **non-streaming only**. Callers with `stream=True` intent stay on the pre-B2 build + `_execute_stream` path; no cost hooks run. Chunk-level tokenization and partial-ledger semantics are FAZ-C scope.

Operators running streaming workloads should scope cost tracking to non-streaming calls only, or accept that streaming consumption lies outside the `spend.jsonl` audit trail until FAZ-C lands.

A process-level `logger.warning(...)` may be emitted on the first streaming call after `policy.enabled=true` to surface this gap to operators (implementation detail; not a policy knob).

## 10. Migration from v3.1.0 → v3.2.0

### 10.1 Opt-in sequence

1. Keep `policy_cost_tracking.enabled: false` initially (bundled default — no runtime change).
2. Add `budget.cost_usd` axis to your workflow specs (required by `policy.enabled=true` per Option A fail-closed guard — `CostTrackingConfigError` fires at first LLM call otherwise).
3. Optionally add granular `budget.tokens_input` / `budget.tokens_output` axes for per-direction caps.
4. Drop a workspace override at `{project_root}/.ao/policies/policy_cost_tracking.v1.json` with `enabled: true`.
5. Ensure the bundled price catalog covers your routed (provider, model) pairs — add a workspace override at `{project_root}/.ao/cost/catalog.v1.json` for models not in the bundled starter.
6. Confirm the workspace has write access to `{project_root}/.ao/cost/` (auto-created with `mode=0o700`).

### 10.2 Back-compat invariants

- Legacy workflow-run records with only aggregate `tokens` axis → loader synthesizes `tokens_input = BudgetAxis(copy)`, `tokens_output = None` (conservative legacy-to-granular mapping; plan v7 §2.5).
- Legacy `spend.jsonl` files without `attempt` / `usage_missing` / `billing_digest` fields parse cleanly (additive schema widen; pre-B2 tools still read them).
- `extract_usage` (PR-A callers, 0-fallback default) unchanged; B2 middleware uses the new `extract_usage_strict` (None-sentinel) variant internally.

### 10.3 Cross-References

- Schemas: [`price-catalog.schema.v1.json`](../ao_kernel/defaults/schemas/price-catalog.schema.v1.json), [`spend-ledger.schema.v1.json`](../ao_kernel/defaults/schemas/spend-ledger.schema.v1.json), [`policy-cost-tracking.schema.v1.json`](../ao_kernel/defaults/schemas/policy-cost-tracking.schema.v1.json).
- Runtime (shipped): PR-B2 `ao_kernel/cost/` package; facade `ao_kernel.llm.governed_call`.
- Downstream: PR-B3 (cost-aware routing) consumes `policy.routing_by_cost.enabled`; ledger rotation is a separate FAZ-B follow-up (out of B2 scope).
- Metrics exposure: [METRICS.md](METRICS.md) — derivation-based, consumes ledger events, independent of the `[otel]` extra.

## 11. Document Status

Skeleton in PR-B0 commit 1 (dormant contract pin). Runtime notes
(§7-§10) land in PR-B2 commit 6 alongside the 7-commit DAG merge.
Plan: `.claude/plans/PR-B2-IMPLEMENTATION-PLAN.md` v7 (Codex
CNS-20260417-031 thread 019d9aa8 AGREE, ready_for_impl=true after
7 adversarial iters).
