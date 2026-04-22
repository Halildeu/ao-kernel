# PB-3 — deterministic test hygiene / time seams

**Durum tarihi:** 2026-04-22
**İlişkili issue:** [#226](https://github.com/Halildeu/ao-kernel/issues/226)
**Üst tracker:** [#219](https://github.com/Halildeu/ao-kernel/issues/219)
**Durum:** In progress

## Amaç

Post-beta correctness hattında fake-green riskini azaltmak: zayıf test
assertion'larını davranışsal kontrata çekmek, zaman-bağımlı seam'leri görünür
kılmak ve deterministik olmayan test yüzeylerini küçük tranche'lerle kapatmak.

## Bu Slice'ın Sınırı

- zayıf `result is not None` / benzeri düşük sinyalli assertion alanları
- time-dependent test seam envanteri
- uygun yerlerde `now=` veya eşdeğer deterministik seam kullanımı

## Kapsam Dışı

- support boundary widening
- adapter-path `cost_usd` / evidence completeness closure
- genel amaçlı production expansion gap map
- yeni runtime feature ekleme

## İlk Tranche

1. `tests/test_intent_router.py` içindeki zayıf classification assertion'larını
   davranışsal sonuca çekmek
2. `tests/test_config.py` workspace root kontratını doğrudan path eşitliği ile
   pinlemek
3. `tests/test_context_pack_ref_plumbing.py` adapter envelope override çıktısını
   tam sözleşme seviyesinde doğrulamak

## Kabul Kriterleri

1. İlk tranche merge edilir ve ilgili testler hedefli pytest ile kanıtlanır.
2. Status SSOT ve GitHub issue/tracker aktif tranche ile hizalıdır.
3. `PB-3` halen küçük tranche'lerle yürür; time-seam audit tek PR'da
   yığılmaz.
4. Testler artık yalnız “çökmemiş olmayı” değil, beklenen veri sözleşmesini
   doğrular.

## Beklenen Sonraki Adım

İlk tranche merge olduktan sonra doğru devam, time-dependent seam envanterini
somut deterministic fix tranche'lerine bölmektir.

## İkinci Tranche

1. `ao_kernel.coordination.status.build_coordination_status(...)` için opsiyonel
   `now` seam'i eklemek
2. `tests/test_coordination_status.py` içindeki canlı saat kullanımını sabit
   zamana çekmek
3. snapshot `generated_at` alanını da deterministic sözleşme olarak pinlemek

## Üçüncü Tranche

1. `ao_kernel._internal.session.context_store` içinde dağınık `datetime.now(...)`
   çağrılarını mevcut `_now_iso8601()` seam'i ile hizalamak
2. `tests/test_context_store_internal.py` içinde `new_context` ve
   `renew_context` için exact timestamp sözleşmesini pinlemek
3. daha geniş `context_store_coverage` alanını sonraki küçük tranche'lere
   bırakmak

## Dördüncü Tranche

1. `tests/test_context_store_coverage.py` içindeki kalan ad hoc
   `datetime.now(...)` kullanımını sabit zaman helper'ına çekmek
2. `inherit_parent_decisions` ve prune edge testlerini wall-clock'tan
   bağımsız hale getirmek
3. runtime yüzeyine dokunmadan yalnız test deterministikliğini artırmak

## Beşinci Tranche

1. `tests/test_context_store_internal.py` içindeki kalan dört canlı zaman
   kullanımını sabit helper'a toplamak
2. prune / expiry edge testlerini exact sabit timestamp ile çalıştırmak
3. `PB-3` closeout öncesi internal + coverage test yüzeyini aynı zaman
   yaklaşımına hizalamak
