# Post-Beta Correctness and Expansion Status

**Durum tarihi:** 2026-04-22
**Amaç:** Public Beta closeout sonrasında kalan correctness debt'ini
fail-closed disiplinle kapatmak, support-surface widening kararlarını kanıtla
yönetmek ve genel amaçlı production çizgisine geçiş için gerçek gap'leri
ayrı ayrı görünür kılmak.
**Yürütme modu:** Kapsam disiplini
**Bu dosyanın rolü:** yaşayan execution backlog + program status SSOT

## 1. SSOT Sınırları

- **Execution status / backlog:** bu dosya
- **Tarihsel closeout snapshot:** `.claude/plans/PRODUCTION-HARDENING-PROGRAM-STATUS.md`
- **Aktif slice planı:** `.claude/plans/PB-3-DETERMINISTIC-TEST-HYGIENE.md`
- **Public Beta support boundary:** `docs/PUBLIC-BETA.md`
- **Known bugs registry:** `docs/KNOWN-BUGS.md`
- **GitHub milestone:** [Post-Beta Correctness and Expansion](https://github.com/Halildeu/ao-kernel/milestone/2)
- **GitHub tracker issue:** [#219](https://github.com/Halildeu/ao-kernel/issues/219)
- **Aktif issue:** [#226](https://github.com/Halildeu/ao-kernel/issues/226)

## 2. Başlangıç Gerçeği

- `WP-5` ile `WP-9` production hardening programı `main` üzerinde kapanmıştır.
- Repo bugün dar ama kanıtlı bir Public Beta / governed runtime yüzeyine sahiptir.
- Support boundary hâlâ bilerek dardır; `review_ai_flow + codex-stub` shipped
  baseline, gerçek adapter lane'leri ise operator-managed beta durumundadır.
- Public Beta closeout sonrası aktif program odağı artık defer edilmiş ilk
  correctness boşlukları değil; deterministik test hygiene, support-surface
  widening kararları ve adapter-path cost/evidence completeness gibi kalan
  post-beta işlerdir.
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
| `PB-3` deterministic test hygiene / time seams | In progress ([#226](https://github.com/Halildeu/ao-kernel/issues/226)) | zaman-bağımlı test ve zayıf assertion drift'ini sistematik azaltmak | suite proof + seam inventory |
| `PB-4` support-surface widening decisions | Planned | `gh-cli-pr` full E2E ve operator lane promotion kararlarını kanıtla vermek | smoke/e2e kanıtı + docs parity |
| `PB-5` adapter-path cost/evidence completeness | Planned | `cost_usd` reconcile ve evidence completeness boşluklarını kapatmak | tests + evidence parity |
| `PB-6` general-purpose expansion gap map | Planned | narrow beta'dan daha geniş production platform çizgisine geçiş için önkoşulları tabloya dökmek | written gap map + ordered backlog |

## 5. Şimdi

### `PB-3` — deterministic test hygiene / time seams

**Neden şimdi**
- `PB-2` merge edildi ve `bug_fix_flow` yolundaki `open_pr` metadata/evidence
  boşluğu kapandı; aktif runtime correctness slice artık bu değil.
- Bir sonraki yüksek değerli debt, zaman bağımlı test seam'leri ve davranışsal
  olarak zayıf assertion alanlarının sistematik temizlenmesidir.
- İlk tranche deliberately küçüktür: weak assertion cleanup ile behavior-first
  test kontratı dar ama kanıtlı şekilde güçlendirilecektir.

**Aktif kapsam**
1. zaman bağımlı testlerin envanteri
2. `now=` seam'lerinin deterministik hale getirilmesi
3. `result is not None` tipi zayıf assertion'ların davranışsal kontrata çekilmesi

**Definition of Done**
- flaky / date-sensitive test kümeleri yazılı envanterle görünürdür
- en az ilk tranche seam fix + behavior-first assertion güçlendirmesi merge edilir
- suite gerçek deterministik kontrata biraz daha yaklaşır; fake-green alan daralır

## 6. Sonra

`PB-3` kapandıktan sonraki doğru sıra:

1. `PB-4` support-surface widening decisions
2. `PB-5` adapter-path cost/evidence completeness
3. `PB-6` general-purpose expansion gap map

## 7. Riskler

| Risk | Etki | Önlem |
|---|---|---|
| Küçük correctness fix'i support widening gibi sunmak | Orta | status + docs boundary'yi dar tut |
| `PB-1` için stale backlog üzerinde çalışmak | Orta | canlı testle doğrula, sonra status'u düzelt |
| Deterministic test hygiene işinde scope creep | Yüksek | `PB-3`ü seam inventory + küçük tranche fix'ler olarak dilimle |
| Zayıf testlerle fake green oluşması | Yüksek | behavior-first assertions ve smoke kanıtı zorunlu |

## 8. Anlık Öncelik

Bugünden itibaren doğru sıra:

1. `PB-3` deterministic test hygiene / time seams

## 9. Güncelleme Protokolü

Her merge sonrası bu dosyada en az şu alanlar güncellenecek:

- aktif slice
- tamamlanan slice'ın durumu
- issue / PR / kanıt referansı
- yeni risk veya deferred notu
- sıradaki tek aktif hat
