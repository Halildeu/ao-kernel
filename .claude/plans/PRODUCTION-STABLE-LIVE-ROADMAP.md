# Production Stable Live Roadmap

**Durum tarihi:** 2026-04-24
**Rol:** Public Beta / post-beta correctness hattindan production stable live
release'e gecis icin takip edilebilir program kontrati.
**Sonuç:** `v4.0.0` stable runtime baseline live on PyPI.
**Kapsam mottosu:** once gercegi kilitle, sonra support'u genislet.

## 1. Hedef

Bu roadmap'in hedefi `ao-kernel` icin "canli stable production" kararini
kanita baglamaktir. Stable release, sadece surum numarasi degildir; asagidaki
bes seyin ayni anda dogru oldugu release'tir:

1. `pip install ao-kernel` ile gelen stable paket gercek desteklenen yuzeyi
   kurar.
2. Runtime, docs, tests, CI ve runbook ayni support boundary'yi anlatir.
3. Wheel-installed smoke repo kokune, editable install'a veya host PATH
   tesaduflerine dayanmaz.
4. Shipped iddialar negative/positive behavior testleriyle kanitlidir.
5. Operator, hata aninda rollback/incident/known-bug yolunu bilir.

## 2. Stable Claim Seviyeleri

Iki farkli hedef birbirine karistirilmeyecek:

| Seviye | Anlam | Stable icin durum |
|---|---|---|
| Stable runtime release | Dar support boundary ile guvenilir, paketlenmis, isletilebilir cekirdek | `v4.0.0` ile live |
| General-purpose production coding automation platform | Gercek adapter'lar, live-write E2E, multi-agent safety ve operator runbook'lariyla genis platform | Ancak sertifikasyon kapilari kapandiktan sonra iddia edilir |

`4.0.0` stable release dar ama dogru bir production runtime olarak live'dir.
"Genel amacli production coding automation platform" iddiasi, gercek adapter
sertifikasyonu ve live-write rollback kanitlari kapanmadan kullanilmayacak.

## 3. Mevcut Baseline

- `main` temiz ve `origin/main` ile senkron.
- Public tag `v4.0.0` mevcut; PyPI exact pin `ao-kernel==4.0.0` ve bare
  stable install `pip install ao-kernel` fresh venv ile doğrulandı.
- GitHub Release `v4.0.0` latest release olarak yayımlandı.
- `ST-1` release PR package metadata hedefi `4.0.0b2` idi ve tamamlandi.
- Public tag `v4.0.0-beta.2` mevcut; PyPI exact pin
  `ao-kernel==4.0.0b2` fresh venv ile dogrulandi.
- Public Beta support boundary dar: `review_ai_flow + codex-stub`,
  entrypoint'ler, doctor, policy command enforcement ve wheel smoke kanitli
  cekirdek shipped yuzeydir.
- `claude-code-cli`, `gh-cli-pr` ve write/live hatlari operator-managed beta
  veya karar bekleyen yuzeylerdir.
- Post-beta programda GP-2 hattinda deferred support lane'leri kanitla
  kapatiliyor.

## 4. Closed Drift Kayitlari

Stable roadmap boyunca şu drift'ler kapatıldı veya karar notuna bağlandı:

1. `docs/PUBLIC-BETA.md` stable kanal dili `v4.0.0` live sonucuna çekildi.
2. `.claude/plans/POST-BETA-CORRECTNESS-EXPANSION-STATUS.md` icinde GP-2.2b
   issue/status satirlari merge sonrasi gercekle hizalanacak.
3. Adapter-path `cost_usd` reconcile icin "runtime fix gerekir mi, yoksa
   evidence/test/docs closeout yeterli mi" karari GP-2.2d'de kapanacak.
4. `v4.0.0-beta.1` tag'i main'in gerisinde kaldigi icin stable release eski
   tag üzerinden değil current `main` üzerinden çıktı.

## 5. Release Stratejisi

Stable'a dogrudan ziplanmadi. Tamamlanan yol:

1. `4.0.0b2` pre-release cikti ve fresh install / wheel / docs / smoke /
   runbook kanitlari toplandi.
