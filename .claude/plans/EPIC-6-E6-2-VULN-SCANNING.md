# Epic 6 E-6-2 — Vulnerability Scanning Baseline (Dependabot + Trivy)

**Status:** Implementing.
**Codex thread:** `019e8385` (plan-time REVISE, `ready_for_impl: true`
with three critical revisions absorbed).
**Slice:** E-6-2 baseline (this PR) — Dependabot + Trivy filesystem
advisory baseline. **Snyk OUT (deferred to operator-bound follow-up).**
**Out-of-scope:** Snyk workflow, container image scans, required-gate
promotion, MEDIUM-severity widening, config/secret scanning.

## 1. Sorun

V5 Epic 6 E-6-2 plan'da yazıyor: "Vulnerability scanning: GitHub
Dependabot + Trivy + Snyk". Mevcut `.github/` baseline:

- Dependabot config YOK
- Trivy workflow YOK
- Snyk workflow YOK
- Sadece CodeQL (PR #796 pending merge) static analysis var

E-6-2 baseline kurulmalı; advisory mode'da başlamalı (alert baseline
triajı yapılmadan required gate'e promote etmek yanlış semantic
signal verir).

## 2. Codex iter-1 absorb (REVISE → ready_for_impl)

| # | Codex bulgu | Absorb |
|---|---|---|
| 1 | Snyk SNYK_TOKEN secret + tier decision + fork PR secret davranışı operator-bound | Snyk OUT/deferred; empty placeholder workflow YASAK; plan doc'ta explicit deferred note |
| 2 | Trivy advisory only ilk baseline'da (alert envanteri triajı yokken `exit-code: 1` yanlış semantic) | `exit-code: "0"` advisory; required-gate promotion ayrı hardening PR |
| 3 | `aquasecurity/trivy-action@v0` floating major risky | Exact semver pin (`@0.28.0`); Dependabot github-actions ecosystem güncel tutar |
| 4 | Dependabot runtime/dev groups doğru (flat tek group gürültü yaratır) | python-runtime + python-dev groups (exclude-patterns ile ayrım) |
| 5 | Trivy fs-only ≠ container image coverage | Plan doc'ta açık ayrım; container image scan follow-up slice (2 Dockerfile: deploy/ao-release-gate-service, deploy/live-adapter-gate-policy-service) |
| 6 | SARIF category `trivy-fs` doğru; CodeQL ile çakışmamalı | `category: trivy-fs` pinli; image scan eklenirse ayrı kategori (`trivy-image-<service>`) |
| 7 | Trivy permissions minimum | `contents:read + security-events:write` only; `actions:read` + `pull-requests:read` gereksiz |
| 8 | `scanners: vuln` ekle (config/secret scanning yanlışlıkla sızmasın) | Pinli; vulnerability scanning amacı net |
| 9 | Severity `CRITICAL,HIGH` baseline (MEDIUM noise sonraki PR) | Pinli |
| 10 | PyYAML `on:` boolean trap | Tests substring matching kullanır; YAML parse ETMEZ |
| 11 | open-pull-requests-limit semantiği (haftalık üretim değil; eşzamanlı açık PR sınırı) | Plan doc'ta açıklama; 5/3 conservative |

## 3. E-6-2 baseline değişiklik scope

### 3a. `.github/dependabot.yml` (YENİ)

```yaml
version: 2
updates:
  - package-ecosystem: pip
    directory: /
    schedule: { interval: weekly, day: monday, time: "04:00", timezone: UTC }
    open-pull-requests-limit: 5
    labels: [dependencies, security]
    commit-message: { prefix: "chore(deps)", include: scope }
    groups:
      python-runtime: { patterns: ["*"], exclude-patterns: [pytest*, ruff, mypy, mutmut, build, twine] }
      python-dev: { patterns: [pytest*, ruff, mypy, mutmut, build, twine] }
  - package-ecosystem: github-actions
    directory: /
    schedule: { interval: weekly, day: monday, time: "04:00", timezone: UTC }
    open-pull-requests-limit: 3
    labels: [dependencies, github-actions]
    commit-message: { prefix: "chore(actions)" }
```

### 3b. `.github/workflows/trivy.yml` (YENİ)

| Decision | Why (Codex absorb) |
|---|---|
| 4 trigger (push main + PR main + schedule + dispatch) | Standart security workflow pattern |
| Schedule cron `"23 4 * * 1"` (Mon 04:23 UTC) | Off-peak; best-effort stagger after the Dependabot 04:00 window (GitHub may delay either job; strict ordering is NOT guaranteed) |
| Permissions: `contents:read + security-events:write` | Minimum surface; gereksiz scope yok |
| `pull_request_target` YASAK | Fork-PR token risk |
| `actions/checkout@v6 + persist-credentials: false` | Repo convention + supply-chain hardening |
| `aquasecurity/trivy-action@0.28.0` | Exact semver pin (not `@v0` floating major) |
| `scan-type: fs` | Filesystem baseline; container image scan follow-up |
| `severity: CRITICAL,HIGH` | Baseline; MEDIUM noise deferred |
| `scanners: vuln` | Vulnerability only; config/secret scanning ayrı concern |
| `ignore-unfixed: true` | Unfixable CVE noise filter |
| `exit-code: "0"` | Advisory baseline (Codex absorb — required-gate promotion ayrı slice) |
| SARIF upload `category: trivy-fs` | CodeQL ile collision yok |
| `timeout-minutes: 20` | Fs scan beklenen 5-10 min |

