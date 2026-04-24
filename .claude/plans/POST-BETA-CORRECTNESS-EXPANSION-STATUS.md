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
- **Son tamamlanan GP closeout decision:** `.claude/plans/GP-2-CLOSEOUT-DECISION.md`
- **Son tamamlanan maintenance baseline:** `.claude/plans/SM-1-STABLE-MAINTENANCE-BASELINE.md`
- **Son tamamlanan stable evidence refresh:** `.claude/plans/SM-2-STABLE-BASELINE-EVIDENCE-REFRESH.md`
- **Son tamamlanan status truth cleanup:** `.claude/plans/SM-3-PROGRAM-STATUS-ACTIVE-SECTION-CLEANUP.md`
- **Son tamamlanan historical beta pin wording cleanup:** `.claude/plans/SM-4-HISTORICAL-BETA-PIN-WORDING.md`
- **Son tamamlanan GP-3 promotion roadmap:** `.claude/plans/GP-3-PRODUCTION-CERTIFIED-ADAPTER-PROMOTION-ROADMAP.md`
- **Son tamamlanan GP-3 prerequisite truth refresh:** `.claude/plans/GP-3.1-CLAUDE-CODE-CLI-PREREQUISITE-TRUTH-REFRESH.md`
- **Son tamamlanan GP-3 repeatability record:** `.claude/plans/GP-3.2-CLAUDE-CODE-CLI-GOVERNED-WORKFLOW-REPEATABILITY.md`
- **Son tamamlanan GP-3 failure-mode matrix:** `.claude/plans/GP-3.3-CLAUDE-CODE-CLI-FAILURE-MODE-MATRIX.md`
- **Son tamamlanan GP-3 evidence completeness record:** `.claude/plans/GP-3.4-CLAUDE-CODE-CLI-EVIDENCE-COMPLETENESS.md`
- **Son tamamlanan GP-3 support-boundary decision record:** `.claude/plans/GP-3.5-CLAUDE-CODE-CLI-SUPPORT-BOUNDARY-DECISION.md`
- **Son tamamlanan GP-3 closeout decision:** `.claude/plans/GP-3.6-PRODUCTION-CERTIFIED-ADAPTER-PROMOTION-CLOSEOUT.md`
- **Son tamamlanan GP-4 CI-managed live adapter gate design:** `.claude/plans/GP-4-CI-MANAGED-LIVE-ADAPTER-GATE-DESIGN.md`
- **Son tamamlanan GP-4.1 CI-safe live adapter gate skeleton:** `.claude/plans/GP-4.1-CI-SAFE-LIVE-ADAPTER-GATE-SKELETON.md`
- **Son tamamlanan GP-4.2 live adapter evidence artifact contract:** `.claude/plans/GP-4.2-LIVE-ADAPTER-EVIDENCE-ARTIFACT-CONTRACT.md`
- **Son tamamlanan GP-4.3 protected environment / secret contract:** `.claude/plans/GP-4.3-PROTECTED-ENVIRONMENT-SECRET-CONTRACT.md`
- **Son tamamlanan GP-4.4 protected live rehearsal blocked decision:** `.claude/plans/GP-4.4-PROTECTED-LIVE-REHEARSAL-BLOCKED-DECISION.md`
- **Son tamamlanan GP-4.5 support-boundary closeout:** `.claude/plans/GP-4.5-SUPPORT-BOUNDARY-CLOSEOUT.md`
- **Son tamamlanan GP-5 roadmap setup:** `.claude/plans/GP-5-GENERAL-PURPOSE-PRODUCTION-PLATFORM-INTEGRATION.md`
- **Son tamamlanan GP-5.1a protected gate prerequisite audit:** `.claude/plans/GP-5.1a-PROTECTED-GATE-PREREQUISITE-AUDIT.md`
- **Son tamamlanan GP-5.3a repo-intelligence retrieval evidence contract:** `.claude/plans/GP-5.3a-REPO-INTELLIGENCE-RETRIEVAL-EVIDENCE-CONTRACT.md`
- **Son tamamlanan GP-5.3b agent context handoff contract:** `.claude/plans/GP-5.3b-AGENT-CONTEXT-HANDOFF-CONTRACT.md`
- **Son tamamlanan GP-5.3c workflow opt-in design contract:** `.claude/plans/GP-5.3c-WORKFLOW-OPT-IN-DESIGN-CONTRACT.md`
- **Son tamamlanan GP-5.3d no-MCP/no-root-export guard:** `.claude/plans/GP-5.3d-NO-MCP-NO-ROOT-EXPORT-GUARD.md`
- **Son tamamlanan GP-5.3e workflow building-block decision:** `.claude/plans/GP-5.3e-REPO-INTELLIGENCE-WORKFLOW-BUILDING-BLOCK-DECISION.md`
- **Son tamamlanan GP-5.4a governed read-only workflow rehearsal:** `.claude/plans/GP-5.4a-GOVERNED-READ-ONLY-WORKFLOW-REHEARSAL.md`
- **Son tamamlanan GP-5.5a controlled patch/test design:** `.claude/plans/GP-5.5a-CONTROLLED-PATCH-TEST-DESIGN.md`
- **Son tamamlanan GP-5.5b controlled local patch/test rehearsal:** `.claude/plans/GP-5.5b-CONTROLLED-LOCAL-PATCH-TEST-REHEARSAL.md`
- **Aktif GP-5.6a disposable PR write rehearsal:** `.claude/plans/GP-5.6a-DISPOSABLE-PR-WRITE-REHEARSAL.md`
- **Son tamamlanan RI-5 design gate:** `.claude/plans/RI-5-REPO-INTELLIGENCE-ROOT-EXPORT.md`
- **Aktif GP-5 integration roadmap:** `.claude/plans/GP-5-GENERAL-PURPOSE-PRODUCTION-PLATFORM-INTEGRATION.md`
- **Production stable live roadmap:** `.claude/plans/PRODUCTION-STABLE-LIVE-ROADMAP.md`
- **Son tamamlanan stable-gate contract:** `.claude/plans/ST-8-STABLE-PUBLISH-AND-POST-PUBLISH-VERIFICATION.md` (`ST-8 completed`)
- **Son tamamlanan certification contract:** `.claude/plans/GP-2.4-CLAUDE-CODE-CLI-READ-ONLY-CERTIFICATION.md`
- **Son tamamlanan rollback rehearsal contract:** `.claude/plans/GP-2.5-GH-CLI-PR-LIVE-WRITE-ROLLBACK-REHEARSAL.md`
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
- **GP-2 tracker issue:** [#329](https://github.com/Halildeu/ao-kernel/issues/329) (`closed by GP-2 closeout PR`)
- **GP-2.1 issue:** [#331](https://github.com/Halildeu/ao-kernel/issues/331) (`closed`)
- **GP-2.2 issue:** [#333](https://github.com/Halildeu/ao-kernel/issues/333) (`closed`)
- **GP-2.2b issue:** [#336](https://github.com/Halildeu/ao-kernel/issues/336) (`closed`)
- **GP-2.3 issue:** [#361](https://github.com/Halildeu/ao-kernel/issues/361) (`closed`)
- **GP-2.4 issue:** [#363](https://github.com/Halildeu/ao-kernel/issues/363) (`closed`)
- **GP-2.4a issue:** [#365](https://github.com/Halildeu/ao-kernel/issues/365) (`closed after merge`)
- **GP-2.4d issue:** [#371](https://github.com/Halildeu/ao-kernel/issues/371) (`closed after merge`)
- **GP-2.5 issue:** [#373](https://github.com/Halildeu/ao-kernel/issues/373) (`closed`)
- **GP-2.5a issue:** [#375](https://github.com/Halildeu/ao-kernel/issues/375) (`closed`)
- **ST-1 issue:** [#340](https://github.com/Halildeu/ao-kernel/issues/340) (`closed after closeout`)
- **ST-2 issue:** [#344](https://github.com/Halildeu/ao-kernel/issues/344) (`closed`)
- **ST-6 issue:** [#351](https://github.com/Halildeu/ao-kernel/issues/351) (`closed`)
- **ST-7 issue:** [#355](https://github.com/Halildeu/ao-kernel/issues/355) (`closed after closeout`)
- **ST-8 issue:** [#358](https://github.com/Halildeu/ao-kernel/issues/358) (`closed after closeout`)
- **SM-1 issue:** [#378](https://github.com/Halildeu/ao-kernel/issues/378) (`closed by maintenance baseline PR`)
- **SM-2 issue:** [#380](https://github.com/Halildeu/ao-kernel/issues/380) (`closed by evidence refresh PR`)
- **SM-3 issue:** [#382](https://github.com/Halildeu/ao-kernel/issues/382) (`closed by status cleanup PR`)
- **SM-4 issue:** [#384](https://github.com/Halildeu/ao-kernel/issues/384) (`closed by docs wording PR`)
- **GP-3 tracker issue:** [#386](https://github.com/Halildeu/ao-kernel/issues/386) (`closed by GP-3.6 closeout PR`)
- **GP-3.1 issue:** [#388](https://github.com/Halildeu/ao-kernel/issues/388) (`closed`)
- **GP-3.2 issue:** [#390](https://github.com/Halildeu/ao-kernel/issues/390) (`closed`)
- **GP-3.3 issue:** [#392](https://github.com/Halildeu/ao-kernel/issues/392) (`closed`)
- **GP-3.4 issue:** [#394](https://github.com/Halildeu/ao-kernel/issues/394) (`closed`)
- **GP-3.5 issue:** [#396](https://github.com/Halildeu/ao-kernel/issues/396) (`closed`)
- **GP-3.6 issue:** [#398](https://github.com/Halildeu/ao-kernel/issues/398) (`closed by closeout PR`)
- **GP-4 tracker issue:** [#400](https://github.com/Halildeu/ao-kernel/issues/400) (`closes with GP-4.5 PR`)
- **GP-4.1 issue:** [#402](https://github.com/Halildeu/ao-kernel/issues/402) (`closed`)
- **GP-4.2 issue:** [#404](https://github.com/Halildeu/ao-kernel/issues/404) (`closes with GP-4.2 PR`)
- **GP-4.3 issue:** [#407](https://github.com/Halildeu/ao-kernel/issues/407) (`closes with GP-4.3 PR`)
- **GP-4.4 issue:** [#410](https://github.com/Halildeu/ao-kernel/issues/410) (`closes with GP-4.4 PR`)
- **GP-4.5 issue:** [#413](https://github.com/Halildeu/ao-kernel/issues/413) (`closes with GP-4.5 PR`)
- **GP-5 tracker issue:** [#424](https://github.com/Halildeu/ao-kernel/issues/424) (`active`)
- **GP-5.1a issue:** [#429](https://github.com/Halildeu/ao-kernel/issues/429) (`closed after GP-5.1a PR`)
- **GP-5.3a issue:** [#431](https://github.com/Halildeu/ao-kernel/issues/431) (`closed after GP-5.3a PR`)
- **GP-5.3b issue:** [#433](https://github.com/Halildeu/ao-kernel/issues/433) (`closed after GP-5.3b PR`)
- **GP-5.3c issue:** [#435](https://github.com/Halildeu/ao-kernel/issues/435) (`closed after GP-5.3c PR`)
- **GP-5.3d issue:** [#437](https://github.com/Halildeu/ao-kernel/issues/437) (`closed after GP-5.3d PR`)
- **GP-5.3e issue:** [#439](https://github.com/Halildeu/ao-kernel/issues/439) (`closed after GP-5.3e PR`)
- **GP-5.4a issue:** [#441](https://github.com/Halildeu/ao-kernel/issues/441) (`closed after GP-5.4a PR`)
- **GP-5.5a issue:** [#443](https://github.com/Halildeu/ao-kernel/issues/443) (`closed after GP-5.5a PR`)
- **GP-5.5b issue:** [#445](https://github.com/Halildeu/ao-kernel/issues/445) (`closed after GP-5.5b PR`)
- **GP-5.6a issue:** [#447](https://github.com/Halildeu/ao-kernel/issues/447) (`active closeout candidate`)
- **RI-5 design gate:** PR `#426` merged; next slice is RI-5a export-plan preview implementation
- **Current mode:** GP-5 active integration planning / no support widening yet.
  Future widening requires protected live-adapter evidence, repo-intelligence
  integration gates, write-side rollback evidence, and an explicit closeout
  decision.

## 2. Başlangıç Gerçeği

- `WP-5` ile `WP-9` production hardening programı `main` üzerinde kapanmıştır.
- Repo bugün dar ama kanıtlı bir stable governed runtime yüzeyine sahiptir.
- Support boundary hâlâ bilerek dardır; `review_ai_flow + codex-stub` shipped
  baseline, gerçek adapter lane'leri ise operator-managed beta durumundadır.
- Public Beta closeout sonrası `PB-8.4` docs/runbook/release-gate parity
  tranche'i tamamlandı ve `PB-8` tracker kapandı; `PB-9.1` prerequisite parity,
  `PB-9.2` truth inventory debt ratchet, `PB-9.3` write/live evidence rehearsal
  ve `PB-9.4` production claim decision closeout dilimleri kapanmıştır.
- `GP-1` tracker kapanmıştır; `GP-1.1..GP-1.5` kararları tamamlanmış ve
  support boundary `stay_beta_operator_managed` çizgisinde korunmuştur.
- `ST-8` tamamlanmıştır: `v4.0.0` PyPI üzerinde canlıdır, exact pin ve bare
  stable install fresh venv içinde `ao-kernel 4.0.0` döndürmüştür.
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
| `GP-2` deferred support-lane backlog reprioritization | Completed ([#329](https://github.com/Halildeu/ao-kernel/issues/329), closeout decision `.claude/plans/GP-2-CLOSEOUT-DECISION.md`) | `GP-1` ve `v4.0.0` stable sonrası deferred/support widening lane'lerini tek anlamlı sıraya indirip post-stable support-lane gates yürütmek | GP-2.5a sandbox rehearsal evidence + support boundary unchanged verdict |
| `SM-1` stable maintenance baseline | Completed ([#378](https://github.com/Halildeu/ao-kernel/issues/378), decision `.claude/plans/SM-1-STABLE-MAINTENANCE-BASELINE.md`) | GP-2 sonrası varsayılan çalışma modunu maintenance olarak sabitlemek | no active widening gate + support-boundary prerequisite drift fixed |
| `SM-2` stable baseline evidence refresh | Completed ([#380](https://github.com/Halildeu/ao-kernel/issues/380), evidence `.claude/plans/SM-2-STABLE-BASELINE-EVIDENCE-REFRESH.md`) | SM-1 sonrası shipped baseline kanıtını tazelemek | entrypoints + doctor + truth inventory + wheel-installed packaging smoke + targeted tests |
| `SM-3` program status active-section cleanup | Completed ([#382](https://github.com/Halildeu/ao-kernel/issues/382), record `.claude/plans/SM-3-PROGRAM-STATUS-ACTIVE-SECTION-CLEANUP.md`) | yaşayan status dosyasındaki stale historical `ST-2` anlatımını temizlemek | no active widening gate + historical records clearly non-active |
| `SM-4` historical beta pin wording | Completed ([#384](https://github.com/Halildeu/ao-kernel/issues/384), record `.claude/plans/SM-4-HISTORICAL-BETA-PIN-WORDING.md`) | `4.0.0b2` beta pinini aktif kanal gibi değil historical pre-release yolu gibi anlatmak | stable `4.0.0` remains default + no support widening |
| `GP-3` production-certified adapter promotion | Completed ([#386](https://github.com/Halildeu/ao-kernel/issues/386), [#388](https://github.com/Halildeu/ao-kernel/issues/388), [#390](https://github.com/Halildeu/ao-kernel/issues/390), [#392](https://github.com/Halildeu/ao-kernel/issues/392), [#394](https://github.com/Halildeu/ao-kernel/issues/394), [#396](https://github.com/Halildeu/ao-kernel/issues/396), [#398](https://github.com/Halildeu/ao-kernel/issues/398), roadmap `.claude/plans/GP-3-PRODUCTION-CERTIFIED-ADAPTER-PROMOTION-ROADMAP.md`) | ilk real-adapter lane'i production-certified read-only seviyesine aday yapmak | final verdict `close_keep_operator_beta`; support boundary unchanged |
| `GP-4` CI-managed live adapter gate design | Completed by GP-4.5 closeout ([#400](https://github.com/Halildeu/ao-kernel/issues/400), design `.claude/plans/GP-4-CI-MANAGED-LIVE-ADAPTER-GATE-DESIGN.md`) | GP-3'te eksik kalan project-owned live-adapter gate'i support widening olmadan tasarlamak | final verdict `close_no_widening_keep_operator_beta`; no secrets, no live default CI call, no support widening |
| `GP-4.1` CI-safe live adapter gate skeleton | Completed on `main` ([#402](https://github.com/Halildeu/ao-kernel/issues/402), record `.claude/plans/GP-4.1-CI-SAFE-LIVE-ADAPTER-GATE-SKELETON.md`) | workflow-dispatch-only contract artifact yüzeyini eklemek | no secrets, no live adapter execution, report `overall_status=blocked`, no support widening |
| `GP-4.2` live adapter evidence artifact contract | Completed by GP-4.2 PR ([#404](https://github.com/Halildeu/ao-kernel/issues/404), record `.claude/plans/GP-4.2-LIVE-ADAPTER-EVIDENCE-ARTIFACT-CONTRACT.md`) | live gate evidence artifact shape'i schema-backed hale getirmek | schema validation + blocked evidence slots + no live adapter execution + no support widening |
| `GP-4.3` protected environment / secret contract | Completed by GP-4.3 PR ([#407](https://github.com/Halildeu/ao-kernel/issues/407), record `.claude/plans/GP-4.3-PROTECTED-ENVIRONMENT-SECRET-CONTRACT.md`) | protected GitHub environment, secret handle ve fork-safety contract'ini schema-backed hale getirmek | no secret values, no environment creation, no live adapter execution, no support widening |
| `GP-4.4` protected live rehearsal blocked decision | Completed by GP-4.4 PR ([#410](https://github.com/Halildeu/ao-kernel/issues/410), record `.claude/plans/GP-4.4-PROTECTED-LIVE-REHEARSAL-BLOCKED-DECISION.md`) | protected live rehearsal prerequisite eksikse fake live success üretmeden blocked decision kaydetmek | schema validation + blocked rehearsal decision artifact + no live adapter execution + no support widening |
| `GP-4.5` support-boundary closeout | Completed by GP-4.5 PR ([#413](https://github.com/Halildeu/ao-kernel/issues/413), record `.claude/plans/GP-4.5-SUPPORT-BOUNDARY-CLOSEOUT.md`) | blocked GP-4 evidence against support boundary kararını kapatmak | verdict `close_no_widening_keep_operator_beta`; `claude-code-cli` remains Beta/operator-managed |
| `GP-5` general-purpose platform integration | Active setup / `GP-5.3e` current | repo intelligence, protected real-adapter gate, governed read-only E2E, controlled patch/test, disposable PR rehearsal ve ops widening paketini tek entegrasyon programına bağlamak | `GP-5.1a` completed blocked protected gate audit; `GP-5.3a` pins retrieval evidence; `GP-5.3b` pins explicit handoff; `GP-5.3c` defines future opt-in contract; `GP-5.3d` pins no-MCP/no-root-export guard; `GP-5.3e` decides beta explicit-handoff building-block use; no production support widening until GP-5.9 closeout |
| `ST-0` production stable truth closeout | Completed on `main` ([#338](https://github.com/Halildeu/ao-kernel/pull/338), [#339](https://github.com/Halildeu/ao-kernel/pull/339)) | stable/live yol haritasını eklemek ve GP-2.2 drift'i kapatmak | production stable roadmap + GP-2.2 closeout verdict |
| `ST-1` releasable pre-release gate | Completed on `main` ([#340](https://github.com/Halildeu/ao-kernel/issues/340), [#341](https://github.com/Halildeu/ao-kernel/pull/341), [#342](https://github.com/Halildeu/ao-kernel/pull/342)) | current `main`i `4.0.0b2` pre-release gate'e hazırlamak ve publish etmek | release contract + exact file/test/publish checklist + PyPI exact pin verify |
| `ST-2` stable support boundary freeze | Completed on `main` ([#344](https://github.com/Halildeu/ao-kernel/issues/344), [#347](https://github.com/Halildeu/ao-kernel/pull/347)) | `4.0.0` stable öncesinde shipped/beta/deferred/known-bug boundary'yi kanıtla dondurmak | support matrix evidence map + docs parity + stable blocker decision |
| `ST-5` deferred correctness closure | Completed on `main` ([#348](https://github.com/Halildeu/ao-kernel/issues/348), [#350](https://github.com/Halildeu/ao-kernel/pull/350)) | known deferred correctness kalemlerini stable blocker olmaktan çıkarıp açık support boundary'ye bağlamak | deferred bug contract + stable impact decision |
| `ST-6` operations readiness | Completed on `main` ([#351](https://github.com/Halildeu/ao-kernel/issues/351), [#353](https://github.com/Halildeu/ao-kernel/pull/353)) | stable release öncesi incident, rollback, upgrade, known-bugs ve release-gate runbook'unu işletilebilir hale getirmek | operations runbook + rollback matrix + fresh-venv verification + packaging smoke parity |
| `ST-7` stable release candidate | Completed on `main` ([#355](https://github.com/Halildeu/ao-kernel/issues/355), [#356](https://github.com/Halildeu/ao-kernel/pull/356), [#357](https://github.com/Halildeu/ao-kernel/pull/357)) | `4.0.0` stable için final aday branch/PR hazırlamak | version/changelog/docs final + full CI + installed-package smoke |
| `ST-8` stable publish and post-publish verification | Completed ([#358](https://github.com/Halildeu/ao-kernel/issues/358), tag `v4.0.0`, publish workflow [`24866683491`](https://github.com/Halildeu/ao-kernel/actions/runs/24866683491)) | `4.0.0` stable tag/publish ve public install gerçeğini doğrulamak | publish workflow success + PyPI exact/bare install verify + installed demo smoke |

## 5. Şimdi

### Current mode — GP-5 active integration planning / no support widening yet

`GP-3` parent promotion programı `close_keep_operator_beta` kararıyla
kapanmıştır. `GP-4.1` workflow skeleton, `GP-4.2` evidence artifact,
`GP-4.3` protected environment contract, `GP-4.4` blocked rehearsal decision ve
`GP-4.5` support-boundary closeout tamamlanmıştır.

Final GP-4 verdict: `close_no_widening_keep_operator_beta`.

Historical GP-4 closeout mode before GP-5 opened was
`stable maintenance / no active widening gate`. GP-5 changes the active
planning mode, not the GP-4 verdict or support boundary.

Bu nedenle `claude-code-cli` lane hâlâ `Beta (operator-managed)` kalır;
production-certified real-adapter support, stable support widening ve genel
amaçlı production coding automation platform claim'i verilmez. `SM-1` stable
maintenance baseline ve `SM-2` stable baseline evidence refresh geçerlidir.

Mevcut yol:

1. `GP-3.0` scope freeze / roadmap kayıt — completed
2. `GP-3.1` `claude-code-cli` prerequisite truth refresh — completed
3. `GP-3.2` governed workflow repeatability — completed
4. `GP-3.3` failure-mode matrix — completed
5. `GP-3.4` evidence completeness — completed
6. `GP-3.5` support-boundary decision — completed; verdict `keep_operator_beta`
7. `GP-3.6` program closeout — completed; final verdict `close_keep_operator_beta`

Promotion sadece code path + behavior tests + smoke + docs + runbook + CI
evidence aynı yönde ise yapılır. `GP-4` bu eksik gate'in contract/evidence
yüzeyini hazırladı, ancak required protected environment ve project-owned
credential attested olmadığı için live rehearsal `blocked_no_rehearsal` kaldı.
Bu yüzden support boundary değişmedi.

`GP-5` bu kapanmış kararların üzerine yeni aktif entegrasyon programıdır.
Amaç, genel amaçlı production coding automation platform claim'ini hemen
vermek değil; repo-intelligence context, protected real-adapter evidence,
governed read-only E2E, controlled patch/test, disposable PR rehearsal ve ops
support widening kapılarını sırayla kapatmaktır. `GP-5.0` roadmap/authority
freeze, `GP-5.0a` Claude/MCP consultation absorb, `GP-5.1a` protected gate
prerequisite audit, `GP-5.3a` retrieval evidence contract, `GP-5.3b` agent
context handoff contract, `GP-5.3c` workflow opt-in design contract ve
`GP-5.3d` no-MCP/no-root-export guard tamamlandı. Aktif slice `GP-5.3e`
workflow building-block decision closeout adayıdır. Bu slice production support
boundary'yi genişletmez.

`GP-5.0a` ile yazılı hale getirilen ek kapılar:

1. Packaging freshness: release/support readiness yalnız wheel-installed
   fresh-venv smoke ile kanıtlanır; editable-install geçişi yeterli değildir.
2. Shipped-baseline non-regression: her widening slice mevcut stable baseline
   entrypoints, doctor, demo review ve packaging smoke davranışını korur.
3. Cost/token evidence: real-adapter ve governed workflow kanıtı adapter
   identity, elapsed time, token usage varsa token bilgisi ve `cost_usd` ya da
   açık `usage_missing` / `cost_unavailable` nedeni taşır.
4. `RI-5` / `GP-5.3` ownership: `RI-5` explicit root/context export planını,
   `GP-5.3` governed workflow context handoff'unu sahiplenir; ilk
   `GP-5.3a` / `GP-5.3b` dilimleri `RI-5a` export-plan dosyasını gerektirmez.
5. Runbook skeleton: `GP-5.5` ve `GP-5.6` write-side slice'ları incident /
   rollback runbook iskeletini aynı PR içinde güncellemeden kapanamaz.
6. Workspace metadata drift: `.ao/workspace.json` içindeki workspace metadata
   versiyonu runtime package versiyonundan ayrı bir sinyaldir; platform
   readiness sinyali olarak kullanılmadan önce ayrı küçük investigation/fix
   slice'ı açılmalıdır.

`GP-5` aktif yol artık:

1. `GP-5.1a` protected gate prerequisite audit — completed on `main`
2. `GP-5.3a` repo-intelligence retrieval evidence contract — completed on `main`
3. `GP-5.3b` agent context handoff contract — completed on `main`
4. `GP-5.3c` workflow opt-in design — completed on `main`
5. `GP-5.3d` no-MCP/no-root-export guard — completed on `main`
6. `GP-5.3e` repo-intelligence workflow building-block promotion decision — completed on `main`
7. `GP-5.4a` governed read-only workflow rehearsal — current closeout candidate
8. `GP-5.1b` protected workflow binding patch — blocked until attestation

`GP-5.3a` ve `GP-5.3b`, `GP-5.1a` ile paralel yürüyebilir; çünkü read-only
retrieval evidence ve manual/stdout handoff protected real-adapter credential'a
bağlı değildir. Buna rağmen support widening ancak GP-5 closeout kapıları
tamamlanınca yapılır.

`GP-5.1a` canlı audit sonucu:

1. GitHub environments inventory yalnız `pypi` döndürdü.
2. Required environment `ao-kernel-live-adapter-gate` yoktur.
3. Repository secret lookup `AO_CLAUDE_CODE_CLI_AUTH` için boş liste döndürdü.
4. Environment secret lookup `ao-kernel-live-adapter-gate` için `HTTP 404`
   döndürdü; environment yokken env-secret attestation yapılamaz.
5. `.github/workflows/live-adapter-gate.yml` hâlâ `workflow_dispatch` only,
   `environment:` binding yok, `secrets.` referansı yok ve live adapter
   çalıştırmıyor.
6. `scripts/live_adapter_gate_contract.py` blocked evidence üretmeye devam
   ediyor: `overall_status=blocked`, `decision=blocked_no_rehearsal`,
   `support_widening=false`.

Karar: `blocked_unattested_keep_operator_beta`. `GP-5.1b` workflow binding
patch'i, protected environment ve credential handle metadata attestation
gelmeden açılmayacak. Bu blokaj `GP-5.3a` ve `GP-5.3b` read-only
repo-intelligence contract slice'larını engellemez.

`GP-5.3a` closeout adayı:

1. Karar: `keep_beta_read_only_retrieval_contract`.
2. `repo query` sonucu source artifact hash'leri, `min_similarity`,
   current-only result sınırı, untruncated snippet hash'i, namespace/metadata
   filtreleri, path-escape exclusion ve stale-source diagnostics davranışları
   focused testlerle pinlenmiştir.
3. `RI-5a` export-plan preview bu slice için `not_used`; `.ao/context`,
   `CLAUDE.md`, `AGENTS.md`, `ARCHITECTURE.md` ve `CODEX_CONTEXT.md` root
   yazıları yapılmaz.
4. Relevance sınırı bilinçli olarak vector similarity + filtreler +
   deterministic ordering ile sınırlıdır; arbitrary coding task semantic
   correctness iddiası yoktur.
5. Bu slice sonrasında `GP-5.3b` agent context handoff contract açılmıştır.

`GP-5.3b` closeout adayı:

1. Karar: `keep_beta_explicit_stdout_handoff_contract`.
2. `repo query --output markdown` çıktısı runtime içinde `## Handoff Contract`
   bölümü taşır.
3. Tek desteklenen handoff, operatörün stdout Markdown çıktısını görünür agent
   input'u olarak açıkça vermesidir.
4. Markdown pack `No hidden injection` sınırını ve MCP/root export/
   `context_compiler` auto-feed dışlamasını açık yazar.
5. `RI-5a` export-plan preview bu slice için `not_used`; support boundary
   genişlemez.

`GP-5.3c` closeout adayı:

1. Karar: `design_only_no_runtime_auto_feed`.
2. Future opt-in shape
   `repo-intelligence-workflow-context-opt-in.schema.v1.json` ile schema-backed
   hale gelir.
3. Schema explicit opt-in, source artifact hash'leri, current-only freshness,
   beta read-only support tier ve safety flag'lerini zorunlu kılar.
4. Mevcut bundled workflow definition'ları `repo_intelligence_context` veya
   `repo_query_context` declare etmez.
5. Mevcut `compile_context()` arbitrary `repo_query_context` session input'unu
   ingest etmez.
6. Runtime schema/executor/`context_compiler` wiring yoktur; support boundary
   genişlemez.

`GP-5.3d` closeout adayı:

1. Karar: `keep_beta_read_only_negative_boundary_pinned`.
2. MCP tool registry/dispatch yüzeyi repo-intelligence tool'u expose etmez.
3. `repo` CLI subcommand listesi `scan`, `index`, `query` dışına çıkmaz.
4. CLI help yüzeyi MCP/root-export flag'i advertise etmez.
5. `repo query` root authority file, MCP config export veya
   `.ao/context/repo_export_plan.json` yazmaz.
6. `RI-5a` export-plan preview bu slice için `not_used`; support boundary
   genişlemez.

`GP-5.3e` closeout adayı:

1. Karar: `promote_beta_explicit_handoff_building_block`.
2. `repo query --output markdown` çıktısı future GP-5 read-only workflow
   rehearsal için explicit operator-provided context input olarak kullanılabilir.
3. Bu yalnız beta building-block seviyesidir; production workflow integration
   veya semantic-correctness guarantee değildir.
4. Automatic prompt injection, MCP tool, root export, workflow runtime wiring ve
   `context_compiler` auto-feed hâlâ yoktur.
5. `RI-5a` export-plan preview bu slice için `not_used`; support boundary
   yalnız beta wording seviyesinde netleşir.
6. Sıradaki unblocked slice `GP-5.4a` governed read-only workflow rehearsal'dır;
   `GP-5.1b` protected gate attestation gelene kadar bloklu kalır.

`GP-5.4a` closeout adayı:

1. Karar: `pass_read_only_rehearsal_no_support_widening`.
2. `python3 scripts/gp5_read_only_rehearsal.py --output json` wheel-installed
   temporary virtualenv içinde `review_ai_flow + codex-stub` demo yolunu
   çalıştırır.
3. Repo-intelligence context yalnız `--intent-file` ile görünür workflow
   intent input'u olarak verilir; MCP tool, root export,
   `context_compiler` auto-feed veya workflow runtime wiring yoktur.
4. Evidence artifact `gp5-read-only-rehearsal-report.schema.v1.json` ile
   validate edilir ve `support_widening=false` taşır.
5. Bu slice production real-adapter support, live-write support veya arbitrary
   repo retrieval semantic correctness iddiası vermez.
6. `GP-5.5a` controlled patch/test design tamamlandı; sıradaki unblocked
   slice `GP-5.5b` controlled local patch/test rehearsal'dır.

`GP-5.5a` completed:

1. Karar: `design_contract_ready_no_runtime_write_support`.
2. `gp5-controlled-patch-test-contract.schema.v1.json` future controlled
   local patch/test rehearsal için zorunlu evidence alanlarını pinler:
   disposable/dedicated worktree, path ownership, diff preview, explicit apply
   decision, targeted tests + full-gate fallback, rollback, cleanup ve runbook.
3. `runtime_patch_application_enabled=false`,
   `remote_side_effects_allowed=false`, `active_main_worktree_allowed=false`
   ve `support_widening=false` zorunludur.
4. Existing lower-level `patch_preview` / `patch_apply` / `patch_rollback`
   runtime varlığı bu slice'ta GP-5 support widening üretmez.
5. `GP-5.5b` controlled local patch/test rehearsal tamamlandı; aktif closeout
   adayı `GP-5.6a` disposable PR write rehearsal'dır.

`GP-5.5b` closeout adayı:

1. Karar: `pass_controlled_local_patch_test_rehearsal_no_support_widening`.
2. `gp5-controlled-patch-test-rehearsal-report.schema.v1.json` local
   disposable worktree rehearsal evidence'ını pinler: preview, explicit
   apply approval, path-scoped apply/rollback claims, targeted test,
   reverse-diff rollback, idempotency ve cleanup.
3. `scripts/gp5_controlled_patch_test_rehearsal.py --approve-apply --output json`
   deterministic rehearsal komutudur.
4. Bu slice `runtime_patch_support_widening=false`,
   `remote_side_effects_allowed=false`, `active_main_worktree_touched=false`
   ve `support_widening=false` taşır.
5. Sıradaki unblocked slice `GP-5.6a` disposable PR write rehearsal'dır;
   remote PR rehearsal GP-5.5b rollback evidence olmadan başlamaz.

`GP-5.6a` closeout adayı:

1. Karar adayı: `pass_disposable_pr_write_rehearsal_no_support_widening`.
2. `gp5-disposable-pr-write-rehearsal-report.schema.v1.json` remote
   side-effect evidence'ını pinler: GP-5.5b precondition, sandbox repo guard,
   explicit `--allow-live-write`, ephemeral branch create/seed, draft PR
   create/open verify/close, final closed-state verify, branch delete verify
   ve cleanup.
3. `scripts/gp5_disposable_pr_write_rehearsal.py` default olarak remote write
   yapmaz; live path explicit opt-in ve `sandbox` keyword guard ister.
4. Bu slice `support_widening=false`, `production_remote_pr_support=false` ve
   `arbitrary_repo_support=false` taşır.
5. Sıradaki unblocked slice `GP-5.7` full production rehearsal planning'dir;
   fakat protected live-adapter environment/credential attestation gelirse
   `GP-5.1b` öne alınabilir.

Tarihi `ST`, `PB` ve `GP` kayıtları aşağıda korunur; bunlar güncel aktif gate
değildir.

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

Aktif runtime/support-widening slice yoktur. GP-2 closeout tamamlanmıştır,
SM-1 stable maintenance baseline geçerlidir ve support boundary değişmemiştir.
SM-2 stable evidence refresh tamamlanmıştır; SM-3 yalnız status drift
temizliğidir. SM-4 historical beta pin wording cleanup olarak tamamlanmıştır.

Bundan sonraki varsayılan yol maintenance'tır. Support widening istenirse yeni
bir promotion programı açılır; bu program tek lane, tek decision record, tek PR
disipliniyle yürür.

1. Son kapanan stable slice: `ST-8` stable publish and post-publish verification
   ([#358](https://github.com/Halildeu/ao-kernel/issues/358))
2. Son kapanan GP slice: `GP-2.2` adapter-path `cost_usd` reconcile
   completeness closeout ([#333](https://github.com/Halildeu/ao-kernel/issues/333))
3. Son karar slice'ı: `GP-2.3` post-stable entry decision
   ([#361](https://github.com/Halildeu/ao-kernel/issues/361))
4. Son certification contract:
   `.claude/plans/GP-2.4-CLAUDE-CODE-CLI-READ-ONLY-CERTIFICATION.md`
5. Son rollback rehearsal contract:
   `.claude/plans/GP-2.5-GH-CLI-PR-LIVE-WRITE-ROLLBACK-REHEARSAL.md`
6. Son GP closeout decision:
   `.claude/plans/GP-2-CLOSEOUT-DECISION.md`
7. Son maintenance baseline:
   `.claude/plans/SM-1-STABLE-MAINTENANCE-BASELINE.md`
8. Son evidence refresh:
   `.claude/plans/SM-2-STABLE-BASELINE-EVIDENCE-REFRESH.md`
9. Son status cleanup:
   `.claude/plans/SM-3-PROGRAM-STATUS-ACTIVE-SECTION-CLEANUP.md`
10. Son historical beta pin wording cleanup:
   `.claude/plans/SM-4-HISTORICAL-BETA-PIN-WORDING.md`
11. GP-2.4 sıra:
   - `GP-2.4a`: preflight evidence contract (`closed after merge`)
   - `GP-2.4b`: governed workflow smoke evidence (`closed after merge`)
   - `GP-2.4c`: failure-mode matrix (`closed after merge`)
   - `GP-2.4d`: support boundary verdict (`operator_managed_beta_keep`)
12. GP-2.5/GP-2.5a kanıtı:
   - preflight smoke: `overall_status=pass`
   - live-write guard smoke: `overall_status=blocked`,
     finding `gh_pr_live_write_same_head_base`
   - sandbox live-write smoke: `overall_status=pass`,
     PR `https://github.com/Halildeu/ao-kernel-sandbox/pull/1`,
     final state `CLOSED`, remote head cleanup verified
13. Stable live iddiası geçerlidir: `pip install ao-kernel` ve exact pin
   `ao-kernel==4.0.0` fresh venv içinde `4.0.0` kurmuştur.
14. Stable support boundary unchanged kalır; `gh-cli-pr` full remote PR opening
   hâlâ Deferred support yüzeyidir.

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

## 16. GP-2.1 Completed Snapshot

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

## 18. GP-2.3 Post-Stable Entry Snapshot

`ST-8` stable publish closeout sonrası aktif karar slice'ı `GP-2.3` olarak
açıldı.

1. Issue: [#361](https://github.com/Halildeu/ao-kernel/issues/361) (`closed`)
2. Active contract:
   `.claude/plans/GP-2.3-POST-STABLE-ADAPTER-CERTIFICATION-ENTRY.md`
3. Scope:
   - post-stable support-widening giriş kapısını seçmek
   - `ST-3`, `ST-4` ve extension/support widening sırasını netleştirmek
   - sonraki implementation slice için cevaplanacak contract sorularını yazmak
4. Sınır:
   - runtime değişikliği yok
   - stable support boundary widening yok
   - version bump, tag ve publish yok
5. Varsayılan karar:
   - `Now`: `claude-code-cli` read-only real-adapter certification
   - `Next`: `gh-cli-pr` live-write rollback rehearsal
   - `Later`: extension/support widening
6. Closeout:
   - next active issue: [#363](https://github.com/Halildeu/ao-kernel/issues/363)
   - next active contract:
     `.claude/plans/GP-2.4-CLAUDE-CODE-CLI-READ-ONLY-CERTIFICATION.md`

## 19. GP-2.4 Claude Code CLI Certification Snapshot

`GP-2.3` handoff sonrası contract slice `GP-2.4` olarak açıldı ve
`GP-2.4d` ile kapandı.

1. Issue: [#363](https://github.com/Halildeu/ao-kernel/issues/363) (`closed`)
2. Verdict issue: [#371](https://github.com/Halildeu/ao-kernel/issues/371)
3. Contract:
   `.claude/plans/GP-2.4-CLAUDE-CODE-CLI-READ-ONLY-CERTIFICATION.md`
4. Scope:
   - `claude-code-cli` read-only certification evidence package
   - preflight helper contract
   - governed workflow smoke requirements
   - failure-mode matrix
   - support boundary verdict criteria
5. Sınır:
   - runtime support widening yok
   - live-write yok
   - stable support boundary unchanged
6. Current local baseline probe:
   - `python3 scripts/claude_code_cli_smoke.py --output json --timeout-seconds 30`
   - `overall_status=pass`
   - `version`, `auth_status`, `prompt_access`, `manifest_invocation` checks pass
   - API key env route not present; session auth path used
   - note: 10 saniyelik probe aynı oturumda `prompt_smoke_timeout`
     üretebildiği için certification prerequisite 30 saniye timeout kullanır
7. `GP-2.4a` closeout:
   - issue: [#365](https://github.com/Halildeu/ao-kernel/issues/365)
   - `tests/test_claude_code_cli_smoke.py` now pins the helper JSON evidence
     contract shape
   - `auth_status=pass` + `prompt_access=fail` remains `blocked`
   - API key/env-token presence is observed but cannot turn prompt failure into
     certification success
8. `GP-2.4b` closeout:
   - issue: [#367](https://github.com/Halildeu/ao-kernel/issues/367)
   - `ao_kernel.real_adapter_workflow_smoke` and
     `scripts/claude_code_cli_workflow_smoke.py` run the real governed
     workflow path
   - live command:
     `python3 scripts/claude_code_cli_workflow_smoke.py --output json --timeout-seconds 60`
   - live result:
     `overall_status=pass`, `final_state=completed`,
     `run_id=c17e1456-2e4c-40fd-8942-c4880bd6fcc8`
   - verified:
     `review_findings` schema-valid artifact, `policy_checked`,
     `adapter_invoked`, `step_completed`, `workflow_completed`, redacted
     `adapter-claude-code-cli.jsonl`
9. `GP-2.4c` closeout:
   - issue: [#369](https://github.com/Halildeu/ao-kernel/issues/369)
   - helper-level negative tests pin:
     `claude_binary_missing`, `claude_not_logged_in`,
     `prompt_access_denied`, `manifest_smoke_timeout`,
     `manifest_output_not_json`
   - workflow-level fail-closed tests pin:
     `adapter_non_zero_exit`, `output_parse_failed`, `policy_denied`
   - `WorkflowSmokeCheck.finding_code` makes workflow smoke failures stable
     machine-readable evidence instead of prose-only failures
10. `GP-2.4d` closeout:
    - issue: [#371](https://github.com/Halildeu/ao-kernel/issues/371)
    - final verdict: `operator_managed_beta_keep`
    - support tier: `Beta (operator-managed)`
    - production-certified read-only: hayır
    - stable support boundary: unchanged
11. Next default:
    - GP-2 closeout or a separate `gh-cli-pr` promotion decision PR; no
      automatic support widening from `GP-2.5a`

## 20. GP-2.5 gh-cli-pr Rollback Rehearsal Snapshot

`GP-2.4` closeout sonrası contract slice `GP-2.5` olarak açıldı ve
`GP-2.5a` ile disposable sandbox canlı rehearsal kanıtı üretildi.

1. Issue: [#373](https://github.com/Halildeu/ao-kernel/issues/373) (`closed`)
2. Live rehearsal issue: [#375](https://github.com/Halildeu/ao-kernel/issues/375)
   (`closed`)
3. Contract:
   `.claude/plans/GP-2.5-GH-CLI-PR-LIVE-WRITE-ROLLBACK-REHEARSAL.md`
4. Scope:
   - `gh-cli-pr` live-write rollback rehearsal contract
   - disposable sandbox target repo requirements
   - create -> verify -> rollback evidence contract
   - fail-closed matrix and verdict options
5. Sınır:
   - production repo üzerinde remote PR oluşturulmadı
   - stable support boundary unchanged
   - full remote PR opening remains Deferred
6. No-side-effect evidence:
   - `python3 scripts/gh_cli_pr_smoke.py --mode preflight --output json --timeout-seconds 20`
     -> `overall_status=pass`
   - `python3 scripts/gh_cli_pr_smoke.py --mode live-write --allow-live-write --repo Halildeu/ao-kernel-sandbox --head main --base main --output json --timeout-seconds 20`
     -> `overall_status=blocked`, finding `gh_pr_live_write_same_head_base`
7. Disposable rehearsal evidence:
   - repo: `Halildeu/ao-kernel-sandbox`
   - created PR: `https://github.com/Halildeu/ao-kernel-sandbox/pull/1`
   - final state: `CLOSED`
   - remote head branch: deleted
   - verdict: `rehearsal_pass_keep_beta`
8. Next default:
   - GP-2 closeout completed; any support widening requires a separate
     promotion decision PR

## 21. GP-2 Parent Closeout Snapshot

GP-2 parent tracker, deferred support-lane reprioritization hedefini tamamladı.

1. Issue: [#329](https://github.com/Halildeu/ao-kernel/issues/329)
2. Decision record:
   `.claude/plans/GP-2-CLOSEOUT-DECISION.md`
3. Final verdict:
   - `claude-code-cli`: `Beta (operator-managed)`, production-certified değil
   - `gh-cli-pr`: `Beta (operator-managed)`, sandbox rehearsal geçti ama stable
     shipped support değil
   - `bug_fix_flow`: deferred
   - adapter-path `cost_usd`: deferred public support claim
4. Boundary:
   - `v4.0.0` stable baseline dar kalır
   - general-purpose production platform claim'i açılmadı
   - support widening için ayrı promotion programı gerekir

## 22. SM-1 Stable Maintenance Baseline Snapshot

GP-2 sonrası varsayılan yürütme modu maintenance olarak sabitlendi.

1. Issue: [#378](https://github.com/Halildeu/ao-kernel/issues/378)
2. Decision record:
   `.claude/plans/SM-1-STABLE-MAINTENANCE-BASELINE.md`
3. Mode:
   - active runtime widening gate yok
   - default path stable maintenance
   - support widening için ayrı promotion programı gerekir
4. Scope:
   - runtime değişikliği yok
   - version bump/tag/publish yok
   - support boundary widening yok
5. Drift fixed:
   - operator-facing `gh-cli-pr` live-write prerequisite prose now includes
     explicit `--repo <owner>/<sandbox-repo>`

## 23. SM-2 / SM-3 Stable Maintenance Refresh Snapshot

Stable maintenance hattında support widening yapılmadan kanıt ve status
doğruluğu tazelendi.

1. SM-2 issue: [#380](https://github.com/Halildeu/ao-kernel/issues/380)
2. SM-2 evidence record:
   `.claude/plans/SM-2-STABLE-BASELINE-EVIDENCE-REFRESH.md`
3. SM-3 issue: [#382](https://github.com/Halildeu/ao-kernel/issues/382)
4. SM-3 status cleanup record:
   `.claude/plans/SM-3-PROGRAM-STATUS-ACTIVE-SECTION-CLEANUP.md`
5. Current mode:
   - active runtime widening gate yok
   - default path stable maintenance
   - support widening için ayrı promotion programı gerekir
6. SM-2 evidence:
   - `python3 -m ao_kernel doctor`: `8 OK`, `1 WARN`, `0 FAIL`
   - truth inventory: `runtime_backed=2`, `contract_only=1`,
     `quarantined=16`
   - wheel-installed packaging smoke passed
   - targeted tests: `3 passed`, `1 skipped`
7. SM-3 fixed:
   - stale historical `ST-2` wording removed from `## 5. Şimdi`

## 24. SM-4 Historical Beta Pin Wording Snapshot

Stable maintenance hattında `4.0.0b2` historical Public Beta pin'i korunurken
operator-facing dil netleştirildi.

1. Issue: [#384](https://github.com/Halildeu/ao-kernel/issues/384)
2. Decision record:
   `.claude/plans/SM-4-HISTORICAL-BETA-PIN-WORDING.md`
3. Scope:
   - runtime değişikliği yok
   - version bump/tag/publish yok
   - support boundary widening yok
4. Drift fixed:
   - `docs/UPGRADE-NOTES.md` no longer presents `4.0.0b2` as a normal active
     beta channel
   - `docs/ROLLBACK.md` labels the beta rollback path as historical
     pre-release rollback
   - `docs/PUBLIC-BETA.md` keeps stable `4.0.0` as the default user path

## 25. GP-3 Production-Certified Adapter Promotion Snapshot

Stable maintenance sonrası ilk kontrollü promotion programı açıldı.

1. Tracker: [#386](https://github.com/Halildeu/ao-kernel/issues/386)
2. Roadmap:
   `.claude/plans/GP-3-PRODUCTION-CERTIFIED-ADAPTER-PROMOTION-ROADMAP.md`
3. Initial lane:
   - `claude-code-cli` read-only governed workflow lane
4. Current slice:
   - `GP-3.0` scope freeze
5. Boundary:
   - runtime değişikliği yok
   - version bump/tag/publish yok
   - stable support boundary widening yok
6. Next implementation slice:
   - `GP-3.1` prerequisite truth refresh
7. Promotion rule:
   - no promotion from one-off smoke, manifest inventory, or docs-only changes
   - promotion requires code path, behavior tests, smoke, docs, runbook, and CI
     evidence alignment

## 26. GP-3.1 Claude Code CLI Prerequisite Truth Refresh Snapshot

`claude-code-cli` için production-certified support promotion öncesi canlı
prerequisite gerçeği tazelendi.

1. Tracker: [#388](https://github.com/Halildeu/ao-kernel/issues/388)
2. Decision record:
   `.claude/plans/GP-3.1-CLAUDE-CODE-CLI-PREREQUISITE-TRUTH-REFRESH.md`
3. Commands:
   - `python3 scripts/claude_code_cli_smoke.py --output json --timeout-seconds 30`
   - `python3 scripts/claude_code_cli_workflow_smoke.py --output json --timeout-seconds 60 --cleanup`
4. Results:
   - preflight `overall_status="pass"`
   - binary/version, auth status, prompt access and manifest invocation passed
   - workflow `overall_status="pass"`
   - workflow final state `completed`
   - evidence events, `review_findings` artifact, adapter log and schema checks passed
5. Boundary:
   - runtime değişikliği yok
   - version bump/tag/publish yok
   - stable support boundary widening yok
   - `claude-code-cli` remains `Beta (operator-managed)`
6. Next slice:
   - `GP-3.2` governed workflow repeatability

## 27. GP-3.2 Claude Code CLI Governed Workflow Repeatability Snapshot

`claude-code-cli` governed read-only workflow için tek başarılı smoke yerine
tekrarlanabilirlik kanıtı üretildi.

1. Tracker: [#390](https://github.com/Halildeu/ao-kernel/issues/390)
2. Decision record:
   `.claude/plans/GP-3.2-CLAUDE-CODE-CLI-GOVERNED-WORKFLOW-REPEATABILITY.md`
3. Command:
   - `python3 scripts/claude_code_cli_workflow_smoke.py --output json --timeout-seconds 60 --cleanup`
4. Repetition:
   - run 1: `overall_status="pass"`, `preflight_status="pass"`,
     final state `completed`
   - run 2: `overall_status="pass"`, `preflight_status="pass"`,
     final state `completed`
   - run 3: `overall_status="pass"`, `preflight_status="pass"`,
     final state `completed`
5. Required checks passed in every run:
   - `final_state`
   - `evidence_events`
   - `review_findings_artifact`
   - `adapter_log`
   - `review_findings_schema`
6. Boundary:
   - runtime değişikliği yok
   - version bump/tag/publish yok
   - stable support boundary widening yok
   - `claude-code-cli` remains `Beta (operator-managed)`
7. Next slice:
   - `GP-3.3` failure-mode matrix

## 28. GP-3.3 Claude Code CLI Failure-Mode Matrix Snapshot

`claude-code-cli` helper ve governed workflow smoke için promotion blocker
failure-mode matrix'i davranışsal testlerle hizalandı.

1. Tracker: [#392](https://github.com/Halildeu/ao-kernel/issues/392)
2. Decision record:
   `.claude/plans/GP-3.3-CLAUDE-CODE-CLI-FAILURE-MODE-MATRIX.md`
3. Covered categories:
   - missing binary
   - auth missing / malformed auth status
   - prompt denied
   - timeout
   - malformed manifest/workflow output
   - policy denied
4. Added tests:
   - `test_auth_status_non_json_blocks_preflight_contract`
   - `test_manifest_json_missing_status_is_contract_failure`
   - `test_workflow_smoke_classifies_adapter_timeout`
5. Validation:
   - `python3 -m pytest -q tests/test_claude_code_cli_smoke.py tests/test_claude_code_cli_workflow_smoke.py`
   - result: `21 passed`
6. Boundary:
   - runtime behavior değişikliği yok
   - version bump/tag/publish yok
   - stable support boundary widening yok
   - `claude-code-cli` remains `Beta (operator-managed)`
7. Next slice:
   - `GP-3.4` evidence completeness

## 29. GP-3.4 Claude Code CLI Evidence Completeness Snapshot

`claude-code-cli` governed workflow smoke için evidence completeness gate'i
kapandı.

1. Tracker: [#394](https://github.com/Halildeu/ao-kernel/issues/394)
2. Decision record:
   `.claude/plans/GP-3.4-CLAUDE-CODE-CLI-EVIDENCE-COMPLETENESS.md`
3. Added smoke checks:
   - `event_order`
   - `review_findings_contents`
4. Added negative tests:
   - out-of-order required events fail with `evidence_event_order_invalid`
   - adapter log secret-like leak fails with
     `adapter_log_missing_or_unredacted`
5. Live smoke:
   - `python3 scripts/claude_code_cli_workflow_smoke.py --output json --timeout-seconds 60 --cleanup`
   - result: `overall_status="pass"`, final state `completed`
   - run id: `d269c4f7-78d5-4773-b609-a0891513e464`
6. Validation:
   - targeted tests: `26 passed, 1 skipped`
   - ruff: all checks passed
   - doctor: `8 OK, 1 WARN, 0 FAIL`
7. Cost/usage:
   - adapter-path `cost_usd` / token usage completeness is explicit non-claim
   - no public support widening should be inferred from this gate
8. Boundary:
   - stable support boundary widening yok
   - version bump/tag/publish yok
   - `claude-code-cli` remains `Beta (operator-managed)`
9. Next slice:
   - `GP-3.5` support-boundary decision

## 30. GP-3.5 Claude Code CLI Support-Boundary Decision Snapshot

`claude-code-cli` governed read-only lane için promotion kararı verildi:
`keep_operator_beta`.

1. Tracker: [#396](https://github.com/Halildeu/ao-kernel/issues/396)
2. Decision record:
   `.claude/plans/GP-3.5-CLAUDE-CODE-CLI-SUPPORT-BOUNDARY-DECISION.md`
3. Fresh preflight:
   - `python3 scripts/claude_code_cli_smoke.py --output json --timeout-seconds 30`
   - result: `overall_status="pass"`
   - Claude Code version: `2.1.87 (Claude Code)`
   - auth method: `claude.ai`
   - prompt access: pass
4. Fresh workflow smoke:
   - `python3 scripts/claude_code_cli_workflow_smoke.py --output json --timeout-seconds 60 --cleanup`
   - result: `overall_status="pass"`, final state `completed`
   - run id: `25af3707-9f8b-497f-bdb1-32cd82e7cd52`
   - checks: `event_order`, `review_findings_schema`,
     `review_findings_contents`, `adapter_log` redaction all pass
5. Verdict:
   - `promote_read_only`: rejected
   - `defer`: rejected
   - `keep_operator_beta`: accepted
6. Blocking reasons for production-certified read-only:
   - external `claude` PATH binary and local session auth remain operator state
   - `KB-001` and `KB-002` remain open
   - no CI-managed live `claude-code-cli` governed workflow gate exists
   - adapter-path `cost_usd` / token usage remains explicit non-claim
7. Boundary:
   - stable support boundary widening yok
   - version bump/tag/publish yok
   - `claude-code-cli` remains `Beta (operator-managed)`
8. Next slice:
   - `GP-3.6` program closeout

## 31. GP-3.6 Production-Certified Adapter Promotion Closeout

`GP-3` parent promotion programı kapandı.

1. Tracker: [#398](https://github.com/Halildeu/ao-kernel/issues/398)
2. Parent tracker: [#386](https://github.com/Halildeu/ao-kernel/issues/386)
3. Decision record:
   `.claude/plans/GP-3.6-PRODUCTION-CERTIFIED-ADAPTER-PROMOTION-CLOSEOUT.md`
4. Final verdict:
   - `close_keep_operator_beta`
5. Final support boundary:
   - stable shipped baseline unchanged
   - `claude-code-cli` remains `Beta (operator-managed)`
   - production-certified read-only claim not granted
   - general-purpose production coding automation platform claim not granted
6. Fresh closeout smoke:
   - `python3 scripts/claude_code_cli_smoke.py --output json --timeout-seconds 30`
   - result: `overall_status="pass"`
   - `python3 scripts/claude_code_cli_workflow_smoke.py --output json --timeout-seconds 60 --cleanup`
   - result: `overall_status="pass"`, final state `completed`
   - run id: `58939f02-2efc-4d0d-ac55-b3418fcbe7ae`
7. Closeout reason:
   - positive evidence exists, but not enough for ao-kernel-owned production
     support
   - external `claude` binary/session auth remains operator state
   - `KB-001` and `KB-002` remain open
   - no CI-managed live `claude-code-cli` governed workflow gate exists
   - adapter-path `cost_usd` / token usage remains explicit non-claim
8. Next mode:
   - stable maintenance or a new explicit CI-managed live adapter gate design

## 32. GP-4 CI-Managed Live Adapter Gate Design

`GP-4` support widening değildir. `GP-3` sonucunda eksik kalan project-owned
live adapter gate'i tasarlar.

1. Tracker: [#400](https://github.com/Halildeu/ao-kernel/issues/400)
2. Design record:
   `.claude/plans/GP-4-CI-MANAGED-LIVE-ADAPTER-GATE-DESIGN.md`
3. Final decision:
   - `close_no_widening_keep_operator_beta`
4. Preferred direction:
   - protected manual or scheduled workflow using restricted GitHub
     environment secrets
   - no fork-triggered live execution
   - machine-readable evidence artifacts
   - missing credentials become explicit `skipped`/`blocked`, not fake green
5. Rejected for now:
   - required live adapter PR check on every PR
6. Boundary:
   - `claude-code-cli` remains `Beta (operator-managed)`
   - no version bump/tag/publish
   - no runtime behavior change
   - no support widening
7. `GP-4.1` slice:
   - tracker [#402](https://github.com/Halildeu/ao-kernel/issues/402)
   - record `.claude/plans/GP-4.1-CI-SAFE-LIVE-ADAPTER-GATE-SKELETON.md`
   - workflow `.github/workflows/live-adapter-gate.yml`
   - script `scripts/live_adapter_gate_contract.py`
   - report artifact `live-adapter-gate-contract.v1.json`
   - expected report status `blocked` / `live_gate_not_implemented`
   - no live adapter execution, no secret access, no support widening
8. `GP-4.2` slice:
   - tracker [#404](https://github.com/Halildeu/ao-kernel/issues/404)
   - record `.claude/plans/GP-4.2-LIVE-ADAPTER-EVIDENCE-ARTIFACT-CONTRACT.md`
   - schema `ao_kernel/defaults/schemas/live-adapter-gate-evidence.schema.v1.json`
   - evidence artifact `live-adapter-gate-evidence.v1.json`
   - expected artifact status `blocked`, `support_widening=false`,
     `production_certified=false`
   - no live adapter execution, no secret access, no support widening
9. `GP-4.3` slice:
   - record `.claude/plans/GP-4.3-PROTECTED-ENVIRONMENT-SECRET-CONTRACT.md`
   - schema `ao_kernel/defaults/schemas/live-adapter-gate-environment.schema.v1.json`
   - environment contract artifact `live-adapter-gate-environment-contract.v1.json`
   - required protected environment `ao-kernel-live-adapter-gate`
   - required secret handle `AO_CLAUDE_CODE_CLI_AUTH`
   - expected contract status `blocked`, `live_execution_allowed=false`,
     `support_widening=false`
   - no live adapter execution, no secret value, no support widening
10. `GP-4.4` slice:
   - record `.claude/plans/GP-4.4-PROTECTED-LIVE-REHEARSAL-BLOCKED-DECISION.md`
   - schema `ao_kernel/defaults/schemas/live-adapter-gate-rehearsal-decision.schema.v1.json`
   - rehearsal decision artifact `live-adapter-gate-rehearsal-decision.v1.json`
   - expected decision status `blocked_no_rehearsal`
   - no live adapter execution, no secret value, no support widening
11. `GP-4.5` closeout:
   - record `.claude/plans/GP-4.5-SUPPORT-BOUNDARY-CLOSEOUT.md`
   - slice issue [#413](https://github.com/Halildeu/ao-kernel/issues/413)
   - final verdict `close_no_widening_keep_operator_beta`
   - `claude-code-cli` remains `Beta (operator-managed)`
   - production-certified real-adapter support not granted
   - general-purpose production platform claim not granted
12. Next slice:
   - no active GP-4 widening gate
   - future widening requires a new explicit gate after protected live evidence
     exists
