# PB-7.2 — bug_fix_flow Support-Boundary Graduation Decision

**Status:** Completed (decision: `stay_deferred`)  
**Date:** 2026-04-23  
**Tracker:** [#219](https://github.com/Halildeu/ao-kernel/issues/219)  
**Active issue:** [#283](https://github.com/Halildeu/ao-kernel/issues/283)

## Amaç

`bug_fix_flow` yüzeyinin Public Beta support boundary içinde
genişletilip genişletilmeyeceğini canlı kanıtla karara bağlamak.

Bu slice runtime davranışı genişletmez; önce karar kapısını tekilleştirir.

## Kapsam

1. `bug_fix_flow` workflow/runtime kanıtı
2. benchmark/integration doğrulama çıktıları
3. `PUBLIC-BETA` ve `SUPPORT-BOUNDARY` parity metni
4. status SSOT güncellemesi

## Kapsam Dışı

1. `bug_fix_flow` lane'ini shipped/beta support'e yükseltecek runtime guard
   implementationı
2. `gh-cli-pr` full live remote PR opening widening
3. `PRJ-KERNEL-API` write-side widening

## Canlı Kanıt Özeti

Çalıştırılan komutlar:

```bash
pytest -q tests/test_executor_integration.py -k "open_pr_step_persists_pr_metadata"
pytest -q tests/benchmarks
python3 scripts/gh_cli_pr_smoke.py --output json
python3 scripts/gh_cli_pr_smoke.py --mode live-write --output json
```

Özet:

1. `bug_fix_flow` `open_pr` step metadata/evidence yolu integration testte yeşil.
2. Benchmark paketi yeşil (`15 passed, 1 skipped`), fakat bu lane mock harness
   üzerinden koşar.
3. `gh-cli-pr` preflight smoke yeşil.
4. `gh-cli-pr` live-write path explicit opt-in olmadan fail-closed (`blocked`).
5. Workflow-level `open_pr` adımı hâlâ gerçek `gh pr create` side-effect
   yoludur; support widening için disposable/rollback guardları workflow runtime
   düzeyinde henüz zorunlu kontrata bağlanmış değildir.

## Karar

**Final verdict:** `stay_deferred`.

Gerekçe:

1. Mevcut kanıt `bug_fix_flow` correctness ve artifact zincirini doğruluyor,
   fakat support widening için gereken side-effect safety kapısı henüz workflow
   runtime seviyesinde enforce edilmiş değil.
2. `PB-7.1` ile gelen live-write readiness guard'ları smoke düzeyinde mevcut;
   bu guard'lar tek başına `bug_fix_flow` support tier'ını genişletmeye
   yetmez.
3. Bu nedenle `bug_fix_flow release closure` satırı Public Beta deferred
   boundary'de kalır.

## Sonraki Doğru Hat

`PB-7.3` — `PRJ-KERNEL-API` write-side widening preconditions karar dilimi.

## DoD

1. karar tekilleşti: `stay_deferred`
2. status dosyası aktif issue/aktif slice gerçeğiyle güncellendi
3. public support dokümanları kararla aynı dili konuşuyor
