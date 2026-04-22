# PB-3 — deterministic test hygiene / time seams

**Durum tarihi:** 2026-04-22
**İlişkili issue:** [#226](https://github.com/Halildeu/ao-kernel/issues/226)
**Üst tracker:** [#219](https://github.com/Halildeu/ao-kernel/issues/219)
**Durum:** Completed on `main`

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

`PB-3` kapandıktan sonra doğru devam, support boundary widening kararlarını
kanıt temelli olarak ele alan `PB-4` hattına geçmektir.

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

## Closeout

`PB-3` aşağıdaki tranche zinciri ile `main` üzerinde kapanmıştır:

1. `#227` weak assertion cleanup
2. `#228` coordination status `now` seam
3. `#229` `context_store` runtime/internal seam hizası
4. `#230` `context_store_coverage` sabit zaman helper geçişi
5. `#231` `context_store_internal` kalan canlı zaman kullanımlarının kapanışı

## Closeout Kanıtı

Hedefli PB-3 doğrulama kümesi:

```bash
python3 -m pytest \
  tests/test_intent_router.py \
  tests/test_config.py \
  tests/test_context_pack_ref_plumbing.py \
  tests/test_coordination_status.py \
  tests/test_coordination_cli.py \
  tests/test_context_store_internal.py \
  tests/test_context_store_coverage.py \
  tests/test_coordination_takeover_prune.py \
  tests/test_cost_catalog.py \
  tests/test_shared_utils_coverage.py \
  tests/test_memory_tiers.py -q
```

Sonuç: `210 passed in 5.83s`

## Residual Inventory

Kalan `datetime.now(...)` kullanımları closeout audit'inde yeniden tarandı.
Bugün için `PB-3` blocker sayılmayan kalıntılar:

1. `tests/test_coordination_cli.py`
   - relative backdate helper kullanıyor
   - exact timestamp kontratı test etmiyor
2. `tests/test_coordination_takeover_prune.py`
   - geçmişe alma helper'ı yalnız grace/past-grace simülasyonu için var
   - wall-clock çıktısını pinlemiyor
3. `tests/test_cost_catalog.py`
   - stale/fresh kapısı için `now - 1 day` / `now + 30 days` kullanıyor
   - self-contained relative eşik testi, seam eksikliği bugün fake-green üretmiyor
4. `tests/test_shared_utils_coverage.py`
   - round-trip parse testi kendi ürettiği timestamp'i parse ediyor
   - dış wall-clock kontratı yok

Bu kalıntılar yeni flaky sinyal üretmediği sürece ayrı opportunistic cleanup
olarak ele alınacak; `PB-3` tekrar açılmayacak.
