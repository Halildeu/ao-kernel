# v5.0.0 — Full Production Promotion Roadmap

**Status:** PROPOSED · **Target:** 2026-12-31 (aspirational; exit criteria are authoritative)
**Owner:** Halil Kocoglu · **Consultation:** CNS-20260601-004 · **Codex thread** `019e80b3` (1 tur REVISE → revize 4-PR yapısı + 8 missing invariant absorb)

> **Visibility, NOT authority.** GitHub Milestones / Issues / Project board are a one-way mirror of this plan. Repo artifacts (`.claude/plans/`, JSONL evidence, `ao-release-gate`) remain the SSOT. Promotion authority lives in the **final operator-bound supersession PR** at the end of this roadmap; no individual epic or slice can flip the three guard flags on its own.

## 1. Mevcut durum (2026-06-01)

- **PyPI:** `v4.1.0` source LIVE on main (post-PR #770 merge `4d0aa6d` + tag `v4.1.0` pushed 2026-06-01); GitHub Actions publish.yml `dist/` artifact format hatasıyla başarısız (twine check JSON evidence dosyalarını distribution saydı); fix ayrı PR (`.github/workflows/publish.yml` high-risk operator review gerek)
- **Master plan:** AO-MA-SPM §Faz 1-7 program tamamlandı (7/7 fazlar MERGED 2026-06-01); autonomous multi-AI code-writing makinesi inşa edildi
- **Guard flags:** `support_widening` + `production_platform_claim` + `live_adapter_execution` = **const false** (GPP-9 closed; `keep_narrow_stable_runtime` decision)
- **Public claim:** "narrow stable runtime" governance plane; production-ready iddiası YOK
- **Pending follow-up:** PR #764 (CI shadow-skip permanent fix operator gate), 11A-2 (GH Environment gate wiring), 11E-2 (GH Projects/Milestone/Issue mirror sync), 11G-2c (CI/pre-commit changelog enforcement + 4.6 dogfooding + retro ADR cross-AI revalidation)

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

### Epic 2 (Live Adapter Execution — `live_adapter_execution=true` enablement)

**Risk:** critical · **Bağımlılık:** Epic 1 + E-P0-2 (master plan amend)

- E-2-1 Operator-bound GPP supersession PR (live_adapter_execution flip authority decision)
- E-2-2 Production runbook: live adapter envelope + cost guardrails production tuning + circuit breaker production limits
- E-2-3 4.5 stub → 4.6 native-import → real LLM worker production envelope (Anthropic + OpenAI + Mavis canlı providers)
- E-2-4 Live adapter test suite (real provider calls; SLA budget; cost tracking enabled; mocked olmayan)
- E-2-5 Production telemetry: OTEL trace gerçek provider calls; usage/cost metrics

### Epic 3 (Support Widening — `support_widening=true` enablement)

**Risk:** critical · **Bağımlılık:** Epic 1 + Epic 2

- E-3-1 Operator-bound GPP supersession PR (support_widening flip authority)
- E-3-2 Windows desktop support (mevcut "Operating System :: POSIX" enlarge; Windows + macOS Apple Silicon + Linux ARM64)
- E-3-3 Python 3.10 backward compat decision (mevcut >=3.11; eski distro için yararlı?)
- E-3-4 Provider widening matrix: Mistral / Cohere / Llama (HuggingFace adapter); per-provider capability profile
- E-3-5 ARM64/Apple Silicon Docker images (CI multi-arch build)

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

**PR-Xfinal:** operator-bound supersession decision PR. Tüm epic evidence refs'i bağlar + 3 guard flag flip (`support_widening=true` + `production_platform_claim=true` + `live_adapter_execution=true`) + version bump (`v4.x` → `v5.0.0`) + CHANGELOG release entry + tag push. **Bu PR'dan ÖNCE hiçbir flag flip YOK.**

## 4. Bağımlılık + sıralama (Codex iter-1 absorb)

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
   |   Epic 2 (live adapter envelope + flip)
   |                |
   |                v
   |   Epic 3 (support widening + flip)
   |   Epic 4 (deployment + tenancy)
   |   Epic 5 (observability prod)
   |   Epic 7 (performance + scalability)
   |                |
   +----------------+
                    v
   Epic 9 (final operator-bound promotion decision PR + 3 flag flip + v5.0.0)
```

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

**P0 first wave issues (13 total: 10 epic parent + 3 P0 gate):**
1. Epic P0 — Promotion governance + visibility source manifest (parent)
2. Epic 1 — AO-MA-SPM follow-up (parent)
3. Epic 2 — Live adapter execution (parent; guard-flip)
4. Epic 3 — Support widening (parent; guard-flip)
5. Epic 4 — Deployment + operations + tenancy (parent)
6. Epic 5 — Observability + production telemetry (parent)
7. Epic 6 — Security + compliance (parent)
8. Epic 7 — Performance + scalability (parent)
9. Epic 8 — Documentation + onboarding (parent)
10. Epic 9 — Final promotion decision (parent; guard-flip + flag flip)
11. P0-GATE-1: v4.1.0 PyPI publish workflow fix (`.github/workflows/publish.yml` twine check JSON-distribution false-positive; high-risk operator gate)
12. P0-GATE-2: PR #764 CI shadow-skip permanent fix (high-risk `.github/workflows/test.yml` operator gate)
13. P0-GATE-3: V5 GitHub mirror create (PR-X2 manuel mirror NOW path; AO-MA-11E-2 drift checker LATER binding adapter)

Alt issues lazy expand: her epic'in sub-issue'ları E-N-M ID ile epic issue body'sinde checklist olarak listelenir; gerçek sub-issue açılışı epic in_progress'a girdiğinde.

### Project board

- **Title:** "Roadmap v5.0.0"
- **Layout:** Kanban (Todo / In Progress / Review / Blocked / Done) + Roadmap view (epic timeline)
- **Custom fields:** Epic (single-select 9 epic) / Risk (computed) / Guard (single-select live_adapter/support/production/none) / Dependency (text) / Estimate (number) / Consensus (single-select agreed/pending/not_started) / Evidence (URL) / Mirror digest (text) / Release impact (single-select minor/patch/major)

### Labels

- `epic-p0`, `epic-1`, ..., `epic-9`
- `status:planned`, `status:in_progress`, `status:review`, `status:blocked`, `status:done`
- `risk:critical`, `risk:high`, `risk:normal`, `risk:low`
- `guard-flip:live_adapter`, `guard-flip:support_widening`, `guard-flip:production_platform_claim`
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

## 10. PR yapısı (Codex iter-1 revize 4-PR plan + PR-X2 manuel mirror NOW amend)

| PR | Scope | Risk | Guard flip |
|---|---|---|---|
| **PR-X0** (MERGED main 565876b, #771) | plan doc + projection manifest + acceptance matrix + master plan amend | normal | YOK |
| **PR-X1** | (PR-X0'a dahil; combined) | — | YOK |
| **PR-X2 (BU PR)** | manuel mirror NOW path amend: `github_write_authorized=true` + plan/projection PR-X2 path "manuel mirror NOW + 11E-2 drift checker LATER" yeniden tanım + master plan §12 satır eşleştirme | normal | YOK |
| **PR-X2-impl** | PR-X2 merge sonrası gh CLI ile mirror create (milestone + 23 label + 13 issue + project board) — repo-side state mutation; PR DEĞİL | normal | YOK |
| **PR-X2-evidence** | PR-X2-impl sonrası: created GH IDs + projection digest manifest'e geri yazılır (one-way mirror evidence write-back) | normal | YOK |
| **PR-Xfinal** | Final operator-bound production promotion decision; 3 guard flag flip + v5.0.0 version bump + CHANGELOG release + tag push | critical | EVET (operator-bound) |

PR-X2 (BU PR) ön koşulu: YOK (manifest amend authorized — cross-AI peer review + CI + merge). PR-X2-impl ön koşulu: PR-X2 merged. PR-X2-evidence ön koşulu: PR-X2-impl tamamlandı. AO-MA-11E-2 drift checker (Epic 1 E-1-2 sub-issue) LATER binding adapter olarak gelir; manuel mirror precondition DEĞİL.

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

## 14. Sonraki adımlar (PR-X0 merge sonrası)

1. PR-X2 (manuel mirror NOW path amend; BU PR) merge sonrası: PR-X2-impl gh CLI mirror create (milestone + 23 label + 13 issue + project board); PR-X2-evidence ayrı PR ile created IDs + digest manifest'e geri yazılır; AO-MA-11E-2 (Epic 1 E-1-2) drift checker LATER binding adapter
2. Epic 1 sub-issue'ları lazy-expand (her sub-issue kendi consensus consultation)
3. Epic 2+3 (guard-flip) ayrı Codex+Mavis cross-AI consensus
4. Epic 4-8 paralel sub-issue açılışı (her sub-issue kendi plan-consensus + impl + cross-AI review + merge)
5. Tüm epic evidence complete → PR-Xfinal operator-bound supersession decision + flag flip + v5.0.0 publish
