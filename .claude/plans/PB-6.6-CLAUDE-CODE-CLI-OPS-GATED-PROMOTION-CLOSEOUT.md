# PB-6.6 — Claude Code CLI Lane Ops-Gated Promotion Closeout

**Status:** Completed (decision closeout)  
**Date:** 2026-04-23  
**Parent:** `PB-6`  
**Parent issue:** [#243](https://github.com/Halildeu/ao-kernel/issues/243)  
**Decision issue:** [#277](https://github.com/Halildeu/ao-kernel/issues/277)  
**Next active issue:** [#243](https://github.com/Halildeu/ao-kernel/issues/243)

## Amaç

`PB-6.5` sonucunda `promotion_candidate_with_ops_gates` çıkan
`claude-code-cli` lane'i için tekil support-tier closeout kararını üretmek.

Bu slice runtime davranışını değiştirmez; support-tier kararını ve operator
işletim kapılarını finalize eder.

## Kapsam

1. `claude-code-cli` lane için ops-gated promotion checklist finalizasyonu
2. decision sonucu:
   - `stay_beta_operator_managed` veya
   - `promoted_with_ops_gates`
3. `PUBLIC-BETA`, `SUPPORT-BOUNDARY`, `OPERATIONS-RUNBOOK`, `KNOWN-BUGS`,
   `ROLLBACK` yüzeylerinde karar uyumunu sağlamak
4. `PB-6` umbrella üzerinde sonraki aktif hattı netleştirmek

## Kapsam Dışı

1. adapter/runtime/policy behavior değişikliği
2. `gh-cli-pr` live write widening
3. `PRJ-KERNEL-API` write-side widening

## Giriş Kanıtı

`PB-6.5` closeout çıktısı:

1. `claude-code-cli` lane verdict:
   `promotion_candidate_with_ops_gates`
2. known-bug etkisi:
   `KB-001`, `KB-002` bounded, workaround yazılı
3. live smoke:
   `python3 scripts/claude_code_cli_smoke.py --output json` -> pass

## Canlı Kanıt Turu (2026-04-23)

Komut:

```bash
python3 scripts/claude_code_cli_smoke.py --output json
```

Özet:

1. `overall_status="pass"`
2. `version`, `auth_status`, `prompt_access`, `manifest_invocation` alt
   kontrolleri geçiyor
3. lane teknik olarak canlı ve tekrar edilebilir smoke üretiyor

## Gate Seti

1. Evidence repeatability gate:
   - bağımsız smoke koşularında lane kararlı mı?
2. Known-bug containment gate:
   - açık bug'lar operator için yönetilebilir ve yanlış destek iddiası üretmiyor mu?
3. Ops runbook gate:
   - incident/rollback akışı lane özelinde uygulanabilir mi?
4. Docs parity gate:
   - support tier dili tüm SSOT yüzeylerinde tek anlamlı mı?

## Gate Değerlendirmesi (Final)

| Gate | Durum | Kanıt | Yorum |
|---|---|---|---|
| Evidence repeatability | PASS | `scripts/claude_code_cli_smoke.py --output json` | Lane tekrar eden smoke ile doğrulanıyor |
| Known-bug containment | PASS (bounded) | `KB-001`, `KB-002` | Etki operator-managed sınır içinde yönetilebilir; shipped baseline etkisi yok |
| Ops runbook | PASS | `docs/OPERATIONS-RUNBOOK.md`, `docs/ROLLBACK.md` | Incident/rollback akışı lane için yazılı ve uygulanabilir |
| Docs parity | PASS | `PUBLIC-BETA`, `SUPPORT-BOUNDARY`, `KNOWN-BUGS` | Lane tier anlatımı tek anlamlı ve çelişkisiz |

## PB-6.6 Karar Çıkışı

**Final verdict:** `stay_beta_operator_managed`

Gerekçe:

1. `promotion_candidate_with_ops_gates` sinyali korunuyor, fakat lane bugün hâlâ
   operator çevresine bağımlı canlı auth/prompt precondition'ları taşıyor.
2. `KB-001` ve `KB-002` bounded olsa da support tier'i widen edecek kadar
   evrensel/çevre-bağımsız dayanıklılık kanıtı üretilmiş değil.
3. Bu nedenle lane support sınırı `Beta (operator-managed)` olarak kalır;
   shipped baseline'a yükseltilmez.

## Docs/Status Parity Sonucu

1. `docs/PUBLIC-BETA.md`: `claude-code-cli` satırı `Beta (operator-managed)`
2. `docs/SUPPORT-BOUNDARY.md`: Beta layer aynı sınırı taşıyor
3. `docs/OPERATIONS-RUNBOOK.md`, `docs/KNOWN-BUGS.md`, `docs/ROLLBACK.md`:
   incident/known-bug/rollback anlatımı bu verdict ile uyumlu
4. program status SSOT (`POST-BETA-...STATUS.md`) aktif issue/hat bilgisini
   `#243` umbrella seviyesine çeker

## DoD

1. `claude-code-cli` lane için tek support-tier verdict üretildi
2. kararın gerekçesi gate bazında yazılı
3. docs/status/issue yüzeyleri aynı kararı taşıyor
4. `PB-6` umbrella'da bir sonraki aktif hat tek issue ile bırakıldı (`#243`)
