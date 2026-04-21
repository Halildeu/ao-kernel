# Production Hardening Program Status

**Durum tarihi:** 2026-04-22
**Amaç:** `ao-kernel`'i dar ama kanıtlı Public Beta yüzeyinden, kontrollü
adımlarla daha güvenilir ve sonunda daha genel amaçlı production-grade coding
automation platform çizgisine taşımak.
**Yürütme modu:** Kapsam disiplini
**Bu dosyanın rolü:** yaşayan execution backlog + program status SSOT

## 1. SSOT Sınırları

- **Program execution status / backlog:** bu dosya
- **Yaşayan hardening ilkeleri:** `CLAUDE.md` §20
- **Public Beta support boundary:** `docs/PUBLIC-BETA.md`
- **Tarihsel policy-command closure planı:** `.claude/plans/POLICY-COMMAND-ENFORCEMENT-PROGRAM-PLAN.md`
- **GitHub milestone:** [Production Hardening Program](https://github.com/Halildeu/ao-kernel/milestone/1)
- **GitHub tracker issue:** [#201](https://github.com/Halildeu/ao-kernel/issues/201)

## 2. Başlangıç Gerçeği

- `WP-0` ile `WP-4` fiilen kapanmıştır.
- `main` hattında truth parity, policy command enforcement, behavioral policy
  tests ve wheel-first packaging smoke mevcuttur.
- Repo bugün **dar ama kanıtlı bir governed runtime / Public Beta** seviyesindedir.
- Repo bugün hâlâ **genel amaçlı production coding automation platformu**
  seviyesinde değildir.

## 3. Yürütme Kuralları

1. Aynı anda en fazla `1 ana WP + 1 düşük riskli docs/test WP` açık olur.
2. Her WP tek branch, tek PR, tek net kabul kriteri ile yürür.
3. Runtime semantiği değiştiren WP, kendinden önceki aktif runtime WP merge
   olmadan başlamaz.
4. Her WP kapanışında zorunlu kayıt:
   - status güncellemesi
   - PR / commit referansı
   - test kanıtı
   - smoke / package kanıtı gerekiyorsa onun çıktısı
   - kalan deferred notları
5. Support boundary ancak code path + davranışsal test + CI gate + ilgili doc
   birlikte mevcutsa genişletilir.

## 4. Program Tahtası

| WP | Faz | Durum | Hedef | Zorunlu kanıt |
|---|---|---|---|---|
| `WP-0` Authority/support matrix | Baseline | Completed on `main` | shipped / beta / deferred / inventory ayrımı | `docs/PUBLIC-BETA.md`, README parity |
| `WP-1` Runtime/docs truth patch | Baseline | Completed on `main` | docs overclaim temizliği | docs diff + review |
| `WP-2` Policy command enforcement | Baseline | Completed on `main` | adapter CLI command deny gerçekten live | runtime tests + deny repro |
| `WP-3` Policy rollout test upgrade | Baseline | Completed on `main` | behavior-first governance testleri | rollout pytest paketi |
| `WP-4` Packaging/install trust | Baseline | Completed on `main` | wheel-only smoke gerçek gate olur | `scripts/packaging_smoke.py` + CI |
| `WP-5` Release governance hardening | Faz 3 | **Active** ([#196](https://github.com/Halildeu/ao-kernel/issues/196)) | branch protection / required checks / CODEOWNERS / merge gate sertliği | repo diff + GitHub settings checklist |
| `WP-6` Worktree/branch safety control loop | Faz 3 | Planned ([#197](https://github.com/Halildeu/ao-kernel/issues/197)) | stale base / overlap / dirty worktree riskini operasyonel kapatmak | ops komutları + usage proof |
| `WP-7` Path-scoped write ownership | Faz 3 | Planned ([#198](https://github.com/Halildeu/ao-kernel/issues/198)) | aynı path alanına iki aktif writer çakışmasın | ownership tests + takeover audit |
| `WP-8` Real adapter certification | Faz 4 | Planned ([#199](https://github.com/Halildeu/ao-kernel/issues/199)) | en az 2 gerçek adapter prod-tier smoke ve failure-mode testlerinden geçsin | capability matrix + smoke logs |
| `WP-9` Ops/runbook/incident readiness | Faz 4 | Planned ([#200](https://github.com/Halildeu/ao-kernel/issues/200)) | rollback / incident / support boundary / known bugs paketi | runbook + drill evidence |

## 5. Şimdi

### `WP-5` — Release Governance Hardening

**Neden şimdi**
- Teknik closure büyük ölçüde tamam; bundan sonraki ana risk yanlış merge,
  yumuşak gate veya repo-policy bypass.

**GitHub takip**
- üst issue: [#196](https://github.com/Halildeu/ao-kernel/issues/196)
- aktif slice: [#195](https://github.com/Halildeu/ao-kernel/issues/195)
- canlı envanter: [`WP-5.1-GOVERNANCE-INVENTORY.md`](./WP-5.1-GOVERNANCE-INVENTORY.md)
- repo-side governance SSOT: [`.github/REPO-GOVERNANCE.md`](../../.github/REPO-GOVERNANCE.md)

**Adım sırası**
1. `[x]` Repo içinden zorunlu check isimlerini ve merge protokolünü netleştir.
2. `[x]` GitHub settings tarafında repo dışı kalan kontroller için yazılı checklist üret.
3. `[x]` `.github/CODEOWNERS` eklendi; code-owner enforcement önkoşulu yazılı hale getirildi.
4. `[x]` `main` release gate'inin hangi kısmı repoda, hangi kısmı platform ayarında
   enforced bunu kalıcı governance dokümanına bağla.
5. `[ ]` GitHub branch protection ayarlarını hedef konfigürasyona çek (`WP-5.3`).

**Canlı snapshot**
- required check'ler şu an: `lint`, `test (3.11)`, `test (3.12)`,
  `test (3.13)`, `coverage`, `typecheck`
- `packaging-smoke` workflow'da blocking ama branch protection'da required değil
- `.github/CODEOWNERS` repo içinde var; platform enforcement için ikinci maintainer
  veya açık istisna kararı gerekiyor
- `dismiss_stale_reviews=false`
- `require_code_owner_reviews=false`
- `enforce_admins=false`

**Definition of Done**
- required checks listesi yazılı ve güncel
- code-owner review beklentisi repo içinde görünür
- admin bypass / stale review / strict merge için dış-ayar checklist'i mevcut
- normal geliştirici akışını bozmadan merge güvenliği artmış

## 6. Sonra

### `WP-6` — Worktree/Branch Safety Control Loop

**Amaç**
- merge'de kaybolma, stale worktree ile ilerleme, overlap fark etmeme
  problemlerini operasyona gömmek

**Hedef slice'lar**
1. `ops preflight`
2. `ops overlap-check`
3. `ops close-worktree`
4. `ops archive-worktree`

### `WP-7` — Path-Scoped Write Ownership

**Amaç**
- mevcut claim/fencing altyapısını path-grubu ownership seviyesine taşımak

**Hedef slice'lar**
1. ownership model ve resource namespace kararı
2. claim / release / takeover / handoff kaydı
3. executor veya orchestration girişinde write ownership enforcement

## 7. En Son

### `WP-8` — Real Adapter Certification

**Amaç**
- stub-demodan çıkıp gerçek adapter yüzeyini kanıtlı hale getirmek

**Minimum kabul**
- en az 2 gerçek adapter
- timeout / cancel / retry / idempotency / secret handling / audit completeness
- production-tier smoke + failure-mode testleri

### `WP-9` — Operations / Runbook / Incident Readiness

**Amaç**
- ürünün sadece çalışması değil, işletilebilir olması

**Minimum kabul**
- incident runbook
- rollback yolu
- upgrade notes
- support boundary
- non-empty known bugs registry

## 8. Anlık Öncelik

Bugünden itibaren doğru sıra:

1. `WP-5` Release governance hardening
2. `WP-6` Worktree/branch safety control loop
3. `WP-7` Path-scoped write ownership
4. `WP-8` Real adapter certification
5. `WP-9` Ops/runbook/incident readiness

## 9. Güncelleme Protokolü

Her merge sonrası bu dosyada en az şu alanlar güncellenecek:

- aktif WP
- tamamlanan WP'nin durumu
- kanıt referansı
- yeni risk veya deferred notu
- sıradaki tek aktif hat
