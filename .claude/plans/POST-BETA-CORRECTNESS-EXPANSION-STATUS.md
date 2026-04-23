# Post-Beta Correctness and Expansion Status

**Durum tarihi:** 2026-04-23
**Amaç:** Public Beta closeout sonrasında kalan correctness debt'ini
fail-closed disiplinle kapatmak, support-surface widening kararlarını kanıtla
yönetmek ve genel amaçlı production çizgisine geçiş için gerçek gap'leri
ayrı ayrı görünür kılmak.
**Yürütme modu:** Kapsam disiplini
**Bu dosyanın rolü:** yaşayan execution backlog + program status SSOT

## 1. SSOT Sınırları

- **Execution status / backlog:** bu dosya
- **Tarihsel closeout snapshot:** `.claude/plans/PRODUCTION-HARDENING-PROGRAM-STATUS.md`
- **Son tamamlanan implementation contract:** `.claude/plans/PB-8.3-BUG-FIX-FLOW-RELEASE-CLOSURE-PROMOTION.md`
- **Son extension decision record:** `.claude/plans/PB-6.3-CONTEXT-ORCHESTRATION-DECISION.md`
- **Program roadmap:** `.claude/plans/PB-8-GENERAL-PURPOSE-PRODUCTIONIZATION-ROADMAP.md`
- **Aktif decision/ordering contract:** `.claude/plans/PB-8-GENERAL-PURPOSE-PRODUCTIONIZATION-ROADMAP.md` (`PB-8` closeout tamam; `PB-9` kickoff pending)
- **Public Beta support boundary:** `docs/PUBLIC-BETA.md`
- **Known bugs registry:** `docs/KNOWN-BUGS.md`
- **GitHub milestone:** [Post-Beta Correctness and Expansion](https://github.com/Halildeu/ao-kernel/milestone/2)
- **GitHub tracker issue:** [#219](https://github.com/Halildeu/ao-kernel/issues/219)
- **PB-6 umbrella issue:** [#243](https://github.com/Halildeu/ao-kernel/issues/243)
- **PB-8 tracker issue:** [#288](https://github.com/Halildeu/ao-kernel/issues/288)
- **Aktif issue:** yok (`PB-8` closeout sonrası `PB-9` kickoff issue'su açılacak)

## 2. Başlangıç Gerçeği

- `WP-5` ile `WP-9` production hardening programı `main` üzerinde kapanmıştır.
- Repo bugün dar ama kanıtlı bir Public Beta / governed runtime yüzeyine sahiptir.
- Support boundary hâlâ bilerek dardır; `review_ai_flow + codex-stub` shipped
  baseline, gerçek adapter lane'leri ise operator-managed beta durumundadır.
- Public Beta closeout sonrası `PB-8.4` docs/runbook/release-gate parity
  tranche'i tamamlandı; bir sonraki aktif hat `PB-9` kickoff planlamasıdır.
- Repo bugün hâlâ genel amaçlı production coding automation platformu değildir;
  bu programın amacı o iddiayı hemen widen etmek değil, önce kalan debt'i
  kontrollü kapatmaktır.

## 3. Yürütme Kuralları

1. Aynı anda en fazla `1 ana runtime slice` açık olur.
2. Her slice tek branch, tek PR, tek net kabul kriteri ile yürür.
3. Support boundary, code path + davranışsal test/smoke + CI + doc birlikte
   mevcutsa genişletilir; hiçbir tekil kanıt yeterli sayılmaz.
4. Runtime semantics değiştiren slice merge olmadan bir sonraki runtime slice
   başlamaz.
5. Her slice kapanışında zorunlu kayıt:
   - status güncellemesi
   - issue / PR referansı
   - test kanıtı
   - smoke kanıtı gerekiyorsa onun çıktısı
   - kalan deferred notları

## 4. Program Tahtası

| Slice | Durum | Hedef | Zorunlu kanıt |
|---|---|---|---|
| `PB-1` Deferred correctness pack 1 | Completed on `main` ([#220](https://github.com/Halildeu/ao-kernel/issues/220)) | `sanitize.py`, `compiler.py`, `init_cmd.py` correctness boşluklarının zaten kapanmış olduğunu backfill doğrulamak | targeted tests on `main` + status correction |
| `PB-2` `bug_fix_flow + codex-stub patch_preview` closure | Completed on `main` ([#222](https://github.com/Halildeu/ao-kernel/issues/222), [#224](https://github.com/Halildeu/ao-kernel/pull/224)) | `open_pr` adımında PR metadata/evidence boşluğunu kapatmak ve deferred bugfix workflow yüzeyini deterministik integration coverage ile doğrulamak | merged runtime fix + integration tests + green CI |
| `PB-3` deterministic test hygiene / time seams | Completed on `main` ([#226](https://github.com/Halildeu/ao-kernel/issues/226), [#227](https://github.com/Halildeu/ao-kernel/pull/227), [#228](https://github.com/Halildeu/ao-kernel/pull/228), [#229](https://github.com/Halildeu/ao-kernel/pull/229), [#230](https://github.com/Halildeu/ao-kernel/pull/230), [#231](https://github.com/Halildeu/ao-kernel/pull/231)) | zaman-bağımlı test ve zayıf assertion drift'ini sistematik azaltmak | targeted suite proof + residual seam inventory |
| `PB-4` support-surface widening decisions | Completed on `main` ([#232](https://github.com/Halildeu/ao-kernel/issues/232), [#237](https://github.com/Halildeu/ao-kernel/pull/237)) | `gh-cli-pr` full E2E ve operator lane promotion kararlarını kanıtla vermek | canlı smoke + karar notu + docs parity |
| `PB-5` adapter-path cost/evidence completeness | Completed ([#238](https://github.com/Halildeu/ao-kernel/issues/238)) | `cost_usd` reconcile ve evidence completeness yüzeyinde ayrı runtime gap olup olmadığını karara bağlamak; sonuç: docs parity closeout yeterli, ayrı tranche 3 gerekmedi | truth audit + targeted tests + docs parity closeout |
| `PB-6` general-purpose expansion gap map | Completed on `main` ([#243](https://github.com/Halildeu/ao-kernel/issues/243), [#279](https://github.com/Halildeu/ao-kernel/pull/279)) | narrow beta'dan daha geniş production platform çizgisine geçiş için hangi yüzeylerin neden henüz promoted olmadığını canlı kanıtla sınıflandırmak | written gap map + ordered tranche backlog + PB-6.6 final verdict closeout |

## 5. Şimdi

### `PB-6.4` — real-adapter/write-side graduation criteria yeniden sıralama

`PB-6` içinde `PB-6.4` sıralama/karar alt hattı tamamlandı. Bu slice'ın işi,
genel amaçlı platform widening'i için real-adapter/write-side promotion
kriterlerini risk sırasına göre yeniden düzenlemek ve yalnız kanıtlı adayları
bir sonraki implementation hattına taşımaktır.

`PB-6.4` kickoff:

1. Issue: [#263](https://github.com/Halildeu/ao-kernel/issues/263)
2. Decision/ordering contract:
   `.claude/plans/PB-6.4-REAL-ADAPTER-WRITE-SIDE-GRADUATION-ORDER-CONTRACT.md`
3. Hedef: first/second/hold tranche sırasını yazılı kapıya çevirmek ve
   yalnız aktif tranche'ı net tutmak.

`PB-6.4a` implementation slice'ı tamamlandı:

1. Issue: [#265](https://github.com/Halildeu/ao-kernel/issues/265)
2. PR: [#266](https://github.com/Halildeu/ao-kernel/pull/266)
3. Merge commit: `b934fb65003dd0b3713fac982a066e8c252a92b8`
4. Sonuç: support mapping parity (`PUBLIC-BETA` + `SUPPORT-BOUNDARY`) ve
   `tests/test_doctor_cmd.py` doğrulamaları hizalandı.

`PB-6.4b` decision slice'ı tamamlandı:

1. Issue: [#267](https://github.com/Halildeu/ao-kernel/issues/267)
2. PR: [#268](https://github.com/Halildeu/ao-kernel/pull/268)
3. Karar: `promotion_candidate` (otomatik support widening yok)
4. Gerekçe: checklist kapıları geçildi, smoke tekrar edilebilir, known-bug
   etkisi operator-managed lane sınırında bounded kaldı.
5. Sınır: lane support tier'i ayrı widening slice açılana kadar
   `Beta (operator-managed)` olarak kalır.
6. Slice plan:
   `.claude/plans/PB-6.4b-CLAUDE-CODE-CLI-PROMOTION-READINESS.md`

`PB-6.4c` decision slice'ı tamamlandı:

1. Issue: [#271](https://github.com/Halildeu/ao-kernel/issues/271)
2. Karar: `stay_preflight`
3. Gerekçe: live write lane için sandbox/side-effect/rollback/evidence
   kapıları henüz karşılanmadı; preflight-only support sınırı korunuyor
4. Slice plan:
   `.claude/plans/PB-6.4c-GH-CLI-PR-LIVE-WRITE-GRADUATION.md`

`PB-6.4d` decision slice'ı tamamlandı:

1. Issue: [#270](https://github.com/Halildeu/ao-kernel/issues/270)
2. Karar: `stay_deferred`
3. Gerekçe: governance + behavior + safety + rollback kapıları write-side
   widening için karşılanmadı; docs parity tek başına widening açmadı
4. Slice plan:
   `.claude/plans/PB-6.4d-KERNEL-API-WRITE-SIDE-WIDENING-PRECONDITIONS.md`

`PB-6.5` decision closeout tamamlandı:

1. Issue: [#275](https://github.com/Halildeu/ao-kernel/issues/275)
2. Karar özeti:
   - `claude-code-cli`: `promotion_candidate_with_ops_gates`
   - `gh-cli-pr` preflight: `stay_beta_operator_managed`
   - `gh-cli-pr` live write: `stay_deferred`
   - `PRJ-KERNEL-API` write-side: `stay_deferred`
3. Slice plan:
   `.claude/plans/PB-6.5-OPS-READINESS-FOR-WIDENED-LANES.md`

`PB-6.6` decision closeout tamamlandı:

1. Issue: [#277](https://github.com/Halildeu/ao-kernel/issues/277)
2. Final verdict: `stay_beta_operator_managed`
3. Gerekçe özeti:
   - smoke repeatability var, fakat lane hâlâ operator-env bağımlı
   - `KB-001` ve `KB-002` bounded/open olarak kalıyor
   - support tier widening yerine narrow beta sınırı korunuyor
4. Slice plan:
   `.claude/plans/PB-6.6-CLAUDE-CODE-CLI-OPS-GATED-PROMOTION-CLOSEOUT.md`

`PB-6.2` contract slice'ı tamamlandı:

1. Issue: [#251](https://github.com/Halildeu/ao-kernel/issues/251)
2. PR: [#252](https://github.com/Halildeu/ao-kernel/pull/252)
3. Merge commit: `8401092d5feafde07b4b8b75833f002b9499fa8d`
4. Contract: `.claude/plans/PB-6.2-KERNEL-API-PROMOTION-CONTRACT.md`

`PB-6.2b` implementation slice'ı tamamlandı:

1. Issue: [#253](https://github.com/Halildeu/ao-kernel/issues/253)
2. PR: [#255](https://github.com/Halildeu/ao-kernel/pull/255)
3. Merge commit: `f979f4b8d652f71e726b1f69838f4372e6a7d638`
4. Support boundary yalnız `PRJ-KERNEL-API` `system_status` ve
   `doc_nav_check` action'ları için genişledi.
5. `project_status`, `roadmap_follow`, `roadmap_finish` deferred kaldı.

Güncel runtime baseline:

1. `python3 -m ao_kernel doctor`
   - `8 OK, 1 WARN, 0 FAIL`
   - `runtime_backed=2`, `contract_only=1`, `quarantined=16`
   - `remap_candidate_refs=61`, `missing_runtime_refs=152`
   - `runtime_backed_ids=PRJ-HELLO, PRJ-KERNEL-API`
   - `contract_only_ids=PRJ-CONTEXT-ORCHESTRATION`
2. `python3 scripts/claude_code_cli_smoke.py --output json`
   - `overall_status="pass"`
3. `python3 scripts/gh_cli_pr_smoke.py --output json`
   - `overall_status="pass"`

`PB-6.3` decision slice'ı tamamlandı:

1. Issue: [#256](https://github.com/Halildeu/ao-kernel/issues/256)
2. PR: [#258](https://github.com/Halildeu/ao-kernel/pull/258)
3. Merge commit: `1b4991817618445526552ae39cae0b72d140ac17`
4. Decision record:
   `.claude/plans/PB-6.3-CONTEXT-ORCHESTRATION-DECISION.md`

`PB-6.3` karar sonucu:

1. `PRJ-CONTEXT-ORCHESTRATION` `remap-needed` later candidate olarak kalır.
2. Bu slice runtime behavior değiştirmez ve support boundary genişletmez.
3. `PB-6.3` karar anındaki snapshot'ta extension
   `truth_tier=quarantined`,
   `runtime_handler_registered=False`, `remap_candidate_refs=5`,
   `missing_runtime_refs=4` durumundadır.
4. Canlı runtime owner sinyali `ao_kernel.context` paketidir; fakat extension
   handler owner henüz yoktur.
5. Gelecek runtime promotion ancak
   `ao_kernel/extensions/handlers/prj_context_orchestration.py` gibi explicit
   bir handler, dar `kernel_api_actions`, behavior-first tests ve docs parity
   ile yapılabilir.
6. `PB-6.3b` manifest cleanup sonrası extension truth
   `contract_only` katmanına çekilmiş ve runtime handler register edilmemiştir.

`PB-6.3b` completion:

1. `PB-6.3b` issue: [#259](https://github.com/Halildeu/ao-kernel/issues/259)
2. `PB-6.3b` PR: [#261](https://github.com/Halildeu/ao-kernel/pull/261)
3. Merge commit: `08a3a95`
4. Legacy top-level refs temizlenmiş, package-local `defaults/...` refs
   korunmuş, missing packaged refs kaldırılmıştır.
5. `future_handler_contract` sınırı manifestte explicit yazılmıştır.
6. Scope guard korunmuştur: runtime handler registration ayrı slice'tadır.

## 6. Sonra

`PB-6` açıldıktan sonraki doğru sıra:

1. `PB-6.2b` `PRJ-KERNEL-API` minimum runtime-backed implementation
   - completed on `main` via [#255](https://github.com/Halildeu/ao-kernel/pull/255)
2. `PB-6.3` `PRJ-CONTEXT-ORCHESTRATION` remap/owner decision
   - completed on `main` via [#258](https://github.com/Halildeu/ao-kernel/pull/258)
   - decision: `remap-needed`, keep non-shipped until contract cleanup
3. `PB-6.3b` `PRJ-CONTEXT-ORCHESTRATION` manifest/contract cleanup
   - completed on `main` via [#261](https://github.com/Halildeu/ao-kernel/pull/261)
   - outcome: `truth_tier=contract_only`, no runtime handler registration
4. `PB-6.4` real-adapter/write-side graduation criteria yeniden sıralama
   - completed (ordering + second decision tranche)
   - issue: [#263](https://github.com/Halildeu/ao-kernel/issues/263)
   - contract:
     `.claude/plans/PB-6.4-REAL-ADAPTER-WRITE-SIDE-GRADUATION-ORDER-CONTRACT.md`
   - first tranche complete: `PB-6.4a` ([#265](https://github.com/Halildeu/ao-kernel/issues/265), [#266](https://github.com/Halildeu/ao-kernel/pull/266))
   - second tranche complete: `PB-6.4b` ([#267](https://github.com/Halildeu/ao-kernel/issues/267), [#268](https://github.com/Halildeu/ao-kernel/pull/268))
   - third tranche complete: `PB-6.4c` decision closeout (`stay_preflight`, [#271](https://github.com/Halildeu/ao-kernel/issues/271))
   - fourth tranche complete: `PB-6.4d` decision closeout (`stay_deferred`, [#270](https://github.com/Halildeu/ao-kernel/issues/270))
5. `PB-6.5` ops readiness gates
   - completed decision closeout (issue: [#275](https://github.com/Halildeu/ao-kernel/issues/275))
   - plan:
     `.claude/plans/PB-6.5-OPS-READINESS-FOR-WIDENED-LANES.md`
6. `PB-6.6` claude-code-cli lane ops-gated promotion closeout
   - completed decision closeout (issue: [#277](https://github.com/Halildeu/ao-kernel/issues/277))
   - plan:
     `.claude/plans/PB-6.6-CLAUDE-CODE-CLI-OPS-GATED-PROMOTION-CLOSEOUT.md`

Not:

1. `PB-6.2` planning slice'ı support boundary'yi değiştirmedi; yalnız
   implementation PR için contract çıkardı.
2. `PB-6.2b` support boundary'yi yalnız iki read-only action için genişletti.
3. `PB-6.4c` kararı `stay_preflight` olarak kapanmıştır; live write widening
   support boundary dışında kalır.
4. `PB-6.4d` kararı `stay_deferred` olarak kapanmıştır; kernel-api write-side
   widening için ayrı implementation tranche'i yalnız yazılı önkoşullar
   karşılandığında açılabilir.

## 7. Riskler

| Risk | Etki | Önlem |
|---|---|---|
| Küçük correctness fix'i support widening gibi sunmak | Orta | status + docs boundary'yi dar tut |
| `PB-1` için stale backlog üzerinde çalışmak | Orta | canlı testle doğrula, sonra status'u düzelt |
| Deterministic test hygiene işinde scope creep | Yüksek | `PB-3`ü seam inventory + küçük tranche fix'ler olarak dilimle |
| Zayıf testlerle fake green oluşması | Yüksek | behavior-first assertions ve smoke kanıtı zorunlu |
| Inventory genişliği nedeniyle yanlış promotion yapmak | Yüksek | extension bazlı karar tablosu olmadan support widening yapma |

## 8. Anlık Öncelik

`PB-8` programı kapanış aşamasına geçti.

1. Son kapanan slice: `PB-8.4` (`support widening closeout`)
2. Bugünkü aktif iş: `PB-8` tracker closeout ve `PB-9` kickoff hazırlığı
3. Sonraki sıra (planlı): `PB-9` issue + ordering contract

`PB-8.2` completion kaydı:

1. Issue: [#290](https://github.com/Halildeu/ao-kernel/issues/290) (`closed`)
2. PR: [#295](https://github.com/Halildeu/ao-kernel/pull/295)
3. Merge commit: `c0e98f7`
4. Sonuç: `PRJ-KERNEL-API` write-side action'lar runtime-backed hale geldi ve
   behavior-first test matrisi + docs parity merge edildi.

`PB-8.3` completion kaydı:

1. Issue: [#291](https://github.com/Halildeu/ao-kernel/issues/291)
2. PR'ler:
   - [#297](https://github.com/Halildeu/ao-kernel/pull/297) (`f09d9fa`)
   - [#298](https://github.com/Halildeu/ao-kernel/pull/298) (`99f9ed3`)
3. Sonuç:
   - `open_pr` failure metadata parity (run + step + event) güçlendirildi
   - `bug_fix_flow` `open_pr` adımı workflow-level explicit live-write guard
     (`AO_KERNEL_ALLOW_GH_CLI_PR_LIVE_WRITE=1`) arkasına alındı
4. Karar: `stay_deferred`
   - gerekçe: guard + evidence iyileştirmelerine rağmen disposable/live rollback
     zinciri workflow runtime contract'ında promoted support kapısı değildir.

`PB-8.4` implementation odakları:

1. `PB-8.1`..`PB-8.3` kararlarını support docs yüzeyinde tek anlamlı closeout'a
   indirmek
2. `PUBLIC-BETA` + `SUPPORT-BOUNDARY` + status parity drift'ini kapatmak
3. `PB-8` tracker closeout kararını issue/docs kanıtlarıyla netleştirmek

`PB-8.4` completion kaydı:

1. Issue: [#292](https://github.com/Halildeu/ao-kernel/issues/292)
2. PR: [#300](https://github.com/Halildeu/ao-kernel/pull/300)
3. Merge commit: `e2c57c1`
4. Sonuç:
   - status SSOT referansları `PB-8.4` closeout hattına hizalandı
   - `ROLLBACK` stable rollback satırı drift-safe hale getirildi
   - `OPERATIONS-RUNBOOK` + `UPGRADE-NOTES` üzerinde `bug_fix_flow open_pr`
     fail-closed guard beklentisi explicit yazıldı
5. Karar: `PB-8` support closeout tranche'i tamamlandı, tracker closeout adımına geçildi

## 9. PB-7 Closeout Snapshot

**Kapanış tarihi:** 2026-04-23

1. `PB-1` ... `PB-6` dilimleri `main` üzerinde yazılı kanıtlarla kapatıldı.
2. Son karar: `claude-code-cli` lane için `stay_beta_operator_managed`
   (PB-6.6 / issue `#277`).
3. Support boundary bilerek dar bırakıldı; shipped baseline dışı widening
   otomatik açılmadı.
4. O günkü program tracker/umbrella issue kapanışı bu closeout ile yapılır:
   `#243`, `#219`.

## 10. Güncelleme Protokolü

Her merge sonrası bu dosyada en az şu alanlar güncellenecek:

- aktif slice
- tamamlanan slice'ın durumu
- issue / PR / kanıt referansı
- yeni risk veya deferred notu
- sıradaki tek aktif hat

## 11. PB-7 Kickoff

`PB-6` closeout sonrası bir sonraki dar implementation hattı bugün
`PB-7.1` olarak açıldı:

1. Issue: [#281](https://github.com/Halildeu/ao-kernel/issues/281)
2. Plan: `.claude/plans/PB-7.1-GH-CLI-PR-LIVE-WRITE-READINESS.md`
3. Hedef: `gh-cli-pr` lane'inde live-write promotion için eksik kalan
   sandbox/side-effect/rollback/evidence kapılarını
   **support boundary widening yapmadan** kod/test seviyesinde somutlamak.

`PB-7.1` closeout:

1. Issue: [#281](https://github.com/Halildeu/ao-kernel/issues/281)
2. PR: [#282](https://github.com/Halildeu/ao-kernel/pull/282)
3. Merge commit: `431e0d9`
4. Sonuç: `gh-cli-pr` lane'i için preflight default korunarak live-write
   readiness guard/rollback check katmanı eklendi; support widening açılmadı.

`PB-7.2` closeout:

1. Issue: [#283](https://github.com/Halildeu/ao-kernel/issues/283)
2. Plan: `.claude/plans/PB-7.2-BUGFIX-FLOW-SUPPORT-GRADUATION.md`
3. Karar: `stay_deferred`
4. Gerekçe özeti: `bug_fix_flow` correctness/evidence zinciri doğrulansa da
   write-side support widening için workflow-level side-effect safety kapıları
   henüz promoted kontrat seviyesinde değil.
5. Sonraki hat: `PB-7.3` (`PRJ-KERNEL-API` write-side widening preconditions)

`PB-7.3` closeout:

1. Issue: [#285](https://github.com/Halildeu/ao-kernel/issues/285)
2. Plan: `.claude/plans/PB-7.3-KERNEL-API-WRITE-SIDE-WIDENING-DECISION.md`
3. Karar: `stay_deferred`
4. Gerekçe özeti: write-side action'lar runtime registry'de açılmadı
   (`project_status`, `roadmap_follow`, `roadmap_finish` owner yok); behavior +
   safety + rollback kapıları widening için hâlâ tamamlanmadı.
5. Sonraki hat: yok (explicit widening implementation tranche açılmadan
   support boundary dar kalır)

## 12. PB-8 Closeout

`PB-7` closeout sonrası açılan `PB-8` widening programındaki tranche'lar tamamlandı.

1. Program roadmap: `.claude/plans/PB-8-GENERAL-PURPOSE-PRODUCTIONIZATION-ROADMAP.md`
2. Tracker issue: [#288](https://github.com/Halildeu/ao-kernel/issues/288) (`closeout pending`)
3. Kapanan tranche'lar:
   - `PB-8.1` ([#289](https://github.com/Halildeu/ao-kernel/issues/289))
   - `PB-8.2` ([#290](https://github.com/Halildeu/ao-kernel/issues/290))
   - `PB-8.3` ([#291](https://github.com/Halildeu/ao-kernel/issues/291))
   - `PB-8.4` ([#292](https://github.com/Halildeu/ao-kernel/issues/292))
4. Sonraki hat:
   - `PB-9` (yeni issue + aktif ordering contract ataması ile açılacak)
5. Program kuralı korunur: tek aktif runtime tranche + zorunlu kanıt paketi.
