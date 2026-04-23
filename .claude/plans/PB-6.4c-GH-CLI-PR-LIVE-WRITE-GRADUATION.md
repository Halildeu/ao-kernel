# PB-6.4c — gh-cli-pr Live Write Lane Graduation Preconditions

**Status:** Active (decision)  
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

## Canlı Başlangıç Baseline

2026-04-23 itibarıyla:

1. `python3 scripts/gh_cli_pr_smoke.py --output json` -> `overall_status=pass`
2. smoke yüzeyi `gh pr create --dry-run` ile sınırlıdır
3. canlı remote write side-effect kanıtı henüz support boundary içinde değildir

Bu baseline, `live write` promotion kararı için tek başına yeterli değildir.

## Graduation Gate'leri (Draft)

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

## Failure-Mode Matrisi (Draft)

| Failure mode | Etki | Karar |
|---|---|---|
| preflight geçer, live write senaryosu kanıtsız | yanlış güven | `stay_preflight` |
| yanlış repo/branch'e write riski | yüksek side-effect | `stay_preflight`; guard contract zorunlu |
| rollback adımları eksik | operasyonel risk | `stay_preflight` |
| evidence eksikliği (`pr_opened`/metadata boşluğu) | audit zayıf | `stay_preflight` |
| tüm gate'ler karşılanır ve tekrar edilebilir | risk düşer | `promotion_candidate_live_write` değerlendirmesi açılabilir |

## DoD

1. gate checklist ve failure-mode matrisi finalize edilmiş
2. preflight/live boundary testlenebilir sözleşme halinde yazılmış
3. tek karar çıktısı ve sonraki dar adım net
4. status SSOT ve issue yüzeyi aynı kararı taşıyor
