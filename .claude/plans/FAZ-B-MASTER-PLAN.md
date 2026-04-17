# FAZ-B Master Plan — Ops Hardening (v3.2.0)

**4 hafta / 9 PR target / v3.2.0 release.** Post-CNS-027 iter-1 PARTIAL (4B absorbed). B8 (network sandbox) **stretch/deferred** — v3.2.x veya FAZ-C scope.

## 1. Scope (strategy §3 P1)

9 item, 6 workstream:

| # | Feature | Category | Workstream |
|---|---|---|---|
| 4 | Multi-agent lease/fencing + capability matrix | build | **Agent coordination** |
| 18 | Code review AI workflow step | write-lite | **AI workflow steps** |
| 20 | Commit AI (auto-message) | write-lite | **AI workflow steps** |
| 7 (full) | Cost tracking full + price catalog | build | **Cost + routing** |
| 21 | Model routing by cost | build | **Cost + routing** |
| NEW | Policy simulation harness | build | **Policy ops** |
| NEW | Price catalog + spend ledger | build | **Cost + routing** |
| NEW | Metrics export (Prometheus / OTEL) | integrate `[metrics]` | **Observability** |
| NEW | Agent benchmark / regression suite | build | **Quality gate** |

## 2. Release Gates (strategy §10)

- [ ] Governed review + governed bugfix benchmarks pass
- [ ] Cost cap fail-closed test: budget exceeded → deny + audit
- [ ] Policy simulation reports deny/allow diff for fixture changes
- [ ] Metrics export visible in Prometheus + Grafana dashboard
- [ ] **Lease/fencing race test**: two concurrent agents, one owns claim, second receives `CLAIM_CONFLICT` with fencing_token, expired claim takeover works
- [ ] Pre-FAZ-B design note for #4 lease/fencing (CNS-016 recommendation)

## 3. PR Breakdown (9 PRs post CNS-027 absorb)

