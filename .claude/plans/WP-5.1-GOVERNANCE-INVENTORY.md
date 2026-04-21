# WP-5.1 — Governance Inventory and Merge Gate Checklist

**Durum tarihi:** 2026-04-22
**İlişkili issue:** [#195](https://github.com/Halildeu/ao-kernel/issues/195)
**Üst WP:** [#196](https://github.com/Halildeu/ao-kernel/issues/196)
**Milestone:** [Production Hardening Program](https://github.com/Halildeu/ao-kernel/milestone/1)

## 1. Amaç

Repo içindeki merge/review/check guard'larını tek yerde envanterlemek ve
repo dışı GitHub settings tarafında kalan enforcement boşluklarını görünür
hale getirmek.

Bu slice runtime davranışı değiştirmez. Amacı, `WP-5` için gerçek
başlangıç noktası ve sıradaki governance PR kapsamını kilitlemektir.

## 2. Repo İçi Guard Envanteri

### 2.1 CI / workflow yüzeyi

`test.yml` şu işleri üretir:

- `event-gate`
- `lint`
- `test (3.11)`
- `test (3.12)`
- `test (3.13)`
- `coverage`
- `typecheck`
- `packaging-smoke`
- `benchmark-fast`
- `scorecard`
- `extras-install`

Canlı gözlem:

- `packaging-smoke` workflow içinde blocking iş olarak tanımlı; `needs:
  [event-gate, test, coverage, lint, typecheck]` ile ana test katmanına bağlı.
- `scorecard` advisory (`continue-on-error: true`).
- `extras-install` non-blocking (`continue-on-error: true`).
- `push` için `main` ve `codex/**` branch'lerinde tetikleniyor.
- `pull_request` için `opened`, `reopened`, `synchronize`,
  `ready_for_review`, `edited` (retarget) olaylarında tetikleniyor.
- `workflow_dispatch` fallback mevcut.

### 2.2 Repo içi operasyon guard'ları

- `.claude/scripts/check-branch-sync.sh`
  - stale branch / forbidden branch pattern / detached HEAD kontrolü
- `.claude/scripts/pre-commit-version-gate.sh`
  - stale base üstünde version bump bloklama
- `.claude/scripts/trigger-test-workflow.sh`
  - retarget sonrası manuel workflow tetikleme fallback'i
- `CLAUDE.md`
  - branch discipline
  - stacked PR merge protocol
  - living hardening principles

## 3. GitHub Protection Snapshot

Kaynak: `gh api repos/Halildeu/ao-kernel/branches/main/protection`

### 3.1 Aktif branch protection

- Required status checks: **aktif**
- Required review count: **1**
- Required conversation resolution: **aktif**
- Force push: **kapalı**
- Branch deletion: **kapalı**

### 3.2 Şu an required olan check'ler

- `lint`
- `test (3.11)`
- `test (3.12)`
- `test (3.13)`
- `coverage`
- `typecheck`

### 3.3 Şu an required OLMAYAN ama kritik olanlar

- `packaging-smoke`

### 3.4 Şu an zayıf kalan protection ayarları

- `required_status_checks.strict = false`
- `dismiss_stale_reviews = false`
- `require_code_owner_reviews = false`
- `require_last_push_approval = false`
- `enforce_admins = false`

### 3.5 Şu an eksik repo artefaktı

- `.github/CODEOWNERS` **yok**

### 3.6 Ruleset durumu

Kaynak: `gh api repos/Halildeu/ao-kernel/rules/branches/main`

- `main` için ayrı branch ruleset dönmüyor (`[]`)
- Mevcut enforcement klasik branch protection üstünden geliyor gibi görünüyor

## 4. Hüküm

Bugünkü governance resmi:

- Repo tarafında CI, branch discipline ve stacked PR protokolü artık güçlü.
- GitHub protection tarafı ise **temel seviyede**, ama henüz "sert" değil.
- En kritik açıklık: `packaging-smoke` required değil.
- İkinci kritik açıklık: `CODEOWNERS` yok, dolayısıyla code-owner review
  beklentisi fiilen enforce edilemiyor.
- Üçüncü kritik açıklık: stale review dismissal ve admin enforcement kapalı.

## 5. WP-5 İçin Sıradaki Slice'lar

### `WP-5.2` Repo-side governance PR

Hedef:

1. `.github/CODEOWNERS` ekle
2. governance/readme/checklist dokümanını repo içinde görünür hale getir
3. required check seti için önerilen hedef konfigürasyonu yaz
4. tek-maintainer döneminde code-owner enforcement önkoşulunu açık yaz

Beklenen repo diff:

- `.github/CODEOWNERS`
- `.github/REPO-GOVERNANCE.md`
- `.github/PULL_REQUEST_TEMPLATE.md`
- yaşayan status dosyasında `WP-5` ilerleme notu

### `WP-5.3` GitHub settings enforcement pass

Repo dışı uygulama checklist'i:

1. `packaging-smoke` required check olarak ekle
2. `strict=true`
3. `dismiss_stale_reviews=true`
4. `require_code_owner_reviews=true`
5. `enforce_admins=true`

Not:

- `require_last_push_approval=true` isteğe bağlı sıkılaştırmadır; ayrı karar
  ister. İlk governance pass'te zorunlu kabul edilmez.
- `require_code_owner_reviews=true` ayarı, canlı collaborator seti tek maintainer
  ise merge akışını kilitleyebilir; bu yüzden repo-side ownership yüzeyi ile
  platform enforcement kararı bilinçli olarak ayrılır.

## 6. Slice DoD

`WP-5.1` tamamlandı sayılabilmesi için:

1. Repo içi guard envanteri yazılı olmalı
2. GitHub protection snapshot yazılı olmalı
3. Açık boşluklar net listelenmiş olmalı
4. Sıradaki repo-side PR (`WP-5.2`) kapsamı tek anlamlı olmalı
5. Issue #195 ve yaşayan status dosyası bu snapshot'a bağlanmış olmalı
