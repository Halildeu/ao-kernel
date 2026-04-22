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
- **Aktif slice planı:** `.claude/plans/PB-2-BUGFIX-FLOW-PATCH-PREVIEW-CLOSURE.md`
- **Public Beta support boundary:** `docs/PUBLIC-BETA.md`
- **Known bugs registry:** `docs/KNOWN-BUGS.md`
- **GitHub milestone:** [Post-Beta Correctness and Expansion](https://github.com/Halildeu/ao-kernel/milestone/2)
- **GitHub tracker issue:** [#219](https://github.com/Halildeu/ao-kernel/issues/219)
- **Aktif issue:** [#222](https://github.com/Halildeu/ao-kernel/issues/222)

## 2. Başlangıç Gerçeği

- `WP-5` ile `WP-9` production hardening programı `main` üzerinde kapanmıştır.
- Repo bugün dar ama kanıtlı bir Public Beta / governed runtime yüzeyine sahiptir.
- Support boundary hâlâ bilerek dardır; `review_ai_flow + codex-stub` shipped
  baseline, gerçek adapter lane'leri ise operator-managed beta durumundadır.
- Public Beta closeout sonrası hâlâ ayrı correctness işleri vardır:
  `sanitize.py:39`, `compiler.py:139`, `init_cmd.py:30-33`,
  `bug_fix_flow + codex-stub patch_preview`, time-dependent test hygiene ve
  adapter-path cost/evidence completeness.
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
| `PB-2` `bug_fix_flow + codex-stub patch_preview` closure | **Active** ([#222](https://github.com/Halildeu/ao-kernel/issues/222)) | deferred bugfix workflow yüzeyini ya gerçekten çalışır hale getirmek ya da boundary'yi kalıcı daraltmak | workflow repro + decision doc + tests |
| `PB-3` deterministic test hygiene / time seams | Planned | zaman-bağımlı test ve zayıf assertion drift'ini sistematik azaltmak | suite proof + seam inventory |
| `PB-4` support-surface widening decisions | Planned | `gh-cli-pr` full E2E ve operator lane promotion kararlarını kanıtla vermek | smoke/e2e kanıtı + docs parity |
| `PB-5` adapter-path cost/evidence completeness | Planned | `cost_usd` reconcile ve evidence completeness boşluklarını kapatmak | tests + evidence parity |
| `PB-6` general-purpose expansion gap map | Planned | narrow beta'dan daha geniş production platform çizgisine geçiş için önkoşulları tabloya dökmek | written gap map + ordered backlog |

## 5. Şimdi

### `PB-2` — `bug_fix_flow + codex-stub patch_preview` closure

**Neden şimdi**
- `PB-1` için hedeflenen üç defect zaten `main` üzerinde kapanmış durumda;
  bu, canlı testlerle doğrulandı.
- Bundan sonraki en büyük kalan runtime debt, `bug_fix_flow` yüzeyinin ya
  gerçekten kapanması ya da support boundary'den kalıcı biçimde çıkarılmasıdır.

**Aktif kapsam**
1. bundled `bug_fix_flow` workflow yüzeyi
2. `codex-stub` ile `patch_preview` / apply / human gate zinciri
3. docs/test/runtime parity kararı

**Definition of Done**
- bu yüzey ya canlı ve kanıtlı şekilde çalışır hale gelir ya da yanlış destek
  beklentisi bırakmayacak şekilde boundary daraltılır
- workflow repro / test / doc üçlüsü aynı şeyi söyler
- fake demo yüzeyi bırakılmaz

## 6. Sonra

`PB-2` kapandıktan sonraki doğru sıra:

1. `PB-3` deterministic test hygiene / time seams
2. `PB-4` support-surface widening decisions
3. `PB-5` adapter-path cost/evidence completeness

## 7. Riskler

| Risk | Etki | Önlem |
|---|---|---|
| Küçük correctness fix'i support widening gibi sunmak | Orta | status + docs boundary'yi dar tut |
| `PB-1` için stale backlog üzerinde çalışmak | Orta | canlı testle doğrula, sonra status'u düzelt |
| Deferred bugfix closure sırasında yeniden kapsam kayması | Yüksek | `PB-2`yi ayrıca slice'la |
| Zayıf testlerle fake green oluşması | Yüksek | behavior-first assertions ve smoke kanıtı zorunlu |

## 8. Anlık Öncelik

Bugünden itibaren doğru sıra:

1. `PB-2` `bug_fix_flow + codex-stub patch_preview` closure

## 9. Güncelleme Protokolü

Her merge sonrası bu dosyada en az şu alanlar güncellenecek:

- aktif slice
- tamamlanan slice'ın durumu
- issue / PR / kanıt referansı
- yeni risk veya deferred notu
- sıradaki tek aktif hat
