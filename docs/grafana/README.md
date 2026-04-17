# ao-kernel Grafana dashboards

`ao_kernel_default.v1.json` is a **default observability dashboard** for the eight metric families emitted by `ao-kernel metrics export` (PR-B5). It ships with the repository so operators can import a known-good surface without hand-rolling queries.

## Panel → metric matrix

| # | Panel | Metric family | PromQL |
|---|---|---|---|
| 1 | LLM call duration p95 | `ao_llm_call_duration_seconds` | `histogram_quantile(0.95, sum(rate(ao_llm_call_duration_seconds_bucket[5m])) by (provider, le))` |
| 2 | LLM tokens/s | `ao_llm_tokens_used_total` | `sum(rate(ao_llm_tokens_used_total[5m])) by (provider, direction)` |
| 3 | LLM cost USD/hour | `ao_llm_cost_usd_total` | `sum(rate(ao_llm_cost_usd_total[1h])) by (provider) * 3600` |
| 4 | LLM usage-missing rate | `ao_llm_usage_missing_total` | `sum(rate(ao_llm_usage_missing_total[5m])) by (provider)` |
| 5 | Policy deny rate | `ao_policy_check_total` | `sum(rate(ao_policy_check_total{outcome="deny"}[5m]))` |
| 6 | Workflow duration p95 | `ao_workflow_duration_seconds` | `histogram_quantile(0.95, sum(rate(ao_workflow_duration_seconds_bucket[5m])) by (final_state, le))` |
| 7 | Active coordination claims | `ao_claim_active_total` | `ao_claim_active_total` |
| 8 | Claim takeovers (1h) | `ao_claim_takeover_total` | `increase(ao_claim_takeover_total[1h])` |

The dashboard shape test (`tests/test_grafana_dashboard_shape.py`) pins the fact that every panel's first target references the metric family in the table above.

## Import recipes

### 1. Grafana UI (manual)

1. Open **Dashboards → New → Import**.
2. Click **Upload JSON file** and select `docs/grafana/ao_kernel_default.v1.json`.
3. Pick your Prometheus datasource for `DS_PROMETHEUS`.
4. Click **Import**.

### 2. Local file provisioning (self-hosted Grafana)

```yaml
# /etc/grafana/provisioning/dashboards/ao-kernel.yaml
apiVersion: 1
providers:
  - name: ao-kernel
    orgId: 1
    folder: ao-kernel
    type: file
    disableDeletion: false
    updateIntervalSeconds: 60
    allowUiUpdates: true
    options:
      path: /var/lib/grafana/dashboards/ao-kernel
```

Copy `ao_kernel_default.v1.json` to `/var/lib/grafana/dashboards/ao-kernel/`.

### 3. Kubernetes ConfigMap (grafana-operator)

```bash
kubectl create configmap ao-kernel-default-dashboard \
  --from-file=ao_kernel_default.v1.json=docs/grafana/ao_kernel_default.v1.json \
  -n monitoring
```

Reference the ConfigMap from your `GrafanaDashboard` CR or sidecar loader.

### 4. Grafana HTTP API

```bash
curl -X POST \
  -H "Authorization: Bearer $GRAFANA_API_TOKEN" \
  -H "Content-Type: application/json" \
  -d @docs/grafana/ao_kernel_default.v1.json \
  "https://grafana.example.com/api/dashboards/db"
```

## Prerequisite: Prometheus textfile scrape

Every panel assumes a Prometheus instance scrapes the textfile ao-kernel writes:

```bash
ao-kernel metrics export --output /var/lib/node_exporter/textfile/ao-kernel.prom
```

Wire this into a cron job (every minute) or a systemd timer. The **textfile collector** on your node_exporter or pushgateway-free equivalent ingests the file on the next scrape.

## Dormant workspaces

When `policy_metrics.v1.json.enabled=false` (bundled default) the textfile contains only banner comments — Grafana renders every panel as "No data". That is the intended behaviour; the banner spells out the rationale so operators can opt in explicitly.

## Cost-tracking prerequisite

LLM panels (1–4) depend on `policy_cost_tracking.v1.json.enabled=true`. When cost tracking is dormant the textfile omits the `ao_llm_*` family entirely and the four LLM panels display "No data" — see `docs/METRICS.md` §6 for the disjunction contract.

## Advanced labels (opt-in, high cardinality)

Set `labels_advanced.enabled=true` and list values in `allowlist` (closed enum: `model`, `agent_id`) to expand the panels with an extra dimension. Cardinality warning: do not set `agent_id` to an ephemeral / per-request string — the time-series explosion will crush your Prometheus storage.
