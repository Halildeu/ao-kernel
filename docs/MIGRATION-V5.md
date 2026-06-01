# Migration Guide: v4.x → v5.0.0

**Status:** Draft (Epic 8 E-8-6 of V5 Full Production Promotion Roadmap)
**Target release:** 2026-12-31 (forecast)
**Audience:** Operators upgrading from v4.0.0 / v4.1.0 to v5.0.0

> **Important — v5.0.0 is a governance plane promotion, not a runtime
> breaking change.** The supported `narrow stable runtime` surface
> (4.0.0 baseline) is preserved verbatim. Three guard flags
> (`support_widening`, `production_platform_claim`,
> `live_adapter_execution`) remain `const false` unless and until
> Epic 9 final promotion lands with explicit operator authorization.

---

## 1. TL;DR

| Question | Answer |
|---|---|
| Breaking runtime changes? | **No.** Public facade (`AoKernelClient`, MCP tools, CLI) unchanged. |
| Schema breakage? | **No.** Existing artifacts (`policy_*.v1.json`, `ao-ma-*.v1.json`) backward-compatible. |
| Required ops work? | Optional — adopt OTEL prod tunables (Epic 5 E-5-1) + Grafana dashboard (PR-B5) for production telemetry. |
| Guard flag flips? | **No.** v5.0.0 keeps all three guard flags `const false`. Live adapter / support widening / production-platform claim remain operator-bound and require Epic 9 supersession. |
| Downgrade path? | `pip install ao-kernel==4.1.0`. No data migration required. |
| Workspace `.ao/` compat? | Yes. v5.0.0 reads v4.x workspace artifacts unchanged. |

---

## 2. What changed (Epic 1-9 summary)

Each epic ships as a self-contained slice with cross-AI peer review,
ao-release-gate enforcement, and evidence trail in repo. See
[`.claude/plans/V5-FULL-PRODUCTION-PROMOTION-ROADMAP.md`](../.claude/plans/V5-FULL-PRODUCTION-PROMOTION-ROADMAP.md)
for the SSOT.

### Epic P0 — Promotion governance + visibility source manifest

