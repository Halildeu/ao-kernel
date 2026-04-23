# PB-7.3 — PRJ-KERNEL-API Write-side Widening Decision

**Status:** Completed (decision: `stay_deferred`)  
**Date:** 2026-04-23  
**Tracker:** [#219](https://github.com/Halildeu/ao-kernel/issues/219)  
**Active issue:** [#285](https://github.com/Halildeu/ao-kernel/issues/285)

## Amaç

`PRJ-KERNEL-API` write-side action widening
(`project_status`, `roadmap_follow`, `roadmap_finish`) için support-boundary
kararını güncel runtime/test kanıtıyla tekilleştirmek.

Bu slice runtime davranışı genişletmez; widening öncesi kapıların durumunu
kanıtla değerlendirir.

## Kapsam

1. runtime registry / entrypoint owner doğrulaması
2. kernel-api manifest ve bootstrap tranche doğrulaması
3. write-side action precondition gate değerlendirmesi
4. `PUBLIC-BETA` + `SUPPORT-BOUNDARY` parity güncellemesi

## Kapsam Dışı

1. write-side action implementation widening
2. support tier yükseltmesini bu slice içinde açmak
3. `system_status` / `doc_nav_check` read-only tranche kapsamını değiştirmek

## Canlı Kanıt Özeti

Çalıştırılan komutlar:

```bash
pytest -q tests/test_extension_dispatch.py::TestBootstrapKernelApiExtension::test_kernel_api_minimum_actions_registered_by_default
pytest -q tests/test_extension_dispatch.py::TestBootstrapKernelApiExtension::test_kernel_api_system_status_payload_is_bounded tests/test_extension_dispatch.py::TestBootstrapKernelApiExtension::test_kernel_api_doc_nav_check_reports_clean_runtime_refs
pytest -q tests/test_extension_loader.py::TestBundledDefaults::test_kernel_api_manifest_is_minimum_runtime_backed
python3 -m ao_kernel doctor
python3 - <<'PY'
from ao_kernel.extensions.loader import ExtensionRegistry
r = ExtensionRegistry(); r.load_from_defaults()
for action in ['project_status','roadmap_follow','roadmap_finish','system_status','doc_nav_check']:
    owners = [m.extension_id for m in r.find_by_entrypoint(action)]
    print(action, owners)
PY
```

Özet:

1. kernel-api bootstrap testleri yeşil; runtime-backed yüzey yalnız
   `system_status` ve `doc_nav_check`.
2. `project_status`, `roadmap_follow`, `roadmap_finish` için owner bulunmuyor;
   runtime entrypoint registry bu action'ları hâlâ açmıyor.
3. `ao-kernel doctor` çıktısı geniş inventory uyarılarına rağmen
   shipped minimum tranche'i doğruluyor (`runtime_backed_ids` içinde
   `PRJ-KERNEL-API` var).
4. Write-side widening için governance/behavior/safety/rollback kapıları
   promoted support kontratı seviyesinde hâlâ tamamlanmış değil.

## Karar

**Final verdict:** `stay_deferred`.

Gerekçe:

1. Runtime manifest + handler yüzeyi bilerek minimum read-only tranche ile
   sınırlandırılmış durumda.
2. Write-side action'lar registry'de açılmadığı için support widening için
   gerekli behavior/safety/rollback kanıt zinciri oluşmuyor.
3. Docs parity korunarak fake widening riski engelleniyor.

## Sonraki Durum

1. Aktif widening implementation slice açılmadı.
2. Support boundary dar read-only tranche'ta korunuyor.
3. Yeni widening hattı yalnız explicit runtime implementation + behavior-first
   test + rollback/runbook paketi ile açılabilir.

## DoD

1. karar tekilleşti: `stay_deferred`
2. status SSOT aktif slice gerçeğiyle güncellendi
3. Public support dokümanları kararla aynı dili konuşuyor
