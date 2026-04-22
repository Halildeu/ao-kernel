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
- `WP-5` repo-side governance closure ve güvenli branch-protection tightening
  uygulanmıştır; `enforce_admins` kişisel repo + tek maintainer kısıtı nedeniyle
  bilinçli olarak deferred kalır.
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
| `WP-5` Release governance hardening | Faz 3 | Completed on `main` | branch protection / required checks / CODEOWNERS / merge gate sertliği | PR #202 + branch protection snapshot |
| `WP-6` Worktree/branch safety control loop | Faz 3 | Completed on `main` | stale base / overlap / dirty worktree riskini operasyonel kapatmak | ops komutları + usage proof |
| `WP-7` Path-scoped write ownership | Faz 3 | **Active** ([#198](https://github.com/Halildeu/ao-kernel/issues/198)) | aynı path alanına iki aktif writer çakışmasın | ownership tests + takeover audit |
| `WP-8` Real adapter certification | Faz 4 | Planned ([#199](https://github.com/Halildeu/ao-kernel/issues/199)) | en az 2 gerçek adapter prod-tier smoke ve failure-mode testlerinden geçsin | capability matrix + smoke logs |
| `WP-9` Ops/runbook/incident readiness | Faz 4 | Planned ([#200](https://github.com/Halildeu/ao-kernel/issues/200)) | rollback / incident / support boundary / known bugs paketi | runbook + drill evidence |

## 5. Şimdi

### `WP-7` — Path-Scoped Write Ownership

**Neden şimdi**
- Worktree/branch safety hattı kapandı. Bundan sonraki ana değişim riski,
  aynı logical path alanına iki writer'ın sessizce girmesi.

**GitHub takip**
- üst issue: [#198](https://github.com/Halildeu/ao-kernel/issues/198)
- son merge: `WP-7.3 slice 1` / PR #209
- aktif slice: [`WP-7.3-EXECUTOR-ENFORCEMENT.md`](./WP-7.3-EXECUTOR-ENFORCEMENT.md)

**Adım sırası**
1. `[x]` `WP-7.1` path resource namespace kararı + acquire/release helper'ları
2. `[x]` `WP-7.2` claim visibility (`coordination status`) yüzeyi
3. `[~]` `WP-7.3` patch apply / patch rollback write-ownership enforcement
4. `[ ]` handoff / takeover ergonomics ve daha geniş orchestration entry coverage

**Canlı snapshot**
- `patch_apply` artık coordination enabled workspace'te preview edilen
  `files_changed` üstünden path-scoped write claim alıyor
- claim scope top-level area üstünden belirlenir (`src/*` -> tek claim alanı)
- claim acquire/release event'leri workflow evidence akışına bağlanır
- conflict path'i deterministic `_StepFailed(code=WRITE_OWNERSHIP_CONFLICT)`
  olarak yüzeye çıkar
- aktif alt slice aynı kontratı `patch_rollback` yoluna genişletir
- read-only preview/status yüzeyleri unchanged

**Definition of Done**
- coordination enabled patch apply ve patch rollback yolları claim
  acquire/release ile çalışıyor
- conflict aynı path alanında deterministic fail üretiyor
- dormant coordination semantics korunuyor
- yeni davranış behavior-first testlerle pinleniyor
- docs/runtime/story aynı şeyi söylüyor

## 6. Sonra

### `WP-8` — Real Adapter Certification

**Amaç**
- stub-demodan çıkıp gerçek adapter yüzeyini kanıtlı hale getirmek

## 7. En Son

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

1. `WP-7` Path-scoped write ownership
2. `WP-8` Real adapter certification
3. `WP-9` Ops/runbook/incident readiness

## 9. Güncelleme Protokolü

Her merge sonrası bu dosyada en az şu alanlar güncellenecek:

- aktif WP
- tamamlanan WP'nin durumu
- kanıt referansı
- yeni risk veya deferred notu
- sıradaki tek aktif hat
