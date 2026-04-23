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
- **Aktif slice planı:** `.claude/plans/PB-6.2-KERNEL-API-PROMOTION-CONTRACT.md`
- **Public Beta support boundary:** `docs/PUBLIC-BETA.md`
- **Known bugs registry:** `docs/KNOWN-BUGS.md`
- **GitHub milestone:** [Post-Beta Correctness and Expansion](https://github.com/Halildeu/ao-kernel/milestone/2)
- **GitHub tracker issue:** [#219](https://github.com/Halildeu/ao-kernel/issues/219)
- **Aktif issue:** [#251](https://github.com/Halildeu/ao-kernel/issues/251)

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

### `PB-6.2` — `PRJ-KERNEL-API` minimum runtime-backed promotion contract

`PB-6` içinde aktif alt hat artık `PB-6.2`'dir. Bu slice'ın işi,
`PRJ-KERNEL-API` için minimum runtime-backed promotion contract'ını yazmaktır.
Bu slice runtime behavior değiştirmez; sonraki implementation PR'ının dar
scope'unu belirler.

Canlı baseline:

1. `python3 -m ao_kernel doctor`
   - `8 OK, 1 WARN, 0 FAIL`
   - `runtime_backed=1`, `quarantined=18`, `missing_runtime_refs=161`
2. `python3 scripts/claude_code_cli_smoke.py --output json`
   - `overall_status="pass"`
3. `python3 scripts/gh_cli_pr_smoke.py --output json`
   - `overall_status="pass"`

`PB-6.1a` closeout'u bu slice için artık giriş kanıtıdır:

1. `PRJ-EXECUTORPORT`
2. `PRJ-MEMORYPORT`
3. `PRJ-SEARCH`
4. `PRJ-UI-COCKPIT-LITE`

hepsi confirmatory pass sonunda **confirmed retire/archive candidate** olarak
kaldı.

`PB-6.1b` closeout sonucu artık giriş kanıtıdır:

1. `first`: `PRJ-KERNEL-API`
2. `second`: `PRJ-CONTEXT-ORCHESTRATION`
3. `hold`: `PRJ-RELEASE-AUTOMATION`

`PB-6.2` contract hedefi:

1. İlk runtime-backed tranche yalnız `system_status` ve `doc_nav_check`
   action'larını kapsayacak.
2. `project_status`, `roadmap_follow`, `roadmap_finish` deferred kalacak.
3. Handler yolu explicit olacak:
   - `ao_kernel/extensions/bootstrap.py`
   - `ao_kernel/extensions/handlers/prj_kernel_api.py`
4. Missing runtime refs sıfırlanmadan support widening yapılmayacak.
5. `doctor` hedef metriği implementation PR'ında `runtime_backed=2`,
   `quarantined=17` olacak.

Beklenen çıktı:

1. `PB-6.2` planı review/merge hattına girecek.
2. Merge sonrası aktif hat `PB-6.2b` veya doğrudan implementation PR olarak
   `PRJ-KERNEL-API` handler/smoke promotion olacak.
3. `PRJ-CONTEXT-ORCHESTRATION`, `PRJ-KERNEL-API` hattı kapanana kadar
   başlamayacak.

## 6. Sonra

`PB-6` açıldıktan sonraki doğru sıra:

1. `PB-6.2b` `PRJ-KERNEL-API` minimum runtime-backed implementation
2. `PB-6.3` `PRJ-CONTEXT-ORCHESTRATION` remap/owner decision
3. `PB-6.4` real-adapter/write-side graduation criteria yeniden sıralama

Not:

1. `PB-6.2` planning slice'ı support boundary'yi değiştirmez; yalnız
   implementation PR için contract çıkarır.

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

1. `PB-6.2` `PRJ-KERNEL-API` minimum runtime-backed promotion contract

## 9. Güncelleme Protokolü

Her merge sonrası bu dosyada en az şu alanlar güncellenecek:

- aktif slice
- tamamlanan slice'ın durumu
- issue / PR / kanıt referansı
- yeni risk veya deferred notu
- sıradaki tek aktif hat
