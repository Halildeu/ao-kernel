# GP-2 — Deferred Support-Lane Backlog Reprioritization

**Status:** Active
**Date:** 2026-04-24
**Tracker:** [#329](https://github.com/Halildeu/ao-kernel/issues/329)
**Execution mode:** Kapsam disiplini, tek aktif planning/runtime tranche

## Amaç

`GP-1` closeout sonrası deferred support-lane backlog'unu tek anlamlı,
kanıt odaklı ve uygulanabilir bir sıraya indirmek.

Bu hattın amacı doğrudan widening implementasyonu değildir.
Amaç, bir sonraki runtime slice açılmadan önce backlog sırasını ve
giriş kapılarını netleştirmektir.

## Başlangıç Gerçeği

1. `GP-1` kapanmıştır ve verdict `stay_beta_operator_managed` olarak
   sabittir.
2. `docs/PUBLIC-BETA.md` içinde şu satırlar deferred durumdadır:
   - `bug_fix_flow` release closure
   - `gh-cli-pr` ile tam E2E remote PR açılışı
   - `docs/roadmap/DEMO-SCRIPT-SPEC.md` üç-adapter akışının canlı destek iddiası
   - adapter-path `cost_usd` reconcile
3. `GP-2.2` adapter-path `cost_usd` reconcile completeness hattı
   tamamlanmıştır; ek runtime patch gerekmemiş ve public support claim
   deferred kalmıştır.
4. `ST-8` tamamlanmıştır: `v4.0.0` stable PyPI üzerinde canlıdır.
5. Aktif widening tranche yoktur; yeni runtime/support işi açılmadan önce
   post-stable giriş sırası ve kanıt boşluğu kararı yazılı olmalıdır.

## Tranche Sırası

### `GP-2.1` — Deferred lane evidence-delta map (Completed)

- Issue: [#331](https://github.com/Halildeu/ao-kernel/issues/331)
- Hedef: her deferred satır için mevcut kanıt, kalan kanıt boşluğu, risk seviyesi
  ve promotion önkoşulunu tek tabloda toplamak.
- Çıktı: `Now / Next / Later` sırası + ilk uygulanabilir tranche önerisi.
- Decision record:
  `.claude/plans/GP-2.1-DEFERRED-LANE-EVIDENCE-DELTA-MAP.md`
- DoD:
  1. Deferred lane tablosu tek anlamlı hale gelir.
  2. İlk aktif runtime tranche açıkça seçilir.
  3. Seçilen tranche için tek issue + tek contract referansı üretilir.
- Kapanış: [#331](https://github.com/Halildeu/ao-kernel/issues/331) closed, PR [#332](https://github.com/Halildeu/ao-kernel/pull/332)

### `GP-2.2` — First runtime slice kickoff (Completed)

- Issue: [#333](https://github.com/Halildeu/ao-kernel/issues/333)
- Contract:
  `.claude/plans/GP-2.2-COST-USD-RECONCILE-COMPLETENESS.md`
- Hedef: `GP-2.1` çıktısındaki ilk lane'i dar kapsamlı bir implementation dilimi olarak başlatmak.
- Current candidate lane (from `GP-2.1`): adapter-path `cost_usd` reconcile completeness.
- Kural: yalnız bir lane açılır; diğer deferred satırlar status dosyasında
  `deferred` olarak kalır.
- İlerleme:
  1. `GP-2.2a` truth-capture closure merged via PR [#335](https://github.com/Halildeu/ao-kernel/pull/335)
  2. `GP-2.2b` deterministic assertion upgrade closed via issue [#336](https://github.com/Halildeu/ao-kernel/issues/336) and PR [#337](https://github.com/Halildeu/ao-kernel/pull/337)
  3. `GP-2.2c` runtime patch no-op closeout: ek runtime gap kanıtlanmadı
  4. `GP-2.2d` docs/status parity closeout merged via PR [#338](https://github.com/Halildeu/ao-kernel/pull/338)
- Sonuç: adapter-path `cost_usd` reconcile public support claim olarak
  **Deferred** kalır; behavior/evidence assertions mevcut ama support widening
  üretmez.

### `GP-2.3` — Post-stable adapter certification entry decision (Completed)

- Issue: [#361](https://github.com/Halildeu/ao-kernel/issues/361)
- Contract:
  `.claude/plans/GP-2.3-POST-STABLE-ADAPTER-CERTIFICATION-ENTRY.md`
- Hedef: `v4.0.0` stable live sonrası ilk support-widening giriş kapısını
  seçmek; bu tranche runtime widening veya yeni stable claim üretmez.
- Karar sırası:
  1. **Now:** `claude-code-cli` read-only real-adapter certification decision
  2. **Next:** `gh-cli-pr` live-write rollback rehearsal
  3. **Later:** extension/support widening ve genel amaçlı platform claim'i
- Sınır:
  - Runtime değişikliği yok
  - Version bump, tag veya publish yok
  - Stable support boundary unchanged kalır
- Closeout:
  - Next active issue: [#363](https://github.com/Halildeu/ao-kernel/issues/363)
  - Next active contract:
    `.claude/plans/GP-2.4-CLAUDE-CODE-CLI-READ-ONLY-CERTIFICATION.md`

### `GP-2.4` — `claude-code-cli` read-only certification contract (Completed)

- Issue: [#363](https://github.com/Halildeu/ao-kernel/issues/363)
- Verdict issue: [#371](https://github.com/Halildeu/ao-kernel/issues/371)
- Contract:
  `.claude/plans/GP-2.4-CLAUDE-CODE-CLI-READ-ONLY-CERTIFICATION.md`
- Hedef: `claude-code-cli` read-only real-adapter certification için
  prerequisite, smoke, evidence, failure-mode ve support-boundary karar
  kapılarını tek contract altında toplamak.
- Sıra:
  1. `GP-2.4a` preflight evidence contract (Completed via [#365](https://github.com/Halildeu/ao-kernel/issues/365))
  2. `GP-2.4b` governed workflow smoke evidence (Completed via [#367](https://github.com/Halildeu/ao-kernel/issues/367))
  3. `GP-2.4c` failure-mode matrix (Completed via [#369](https://github.com/Halildeu/ao-kernel/issues/369))
  4. `GP-2.4d` support boundary verdict (Completed via [#371](https://github.com/Halildeu/ao-kernel/issues/371))
- Son ilerleme:
  - `tests/test_claude_code_cli_smoke.py` helper JSON output contract'ını pinler
  - `auth_status=pass` + `prompt_access=fail` blocker olarak kalır
  - API key/env-token presence başarı sinyali sayılmaz
  - `scripts/claude_code_cli_workflow_smoke.py --output json --timeout-seconds 60`
    canlı governed workflow smoke'u `completed` state, schema-valid
    `review_findings`, `policy_checked` dahil evidence seti ve redacted
    adapter log doğrulamasıyla geçti
  - helper/workflow negative matrix stable finding code'larla pinlendi:
    `claude_binary_missing`, `claude_not_logged_in`, `prompt_access_denied`,
    `manifest_smoke_timeout`, `manifest_output_not_json`,
    `adapter_non_zero_exit`, `output_parse_failed`, `policy_denied`
- Final verdict:
  - `operator_managed_beta_keep`
- Next default:
  - `gh-cli-pr` live-write rollback rehearsal
- Sınır:
  - `claude-code-cli` production-certified değildir
  - Live-write yok
  - Stable support boundary unchanged kalır

### `GP-2.5` — `gh-cli-pr` live-write rollback rehearsal (Completed)

- Issue: [#373](https://github.com/Halildeu/ao-kernel/issues/373)
- Live rehearsal issue: [#375](https://github.com/Halildeu/ao-kernel/issues/375)
- Contract:
  `.claude/plans/GP-2.5-GH-CLI-PR-LIVE-WRITE-ROLLBACK-REHEARSAL.md`
- Hedef: `GP-2.3` kararındaki next lane'i açmadan önce remote side-effect,
  disposable sandbox, rollback/idempotency ve support-boundary kapılarını
  yazılı hale getirmek.
- No-side-effect kanıt:
  - `python3 scripts/gh_cli_pr_smoke.py --mode preflight --output json --timeout-seconds 20`
    -> `overall_status=pass`
  - `python3 scripts/gh_cli_pr_smoke.py --mode live-write --allow-live-write --head main --base main --output json --timeout-seconds 20`
    -> `overall_status=blocked`, finding `gh_pr_live_write_same_head_base`
- Live-write kanıt:
  - target repo: `Halildeu/ao-kernel-sandbox`
  - head branch: `smoke/gp25-livewrite-20260424T024918Z`
  - created PR: `https://github.com/Halildeu/ao-kernel-sandbox/pull/1`
  - final state: `CLOSED`
  - remote head cleanup: verified deleted (`404 Not Found`)
  - report: `/tmp/ao-kernel-gp25a-gh-cli-pr-live-write/gh-cli-pr-live-write.report.json`
- Helper fix:
  - `gh repo view` repo override artık current GitHub CLI ile uyumlu positional
    repo arg kullanır; regression `tests/test_gh_cli_pr_smoke.py` içinde pinlidir.
- Verdict:
  - `rehearsal_pass_keep_beta`
- Sınır:
  - `gh-cli-pr` live-write readiness probe Beta/operator-managed kalır.
  - `gh-cli-pr` tam E2E remote PR açılışı hâlâ stable shipped support değildir.
  - Support widening ancak ayrı promotion decision PR'ı ile açılır.

## Gate Modeli

1. **G1 — Truth parity:** docs/runtime/tests/CI aynı support sınırını söylemeli.
2. **G2 — Evidence-first ordering:** runtime değişiklikten önce kanıt boşluğu yazılı olmalı.
3. **G3 — Narrow-slice execution:** birden fazla deferred lane aynı PR hattında açılmaz.
4. **G4 — Decision record:** her promote/stay kararı issue + plan kaydı ile bağlanır.

## Başarı Kriterleri

1. `GP-2.1` sonunda deferred satırların sırasi tartışmasızdır.
2. `GP-2.2` ilk runtime/evidence slice olarak tamamlanmıştır.
3. `GP-2.3` post-stable next-slice kararını tamamlamıştır.
4. `GP-2.4` certification contract'ı açık issue/contract ile aktiftir.
5. Status SSOT'ta aktif issue/contract alanı günceldir.

## Risk Register

| Risk | Etki | Önlem |
|---|---|---|
| Scope creep | Yüksek | yalnız reprioritization; runtime widening bu tranche'ta yok |
| Overclaim drift | Yüksek | PUBLIC-BETA ve SUPPORT-BOUNDARY parity zorunlu |
| Paralel lane açma | Orta | tek aktif runtime slice kuralı |
| Karar kaydı eksikliği | Orta | issue + contract + status üçlüsü zorunlu |
