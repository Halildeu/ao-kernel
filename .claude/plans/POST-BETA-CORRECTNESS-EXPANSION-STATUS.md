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
- **Aktif slice planı:** `.claude/plans/PB-5-ADAPTER-PATH-COST-EVIDENCE-COMPLETENESS.md`
- **Public Beta support boundary:** `docs/PUBLIC-BETA.md`
- **Known bugs registry:** `docs/KNOWN-BUGS.md`
- **GitHub milestone:** [Post-Beta Correctness and Expansion](https://github.com/Halildeu/ao-kernel/milestone/2)
- **GitHub tracker issue:** [#219](https://github.com/Halildeu/ao-kernel/issues/219)
- **Aktif issue:** [#238](https://github.com/Halildeu/ao-kernel/issues/238)

## 2. Başlangıç Gerçeği

- `WP-5` ile `WP-9` production hardening programı `main` üzerinde kapanmıştır.
- Repo bugün dar ama kanıtlı bir Public Beta / governed runtime yüzeyine sahiptir.
- Support boundary hâlâ bilerek dardır; `review_ai_flow + codex-stub` shipped
  baseline, gerçek adapter lane'leri ise operator-managed beta durumundadır.
- Public Beta closeout sonrası aktif program odağı artık defer edilmiş ilk
  correctness boşlukları değil; support-surface widening closeout'u bitmiş,
  aktif odak adapter-path cost/evidence completeness ve onun arkasındaki daha
  geniş expansion gap'lerdir.
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
| `PB-5` adapter-path cost/evidence completeness | In progress ([#238](https://github.com/Halildeu/ao-kernel/issues/238)) | `cost_usd` reconcile ve evidence completeness boşluklarını tek anlamlı kontrata indirmek | truth audit + tests/evidence parity |
| `PB-6` general-purpose expansion gap map | Planned | narrow beta'dan daha geniş production platform çizgisine geçiş için önkoşulları tabloya dökmek | written gap map + ordered backlog |

## 5. Şimdi

### `PB-5` — adapter-path cost/evidence completeness

**Neden şimdi**
- `PB-4` closeout-ready karardan çıkıp fiilen kapanmıştır; support surface
  widening tarafında bugünkü boundary artık yazılı ve tek anlamlıdır.
- Bir sonraki gerçek risk alanı, adapter-path cost ve evidence yüzeyinde kalan
  truth gap'tir: bazı docs satırları bu alanı deferred söylerken bazı
  benchmark/test yüzeyleri kapanmış contract gibi anlatmaktadır.
- Bu slice'ın işi yeni promise eklemek değil; cost/evidence sözleşmesini
  authoritative hale getirmektir.

**Aktif kapsam**
1. adapter-path `cost_usd` reconcile anlatısının truth audit'i
2. evidence/event/materialization completeness yüzeyinin truth audit'i
3. docs/runtime/tests/benchmark parity sonucu tek anlamlı verdict üretmek

**Definition of Done**
- adapter-path cost/evidence için tek authoritative contract yazılıdır
- docs/runtime/tests/benchmark aynı sonucu söyler
- gerçek gap varsa sonraki tranche'ler net repro/test planı ile sıralanır

**Anlık ilerleme**
- `PB-5` issue'su açıldı: [#238](https://github.com/Halildeu/ao-kernel/issues/238)
- yaşayan slice planı oluşturuldu:
  `.claude/plans/PB-5-ADAPTER-PATH-COST-EVIDENCE-COMPLETENESS.md`
- tranche 1 truth audit yapıldı; hüküm şu:
  adapter-path cost/evidence runtime hook'u repoda mevcut ve behavior-first
  test/benchmark kanıtı var, fakat public support docs bunu bilerek deferred
  support claim olarak tutuyor
- bugün görünen ana gerilim runtime yokluğu değil; benchmark/operator contract
  ile support-boundary dilinin scope ayrımını her yerde aynı netlikte
  söylememesi
- sıradaki doğru alt adım docs parity patch; runtime semantics değişikliği
  ancak bu temizlendikten sonra gerçek bir completeness gap kalırsa açılacak
- tranche 1 yerel kanıtı toplandı:
  `test_post_adapter_reconcile` `17 passed`,
  `test_cost_marker_idempotency` `12 passed`,
  `test_scorecard_render` `10 passed`;
  full-mode smoke operator prereq yokluğunda `skip` verdi

## 6. Sonra

`PB-5` kapandıktan sonraki doğru sıra:

1. `PB-6` general-purpose expansion gap map

## 7. Riskler

| Risk | Etki | Önlem |
|---|---|---|
| Küçük correctness fix'i support widening gibi sunmak | Orta | status + docs boundary'yi dar tut |
| `PB-1` için stale backlog üzerinde çalışmak | Orta | canlı testle doğrula, sonra status'u düzelt |
| Deterministic test hygiene işinde scope creep | Yüksek | `PB-3`ü seam inventory + küçük tranche fix'ler olarak dilimle |
| Zayıf testlerle fake green oluşması | Yüksek | behavior-first assertions ve smoke kanıtı zorunlu |

## 8. Anlık Öncelik

Bugünden itibaren doğru sıra:

1. `PB-5` adapter-path cost/evidence completeness

## 9. Güncelleme Protokolü

Her merge sonrası bu dosyada en az şu alanlar güncellenecek:

- aktif slice
- tamamlanan slice'ın durumu
- issue / PR / kanıt referansı
- yeni risk veya deferred notu
- sıradaki tek aktif hat
