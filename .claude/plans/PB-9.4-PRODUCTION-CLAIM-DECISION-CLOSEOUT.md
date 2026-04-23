# PB-9.4 — Production Claim Decision Closeout

**Durum:** Completed (`PB-9.4`)  
**Issue:** [#312](https://github.com/Halildeu/ao-kernel/issues/312)  
**Tracker:** [#302](https://github.com/Halildeu/ao-kernel/issues/302)  
**Karar tarihi:** 2026-04-23

## 1) Karar

`ao-kernel` icin production claim karari:

1. `stay_beta_operator_managed`

Bu karar platformun "hic calismiyor" oldugu anlamina gelmez. Karar,
destek sinirinin kontrollu ve kanita dayali sekilde dar tutulmasi anlamina
gelir.

## 2) Karar Giris Kaniti (Canli)

Bu dilimde tekrar uretilen paket:

```bash
python3 scripts/kernel_api_write_smoke.py --output json
python3 scripts/gh_cli_pr_smoke.py --output json
python3 scripts/claude_code_cli_smoke.py --output json
python3 scripts/gh_cli_pr_smoke.py --mode live-write --allow-live-write --head main --base main --output json
python3 -m pytest -q tests/test_kernel_api_write_smoke.py tests/test_gh_cli_pr_smoke.py tests/test_executor_policy_rollout_v311_p2.py
python3 scripts/packaging_smoke.py
```

Gozlem:

1. `kernel_api_write_smoke`: `overall_status=pass` ve write contract check seti
   tamami `pass`.
2. `gh_cli_pr_smoke` preflight: `overall_status=pass`.
3. `claude_code_cli_smoke`: `overall_status=pass`.
4. `gh_cli_pr_smoke` live-write denemesi (`--head main --base main`):
   fail-closed `blocked` (`gh_pr_live_write_same_head_base`), yani explicit
   guard davranisi aktif.
5. Targeted behavior test paketi: `28 passed`.
6. Packaging smoke: wheel-install yolunda entrypoint + `demo_review` tamam
   (`final state: completed`).

## 3) Gate Degerlendirmesi

| Gate | Sonuc | Not |
|---|---|---|
| G1 Truth parity | pass | `PUBLIC-BETA`, `SUPPORT-BOUNDARY`, `OPERATIONS-RUNBOOK` ayni tier sinirini tasiyor |
| G2 Prerequisite determinism | pass | operator smoke komutlari tekrar uretilir ve rapor formati deterministik |
| G3 Behavior + evidence completeness | pass (beta scope) | write-side contract + policy rollout testleri + lane smoke kaniti var |
| G4 Rollback/incident readiness | bounded pass | side-effect lane karar akisi runbook'ta net; live-write genel destek degil, explicit guard altinda |
| G5 Governance enforcement | pass | required CI zinciri + packaging smoke PR turunda gecerli |
| G6 Decision record | pass | bu closeout notu + roadmap/status parity + issue/tracker senkronu |

## 4) Neden `promote` degil?

1. `gh-cli-pr` remote live PR opening hala support boundary'de deferred.
2. `bug_fix_flow` release closure hala deferred.
3. Public support claim'i deterministic shipped baseline + operator-managed beta
   lane'ler disina genisletmek icin ek widening karari/implementationi yok.
4. Extension envanterinin buyuk kismi halen quarantine/contract-only; bu durum
   tek basina blocker degil ama "general-purpose production" iddiasi icin
   yeterli promotion sinyali degil.

## 5) Boundary Sonucu

1. Shipped baseline iddiasi korunur.
2. `claude-code-cli`, `gh-cli-pr`, `PRJ-KERNEL-API` write-side lane'leri
   `Beta (operator-managed)` tier'inda kalir.
3. Deferred satirlari aynen korunur; bu dilimde widening yoktur.

## 6) Closeout

1. `PB-9.1..PB-9.4` karar kayitlari tamamlandi.
2. `PB-9` tracker kapanisina izin veren karar kaydi olustu.
3. Sonraki adim, yeni backlog/program acilacaksa ayri tracker ile acilmalidir;
   `PB-9` icinde yeni widening dilimi acilmaz.

