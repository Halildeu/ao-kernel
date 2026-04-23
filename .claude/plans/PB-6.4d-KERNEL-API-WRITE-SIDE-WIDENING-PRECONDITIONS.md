# PB-6.4d — Kernel API Write-side Widening Preconditions

**Status:** Completed (decision: `stay_deferred`)  
**Date:** 2026-04-23  
**Parent:** `PB-6` / `PB-6.4`  
**Parent issue:** [#243](https://github.com/Halildeu/ao-kernel/issues/243)  
**Queue issue:** [#270](https://github.com/Halildeu/ao-kernel/issues/270)

## Amaç

`PRJ-KERNEL-API` write-side action widening için gerekli governance, test ve
support-boundary kapılarını implementation'dan önce yazılı karar dilimi olarak
sabitlemek.

## Kapsam

1. write-side governance/policy contract önkoşulları
2. action-level behavior test ve negative path coverage gereksinimleri
3. support-boundary update gate'leri
4. hold-to-implementation geçiş kriterleri

## Kapsam Dışı

1. bu slice içinde write-side action widening implementation yapmak
2. support tier yükseltmesini doğrudan uygulamak
3. read-only `system_status` / `doc_nav_check` kapsamını değiştirmek

## Başlangıç Durumu

1. `PRJ-KERNEL-API` bugün yalnız read-only iki action ile support boundary'de
   yer alır: `system_status`, `doc_nav_check`
2. `project_status`, `roadmap_follow`, `roadmap_finish` write-side widening
   adayları defer/hold durumundadır

## Hold Kapıları (Final)

| Gate | Sonuç | Kanıt | Değerlendirme |
|---|---|---|---|
| Governance gate | FAIL | `ao_kernel/extensions/handlers/prj_kernel_api.py` yalnız `system_status` ve `doc_nav_check` register ediyor; write-side aday action'lar runtime'a bağlı değil | Write-side widening için action-level fail-closed policy contract henüz yok |
| Behavior gate | FAIL | `pytest -q tests/test_extension_dispatch.py::TestBootstrapKernelApiExtension::test_kernel_api_minimum_actions_registered_by_default` (pass) ile write-side action'ların register edilmediği pinli | Write-side positive/negative/deny behavior test matrisi yok |
| Safety gate | FAIL | `project_status`, `roadmap_follow`, `roadmap_finish` için overwrite/conflict/idempotency sözleşmesi ve testleri yok | Write-side safety semantics tanımsız |
| Docs parity gate | PASS | `docs/PUBLIC-BETA.md` ve `docs/SUPPORT-BOUNDARY.md` write-side action'ları açıkça `Deferred` sınırında tutuyor | Operator-facing boundary doğru ve dürüst |
| Rollback gate | FAIL | Write-side action lane'i açılmadığı için rollback/runbook adımları tanımlı değil | Promotion için rollback/containment yolu önceden yazılmalı |

## Evidence Snapshot

1. Runtime registry çözümleme:
   - `project_status -> missing`
   - `roadmap_follow -> missing`
   - `roadmap_finish -> missing`
   - `system_status -> registered`
   - `doc_nav_check -> registered`
2. Targeted tests:
   - `pytest -q tests/test_extension_dispatch.py::TestBootstrapKernelApiExtension::test_kernel_api_minimum_actions_registered_by_default` -> pass
   - `pytest -q tests/test_extension_loader.py::TestBundledDefaults::test_kernel_api_manifest_is_minimum_runtime_backed` -> pass
3. Boundary docs:
   - `docs/PUBLIC-BETA.md`: write-side kernel-api actions `Deferred`
   - `docs/SUPPORT-BOUNDARY.md`: support boundary read-only iki action ile sınırlı

## Karar

`PRJ-KERNEL-API` write-side widening bu tranche'ta açılmıyor.  
**Final verdict:** `stay_deferred`.

Gerekçe:

1. Runtime + behavior + safety + rollback kapıları write-side için henüz yok.
2. Docs parity kapısı tek başına widening için yeterli değil.
3. Mevcut dar read-only support boundary (`system_status`, `doc_nav_check`)
   korunarak fake support widening riski engelleniyor.

## Sonraki Slice Önkoşulları (Implementation Açmadan Önce)

1. Action-level write contract:
   - her action için input/output schema, write root sınırı, fail-closed policy
2. Behavior-first test matrisi:
   - positive + negative + deny + idempotency + conflict path testleri
3. Safety/rollback:
   - kısmi write başarısızlığı için rollback/compensation adımları ve runbook
4. Support parity:
   - docs + status + tests + smoke zinciri birlikte güncellenmeden boundary widen edilmez

## DoD (Karar Slice)

1. write-side widening gate tablosu finalize edildi
2. karar tekilleşti: `stay_deferred`
3. implementation açılış önkoşulları dar, ölçülebilir ve yazılı bırakıldı
