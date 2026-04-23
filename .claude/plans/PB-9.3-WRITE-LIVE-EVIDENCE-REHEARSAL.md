# PB-9.3 — Write/Live Lane Evidence Rehearsal

**Durum:** Active (`PB-9.3`)  
**Issue:** [#309](https://github.com/Halildeu/ao-kernel/issues/309)  
**Tracker:** [#302](https://github.com/Halildeu/ao-kernel/issues/302)

## 1) Amaç

Write-side ve live-write tarafinda "calisiyor gibi" degil, tekrar
uretilebilir kanit paketi uretmek.

Bu tranche support widening karari vermez. Yalniz su soruyu kapatir:

1. incident veya release review aninda hangi komutlar ve hangi kanitlar ile
   write/live lane guven sinyali olusturuluyor?
2. hangi sonuc pass, hangi sonuc bounded-blocked sayiliyor?

## 2) Kapsam

1. `PRJ-KERNEL-API` write-side lane icin helper-backed deterministic smoke:
   `scripts/kernel_api_write_smoke.py`
2. `gh-cli-pr` lane icin preflight + optional live-write rehearsal siniri:
   `scripts/gh_cli_pr_smoke.py`
3. policy evidence semantigi icin mevcut behavior testlerinin yeniden
   calistirilabilir kanit paketi olarak pinlenmesi.

## 3) Deterministik Kanit Paketi (Zorunlu)

Repo root'tan:

```bash
python3 scripts/kernel_api_write_smoke.py --output json
python3 scripts/gh_cli_pr_smoke.py --output json
python3 -m pytest -q \
  tests/test_kernel_api_write_smoke.py \
  tests/test_gh_cli_pr_smoke.py \
  tests/test_executor_policy_rollout_v311_p2.py
```

Bu paket her ortamda side-effect-safe tekrar edilebilir olmalidir.

## 4) Optional Live-Write Rehearsal (Disposable Sandbox)

Yalniz disposable repo + explicit opt-in ile:

```bash
python3 scripts/gh_cli_pr_smoke.py \
  --mode live-write \
  --allow-live-write \
  --head <disposable-head-branch> \
  --base <disposable-base-branch> \
  --output json
```

Beklenen:

1. `pr_live_write`, `pr_live_write_verify`, `pr_live_write_rollback` check'leri
   birlikte `pass` doner, veya
2. disposable guard nedeniyle lane bilincli `blocked` doner
   (`gh_pr_live_write_repo_not_disposable`).

`--keep-live-write-pr-open` sonucu riskli kabul edilir; widening sinyali sayilmaz.

## 5) Kabul Kriterleri

| Gate | Kriter |
|---|---|
| Kernel API write smoke | `overall_status=pass`; check seti (`project_status_*`, `roadmap_follow_conflict_takeover`, `roadmap_finish_idempotent`, `write_audit_artifacts`) pass |
| gh-cli-pr preflight smoke | `overall_status=pass` ve `pr_dry_run` pass |
| Policy evidence testleri | ilgili pytest paketi green; command-policy rollout semantigi regress etmez |
| Live-write rehearsal (optional) | Disposable ortamda create->verify->rollback zinciri pass ise kayit altina alinir; degilse bounded-blocked olarak raporlanir |

## 6) Kanit Artefaktlari

1. `scripts/kernel_api_write_smoke.py` JSON raporu (`checks`, `findings`,
   `artifacts`)
2. `scripts/gh_cli_pr_smoke.py` JSON raporu (`checks`, `findings`)
3. pytest sonucu (policy rollout + lane smoke testleri)
4. Ops runbook parity:
   - `docs/OPERATIONS-RUNBOOK.md`
   - `docs/PUBLIC-BETA.md`
   - `docs/SUPPORT-BOUNDARY.md`

## 7) Karar Siniri

Bu tranche kapanisinda yalniz su karar verilir:

1. write/live lane evidence paketi incident-ready mi degil mi?

Asagidaki kararlar bu tranche'in disindadir:

1. support tier widening
2. live remote PR opening'i public support'e yukselme
3. `stay_beta_operator_managed` sinirinin kaldirilmasi

