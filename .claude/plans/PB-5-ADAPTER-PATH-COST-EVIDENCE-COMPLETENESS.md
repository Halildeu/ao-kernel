# PB-5 — adapter-path cost/evidence completeness

**Durum tarihi:** 2026-04-22
**İlişkili issue:** [#238](https://github.com/Halildeu/ao-kernel/issues/238)
**Üst tracker:** [#219](https://github.com/Halildeu/ao-kernel/issues/219)
**Durum:** Completed

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

## İlk Tranche — Truth Audit Bulguları

**Audit tarihi:** 2026-04-22

| Surface | Current claim | Runtime truth | Evidence source | Conflict | Verdict |
|---|---|---|---|---|---|
| `docs/PUBLIC-BETA.md` | `adapter-path cost_usd reconcile` deferred | Runtime hook'un yok olduğunu değil, public support claim'in dar tutulduğunu söylüyor | `PUBLIC-BETA.md`, `SUPPORT-BOUNDARY.md` | Terminoloji kolay yanlış okunur | support-boundary statement |
| `docs/SUPPORT-BOUNDARY.md` | deferred / not a support claim | Benchmark/internal contract'i reddetmiyor; shipped baseline dışı bırakıyor | `SUPPORT-BOUNDARY.md` | `Deferred` ifadesi implementation eksikliği gibi okunabilir | support-boundary statement |
| `docs/BENCHMARK-SUITE.md` | v3.7 F2 bu gap'i kapattı | Benchmark/full-mode bağlamında `post_adapter_reconcile` event-backed çalışıyor | `BENCHMARK-SUITE.md`, `BENCHMARK-FULL-MODE.md` | Public support ile internal benchmark contract aynı cümle ailesinde değil | benchmark-scoped closure |
| `docs/BENCHMARK-FULL-MODE.md` | operator-only validation lane, event-backed reconcile | Full-mode smoke yalnız adapter-path reconcile'in çalıştığını kanıtlıyor; blanket production claim vermiyor | `BENCHMARK-FULL-MODE.md`, `tests/benchmarks/test_full_mode_smoke.py` | Düşük; scope-out notları açık | operator validation only |
| `ao_kernel/cost/middleware.py::post_adapter_reconcile` | adapter-path reconcile contract | `policy.enabled=true` ve `cost_actual` varsa ledger + budget + evidence emit akışı implement edilmiş | `ao_kernel/cost/middleware.py` | Conflict yok | implemented runtime contract |
| `ao_kernel/executor/executor.py` adapter path | reconcile-before-terminal ordering | Executor cost policy açıksa `post_adapter_reconcile`'i terminal event öncesi çağırıyor | `ao_kernel/executor/executor.py` | Conflict yok | wired in runtime |
| `tests/test_post_adapter_reconcile.py` | core contract tests | dormant, happy path, usage-missing, idempotency, wire-format davranışları pinli | `tests/test_post_adapter_reconcile.py` | Contract coverage güçlü | behavior pinned |
| `tests/benchmarks/test_full_mode_smoke.py` | full-mode smoke | `llm_spend_recorded(source=\"adapter_path\")` sinyalini gerçek invoke_cli hattında pinliyor | `tests/benchmarks/test_full_mode_smoke.py` | Operator prereq bağımlı | high-signal operator proof |
| scorecard consumer/render | `real_adapter` label | Event-backed adapter-path reconcile'i tüketiyor; vendor billing claim'i yapmıyor | `ao_kernel/_internal/scorecard/collector.py`, `render.py`, `tests/test_scorecard_render.py` | İsimlendirme tek başına yanlış okunabilir ama wording daraltılmış | downstream consumer aligned |

## İlk Tranche — Verdict

1. `post_adapter_reconcile` runtime hook'u ve onun evidence emit davranışı
   repoda **mevcuttur**; bu yüzey "runtime yok" türü bir boşluk değildir.
2. `PUBLIC-BETA.md` ve `SUPPORT-BOUNDARY.md` içindeki `Deferred` satırı,
   core hook'un eksik olduğunu değil, bunun bugün için **public support claim**
   olmadığını söylemektedir.
3. Gerilim, esas olarak **scope/terminology parity** problemidir:
   benchmark docs "gap closed" derken internal benchmark/operator doğrulama
   kontratını anlatıyor; support docs ise shipped/public support sınırını
   anlatıyor.
4. Bu tranche'in hükmü: **ana sorun docs/parity netliği**; tranche 2'nin doğru
   yönü önce operator-facing ve benchmark-facing anlatıyı tek anlamlı hale
   getirmektir. Runtime semantics değişikliği ancak bu ayrımdan sonra gerçek
   bir evidence completeness boşluğu kalırsa açılmalıdır.

## İlk Tranche — Yerel Kanıt

Çalıştırılan komutlar:

```bash
python3 -m pytest tests/test_post_adapter_reconcile.py -q
python3 -m pytest tests/test_cost_marker_idempotency.py -q
python3 -m pytest tests/test_scorecard_render.py -q
python3 -m pytest tests/benchmarks/test_full_mode_smoke.py -q -m full_mode --benchmark-mode=full
```

Sonuç özeti:

1. `tests/test_post_adapter_reconcile.py` → `17 passed`
2. `tests/test_cost_marker_idempotency.py` → `12 passed`
3. `tests/test_scorecard_render.py` → `10 passed`
4. `tests/benchmarks/test_full_mode_smoke.py` → `1 skipped, 5 deselected`
   - skip, operator/full-mode prereq yokluğunda beklenen davranış; tranche 1
     verdict'ini invalid kılmıyor ama live operator proof olarak sayılmıyor

## İkinci Tranche — Docs Parity Patch

Amaç: support-boundary dili ile benchmark/operator dili arasındaki scope
ayrımını aynı anlamla yazmak; "deferred support claim" ile "runtime hook yok"
yorumunun karışmasını engellemek.

Hedef yüzeyler:

1. `docs/PUBLIC-BETA.md`
2. `docs/SUPPORT-BOUNDARY.md`
3. `docs/BENCHMARK-SUITE.md`
4. `docs/BENCHMARK-FULL-MODE.md`

Bu tranche'de özellikle yapılacaklar:

1. support-facing docs'ta `adapter-path cost_usd reconcile` satırını
   "public support claim deferred" olarak açıklaştırmak
2. benchmark docs'ta "gap closed" cümlesini benchmark/internal contract
   bağlamına sabitlemek
3. `real_adapter` scorecard dilinin support-tier promotion değil, benchmark
   consumer sinyali olduğunu doküman seviyesinde netleştirmek

Bu tranche'de özellikle yapılmayacaklar:

1. runtime semantics değişikliği
2. scorecard/render kodu değişikliği
3. support boundary widening

Yerel kanıt:

```bash
python3 -m pytest tests/test_post_adapter_reconcile.py -q
python3 -m pytest tests/test_scorecard_render.py -q
```

## Closeout Verdict

**Closeout tarihi:** 2026-04-22

Docs parity patch sonrasında yeniden yapılan runtime/test/evidence audit
sonucu:

1. `main` üzerinde ayrı bir `PB-5 tranche 3` runtime/evidence fix hattı
   gerektiren yeni bir boşluk tespit edilmedi.
2. `post_adapter_reconcile` runtime hook'u mevcuttur, executor adapter-path
   akışına wired durumdadır ve downstream scorecard consumer / render yüzeyi
   event-backed sinyali tüketmektedir.
3. Support-boundary ile benchmark/operator dili artık aynı şeyi söylemektedir:
   runtime hook'un varlığı internal/benchmark contract'tir; bu, public support
   claim'i kendiliğinden widen etmez.
4. Bu nedenle `PB-5`in açık kalan kısmı runtime semantics değil, docs parity
   closeout'uydu; o closeout bu slice içinde tamamlanmıştır.

## Closeout Kanıtı

Karar öncesi yeniden koşulan yerel kanıt paketi:

```bash
python3 -m pytest tests/test_post_adapter_reconcile.py -q
python3 -m pytest tests/test_cost_marker_idempotency.py -q
python3 -m pytest tests/test_scorecard_render.py -q
python3 -m pytest tests/benchmarks/test_full_mode_smoke.py -q -m full_mode --benchmark-mode=full
```

Sonuç özeti:

1. `tests/test_post_adapter_reconcile.py` → `17 passed`
2. `tests/test_cost_marker_idempotency.py` → `12 passed`
3. `tests/test_scorecard_render.py` → `10 passed`
4. `tests/benchmarks/test_full_mode_smoke.py` → `1 skipped, 5 deselected`
   - skip, operator/full-mode prerequisite yokluğunda beklenen davranış olarak
     değerlendirildi; public support boundary zaten bu lane'i shipped claim
     yapmamaktadır

## Residual Notlar

1. `tests/benchmarks/test_governed_review.py::TestCostReconcile::test_cost_usd_not_drained_in_fast_mode`
   hâlâ `ADV-001` kalite advisory'si üretmektedir; bu, helper tabanlı assert
   kullanan test-hijyen alanıdır.
2. Bu advisory, `PB-5` kapsamında yeni bir runtime/evidence completeness gap
   sayılmamıştır; deterministic test hygiene / genişleme backlog'unda ele
   alınmalıdır.

## Kabul Kriterleri

1. Adapter-path cost/evidence için tek bir authoritative contract yazılıdır.
2. Docs/runtime/tests/benchmark anlatısı aynı sonucu söyler.
3. Eğer gerçek gap runtime veya evidence completeness tarafındaysa, bunun
   repro/test planı ayrı tranche'lerle açıkça sıralanır.
4. Closeout anında kalan deferred alanlar sessizce kaybolmaz; status ve known
   boundary yüzeyinde görünür kalır.

## Sonraki Adım

`PB-5` closeout sonrasındaki doğru sıra `PB-6` general-purpose expansion gap
map'tir. Bir sonraki canlı slice, dar Public Beta'dan daha geniş production
platform çizgisine geçiş için eksik adapter/runtime/ops alanlarını tabloya
dökecektir.
