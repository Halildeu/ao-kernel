# Model Routing

`ao_kernel._internal.prj_kernel_api.llm_router.resolve` is the deterministic entrypoint that turns an intent (`DISCOVERY`, `BASELINE`, `APPLY`, ...) into a verified `(provider, model)` pair.

## 1. Inputs

- `intent` — one of the keys in `llm_resolver_rules.v1.json::intent_to_class`.
- `provider_priority` (optional) — caller-supplied ordered list of provider short names. **Overrides all cost-aware logic when non-empty** (caller intent wins).
- `workspace_root` — used for probe state + cost policy + catalog loading.

## 2. Resolution Steps

1. Validate intent; rejection codes: `MODEL_OVERRIDE_NOT_ALLOWED`, `PROFILE_PARAM_OVERRIDE_NOT_ALLOWED`, `UNKNOWN_INTENT`.
2. Map intent → `target_class` via `intent_to_class`.
3. Load `llm_class_registry.v1.json` + `llm_resolver_rules.v1.json` + `llm_provider_map.v1.json` (bundled) and merge with `<workspace>/.cache/state/llm_probe_state.v1.json` if present.
4. Compute `order`:
   - `provider_priority` if the caller supplied it.
   - Otherwise `resolver_rules.fallback_order_by_class[target_class]`.
5. **PR-B3 cost-aware injection** — see [COST-MODEL.md §6](./COST-MODEL.md#6-cost-aware-routing-pr-b3). Only applied when all of the following hold:
   - `policy_cost_tracking.enabled=true`
   - `routing_by_cost.enabled=true`
   - `routing_by_cost.priority="lowest_cost"`
   - Caller did **not** supply `provider_priority`
6. For each provider in `order`, check provider slot + pinned model + probe state (`verified`, TTL, probe kind for `APPLY`/`CODE_AGENTIC`).
7. First eligible match becomes `selected`; all attempts logged in `provider_attempts`.

## 3. Failure Modes

| Status | Reason | When |
|---|---|---|
| `FAIL` | `MODEL_OVERRIDE_NOT_ALLOWED` | Caller supplied `model` key |
| `FAIL` | `PROFILE_PARAM_OVERRIDE_NOT_ALLOWED` | Caller supplied `params_override` |
| `FAIL` | `UNKNOWN_INTENT` | Intent not in `intent_to_class` |
| `FAIL` | `APPLY_BLOCKED_NO_VERIFIED_CODE_AGENTIC` | `APPLY`/`CODE_AGENTIC` with no verified, probe-ready model |
| `FAIL` | `NO_VERIFIED_MODEL_FOR_CLASS` | Other intent classes with no eligible model |
| `RAISE` | `RoutingCatalogMissingError` | Cost-aware active + catalog load fails + strict mode (see COST-MODEL.md §6.5) |
| `RAISE` | `json.JSONDecodeError` / `jsonschema.ValidationError` | Malformed workspace cost policy override |

## 4. Selection Invariants

- `verified`-only (`probe_status="ok"`) — no routing to probes, stubs, or untested models.
- TTL-gated (`ttl_hours_by_class` with a default of 72h).
- Probe-kind gate for `APPLY`/`CODE_AGENTIC`: rejects missing / synthetic probes with distinct reason codes so UI can surface "NOT READY" vs generic failure.
- Provider/model selection is deterministic given identical inputs and probe state.

## 5. Extensibility

- Adding an intent: update `llm_resolver_rules.v1.json::intent_to_class` + `fallback_order_by_class`.
- Adding a provider: add entry to `llm_provider_map.v1.json::classes[class].providers[provider]` plus (optionally) an alias in `ao_kernel/cost/routing.py::_PROVIDER_ALIAS_MAP` for catalog lookups.
- Model aliasing (non-exact catalog provider/model matches) is explicitly **out of scope for v1**. Uncovered models flow through the cost-aware unknown bucket and are handled by the drop-or-fallback branch.
