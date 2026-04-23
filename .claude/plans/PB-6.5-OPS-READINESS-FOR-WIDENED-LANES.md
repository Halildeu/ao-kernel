# PB-6.5 — Ops Readiness Gates for Widened Lanes

**Status:** Completed (decision closeout)  
**Date:** 2026-04-23  
**Parent:** `PB-6`  
**Parent issue:** [#243](https://github.com/Halildeu/ao-kernel/issues/243)  
**Decision issue:** [#275](https://github.com/Halildeu/ao-kernel/issues/275)  
**Next active issue:** [#277](https://github.com/Halildeu/ao-kernel/issues/277)

## Amaç

Widening adayları (operator-managed lane veya ileride write-side lane) için
support tier kararı öncesinde zorunlu operasyon kapılarını netleştirmek:

1. incident class + severity + owner sınırı
2. rollback/containment önkoşulları
3. known-bug registry ve support boundary parity
4. lane bazlı operator prerequisite/exit criteria

## Kapsam

1. `claude-code-cli` lane için ops readiness gate tablosu
2. `gh-cli-pr` preflight lane için ops readiness gate tablosu
3. deferred write-side lane'ler için (`gh-cli-pr` live write, `PRJ-KERNEL-API`
   write-side actions) açılış önkoşulu checklist'i
4. runbook/docs parity kontrol listesi (`PUBLIC-BETA`, `SUPPORT-BOUNDARY`,
   `OPERATIONS-RUNBOOK`, `KNOWN-BUGS`, `ROLLBACK`)

## Kapsam Dışı

1. runtime widening implementation
2. support tier promotion'ı doğrudan açmak
3. yeni adapter/handler geliştirmek

## Başlangıç Gerçeği

1. `PB-6.4c` kararı `stay_preflight`: `gh-cli-pr` live write lane açılmadı.
2. `PB-6.4d` kararı `stay_deferred`: kernel-api write-side widening açılmadı.
3. Operator-managed lane'ler (claude-code-cli / gh-cli-pr preflight) canlı
   smoke ile doğrulanabiliyor; fakat widening kararı için ops gates henüz tek
   tabloda toplanmış değil.

## Canlı Kanıt Turu (2026-04-23)

Komutlar:

```bash
python3 -m ao_kernel doctor
python3 scripts/claude_code_cli_smoke.py --output json
python3 scripts/gh_cli_pr_smoke.py --output json
python3 - <<'PY'
from ao_kernel.client import AoKernelClient
c=AoKernelClient()
for name in ["project_status","roadmap_follow","roadmap_finish","system_status","doc_nav_check"]:
    rec=c.action_registry.resolve(name)
    print(f"{name}={'registered' if rec else 'missing'}")
PY
```

Özet:

1. `doctor`: `8 OK, 1 WARN, 0 FAIL` (`runtime_backed=2`, `contract_only=1`,
   `quarantined=16`)
2. `claude_code_cli_smoke`: `overall_status="pass"`
3. `gh_cli_pr_smoke`: `overall_status="pass"` (`pr_dry_run` dahil)
4. kernel-api write-side action'lar runtime'da `missing`:
   `project_status`, `roadmap_follow`, `roadmap_finish`

## Ops Gate Matrisi (Final)

Her lane için aşağıdaki kapılar birlikte değerlendirilir:

1. Incident gate:
   - class/severity/owner açık mı?
2. Rollback gate:
   - lane bozulduğunda containment/rollback adımı tanımlı mı?
3. Known-bug gate:
   - açık riskler registry'de ve support boundary notlarında görünüyor mu?
4. Prerequisite gate:
   - operator'ın lane'i çalıştırmadan önce sağlaması gereken koşullar açık mı?
5. Evidence gate:
   - smoke/test/CI kanıtı reproducible ve lane-level raporlanabilir mi?
6. Docs parity gate:
   - docs yüzeyleri aynı support sınırını konuşuyor mu?

| Lane | Incident | Rollback | Known-bug | Prerequisite | Evidence | Docs parity | Verdict |
|---|---|---|---|---|---|---|---|
| `claude-code-cli` helper lane | PASS | PASS | PASS (bounded) | PASS | PASS | PASS | `promotion_candidate_with_ops_gates` |
| `gh-cli-pr` preflight lane | PASS | PASS | PASS | PASS | PASS | PASS | `stay_beta_operator_managed` |
| `gh-cli-pr` live write lane | FAIL | FAIL | INCONCLUSIVE | FAIL | FAIL | PASS | `stay_deferred` |
| `PRJ-KERNEL-API` write-side actions | FAIL | FAIL | INCONCLUSIVE | FAIL | FAIL | PASS | `stay_deferred` |

Notlar:

1. `claude-code-cli` lane için açık KB'ler (`KB-001`, `KB-002`) support
   sınırını bozmayacak şekilde operator-managed lane içinde bounded kaldı.
2. `gh-cli-pr` için canlı lane kanıtı yalnız preflight (`--dry-run`) seviyesinde
   olduğu için live write widening açılmadı.
3. kernel-api write-side action'lar runtime registry'de yok; bu yüzden
   write-side widening ops gates bu slice'ta geçmedi.

## PB-6.5 Karar Çıkışı

1. `claude-code-cli` lane:
   `promotion_candidate_with_ops_gates` (otomatik support widening yok)
2. `gh-cli-pr` preflight lane:
   `stay_beta_operator_managed` (preflight-only boundary korunur)
3. `gh-cli-pr` live write lane:
   `stay_deferred`
4. `PRJ-KERNEL-API` write-side actions:
   `stay_deferred`

## PB-6.5 DoD Doğrulaması

1. lane bazlı ops-readiness gate tablosu finalize edildi
2. her lane için tekil verdict üretildi
3. sonraki aktif implementation/decision slice issue + plan ile açıldı:
   `PB-6.6` / [#277](https://github.com/Halildeu/ao-kernel/issues/277)
4. status SSOT ve umbrella issue hizası bu closeout ile güncellenecek

## Sonraki Aktif Hat

`PB-6.6` — claude-code-cli lane ops-gated promotion closeout:

1. issue: [#277](https://github.com/Halildeu/ao-kernel/issues/277)
2. plan:
   `.claude/plans/PB-6.6-CLAUDE-CODE-CLI-OPS-GATED-PROMOTION-CLOSEOUT.md`

## DoD

1. lane bazlı ops readiness gate tablosu finalize edildi
2. her lane için verdict tekilleşti
3. bir sonraki aktif slice tek issue + tek DoD ile açıldı
4. status SSOT ve umbrella issue güncellendi

## İlk Yürütüm Sırası

1. `docs/OPERATIONS-RUNBOOK.md`, `docs/KNOWN-BUGS.md`, `docs/ROLLBACK.md`,
   `docs/PUBLIC-BETA.md`, `docs/SUPPORT-BOUNDARY.md` parity taraması
2. lane bazlı readiness checklist'in mevcut kanıtla doldurulması
3. açık ops gap'ler için dar kapsamlı follow-up slice önerisi
