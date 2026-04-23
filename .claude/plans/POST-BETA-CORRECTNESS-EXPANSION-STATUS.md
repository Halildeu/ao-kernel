# Post-Beta Correctness and Expansion Status

**Durum tarihi:** 2026-04-24
**Amaç:** Public Beta closeout sonrasında kalan correctness debt'ini
fail-closed disiplinle kapatmak, support-surface widening kararlarını kanıtla
yönetmek ve genel amaçlı production çizgisine geçiş için gerçek gap'leri
ayrı ayrı görünür kılmak.
**Yürütme modu:** Kapsam disiplini
**Bu dosyanın rolü:** yaşayan execution backlog + program status SSOT

## 1. SSOT Sınırları

- **Execution status / backlog:** bu dosya
- **Tarihsel closeout snapshot:** `.claude/plans/PRODUCTION-HARDENING-PROGRAM-STATUS.md`
- **Son tamamlanan implementation contract:** `.claude/plans/PB-8-GENERAL-PURPOSE-PRODUCTIONIZATION-ROADMAP.md` (`PB-8` closeout)
- **Son extension decision record:** `.claude/plans/PB-6.3-CONTEXT-ORCHESTRATION-DECISION.md`
- **Program roadmap:** `.claude/plans/GP-2-DEFERRED-SUPPORT-LANES-REPRIORITIZATION.md`
- **Production stable live roadmap:** `.claude/plans/PRODUCTION-STABLE-LIVE-ROADMAP.md`
- **Son tamamlanan stable-gate contract:** `.claude/plans/ST-1-RELEASABLE-PRE-RELEASE-GATE.md` (`ST-1 completed`)
- **Aktif decision/ordering contract:** `.claude/plans/ST-2-STABLE-SUPPORT-BOUNDARY-FREEZE.md` (`ST-2 active`)
- **GP-2.2 closeout contract:** `.claude/plans/GP-2.2-COST-USD-RECONCILE-COMPLETENESS.md`
- **PB-9.2 karar notu:** `.claude/plans/PB-9.2-TRUTH-INVENTORY-DEBT-RATCHET.md`
- **PB-9.3 karar notu:** `.claude/plans/PB-9.3-WRITE-LIVE-EVIDENCE-REHEARSAL.md`
- **PB-9.4 karar notu:** `.claude/plans/PB-9.4-PRODUCTION-CLAIM-DECISION-CLOSEOUT.md`
- **GP-1.2 karar notu:** `.claude/plans/GP-1.2-GH-CLI-PR-LIVE-WRITE-DISPOSABLE-DECISION.md`
- **GP-1.3 karar notu:** `.claude/plans/GP-1.3-BUG-FIX-FLOW-RELEASE-CLOSURE-DECISION.md`
- **GP-1.4 karar notu:** `.claude/plans/GP-1.4-CONTEXT-ORCHESTRATION-PROMOTION-DECISION.md`
- **GP-1.5 karar notu:** `.claude/plans/GP-1.5-PROGRAM-CLOSEOUT-DECISION.md`
- **GP-1 roadmap:** `.claude/plans/GP-1-GENERAL-PURPOSE-PRODUCTION-WIDENING-ROADMAP.md`
- **GP-2 roadmap:** `.claude/plans/GP-2-DEFERRED-SUPPORT-LANES-REPRIORITIZATION.md`
- **GP-2.1 karar notu:** `.claude/plans/GP-2.1-DEFERRED-LANE-EVIDENCE-DELTA-MAP.md`
- **GP-2.2 contract:** `.claude/plans/GP-2.2-COST-USD-RECONCILE-COMPLETENESS.md`
- **Public Beta support boundary:** `docs/PUBLIC-BETA.md`
- **Known bugs registry:** `docs/KNOWN-BUGS.md`
- **GitHub milestone:** [Post-Beta Correctness and Expansion](https://github.com/Halildeu/ao-kernel/milestone/2)
- **GitHub tracker issue:** [#219](https://github.com/Halildeu/ao-kernel/issues/219)
- **PB-6 umbrella issue:** [#243](https://github.com/Halildeu/ao-kernel/issues/243)
- **PB-8 tracker issue:** [#288](https://github.com/Halildeu/ao-kernel/issues/288) (`closed`)
- **PB-9 tracker issue:** [#302](https://github.com/Halildeu/ao-kernel/issues/302) (`closed`)
- **GP-1 tracker issue:** [#316](https://github.com/Halildeu/ao-kernel/issues/316) (`closed`)
- **GP-2 tracker issue:** [#329](https://github.com/Halildeu/ao-kernel/issues/329) (`open`)
- **GP-2.1 issue:** [#331](https://github.com/Halildeu/ao-kernel/issues/331) (`closed`)
- **GP-2.2 issue:** [#333](https://github.com/Halildeu/ao-kernel/issues/333) (`closed`)
- **GP-2.2b issue:** [#336](https://github.com/Halildeu/ao-kernel/issues/336) (`closed`)
- **ST-1 issue:** [#340](https://github.com/Halildeu/ao-kernel/issues/340) (`closed after closeout`)
- **ST-2 issue:** [#344](https://github.com/Halildeu/ao-kernel/issues/344) (`open`)
- **Aktif issue:** [#344](https://github.com/Halildeu/ao-kernel/issues/344) (`ST-2 stable support boundary freeze`)

## 2. Başlangıç Gerçeği

- `WP-5` ile `WP-9` production hardening programı `main` üzerinde kapanmıştır.
- Repo bugün dar ama kanıtlı bir Public Beta / governed runtime yüzeyine sahiptir.
- Support boundary hâlâ bilerek dardır; `review_ai_flow + codex-stub` shipped
  baseline, gerçek adapter lane'leri ise operator-managed beta durumundadır.
- Public Beta closeout sonrası `PB-8.4` docs/runbook/release-gate parity
  tranche'i tamamlandı ve `PB-8` tracker kapandı; `PB-9.1` prerequisite parity,
  `PB-9.2` truth inventory debt ratchet, `PB-9.3` write/live evidence rehearsal
  ve `PB-9.4` production claim decision closeout dilimleri kapanmıştır.
- `GP-1` tracker kapanmıştır; `GP-1.1..GP-1.5` kararları tamamlanmış ve
  support boundary `stay_beta_operator_managed` çizgisinde korunmuştur.
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
| `PB-8` general-purpose productionization roadmap | Completed on `main` ([#288](https://github.com/Halildeu/ao-kernel/issues/288), [#300](https://github.com/Halildeu/ao-kernel/pull/300), [#301](https://github.com/Halildeu/ao-kernel/pull/301)) | widening kararlarını tranche bazında kapatmak ve support closeout parity'yi tamamlamak | tracker closeout + docs/runbook/release-gate parity |
| `PB-9` production claim readiness gates | Completed on `main` ([#302](https://github.com/Halildeu/ao-kernel/issues/302), closed tranche [#303](https://github.com/Halildeu/ao-kernel/issues/303), closed tranche [#306](https://github.com/Halildeu/ao-kernel/issues/306), closed tranche [#309](https://github.com/Halildeu/ao-kernel/issues/309), closed tranche [#312](https://github.com/Halildeu/ao-kernel/issues/312)) | production claim kararını gate bazlı ve kanıt odaklı yürütmek | roadmap + decision records + tracker closeout |
| `GP-1` general-purpose production widening | Completed on `main` ([#316](https://github.com/Halildeu/ao-kernel/issues/316), [#327](https://github.com/Halildeu/ao-kernel/pull/327), [#326](https://github.com/Halildeu/ao-kernel/issues/326)) | PB-9 sonrası widening kararlarını tranche bazında ve gate-first disiplinde tamamlamak | GP-1.1..GP-1.5 decision records + closeout parity |
| `GP-2` deferred support-lane backlog reprioritization | Active ([#329](https://github.com/Halildeu/ao-kernel/issues/329), latest slice [#333](https://github.com/Halildeu/ao-kernel/issues/333) closed) | `GP-1` sonrası deferred lane'leri tek anlamlı sıraya indirip ilk aktif runtime tranche'i seçmek | deferred lane evidence-delta map + `Now/Next/Later` kararı + GP-2.2 closeout |
| `ST-0` production stable truth closeout | Completed on `main` ([#338](https://github.com/Halildeu/ao-kernel/pull/338), [#339](https://github.com/Halildeu/ao-kernel/pull/339)) | stable/live yol haritasını eklemek ve GP-2.2 drift'i kapatmak | production stable roadmap + GP-2.2 closeout verdict |
| `ST-1` releasable pre-release gate | Completed on `main` ([#340](https://github.com/Halildeu/ao-kernel/issues/340), [#341](https://github.com/Halildeu/ao-kernel/pull/341), [#342](https://github.com/Halildeu/ao-kernel/pull/342)) | current `main`i `4.0.0b2` pre-release gate'e hazırlamak ve publish etmek | release contract + exact file/test/publish checklist + PyPI exact pin verify |
| `ST-2` stable support boundary freeze | Active ([#344](https://github.com/Halildeu/ao-kernel/issues/344)) | `4.0.0` stable öncesinde shipped/beta/deferred/known-bug boundary'yi kanıtla dondurmak | support matrix evidence map + docs parity + stable blocker decision |

## 5. Şimdi

### `ST-1` — releasable pre-release gate (`4.0.0b2`) completed

Production-stable roadmap'teki `ST-1` kapısı tamamlandı. Issue
[#340](https://github.com/Halildeu/ao-kernel/issues/340) için aktif contract
`.claude/plans/ST-1-RELEASABLE-PRE-RELEASE-GATE.md` olarak belirlendi ve
release/publish sonucu aynı dosyaya işlendi.
`GP-2.2b` deterministic assertion upgrade issue'su
[#336](https://github.com/Halildeu/ao-kernel/issues/336) kapanmış, PR
[#337](https://github.com/Halildeu/ao-kernel/pull/337) merge edilmiştir.
`GP-2.2d` docs/status closeout PR
[#338](https://github.com/Halildeu/ao-kernel/pull/338) ile tamamlandı.

Son GP-2.2 kararı:

1. `GP-2.2c` runtime patch no-op kalır; ek runtime gap kanıtlanmadı.
2. Adapter-path `cost_usd` reconcile public support
   claim olarak deferred kalır.
3. Public Beta stable kanal dili hard-code exact stable sürüm taşımaz.
4. [#333](https://github.com/Halildeu/ao-kernel/issues/333) merge sonrası
   closeout comment ile kapatılır.

Contract PR [#341](https://github.com/Halildeu/ao-kernel/pull/341) ile
tamamlandı. Release PR [#342](https://github.com/Halildeu/ao-kernel/pull/342)
ile merge edildi ve tag/publish doğrulaması tamamlandı:

1. `pyproject.toml` ve `ao_kernel/__init__.py` version surfaces
   `4.0.0b2`ye çekildi.
2. `CHANGELOG.md`, `docs/PUBLIC-BETA.md`, `docs/UPGRADE-NOTES.md` ve
   `docs/ROLLBACK.md` beta pinleri hizalandı.
3. Full CI + packaging-smoke geçti.
4. Tag `v4.0.0-beta.2` `main` merge commit'i `bc1bca7` üzerine pushlandı.
5. `publish.yml` run `24863200216` success oldu.
6. PyPI `https://pypi.org/project/ao-kernel/4.0.0b2/` `HTTP/2 200` döndü.
7. Fresh venv exact pin install `ao-kernel==4.0.0b2`, üç entrypoint ve
   installed-package `examples/demo_review.py --cleanup` smoke geçti.

Tarihi PB/GP kayıtları aşağıda korunur; güncel yürütme kararı yukarıdaki
`ST-1` closeout bloğudur. Aktif hat artık `ST-2` stable support boundary
freeze'dir; issue [#344](https://github.com/Halildeu/ao-kernel/issues/344)
ve contract
`.claude/plans/ST-2-STABLE-SUPPORT-BOUNDARY-FREEZE.md` üzerinden yürür.
Stable scope, bu gate tamamlanmadan genişletilmeyecek.

### `ST-2` — stable support boundary freeze active

`ST-2` amacı `4.0.0` stable öncesinde support boundary'yi dondurmaktır. Bu
runtime widening işi değildir. İlk PR yalnız contract/status bağlantısını
kurar; sonraki freeze PR'i `docs/PUBLIC-BETA.md`,
`docs/SUPPORT-BOUNDARY.md`, `docs/KNOWN-BUGS.md`, `docs/UPGRADE-NOTES.md`,
`docs/ROLLBACK.md` ve gerekirse `CHANGELOG.md` üzerinde docs parity +
stable-blocker kararını kapatır.

Mevcut varsayılan karar:

1. Shipped candidate dar kalır: entrypoint'ler, `doctor`,
   `review_ai_flow + codex-stub`, `examples/demo_review.py`,
   `PRJ-KERNEL-API` read-only actions, policy command enforcement ve release
   gate'leri.
2. `claude-code-cli`, `gh-cli-pr`, `PRJ-KERNEL-API` write-side actions ve
   real-adapter benchmark tam modu operator-managed beta kalır.
3. `bug_fix_flow` release closure, full remote PR opening, roadmap/spec demo
   ve adapter-path `cost_usd` public support claim deferred kalır.
4. Known bug registry shipped baseline blocker taşımıyorsa stable blocker yok
   olarak yazılır; shipped baseline etkilenirse ST-2 durur.

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

Aktif slice: `ST-5` deferred correctness closure contract.

1. Son kapanan slice: `GP-2.2` adapter-path `cost_usd` reconcile completeness
   closeout ([#333](https://github.com/Halildeu/ao-kernel/issues/333))
2. Production-stable roadmap: `.claude/plans/PRODUCTION-STABLE-LIVE-ROADMAP.md`
3. Completed contract: `.claude/plans/ST-1-RELEASABLE-PRE-RELEASE-GATE.md`
4. Completed contract: `.claude/plans/ST-2-STABLE-SUPPORT-BOUNDARY-FREEZE.md`
5. Son kapanan PR: [#346](https://github.com/Halildeu/ao-kernel/pull/346)
6. ST-2 freeze kararı: dar stable runtime için ST-3/ST-4 blocker değildir;
   real-adapter/live-write promotion istenirse ayrı gate gerekir.
7. Aktif issue: [#348](https://github.com/Halildeu/ao-kernel/issues/348)
8. Aktif contract: `.claude/plans/ST-5-DEFERRED-CORRECTNESS-CLOSURE.md`
9. Sonraki iş: `ST-5` altında deferred correctness kalemlerini `ship`, `beta`,
   `deferred` veya `retire` kararına indirmek.
10. Stable release'e doğrudan geçilmez; önce `ST-5`, `ST-6` ve `ST-7` gates
   kapanır.

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
5. Karar: `PB-8` support closeout tranche'i tamamlandı

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
2. Tracker issue: [#288](https://github.com/Halildeu/ao-kernel/issues/288) (`closed`)
3. Kapanan tranche'lar:
   - `PB-8.1` ([#289](https://github.com/Halildeu/ao-kernel/issues/289))
   - `PB-8.2` ([#290](https://github.com/Halildeu/ao-kernel/issues/290))
   - `PB-8.3` ([#291](https://github.com/Halildeu/ao-kernel/issues/291))
   - `PB-8.4` ([#292](https://github.com/Halildeu/ao-kernel/issues/292))
4. Sonraki hat:
   - `PB-9` ([#302](https://github.com/Halildeu/ao-kernel/issues/302))
5. Program kuralı korunur: tek aktif runtime tranche + zorunlu kanıt paketi.

## 13. PB-9 Kickoff

`PB-8` closeout sonrası yeni aktif widening/decision hattı `PB-9` olarak açıldı.

1. Program roadmap:
   `.claude/plans/PB-9-PRODUCTION-CLAIM-READINESS-GATES.md`
2. Tracker issue: [#302](https://github.com/Halildeu/ao-kernel/issues/302) (`closed`)
3. `PB-9.1` completion:
   - issue: [#303](https://github.com/Halildeu/ao-kernel/issues/303) (`closed`)
   - PR: [#305](https://github.com/Halildeu/ao-kernel/pull/305)
   - merge commit: `ea32ee4`
   - sonuç: operator prerequisite contract docs + smoke-help yüzeylerinde
     tek anlamlı hale getirildi.
4. `PB-9.2` completion:
   - issue: [#306](https://github.com/Halildeu/ao-kernel/issues/306) (`closed`)
   - PR: [#308](https://github.com/Halildeu/ao-kernel/pull/308)
   - merge commit: `dd371bb`
   - sonuç: doctor truth inventory için deterministic debt ratchet kontratı
     (`.claude/plans/PB-9.2-TRUTH-INVENTORY-DEBT-RATCHET.md`) ve
     script+test kanıtı (`scripts/truth_inventory_ratchet.py`,
     `tests/test_extension_truth_ratchet.py`) `main`e alındı.
5. `PB-9.3` completion:
   - issue: [#309](https://github.com/Halildeu/ao-kernel/issues/309) (`closed`)
   - PR: [#311](https://github.com/Halildeu/ao-kernel/pull/311)
   - merge commit: `7df83c9`
   - sonuç: write/live lane için deterministic rehearsal komut paketi
     (`scripts/kernel_api_write_smoke.py` + `scripts/gh_cli_pr_smoke.py`)
     ve karar notu (`.claude/plans/PB-9.3-WRITE-LIVE-EVIDENCE-REHEARSAL.md`)
     `main`e alındı.
6. `PB-9.4` completion:
   - issue: [#312](https://github.com/Halildeu/ao-kernel/issues/312) (`closed`)
   - PR: [#314](https://github.com/Halildeu/ao-kernel/pull/314)
   - merge commit: `06997b8`
   - sonuç: production claim closeout kararı
     `stay_beta_operator_managed` olarak yazılı karar notuna bağlandı
     (`.claude/plans/PB-9.4-PRODUCTION-CLAIM-DECISION-CLOSEOUT.md`).
7. Program kapanış notu:
   - `PB-9.1..PB-9.4` tamamlandı
   - active tranche yok
   - yeni widening/program hattı ayrı tracker ile açılacak

## 14. GP-1 Closeout Snapshot

`GP-1` programı kapanmıştır.

1. Program roadmap:
   `.claude/plans/GP-1-GENERAL-PURPOSE-PRODUCTION-WIDENING-ROADMAP.md`
2. Tracker issue: [#316](https://github.com/Halildeu/ao-kernel/issues/316) (`closed`)
3. `GP-1.1` completion:
   - issue: [#315](https://github.com/Halildeu/ao-kernel/issues/315) (`closed`)
   - PR: [#317](https://github.com/Halildeu/ao-kernel/pull/317)
   - verdict: authority gate map completed
4. `GP-1.2` completion:
   - issue: [#318](https://github.com/Halildeu/ao-kernel/issues/318) (`closed`)
   - karar notu: `.claude/plans/GP-1.2-GH-CLI-PR-LIVE-WRITE-DISPOSABLE-DECISION.md`
   - verdict: `stay_preflight`
5. `GP-1.3` completion:
   - issue: [#322](https://github.com/Halildeu/ao-kernel/issues/322) (`closed`)
   - karar notu: `.claude/plans/GP-1.3-BUG-FIX-FLOW-RELEASE-CLOSURE-DECISION.md`
   - verdict: `stay_deferred`
6. `GP-1.4` completion:
   - issue: [#324](https://github.com/Halildeu/ao-kernel/issues/324) (`closed`)
   - karar notu: `.claude/plans/GP-1.4-CONTEXT-ORCHESTRATION-PROMOTION-DECISION.md`
   - verdict: `stay_contract_only`
7. `GP-1.5` completion:
   - issue: [#326](https://github.com/Halildeu/ao-kernel/issues/326) (`closed`)
   - karar notu: `.claude/plans/GP-1.5-PROGRAM-CLOSEOUT-DECISION.md`
   - verdict: program closed (`stay_beta_operator_managed`)
8. Closeout sonucu:
   - aktif tranche yok
   - support boundary genişletilmedi
   - yeni widening hattı için ayrı tracker açılmadan program tekrar açılmaz

## 15. GP-2 Kickoff Snapshot

`GP-1` closeout sonrası aktif hat `GP-2` olarak başlatıldı.

1. Program roadmap:
   `.claude/plans/GP-2-DEFERRED-SUPPORT-LANES-REPRIORITIZATION.md`
2. Tracker issue:
   [#329](https://github.com/Halildeu/ao-kernel/issues/329) (`open`)
3. Aktif tranche:
   `GP-2.1` deferred lane evidence-delta map
4. Tranche hedefi:
   - deferred lane tablosunu `Now / Next / Later` sırasına indirmek
   - ilk aktif runtime slice için tek issue + tek contract seçmek
5. Sınır:
   - bu kickoff dilimi runtime widening implementasyonu içermez
   - support boundary kararı yalnız yazılı kanıt/karar notu ile güncellenir

## 16. GP-2.1 Active Snapshot

`GP-2` kickoff sonrası aktif ordering tranche `GP-2.1`e indirildi.

1. Issue: [#331](https://github.com/Halildeu/ao-kernel/issues/331) (`open`)
2. Active contract:
   `.claude/plans/GP-2.1-DEFERRED-LANE-EVIDENCE-DELTA-MAP.md`
3. Ordering verdict:
   - `Now`: adapter-path `cost_usd` reconcile completeness
   - `Next`: `gh-cli-pr` full E2E live remote PR opening
   - `Later`: `bug_fix_flow` release closure + `DEMO-SCRIPT-SPEC` widening
4. Next implementation start condition:
   - `GP-2.2` için tek issue/branch açılacak
   - ilk runtime slice yalnız `cost_usd` evidence parity kapsamıyla sınırlı kalacak

## 17. GP-2.2 Kickoff Snapshot

`GP-2.1` ordering closeout sonrası aktif runtime tranche `GP-2.2` olarak açıldı.

1. Issue: [#333](https://github.com/Halildeu/ao-kernel/issues/333) (`closed`)
2. Active contract:
   `.claude/plans/GP-2.2-COST-USD-RECONCILE-COMPLETENESS.md`
3. Scope:
   - adapter-path `cost_usd` reconcile completeness gap'ini dar kapsamda kapatmak
   - behavior-first test/evidence assertion setini güçlendirmek
4. Sınır:
   - support boundary widening kararı bu tranche'ta verilmeyecek
   - `gh-cli-pr` full E2E ve `bug_fix_flow` closure lane'leri `deferred` kalacak
5. İlk ilerleme:
   - `GP-2.2a` truth capture sonucu canonical assertion matrisi
     `.claude/plans/GP-2.2-COST-USD-RECONCILE-COMPLETENESS.md` içine işlendi
6. Closeout:
   - `GP-2.2b` deterministic assertion upgrade [#336](https://github.com/Halildeu/ao-kernel/issues/336) ile kapandı
   - `GP-2.2c` runtime patch no-op kaldı
   - `GP-2.2d` docs/status parity PR [#338](https://github.com/Halildeu/ao-kernel/pull/338) ile tamamlandı
   - adapter-path `cost_usd` reconcile public support claim olarak deferred kaldı
