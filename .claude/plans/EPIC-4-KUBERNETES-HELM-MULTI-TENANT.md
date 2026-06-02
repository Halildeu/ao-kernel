# Epic 4 — Deployment, Operations, Tenancy (Kubernetes Helm + Multi-Tenant Pattern)

> **Statü:** PROPOSED · V5 roadmap'in 4. epic'i. PR-X0 (`V5-FULL-PRODUCTION-PROMOTION-ROADMAP.md`) ile mühürlenmiş E-4-1..E-4-6 sub-slice tabanı bu plana göre genişletilir.
> **Parent:** `.claude/plans/V5-FULL-PRODUCTION-PROMOTION-ROADMAP.md` §3 Epic 4
> **Owner:** Halil Kocoglu · **Cross-AI consensus:** TBD per-slice (Codex MCP plan-time iter; Mavis/MiniMax kritik slice'larda 3-way)
> **Bağımlılık:** Epic 1 (sistem mod aktivasyon) + Epic 2 paralel (live adapter envelope opsiyonel; bu epic'in template'leri için **gerekli değil** — operator-side runbook olarak yayınlanır)
> **Risk:** high (cross-tenant isolation pattern + multi-namespace pattern docs) · **Forecast:** 4-6 hafta lazy infaza yayılır

> **Authority hatırlatması (V5 invariant #1):** Bu epic **hiçbir guard flag flip ETMEZ**. Helm chart + multi-tenant pattern + operator runbook'lar **opsiyonel `[k8s-helm]` extra** ve **operator-side artifact** olarak yayınlanır. `live_adapter_execution` / `support_widening` / `production_platform_claim` üçü de **const false** kalır. Final guard flag flip yetkisi **PR-Xfinal** operator-bound supersession decision'da. Epic 4'ün hiçbir slice'ı tek başına bu yetkiyi taşımaz.

---

## 1. Scope

### Ne ekler

- `deploy/helm/ao-kernel/` altında **operator-installable Helm chart skeleton** — Chart.yaml + values.yaml + 4-5 baseline template (Deployment, Service, ConfigMap, ServiceAccount + RBAC, NetworkPolicy)
- **Multi-tenant isolation pattern doc** (`docs/MULTI-TENANT-DEPLOYMENT.md`) — namespace-per-tenant + RBAC + secret isolation + quota + audit boundary tanımları; `tenant_isolation_matrix.v1.json` advisory artifact
- **Operator-owned PostgreSQL provisioning pattern doc** — operator DDL responsibility; ao-kernel hiçbir DDL execute etmez; env-only secret resolution
- **Observability surface template'leri** — opt-in Prometheus ServiceMonitor template + OpenTelemetry sidecar pattern doc (Microsoft Teams Power Automate primary alert sink per HARD RULE)
- **NetworkPolicy + PodSecurityStandards baseline** template'leri
- **helm-unittest CI invocation doc** (yeni workflow EKLENMEZ; runbook + lokal helm-unittest invocation)
- `pyproject.toml`'a opsiyonel `[k8s-helm]` extra (içerik: dependency YOK; sadece extras index'inde dökümantasyon işaretçisi olarak yer alır — wheel'a chart push edilmez)

### Out-of-scope (ZERO TOUCH)

- `.github/workflows/**` — Epic 4 hiçbir workflow file eklemez, mevcut workflow'lara dokunmaz
- `ao_kernel/` source modülleri — runtime'a yeni Python code path eklenmez
- Mevcut Epic 1-3, 5-7, 8 slice'larında çakışan kod path'leri — Epic 4 sadece `deploy/helm/`, `docs/`, opsiyonel `.claude/plans/E-4-*.v1.json` evidence
- Live Helm install/upgrade execution — chart **rendering** test'lenir (helm template + helm-unittest), `helm install` chain LIVE smoke YASAK (Epic 9 PR-Xfinal sonrası operator-side)
- Guard flag flip — hiçbir slice 3 guard flag'i değiştirmez; `support_widening_allowed=false` korunur
- `cost_tracking.available const false → flip` (V5 roadmap E-4-5 olarak listelenmiş; bu plan'da **AYRI EPIC slice'ı** olarak Epic 2 live adapter zincirine taşınır — Epic 4 scope dışı)
- "Production-ready" public claim — chart README'sinde dil "operator-installable beta template; production claim deferred to v5 final promotion" kalır

---

## 2. Slice Breakdown (6 slice; her biri ≤ 1 PR worth, additive only)

### E-4-1 — Helm Chart Skeleton (`deploy/helm/ao-kernel/`)

**Risk:** low (additive doc/template; runtime'a etki yok)
**Cross-AI:** Implementer Claude (Anthropic) · Reviewer Codex (OpenAI) · plan-time iter + post-impl review
**Bağımlılık:** YOK (V5 P0 mirror sonrası başlayabilir)

**Write-set:**

```
deploy/helm/ao-kernel/
  Chart.yaml                          # apiVersion v2; appVersion bind ao_kernel.__version__ (no auto-bump)
  values.yaml                         # replicaCount: 1 (HARD RULE; 0 YASAK), image.repo + tag, resources, env block (secret refs)
  values.schema.json                  # JSON Schema for values.yaml (strict; additionalProperties:false)
  templates/_helpers.tpl              # standart Helm helper'ları
  templates/deployment.yaml           # Deployment; replicas = .Values.replicaCount; ServiceAccount bind
  templates/service.yaml              # ClusterIP; healthz + readyz port
  templates/configmap.yaml            # workspace_root + non-secret config
  templates/serviceaccount.yaml       # default SA; minimum RBAC
  templates/rbac.yaml                 # Role + RoleBinding (namespace-scoped; ClusterRole YOK)
  templates/NOTES.txt                 # post-install message: "operator-installable beta; production claim deferred"
  README.md                           # chart usage + 6 invariant bullet (no flag flip, no live adapter, no secret in values, env-only)
.claude/plans/E-4-1-HELM-CHART-SKELETON.md
.claude/plans/E-4-1-HELM-CHART-SKELETON.v1.json   # schema-backed evidence (decision, write_set, no_guard_flip)
ao_kernel/defaults/schemas/e-4-1-helm-chart-evidence.schema.v1.json
```

**Acceptance:**
- `helm lint deploy/helm/ao-kernel/` clean (lokal; CI'da `make helm-lint` runbook'lu, workflow EKLENMEZ)
- `helm template` deterministic (3 ardışık render byte-identical, sha256 diff yok)
- `values.yaml::replicaCount` default = 1 (test invariant: schema `minimum: 1`)
- `values.schema.json` `additionalProperties:false` her object'te (strict)
- Hiçbir template `secret` value içermez (sadece secretKeyRef env'leri)

---

### E-4-2 — Multi-Tenant Namespace + RBAC Pattern Doc + `tenant_isolation_matrix.v1.json`

**Risk:** high (cross-tenant boundary docs; pattern yanlış dökümanlanırsa operator yanlış kurar)
**Cross-AI:** Implementer Claude · Reviewer Codex + Mavis (3-way: cross-tenant boundary kritik)
**Bağımlılık:** E-4-1 (chart skeleton kullanılır; örnek namespace overlay)

**Write-set:**

```
docs/MULTI-TENANT-DEPLOYMENT.md              # namespace-per-tenant pattern; 7 isolation dimension
.claude/plans/E-4-2-MULTI-TENANT-PATTERN.md
.claude/plans/E-4-2-MULTI-TENANT-PATTERN.v1.json
.claude/plans/tenant_isolation_matrix.v1.json   # advisory matrix; per-dimension status + evidence ref
ao_kernel/defaults/schemas/e-4-2-tenant-isolation-matrix.schema.v1.json
ao_kernel/defaults/schemas/e-4-2-multi-tenant-pattern-evidence.schema.v1.json
```

**`tenant_isolation_matrix.v1.json` 7 dimension (advisory only — runtime enforcement YOK):**

1. **Namespace isolation** — bir Helm release = bir namespace; ClusterRole YASAK
2. **RBAC scope** — Role + RoleBinding namespace-scoped; cross-namespace verb yok
3. **Secret isolation** — Kubernetes Secret per-namespace; cross-namespace mount engellenmiş (operator runbook)
4. **NetworkPolicy** — default-deny ingress + egress; sadece allowlist'li peer'lar (E-4-5'e bağlı)
5. **Resource quota** — ResourceQuota + LimitRange per-namespace (operator template)
6. **Audit boundary** — JSONL evidence per-namespace `workspace_root`; cross-tenant fact promotion YASAK (advisory note)
7. **Cost tracking advisory** — `cost_tracking.available` const false korunur; per-tenant cost tracking flip Epic 2/9 yetkisinde

**Acceptance:**
- Pattern doc'ta her 7 dimension için minimum 1 enforcement mekanizması (Kubernetes-native) + 1 operator runbook adımı
- `tenant_isolation_matrix.v1.json` schema strict (additionalProperties:false, 7 dimension required, per-dimension `status` enum)
- Schema'da `runtime_enforced: false` const + `operator_enforced: true` const — advisory boundary açık
- Cross-AI consensus 3-way evidence ref (Codex + Mavis verdict)

---

### E-4-3 — Operator-Owned PostgreSQL Provisioning Pattern + Secret Management

**Risk:** medium (DDL ownership boundary kritik; yanlış dökümanlanırsa operator ao-kernel'in DDL koşturduğunu sanır)
**Cross-AI:** Implementer Claude · Reviewer Codex
**Bağımlılık:** E-4-1 (values.yaml env structure kullanılır)

**Write-set:**

```
docs/OPERATOR-DATABASE-PROVISIONING.md        # operator DDL pattern; ao-kernel asla DDL çalıştırmaz
docs/OPERATOR-SECRET-MANAGEMENT.md            # env-only secret resolution; ASLA log/MCP param/values.yaml
.claude/plans/E-4-3-DB-SECRET-OPERATOR-OWNED.md
.claude/plans/E-4-3-DB-SECRET-OPERATOR-OWNED.v1.json
ao_kernel/defaults/schemas/e-4-3-operator-owned-evidence.schema.v1.json
```

**İçerik özeti:**

- **PostgreSQL DDL pattern (Epic 7-5 pgvector forward-compat):** operator manuel `psql` ile schema yaratır; ao-kernel migration runner GİBİ DAVRANMAZ; `pgvector` extra ileride backend gelirse de operator-side DDL kalır
- **Secret kaynak öncelik tablosu:** 1) Kubernetes Secret (operator-managed) → 2) env var (`secretKeyRef`) → 3) ao-kernel sadece `os.environ` resolve eder
- **YASAK pattern'ler:** values.yaml'da plain secret, ConfigMap'te API key, container args'da token, Helm release notes'da secret, JSONL evidence'a secret yazma (CLAUDE.md değişmez #3)
- **Microsoft Teams primary** alert delivery referansı (E-4-4 ile uyum) — yanlışlıkla Slack webhook seed'i önerme YASAK

**Acceptance:**
- Doc'ta operator-checklist (15+ adım): credential rotation, DR snapshot, RBAC binding, secret rotation cadence
- "ao-kernel DDL koşturmaz" ifadesi en az 3 yerde tekrarlanır (kritik framing)
- pgvector forward-compat note (Epic 7-5 ileride backend eklenirse pattern aynı kalır)

---

### E-4-4 — Observability Surface (ServiceMonitor Template + OTEL Sidecar Pattern Doc)

**Risk:** medium (alert delivery yanlış default'lanırsa Slack pattern sızar — HARD RULE Teams primary)
**Cross-AI:** Implementer Claude · Reviewer Codex
**Bağımlılık:** E-4-1 (chart skeleton'a opt-in template eklenir)

**Write-set:**

```
deploy/helm/ao-kernel/templates/servicemonitor.yaml   # ConditionalIf .Values.observability.serviceMonitor.enabled
deploy/helm/ao-kernel/values.yaml                     # observability.* default DISABLED (opt-in)
docs/OBSERVABILITY-DEPLOYMENT.md                      # OTEL sidecar pattern + alert delivery (Teams)
.claude/plans/E-4-4-OBSERVABILITY-SURFACE.md
.claude/plans/E-4-4-OBSERVABILITY-SURFACE.v1.json
ao_kernel/defaults/schemas/e-4-4-observability-evidence.schema.v1.json
```

**İçerik:**

- **ServiceMonitor template** Prometheus-Operator CRD; `.Values.observability.serviceMonitor.enabled = false` default; opt-in (`crd.spec.metric_endpoint` boş bırakılırsa render YAPILMAZ — conditional include)
- **OpenTelemetry sidecar pattern** sadece doc (chart'ta sidecar default EKLENMEZ); operator manuel ekler; lazy + no-op fallback (CLAUDE.md D12) korunur
- **Alert delivery default** (HARD RULE):

| Slot | Doğru pattern | Yasak pattern |
|---|---|---|
| Primary alert sink | **Microsoft Teams Power Automate workflow + Adaptive Card** (Alertmanager v4 webhook JSON raw POST; transform Power Automate flow içinde) | Slack webhook default kurma |
| Vault env key (operator) | `TEAMS_WEBHOOK_URL` (active); `SLACK_WEBHOOK_URL` (dormant, asset-preserved başka tenant için) | İki webhook key tek ExternalSecret altında (Ready=False zinciri) |
| Helm route matcher | Single-tenant `team=<x>` veya multi-tenant `tenant_channel=teams` | `slack_configs` LIVE rendered config (bizim için) |
| Reactivation chain (başka tenant Slack ister) | `runbooks/RB-teams-reactivation-chain.md` referansı + operator demand-driven explicit trigger | "Slack pattern silmek" — asset-preserved (multi-tenant gelecek için) |

- Slack snippet doc'ta **asset-preserved dormant** (silinmez), ama bizim chart default'unda LIVE config YAPILMAZ. Doc'ta "Slack reactivation chain only via tenant demand-driven explicit trigger" cümlesi.

**Acceptance:**
- Default `values.yaml::observability.serviceMonitor.enabled = false` (opt-in)
- Alert delivery section'ında Teams pattern primary; Slack asset-preserved dormant açıkça etiketlenmiş
- ServiceMonitor template conditional render (helm template `--set observability.serviceMonitor.enabled=false` → boş çıktı; `=true` → tek deterministic manifest)
- OTEL sidecar pattern doc + CLAUDE.md §11 telemetry lazy-import referansı

---

### E-4-5 — NetworkPolicy + PodSecurityStandards Baseline

**Risk:** medium (yanlış NetworkPolicy = cluster izolasyonu kırılır veya sağlam çalışmaz)
**Cross-AI:** Implementer Claude · Reviewer Codex
**Bağımlılık:** E-4-1 (chart template'lerine eklenir) + E-4-2 (multi-tenant boundary pattern kullanılır)

**Write-set:**

```
deploy/helm/ao-kernel/templates/networkpolicy.yaml         # default-deny + allowlist
deploy/helm/ao-kernel/templates/podsecuritypolicy.yaml     # PSS baseline labels (DEPRECATED PSP migration not gerek)
deploy/helm/ao-kernel/values.yaml                          # security.networkPolicy.enabled default true; security.podSecurityStandard "restricted" default
docs/CLUSTER-SECURITY-BASELINE.md                          # PSS profil + NetworkPolicy pattern + operator checklist
.claude/plans/E-4-5-SECURITY-BASELINE.md
.claude/plans/E-4-5-SECURITY-BASELINE.v1.json
ao_kernel/defaults/schemas/e-4-5-security-baseline-evidence.schema.v1.json
```

**İçerik:**

- **NetworkPolicy default-deny pattern:** default ingress + egress deny; sadece namespace-içi same-app peer + DNS egress (kube-dns)
- **Pod Security Standards (PSS):** baseline → restricted profil seçilebilir; pod labels `pod-security.kubernetes.io/enforce: restricted` operator-overlay'de
- **runAsNonRoot: true**, **readOnlyRootFilesystem: true**, **allowPrivilegeEscalation: false**, **capabilities.drop: [ALL]**
- **Egress allowlist pattern doc:** operator istediği LLM provider hostname'lerini namespace-overlay'de allowlist'e ekler (chart default minimum: kube-dns + cluster-internal)

**Acceptance:**
- NetworkPolicy template default ingress deny + DNS egress allow only (helm template'de doğrulanır)
- PSS labels values'tan override edilebilir ama default = `restricted`
- Doc'ta operator-checklist (PSP migration not, PSS adoption, NetworkPolicy CNI desteği kontrolü)
- `securityContext` block tüm container'larda render edilir (helm template invariant)

---

### E-4-6 — helm-unittest CI Invocation Doc + Lokal Test Runbook

**Risk:** low (sadece runbook + lokal test invocation; hiçbir CI workflow file EKLENMEZ)
**Cross-AI:** Implementer Claude · Reviewer Codex
**Bağımlılık:** E-4-1 + E-4-2 + E-4-4 + E-4-5 (test edilecek template'ler hazır)

**Write-set:**

```
deploy/helm/ao-kernel/tests/                   # helm-unittest test suite directory
  deployment_test.yaml
  service_test.yaml
  configmap_test.yaml
  rbac_test.yaml
  networkpolicy_test.yaml
  servicemonitor_test.yaml
  values_invariants_test.yaml                  # replicaCount >= 1; no flag flip in any rendered ConfigMap
docs/HELM-UNITTEST-RUNBOOK.md                  # lokal invocation; opsiyonel CI integration (gelecek epic)
.claude/plans/E-4-6-HELM-UNITTEST-RUNBOOK.md
.claude/plans/E-4-6-HELM-UNITTEST-RUNBOOK.v1.json
ao_kernel/defaults/schemas/e-4-6-helm-unittest-evidence.schema.v1.json
```

**İçerik:**

- **Lokal invocation:** `helm plugin install https://github.com/helm-unittest/helm-unittest` + `helm unittest deploy/helm/ao-kernel/`
- **CI runbook (NOT a workflow):** dökümanlanır; gelecek epic'te (PR-Xfinal sonrası, ayrı governance migration ile) `.github/workflows/helm-unittest.yml` eklenebilir; **bu Epic 4'te EKLENMEZ**
- **Test invariants:** her template için minimum 3 assertion (rendered manifest shape + no-secret-in-values + no-guard-flag-flip)
- **`values_invariants_test.yaml`:** ConfigMap'lerin hiçbirinde `support_widening: true` / `production_platform_claim: true` / `live_adapter_execution: true` string'i geçmediğini doğrular (AST-grep style)

**Acceptance:**
- Lokal `helm unittest deploy/helm/ao-kernel/` 100% pass
- Runbook'ta 5+ adım operator çalıştırma; opsiyonel CI integration not (workflow EKLENMEZ; gelecek epic'in scope'u)
- helm-unittest version pin (reproducible)

---

## 3. Risk Class per Slice (özet)

| Slice | Risk | Sebep |
|---|---|---|
| E-4-1 Helm chart skeleton | **low** | additive template/doc; runtime'a etki yok; replica default 1 (HARD RULE) |
| E-4-2 Multi-tenant pattern + matrix | **high** | cross-tenant boundary docs; 3-way cross-AI |
| E-4-3 DB + secret operator-owned | **medium** | DDL ownership boundary kritik |
| E-4-4 Observability surface | **medium** | Teams default primary; Slack pattern asset-preserved dormant (HARD RULE) |
| E-4-5 NetworkPolicy + PSS | **medium** | yanlış config cluster izolasyonu kırar |
| E-4-6 helm-unittest runbook | **low** | sadece doc + lokal test; CI workflow EKLENMEZ |

**Hiçbir slice "critical" değildir** çünkü hiçbiri guard flag flip'i tetiklemez. Critical risk Epic 9 final operator-bound PR'a kalır.

---

## 4. Cross-AI Consensus Protocol per Slice

| Slice | Implementer | Reviewer | İlave |
|---|---|---|---|
| E-4-1 | Claude (Anthropic) | Codex (OpenAI) | plan-time iter + post-impl review (iki ayrı kapı) |
| E-4-2 | Claude (Anthropic) | Codex (OpenAI) + **Mavis (MiniMax)** | 3-way; cross-tenant kritik boundary |
| E-4-3 | Claude (Anthropic) | Codex (OpenAI) | DDL ownership doc; standart iki-gate |
| E-4-4 | Claude (Anthropic) | Codex (OpenAI) | Teams/Slack pattern doğrulamak için; tek-reviewer yeterli |
| E-4-5 | Claude (Anthropic) | Codex (OpenAI) | NetworkPolicy/PSS pattern; tek-reviewer yeterli |
| E-4-6 | Claude (Anthropic) | Codex (OpenAI) | runbook only; tek-reviewer yeterli |

**CC-2 invariant** (HARD RULE Cross-AI Peer Review): aynı sağlayıcı code yazıp review etmez. Anthropic Claude impl + Anthropic Claude review **YASAK** (aynı sağlayıcı = aynı blind spot). Cross-provider AGREE zorunlu.

**Verdict semantiği per slice:**
- AGREE / `ready_for_impl: true` (plan-time) → impl başlat (Plan Consensus Autonomy, kullanıcıya plan onayı sorulmaz)
- AGREE / `ready_to_merge: true` (post-impl) → normal squash merge (admin bypass YASAK)
- REVISE / PARTIAL → fix iter, reviewer'a tekrar, AGREE'ye kadar
- RED → kullanıcıya rapor + yön sor

---

## 5. Guard-Flag Invariants (Epic 4 değişmezleri)

**3 guard flag const false korunur — her slice'da:**

| Flag | Mevcut state | Epic 4 sonu | Sebep |
|---|---|---|---|
| `support_widening` | false | **false** | Helm chart "operator-installable beta template"; OS/Python/provider widening Epic 3'te |
| `production_platform_claim` | false | **false** | Chart README dil: "production claim deferred to v5 final promotion" |
| `live_adapter_execution` | false | **false** | Hiçbir slice canlı LLM provider call yapmaz; chart render-only test'lenir |

**Slice-by-slice no-flip kanıtları:**

- **E-4-1:** chart `Chart.appVersion` runtime version'a bağlı; flag flip yok. ConfigMap'lerde flag string YASAK (E-4-6 invariant test ile yakalanır)
- **E-4-2:** advisory matrix; runtime_enforced const false; operator_enforced const true; tenant boundary advisory (runtime karar vermez)
- **E-4-3:** DDL operator-owned; ao-kernel DDL koşturmaz → live_adapter_execution flag tetiklenmez
- **E-4-4:** ServiceMonitor + OTEL opt-in (default disabled); telemetry lazy/no-op (CLAUDE.md D12); flag flip yok
- **E-4-5:** NetworkPolicy/PSS Kubernetes-side; ao-kernel runtime'ında değişiklik yok; flag flip yok
- **E-4-6:** test runbook + lokal helm-unittest; hiçbir guard flag asserted true olmaz; her invariant test "ConfigMap içinde flag string=false" doğrular

**No-workflow-mutation invariant (her slice'da):**
- `git diff --name-only` `.github/workflows/` altında değişiklik göstermez (forbidden-change audit; CLAUDE.md HARD RULE uzun-vadeli kalıcı çözüm)
- helm-unittest CI workflow gelecek epic'in scope'u (PR-Xfinal sonrası ayrı governance migration)

---

## 6. Test Invariants per Slice (kategori + minimum count)

Her slice için **minimum 6 invariant test** (AST-backed where applicable, schema-strict, evidence-pinned):

| Slice | Min count | Kategori |
|---|---|---|
| E-4-1 | 7 | shape (chart fields), no_guard_flip (ConfigMap string scan), no_workflow_mutation (git diff guard), helm_template_deterministic (3x render sha256), values_replicas_min_1 (schema), no_secret_in_values (regex scan), evidence_validates (schema-backed) |
| E-4-2 | 8 | shape (7 dimension required), no_guard_flip, no_workflow_mutation, matrix_strict (additionalProperties:false), runtime_enforced_false (const), operator_enforced_true (const), cross_ai_3way_evidence_ref, evidence_validates |
| E-4-3 | 6 | shape (operator-checklist 15+ items), no_guard_flip, no_workflow_mutation, no_ddl_in_runtime (grep ao_kernel/ for DDL keywords = 0), no_secret_in_doc (regex), evidence_validates |
| E-4-4 | 8 | shape (Teams primary + Slack dormant), no_guard_flip, no_workflow_mutation, servicemonitor_opt_in_default (`enabled=false`), alert_default_teams (Teams string present, Slack live config absent), helm_template_deterministic, otel_lazy_referenced (CLAUDE.md D12 link present), evidence_validates |
| E-4-5 | 7 | shape (NetworkPolicy + PSS templates), no_guard_flip, no_workflow_mutation, ingress_default_deny (helm template grep), security_context_render (runAsNonRoot/readOnlyRootFs in all containers), pss_label_restricted_default, evidence_validates |
| E-4-6 | 7 | shape (test files exist), no_guard_flip, no_workflow_mutation (CRITICAL: workflow EKLENMEZ), no_workflow_added (`.github/workflows/helm-unittest.yml` absent), helm_unittest_pass (lokal 100%), values_invariants_no_flag_flip_in_configmap, evidence_validates |

**Toplam:** 43+ invariant test (epic geneli).

**Test placement:**
- `tests/test_epic_4_*_evidence_invariants.py` (Python-side schema + AST guard + git diff audit)
- `deploy/helm/ao-kernel/tests/*.yaml` (helm-unittest)
- `conftest.py` global hooks (BLK-001/002/003 forbidden patterns korunur)

---

## 7. Dependencies + Ordering

```
V5 P0 mirror (PR-X2-evidence merged)
       |
       v
E-4-1 (Helm chart skeleton) ─── tek başına başlayabilir; baseline
       |
       +───────── E-4-2 (Multi-tenant pattern) ─── chart skeleton kullanır
       |                |
       |                +─── 3-way cross-AI (Codex + Mavis) — kritik boundary
       |
       +───────── E-4-3 (DB + secret operator-owned) ─── values.yaml env block kullanır
       |
       +───────── E-4-4 (Observability surface) ─── chart templates'a opt-in eklenir
       |
       +───────── E-4-5 (NetworkPolicy + PSS) ─── chart templates'a eklenir (E-4-2 boundary kullanır)
       |
       v
E-4-6 (helm-unittest runbook) ─── E-4-1..E-4-5 tüm template'leri test eder
       |
       v
Epic 4 closure entry → V5 roadmap §3 Epic 4 closure marker
       |
       v
(Epic 5/6/7 paralel devam; Epic 9 PR-Xfinal bağımlılık zinciri)
```

**Önerilen merge order:**

1. **E-4-1** (chart skeleton; bağımsız; en düşük risk)
2. **E-4-3** (DB/secret operator-owned doc; E-4-1 values structure kullanır; orta risk)
3. **E-4-5** (NetworkPolicy + PSS; chart template'lere eklenir; orta risk)
4. **E-4-4** (Observability surface; chart template'lere opt-in; orta risk — Teams default pattern doğrulanır)
5. **E-4-2** (multi-tenant pattern + matrix; 3-way cross-AI; high risk; en sonda mühürleme)
6. **E-4-6** (helm-unittest runbook; tüm template'leri test eder)

**Paralel yapılabilir:** E-4-3 + E-4-4 + E-4-5 ayrı worktree'lerde paralel; her biri E-4-1 merge sonrası başlar.

---

## 8. Microsoft Teams / Slack Discipline (HARD RULE özelinde Epic 4)

CLAUDE.md HARD RULE **Workspace Tooling: Teams Primary, Slack YOK (bizim için), Slack Asset-Preserved başka tenants için** Epic 4'ün observability slice'ında **doğrudan** uygulanır.

**E-4-4 alert delivery default'u (zorunlu pattern):**

- **Primary alert sink (bizim için):** Microsoft Teams Power Automate workflow + Adaptive Card (raw Alertmanager v4 JSON POST → flow içinde transform)
- **Vault env key (operator-side):** `TEAMS_WEBHOOK_URL` (active)
- **Slack snippet:** **asset-preserved dormant** chart template'ında `# slack: dormant; reactivation via tenant demand-driven explicit trigger only` comment block; LIVE config render YAPILMAZ
- **Multi-tenant gelecek için Slack reactivation chain runbook referansı:** `docs/RB-slack-reactivation-chain.md` (E-4-4 scope dışında ama referans ile bağlanır; ileride başka tenant talep ederse)
- **YASAK pattern'ler (E-4-4 review'da reddedilir):**
  - `slack_configs:` LIVE rendered config (bizim için)
  - Tek `ExternalSecret` altında 2 key (SLACK + TEAMS) — Ready=False chain Teams'i de bozar
  - "Slack pattern sil + temizle" — multi-tenant asset-preserved disiplin (ADR-0027/0029 mirror pattern)
  - Yeni alert sink önerisinde Slack-default başlamak

**E-4-4 review test invariant (`alert_default_teams`):**
- Rendered Alertmanager config'te `slack_configs:` block YOK
- `webhook_configs:` block VAR (Teams Power Automate URL secretKeyRef)
- Doc'ta "Slack reactivation chain only via tenant demand-driven explicit trigger" cümlesi mevcut

---

## 9. References

- **Parent roadmap:** `.claude/plans/V5-FULL-PRODUCTION-PROMOTION-ROADMAP.md` §3 Epic 4
- **Master plan:** `.claude/plans/AO-MA-SPM-MASTER-PLAN.md` (Faz 7+ promotion section)
- **V5 issue projection:** `.claude/plans/v5_issue_projection.v1.json` (Epic 4 sub-issues lazy-expand source)
- **Mevcut deploy artifacts (referans, etkilenmez):** `deploy/ao-release-gate-service/`, `deploy/internal-gate-host/`, `deploy/live-adapter-gate-policy-service/` (Epic 4 bunlara dokunmaz; yeni `deploy/helm/ao-kernel/` ayrı path)
- **AO-MA-11A-2 pattern referansı:** `.claude/plans/AO-MA-11A-2-PLAN-APPROVAL-GATE.md` (operator-bound gate disiplini; Epic 4 promotion authority değil ama review pattern aynı)
- **Schema strict pattern:** `ao_kernel/defaults/schemas/ao-ma-11a-plan-approval.schema.v1.json` (guard flag const false 3'lü pin örnek)
- **CLAUDE.md değişmezler:** §2 fail-closed + secrets + atomic writes; §11 telemetry lazy/no-op; §17 branch discipline; §19 stacked PR merge protocol; §21 hardening principles (1-5)
- **Global HARD RULE'lar (kullanıcı CLAUDE.md):**
  - Workspace tooling Teams primary, Slack asset-preserved (2026-05-27)
  - Uzun vadeli kalıcı çözüm tercih edilir (2026-05-27)
  - Admin merge YASAK (2026-05-05)
  - Cross-AI peer review (2026-05-05 + 2026-05-14)
  - CI kırmızıyken merge YASAK (2026-05-17)
  - TEST cluster scale-to-zero YASAK (2026-05-10) — Helm chart default replicaCount: 1 invariant'ın user-level kaynağı

---

## 10. Closure Criteria (Epic 4 bütünü)

Epic 4 closed sayılması için:

- [ ] E-4-1..E-4-6 6 slice MERGED (her biri cross-AI AGREE + ao-release-gate green + admin bypass YOK)
- [ ] Her slice için `.claude/plans/E-4-N-*.v1.json` schema-backed evidence VAR ve schema validate ediyor
- [ ] `tenant_isolation_matrix.v1.json` 7 dimension complete + 3-way cross-AI evidence ref (E-4-2)
- [ ] `helm template deploy/helm/ao-kernel/` deterministic (3x render sha256-identical)
- [ ] `helm unittest deploy/helm/ao-kernel/` 100% pass (E-4-6 runbook)
- [ ] **Guard flag invariant:** `support_widening=false` + `production_platform_claim=false` + `live_adapter_execution=false` post-merge doğrulanır (`scripts/check_guard_flags.py` veya equivalent)
- [ ] **Workflow invariant:** `.github/workflows/` altında Epic 4 PR'larıyla değişiklik YOK (forbidden-change audit pass)
- [ ] V5 roadmap doc §3 Epic 4 closure entry: "Closed: PR #N1..N6 + evidence ref"
- [ ] V5 mirror Issue #Epic-4 closed; Project board "Done" column'a taşınmış (visibility mirror, not authority)

---

## 11. Out-of-Scope (Epic 4 PR'larında YASAK)

- 3 guard flag'in herhangi birinin flip'i (Epic 9 PR-Xfinal yetkisi)
- `.github/workflows/**` mutation (helm-unittest CI workflow gelecek epic)
- `ao_kernel/` source modülleri içinde yeni code path (Epic 4 doc + template + schema epic'i)
- Live `helm install` execution (chart render-only test; live install operator-side runbook)
- `cost_tracking.available` flip (V5 roadmap E-4-5 olarak listelenmiş; bu plan'da Epic 2/9'a taşındı)
- "Production-ready" public claim (chart README dil "operator-installable beta template; production claim deferred")
- PyPI v5.x publish (Epic 9 PR-Xfinal sonrası)
- Slack LIVE config default (asset-preserved dormant snippet only, bizim için)

---

## 12. Yaşayan dosyalar

- `.claude/plans/EPIC-4-KUBERNETES-HELM-MULTI-TENANT.md` (BU dosya; her slice closure'da entry güncellenir)
- `.claude/plans/E-4-1..E-4-6-*.md` + `.v1.json` (her slice impl'inde eklenir)
- `.claude/plans/tenant_isolation_matrix.v1.json` (E-4-2 advisory artifact; her tenant boundary değişikliğinde güncellenir)
- `ao_kernel/defaults/schemas/e-4-*-evidence.schema.v1.json` (her slice strict schema)
- `.claude/plans/V5-FULL-PRODUCTION-PROMOTION-ROADMAP.md` §3 Epic 4 row (her slice merge sonrası closure entry)