2. `ST-2` stable support boundary freeze tamamlandi.
3. `ST-5` ve `ST-6` ile deferred correctness ve operations readiness kapandı.
4. `ST-7` source candidate merge edildi.
5. `ST-8` ile `v4.0.0` tag, PyPI publish ve public install verify tamamlandı.

Stable release takvim kararı değil gate kararıydı; gate'ler geçtikten sonra
canlıya alındı.

## 6. Work Packages

### ST-0 — Beta Sync ve Status Truth Closeout

**Durum:** Completed on `main` via PR [#338](https://github.com/Halildeu/ao-kernel/pull/338)
and GP-2.2 closeout verdict.

**Amac:** Current `main` ile public beta/live dokumanlari arasindaki drift'i
kapatmak.

**Kapsam:**

- GP-2.2 status/issue satirlarini merge sonrasi gercege cek.
- `docs/PUBLIC-BETA.md`, `docs/SUPPORT-BOUNDARY.md`,
  `docs/KNOWN-BUGS.md` ve status dosyalarinda stable/beta/deferred dilini
  hizala.
- Stable kanal surumunu hard-code etmek yerine install kuralini yaz.

**DoD:**

- Support matrix'te stale issue/surum/status yok.
- GP-2.2d closeout karari yazili.
- Public Beta dokumani current `main` gercegini anlatiyor.

### ST-1 — Releasable Pre-Release Gate (`4.0.0b2`)

**Durum:** Completed on `main` via [#340](https://github.com/Halildeu/ao-kernel/issues/340),
contract PR [#341](https://github.com/Halildeu/ao-kernel/pull/341), release PR
[#342](https://github.com/Halildeu/ao-kernel/pull/342), tag
`v4.0.0-beta.2`, and publish workflow `24863200216`.

**Amac:** Current `main`'i eski `v4.0.0-beta.1` tag'inden ayrilmis yeni bir
kanitli pre-release'e cevirmek.

**Kapsam:**

- Version bump `4.0.0b2`.
- Changelog/release note: `v4.0.0-beta.1` sonrasi kapanan governance,
  support-boundary, evidence ve adapter kararlarini ozetle.
- CI + packaging smoke + publish workflow dry-run/publish gate.

**DoD:**

- Fresh venv, repo disi cwd, wheel install smoke gecti.
- `ao-kernel version`, `python -m ao_kernel version`,
  `python -m ao_kernel.cli version` ayni pre-release surumunu verdi.
- `python3 examples/demo_review.py --cleanup` installed package yuzeyiyle
  `completed` oldu.
- PyPI pre-release verify tamamlandi.

### ST-2 — Stable Support Boundary Freeze

**Durum:** Completed via
[#346](https://github.com/Halildeu/ao-kernel/pull/346) and
`.claude/plans/ST-2-STABLE-SUPPORT-BOUNDARY-FREEZE.md`.

**Amac:** `4.0.0` stable'in neyi destekledigini release oncesi dondurmek.

**Kapsam:**

- Shipped / Beta / Deferred / Known Bugs matrisi final review.
- Her shipped satir icin kod yolu + test/smoke + docs kaniti.
- Her beta/deferred satir icin neden stable scope disinda kaldigi.

**DoD:**

- Stable release notes "genel amacli her seyi yapar" iddiasi tasimiyor.
- Known bug listesinde shipped baseline'i bozan blocker yok.
- Beta operator-managed yuzeyler stable iddianin icine sizmiyor.

### ST-3 — Real Adapter Certification Decision

**Durum:** Parked for support widening. Post-stable first certification
contract is tracked by `GP-2.4`
([#363](https://github.com/Halildeu/ao-kernel/issues/363)); the active
candidate is `claude-code-cli` read-only.
Not a blocker for the narrow stable runtime release because real-adapter lanes
are not stable shipped claims after `ST-2`.

**Amac:** Gercek adapter yuzeylerinin stable scope'a girip girmeyecegini
kanıtla karara baglamak.

**Adaylar:**

- `claude-code-cli`: PATH binary + operator auth/prerequisite lane.
- `gh-cli-pr`: PATH binary + GitHub CLI auth/preflight/live-write lane.
- `codex-stub`: repo-native deterministic stub, production adapter degil.

**DoD:**

- Her adapter icin capability tier: `stub`, `preflight`, `operator-managed
  beta`, `production-certified`.
- Production-certified denilen adapter icin timeout/cancel/retry,
  idempotency, secret handling, evidence completeness ve failure-mode smoke
  mevcut.
- Production-certified adapter yoksa stable claim dar runtime olarak kalir.

### ST-4 — Live Write ve Rollback Rehearsal

**Durum:** Parked for support widening. Not a blocker for the narrow stable
runtime release because live-write / remote side-effect surfaces are not stable
shipped claims after `ST-2`.

**Amac:** Canli yazma yapacak yuzeyler icin geri alma ve kanit kontratini
gercekte denemek.

**Kapsam:**

- Disposable sandbox repo veya controlled test target.
- Live-write create/verify/rollback akisi.
- Idempotent cleanup.
- Evidence JSONL ve operator runbook kaydi.

**DoD:**

- Live-write iddiasi olan her yuzey icin rollback kaniti var.
- Rollback yoksa yuzey stable write scope'a alinmaz.

### ST-5 — Deferred Correctness Closure

**Durum:** Completed via
[#350](https://github.com/Halildeu/ao-kernel/pull/350) and
`.claude/plans/ST-5-DEFERRED-CORRECTNESS-CLOSURE.md`.

**Amac:** Stable shipped yuzeyi etkileyen correctness borcunu kapatmak veya
bilerek stable disina almak.

**Kapsam adaylari:**

- `bug_fix_flow` release closure.
- `gh-cli-pr` full E2E remote PR opening.
- Roadmap/spec demo yuzeyinin live support'a alinip alinmayacagi.
- Adapter-path `cost_usd` reconcile son karari.

**DoD:**

- Her item `ship`, `beta`, `deferred` veya `retire` olarak tek kategoriye
  duser.
- Iki kategoriye birden yazilan yuzey kalmaz.

### ST-6 — Operations Readiness

**Durum:** Completed on `main` via
[#353](https://github.com/Halildeu/ao-kernel/pull/353) and
`.claude/plans/ST-6-OPERATIONS-READINESS.md`.

**Amac:** Stable release'i isletilebilir hale getirmek.

**Kapsam:**

- Incident runbook.
- Rollback/upgrade notes.
- Support boundary.
- Known bugs registry.
- Required checks ve branch protection uyumu.

**DoD:**

- Operator "kurulum bozuldu", "adapter auth bozuk", "policy deny beklenmiyor",
  "publish hatali" durumlarinda hangi komutu kosacagini biliyor.
- Publish sonrasi verify komutlari yazili.
- Emergency rollback ve yanked release karari yazili.

### ST-7 — Stable Release Candidate

**Durum:** Completed on `main` via
[#355](https://github.com/Halildeu/ao-kernel/issues/355), contract PR
[#356](https://github.com/Halildeu/ao-kernel/pull/356), implementation PR
[#357](https://github.com/Halildeu/ao-kernel/pull/357), and
`.claude/plans/ST-7-STABLE-RELEASE-CANDIDATE.md`.

**Amac:** `4.0.0` stable icin final aday cikarmak.

**Kapsam:**

- Version `4.0.0`.
- Changelog final.
- Docs'ta beta/pre-release install dilini stable release diline ayir.
- Full CI, packaging smoke, installed demo, doctor, adapter smokes.

**DoD:**

- `pip install ao-kernel==4.0.0` icin publish-oncesi wheel smoke ayni
  kontrati geciyor.
- `--pre` gerektiren kurulum stable docs'ta stable yol gibi anlatilmiyor.
- Release blocker listesi bos.

### ST-8 — Stable Publish ve Post-Publish Verification

**Durum:** Completed via [#358](https://github.com/Halildeu/ao-kernel/issues/358),
tag `v4.0.0`, publish workflow
[`24866683491`](https://github.com/Halildeu/ao-kernel/actions/runs/24866683491),
GitHub Release [`v4.0.0`](https://github.com/Halildeu/ao-kernel/releases/tag/v4.0.0),
and `.claude/plans/ST-8-STABLE-PUBLISH-AND-POST-PUBLISH-VERIFICATION.md`.

**Amac:** Stable'i canliya almak ve public install gercegini dogrulamak.

**Kapsam:**

- Tag: `v4.0.0`.
- Publish workflow success.
- PyPI HTTP/JSON verify.
- Fresh venv public install verify.
- Post-release issue/status closeout.

**DoD:**

- `pip install ao-kernel` stable kanaldan `4.0.0` kuruyor.
- Fresh venv smoke public paketle geciyor.
- GitHub release, CHANGELOG, docs ve status ayni sonucu anlatiyor.

## 7. Stable Release Blocker Listesi

Asagidaki durumlardan biri varsa stable publish yapilmaz:

- Docs/runtime/test/CI ayni support boundary'yi anlatmiyor.
- Wheel-installed smoke repo kokune veya editable install'a bagimli.
- Shipped yuzeyde bilinen blocker known bug var.
- Policy/security enforcement icin negative test yok.
- Adapter production claim'i sadece manifest veya docs'a dayaniyor.
- Live-write yuzeyi rollback rehearsali olmadan stable scope'a alinmis.
- `docs/PUBLIC-BETA.md` veya `docs/SUPPORT-BOUNDARY.md` stale surum/status
  bilgisi tasiyor.
- `main` ile release branch/tag arasinda aciklanmamis fark var.

## 8. Zorunlu Kanit Paketi

Stable kararindan once en az su komutlar gecmis olacak:

```bash
python3 -m pytest -q tests/ --ignore=tests/benchmarks --cov
python3 -m pytest -q tests/benchmarks/test_governed_review.py tests/benchmarks/test_governed_bugfix.py
python3 scripts/packaging_smoke.py
python3 scripts/truth_inventory_ratchet.py --output json
python3 examples/demo_review.py --cleanup
python3 -m ao_kernel doctor
```

Release branch uzerinde ek olarak fresh temp venv + wheel install smoke
zorunludur. Public publish sonrasinda ayni kontrat PyPI paketinden tekrar
dogrulanir.

## 9. Yurutme Kurali

- Ayni anda en fazla bir `ST-*` implementation slice acik olur.
- Her slice icin issue veya status entry acilir.
- Her PR su paketle kapanir: kod/doc degisikligi, test/smoke kaniti,
  changelog etkisi, kalan deferred maddeler.
- Support boundary genisletme PR'i, onu kanitlayan runtime/test PR'ina
  baglanmadan merge edilmez.
- Stable release karari tek kisi kanaatiyle degil, bu dosyadaki blocker ve DoD
  listesinin kapanmasiyla verilir.

## 10. Hemen Siradaki Is

1. `ST-0` tamamlandi: GP-2.2 closeout ve status/docs drift temizligi.
2. `ST-1` tamamlandi: current `main` icin `4.0.0b2` pre-release publish ve
   PyPI exact pin verify.
3. `ST-2`, `ST-5`, `ST-6`, `ST-7` ve `ST-8` tamamlandi; `v4.0.0` stable live.
4. `GP-2.3` tamamlandı: post-stable ilk giriş kapısı
   `claude-code-cli` read-only certification olarak seçildi.
5. Aktif post-stable contract hattı `GP-2.4`:
   `.claude/plans/GP-2.4-CLAUDE-CODE-CLI-READ-ONLY-CERTIFICATION.md`
6. Varsayılan sıra:
   - `Now`: `GP-2.4` `claude-code-cli` read-only certification contract
   - `Next`: `gh-cli-pr` live-write rollback rehearsal
   - `Later`: extension/support widening
7. Bu roadmap stable runtime release'i tamamlanmış sayar; genel amaçlı
   production platform claim'i için `GP-2.4` certification ve sonraki rollback
   kanıtları gerekir.
