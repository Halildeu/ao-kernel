# PB-6.4c — gh-cli-pr Live Write Lane Graduation Preconditions

**Status:** Completed (decision: `stay_preflight`)  
**Date:** 2026-04-23  
**Parent:** `PB-6` / `PB-6.4`  
**Parent issue:** [#243](https://github.com/Halildeu/ao-kernel/issues/243)  
**Active issue:** [#271](https://github.com/Halildeu/ao-kernel/issues/271)

## Amaç

`gh-cli-pr` lane için mevcut `preflight-only` desteği ile gerçek
`live write` (remote PR opening) desteği arasındaki kapıları yazılı, test
edilebilir ve denetlenebilir bir karar dilimine indirmek.

## Kapsam

1. `preflight-only` ve `live write` lane sınırının kesin tanımı
2. disposable sandbox ve side-effect boundary sözleşmesi
3. rollback + evidence completeness kapıları
4. operator prerequisite ve failure-mode karar matrisi
5. tekil karar çıktısı: `stay_preflight` veya `promotion_candidate_live_write`

## Kapsam Dışı

1. bu slice içinde runtime widening implementation yapmak
2. gerçek remote PR opening support tier'ını doğrudan yükseltmek
3. workflow/adapter kodu veya policy semantics değiştirmek

## Canlı Baseline Kanıtı

Gözlem (2026-04-23):

1. `python3 scripts/gh_cli_pr_smoke.py --output json` -> `overall_status=pass`
2. smoke yüzeyi `gh pr create --dry-run` ile sınırlıdır
3. canlı remote write side-effect kanıtı henüz support boundary içinde değildir
4. auth/repo visibility ve manifest contract adımları geçmektedir; fakat bu
   kanıt write-side side-effect güvenliğini doğrulamaz

Bu baseline, `live write` promotion kararı için tek başına yeterli değildir.

## Graduation Gate'leri (Final)

1. lane boundary gate:
   - preflight ile live write arasındaki sınır davranışsal olarak pinlenmiş mi?
2. sandbox gate:
   - disposable workspace ve cleanup/teardown sözleşmesi açık mı?
3. side-effect gate:
   - yanlış repo/branch/base senaryolarında fail-closed davranış var mı?
4. rollback gate:
   - başarısız write akışı sonrası geri dönüş adımları deterministik mi?
5. evidence gate:
   - PR metadata, event timeline ve karar izleri eksiksiz toplanıyor mu?
6. docs parity gate:
   - `PUBLIC-BETA`, `SUPPORT-BOUNDARY`, `OPERATIONS-RUNBOOK` aynı şeyi söylüyor mu?

| Gate | Durum | Not |
|---|---|---|
| Lane boundary gate | `pass` (bounded) | preflight-only sınırı ve live-write dışı boundary yazılı |
| Sandbox gate | `fail` | disposable sandbox + cleanup contract canlı write için henüz kanıtlı değil |
| Side-effect gate | `fail` | yanlış repo/branch/base write riskleri için runtime guard kanıtı yok |
| Rollback gate | `fail` | live write failure sonrası geri dönüş zinciri testli değil |
| Evidence gate | `inconclusive` | preflight evidence var; live write event/evidence completeness yok |
| Docs parity gate | `pass` | dokümanlar lane'i beta/preflight sınırında tutuyor |

## Failure-Mode Matrisi (Final)

| Failure mode | Etki | Karar |
|---|---|---|
| preflight geçer, live write senaryosu kanıtsız | yanlış güven | `stay_preflight` |
| yanlış repo/branch'e write riski | yüksek side-effect | `stay_preflight`; guard contract zorunlu |
| rollback adımları eksik | operasyonel risk | `stay_preflight` |
| evidence eksikliği (`pr_opened`/metadata boşluğu) | audit zayıf | `stay_preflight` |
| tüm gate'ler karşılanır ve tekrar edilebilir | risk düşer | `promotion_candidate_live_write` değerlendirmesi açılabilir |

## Karar Çıkışı

Bu slice kapanış kararı:

1. Karar: `stay_preflight`
2. Gerekçe:
   - canlı smoke yalnız `preflight-only` yüzeyini doğruluyor
   - live write lane için side-effect/rollback/sandbox kapıları karşılanmadı
   - audit/evidence zinciri live write seviyesinde henüz kanıtlı değil
3. Sınır:
   - `gh-cli-pr` lane support tier'i `Beta (operator-managed preflight only)`
     olarak kalır
   - gerçek remote PR opening support boundary'ye alınmaz
4. Sonraki adım:
   - `PB-6.4d` queued hold slice'ı aktif sıraya alınır
   - live write widening ancak ayrı implementation + governance paketinden
     sonra yeniden değerlendirilir

## DoD

1. gate checklist ve failure-mode matrisi finalize edilmiş
2. preflight/live boundary testlenebilir sözleşme halinde yazılmış
3. tek karar çıktısı ve sonraki dar adım net
4. status SSOT ve issue yüzeyi aynı kararı taşıyor
