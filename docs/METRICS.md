# Metrics — Prometheus / OTEL Export Surface

**Status:** FAZ-B PR-B5 shipped — `ao_kernel/metrics/` runtime + `[metrics]` extra + `ao-kernel metrics {export,debug-query}` CLI + bundled Grafana dashboard. PR-B0 shipped the schema + dormant policy skeleton; PR-B5 added the runtime populator + CLI.

## 1. Overview

ao-kernel exposes governance and runtime metrics in two orthogonal channels:

1. **Prometheus textfile export** (PR-B5) — low-cardinality default label set; operators scrape via `ao-kernel metrics export --format prometheus`. Ships under the `[metrics]` optional extra.
2. **OTEL span bridge** (existing, [PR-A telemetry](../ao_kernel/telemetry.py)) — unchanged; `[metrics]` and `[otel]` extras are independent, installable separately.

The `[metrics]` extra has no hard dependency on `[otel]`. The library never runs an HTTP server; operators who want push-to-Prometheus run the CLI in their own cron or sidecar.

**Runtime architecture (evidence-derived):**

```
events.jsonl  ──►  ao_kernel.metrics.derivation  ──►  prometheus_client registry
                                                  │
state.v1.json ──►  run_store.list_terminal_runs   ├──►  ao_kernel.metrics.export
                                                  │     (Prometheus textfile)
claim SSOT    ──►  coordination.live_claims_count ┘
```

The derivation layer is **stateless + read-only** — no coupling into hot LLM / executor / cost paths. Scrape cadence is driven by the operator's cron or systemd timer calling the CLI.

## 2. Default Metric Set (eight families)

Low-cardinality labels only. See §3 for opt-in expansion.

| Metric | Type | Labels | Source |
|---|---|---|---|
| `ao_llm_call_duration_seconds` | histogram | `provider` | `llm_spend_recorded.duration_ms` (PR-B5 C2b) |
| `ao_llm_tokens_used_total` | counter | `provider`, `direction` ∈ `{input, output, cached}` | `llm_spend_recorded.{tokens_input,tokens_output,cached_tokens}` |
| `ao_llm_cost_usd_total` | counter | `provider` | `llm_spend_recorded.cost_usd` |
| `ao_llm_usage_missing_total` | counter | `provider` | `llm_usage_missing` event count |
| `ao_policy_check_total` | counter | `outcome` ∈ `{allow, deny}` | `policy_checked.violations_count` (`==0` → allow, `>0` → deny). In `v4.0.0b1`, this includes adapter CLI command enforcement along with the earlier secret / sandbox / HTTP-header checks. |
| `ao_workflow_duration_seconds` | histogram | `final_state` ∈ `{completed, failed, cancelled}` | `workflow_started` + terminal event (or `state.v1.json.completed_at` for cancelled) |
| `ao_claim_active_total` | gauge | (none — scalar) | `coordination.registry.live_claims_count()` snapshot |
| `ao_claim_takeover_total` | counter | (none — scalar) | `claim_takeover` event count |

**Histogram buckets** (plan v4 §2.2):

- LLM: `0.1, 0.5, 1, 2.5, 5, 10, 30, 60, 300, 600` seconds (upper 600s tolerates GPT-4-turbo outliers).
- Workflow: `1, 5, 15, 60, 300, 900, 3600, 7200` seconds (human-approval steps can dwell overnight).

**Deliberately excluded by default:** `model`, `agent_id`, `run_id`, `workflow_id`, `step_id`. Each would produce O(100) – O(10k) distinct values in a reasonable deployment, and Prometheus cardinality costs scale multiplicatively. Exposing them without an opt-in would create a silent storage bomb. See §6 for the cardinality guard.

## 3. Advanced Labels (Schema-Backed Opt-In)

`policy_metrics.v1.json` is the control plane for advanced labels. Operators opt in by setting the policy `enabled: true` and listing the labels they want in `labels_advanced.allowlist`.

```json
{
  "enabled": true,
  "labels_advanced": {
    "enabled": true,
    "allowlist": ["model", "agent_id"]
  }
}
```

Allowlist values are constrained to a closed enum (`model | agent_id`) at schema level. Unknown values fail schema validation at load; typos do not silently enable anything.

The `enabled` flag on the top-level policy gates metrics emission altogether. The `labels_advanced.enabled` flag specifically gates the advanced label set. Both default `false` in the bundled policy.

## 4. Grafana Integration

Reference dashboard JSON ships at [`docs/grafana/ao_kernel_default.v1.json`](grafana/ao_kernel_default.v1.json). Operators import into their own Grafana instance via one of four recipes documented in [`docs/grafana/README.md`](grafana/README.md) (UI upload, local file provisioning, Kubernetes ConfigMap, or Grafana HTTP API).

The dashboard ships with eight panels — one per metric family — all targeting the default low-cardinality label set. A shape test (`tests/test_grafana_dashboard_shape.py`) pins the panel → metric mapping so the dashboard and runtime cannot drift apart.

## 5. OTEL Bridge

[`ao_kernel/telemetry.py`](../ao_kernel/telemetry.py) already emits OTEL spans for the same code paths under the `[otel]` extra. The metrics package introduces parallel Prometheus counters/histograms; it does not read OTEL spans or attempt bridge translation.

Operators who want both can install both extras (`pip install ao-kernel[otel,metrics]`); the two surfaces do not interfere.

## 6. CLI + Operator Runbook

### 6.1 `ao-kernel metrics export`

Cumulative Prometheus textfile emitter. Typical integration:

```bash
# Cron every minute:
* * * * * /usr/bin/ao-kernel metrics export \
  --output /var/lib/node_exporter/textfile/ao-kernel.prom
```

The output is always a full workspace scan (no `--since` / `--run` — those flags would break Prometheus counter semantics; see §6.4).

