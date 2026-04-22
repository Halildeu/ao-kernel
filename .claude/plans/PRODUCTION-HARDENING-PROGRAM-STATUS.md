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
| `WP-7` Path-scoped write ownership | Faz 3 | Completed on `main` | aynı path alanına iki aktif writer çakışmasın | ownership tests + takeover audit |
| `WP-8` Real adapter certification | Faz 4 | Completed on `main` ([#199](https://github.com/Halildeu/ao-kernel/issues/199)) | helper-backed real-adapter smoke/failure-mode baseline + capability matrix hizası | smoke logs + support matrix |
| `WP-9` Ops/runbook/incident readiness | Faz 4 | Completed on `main` ([#200](https://github.com/Halildeu/ao-kernel/issues/200)) | rollback / incident / support boundary / known bugs paketi | PR #217 + runbook package |

## 5. Şimdi

### Production Hardening Program Closeout

**Durum**
- `WP-5` ile `WP-9` arası program hattı `main` üzerinde tamamlandı.
- Son kapanış slice'ı `WP-9` / PR #217 ile merge edildi; issue `#200` kapandı.
- Bu dosya içinde artık aktif bir WP yok; sonraki iş ayrı bir tracker / issue
  ve net DoD ile başlatılmalıdır.

**GitHub takip**
- tracker issue: [#201](https://github.com/Halildeu/ao-kernel/issues/201)
- son merge: `WP-9` / PR #217
- son slice: [`WP-9-OPS-RUNBOOK-INCIDENT-READINESS.md`](./WP-9-OPS-RUNBOOK-INCIDENT-READINESS.md)

**Program çıktısı**
1. truth parity tamamlandı
2. policy command enforcement canlıya bağlandı
3. packaging smoke blocking gate oldu
4. governance / worktree / ownership güvenlik hatları eklendi
5. ops / rollback / upgrade / known-bugs paketi repo SSOT'una bağlandı

**Canlı snapshot**
- repo bugün dar ama kanıtlı bir governed runtime / Public Beta yüzeyine sahiptir
- support boundary, runbook, rollback, upgrade ve known-bugs belgeleri canlıdır
- genel amaçlı production platform genişlemesi bu programın dışında kalır

**Closeout Kriteri**
- bu program içinde aktif WP kalmaz
- status SSOT ile GitHub tracker aynı gerçeği söyler
- bundan sonraki iş yeni bir backlog hattı olarak başlatılır

## 8. Anlık Öncelik

Bugünden itibaren bu program için doğru durum:

1. `WP-5` ile `WP-9` tamamlandı
2. yeni aktif iş açılacaksa bu dosya yerine yeni issue / slice ile başlatılmalı

## 9. Güncelleme Protokolü

Her merge sonrası bu dosyada en az şu alanlar güncellenecek:

- aktif WP
- tamamlanan WP'nin durumu
- kanıt referansı
- yeni risk veya deferred notu
- sıradaki tek aktif hat
