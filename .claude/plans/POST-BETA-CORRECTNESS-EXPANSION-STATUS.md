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
- **Son tamamlanan implementation contract:** `.claude/plans/PB-6.2-KERNEL-API-PROMOTION-CONTRACT.md`
- **Son extension decision record:** `.claude/plans/PB-6.3-CONTEXT-ORCHESTRATION-DECISION.md`
- **Public Beta support boundary:** `docs/PUBLIC-BETA.md`
- **Known bugs registry:** `docs/KNOWN-BUGS.md`
- **GitHub milestone:** [Post-Beta Correctness and Expansion](https://github.com/Halildeu/ao-kernel/milestone/2)
- **GitHub tracker issue:** [#219](https://github.com/Halildeu/ao-kernel/issues/219)
- **Aktif issue:** [#256](https://github.com/Halildeu/ao-kernel/issues/256)

## 2. Başlangıç Gerçeği

- `WP-5` ile `WP-9` production hardening programı `main` üzerinde kapanmıştır.
- Repo bugün dar ama kanıtlı bir Public Beta / governed runtime yüzeyine sahiptir.
- Support boundary hâlâ bilerek dardır; `review_ai_flow + codex-stub` shipped
  baseline, gerçek adapter lane'leri ise operator-managed beta durumundadır.
- Public Beta closeout sonrası aktif program odağı artık defer edilmiş ilk
  correctness boşlukları değil; support-surface widening ve PB-5 closeout'u
  tamamlandı, bugünkü aktif odak daha geniş expansion gap'lerin sıralanmasıdır.
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
| `PB-6` general-purpose expansion gap map | In progress ([#243](https://github.com/Halildeu/ao-kernel/issues/243)) | narrow beta'dan daha geniş production platform çizgisine geçiş için hangi yüzeylerin neden henüz promoted olmadığını canlı kanıtla sınıflandırmak | written gap map + ordered tranche backlog + canlı baseline |

## 5. Şimdi

### `PB-6.3` — `PRJ-CONTEXT-ORCHESTRATION` remap and owner boundary decision

`PB-6` içinde aktif alt hat artık `PB-6.3`'tür. Bu slice'ın işi,
`PRJ-CONTEXT-ORCHESTRATION` için support widening'e geçmeden önce remap,
owner ve runtime-boundary kararını yazılı hale getirmektir.

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
   - `runtime_backed=2`, `quarantined=17`
   - `runtime_backed_ids=PRJ-HELLO, PRJ-KERNEL-API`
2. `python3 scripts/claude_code_cli_smoke.py --output json`
   - `overall_status="pass"`
3. `python3 scripts/gh_cli_pr_smoke.py --output json`
   - `overall_status="pass"`

`PB-6.3` giriş kanıtı:

1. `PB-6.1b` shortlist sonucu `PRJ-CONTEXT-ORCHESTRATION` ikinci adaydır.
2. `PRJ-KERNEL-API` hattı kapandı; artık sıradaki extension decision
   slice'ına geçilebilir.
3. Support widening yine code path + behavior tests + smoke/doctor evidence +
   docs parity birlikte mevcut olmadan yapılmayacak.

`PB-6.3` karar sonucu:

1. `PRJ-CONTEXT-ORCHESTRATION` `remap-needed` later candidate olarak kalır.
2. Bu slice runtime behavior değiştirmez ve support boundary genişletmez.
3. Extension bugün `truth_tier=quarantined`,
   `runtime_handler_registered=False`, `remap_candidate_refs=5`,
   `missing_runtime_refs=4` durumundadır.
4. Canlı runtime owner sinyali `ao_kernel.context` paketidir; fakat extension
   handler owner henüz yoktur.
5. Gelecek runtime promotion ancak
   `ao_kernel/extensions/handlers/prj_context_orchestration.py` gibi explicit
   bir handler, dar `kernel_api_actions`, behavior-first tests ve docs parity
   ile yapılabilir.

Beklenen çıktı:

1. Written decision table:
   `.claude/plans/PB-6.3-CONTEXT-ORCHESTRATION-DECISION.md`.
2. Manifest ref cleanup ve handler/action contract ayrı follow-up slice'a
   ayrılacak.
3. `PRJ-RELEASE-AUTOMATION`, context orchestration contract cleanup kararı
   yazılmadan başlamayacak.

## 6. Sonra

`PB-6` açıldıktan sonraki doğru sıra:

1. `PB-6.2b` `PRJ-KERNEL-API` minimum runtime-backed implementation
   - completed on `main` via [#255](https://github.com/Halildeu/ao-kernel/pull/255)
2. `PB-6.3` `PRJ-CONTEXT-ORCHESTRATION` remap/owner decision
   - active via [#256](https://github.com/Halildeu/ao-kernel/issues/256)
   - decision: `remap-needed`, keep non-shipped until contract cleanup
3. `PB-6.3b` `PRJ-CONTEXT-ORCHESTRATION` manifest/contract cleanup
   - next slice after `PB-6.3` merge
4. `PB-6.4` real-adapter/write-side graduation criteria yeniden sıralama

Not:

1. `PB-6.2` planning slice'ı support boundary'yi değiştirmedi; yalnız
   implementation PR için contract çıkardı.
2. `PB-6.2b` support boundary'yi yalnız iki read-only action için genişletti.
3. `PB-6.3b` merge olmadan başka extension promotion hattı başlamayacak.

## 7. Riskler

| Risk | Etki | Önlem |
|---|---|---|
| Küçük correctness fix'i support widening gibi sunmak | Orta | status + docs boundary'yi dar tut |
| `PB-1` için stale backlog üzerinde çalışmak | Orta | canlı testle doğrula, sonra status'u düzelt |
| Deterministic test hygiene işinde scope creep | Yüksek | `PB-3`ü seam inventory + küçük tranche fix'ler olarak dilimle |
| Zayıf testlerle fake green oluşması | Yüksek | behavior-first assertions ve smoke kanıtı zorunlu |
| Inventory genişliği nedeniyle yanlış promotion yapmak | Yüksek | extension bazlı karar tablosu olmadan support widening yapma |

## 8. Anlık Öncelik

Bugünden itibaren doğru sıra:

1. `PB-6.3` `PRJ-CONTEXT-ORCHESTRATION` remap/owner decision
2. `PB-6.3b` `PRJ-CONTEXT-ORCHESTRATION` manifest/contract cleanup

## 9. Güncelleme Protokolü

Her merge sonrası bu dosyada en az şu alanlar güncellenecek:

- aktif slice
- tamamlanan slice'ın durumu
- issue / PR / kanıt referansı
- yeni risk veya deferred notu
- sıradaki tek aktif hat
