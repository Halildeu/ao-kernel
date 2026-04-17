# Cost Model — Price Catalog, Spend Ledger, Cost-Aware Routing

**Status:** FAZ-B PR-B0 contract pin (docs skeleton). Runtime implementation: PR-B2 (catalog + ledger), PR-B3 (cost-aware routing).

## 1. Overview

Cost tracking in ao-kernel has three collaborating contracts:

1. **Price catalog** — a versioned, checksum-verified snapshot of provider/model unit prices. Bundled starter ships with ao-kernel; operators override at workspace scope.
2. **Spend ledger** — append-only JSONL log of every billable LLM call, keyed by run/step, carrying provider, model, tokens, and USD cost.
3. **Budget axes** — extended [`Budget`](../ao_kernel/workflow/budget.py) (PR-A1) with granular token axes (`tokens_input` / `tokens_output`) in addition to the existing `cost_usd` / `tokens` / `time_seconds` axes; fail-closed pre-invocation check.

Cost-aware model routing (PR-B3) reads the catalog to estimate call cost before dispatch and falls back to a cheaper model if the remaining budget cannot cover the estimate.

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

`llm.resolve_route(intent, budget_remaining)` extends PR-A routing with a catalog lookup. When `policy_cost_tracking.routing_by_cost.enabled: true`:

1. Compute `estimated_cost` for the preferred model.
2. If `budget_remaining.cost_usd >= estimated_cost`, return preferred.
3. Otherwise, iterate the same intent class's fallback list (ordered cheapest-first in the catalog) until one fits.
4. If none fits, raise `BudgetExhaustedError`.

Routing failure is explicit; there is no silent "use the cheapest thing that fits" downgrade unless the operator opts into routing.

## 7. Cross-References

- Schemas: [`price-catalog.schema.v1.json`](../ao_kernel/defaults/schemas/price-catalog.schema.v1.json), [`spend-ledger.schema.v1.json`](../ao_kernel/defaults/schemas/spend-ledger.schema.v1.json), [`policy-cost-tracking.schema.v1.json`](../ao_kernel/defaults/schemas/policy-cost-tracking.schema.v1.json).
- Runtime (scope out of B0): PR-B2 (`ao_kernel/cost/`), PR-B3 (`ao_kernel/llm.py` cost-aware routing).
- Metrics exposure: [METRICS.md](METRICS.md) (`ao_llm_tokens_used_total`, optional `ao_llm_call_cost_usd_total` under advanced labels).

## 8. Document Status

Skeleton in PR-B0 commit 1. Worked examples (operator override walkthrough, vendor_api scraping template, ledger query recipes) land in PR-B0 commit 5 (docs final pass).
