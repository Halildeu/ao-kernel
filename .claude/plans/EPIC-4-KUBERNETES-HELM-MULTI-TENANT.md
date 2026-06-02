# Epic 4 — Deployment, Operations, Tenancy (Kubernetes Helm + Multi-Tenant Pattern)

> **Statü:** PROPOSED · V5 roadmap'in 4. epic'i. PR-X0 (`V5-FULL-PRODUCTION-PROMOTION-ROADMAP.md`) ile mühürlenmiş E-4-1..E-4-6 sub-slice tabanı bu plana göre genişletilir.
> **Parent:** `.claude/plans/V5-FULL-PRODUCTION-PROMOTION-ROADMAP.md` §3 Epic 4
> **Owner:** Halil Kocoglu · **Cross-AI consensus:** TBD per-slice (Codex MCP plan-time iter; Mavis/MiniMax kritik slice'larda 3-way)
> **Bağımlılık:** Epic 1 (sistem mod aktivasyon) + Epic 2 paralel (live adapter envelope opsiyonel; bu epic'in template'leri için **gerekli değil** — operator-side runbook olarak yayınlanır)
> **Risk:** high (cross-tenant isolation pattern + multi-namespace pattern docs) · **Forecast:** 4-6 hafta lazy infaza yayılır

> **Iter-2 NOT (2026-06-02):** Bu doc Codex MCP thread `019e879d` iter-1 REVISE verdict'inde tespit edilen 8 finding (F1-F8) absorb edilerek revize edilmiştir. Per-finding fix mapping §13'te. Iter-2 review thread pending; AGREE alınana kadar impl YASAK.

> **Authority hatırlatması (V5 invariant #1):** Bu epic **hiçbir guard flag flip ETMEZ**. Helm chart + multi-tenant pattern + operator runbook'lar **operator-side artifact** olarak yayınlanır. `live_adapter_execution` / `support_widening` / `production_platform_claim` üçü de **const false** kalır. Final guard flag flip yetkisi **PR-Xfinal** operator-bound supersession decision'da. Epic 4'ün hiçbir slice'ı tek başına bu yetkiyi taşımaz.

---

## 1. Scope

### Ne ekler

- `deploy/helm/ao-kernel/` altında **operator-installable Helm chart skeleton** — Chart.yaml + values.yaml + 4-5 baseline template (Deployment, Service, ConfigMap, ServiceAccount + RBAC, NetworkPolicy)
- **Multi-tenant isolation pattern doc** (`docs/MULTI-TENANT-DEPLOYMENT.md`) — namespace-per-tenant + RBAC + secret isolation + quota + audit boundary tanımları; `tenant_isolation_matrix.v1.json` advisory artifact (2-fazlı: E-4-2a early advisory contract + E-4-2b late final seal)
- **Operator-owned PostgreSQL provisioning pattern doc** — operator DDL responsibility; ao-kernel hiçbir DDL execute etmez; env-only secret resolution
- **Observability surface template'leri** — opt-in Prometheus ServiceMonitor template + OpenTelemetry sidecar pattern doc (Microsoft Teams Power Automate primary alert sink per HARD RULE)
- **NetworkPolicy + PodSecurityStandards (PSS) namespace-label baseline** template'leri (PSP YASAK; deprecated API)
- **helm-unittest CI invocation doc** (yeni workflow EKLENMEZ; runbook + lokal helm-unittest invocation)

### F8 absorb: `pyproject.toml [k8s-helm]` extra kararı

`pyproject.toml` `[k8s-helm]` extra **Epic 4 scope'undan ÇIKARILDI**. Gerekçe: Helm chart Python wheel ile dağıtılmaz; operator-installable artifact'tır (`deploy/helm/ao-kernel/`). Wheel'a chart paketleme + dependency ekleme pattern'i Epic 9 PR-Xfinal sonrası ayrı kararla (gerekirse) açılır. E-4-1 invariant test'i `pyproject.toml` diff guard ile bu boundary'yi machine-enforced korur:

- **Invariant `no_pyproject_k8s_helm_extra_added`** (E-4-1): `git diff origin/main..HEAD -- pyproject.toml` `[k8s-helm]` veya `k8s_helm` veya `k8s-helm` substring eklemiyor; wheel build (`python -m build --wheel`) `deploy/helm/` altındaki içeriği `dist/*.whl` içine paketlemiyor (`unzip -l dist/*.whl | grep -c "deploy/helm" == 0` test).

### Out-of-scope (ZERO TOUCH — machine-enforced fail-closed per slice)

- `.github/workflows/**` — Epic 4 hiçbir workflow file eklemez, mevcut workflow'lara dokunmaz. **F3 absorb:** Her slice CI test'i `git diff --name-only origin/main..HEAD` allowlist'i ile bu boundary'yi makine olarak doğrular (ayrıntı §6 invariant `workflow_zero_touch_machine_enforced`).
- `ao_kernel/` source modülleri — runtime'a yeni Python code path eklenmez
- Mevcut Epic 1-3, 5-7, 8 slice'larında çakışan kod path'leri — Epic 4 sadece `deploy/helm/`, `docs/`, opsiyonel `.claude/plans/E-4-*.v1.json` evidence
- Live Helm install/upgrade execution — chart **rendering** test'lenir (helm template + helm-unittest), `helm install` / `helm upgrade` / `kubectl apply` LIVE smoke YASAK (Epic 9 PR-Xfinal sonrası operator-side). **F7 absorb:** Tüm runbook doc'larda live command yokluğu grep ile test'lenir (`tests/test_epic_4_no_live_cluster_commands_in_runbooks.py`).
- Guard flag flip — hiçbir slice 3 guard flag'i değiştirmez; `support_widening_allowed=false` korunur
- `cost_tracking.available const false → flip` (V5 roadmap E-4-5 olarak listelenmiş; bu plan'da **AYRI EPIC slice'ı** olarak Epic 2 live adapter zincirine taşınır — Epic 4 scope dışı)
- "Production-ready" public claim — chart README'sinde dil "operator-installable beta template; production claim deferred to v5 final promotion" kalır
- `pyproject.toml` `[k8s-helm]` extra ekleme (F8 absorb)

---

## 2. Slice Breakdown (7 slice; E-4-2 split sonrası; her biri ≤ 1 PR worth, additive only)

> **F1 absorb:** Önceki E-4-2 (multi-tenant pattern + matrix) iki slice'a bölündü: **E-4-2a** (early advisory boundary contract/schema — düşük risk, erken merge) + **E-4-2b** (late final matrix seal — yüksek risk, 3-way cross-AI, en son merge). Yeni merge order: **E-4-1 → E-4-2a → E-4-3 → E-4-5 → E-4-4 → E-4-2b → E-4-6** (detay §7).

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
tests/test_epic_4_1_helm_chart_evidence_invariants.py
tests/test_epic_4_1_write_set_invariant.py        # F3: write_set ↔ git diff exact match
tests/test_epic_4_1_no_pyproject_k8s_helm_extra.py # F8: pyproject diff guard
```

**Acceptance:**
- `helm lint deploy/helm/ao-kernel/` clean (lokal; CI'da `make helm-lint` runbook'lu, workflow EKLENMEZ)
- `helm template` deterministic (3 ardışık render byte-identical, sha256 diff yok)
- `values.yaml::replicaCount` default = 1 (test invariant: schema `minimum: 1`)
- `values.schema.json` `additionalProperties:false` her object'te (strict)
- Hiçbir template `secret` value içermez (sadece secretKeyRef env'leri)
- **F2 absorb:** Rendered ConfigMap/Deployment/Service/RBAC/SA + values.yaml + tüm template'lerde `support_widening` / `production_platform_claim` / `live_adapter_execution` **key'leri TAMAMEN YOK** (no `: false`, no `: true`, no comment with key name in rendered output). Test: `helm template` çıktısında bu 3 key string'i `grep -c == 0`.
- **F3 absorb:** `write_set` evidence field `git diff --name-only origin/main..HEAD` ile birebir aynı; `.github/workflows/**` path değişikliği = test fail.
- **F8 absorb:** `pyproject.toml` `[k8s-helm]` extra eklenmedi; wheel build çıktısında `deploy/helm/` YOK.

---

### E-4-2a — Multi-Tenant Boundary Contract + Schema (Early Advisory)

**Risk:** low (early advisory contract; schema + boundary kontratı sadece; runtime'a etki yok)
**Cross-AI:** Implementer Claude · Reviewer Codex (plan-time iter + post-impl review)
**Bağımlılık:** E-4-1 (chart skeleton template referansı için)

**Amaç:** E-4-5 (NetworkPolicy + PSS) ve E-4-4 (Observability) `tenant_isolation_matrix` advisory boundary kontratına bağımlı. Bu boundary'yi **erken** kontrat olarak kilitlemek, downstream slice'ları (E-4-5, E-4-4) açar. Final matrix seal (3-way cross-AI) E-4-2b'de.

**Write-set:**

```
docs/MULTI-TENANT-DEPLOYMENT.md              # boundary contract pattern (advisory dil; 7 dimension placeholder)
.claude/plans/E-4-2a-MULTI-TENANT-CONTRACT.md
.claude/plans/E-4-2a-MULTI-TENANT-CONTRACT.v1.json
ao_kernel/defaults/schemas/e-4-2a-tenant-isolation-contract.schema.v1.json
ao_kernel/defaults/schemas/e-4-2a-multi-tenant-contract-evidence.schema.v1.json
tests/test_epic_4_2a_contract_invariants.py
tests/test_epic_4_2a_write_set_invariant.py
```

**İçerik (early advisory contract):**

- 7 isolation dimension **placeholder** + her dimension için `operator_enforceable: true` + `operator_action_required: true` + `runtime_enforced: false` + `live_validated: false` const-pin (F4 absorb)
- Schema `additionalProperties:false`; 7 dimension required slot (status detayları E-4-2b'de doldurulur)
- **F4 absorb:** Doc dili kesinlikle "advisory boundary pattern" / "isolation pattern" — **YASAK kelimeler:** "isolation achieved", "isolation enforced", "operator_enforced:true" (overclaim). Doğru: "operator_enforceable", "operator_action_required", "runtime_enforced:false", "live_validated:false".

**Acceptance:**
- Schema strict (additionalProperties:false, 7 dimension required, 4 const field per dimension)
- Doc'ta `live_validated: false` ve `runtime_enforced: false` ifadeleri en az 3 yerde tekrar (overclaim engellemesi)
- E-4-5 ve E-4-4'ün bağımlı olduğu boundary referans alanları (`namespace_isolation`, `network_isolation`, `audit_isolation`) schema'da pin'li
- **F2 absorb:** Kontrat doc'unda 3 guard flag key string'i YOK; rendered helm output etkilenmediği için chart template'leri değişmedi
- **F3 absorb:** `write_set` ↔ git diff exact match; `.github/workflows/**` YOK

---

### E-4-2b — Multi-Tenant Matrix Final Seal (Late, 3-Way Cross-AI)

**Risk:** high (cross-tenant boundary final seal; pattern yanlış dökümanlanırsa operator yanlış kurar)
**Cross-AI:** Implementer Claude · Reviewer Codex (OpenAI) + **Mavis (MiniMax)** — 3-way zorunlu (cross-tenant boundary kritik)
**Bağımlılık:** E-4-2a (contract base) + E-4-5 (NetworkPolicy rendered) + E-4-4 (Observability rendered) + E-4-3 (DB/secret pattern doc)

**Amaç:** E-4-2a contract'ında pin'lenmiş 7 dimension için **gerçek matrix değerleri** + downstream slice'larla cross-reference + 3-way cross-AI consensus final seal.

**Write-set:**

```
.claude/plans/tenant_isolation_matrix.v1.json   # final matrix; per-dimension status + evidence ref (E-4-5/E-4-4/E-4-3 cross-ref)
docs/MULTI-TENANT-DEPLOYMENT.md                 # 7 dimension complete content + enforcement runbook + 3-way evidence note
.claude/plans/E-4-2b-MULTI-TENANT-FINAL-SEAL.md
.claude/plans/E-4-2b-MULTI-TENANT-FINAL-SEAL.v1.json
ao_kernel/defaults/schemas/e-4-2b-tenant-isolation-matrix.schema.v1.json
ao_kernel/defaults/schemas/e-4-2b-multi-tenant-final-seal-evidence.schema.v1.json
tests/test_epic_4_2b_matrix_invariants.py
tests/test_epic_4_2b_write_set_invariant.py
```

**`tenant_isolation_matrix.v1.json` 7 dimension (advisory only — runtime enforcement YOK; F4 absorb dil):**

1. **Namespace isolation** — bir Helm release = bir namespace; ClusterRole YASAK (`operator_enforceable:true`, `operator_action_required:true`, `runtime_enforced:false`, `live_validated:false`)
2. **RBAC scope** — Role + RoleBinding namespace-scoped; cross-namespace verb yok (aynı 4 const)
3. **Secret isolation** — Kubernetes Secret per-namespace; cross-namespace mount engellenmiş (operator runbook) (aynı 4 const)
4. **NetworkPolicy** — default-deny ingress + egress; sadece allowlist'li peer'lar (E-4-5'e bağlı, evidence ref) (aynı 4 const)
5. **Resource quota** — ResourceQuota + LimitRange per-namespace (operator template) (aynı 4 const)
6. **Audit boundary** — JSONL evidence per-namespace `workspace_root`; cross-tenant fact promotion YASAK (advisory note) (aynı 4 const)
7. **Cost tracking advisory** — `cost_tracking.available` const false korunur; per-tenant cost tracking flip Epic 2/9 yetkisinde (aynı 4 const)

**Acceptance:**
- Pattern doc'ta her 7 dimension için minimum 1 enforcement mekanizması (Kubernetes-native) + 1 operator runbook adımı
- `tenant_isolation_matrix.v1.json` schema strict (additionalProperties:false, 7 dimension required, per-dimension 4 const field — operator_enforceable + operator_action_required + runtime_enforced + live_validated)
- **F4 absorb:** Schema'da 7 dimension her biri için 4 const field; `runtime_enforced:false` ve `live_validated:false` her dimension'da pin'li
- Cross-AI consensus **3-way** evidence ref (Codex verdict + Mavis verdict) — evidence schema her iki reviewer için required
- E-4-5 ve E-4-4'ün rendered manifest'lerinin matrix dimension'larında cross-reference VAR (örn. NetworkPolicy dimension'ı `e-4-5-security-baseline-evidence.v1.json` ref eder)
- **F7 absorb:** Doc + matrix'te secret leak regex scan; live helm/kubectl command yok

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
tests/test_epic_4_3_operator_owned_invariants.py
tests/test_epic_4_3_write_set_invariant.py
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
- **F7 absorb:** Secret leak regex scan (`AKIA[0-9A-Z]{16}`, `sk-[A-Za-z0-9]{40,}`, `xoxp-`, `xoxb-`, `xoxa-`, `ghp_`, `gho_`) doc'larda 0 occurrence
- **F7 absorb:** Live cluster command (`helm install`, `helm upgrade`, `kubectl apply`) absence in all runbooks (grep test)

---

### E-4-4 — Observability Surface (ServiceMonitor Template + OTEL Sidecar Pattern Doc)

**Risk:** medium (alert delivery yanlış default'lanırsa Slack pattern sızar — HARD RULE Teams primary; F5 absorb consistency)
**Cross-AI:** Implementer Claude · Reviewer Codex
**Bağımlılık:** E-4-1 (chart skeleton'a opt-in template eklenir) + E-4-2a (boundary contract referans)

**Write-set (F5 absorb — Alertmanager LIVE config rendered EDİLMEZ):**

```
deploy/helm/ao-kernel/templates/servicemonitor.yaml   # ConditionalIf .Values.observability.serviceMonitor.enabled
deploy/helm/ao-kernel/values.yaml                     # observability.* default DISABLED (opt-in)
docs/OBSERVABILITY-DEPLOYMENT.md                      # OTEL sidecar pattern + alert delivery (Teams primary)
docs/RB-alertmanager-teams-primary.md                 # Alertmanager config ÖRNEK (operator-side; chart template DEĞİL)
docs/RB-slack-reactivation-chain.md                   # Slack dormant reactivation chain (asset-preserved; başka tenant)
.claude/plans/E-4-4-OBSERVABILITY-SURFACE.md
.claude/plans/E-4-4-OBSERVABILITY-SURFACE.v1.json
ao_kernel/defaults/schemas/e-4-4-observability-evidence.schema.v1.json
tests/test_epic_4_4_observability_invariants.py
tests/test_epic_4_4_write_set_invariant.py
```

**F5 absorb — kritik karar:** Alertmanager config **chart template'i değildir**; operator-side runbook'tur (`docs/RB-alertmanager-teams-primary.md`). Chart yalnız ServiceMonitor + OTEL sidecar pattern doc içerir. Bu sayede:
- Chart rendered output'ta `slack_configs:`, `SLACK_WEBHOOK_URL`, "slack" string'i, Slack ExternalSecret key **YOK** (test: rendered output grep 0 occurrence)
- Alertmanager Teams webhook config örnek olarak runbook'ta (operator copy-paste); chart template'de değil
- Slack dormant pattern sadece runbook (`docs/RB-slack-reactivation-chain.md`); chart template'lerden tamamen çıkartıldı

**İçerik:**

- **ServiceMonitor template** Prometheus-Operator CRD; `.Values.observability.serviceMonitor.enabled = false` default; opt-in (conditional include)
- **OpenTelemetry sidecar pattern** sadece doc (chart'ta sidecar default EKLENMEZ); operator manuel ekler; lazy + no-op fallback (CLAUDE.md D12) korunur
- **Alert delivery default** (HARD RULE Teams primary):

| Slot | Doğru pattern | Yasak pattern |
|---|---|---|
| Primary alert sink | **Microsoft Teams Power Automate workflow + Adaptive Card** (Alertmanager v4 webhook JSON raw POST; transform Power Automate flow içinde) — runbook örnek | Slack webhook default kurma; Slack chart template render |
| Vault env key (operator) | `TEAMS_WEBHOOK_URL` (active); `SLACK_WEBHOOK_URL` (dormant, asset-preserved başka tenant için, sadece runbook) | İki webhook key tek ExternalSecret altında (Ready=False zinciri) |
| Helm route matcher | Single-tenant `team=<x>` veya multi-tenant `tenant_channel=teams` | `slack_configs` LIVE rendered config (bizim için) |
| Reactivation chain (başka tenant Slack ister) | `docs/RB-slack-reactivation-chain.md` referansı + operator demand-driven explicit trigger | "Slack pattern silmek" — asset-preserved (multi-tenant gelecek için) |

- Slack snippet sadece **doc'ta dormant** (silinmez), chart template'lerinden tamamen ÇIKARILDI; rendered helm output'ta Slack izi yok.

**Acceptance:**
- Default `values.yaml::observability.serviceMonitor.enabled = false` (opt-in)
- Alert delivery section'ında Teams pattern primary; Slack asset-preserved dormant açıkça etiketlenmiş (sadece runbook)
- ServiceMonitor template conditional render (helm template `--set observability.serviceMonitor.enabled=false` → boş çıktı; `=true` → tek deterministic manifest)
- OTEL sidecar pattern doc + CLAUDE.md §11 telemetry lazy-import referansı
- **F5 absorb:** Rendered helm template çıktısında `slack_configs:`, `SLACK_WEBHOOK_URL`, `slack` string (case-insensitive) **0 occurrence**; `webhook_configs:` block opt-in (operator runbook copy-paste); Slack ExternalSecret rendered key YOK
- **F7 absorb:** Secret leak scan; live helm/kubectl command absence in all 3 docs (OBSERVABILITY-DEPLOYMENT, RB-alertmanager-teams-primary, RB-slack-reactivation-chain)

---

### E-4-5 — NetworkPolicy + PodSecurityStandards (PSS) Namespace-Label Baseline

**Risk:** medium (yanlış NetworkPolicy = cluster izolasyonu kırılır veya sağlam çalışmaz; F6 absorb PSS pattern)
**Cross-AI:** Implementer Claude · Reviewer Codex
**Bağımlılık:** E-4-1 (chart template'lerine eklenir) + E-4-2a (multi-tenant boundary contract kullanılır)

**Write-set (F6 absorb — PSP YASAK, PSS namespace-label pattern):**

```
deploy/helm/ao-kernel/templates/networkpolicy.yaml         # default-deny + egress allowlist (operator-configurable)
deploy/helm/ao-kernel/templates/namespace.yaml             # PSS namespace label (pod-security.kubernetes.io/enforce: restricted) — operator-overlay
deploy/helm/ao-kernel/values.yaml                          # security.networkPolicy.enabled default true; security.podSecurityStandard "restricted" default; security.egress.allowlist alanları
docs/CLUSTER-SECURITY-BASELINE.md                          # PSS namespace-label pattern + NetworkPolicy + egress allowlist + operator checklist + DNS-only default render-only/beta note
.claude/plans/E-4-5-SECURITY-BASELINE.md
.claude/plans/E-4-5-SECURITY-BASELINE.v1.json
ao_kernel/defaults/schemas/e-4-5-security-baseline-evidence.schema.v1.json
tests/test_epic_4_5_security_baseline_invariants.py
tests/test_epic_4_5_write_set_invariant.py
```

**F6 absorb — kritik kararlar:**

1. **PSP YASAK** — `podsecuritypolicy.yaml` manifest'i **YOK** (Kubernetes 1.25+ deprecated). PSS namespace-label pattern: `templates/namespace.yaml` opsiyonel (operator namespace yaratıyorsa) + `pod-security.kubernetes.io/enforce: restricted` label.
2. **Egress allowlist values:** `security.egress.allowlist` alanları:
   - `database` (operator-configurable host/port; fail-closed default boş list)
   - `llm_providers` (operator-configurable hostname list; fail-closed default boş)
   - `teams_webhook` (operator-configurable Teams webhook hostname; fail-closed default boş)
   - `dns` (kube-dns CIDR; default `kube-system` namespaceSelector)
3. **DNS-only default** = chart bundled default (NetworkPolicy egress sadece DNS); operator allowlist'i kendi namespace overlay'inde genişletir. Bu render-only/beta default; **production-ready değil** — doc'ta açıkça etiketlenmiş.

**İçerik:**

- **NetworkPolicy default-deny pattern:** default ingress + egress deny; sadece namespace-içi same-app peer + DNS egress (kube-dns); operator allowlist (DB, LLM, Teams webhook) values'ta eklenir
- **Pod Security Standards (PSS) namespace-label:** `pod-security.kubernetes.io/enforce: restricted` label namespace üzerinde; chart templates'a `podsecuritypolicy.yaml` EKLENMEZ (deprecated API)
- **runAsNonRoot: true**, **readOnlyRootFilesystem: true**, **allowPrivilegeEscalation: false**, **capabilities.drop: [ALL]** — securityContext block tüm container'larda
- **Egress allowlist pattern doc:** operator istediği LLM provider hostname'lerini values'ta `security.egress.allowlist.llm_providers` list'ine ekler; chart default minimum: kube-dns + cluster-internal

**Acceptance:**
- NetworkPolicy template default ingress deny + DNS egress allow only (helm template'de doğrulanır)
- `security.egress.allowlist.{database,llm_providers,teams_webhook}` values alanları VAR; default boş list (fail-closed); operator-configurable
- PSS namespace label `restricted` default; podsecuritypolicy.yaml manifest YOK (rendered output grep `kind: PodSecurityPolicy` 0 occurrence)
- Doc'ta operator-checklist (PSP→PSS migration not, NetworkPolicy CNI desteği kontrolü, egress allowlist genişletme adımları)
- `securityContext` block tüm container'larda render edilir (helm template invariant)
- **F6 absorb:** Rendered output'ta `apiVersion: policy/v1beta1` veya `apiVersion: extensions/v1beta1` YOK (deprecated API absence); `kind: PodSecurityPolicy` YOK
- **F7 absorb:** PSS label format test (`pod-security.kubernetes.io/enforce: restricted`); K8s API deprecation test (no deprecated apiVersion)
- **DNS-only default beta etiketi:** doc'ta "DNS-only egress = render-only/beta default; operator MUST configure security.egress.allowlist before production deployment" cümlesi en az 2 yerde

---

### E-4-6 — helm-unittest CI Invocation Doc + Lokal Test Runbook + Epic-Wide Idempotency

**Risk:** low (sadece runbook + lokal test invocation; hiçbir CI workflow file EKLENMEZ)
**Cross-AI:** Implementer Claude · Reviewer Codex
**Bağımlılık:** E-4-1 + E-4-2a + E-4-4 + E-4-5 (test edilecek template'ler hazır; E-4-2b cross-ref evidence için son closure)

**Write-set:**

```
deploy/helm/ao-kernel/tests/                   # helm-unittest test suite directory
  deployment_test.yaml
  service_test.yaml
  configmap_test.yaml
  rbac_test.yaml
  networkpolicy_test.yaml
  servicemonitor_test.yaml
  namespace_test.yaml                          # PSS label test
  values_invariants_test.yaml                  # replicaCount >= 1; no flag KEY in any rendered output (F2)
  no_slack_rendered_test.yaml                  # F5: rendered output Slack absence
docs/HELM-UNITTEST-RUNBOOK.md                  # lokal invocation; opsiyonel CI integration (gelecek epic)
.claude/plans/E-4-6-HELM-UNITTEST-RUNBOOK.md
.claude/plans/E-4-6-HELM-UNITTEST-RUNBOOK.v1.json
ao_kernel/defaults/schemas/e-4-6-helm-unittest-evidence.schema.v1.json
tests/test_epic_4_6_helm_unittest_invariants.py
tests/test_epic_4_6_write_set_invariant.py
tests/test_epic_4_helm_template_idempotency_epic_wide.py  # F7: 3-render sha256 identical across ALL slices combined
```

**İçerik:**

- **Lokal invocation:** `helm plugin install https://github.com/helm-unittest/helm-unittest` + `helm unittest deploy/helm/ao-kernel/`
- **CI runbook (NOT a workflow):** dökümanlanır; gelecek epic'te (PR-Xfinal sonrası, ayrı governance migration ile) `.github/workflows/helm-unittest.yml` eklenebilir; **bu Epic 4'te EKLENMEZ**
- **Test invariants:** her template için minimum 3 assertion (rendered manifest shape + no-secret-in-values + no-guard-flag-flip)
- **`values_invariants_test.yaml` (F2 absorb):** ConfigMap + Deployment + Service + RBAC + SA + NetworkPolicy rendered output'larında `support_widening` / `production_platform_claim` / `live_adapter_execution` **KEY string'leri TAMAMEN YOK** (AST-grep style; not just `: true` check, full key absence)
- **`no_slack_rendered_test.yaml` (F5 absorb):** rendered output'ta `slack_configs:`, `SLACK_WEBHOOK_URL`, "slack" (case-insensitive) 0 occurrence
- **F7 absorb:** Epic-wide `helm template` idempotency (3 sequential renders sha256-identical across ALL slice templates combined) — `tests/test_epic_4_helm_template_idempotency_epic_wide.py`

**Acceptance:**
- Lokal `helm unittest deploy/helm/ao-kernel/` 100% pass
- Runbook'ta 5+ adım operator çalıştırma; opsiyonel CI integration not (workflow EKLENMEZ; gelecek epic'in scope'u)
- helm-unittest version pin (reproducible)
- **F7 absorb:** Epic-wide idempotency test (combined template render 3x sha256-identical)
- **F7 absorb:** `replicaCount: 0` absence anywhere (HARD RULE TEST cluster scale-to-zero YASAK) — grep test rendered output + values.yaml
- **F7 absorb:** K8s API deprecation test (no `extensions/v1beta1`, no `policy/v1beta1` PodSecurityPolicy, no deprecated APIs)

---

## 3. Risk Class per Slice (özet — E-4-2 split sonrası)

| Slice | Risk | Sebep |
|---|---|---|
| E-4-1 Helm chart skeleton | **low** | additive template/doc; runtime'a etki yok; replica default 1 (HARD RULE) |
| E-4-2a Multi-tenant boundary contract | **low** | early advisory contract; schema + boundary kontratı sadece; runtime'a etki yok |
| E-4-3 DB + secret operator-owned | **medium** | DDL ownership boundary kritik |
| E-4-5 NetworkPolicy + PSS namespace-label | **medium** | yanlış config cluster izolasyonu kırar; PSP YASAK |
| E-4-4 Observability surface | **medium** | Teams default primary; Slack pattern asset-preserved dormant (HARD RULE); Alertmanager runbook (chart template DEĞİL) |
| E-4-2b Multi-tenant matrix final seal | **high** | cross-tenant boundary final seal; 3-way cross-AI (Codex + Mavis); en sonda mühürleme |
| E-4-6 helm-unittest runbook | **low** | sadece doc + lokal test; CI workflow EKLENMEZ; epic-wide idempotency |

**Hiçbir slice "critical" değildir** çünkü hiçbiri guard flag flip'i tetiklemez. Critical risk Epic 9 final operator-bound PR'a kalır.

---

## 4. Cross-AI Consensus Protocol per Slice

| Slice | Implementer | Reviewer | İlave |
|---|---|---|---|
| E-4-1 | Claude (Anthropic) | Codex (OpenAI) | plan-time iter + post-impl review (iki ayrı kapı) |
| E-4-2a | Claude (Anthropic) | Codex (OpenAI) | early advisory contract; tek-reviewer yeterli |
| E-4-3 | Claude (Anthropic) | Codex (OpenAI) | DDL ownership doc; standart iki-gate |
| E-4-5 | Claude (Anthropic) | Codex (OpenAI) | NetworkPolicy/PSS pattern; tek-reviewer yeterli |
| E-4-4 | Claude (Anthropic) | Codex (OpenAI) | Teams/Slack pattern doğrulamak için; tek-reviewer yeterli |
| E-4-2b | Claude (Anthropic) | Codex (OpenAI) + **Mavis (MiniMax)** | **3-way zorunlu**; cross-tenant kritik boundary final seal |
| E-4-6 | Claude (Anthropic) | Codex (OpenAI) | runbook only; tek-reviewer yeterli |

**CC-2 invariant** (HARD RULE Cross-AI Peer Review): aynı sağlayıcı code yazıp review etmez. Anthropic Claude impl + Anthropic Claude review **YASAK** (aynı sağlayıcı = aynı blind spot). Cross-provider AGREE zorunlu.

**Verdict semantiği per slice:**
- AGREE / `ready_for_impl: true` (plan-time) → impl başlat (Plan Consensus Autonomy, kullanıcıya plan onayı sorulmaz)
- AGREE / `ready_to_merge: true` (post-impl) → normal squash merge (admin bypass YASAK)
- REVISE / PARTIAL → fix iter, reviewer'a tekrar, AGREE'ye kadar
- RED → kullanıcıya rapor + yön sor

---

## 5. Guard-Flag Invariants (Epic 4 değişmezleri; F2 + F4 absorb)

**3 guard flag const false korunur — her slice'da; F2 absorb: KEY ABSENCE enforcement, F4 absorb: advisory dil:**

| Flag | Mevcut state | Epic 4 sonu | Sebep |
|---|---|---|---|
| `support_widening` | false | **false** | Helm chart "operator-installable beta template"; OS/Python/provider widening Epic 3'te |
| `production_platform_claim` | false | **false** | Chart README dil: "production claim deferred to v5 final promotion" |
| `live_adapter_execution` | false | **false** | Hiçbir slice canlı LLM provider call yapmaz; chart render-only test'lenir |

**F2 absorb — Key absence enforcement (her slice'da invariant test):**

Önceki yaklaşım: ConfigMap'te `support_widening: true` string'i YOK doğrulanır. **YENİ yaklaşım (F2):** rendered manifest/values/template/configmap/env/args **HİÇBİR YERDE** `support_widening`, `production_platform_claim`, `live_adapter_execution` KEY'leri görünmez. Yani:

- `: false` value pinning DA YASAK (key kendisi YOK; sadece "key=value true" değil, "key whatsoever" yok)
- ConfigMap, Deployment, Service, RBAC, ServiceAccount, NetworkPolicy, ServiceMonitor, namespace, secrets — hepsinde key string'leri grep 0 occurrence
- Repo SSOT guard flag = false **re-verified per slice** (recompute-not-trust; `scripts/check_guard_flags.py` her slice merge öncesi çalıştırılır)

**F4 absorb — Advisory dil (E-4-2a + E-4-2b özelinde):**

| Yasak dil | Doğru dil |
|---|---|
| "isolation achieved" | "isolation pattern" |
| "isolation enforced" | "advisory boundary" |
| "operator_enforced: true" | "operator_enforceable: true" |
| (overclaim) | "operator_action_required: true" |
| (eksik) | "runtime_enforced: false" |
| (eksik) | "live_validated: false" |

E-4-2a contract'ı + E-4-2b matrix'i bu 4 const field'i her dimension için pin'ler; advisory dil ihlali test fail.

**Slice-by-slice no-flip kanıtları:**

- **E-4-1:** chart `Chart.appVersion` runtime version'a bağlı; flag flip yok. Rendered output'ta 3 key string YASAK (F2 invariant test ile yakalanır)
- **E-4-2a:** early advisory contract; runtime_enforced const false; operator_enforceable const true; tenant boundary advisory (runtime karar vermez)
- **E-4-2b:** final matrix seal; aynı 4 const field per dimension; 3-way cross-AI evidence ref
- **E-4-3:** DDL operator-owned; ao-kernel DDL koşturmaz → live_adapter_execution flag tetiklenmez
- **E-4-4:** ServiceMonitor + OTEL opt-in (default disabled); telemetry lazy/no-op (CLAUDE.md D12); flag flip yok; Alertmanager runbook (chart template değil) → rendered output'ta Slack key YOK (F5)
- **E-4-5:** NetworkPolicy/PSS Kubernetes-side; ao-kernel runtime'ında değişiklik yok; flag flip yok; PSP YASAK (F6); egress allowlist fail-closed default
- **E-4-6:** test runbook + lokal helm-unittest; hiçbir guard flag asserted true olmaz; her invariant test "rendered output'ta 3 flag KEY YOK" doğrular (F2)

**No-workflow-mutation invariant (F3 absorb — her slice'da machine-enforced fail-closed):**

- `git diff --name-only origin/main..HEAD` `.github/workflows/` altında değişiklik göstermez (forbidden-change audit; CLAUDE.md HARD RULE uzun-vadeli kalıcı çözüm)
- **F3 absorb:** evidence `write_set` field `git diff --name-only origin/main..HEAD` ile **birebir** match; herhangi bir `.github/workflows/**` path = test fail
- Test placement: her slice için ayrı test (`tests/test_epic_4_*_write_set_invariant.py`); CI'da `pytest` ile koşturulur
- helm-unittest CI workflow gelecek epic'in scope'u (PR-Xfinal sonrası ayrı governance migration)

---

## 6. Test Invariants per Slice (kategori + minimum count; F2 + F3 + F7 absorb)

Her slice için **minimum invariant test** sayısı F7 absorb sonrası arttırıldı (yeni kategoriler eklendi). AST-backed where applicable, schema-strict, evidence-pinned:

| Slice | Min count | Kategori |
|---|---|---|
| E-4-1 | **11** | shape (chart fields), no_guard_flag_key (F2 absorb: 3 key absence in rendered output), no_workflow_mutation, write_set_diff_match (F3), helm_template_deterministic (3x render sha256), values_replicas_min_1 (schema; F7: scale-to-zero absence), no_secret_in_values (regex), secret_leak_scan (F7: AKIA/sk-/xoxp- regex docs+manifests+evidence), no_live_cluster_commands_in_runbooks (F7), no_pyproject_k8s_helm_extra (F8), evidence_validates |
| E-4-2a | **9** | shape (7 dimension placeholder), no_guard_flag_key, no_workflow_mutation, write_set_diff_match, contract_strict (additionalProperties:false), runtime_enforced_false_const (F4), operator_enforceable_true_const (F4), live_validated_false_const (F4), evidence_validates |
| E-4-2b | **11** | shape (7 dimension complete), no_guard_flag_key, no_workflow_mutation, write_set_diff_match, matrix_strict, all_4_const_fields_per_dimension (F4: operator_enforceable + operator_action_required + runtime_enforced + live_validated), cross_ref_e_4_5_evidence, cross_ref_e_4_4_evidence, cross_ref_e_4_3_evidence, cross_ai_3way_evidence_ref (Codex + Mavis), evidence_validates |
| E-4-3 | **9** | shape (operator-checklist 15+ items), no_guard_flag_key, no_workflow_mutation, write_set_diff_match, no_ddl_in_runtime (grep ao_kernel/ for DDL keywords = 0), no_secret_in_doc (regex), secret_leak_scan (F7), no_live_cluster_commands_in_runbooks (F7), evidence_validates |
| E-4-4 | **12** | shape (Teams primary + Slack dormant), no_guard_flag_key, no_workflow_mutation, write_set_diff_match, servicemonitor_opt_in_default, alert_default_teams (Teams string present), slack_absence_in_rendered (F5: rendered output `slack_configs:` / `SLACK_WEBHOOK_URL` / "slack" 0 occurrence), no_alertmanager_in_chart_templates (F5: Alertmanager config sadece runbook), helm_template_deterministic, otel_lazy_referenced, secret_leak_scan (F7), evidence_validates |
| E-4-5 | **12** | shape (NetworkPolicy + namespace + values templates), no_guard_flag_key, no_workflow_mutation, write_set_diff_match, ingress_default_deny, security_context_render (runAsNonRoot/readOnlyRootFs/allowPrivilegeEscalation:false/capabilities.drop:[ALL]), pss_namespace_label_restricted (F6 + F7), no_psp_manifest (F6: `kind: PodSecurityPolicy` 0 occurrence), no_deprecated_k8s_api (F7: no `extensions/v1beta1` / `policy/v1beta1`), egress_allowlist_values_present (F6: database/llm_providers/teams_webhook/dns alanları), dns_only_default_beta_documented (F6), evidence_validates |
| E-4-6 | **12** | shape (test files exist), no_guard_flag_key, no_workflow_mutation, write_set_diff_match, no_workflow_added (`.github/workflows/helm-unittest.yml` absent), helm_unittest_pass, values_invariants_no_flag_key_in_any_rendered (F2), no_slack_rendered (F5), no_scale_to_zero_anywhere (F7), helm_template_idempotency_epic_wide (F7: 3-render sha256 identical across ALL slices), no_deprecated_k8s_api (F7), evidence_validates |

**Toplam:** 76+ invariant test (epic geneli; iter-1 43+'tan F7 absorb ile arttı).

**Test placement:**
- `tests/test_epic_4_*_evidence_invariants.py` (Python-side schema + AST guard + git diff audit)
- `tests/test_epic_4_*_write_set_invariant.py` (F3: per-slice write_set ↔ git diff exact match; `.github/workflows/**` allowlist deny)
- `tests/test_epic_4_helm_template_idempotency_epic_wide.py` (F7: epic-wide combined render sha256)
- `tests/test_epic_4_no_live_cluster_commands_in_runbooks.py` (F7: helm install/upgrade/kubectl apply absence in all runbooks)
- `deploy/helm/ao-kernel/tests/*.yaml` (helm-unittest)
- `conftest.py` global hooks (BLK-001/002/003 forbidden patterns korunur)

---

## 7. Dependencies + Ordering (F1 absorb — yeni merge order)

```
V5 P0 mirror (PR-X2-evidence merged)
       |
       v
E-4-1 (Helm chart skeleton) ─── tek başına başlayabilir; baseline
       |
       v
E-4-2a (Multi-tenant boundary contract; early advisory) ─── chart skeleton kullanır; E-4-5 + E-4-4 unblock eder
       |
       +───────── E-4-3 (DB + secret operator-owned) ─── values.yaml env block kullanır
       |
       +───────── E-4-5 (NetworkPolicy + PSS namespace-label) ─── chart templates'a eklenir (E-4-2a boundary kullanır)
       |
       +───────── E-4-4 (Observability surface) ─── chart templates'a opt-in (E-4-2a boundary kullanır)
       |
       v
E-4-2b (Multi-tenant matrix final seal; 3-way cross-AI) ─── E-4-5 + E-4-4 + E-4-3 evidence ref'leri; en sonda mühürleme
       |
       v
E-4-6 (helm-unittest runbook + epic-wide idempotency) ─── E-4-1..E-4-2b tüm template'leri test eder
       |
       v
Epic 4 closure entry → V5 roadmap §3 Epic 4 closure marker
       |
       v
(Epic 5/6/7 paralel devam; Epic 9 PR-Xfinal bağımlılık zinciri)
```

**Önerilen merge order (F1 absorb — kritik düzeltme):**

1. **E-4-1** (chart skeleton; bağımsız; en düşük risk)
2. **E-4-2a** (multi-tenant boundary contract; early advisory; E-4-5 + E-4-4 unblock eder) — **F1 fix: önceden E-4-2'nin geç sıralanması E-4-5'i bloklamıştı; şimdi E-4-2a erken**
3. **E-4-3** (DB/secret operator-owned doc; E-4-1 values structure kullanır; orta risk; paralel E-4-2a sonrası)
4. **E-4-5** (NetworkPolicy + PSS namespace-label; chart template'lere eklenir; E-4-2a boundary kullanır; orta risk)
5. **E-4-4** (Observability surface; chart template'lere opt-in; E-4-2a boundary kullanır; orta risk — Teams default pattern doğrulanır; Alertmanager runbook DEĞİL chart)
6. **E-4-2b** (multi-tenant matrix final seal; 3-way cross-AI; high risk; E-4-5 + E-4-4 + E-4-3 evidence ref ile mühürleme)
7. **E-4-6** (helm-unittest runbook + epic-wide idempotency; tüm template'leri test eder)

**Paralel yapılabilir:** E-4-3 + E-4-5 + E-4-4 ayrı worktree'lerde paralel; her biri E-4-2a merge sonrası başlar. E-4-2b ise üçünün de merge'i sonrası başlar (downstream evidence ref'leri için).

---

## 8. Microsoft Teams / Slack Discipline (HARD RULE özelinde Epic 4; F5 absorb)

CLAUDE.md HARD RULE **Workspace Tooling: Teams Primary, Slack YOK (bizim için), Slack Asset-Preserved başka tenants için** Epic 4'ün observability slice'ında **doğrudan** uygulanır.

**E-4-4 alert delivery default'u (zorunlu pattern; F5 absorb — Alertmanager chart template DEĞİL):**

- **Primary alert sink (bizim için):** Microsoft Teams Power Automate workflow + Adaptive Card (raw Alertmanager v4 JSON POST → flow içinde transform); örnek **operator-side runbook** (`docs/RB-alertmanager-teams-primary.md`), chart template DEĞİL
- **Vault env key (operator-side):** `TEAMS_WEBHOOK_URL` (active)
- **Slack snippet:** **asset-preserved dormant** sadece `docs/RB-slack-reactivation-chain.md` runbook'unda; chart template'lerinden tamamen ÇIKARILDI; rendered helm output'ta Slack izi YOK
- **Multi-tenant gelecek için Slack reactivation chain runbook referansı:** `docs/RB-slack-reactivation-chain.md` (E-4-4 doc'unda referans); ileride başka tenant talep ederse
- **YASAK pattern'ler (E-4-4 review'da reddedilir):**
  - `slack_configs:` LIVE rendered config (bizim için) — F5: rendered output'ta 0 occurrence
  - Chart template'de Alertmanager config (rendered output'ta) — F5: chart template DEĞİL, runbook
  - Tek `ExternalSecret` altında 2 key (SLACK + TEAMS) — Ready=False chain Teams'i de bozar
  - "Slack pattern sil + temizle" — multi-tenant asset-preserved disiplin (ADR-0027/0029 mirror pattern)
  - Yeni alert sink önerisinde Slack-default başlamak

**E-4-4 review test invariant'ları (F5 absorb):**

- **`slack_absence_in_rendered`:** Rendered helm template çıktısında `slack_configs:`, `SLACK_WEBHOOK_URL`, "slack" (case-insensitive) 0 occurrence
- **`no_alertmanager_in_chart_templates`:** Chart template'lerinde Alertmanager CRD/config rendered EDİLMEZ; sadece `docs/RB-alertmanager-teams-primary.md` runbook'unda örnek
- **`alert_default_teams`:** Doc'larda Teams primary string mevcut; "Slack reactivation chain only via tenant demand-driven explicit trigger" cümlesi `docs/RB-slack-reactivation-chain.md`'de

---

## 9. References

- **Parent roadmap:** `.claude/plans/V5-FULL-PRODUCTION-PROMOTION-ROADMAP.md` §3 Epic 4
- **Master plan:** `.claude/plans/AO-MA-SPM-MASTER-PLAN.md` (Faz 7+ promotion section)
- **V5 issue projection:** `.claude/plans/v5_issue_projection.v1.json` (Epic 4 sub-issues lazy-expand source — E-4-2 split sonrası 7 issue projeksiyonu güncellenmeli)
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

## 10. Closure Criteria (Epic 4 bütünü; F1 + F3 absorb güncel)

Epic 4 closed sayılması için:

- [ ] E-4-1, E-4-2a, E-4-3, E-4-5, E-4-4, E-4-2b, E-4-6 **7 slice MERGED** (F1 absorb: E-4-2 split sonrası) — her biri cross-AI AGREE + ao-release-gate green + admin bypass YOK
- [ ] Her slice için `.claude/plans/E-4-N-*.v1.json` schema-backed evidence VAR ve schema validate ediyor
- [ ] **E-4-2b** için `tenant_isolation_matrix.v1.json` 7 dimension complete + her dimension 4 const field (operator_enforceable + operator_action_required + runtime_enforced + live_validated) + 3-way cross-AI evidence ref (Codex + Mavis)
- [ ] `helm template deploy/helm/ao-kernel/` deterministic (3x render sha256-identical) — E-4-6 epic-wide idempotency test pass
- [ ] `helm unittest deploy/helm/ao-kernel/` 100% pass (E-4-6 runbook)
- [ ] **Guard flag invariant (F2 absorb):** `support_widening=false` + `production_platform_claim=false` + `live_adapter_execution=false` post-merge doğrulanır (`scripts/check_guard_flags.py` veya equivalent) + rendered output'ta 3 flag KEY string'i 0 occurrence
- [ ] **Workflow invariant (F3 absorb):** `.github/workflows/` altında Epic 4 PR'larıyla değişiklik YOK; her PR evidence `write_set` = `git diff` exact match
- [ ] **F7 absorb:** Tüm runbook doc'larda live cluster command yok (`helm install`, `helm upgrade`, `kubectl apply`); secret leak regex scan 0 occurrence; K8s API deprecation absence (no `extensions/v1beta1` / `policy/v1beta1`); `replicaCount: 0` absence anywhere
- [ ] **F5 absorb:** Rendered helm output'ta Slack izi YOK (`slack_configs:`, `SLACK_WEBHOOK_URL` 0 occurrence); Slack dormant sadece runbook
- [ ] **F6 absorb:** PSP manifest YOK (`kind: PodSecurityPolicy` 0 occurrence); PSS namespace label `restricted` default; egress allowlist values alanları (database/llm_providers/teams_webhook/dns) fail-closed default
- [ ] **F8 absorb:** `pyproject.toml` `[k8s-helm]` extra eklenmemiş; wheel build'de `deploy/helm/` YOK
- [ ] V5 roadmap doc §3 Epic 4 closure entry: "Closed: PR #N1..N7 + evidence ref" (7 PR, F1 split sonrası)
- [ ] V5 mirror Issue #Epic-4 closed; Project board "Done" column'a taşınmış (visibility mirror, not authority)

---

## 11. Out-of-Scope (Epic 4 PR'larında YASAK)

- 3 guard flag'in herhangi birinin flip'i (Epic 9 PR-Xfinal yetkisi)
- `.github/workflows/**` mutation (helm-unittest CI workflow gelecek epic; F3 absorb machine-enforced)
- `ao_kernel/` source modülleri içinde yeni code path (Epic 4 doc + template + schema epic'i)
- Live `helm install` / `helm upgrade` / `kubectl apply` execution (chart render-only test; live install operator-side runbook; F7 grep enforcement)
- `cost_tracking.available` flip (V5 roadmap E-4-5 olarak listelenmiş; bu plan'da Epic 2/9'a taşındı)
- "Production-ready" public claim (chart README dil "operator-installable beta template; production claim deferred")
- PyPI v5.x publish (Epic 9 PR-Xfinal sonrası)
- Slack LIVE config default (asset-preserved dormant snippet only sadece runbook; F5 absorb)
- PSP manifest (deprecated API; F6 absorb — PSS namespace-label only)
- `pyproject.toml` `[k8s-helm]` extra ekleme (F8 absorb — Epic 4 scope'undan çıkarıldı)
- "isolation achieved" / "isolation enforced" / "operator_enforced:true" overclaim dili (F4 absorb — advisory dil zorunlu)

---

## 12. Yaşayan dosyalar

- `.claude/plans/EPIC-4-KUBERNETES-HELM-MULTI-TENANT.md` (BU dosya; her slice closure'da entry güncellenir)
- `.claude/plans/E-4-1, E-4-2a, E-4-2b, E-4-3, E-4-4, E-4-5, E-4-6 *.md` + `.v1.json` (her slice impl'inde eklenir; F1 split sonrası 7 dosya)
- `.claude/plans/tenant_isolation_matrix.v1.json` (E-4-2b advisory artifact; her tenant boundary değişikliğinde güncellenir; E-4-2a contract pin'i baz)
- `ao_kernel/defaults/schemas/e-4-*-evidence.schema.v1.json` (her slice strict schema; 7 schema)
- `.claude/plans/V5-FULL-PRODUCTION-PROMOTION-ROADMAP.md` §3 Epic 4 row (her slice merge sonrası closure entry; 7 PR projeksiyonu güncel)

---

## 13. Iter-2 Absorb Summary (Codex thread 019e879d iter-1 → iter-2)

Bu doc Codex MCP thread `019e879d` iter-1 REVISE verdict'inde tespit edilen **8 finding** (7 blocker + 1 non-blocker) absorb edilerek revize edilmiştir. Per-finding fix mapping:

| Finding | Severity | Fix Location | Özet |
|---|---|---|---|
| **F1** | blocker, high | §2 (slice breakdown), §3 (risk table), §4 (cross-AI table), §7 (merge order), §10 (closure 7 slice), §12 (yaşayan dosyalar 7) | E-4-2 SPLIT → E-4-2a (early advisory contract, low risk, Codex only) + E-4-2b (late final matrix seal, high risk, 3-way Codex + Mavis). Yeni merge order: E-4-1 → E-4-2a → E-4-3 → E-4-5 → E-4-4 → E-4-2b → E-4-6. |
| **F2** | blocker, high | §2 (E-4-1 acceptance + E-4-6 values_invariants_test), §5 (Key absence enforcement bloğu), §6 (no_guard_flag_key invariant per slice), §10 (closure F2 absorb) | Guard flag KEY ABSENCE enforcement — rendered manifest/values/template/configmap/env/args HİÇBİR YERDE `support_widening` / `production_platform_claim` / `live_adapter_execution` key'leri yok. `: false` value pinning DA YASAK. Repo SSOT recompute-not-trust per slice. |
| **F3** | blocker, high | §1 (Out-of-scope ZERO TOUCH machine-enforced), §2 (her slice write-set'inde `tests/test_epic_4_*_write_set_invariant.py`), §5 (no-workflow-mutation invariant F3 absorb), §6 (write_set_diff_match invariant per slice), §10 (closure F3 absorb) | ZERO TOUCH `.github/workflows/**` machine-enforced fail-closed per slice — `git diff --name-only origin/main..HEAD` allowlist test; evidence `write_set` = actual diff exact match. |
| **F4** | blocker, high | §2 (E-4-2a + E-4-2b advisory dil bölümleri), §5 (Advisory dil tablosu F4 absorb), §6 (E-4-2a + E-4-2b all_4_const_fields_per_dimension), §11 (out-of-scope advisory dil overclaim YASAK) | E-4-2 matrix dili "operator_enforced:true" overclaim → 4 const field: `operator_enforceable:true` + `operator_action_required:true` + `runtime_enforced:false` + `live_validated:false`. Doc dili "isolation pattern" / "advisory boundary" (NOT "isolation achieved" / "isolation enforced"). |
| **F5** | blocker, medium | §2 (E-4-4 write-set: Alertmanager runbook DEĞİL chart template; Slack dormant sadece runbook), §6 (slack_absence_in_rendered + no_alertmanager_in_chart_templates), §8 (Teams/Slack discipline F5 absorb), §10 (closure F5 absorb), §11 (out-of-scope Slack LIVE config) | Alertmanager config chart template DEĞİL; operator-side runbook (`docs/RB-alertmanager-teams-primary.md`). Slack dormant sadece runbook (`docs/RB-slack-reactivation-chain.md`); chart template'lerinden tamamen ÇIKARILDI. Rendered output'ta Slack izi (`slack_configs:`, `SLACK_WEBHOOK_URL`, "slack") 0 occurrence. |
| **F6** | blocker, medium | §2 (E-4-5 write-set: namespace.yaml PSS label, podsecuritypolicy.yaml YOK), §6 (no_psp_manifest + pss_namespace_label_restricted + egress_allowlist_values_present + dns_only_default_beta_documented), §10 (closure F6 absorb), §11 (out-of-scope PSP YASAK) | PSP manifest YASAK (deprecated API); PSS namespace-label pattern (`pod-security.kubernetes.io/enforce: restricted` label on Namespace). NetworkPolicy values'ta `security.egress.allowlist.{database, llm_providers, teams_webhook, dns}` alanları fail-closed default + operator-configurable. DNS-only default = render-only/beta clearly documented. |
| **F7** | blocker, medium | §2 (her slice'da F7 acceptance/invariant ek), §6 (her slice invariant count arttı: 43+ → 76+), §10 (closure F7 absorb checklist), §11 (out-of-scope live commands) | Test invariant kategori eksik tamamlandı: secret leak regex scan (manifests/docs/evidence; `AKIA[0-9A-Z]{16}` / `sk-[A-Za-z0-9]{40,}` / `xoxp-` / `xoxb-` / `xoxa-` / `ghp_` / `gho_`); live `helm install` / `helm upgrade` / `kubectl apply` command absence in all runbooks (grep); `replicaCount: 0` absence anywhere (HARD RULE TEST cluster scale-to-zero YASAK); K8s API deprecation (no `extensions/v1beta1` / `policy/v1beta1` PodSecurityPolicy); PSS namespace label test (format + restricted); Slack absence in rendered output (0 `slack_configs:`); epic-wide `helm template` idempotency (3 sequential renders sha256-identical across ALL slice templates combined). |
| **F8** | non-blocker, medium | §1 (Scope: F8 absorb bölümü), §2 (E-4-1 acceptance + `tests/test_epic_4_1_no_pyproject_k8s_helm_extra.py`), §6 (E-4-1 no_pyproject_k8s_helm_extra invariant), §11 (out-of-scope) | `pyproject.toml` `[k8s-helm]` extra **Epic 4 scope'undan ÇIKARILDI**. Helm chart Python wheel ile dağıtılmaz; operator-installable artifact. E-4-1 invariant: pyproject diff guard (`[k8s-helm]` substring eklenmedi) + wheel build çıktısında `deploy/helm/` YOK. |

**Toplam değişiklik özeti:**

- 6 slice → **7 slice** (E-4-2 split sonrası)
- 43+ invariant test → **76+ invariant test** (F7 absorb sonrası)
- Önceki merge order: E-4-1 → E-4-3 → E-4-5 → E-4-4 → E-4-2 → E-4-6 (yanlış; E-4-5 boundary olmadan)
- **Yeni merge order:** E-4-1 → E-4-2a → E-4-3 → E-4-5 → E-4-4 → E-4-2b → E-4-6 (F1 absorb)
- Cross-AI: E-4-2a Codex only; **E-4-2b 3-way (Codex + Mavis)** zorunlu
- Yeni dil disiplini: "operator_enforceable" + 3 fail-state const (runtime_enforced:false, live_validated:false, operator_action_required:true) — F4 absorb
- Yeni test kategorileri: write_set_diff_match (F3), no_guard_flag_key (F2), no_psp_manifest (F6), slack_absence_in_rendered (F5), secret_leak_scan (F7), no_live_cluster_commands_in_runbooks (F7), no_deprecated_k8s_api (F7), helm_template_idempotency_epic_wide (F7), no_pyproject_k8s_helm_extra (F8), egress_allowlist_values_present (F6), dns_only_default_beta_documented (F6), all_4_const_fields_per_dimension (F4), no_alertmanager_in_chart_templates (F5)

**Iter-2 gönderim:** Codex MCP thread `019e879d` `codex-reply` ile bu revize edilmiş plan'a review istenecek. AGREE alınana kadar impl YASAK (Plan Consensus Autonomy: cross-AI consensus zorunlu).