**Exit codes:**

| Code | Meaning |
|---|---|
| 0 | Success (textfile emitted; may be banner-only when dormant). |
| 1 | User error (`--output` path not writable). |
| 2 | Internal (corrupt evidence JSONL → `EvidenceSourceCorruptedError`). |
| 3 | `[metrics]` extra not installed — informational banner, not a crash. |

### 6.2 Dormant policy ↔ banner-only textfile

When `policy_metrics.v1.json.enabled=false` (bundled default), the textfile contains only banner comments:

```
# ao-kernel metrics: dormant (policy_metrics.enabled=false). Operator action: ...
```

Grafana renders every panel as "No data" with the banner rationale visible to operators via Prometheus text format.

### 6.3 Cost-tracking prerequisite (disjunction)

**LLM metrics require cost tracking enabled.** When `policy_cost_tracking.v1.json.enabled=false`, the `ao_llm_*` metric family is **absent** from the textfile (plan v4 §2 cost-disjunction invariant). No zero-synthetic samples, no HELP/TYPE metadata stubs — the family simply does not exist in the output:

```
# ao-kernel metrics: cost tracking dormant (policy_cost_tracking.enabled=false); LLM metric family absent.
```

This disjunction matches the runtime reality: `llm_spend_recorded` and `llm_usage_missing` events are only emitted by `governed_call` on the cost-active path. Collecting zero-filled samples when no data exists would lie to the dashboard.

To get LLM metrics, enable both policies:

```json
// .ao/policies/policy_metrics.v1.json
{"version": "v1", "enabled": true, "labels_advanced": {"enabled": false, "allowlist": []}}
// .ao/policies/policy_cost_tracking.v1.json
{"version": "v1", "enabled": true, /* … cost knobs … */}
```

### 6.4 Why no `--since` / `--run` flags

Prometheus textfile collectors are **cumulative** — samples grow monotonically, and the collector computes deltas between scrapes. A windowed (`--since`) or run-scoped (`--run`) export would reset counters between scrapes, which Prometheus interprets as a counter restart and treats the drop as a huge negative rate.

For operator debugging (ad-hoc "what happened in the last hour" queries), use `ao-kernel metrics debug-query` (§6.5) which emits JSON specifically designed for filtering.

### 6.5 `ao-kernel metrics debug-query`

Non-Prometheus JSON query surface for operator debugging. Never emits textfile.

```bash
# All events in run X since a specific moment:
ao-kernel metrics debug-query \
  --run 00000000-0000-4000-8000-000000000001 \
  --since 2026-04-17T18:00:00+00:00 \
  --output debug.json
```

**`--since` contract:** ISO-8601 with **mandatory timezone** (`Z` or `+HH:MM`). Naive input is rejected at argparse:

```
error: argument --since: timezone required, use 'Z' or '+HH:MM' offset
```

Epoch integers are also rejected — the contract insists on ISO-8601 string form so there is no ambiguity about the reference frame.

### 6.6 Cardinality hard-warning

**Do not opt into advanced labels with ephemeral values.** The schema's closed enum constrains *names* (`model`, `agent_id`) but not *values*. If an operator sets `labels_advanced.allowlist = ["agent_id"]` and the runtime sees a fresh `agent_id` per request (e.g., containing a UUID), Prometheus will accumulate unbounded time series — one per request — and storage will collapse.

Treat `agent_id` and `model` as **bounded enumerations** in the workspace. `agent_id` should be a small set of deployment names ("crawler", "reviewer", "planner", …), and `model` the short list of actually-used LLM models. Do not set `agent_id` to a per-request token. This is a non-retrieval-specific invariant: the textfile collector accepts whatever is emitted and Prometheus replicates the mistake forever.

Future formats (OpenMetrics, StatsD, InfluxDB) are not in scope for B5; they are deferred to post-FAZ-E if demanded.

## 7. Cross-References

- Schema: [`policy-metrics.schema.v1.json`](../ao_kernel/defaults/schemas/policy-metrics.schema.v1.json)
- Policy: [`policy_metrics.v1.json`](../ao_kernel/defaults/policies/policy_metrics.v1.json) (PR-B0 — dormant default)
- Runtime:
  - [`ao_kernel/metrics/policy.py`](../ao_kernel/metrics/policy.py) — loader + dataclass
  - [`ao_kernel/metrics/registry.py`](../ao_kernel/metrics/registry.py) — 8 families, lazy `prometheus_client`
  - [`ao_kernel/metrics/derivation.py`](../ao_kernel/metrics/derivation.py) — evidence → metric populator
  - [`ao_kernel/metrics/export.py`](../ao_kernel/metrics/export.py) — textfile serializer + banners
- CLI handlers: [`ao_kernel/_internal/metrics/cli_handlers.py`](../ao_kernel/_internal/metrics/cli_handlers.py), [`ao_kernel/_internal/metrics/debug_query.py`](../ao_kernel/_internal/metrics/debug_query.py)
- Grafana dashboard: [`docs/grafana/ao_kernel_default.v1.json`](grafana/ao_kernel_default.v1.json), [`docs/grafana/README.md`](grafana/README.md)
- OTEL spans: [`ao_kernel/telemetry.py`](../ao_kernel/telemetry.py), docstrings therein
- Cost events consumed: `llm_spend_recorded` + `llm_usage_missing` (emitted by [`ao_kernel/cost/middleware.py`](../ao_kernel/cost/middleware.py); `duration_ms` additive field from PR-B5 C2b)

## 8. Document Status

Operator runbook + cost-disjunction + cardinality warning landed in PR-B5 C5. Future revisions may add: histogram bucket knob walk-through (FAZ-D), streaming token metrics (FAZ-C), evidence → metric extraction recipe beyond the current eight families.
