# Repo Governance and Merge Gates

**Durum tarihi:** 2026-04-22
**Program status SSOT:** [`.claude/plans/PRODUCTION-HARDENING-PROGRAM-STATUS.md`](../.claude/plans/PRODUCTION-HARDENING-PROGRAM-STATUS.md)
**Operasyon protokolü:** `CLAUDE.md` §19 ve §20

Bu doküman `main` hattı için repo tarafında görünen merge güvenliği
yüzeylerinin kısa SSOT özetidir. Amaç, "hangi gate repoda", "hangi gate GitHub
ayarında" ve "hangi sıkılaştırma henüz platformda açılmadı" sorularını tek
bakışta cevaplamaktır.

## 1. Repo İçinde Enforce Edilenler

### 1.1 Workflow gate yüzeyi

Kaynak: `.github/workflows/test.yml`

Workflow içinde gerçek hard gate olarak ele alınan işler:

- `lint`
- `test (3.11)`
- `test (3.12)`
- `test (3.13)`
- `coverage`
- `typecheck`
- `packaging-smoke`

Bu yüzeyde ek CI sinyalleri de vardır:

- `benchmark-fast`
  - görünür regresyon sinyalidir; `main` hattında yeşil kalması beklenir
- `scorecard`
  - advisory, `continue-on-error: true`
- `extras-install`
  - optional smoke, `continue-on-error: true`

### 1.2 Repo içi operasyon guard'ları

- `.claude/scripts/check-branch-sync.sh`
  - stale branch, yasak branch pattern'i, detached HEAD kontrolü
- `.claude/scripts/pre-commit-version-gate.sh`
  - stale base üstünde version bump bloklama
- `.claude/scripts/trigger-test-workflow.sh`
  - retarget sonrası manuel workflow tetikleme fallback'i
- `.github/PULL_REQUEST_TEMPLATE.md`
  - scope, validation ve governance checklist yüzeyi
- `.github/CODEOWNERS`
  - ownership SSOT

## 2. GitHub Platform Ayarında Enforce Edilenler

Kaynak: `gh api repos/Halildeu/ao-kernel/branches/main/protection`

Şu an aktif branch protection unsurları:

- required status checks
- 1 approval
- conversation resolution
- force-push kapalı
- branch deletion kapalı

## 3. `main` İçin Hedef Protection Konfigürasyonu

WP-5 hedefi olarak `main` branch protection için beklenen minimum set:

### 3.1 Required checks

- `lint`
- `test (3.11)`
- `test (3.12)`
- `test (3.13)`
- `coverage`
- `typecheck`
- `packaging-smoke`

### 3.2 Review ve merge ayarları

- `strict = true`
- `dismiss_stale_reviews = true`
- `required_approving_review_count = 1`
- `required_conversation_resolution = true`
- `enforce_admins = true`

### 3.3 Code-owner notu

`CODEOWNERS` dosyası repo içinde şimdi mevcuttur, ancak `require_code_owner_reviews = true`
ayarının platformda açılması operasyonel bir önkoşula bağlıdır:

- Şu an canlı GitHub collaborator görünümünde yalnız `@Halildeu` yazma/admin
  yetkisi ile görünmektedir.
- Bu durumda code-owner review zorunluluğu tek maintainer döneminde normal
  merge akışını kilitleyebilir.

Bu yüzden code-owner enforcement kararı iki şekilde ele alınmalıdır:

1. en az bir ikinci write-access maintainer görünür hale geldiğinde platformda
   `require_code_owner_reviews = true` açılır
2. aksi durumda `CODEOWNERS` repo içi ownership ve review hedefi olarak kalır,
   ama platform enforcement ayrı karar olarak tutulur

Bu nüans `WP-5.3` sırasında açıkça yeniden değerlendirilmelidir.

## 4. İşletim Kuralları

- Stacked PR zincirlerinde varsayılan merge yöntemi `merge commit`tir.
- Alt PR merge olduktan sonra üst PR retarget edilip diff yeniden doğrulanır.
- Retarget sonrası otomatik check üretilmezse `.claude/scripts/trigger-test-workflow.sh`
  fallback olarak kullanılır.
- Runtime veya packaging yüzeyine dokunan değişikliklerde docs/runtime/test/CI
  parity birlikte korunur; yalnız doküman yeşili release kanıtı sayılmaz.

## 5. Bu Dokümanın Rolü

Bu dosya yaşayan backlog değildir. Yaşayan execution durumu için:

- `.claude/plans/PRODUCTION-HARDENING-PROGRAM-STATUS.md`

Tarihsel inventory ve slice geçmişi için:

- `.claude/plans/WP-5.1-GOVERNANCE-INVENTORY.md`
