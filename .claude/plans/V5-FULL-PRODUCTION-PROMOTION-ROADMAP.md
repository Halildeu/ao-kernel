# v5.0.0 — Full Production Promotion Roadmap

**Status:** PROPOSED · **Target:** 2026-12-31 (aspirational; exit criteria are authoritative)
**Owner:** Halil Kocoglu · **Consultation:** CNS-20260601-004 · **Codex thread** `019e80b3` (1 tur REVISE → revize 4-PR yapısı + 8 missing invariant absorb)

> **Visibility, NOT authority.** GitHub Milestones / Issues / Project board are a one-way mirror of this plan. Repo artifacts (`.claude/plans/`, JSONL evidence, `ao-release-gate`) remain the SSOT. Promotion authority lives in the **final operator-bound supersession PR** at the end of this roadmap; no individual epic or slice can flip the three guard flags on its own.

## 1. Mevcut durum (2026-06-01, updated)

- **PyPI:** `v4.1.0` source LIVE on main (post-PR #770 merge `4d0aa6d` + tag `v4.1.0` pushed 2026-06-01); publish.yml twine glob whitelist + workflow_dispatch fix MERGED (PR #787 → `5fede58`). PyPI publish operator dispatch pending.
- **Master plan:** AO-MA-SPM §Faz 1-7 program tamamlandı (7/7 fazlar MERGED 2026-06-01); autonomous multi-AI code-writing makinesi inşa edildi
- **Guard flags:** `support_widening` + `production_platform_claim` + `live_adapter_execution` = **const false** (GPP-9 closed; `keep_narrow_stable_runtime` decision)
- **Public claim:** "narrow stable runtime" governance plane; production-ready iddiası YOK
- **Epic ilerleme (this turn 2026-06-01):**
  - **Epic 1 E-1-1** AO-MA-11A-2 plan-approval gate wiring **MERGED** (PR #792 → `009d43b`)
  - **Epic 1 E-1-2** AO-MA-11E-2a drift checker **MERGED** (PR #788 → `7129bdb`)
  - **Epic 1 E-1-2** AO-MA-11E-2b sync workflow + PAT fallback **MERGED** (PR #789+#790 → `52307e1`+`abd9d58`)
  - **Epic 5 E-5-1** OTEL production tunables **MERGED** (PR #791 → `a8defc9`)
  - **Epic 5 E-5-2** Prometheus + Grafana dashboard **DONE-DISCOVERED** (PR-B5 baseline `docs/grafana/ao_kernel_default.v1.json` 8 panels + README + shape test)
  - **Epic 8 E-8-6** Migration guide v4.x → v5.0.0 **THIS PR** (`docs/MIGRATION-V5.md`)
  - **P0-4** ao-release-gate finding taxonomy fix **MERGED-PENDING** (PR #793 — CI green, awaiting auto-merge)
- **Pending operator action:** PR #764 CI shadow-skip permanent fix (operator review; PR #793 unblocks the dual check-run semantic), 11A-2 GH Environment setup (operator UI), 11E-2b PAT secret + workflow_dispatch (operator).

## 2. "Tam production" semantiği (Codex iter-1 invariant #1)

`production_platform_claim=true` flag flip **production-ready KANITI DEĞIL**. Sadece tüm kanıtlar tamamlandıktan sonra **kaydedilen sonuç bayrağı**. Semantic readiness 9 boyutta evidence matrix gerektirir:

1. Public support matrix net (OS/Python/provider)
2. Real provider live calls protected env'de çalışmış (live adapter envelope)
3. Cost/rate/circuit breaker limits canlı evidence ile doğrulanmış
4. Observability prod tunables (OTEL traces/metrics + dashboards)
5. Security/SBOM/license scans temiz (SOC2/CodeQL/Snyk/Dependabot)
6. Install/deploy lifecycle smoke (k8s/Helm + standalone PyPI)
7. Multi-tenancy isolation (varsa) testli (RBAC + secret + quota + audit)
8. Docs/runbooks güncel (deployment guide + operator runbook + API ref)
9. ao-release-gate + GitHub ruleset bypass-sız geçmiş (autonomous merge trail)

Final operator-bound decision PR tüm evidence refs'i bağlar — flag flip ANCAK orada.

## 3. 9 Epic (Codex iter-1 absorb: multi-tenancy ayrı epic; promotion governance P0)

### Epic P0 (Promotion Governance + Visibility Source Manifest)

**Purpose:** Roadmap'in görünürlük + governance temelini koy. Hiçbir guard flag flip içermez.

- E-P0-1 v5 roadmap plan doc (BU dosya) + projection manifest + acceptance matrix
- E-P0-2 Master plan amend (v5 operator-bound production promotion section)
- E-P0-3 GitHub mirror create — **manuel NOW path** (bu PR'da `github_write_authorized=true` flip; PR-X2 manuel mirror impl): Milestone "v5.0.0" + 13 issue (9 epic + 3 P0 gate + bu epic kendisi) + 23 label + Project board (Roadmap view + custom fields: Epic/Risk/Guard/Dependency/Estimate/Consensus/Evidence/Mirror digest/Release impact); created IDs + projection digest repo evidence'a geri yazılır (one-way mirror); AO-MA-11E-2 drift checker **LATER** binding adapter olarak gelir (manuel mirror precondition DEĞİL)
- E-P0-4 README badge + roadmap link (dil: "v5 production promotion roadmap"; "production-ready" badge YOK final PR'a kadar)
- E-P0-5 Issue forms (YAML): zorunlu `spm_anchor` + `ao_authority_artifact` + `artifact_sha256` + `plan_digest` + `slice_id` + `risk_class_source` + `evidence_classes`; risk field manuel düşürülemez (computed classifier'dan)

### Epic 1 (AO-MA-SPM follow-up — sistem mod tam aktivasyon)

**Risk:** normal · **Bağımlılık:** YOK (P0 runway)

- E-1-1 AO-MA-11A-2: GitHub Environment `ao-ma-plan-approval` required-reviewer wiring (otonom plan-consensus gate aktif)
- E-1-2 AO-MA-11E-2: GH Projects/Milestone/Issue one-way sync + anchor injection + drift checker (`mirror_drift_detected` → otonom DUR)
- E-1-3 AO-MA-11G-2c: CI workflow changelog enforcement check (`ao-kernel quality check-changelog` PR'da CI seviyesinde bloklar)
- E-1-4 AO-MA-11G-2d: Pre-commit hook for changelog (lokal yardımcı; release authority değil)
- E-1-5 AO-MA-4.6-2: native-import operator dogfooding (operator claude-cli ile worker_result üret → ao-kernel native-import ingest)
- E-1-6 Retro ADR cross-AI revalidation: ADR-0001..0004 Codex+Mavis ile `cross_ai_validated` review_status
- E-1-7 PR #764: CI shadow-skip permanent fix (operator gate; halen pending)

### Epic 2 (Live Adapter Execution Infrastructure — flag flip ITSELF Epic 9'da)

**Risk:** critical (epic-aggregate; eventual flip downstream) · **Bağımlılık:** Epic 1 + E-P0-2 (master plan amend) + **HARD STOP §14a preconditions** · **Reframe:** 2026-06-02 (Codex thread `019e87b6` iter-1 F7 absorb; this amend `019e87c9` iter-1 REVISE → iter-2 absorb)

> **AMEND NOTU (2026-06-02, iter-2 absorb):** Önceki E-2-1 listesi "operator-bound GPP supersession PR (flip authority)" idi. Bu yapı yeniden çerçevelendi: **bu epic infrastructure-only**; `live_adapter_execution` flag flip authority **Epic 9 PR-Xfinal**'e taşındı. Detaylı plan: `.claude/plans/EPIC-2-LIVE-ADAPTER-EXECUTION.md` (kaynak PR #827).
>
> **FAIL-CLOSED READINESS (iter-2 F1 absorb):** PR #827 is the Epic 2 detailed plan source; **current status REVISE / pending** until real Codex AGREE recorded and PR merged. **E-2-1 implementation MUST NOT start until:**
> 1. PR #827 merged to main with Codex AGREE evidence (cross-AI peer review verdict), AND
> 2. This amend (PR #828) merged to main with Codex AGREE evidence, AND
> 3. Full drift sweep complete (§4 / §7 / §10 / §14 / §14a all aligned).
>
> See §14a "HARD STOP — E-2-* + E-3-* implementation prerequisites" for machine-checkable gate conditions.
>
> **Scope-mapping for removed content (iter-2 F4 absorb):** Previous Epic 2 included production execution slices that are now mapped to other epics:
>
> | Old slice | New destination | Notes |
> |---|---|---|
> | Old E-2-2 production runbook | **Epic 4 (Deployment, Operations, Tenancy)** + **Epic 8 E-8-3 (Operator runbook docs)** | Runbook authority follows deployment epic |
> | Old E-2-3 real LLM worker / live provider envelope | **Epic 9 PR-Xfinal prerequisites** (live-evidence window) OR explicit pre-Xfinal operator-bound slice | Real network calls only under flip authority chain |
> | Old E-2-4 live test suite | **Epic 9 PR-Xfinal** pre-supersession 7-day live test window evidence | Time-bound live evidence is supersession prerequisite |
> | Old E-2-5 production telemetry | **Epic 5 (Observability + Production Telemetry)** — mostly merged via E-5-1 / E-5-2 | OTEL prod tunables already shipped |

- E-2-1 Live adapter envelope schema (`live_adapter_envelope.v1.json`; `mode` enum stub/dry_run only; `live_adapter_execution: const false` pin)
- E-2-2 Per-call audit evidence schema (`per_call_audit.v1.json`; cost field required = fail-closed)
- E-2-3 Cost ceiling enforcement module (soft/hard breach + concurrent atomicity)
- E-2-4 Dry-run harness (library-mode; runtime kill-switches; no live network)
- E-2-5 Secret resolution discipline module (value-based taint; env-var-only; 3-way cross-AI)
- E-2-6 Opt-in advisory CI workflow (artifact-only; no required check; pull_request type)
- E-2-7 Pre-supersession-PR checklist artifact for Epic 9 PR-Xfinal (18 conditions; 3-way cross-AI)

### Epic 3 (Support Widening Infrastructure — flag flip ITSELF Epic 9'da)

**Risk:** critical (epic-aggregate; eventual flip downstream) · **Bağımlılık:** Epic 1 (Epic 2 paralel olabilir) + **HARD STOP §14a preconditions** · **Reframe:** 2026-06-02 (Codex thread `019e87b2` iter-4 AGREE; this amend `019e87c9` iter-1 REVISE → iter-2 absorb)

> **AMEND NOTU (2026-06-02, iter-2 absorb):** Önceki E-3-1 listesi "operator-bound GPP supersession PR (flip authority)" idi. Bu yapı yeniden çerçevelendi: **bu epic infrastructure-only**; `support_widening` flag flip authority **Epic 9 PR-Xfinal**'e taşındı. Detaylı plan: `.claude/plans/EPIC-3-SUPPORT-WIDENING-MATRIX.md` (kaynak PR #826; Codex 4-iter chain AGREE, pending merge).
>
> **FAIL-CLOSED READINESS (iter-2 F1 absorb):** PR #826 (Epic 3 detail plan) is AGREE'd but pending merge. **E-3-1 implementation MUST NOT start until:**
> 1. PR #826 merged to main with Codex AGREE evidence, AND
> 2. This amend (PR #828) merged to main with Codex AGREE evidence, AND
> 3. Full drift sweep complete (§4 / §7 / §10 / §14 / §14a all aligned).
>
> See §14a "HARD STOP — E-2-* + E-3-* implementation prerequisites" for machine-checkable gate conditions.
>
> **Per-surface enablement future map (iter-2 F5 absorb):** Previous Epic 3 framed each surface dimension as part of its own flip PR. The reframed model is: **Epic 3 ships decision infrastructure only**; actual per-surface enablement happens in **Epic 9 PR-Xfinal per-class evidence subordinate PRs** (one PR per surface dimension), each requiring its own live evidence + operator authorization.
>
> | Old slice (support widening surface) | New destination | Provider-class | Specific platform / dimension |
> |---|---|---|---|
> | Old E-3-2 Windows desktop | Epic 9 PR-Xfinal per-surface supersession evidence | `os_platform` | `windows-amd64` |
> | Old E-3-3 Python 3.10 backward compat | Epic 9 PR-Xfinal per-surface supersession evidence | `python_version` | `cpython-3.10` |
> | Old E-3-4 Provider widening Mistral/Cohere/Llama | Epic 9 PR-Xfinal per-surface supersession evidence | `provider` | Mistral / Cohere / Llama (one PR per provider) |
> | Old E-3-5 ARM64 / Apple Silicon Docker | Epic 9 PR-Xfinal per-surface supersession evidence | `os_platform` | `linux-arm64` / `macos-arm64` |
>
> Each per-class evidence subordinate PR is operator-bound (no autonomous flip), carries its own live evidence pack, and supersedes a single surface dimension only. Aggregate `support_widening=true` flip remains in Epic 9 PR-Xfinal after all per-class subordinate PRs land.

- E-3-1 Support widening evidence schema v1 (`support_widening_evidence.v1.json`; const false + recursive closure)
- E-3-2 Per-surface smoke harness scaffolding (library-mode; stub adapters; runtime kill-switches)
- E-3-3 Advisory CI matrix workflow (`support-matrix-smoke.yml`; opt-in label trigger; no required check)
- E-3-4 Surface inventory document (`docs/SUPPORT-SURFACE-INVENTORY.md`; forbidden-language regex set)
- E-3-5 Cross-AI consensus protocol checklist (`widening-supersession-checklist.v1.json`; recompute bind fields)
- E-3-6 Recompute-not-trust validator (v1-only fail-closed; replay/TOCTOU/identity drift guards)

### Epic 4 (Deployment, Operations, Tenancy — multi-tenant production)

**Risk:** high · **Bağımlılık:** Epic 1 + Epic 2 paralel

- E-4-1 k8s Helm chart (deploy as governance microservice)
- E-4-2 Production deploy runbook (k8s + standalone + Docker Compose)
- E-4-3 Multi-tenant production config recipe (RBAC + secret isolation + quota + audit)
- E-4-4 Tenancy isolation test suite (cross-tenant leak prevention)
- E-4-5 Per-tenant cost tracking + rate limit (mevcut `cost_tracking.available const false` → flip)
- E-4-6 Operator incident response runbook (rollback + tag revert + pause)

### Epic 5 (Observability + Production Telemetry)

**Risk:** normal · **Bağımlılık:** Epic 2 (live adapter için anlamlı)

- E-5-1 OTEL production tracing (lazy-loadable; mevcut no-op fallback → prod tunables)
- E-5-2 Prometheus dashboard templates (Grafana JSON)
- E-5-3 Distributed tracing (multi-session correlation)
- E-5-4 SLI/SLO definitions (uptime, latency, cost burn-rate)
- E-5-5 Alertmanager rule templates (escalation policy)

### Epic 6 (Security + Compliance)

**Risk:** high · **Bağımlılık:** paralel

- E-6-1 SBOM generation (cyclonedx-py; release artifact)
- E-6-2 Vulnerability scanning: GitHub Dependabot + Trivy + Snyk
- E-6-3 SOC2/ISO 27001 documentation paket (audit-ready; NOT certification)
- E-6-4 3rd party license compliance audit (MIT bağımlılık matrisi)
- E-6-5 CodeQL workflow (GitHub Advanced Security)
- E-6-6 Security incident response playbook

### Epic 7 (Performance + Scalability)

**Risk:** normal · **Bağımlılık:** Epic 2 + Epic 5 paralel

- E-7-1 Production benchmark suite (cross-PR regression detection)
- E-7-2 Long-running session stress test (24h+ continuous)
- E-7-3 Memory profiling (mprof; production resource budgets)
- E-7-4 Provider rate limit production tuning per-tenant
- E-7-5 pgvector backend implementation (mevcut extra pin'li, henüz backend yok)

### Epic 8 (Documentation + Onboarding)

**Risk:** low · **Bağımlılık:** paralel

- E-8-1 Production deployment guide (k8s + standalone)
- E-8-2 Multi-tenant production config recipe (Epic 4-3 ile uyumlu)
- E-8-3 Operator runbook (incident response; Epic 4-6 ile)
- E-8-4 API reference auto-generated (Sphinx + autodoc)
- E-8-5 Tutorial: "Build your own AO-MA-SPM program with AI"
- E-8-6 Migration guide (v4.x → v5.0.0)

### Epic 9 (Final Promotion Decision)

**Risk:** critical · **Bağımlılık:** Tüm Epic 1-8 evidence complete

> **AMEND NOTU (2026-06-02, iter-3 absorb):** Epic 2 + Epic 3 reframe sonrası, **3 guard flag flip authority** bu epic'e konsolide edildi. Her flag **bağımsız per-flag gate** üzerinden değerlendirilir (per-flag pre-merge evidence requirement). Flip flag evidence chain'leri:
> - `live_adapter_execution` gate → Epic 2 E-2-7 pre-supersession checklist 18 conditions evidence pack (evidence_pack_A)
> - `support_widening` gate → Epic 3 E-3-5 supersession consensus protocol checklist evidence pack + per-class subordinate PR evidence aggregate (evidence_pack_B)
> - `production_platform_claim` gate → Epic 1-8 toplam evidence (evidence_pack_C)
>
> **All-or-none flip discipline (iter-3 N2 absorb — net ambiguity resolution):** PR-Xfinal **single all-or-none operator-bound decision PR**'dır. **3 flag ANCAK üç bağımsız gate de green ise aynı PR'da flip edilir**; **bir gate pending ise PR-Xfinal AÇILMAZ veya hiçbir flip yapılmaz**. Partial flip YASAK (single PR-Xfinal authority). Per-gate evidence bağımsız değerlendirilir (per-flag pre-merge requirement) ama flip kararı tek atomic transaction'da PR-Xfinal'de toplanır:
>
> | Gate state (3 flag) | PR-Xfinal davranışı |
> |---|---|
> | All 3 gates green (A + B + C complete) | PR-Xfinal açılabilir; 3 flag aynı PR'da atomic flip (squash commit'te) |
> | Any gate pending (A or B or C incomplete) | PR-Xfinal AÇILMAZ; pending gate'in evidence chain'i complete olmalı önce |
> | All gates pending | PR-Xfinal AÇILMAZ; Epic 1-8 evidence work devam |
>
> **Önemli:** "Per-flag independent gate" semantic = gate **evaluation** bağımsız (her flag kendi evidence chain'iyle), ama **flip decision** atomic (tek PR-Xfinal, üçü beraber). Partial flip alternatif modeli (per-flag operator-bound supersession PR per-flag) YASAK — single PR-Xfinal model seçildi (HARD RULE Admin Merge YASAK + No Fake Work + Operator-bound supersession discipline ile uyumlu).
>
> Bu konsolidasyon HARD RULE Cross-AI Peer Review + Plan Consensus Autonomy + Admin Merge YASAK + CI Kırmızıyken Merge YASAK ile uyumlu; operator-bound supersession tek noktada (Epic 9 PR-Xfinal) toplanır. Detay supersession PR taslağı: `.claude/plans/EPIC-9-FINAL-SUPERSESSION-PR.md` (gelecek slice; Epic 1-8 complete sonrası).
>
> **Machine-checkable preconditions:** §14a "HARD STOP — E-2-* + E-3-* implementation prerequisites" bu epic için de geçerli — Epic 9 PR-Xfinal açılışı tüm Epic 1-8 evidence + 3 per-flag gate hepsinin green + operator authorization şartlarına bağlı.

**PR-Xfinal:** operator-bound **single all-or-none** supersession decision PR. Tüm epic evidence refs'i bağlar + **3 guard flag atomic flip** (tek squash commit'te: `support_widening=true` + `production_platform_claim=true` + `live_adapter_execution=true`) + version bump (`v4.x` → `v5.0.0`) + CHANGELOG release entry + tag push. **Bu PR'dan ÖNCE hiçbir flag flip YOK; bu PR sonrası 3 flag birlikte true (partial flip YASAK).**

## 4. Bağımlılık + sıralama (Codex iter-1 absorb + iter-2 F3 absorb: Epic 2/3 reframe)

```
P0 runway (visibility + governance manifest)
   |
   v
Epic 1 (follow-up; sistem mod aktivasyon) ----------+
                                                     |
   +-> Epic 6 (security; paralel) ------------------ |
   |                                                 |
   +-> Epic 8 (docs; paralel) ---------------------- |
   |                                                 v
   |   Epic 2 (live adapter infrastructure; flip in Epic 9)
   |                |
   |                v
   |   Epic 3 (support widening infrastructure; flip in Epic 9)
   |   Epic 4 (deployment + tenancy)
   |   Epic 5 (observability prod)
   |   Epic 7 (performance + scalability)
   |                |
   +----------------+
                    v
   Epic 9 (final operator-bound single all-or-none promotion decision PR-Xfinal
           + 3 guard flag atomic flip [per-flag independent gates evaluation,
             but flip decision atomic in PR-Xfinal squash commit]
           + per-class subordinate PR evidence aggregate
           + v5.0.0 version bump)
```

**Reframe NOTU (iter-2 F3 absorb):** Epic 2 ve Epic 3 artık **infrastructure-only** epic'lerdir; içlerinde guard flag flip YOK. Flip authority **Epic 9 PR-Xfinal**'e konsolide edildi (per-flag independent gate semantic). Detay: §3 Epic 2 + Epic 3 + Epic 9 amend notları.

**Forecast:** 2026-12-31 (6 ay). **Authoritative:** exit criteria per epic; tarihten önce tamamlanan epic erken kapanır.

## 5. Exit criteria (epic başına)

Her epic için:
- All sub-issues closed via merged PR (cross-AI HARD RULE; implementer ≠ reviewer provider)
- Evidence ref repo'da (plan doc + JSONL + schema-backed artifact)
- ao-release-gate green + autonomous merge trail (bypass YOK)
- Plan doc'a "Closed: PR #X + evidence ref" entry

Final epic 9 ek koşullar:
- 9-boyutlu evidence matrix complete
- Operator açık beyan ("I authorize the production claim flip")
- v5.0.0 release notes social media plan
- Migration guide (v4.x → v5.0.0)

## 6. Guard flag flip authority path (Codex iter-1 invariant #4)

`live_adapter_execution` / `support_widening` / `production_platform_claim` için **AO-MA-11A normal approval YETMEZ** (`ao-ma-11a-plan-approval.schema.v1.json` zaten guard flags const false pin'liyor). Bunlar **ayrı operator-bound supersession path** gerektirir:

- Operator açık decision (commit/comment ile "I authorize flag flip")
- AO-MA-11A consensus advisory evidence (release authority değil; flag flip authority değil)
- Promotion decision PR tüm 9 epic evidence refs'i bağlar
- Final PR squash mesajında flag flip + evidence ref + operator authorization açık kayıt

## 7. GitHub-native görünürlük (mirror, NOT authority)

### Milestone
- **Title:** "v5.0.0 — Full Production Promotion"
- **Description:** "Roadmap target 2026-12-31; exit criteria are authoritative. GitHub project is a visibility mirror; repo artifacts remain authority. See `.claude/plans/V5-FULL-PRODUCTION-PROMOTION-ROADMAP.md`."
- **Due date:** 2026-12-31 (forecast)
- **State:** open

### Issues (P0 first wave; 9 epic issue + ~3 P0 gate issue)

Codex iter-1 invariant #7: ilk dalgada 80 issue açma; epic + P0 gate issues + source manifest projection açılır, alt issues lazy-expand edilir.

**P0 first wave issues (13 total: 10 epic parent + 3 P0 gate; iter-2 F3 absorb: Epic 2/3 labels updated to "infrastructure / flip-prerequisite"):**
1. Epic P0 — Promotion governance + visibility source manifest (parent)
2. Epic 1 — AO-MA-SPM follow-up (parent)
3. Epic 2 — Live adapter execution **infrastructure** (parent; flip-prerequisite — flip authority Epic 9)
4. Epic 3 — Support widening **infrastructure** (parent; flip-prerequisite — flip authority Epic 9)
5. Epic 4 — Deployment + operations + tenancy (parent)
6. Epic 5 — Observability + production telemetry (parent)
7. Epic 6 — Security + compliance (parent)
8. Epic 7 — Performance + scalability (parent)
9. Epic 8 — Documentation + onboarding (parent)
10. Epic 9 — Final promotion decision (parent; **3 guard flag flip authority — per-flag independent gate; consolidates Epic 2/3 flip authority**)
11. P0-GATE-1: v4.1.0 PyPI publish workflow fix (`.github/workflows/publish.yml` twine check JSON-distribution false-positive; high-risk operator gate)
12. P0-GATE-2: PR #764 CI shadow-skip permanent fix (high-risk `.github/workflows/test.yml` operator gate)
13. P0-GATE-3: V5 GitHub mirror create (PR-X2 manuel mirror NOW path; AO-MA-11E-2 drift checker LATER binding adapter)

Alt issues lazy expand: her epic'in sub-issue'ları E-N-M ID ile epic issue body'sinde checklist olarak listelenir; gerçek sub-issue açılışı epic in_progress'a girdiğinde.

### Project board

- **Title:** "Roadmap v5.0.0"
- **Layout:** Kanban (Todo / In Progress / Review / Blocked / Done) + Roadmap view (epic timeline)
- **Custom fields:** Epic (single-select 9 epic) / Risk (computed) / Guard role (single-select `flip-prerequisite:live_adapter` / `flip-prerequisite:support_widening` / `flip-prerequisite:production_platform_claim` / `flip-authority` / `none`; iter-2 F3 absorb: prerequisite vs authority ayrımı) / Dependency (text) / Estimate (number) / Consensus (single-select agreed/pending/not_started) / Evidence (URL) / Mirror digest (text) / Release impact (single-select minor/patch/major)

### Labels

- `epic-p0`, `epic-1`, ..., `epic-9`
- `status:planned`, `status:in_progress`, `status:review`, `status:blocked`, `status:done`
- `risk:critical`, `risk:high`, `risk:normal`, `risk:low`
- `flip-prerequisite:live_adapter` (Epic 2 infrastructure slices), `flip-prerequisite:support_widening` (Epic 3 infrastructure slices), `flip-prerequisite:production_platform_claim` (Epic 1-8 prerequisite slices)
- `flip-authority:live_adapter`, `flip-authority:support_widening`, `flip-authority:production_platform_claim` (Epic 9 PR-Xfinal ONLY; iter-2 F3 absorb: flip authority labels gate Epic 9'a kilitli, per-flag independent gate)
- `mirror:authority` (kalıcı; bu issue authority değil)

### README badge + roadmap link

- Mevcut README'de badge alanı: "[v5 Roadmap](https://github.com/Halildeu/ao-kernel/milestone/X) (production promotion in progress)"
- README'de "GitHub project is a visibility mirror; repo artifacts remain authority" cümlesi (Codex iter-1 invariant #2)

## 8. Cross-AI consensus per epic (Codex iter-1 invariant #9)

Blanket AGREE bu V5 roadmap planı (PR-X0 + PR-X1 + PR-X2 mirror sync) için kullanılır. Her epic/slice **kendi exact plan digest'i, write-set'i, risk class'ı, evidence requirement'ı** ile **ayrı plan-consensus consultation** gerektirir. Özellikle:

- Epic 2 (live adapter) — Codex + Mavis cross-AI consensus + operator approval
- Epic 3 (support widening) — Codex + Mavis cross-AI consensus + operator approval
- Epic 6 (security + compliance) — Codex + Mavis cross-AI consensus
- Epic 9 (final promotion) — Codex + Mavis cross-AI consensus + operator-bound supersession

## 9. Public claim language (Codex iter-1 invariant #8)

README, project page, badges — **dil "roadmap / planned" kalır**. "production-ready" / "full production" public claim **final promotion PR'dan ÖNCE KULLANILMAZ**. Mevcut "narrow stable runtime" framing devam eder.

Final promotion sonrası: "v5.0.0 — Production-Ready Governed Multi-AI Orchestration Runtime" claim'i public yapılır.

## 10. PR yapısı (Codex iter-1 revize 4-PR plan + PR-X2 manuel mirror NOW amend + iter-2 F3 absorb: Epic 2/3 slice families)

| PR | Scope | Risk | Guard flip |
|---|---|---|---|
| **PR-X0** (MERGED main 565876b, #771) | plan doc + projection manifest + acceptance matrix + master plan amend | normal | YOK |
| **PR-X1** | (PR-X0'a dahil; combined) | — | YOK |
| **PR-X2 (PR #769 family ailesi)** | manuel mirror NOW path amend: `github_write_authorized=true` + plan/projection PR-X2 path "manuel mirror NOW + 11E-2 drift checker LATER" yeniden tanım + master plan §12 satır eşleştirme | normal | YOK |
| **PR-X2-impl** | PR-X2 merge sonrası gh CLI ile mirror create (milestone + 23 label + 13 issue + project board) — repo-side state mutation; PR DEĞİL | normal | YOK |
| **PR-X2-evidence** | PR-X2-impl sonrası: created GH IDs + projection digest manifest'e geri yazılır (one-way mirror evidence write-back) | normal | YOK |
| **PR-X3-epic-2 (BU PR ailesi: detay plan + amend)** | Epic 2 reframe family: PR #827 (Epic 2 detail plan doc) + PR #828 (this; V5 roadmap §3 Epic 2 + Epic 3 amend) | medium (governance/docs) | YOK (infrastructure-only) |
| **PR-X3-epic-3** | Epic 3 reframe family: PR #826 (Epic 3 detail plan doc; Codex 4-iter AGREE pending merge) | medium (governance/docs) | YOK (infrastructure-only) |
| **Epic 2 slice family (E-2-1..E-2-7)** | 7 infrastructure slice PR'ları (envelope schema, audit, cost ceiling, dry-run, secret discipline, opt-in CI, pre-supersession checklist); each PR cross-AI reviewed | normal..high | YOK (infrastructure; flip authority Epic 9) |
| **Epic 3 slice family (E-3-1..E-3-6)** | 6 infrastructure slice PR'ları (evidence schema, smoke harness, advisory CI matrix, surface inventory, consensus protocol, recompute validator); each PR cross-AI reviewed | normal..high | YOK (infrastructure; flip authority Epic 9) |
| **PR-Xfinal** | Final operator-bound production promotion decision; 3 guard flag flip (per-flag independent gates) + v5.0.0 version bump + CHANGELOG release + tag push; per-class subordinate PRs (per-surface enablement) supersession evidence aggregate | critical | EVET (operator-bound; per-flag) |

PR-X2 (PR #769) ön koşulu: YOK (manifest amend authorized — cross-AI peer review + CI + merge). PR-X2-impl ön koşulu: PR-X2 merged. PR-X2-evidence ön koşulu: PR-X2-impl tamamlandı. AO-MA-11E-2 drift checker (Epic 1 E-1-2 sub-issue) LATER binding adapter olarak gelir; manuel mirror precondition DEĞİL.

**PR-X3 family ön koşulu (iter-2 F1 absorb):** Epic 2 + Epic 3 slice family PR'larının açılışı **§14a HARD STOP** preconditions'a bağlı — PR #826 + PR #827 + PR #828 üçü de merged + Codex AGREE evidence + drift sweep complete olmadan E-2-* / E-3-* slice PR'ı AÇILMAZ.

**Detay plan referansları:**
- Epic 2 (E-2-1..E-2-7): `.claude/plans/EPIC-2-LIVE-ADAPTER-EXECUTION.md` (PR #827)
- Epic 3 (E-3-1..E-3-6): `.claude/plans/EPIC-3-SUPPORT-WIDENING-MATRIX.md` (PR #826)
- Epic 9 supersession draft: `.claude/plans/EPIC-9-FINAL-SUPERSESSION-PR.md` (future slice; Epic 1-8 complete sonrası)

Opt-in CI check eklenebilir (gelecek slice) — slice PR'larının body'sinde §14a preconditions explicit declaration ZORUNLU (şimdilik PR body-based, gelecekte machine-checkable CI gate'e taşınabilir).

## 11. Out-of-scope (bu PR; v5 roadmap PR-X0)

- GitHub mirror sync (PR-X2)
- Guard flag flip (PR-Xfinal)
- Epic 1-9 slice impl (her epic kendi follow-up PR'ı)
- PyPI v5.0.0 publish (Epic 9 PR-Xfinal sonrası)
- "production-ready" public claim (final promotion sonrası)

## 12. Yaşayan dosyalar

- `.claude/plans/V5-FULL-PRODUCTION-PROMOTION-ROADMAP.md` (BU dosya; epic durumu güncellenir her epic kapandığında)
- `.claude/plans/v5_issue_projection.v1.json` (PR-X0'da; PR-X2 mirror sync source manifest; created GH IDs + digest binding)
- `.claude/plans/AO-MA-SPM-MASTER-PLAN.md` (PR-X0'da amend; v5 promotion section)
- `.claude/plans/ao_ma_status.v1.json` (epic merge sonrası status drift fix gerek)

## 13. Cross-AI review

Implementer: Claude (Anthropic). Reviewer: Codex (OpenAI) thread `019e80b3` — plan-time iter-1 REVISE (8 missing invariants + revize 4-PR yapısı: production_ready_semantics + visibility_not_authority + v5_source_manifest + guard_flip_path + tenant_isolation_claim + final_promotion_decision + issue_scale_control + public_claim_language). Post-impl review iter ile authoritative contract verify.

## 14. Sonraki adımlar (PR-X0 merge sonrası; iter-2 F3 absorb: Epic 2/3 reframe)

1. PR-X2 (manuel mirror NOW path amend; PR #769) merge sonrası: PR-X2-impl gh CLI mirror create (milestone + 23 label + 13 issue + project board); PR-X2-evidence ayrı PR ile created IDs + digest manifest'e geri yazılır; AO-MA-11E-2 (Epic 1 E-1-2) drift checker LATER binding adapter
2. Epic 1 sub-issue'ları lazy-expand (her sub-issue kendi consensus consultation)
3. **Epic 2 + Epic 3 infrastructure consensus before implementation** (iter-2 F3 absorb): PR #827 (Epic 2 detail plan) + PR #826 (Epic 3 detail plan) + PR #828 (this amend) üçü merged + Codex AGREE evidence; slice family PR'ları (E-2-1..E-2-7 + E-3-1..E-3-6) §14a HARD STOP preconditions sağlandıktan sonra açılır
4. Epic 4-8 paralel sub-issue açılışı (her sub-issue kendi plan-consensus + impl + cross-AI review + merge)
5. **Flip authority Epic 9 PR-Xfinal** (iter-2 F3 + iter-3 N2 absorb): per-flag independent gate **evaluation** + **atomic all-or-none flip decision** in single PR-Xfinal. Epic 1-8 evidence complete + 3 per-flag gates green (evidence_pack_A + B + C) → PR-Xfinal operator-bound supersession decision + 3 flag atomic flip (single squash commit: `live_adapter_execution=true` + `support_widening=true` + `production_platform_claim=true`) + per-class subordinate PR evidence aggregate + v5.0.0 publish. **Partial flip YASAK** — herhangi bir gate pending ise PR-Xfinal açılmaz.

## 14a. HARD STOP — E-2-* + E-3-* implementation prerequisites (iter-2 F2 absorb)

Epic 2 ve Epic 3 slice (E-2-1..E-2-7 ve E-3-1..E-3-6) implementation PR'ı **AÇILMAZ** aşağıdaki **machine-checkable preconditions** sağlanmadan:

### Pre-implementation gate conditions

All verify commands are **commit-scoped** (use PR merge commit, not current root file) and reference **existing-file** SSOT (no nonexistent paths). Output snippets are shown for clarity.

1. **PR #828 (this amend) MERGED to main**
   - Verify merge state + base + commit ancestry:
     ```bash
     gh pr view 828 --json mergedAt,baseRefName,mergeCommit \
       --jq 'select(.mergedAt != null and .baseRefName == "main" and .mergeCommit.oid != null)'
     # Then verify mergeCommit is ancestor of origin/main:
     PR828_SHA=$(gh pr view 828 --json mergeCommit --jq '.mergeCommit.oid')
     git fetch origin main --quiet
     git merge-base --is-ancestor "$PR828_SHA" origin/main && echo "PR #828 in main ancestry"
     ```

2. **PR #827 (Epic 2 detail plan source) MERGED to main with Codex AGREE evidence**
   - Verify merge state:
     ```bash
     gh pr view 827 --json mergedAt,baseRefName,mergeCommit \
       --jq 'select(.mergedAt != null and .baseRefName == "main")'
     ```
   - Verify Codex AGREE evidence at merge commit (NOT current root file — commit-scoped to avoid overwrite):
     ```bash
     PR827_SHA=$(gh pr view 827 --json mergeCommit --jq '.mergeCommit.oid')
     git fetch origin main --quiet
     git show "$PR827_SHA:local-ai-review-evidence.v1.json" \
       | jq -e '.work_package=="V5-EPIC-2-LIVE-ADAPTER-EXECUTION-PLAN" and .reviewer.verdict=="AGREE"'
     # Alternative via GitHub contents API (no local clone):
     gh api "repos/Halildeu/ao-kernel/contents/local-ai-review-evidence.v1.json?ref=$PR827_SHA" \
       --jq '.content' | base64 -d | jq -e '.reviewer.verdict=="AGREE"'
     ```
   - Verify detail plan file exists on `origin/main`:
     ```bash
     git fetch origin main --quiet
     git cat-file -e "origin/main:.claude/plans/EPIC-2-LIVE-ADAPTER-EXECUTION.md" \
       && echo "Epic 2 detail plan present on main"
     ```

3. **PR #826 (Epic 3 detail plan source) MERGED to main with Codex AGREE evidence**
   - Verify merge state:
     ```bash
     gh pr view 826 --json mergedAt,baseRefName,mergeCommit \
       --jq 'select(.mergedAt != null and .baseRefName == "main")'
     ```
   - Verify Codex AGREE evidence at merge commit (commit-scoped):
     ```bash
     PR826_SHA=$(gh pr view 826 --json mergeCommit --jq '.mergeCommit.oid')
     git fetch origin main --quiet
     git show "$PR826_SHA:local-ai-review-evidence.v1.json" \
       | jq -e '.work_package=="V5-EPIC-3-SUPPORT-WIDENING-MATRIX-PLAN" and .reviewer.verdict=="AGREE"'
     ```
   - Verify detail plan file exists on `origin/main`:
     ```bash
     git cat-file -e "origin/main:.claude/plans/EPIC-3-SUPPORT-WIDENING-MATRIX.md" \
       && echo "Epic 3 detail plan present on main"
     ```

4. **3 guard flags STILL allowed=false** (no premature flip; canonical SSOT path)
   - Canonical guard authority SSOT: `.claude/plans/gpp_status.v1.json` + `scripts/gpp_next.py` (NOT `ao_kernel/defaults/extensions.v1.json` — that file does not exist as a guard manifest):
     ```bash
     jq -e '.support_widening_allowed == false and .production_platform_claim_allowed == false and .live_adapter_execution_allowed == false' \
       .claude/plans/gpp_status.v1.json
     # Cross-check via gpp_next.py canonical guard authority output:
     python3 scripts/gpp_next.py | grep -E "(support_widening|production_platform_claim|live_adapter_execution).*false"
     ```
   - Verify no flag flip commit between this amend merge and slice PR opening:
     ```bash
     PR828_SHA=$(gh pr view 828 --json mergeCommit --jq '.mergeCommit.oid')
     git log "$PR828_SHA..origin/main" --oneline -- .claude/plans/gpp_status.v1.json \
       | grep -iE "(flip|allowed.*true)" || echo "No flag flip in window — gate clear"
     ```

5. **Drift sweep complete** (iter-2 F3 alignment verified — check at merge commit, not WIP)
   - Verify at PR #828 merge commit (commit-scoped; immune to subsequent edits):
     ```bash
     PR828_SHA=$(gh pr view 828 --json mergeCommit --jq '.mergeCommit.oid')
     git show "$PR828_SHA:.claude/plans/V5-FULL-PRODUCTION-PROMOTION-ROADMAP.md" \
       | grep -E "Epic 2 \(.*\+ flip\)|Epic 3 \(.*\+ flip\)" \
       && echo "DRIFT: + flip language still present" \
       || echo "Drift sweep clean (no + flip language in Epic 2/3)"
     # Verify §7 labels use flip-prerequisite/flip-authority:
     git show "$PR828_SHA:.claude/plans/V5-FULL-PRODUCTION-PROMOTION-ROADMAP.md" \
       | grep -E "flip-prerequisite:|flip-authority:" \
       && echo "§7 labels use prerequisite/authority semantic"
     ```

### Slice PR opening discipline (interim — until CI gate exists)

Şimdilik (iter-2 F2 absorb partial): Slice implementation PR'larının body'sinde **explicit declaration ZORUNLU**. PR body template:

```markdown
## §14a HARD STOP precondition check

- [x] PR #828 merged to main (commit: `<sha>`)
- [x] PR #827 merged to main with Codex AGREE (commit: `<sha>`)
- [x] PR #826 merged to main with Codex AGREE (commit: `<sha>`)
- [x] 3 guard flags STILL const false (verified: `<manifest path>`)
- [x] §4 / §7 / §10 / §14 drift sweep complete (verified: this amend merge)

Slice ID: E-X-Y
Detail plan ref: `.claude/plans/EPIC-X-*.md`
Cross-AI reviewer: <provider> (different from implementer)
```

**Gelecek slice (opt-in CI check):** Bu PR body declaration'ı machine-checkable CI gate'e taşınabilir — `.github/workflows/v5-slice-precondition.yml` (opt-in label trigger, advisory; no required check şimdilik). Bu iter-2 F2 absorb full machine-enforcement için gelecek work item.

### No-bypass clause

Bu HARD STOP'u bypass etme — admin merge, force push, ya da declaration eksik PR — **HARD RULE Admin Merge YASAK + HARD RULE No Fake Work** ihlali sayılır. Slice PR'ı açma yetkisi yok; PR açıldıysa close edilir ve §14a precondition complete after merge'den sonra yeniden açılır.