### 3c. `tests/test_vuln_scanning_invariants.py` (YENİ)

31 invariant test (no YAML parse; substring assertions plus one
semver regex for the trivy-action pin — Codex 019e8385 absorb;
YAML 1.1 `on:` bool trap dodge).

Test grupları:
- Dependabot config (9 invariant)
- Trivy workflow shape (17 invariant)
- Snyk deferred + plan doc invariants (5 invariant)

### 3d. Plan doc — bu dosya.

## 4. Out-of-scope (E-6-2 follow-up slices)

| Konu | Sonra |
|---|---|
| **Snyk workflow** | E-6-2-snyk follow-up — `SNYK_TOKEN` repository secret + tier/license decision + fork PR event policy + explicit operator approval gerek |
| **Container image scans** (2 Dockerfile) | E-6-2-container follow-up — `aquasecurity/trivy-action@0.28.0` `image:` mode + matrix job (deploy/ao-release-gate-service + deploy/live-adapter-gate-policy-service) + ayrı SARIF kategorisi `trivy-image-<service>` |
| **Required-gate promotion** | E-6-2-gate follow-up — baseline triajı sonrası `exit-code: "1"` + `.trivyignore` + accepted-risk register + ruleset required check ekleme |
| **MEDIUM severity widening** | E-6-2-severity follow-up — baseline alert count düştükten sonra |
| **Config + secret scanning** (`scanners: secret,config`) | E-6-2-config-scan follow-up — config tarama gürültüsü ayrı triage gerektirir |
| **SBOM-CVE integration** | Epic 6 E-6-1b sonrası — SBOM-driven CVE diff per release |

## 5. Risk + Mitigation

| Risk | Mitigation |
|---|---|
| Fork PR token leak (security-events:write) | `pull_request_target` YASAK + invariant test |
| `aquasecurity/trivy-action` floating tag drift | Exact semver pin (`@0.28.0`) + invariant test reject `@v0` |
| Trivy alert envanteri baseline'sız required-gate | `exit-code: "0"` advisory + plan doc explicit deferred required-gate promotion |
| CodeQL + Trivy SARIF kategorisi çakışma | `category: trivy-fs` distinct + invariant test |
| Dependabot noise (haftalık 5+3 PR) | runtime/dev groups absorb eder; pratik açık-PR limit, üretim sayısı değil |
| Snyk placeholder workflow yanılsaması | Snyk workflow YOK + invariant `snyk.yml` exists assert false |
| Container image CVE'leri fs scan ile yakalanmaz | Plan doc §4 explicit follow-up + closeout "container image complete" demez |
| MEDIUM severity noise baseline'a sızar | `severity: CRITICAL,HIGH` pinli + invariant test |
| Config/secret scanning yanlışlıkla aktif | `scanners: vuln` pinli + invariant test |

## 6. Acceptance

- ✅ `pytest tests/test_vuln_scanning_invariants.py -x` → 31 pass local
- ✅ `ruff check tests/test_vuln_scanning_invariants.py` clean
- ✅ Plan doc — this file
- ⏳ Cross-AI post-impl review (Codex thread `019e8385` reply ile yeni iter)
- ⏳ CI green (4 PR rebase pattern Codex evidence file gerek)
- ⏳ Squash merge audit trail: Implementer Anthropic Claude / Reviewer OpenAI Codex
- ⏳ **Post-merge operator action**: GHAS code scanning enablement (E-6-5 + E-6-2 paylaşır)
- ⏳ **Post-merge measurement**: ilk Trivy main run alert count → plan doc evidence + baseline triage register

## 7. Public claim discipline

> Per Codex 019e8385 absorb — plan doc does NOT make marketing
> claims, does NOT promote guard flags, and explicitly records:

- `support_widening_allowed=false`
- `production_platform_claim_allowed=false`
- `live_adapter_execution_allowed=false`

> E-6-2 adds Dependabot + Trivy filesystem advisory baseline. It does
> NOT claim "production-grade security scanning", does NOT include
> Snyk (operator-bound deferred), does NOT cover container image CVEs
> (follow-up slice), does NOT promote any check to required gate
> (advisory only). The closeout records the baseline coverage and
> the explicit follow-up scope.

## 8. Bağlantı

- V5 Epic 6 plan: `V5-FULL-PRODUCTION-PROMOTION-ROADMAP.md` §3 (Epic
  6 Security + Compliance).
- Peer: Epic 6 E-6-1a SBOM (PR #795, MERGED main).
- Peer: Epic 6 E-6-5 CodeQL (PR #796, MERGEABLE BLOCKED — auto-merge
  pending; SARIF category `codeql` distinct from `trivy-fs`).
- HARD RULE — Cross-AI Peer Review: implementer Anthropic Claude;
  reviewer OpenAI Codex (thread `019e8385`).
- HARD RULE — Uzun Vadeli Kalıcı Çözüm: floating action tag yerine
  exact semver; required-gate promotion baseline triajı sonrası ayrı
  decision; placeholder workflow yanılsaması engellendi.
- HARD RULE — Continuous Autonomous Mode: bu turun 6. PR'ı; cross-AI
  peer reviewed sequential chain.
