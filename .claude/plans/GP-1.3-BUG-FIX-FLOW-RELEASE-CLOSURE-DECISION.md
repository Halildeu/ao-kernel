# GP-1.3 — bug_fix_flow Release-Closure Re-Evaluation Decision

**Status:** Completed  
**Date:** 2026-04-23  
**Tracker:** [#316](https://github.com/Halildeu/ao-kernel/issues/316)  
**Issue:** [#322](https://github.com/Halildeu/ao-kernel/issues/322)

## 1. Karar

`bug_fix_flow` release-closure widening kararı bu tranche'te
**`stay_deferred`** olarak teyit edilmiştir.

## 2. Neden

1. `open_pr` adımı workflow seviyesinde explicit guard
   (`AO_KERNEL_ALLOW_GH_CLI_PR_LIVE_WRITE=1`) arkasındadır ve bu safety iyileştirmesi
   tek başına support widening üretmez.
2. Lane için behavior/evidence zinciri canlıdır, ancak support boundary'de
   promised bir default live side-effect contract açılmamıştır.
3. `PB-8.3` closeout kararı (`stay_deferred`) bugün güncel runtime/test/smoke
   kanıtlarıyla yeniden doğrulanmış ve tersine çevrilmesini gerektirecek yeni
   bir sinyal bulunmamıştır.

## 3. Canlı Kanıtlar

Çalıştırılan komutlar:

```bash
python3 -m pytest -q tests/test_multi_step_driver_integration.py -k "open_pr_requires_explicit_live_write_guard or open_pr_failure_preserves_adapter_error_metadata or real_codex_stub_with_mocked_ci_and_open_pr_completes_full_flow"
python3 -m pytest -q tests/test_executor_integration.py -k "open_pr_step_persists_pr_metadata_and_emits_event"
python3 -m pytest -q tests/benchmarks/test_governed_bugfix.py tests/benchmarks/test_governed_review.py
python3 scripts/gh_cli_pr_smoke.py --mode preflight --output json --report-path /tmp/gp13-gh-preflight.report.json
```

Özet sonuç:

1. `multi_step_driver` hedef testleri: `3 passed`
2. `executor` `open_pr` metadata/evidence testi: `1 passed`
3. `governed_bugfix + governed_review` benchmark seti: `10 passed`
4. `gh-cli-pr` preflight smoke: `overall_status=pass`

Not:

`tests/benchmarks/test_governed_bugfix.py` tek başına çağrıldığında scorecard
primary-scenario kontrolü nedeniyle finalize aşamasında fail eder; canonical
komut seti `governed_review` ile birlikte çalıştırılmalıdır.

## 4. Parity Etkisi

1. `docs/PUBLIC-BETA.md` deferred satırı `GP-1.3` teyidi ile hizalıdır.
2. `docs/SUPPORT-BOUNDARY.md` deferred anlatımı `GP-1.3` teyidi ile hizalıdır.
3. Status/roadmap aktif hat `GP-1.4`e devredilir.

## 5. Sonraki Hat

Bir sonraki aktif tranche: `GP-1.4` extension promotion tranche
(`PRJ-CONTEXT-ORCHESTRATION`) — issue [#324](https://github.com/Halildeu/ao-kernel/issues/324).
