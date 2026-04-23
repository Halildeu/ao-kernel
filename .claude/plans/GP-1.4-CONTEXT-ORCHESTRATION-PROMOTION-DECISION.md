# GP-1.4 — PRJ-CONTEXT-ORCHESTRATION Promotion Decision

**Status:** Completed  
**Date:** 2026-04-23  
**Tracker:** [#316](https://github.com/Halildeu/ao-kernel/issues/316)  
**Issue:** [#324](https://github.com/Halildeu/ao-kernel/issues/324)

## 1. Karar

`PRJ-CONTEXT-ORCHESTRATION` için support widening kararı bu tranche'te
**`stay_contract_only`** olarak sabitlenmiştir.

## 2. Teknik Gerekçe

1. Manifest refs temizdir (`remap_candidate_refs=0`, `missing_runtime_refs=0`)
   ve truth tier `contract_only` olarak doğrulanır.
2. Runtime owner/handler hâlâ yoktur:
   - `ao_kernel/extensions/bootstrap.py` içinde default handler listesinde
     `PRJ-CONTEXT-ORCHESTRATION` yoktur.
   - manifestteki `future_handler_contract.module`
     (`ao_kernel/extensions/handlers/prj_context_orchestration.py`) repo içinde
     mevcut değildir.
3. Bu nedenle extension, promotion backlog'ında `promotion_candidate` olarak
   kalabilir; ancak support boundary genişlemesi için gereken runtime-backed
   koşulu karşılanmamıştır.

## 3. Canlı Kanıtlar

Çalıştırılan komutlar:

```bash
python3 -m pytest -q tests/test_extension_loader.py -k "context_orchestration_manifest_is_contract_only_with_clean_refs or truth_summary_pins_kernel_api_promotion_metrics"
python3 -m pytest -q tests/test_extension_truth_ratchet.py
python3 -m pytest -q tests/test_doctor_cmd.py
python3 scripts/truth_inventory_ratchet.py --output json
python3 -m ao_kernel doctor
```

Özet sonuç:

1. Extension loader odak testleri: `2 passed`
2. Truth ratchet test paketi: `4 passed`
3. Doctor report testi: `1 passed`
4. Ratchet çıktısı: `promotion_candidate=["PRJ-CONTEXT-ORCHESTRATION"]`
5. Doctor canlı çıktısı:
   - `runtime_backed=2`
   - `contract_only=1`
   - `quarantined=16`

## 4. Parity Etkisi

1. `docs/PUBLIC-BETA.md` içindeki `PRJ-CONTEXT-ORCHESTRATION` satırı
   `stay_contract_only` kararıyla hizalanır.
2. `docs/SUPPORT-BOUNDARY.md` contract inventory anlatımına `GP-1.4`
   karar notu referansı eklenir.
3. Program aktif hattı `GP-1.5`e devredilir.

## 5. Sonraki Hat

Bir sonraki aktif tranche: `GP-1.5` program closeout decision —
issue [#326](https://github.com/Halildeu/ao-kernel/issues/326).
