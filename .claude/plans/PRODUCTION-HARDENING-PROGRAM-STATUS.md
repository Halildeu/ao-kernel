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
| `WP-8` Real adapter certification | Faz 4 | **Active** ([#199](https://github.com/Halildeu/ao-kernel/issues/199)) | en az 2 gerçek adapter prod-tier smoke ve failure-mode testlerinden geçsin | capability matrix + smoke logs |
| `WP-9` Ops/runbook/incident readiness | Faz 4 | Planned ([#200](https://github.com/Halildeu/ao-kernel/issues/200)) | rollback / incident / support boundary / known bugs paketi | runbook + drill evidence |

## 5. Şimdi

### `WP-8` — Real Adapter Certification

**Neden şimdi**
- `WP-7` ile change-safety hattı kapandı. Bundan sonraki ana eksik, gerçek
  adapter yüzeyinin stub baseline'dan ayrışmış kanıtla sertifiye edilmemiş
  olması.

**GitHub takip**
- üst issue: [#199](https://github.com/Halildeu/ao-kernel/issues/199)
- son merge: `WP-8.3` / PR #215
- aktif slice: [`WP-8.4-CAPABILITY-MATRIX-ALIGNMENT.md`](./WP-8.4-CAPABILITY-MATRIX-ALIGNMENT.md)

**Adım sırası**
1. `[x]` `WP-8.1` certification baseline + candidate matrix
2. `[x]` `WP-8.2` `claude-code-cli` smoke + failure-mode baseline
3. `[x]` `WP-8.3` `gh-cli-pr` side-effect-safe preflight baseline
4. `[~]` `WP-8.4` public capability/support matrix hizası

**Canlı snapshot**
- bundled gerçek-adapter aday seti `claude-code-cli` + `gh-cli-pr`
  olarak netleşti
- `codex-stub` sertifikasyon dışı deterministic baseline olarak kalıyor
- gerçek-adapter CI hâlâ otomatik release gate değildir; mevcut yüzey
  operator-managed durumdadır
- aktif alt slice için `python3 scripts/claude_code_cli_smoke.py`
  helper'ı eklendi; smoke + manifest contract testleri yeşil
- aktif alt slice için `python3 scripts/gh_cli_pr_smoke.py`
  helper'ı eklendi; `gh` binary + auth + repo visibility + safe
  `gh pr create --dry-run` preflight'ı tek komutta toplandı
- `WP-8.3` PR #215 ile merge edildi; canlı `gh_cli_pr_smoke` + tam CI turu
  yeşil geçti
- repo tarafındaki `manifest_cli_contract_mismatch` kapatıldı
- aynı canlı turda önce `claude auth status` yeşil olsa da `claude -p`
  org-level access hatasıyla düştü; kontrollü re-login sonrası helper tam
  `pass` verdi ve doğrudan `claude -p` smoke'u `ok` döndürdü
- `setup-token` altında üretilen uzun ömürlü token ise bu turda güvenilir
  kurtarma yolu olarak doğrulanmadı; ayrıca `Invalid bearer token` reddi
  görüldü
- `claude-code-cli` lane'i bugün **Beta (operator-managed)** olarak
  hizalanacak: helper-backed preflight ve canlı prompt smoke var, ancak
  default shipped demo değildir
- `gh-cli-pr` lane'i bugün **Beta (operator-managed preflight only)** olarak
  hizalanacak: helper-backed dry-run smoke var, ancak gerçek remote PR açılışı
  hâlâ deferred kalır

**Definition of Done**
- bundled gerçek-adapter aday seti explicit
- her aday için smoke + failure-mode + evidence gereksinimi yazılı
- stub baseline ile gerçek adapter yüzeyi net ayrışmış
- public support boundary yanlış genişletilmemiş

## 6. Sonra

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

1. `WP-8` Real adapter certification
2. `WP-9` Ops/runbook/incident readiness

## 9. Güncelleme Protokolü

Her merge sonrası bu dosyada en az şu alanlar güncellenecek:

- aktif WP
- tamamlanan WP'nin durumu
- kanıt referansı
- yeni risk veya deferred notu
- sıradaki tek aktif hat
