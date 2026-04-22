# PB-5 — adapter-path cost/evidence completeness

**Durum tarihi:** 2026-04-22
**İlişkili issue:** [#238](https://github.com/Halildeu/ao-kernel/issues/238)
**Üst tracker:** [#219](https://github.com/Halildeu/ao-kernel/issues/219)
**Durum:** In progress

## Amaç

Post-beta correctness hattındaki bir sonraki gerçek gap, adapter-path cost ve
evidence yüzeyinde kalan truth/completeness boşluklarını tek anlamlı hale
getirmektir. Bu slice'ın işi support boundary'yi sessizce widen etmek değil;
runtime, test, benchmark ve operator-facing docs hangi sözleşmeyi gerçekten
taşıyorsa onu kanıt bazlı sabitlemektir.

## Başlangıç Gerçeği

Bugünkü ana gerçek:

1. Public-facing support boundary dokümanları adapter-path `cost_usd`
   reconcile yüzeyini hâlâ deferred olarak işaretliyor.
2. Buna karşılık benchmark/full-mode ve bazı test yüzeyleri
   `post_adapter_reconcile` hattını kapanmış/event-backed contract gibi
   anlatıyor.
3. Bu, shipped runtime ile docs/test anlatısı arasında cost/evidence odaklı bir
   truth gap riski oluşturuyor.
4. `PB-5` bu gerilimi gerçek davranışa indirip küçük tranche'lerle kapatmak
   için açılmıştır.

## Bu Slice'ın Sınırı

- adapter-path `cost_usd` reconcile anlatısı
- `post_adapter_reconcile` runtime hook'u ve onun evidence/event sözleşmesi
- artifact/materialization ile evidence completeness ilişkisi
- docs/runtime/test/benchmark/CI parity
- eksik kalan alanlar için açık deferred veya known-gap kaydı

## Kapsam Dışı

- yeni adapter capability eklemek
- support boundary'yi shipped baseline dışına widen etmek
- `gh-cli-pr` full E2E remote PR opening
- genel amaçlı production platform expansion gap map (`PB-6`)

## İlk Tranche

1. Truth audit:
   - `docs/PUBLIC-BETA.md`
   - `docs/SUPPORT-BOUNDARY.md`
   - `docs/BENCHMARK-SUITE.md`
   - `docs/BENCHMARK-FULL-MODE.md`
   - `ao_kernel/cost/middleware.py`
   - `ao_kernel/executor/executor.py`
   - `tests/test_post_adapter_reconcile.py`
   - ilgili benchmark/evidence test yüzeyleri
2. Tek anlamlı verdict:
   adapter-path cost/evidence yüzeyi bugün shipped mi, beta mı, deferred mı?
3. Truth audit sonucunu status + issue üzerinde yazılı karar notuna çevirmek.

## Kabul Kriterleri

1. Adapter-path cost/evidence için tek bir authoritative contract yazılıdır.
2. Docs/runtime/tests/benchmark anlatısı aynı sonucu söyler.
3. Eğer gerçek gap runtime veya evidence completeness tarafındaysa, bunun
   repro/test planı ayrı tranche'lerle açıkça sıralanır.
4. Closeout anında kalan deferred alanlar sessizce kaybolmaz; status ve known
   boundary yüzeyinde görünür kalır.

## Beklenen Sonraki Adım

`PB-5` kapandıktan sonraki doğru sıra `PB-6` general-purpose expansion gap map
olacaktır.
