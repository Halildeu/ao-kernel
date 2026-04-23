# GP-1.2 — gh-cli-pr Live-Write Disposable Contract Decision

**Status:** Completed (`stay_preflight`)  
**Date:** 2026-04-23  
**Tracker:** [#316](https://github.com/Halildeu/ao-kernel/issues/316)  
**Slice issue:** [#318](https://github.com/Halildeu/ao-kernel/issues/318)

## Amaç

`gh-cli-pr` lane için preflight-only sınırından live-write widening kararına
geçmeden önce disposable/rollback kontratını canlı kanıtla doğrulamak.

## Çalıştırılan Kanıt Paketi

1. Preflight smoke (side-effect-safe):
   - `python3 scripts/gh_cli_pr_smoke.py --mode preflight --output json --report-path /tmp/gp12-gh-preflight.report.json`
   - Sonuç: `overall_status=pass`
2. Fail-closed guard smoke (head/base eşit):
   - `python3 scripts/gh_cli_pr_smoke.py --mode live-write --allow-live-write --head main --base main --output json --report-path /tmp/gp12-gh-livewrite-guard.report.json`
   - Sonuç: `overall_status=blocked`, finding: `gh_pr_live_write_same_head_base`
3. Controlled live-write chain (create -> verify -> rollback):
   - Geçici branch: `smoke/gp12-livewrite-20260423-221549`
   - `python3 scripts/gh_cli_pr_smoke.py --mode live-write --allow-live-write --head smoke/gp12-livewrite-20260423-221549 --base main --require-disposable-keyword ao-kernel --output json --report-path /tmp/gp12-gh-livewrite-pass.report.json`
   - Sonuç: `overall_status=pass`
   - Canlı PR: [#321](https://github.com/Halildeu/ao-kernel/pull/321) (`draft`, sonra `CLOSED`)
   - Cleanup: geçici branch local+remote silindi

## Karar

**Verdict: `stay_preflight`**

## Gerekçe

1. Create/verify/rollback zinciri canlı olarak çalışıyor, yani helper lane
   teknik olarak live-write workflow'unu yürütüyor.
2. Ancak doğrulama `Halildeu/ao-kernel` üzerinde, `--require-disposable-keyword ao-kernel`
   override ile yapıldı; bu, default disposable guard (`sandbox`) ile geniş
   public support iddiası için yeterli güvence üretmiyor.
3. Bu nedenle support boundary widening açılmadı; lane
   **Beta (operator-managed preflight + readiness probe)** seviyesinde kalır.

## Sonraki Kapı (Promotion için)

1. Disposable target repo sözleşmesi (isimlendirme + yaratma/temizleme politikası)
   yazılı ve tekrar üretilebilir hale getirilmeli.
2. Live-write prova paketi disposable repo üzerinde aynı evidence formatıyla
   (`--report-path`) düzenli çalıştırılmalı.
3. Bu kanıtlar tamamlanmadan `live gh-cli-pr PR opening` satırı deferred'dan
   çıkarılmamalı.