- V5 issue mirror created on GitHub (milestone `v5.0.0` + 13 issues
  #773-#785 + 23 labels + project board).
- `v5_issue_projection.v1.json` is the **authority** (repo-local);
  GitHub project board is a one-way **visibility mirror**.
- `github_write_authorized: true` flag governs mirror write
  operations. AO-MA-11E-2 drift checker (Epic 1 E-1-2) enforces.

### Epic 1 — AO-MA-SPM follow-up (sistem mod aktivasyon)

- **AO-MA-11A-2** (PR #792 → main `009d43b`): GitHub Environment
  `ao-ma-plan-approval` gate wiring. Plan-approval bundle binding via
  CLI (`scripts/ao_ma11a2_plan_approval_gate.py`) + 7-stage canonical
  emitter + `--validate-only` flag + 5-retry approval polling.
- **AO-MA-11E-2** (PR #788 + #789 + #790): V5 mirror drift checker +
  write sync workflow (Projects v2 graceful degradation + PAT
  fallback `secrets.REPO_GH_PAT_PROJECTS_RW || secrets.GITHUB_TOKEN`).
- **AO-MA-11G-2c/2d:** changelog enforcement (CI workflow + pre-commit).
- **AO-MA-4.6-2:** native-import operator dogfooding.
- **ADR cross-AI revalidation:** ADR-0001..0004.

### Epic 2 — Live adapter execution (operator-bound supersession)

- `live_adapter_execution=true` flip requires Epic 9 supersession PR.
- Production runbook for live adapter envelope + cost guardrails +
  circuit breaker production limits.
- 4.5 stub → 4.6 native-import → real LLM worker production envelope
  (Anthropic + OpenAI + Mavis canlı providers).
- Real-adapter test suite (no mocks; SLA budget; cost tracking enabled).
- OTEL trace gerçek provider calls + usage/cost metrics.

### Epic 3 — Support widening (operator-bound supersession)

- `support_widening=true` flip requires Epic 9 supersession PR.
- Windows desktop support widening (current `Operating System ::
  POSIX` → Windows + macOS Apple Silicon + Linux ARM64).
- Python 3.10 backward compat decision.
- Provider widening matrix (Mistral / Cohere / Llama).
- ARM64 / Apple Silicon Docker images (CI multi-arch).

### Epic 4 — Deployment, operations, tenancy

- k8s Helm chart (governance microservice deploy).
- Production deploy runbook (k8s + standalone + Docker Compose).
- Multi-tenant config recipe (RBAC + secret isolation + quota + audit).
- Tenancy isolation test suite (cross-tenant leak prevention).
- Per-tenant cost tracking + rate limit
  (`cost_tracking.available const false` → flip).
- Operator incident response runbook (rollback + tag revert + pause).

### Epic 5 — Observability + production telemetry

- **E-5-1** (PR #791 → main `a8defc9`): OTEL production tracing
  tunables. `ao_kernel/telemetry_config.py` —
  `ProductionTelemetryConfig` frozen dataclass + `MappingProxyType` +
  9 env vars (see [§4 below](#4-otel-production-tunables-quick-start)).
- **E-5-2** (PR-B5 dashboard, pre-V5 baseline): Prometheus textfile
  metrics + Grafana dashboard at `docs/grafana/ao_kernel_default.v1.json`
  (8 panels covering LLM cost/latency/usage-miss, policy denial,
  workflow duration, coordination claims).
- **E-5-3** Distributed tracing (multi-session correlation; planned).
- **E-5-4** SLI/SLO definitions (planned).
- **E-5-5** Alertmanager rule templates (planned).

### Epic 6 — Security + compliance

- SBOM generation (cyclonedx-py; release artifact).
- Vulnerability scanning (Dependabot + Trivy + Snyk).
- SOC2/ISO 27001 audit-ready documentation paketi (NOT certification).
- 3rd party license compliance audit (MIT bağımlılık matrisi).
- CodeQL workflow (GitHub Advanced Security).
- Security incident response playbook.

### Epic 7 — Performance + scalability

- Production benchmark suite (cross-PR regression detection).
- Long-running session stress test (24h+ continuous).
- Memory profiling (mprof; production resource budgets).
- Provider rate limit production tuning per-tenant.
- `pgvector` backend implementation (current extra pin'li, henüz
  backend yok).

### Epic 8 — Documentation + onboarding

- Production deployment guide (k8s + standalone).
- Multi-tenant production config recipe (Epic 4-3 ile uyumlu).
- Operator runbook (incident response; Epic 4-6 ile).
- API reference auto-generated (Sphinx + autodoc).
- Tutorial: "Build your own AO-MA-SPM program with AI."
- **E-8-6** Migration guide (this document).

### Epic 9 — Final promotion decision (operator-bound)

- 9-dimensional evidence matrix complete.
- Operator açık beyan ("I authorize the production claim flip").
- v5.0.0 release notes + social media plan.
- Migration guide ready (this document).
- PR squash mesajında flag flip + evidence ref + operator
  authorization açık kayıt.

---

## 3. Upgrade steps (v4.x → v5.0.0)

> v5.0.0 is not yet released. The steps below are the **planned**
> upgrade path; they describe what an operator will run once Epic 9
> ships. Until then, `pip install -U ao-kernel` stays on v4.1.0.

### 3.1 Pre-upgrade snapshot (mandatory)

```bash
# Capture current state for downgrade safety net
ao-kernel version
python -m pip show ao-kernel
mkdir -p backup/$(date +%Y%m%d-%H%M%S)
cp -a .ao/ backup/$(date +%Y%m%d-%H%M%S)/
```

### 3.2 Upgrade

```bash
pip install -U ao-kernel==5.0.0
# or follow latest stable:
pip install -U ao-kernel
```

### 3.3 Post-upgrade verification (mandatory)

```bash
ao-kernel version         # → 5.0.0
ao-kernel doctor          # 8 health checks, all green
ao-kernel policy-sim --dry-run  # policy load OK
```

### 3.4 Optional production telemetry adoption (Epic 5)

Existing v4.x deployments without OTEL telemetry remain unchanged —
OTEL is opt-in via the `[otel]` extra:

```bash
pip install -U "ao-kernel[otel]==5.0.0"
```

Configure via env vars (see [§4 below](#4-otel-production-tunables-quick-start)).

### 3.5 Optional Grafana dashboard adoption (Epic 5)

```bash
# Stand up Prometheus textfile collector (every minute)
crontab -e
# Add: * * * * * /usr/local/bin/ao-kernel metrics export --output /var/lib/node_exporter/textfile/ao-kernel.prom

# Import dashboard
curl -X POST \
  -H "Authorization: Bearer $GRAFANA_API_TOKEN" \
  -H "Content-Type: application/json" \
  -d @docs/grafana/ao_kernel_default.v1.json \
  "https://grafana.example.com/api/dashboards/db"
```

See [`docs/grafana/README.md`](grafana/README.md) for full import recipes.

### 3.6 Downgrade path (safety net)

```bash
# Revert package
pip install ao-kernel==4.1.0

# Restore workspace from backup (only if data drift suspected)
rm -rf .ao/
cp -a backup/<timestamp>/.ao/ ./
```

> v5.0.0 does **not** mutate v4.x workspace artifacts in a non-reversible
> way. The downgrade above is safe for clean rollbacks. If your
> deployment adopted multi-tenant per-tenant cost tracking (Epic 4-5
> guard flip), preserve `cost_tracking.v1.json` carefully — that flip
> is data-state, not just config.

---

## 4. OTEL production tunables quick start

Adopt the [Epic 5 E-5-1](https://github.com/Halildeu/ao-kernel/pull/791)
production-grade OTEL tunables via env vars:

```bash
export AO_KERNEL_OTEL_ENABLED=true
export AO_KERNEL_OTEL_EXPORTER_OTLP_ENDPOINT=https://otel-collector.example.com:4317
export AO_KERNEL_OTEL_SAMPLING_RATE=0.1                # 10% sampling
export AO_KERNEL_OTEL_BATCH_SIZE=512
export AO_KERNEL_OTEL_SERVICE_NAME=ao-kernel-prod
export AO_KERNEL_OTEL_RESOURCE_ATTRIBUTES=deployment.environment=production,service.namespace=platform
export AO_KERNEL_OTEL_INSECURE=false
export AO_KERNEL_OTEL_EXPORT_TIMEOUT_MS=10000
export AO_KERNEL_OTEL_HEADERS=x-custom-header=value1,x-another=value2
```

Bounds:
- `SAMPLING_RATE` ∈ `[0.0, 1.0]` (1.0 = full trace)
- `BATCH_SIZE` ∈ `[1, 10000]`
- `EXPORT_TIMEOUT_MS` ∈ `[100, 600000]` (100ms – 10min)
- `HEADERS` — sensitive value detection redacts errors (no leak in logs)

Verify with:

```bash
ao-kernel doctor  # OTEL config validation included
```

---

## 5. V5 mirror discipline (operator-relevant)

V5.0.0 introduces a **manifest authority + visibility mirror**
discipline for GitHub project tracking:

- `v5_issue_projection.v1.json` (repo-local) is **authority**.
- GitHub project / milestone / issues / labels are **one-way mirrors**.
- Direct GitHub state edits drift; the AO-MA-11E-2 drift checker
  detects + flags drift via `mirror_drift_detected` finding.
- Mirror writes are gated:
  - Workflow: `.github/workflows/ao-ma-11e-2b-mirror-sync.yml`
  - Environment: `ao-ma-mirror-sync` (operator-bound required reviewer).
  - Apply confirmation token: `AO-MA-11E-2B-APPLY`.
  - PAT fallback: `secrets.REPO_GH_PAT_PROJECTS_RW || secrets.GITHUB_TOKEN`.

If you maintain a fork or downstream copy, do not edit V5 mirror
artifacts directly — submit changes via `v5_issue_projection.v1.json`
amend PR + mirror sync workflow dispatch.

---

## 6. Plan-approval gate discipline (operator-relevant)

V5.0.0 adds GitHub Environment-protected plan approval as the **single
human approval gate** in the autonomous multi-AI orchestration loop:

- Workflow: `.github/workflows/ao-ma-11a-plan-approval.yml`
- Environment: `ao-ma-plan-approval` (required reviewer).
- Apply confirmation token: `AO-MA-11A-2-APPROVE`.
- Self-review prevention: workflow rejects approvals from the same
  identity that triggered the dispatch.
- Plan binding: bundle `plan_digest` must match canonical digest
  computed at dispatch time (PYTHONHASHSEED-deterministic).

Operator setup (post-merge):

1. Open `https://github.com/Halildeu/ao-kernel/settings/environments/new`
2. Name: `ao-ma-plan-approval`
3. Required reviewers: yourself (or designated reviewer team)
4. Prevent self-review: **true** (defense in depth)
5. Wait timer: 0

Once configured, the workflow's `approve` job will pause for human
approval before emitting `executed` decision.

---

## 7. Known migration gotchas

### 7.1 `ao-release-gate` finding taxonomy (v4.1.0 → v5.0.0)

The release gate's procedural evidence findings
(`review_evidence_not_accepting`, `review_evidence_context_unverifiable`)
moved from `failure` to `action_required` semantic in PR #793
(RG-019e830d extension). Effect:

- Previously: high-risk PR without evidence file → red CI.
- Now: high-risk PR without evidence file → `action_required` on
  `ao-release-gate-review` (yellow "needs attention" UI signal).
- `allow=false` decision unchanged; merge **still blocked** until
  CODEOWNER review or evidence accept.
- Structural defects (`missing`, `schema_invalid`, `context_unbound`)
  remain `failure` (red CI).

If your branch protection ruleset has `ao-release-gate` (legacy
wrapper) as the only required check, verify
`ao-release-gate-technical` + `ao-release-gate-review` are added as
required + source-pinned before relying on the new semantic:

```bash
gh api repos/Halildeu/ao-kernel/rules/branches/main \
  --jq '.[] | select(.type=="required_status_checks") |
        .parameters.required_status_checks[].context'
```

### 7.2 Workspace `.ao/` layout drift

V5.0.0 introduces additional consultation / promotion / canonical
decision storage (E2 consultations from v3.6+ via
`ao_kernel.consultation.promotion.query_promoted_consultations`).
Workspace mode auto-migrates; library mode unaffected. Run
`ao-kernel doctor` after upgrade — it surfaces any unmigrated state.

### 7.3 Pre-existing 4.x behavior preservation

The following remain unchanged across the v5.0.0 promotion:

- Public facade API surface (`AoKernelClient`, MCP tools, CLI commands).
- Existing schema versions (`policy_*.v1.json`, evidence artifacts).
- Sync-API contract (no async surface promotion).
- Default support boundary: `narrow stable runtime`.
- Three guard flags: `const false` (until Epic 9 explicit operator
  flip).

---

## 8. References

- [V5 Full Production Promotion Roadmap](../.claude/plans/V5-FULL-PRODUCTION-PROMOTION-ROADMAP.md)
- [AO-MA-SPM Master Plan](../.claude/plans/AO-MA-SPM-MASTER-PLAN.md)
- [Upgrade Notes (general)](UPGRADE-NOTES.md)
- [Public Beta Support Boundary](PUBLIC-BETA.md)
- [Metrics Documentation](METRICS.md)
- [Grafana Dashboard Import](grafana/README.md)
- [Operations Runbook](OPERATIONS-RUNBOOK.md)
- [Rollback Runbook](ROLLBACK-RUNBOOK.md)
- [Known Bugs](KNOWN-BUGS.md)

---

## 9. Document status

- **Created:** Epic 8 E-8-6 V5 promotion roadmap follow-up.
- **Implementer provider:** Anthropic Claude.
- **Reviewer provider:** OpenAI Codex (post-impl cross-AI peer review).
- **Last v5.0.0 final-release update:** TBD (Epic 9 finalization).
- **Living document:** updated as each Epic 1-9 slice merges.