| PR | Scope | Deps | LOC est |
|---|---|---|---|
| **B0** | Design note: lease/fencing spec + benchmark contract + cost/metrics schemas (docs-first, A0 pattern) | — | ~1500 |
| **B1** | Multi-agent lease/fencing core (#4): `ao_kernel/coordination/` package — claim, fencing_token, heartbeat, takeover, CAS expected_revision, evidence events | B0 | ~2000 |
| **B2** | Cost tracking full (#7) + price catalog (NEW) + spend ledger (NEW): `ao_kernel/cost/` package | B0 | ~1500 |
| **B3** | Model routing by cost (#21): `ao_kernel/llm.py` resolve_route cost-aware + cost policy | B2 | ~800 |
| **B4** | Policy simulation harness (NEW): `ao_kernel/policy_sim/` — mid-depth simulator reusing `governance.check_policy` + executor policy primitives (`build_sandbox`, `resolve_allowed_secrets`, `check_http_header_exposure`) **without worktree/adapter side-effects**. Dry-run policy change → deny/allow diff report. | — | ~1200 |
| **B5** | Metrics export (NEW): `ao_kernel/metrics/` + `[metrics]` extra. **Prometheus textfile export as primary surface** (low-cardinality default labels; advanced labels schema-gated via `policy_metrics.v1.json`). OTEL bridge is NOT in scope — `[metrics]` and `[otel]` extras stay independent per `docs/METRICS.md` §5 ("does not read OTEL spans or attempt bridge translation"). Corrected in pre-B2 docfix (CNS-030 Q3 absorb). | — | ~1000 |
| **B6** | Code review AI workflow step (#18) + commit AI (#20): 2 write-lite bundled workflows + adapter step definitions | B1 | ~800 |
| **B7** | Agent benchmark / regression suite (NEW): `tests/benchmarks/` framework + governed-review + governed-bugfix scenarios | B1, B2, B6 | ~1000 |
| ~~B8~~ | ~~OS-level network sandbox~~ | ~~B1~~ | ~~stretch/deferred to v3.2.x or FAZ-C (CNS-027 B1: 4-week timeline risk)~~ |
| **B8** | Integration + v3.2.0 release: CHANGELOG finalize + version bump + tag | all | ~200 |

**Total estimated:** ~10,000 LOC across 9 PRs (network sandbox deferred).

## 4. Workstream Dependencies

```
B0 (design note)
├── B1 (lease/fencing) ← core coordination primitive
│   ├── B6 (review AI + commit AI workflows)
│   ├── B7 (benchmarks) ← uses B1 + B2 + B6
│   └── B8 (network sandbox)
├── B2 (cost + price catalog + spend ledger)
│   ├── B3 (cost-aware routing)
│   └── B7 (benchmarks)
├── B4 (policy simulation) ← independent
└── B5 (metrics export) ← independent

B8 (release) ← depends on all  # renumbered; network sandbox deferred
```

**Parallel tracks:**
- B4 (policy sim) + B5 (metrics) can run in parallel with B1/B2
- B6 (AI workflows) + B8 (network sandbox) depend on B1
- B7 (benchmarks) is last-before-release

## 5. #4 Lease/Fencing Design Note (B0 scope)

CNS-016 recommendation: mini-CNS or inline spec before FAZ-B starts.

**Core concepts:**
- `Claim`: `{claim_id, owner_agent_id, resource_id, fencing_token, acquired_at, expires_at, heartbeat_at}`
- `fencing_token`: monotonic per-resource (inc on acquire/takeover)
- `heartbeat`: periodic CAS update `heartbeat_at`; expired claim → takeover eligible
- `takeover`: new agent acquires expired claim; old owner's operations rejected via stale fencing_token
- `CLAIM_CONFLICT`: second agent trying to acquire held claim → error with current owner's fencing_token
- CAS: `expected_revision` on claim mutation (same pattern as run_store)
- Evidence events: `claim_acquired`, `claim_released`, `claim_heartbeat`, `claim_expired`, `claim_takeover`, `claim_conflict` (6 new event kinds → 24-kind taxonomy; flat prefix, no namespace — CNS-027 Q3 AGREE)
- **Policy (CNS-027 B2 absorb):** YENİ `policy_coordination_claims.v1.json` (ayrı dosya; mevcut `policy_multi_agent_coordination.v1.json` worktree/branch scope'u, `additionalProperties: false` — lease alanları oraya sığmaz). Alanlar: max_claims_per_agent, heartbeat_interval_seconds, expiry_seconds, takeover_grace_period
- **Heartbeat (CNS-027 B3 absorb):** Caller-driven (`claim.heartbeat()` explicit çağrı). Evidence event yalnızca audit izi — liveness kararı evidence'e bağlı DEĞİL (CLAUDE.md §2: evidence fail-open side-channel; claim liveness correctness-critical).
- **Claim storage (CNS-027 B4 absorb):** File CAS per-resource + **global claims index** (`{workspace}/.ao/claims/_index.v1.json`) under workspace-level lock. `max_claims_per_agent` bu index üzerinden enforce edilir (per-resource lock yetersiz; global lock + index = atomic global quota). SQLite deferred — file CAS pattern proven, yeni dep yok.

**Key questions resolved (CNS-027 iter-1):**
1. Claim storage: file CAS per-resource + global index (B4 absorb)
2. Fencing token validation: driver-level check (Executor.run_step checks `fencing_token` if `driver_managed=True`)
3. Heartbeat: caller-driven, NOT evidence-based (B3 absorb)
4. Multi-workspace: single workspace, federation deferred

## 6. Metrics Export Design Sketch (B5 scope)

- `ao_kernel/metrics/` package under `[metrics]` extra
- Prometheus: `prometheus_client` counters/histograms for LLM latency, token usage, policy check count, workflow duration
- OTEL mapping: existing `ao_kernel/telemetry.py` OTEL spans → metrics bridge
- Dashboard: Grafana JSON model template (not hosted — operator brings own Grafana)
- Evidence-based: MCP event JSONL + workflow JSONL → metric extraction pipeline

## 7. CNS-027 Questions (FAZ-B plan adversarial)

6 strategic questions:

**Q1 — PR ordering.** B0 docs-first → B1 lease → B2 cost → parallel B3/B4/B5 → B6 AI workflows → B7 benchmarks → B8 release (9 PRs, network sandbox deferred to v3.2.x). Optimal mı?

**Q2 — Lease/fencing claim storage.** Per-workspace `.ao/claims/{resource_id}.v1.json` CAS files (run_store pattern) vs SQLite vs in-memory. File-based = no new dep, POSIX file_lock reuse, proven CAS pattern; SQLite = faster reads, row-level locking; in-memory = simplest but no durability.

**Q3 — Evidence taxonomy expansion.** FAZ-A shipped 18 kinds. B1 adds 6 coordination kinds (24 total). B5 may add metrics-specific kinds. Total expansion acceptable for v3.2.0 or should we use a "namespace" pattern (`coordination.claim_acquired`) to prevent taxonomy bloat?

**Q4 — Policy simulation scope.** Dry-run mode: load current policies + proposed change → re-evaluate fixture scenarios → deny/allow diff. How deep: just `governance.check_policy` replay, or full `Executor.run_step` dry-run (heavier, needs adapter mock)?

**Q5 — Metrics extra dep.** `prometheus_client` is BSD-licensed, lightweight. `opentelemetry-api` already in `[otel]` extra. Should `[metrics]` be `prometheus_client` only, or `prometheus_client + opentelemetry-api` bundled?

**Q6 — 4-week timeline.** 9 PRs in 4 weeks (B8 network sandbox stretch/deferred). FAZ-A (8 PRs) took ~2 days of active development. FAZ-B similar density but more independent primitives. Realistic?

## 8. Audit Trail

| Field | Value |
|---|---|
| Plan version | **v2** |
| Head SHA | `b3b1dce` (v3.1.0) |
| Strategy ref | TRANCHE-STRATEGY-V2.md §3 P1, §10 FAZ-B |
| CNS-027 thread | NEW |

| CNS-027 thread | `019d9436-a702-7fa0-996a-ab1c8aeff71f` |

**Status:** Plan v2. Submit iter-2.
