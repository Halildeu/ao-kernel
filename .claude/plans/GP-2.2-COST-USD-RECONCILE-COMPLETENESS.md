# GP-2.2 — Adapter-Path `cost_usd` Reconcile Completeness

**Status:** Active  
**Date:** 2026-04-23  
**Tracker:** [#333](https://github.com/Halildeu/ao-kernel/issues/333)  
**Parent:** `.claude/plans/GP-2-DEFERRED-SUPPORT-LANES-REPRIORITIZATION.md`

## Amaç

`GP-2.1` ordering kararındaki `Now` lane'i dar kapsamda uygulamak:
adapter-path `cost_usd` reconcile davranışını deterministic test + evidence
assertion seviyesinde kapatmak.

Bu tranche support widening kararı üretmez; yalnız completeness gap'ini kapatır.

## Başlangıç Bulgusu

1. `PUBLIC-BETA` içinde adapter-path `cost_usd` reconcile satırı deferred.
2. Runtime'da `post_adapter_reconcile` hook'u mevcut (`executor` ve benchmark lane).
3. Gap: lane'in support-tier kararına temel olacak davranışsal/evidence
   assertion seti henüz tek contract altında kapanmış değil.

## Dar Kapsam (Implementation Slices)

### `GP-2.2a` — Runtime/evidence truth capture (Active)

- Hedef: reconcile akışında hangi alanların canonical assert edilmesi gerektiğini
  çalışma kodundan çıkarmak.
- Hedef dosya alanı:
  - `ao_kernel/executor/executor.py`
  - `ao_kernel/cost/middleware.py`
  - `tests/test_post_adapter_reconcile.py`
  - `tests/benchmarks/*` (özellikle cost-source/reconcile assertion katmanı)
- Çıktı: kapsamı sınırlı assertion matrisi (`required` vs `nice-to-have`)

### `GP-2.2b` — Deterministic assertion upgrade (Pending)

- Hedef: `cost_usd` reconcile davranışı için doğrudan kırmızı/yeşil davranış
  testi eklemek veya mevcut testleri güçlendirmek.
- DoD:
  1. en az bir negatif (reconcile yok/bozuk) yol testte yakalanır
  2. en az bir pozitif yol evidence/cost alanlarını açık assert eder

### `GP-2.2c` — Minimum runtime patch (Conditional)

- Hedef: yalnız testlerle kapanmayan gerçek runtime gap varsa minimal kod düzeltmesi.
- Kural: adapter-path dışına yayılma yok; scope creep blok.

### `GP-2.2d` — Docs/status parity closeout (Pending)

- Hedef: `PUBLIC-BETA` ve status satırlarında tranche sonucu gerçek davranışla hizalı.
- Kural: support tier promotion iddiası yok; karar notu düzeyinde netlik.

## Zorunlu Kanıt Komutları

1. `python3 -m pytest -q tests/test_post_adapter_reconcile.py`
2. `python3 -m pytest -q tests/benchmarks/test_governed_review.py tests/benchmarks/test_governed_bugfix.py`
3. `python3 scripts/truth_inventory_ratchet.py --output json`

## Çıkış Kriteri

1. Reconcile completeness için behavior-first assertion paketi yeşil.
2. Runtime patch gerekiyorsa minimal ve lane-scope içinde.
3. Status SSOT + docs parity güncel.
