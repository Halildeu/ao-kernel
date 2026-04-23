# PB-6.6 — Claude Code CLI Lane Ops-Gated Promotion Closeout

**Status:** Active  
**Date:** 2026-04-23  
**Parent:** `PB-6`  
**Parent issue:** [#243](https://github.com/Halildeu/ao-kernel/issues/243)  
**Active issue:** [#277](https://github.com/Halildeu/ao-kernel/issues/277)

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

## Gate Seti

1. Evidence repeatability gate:
   - bağımsız smoke koşularında lane kararlı mı?
2. Known-bug containment gate:
   - açık bug'lar operator için yönetilebilir ve yanlış destek iddiası üretmiyor mu?
3. Ops runbook gate:
   - incident/rollback akışı lane özelinde uygulanabilir mi?
4. Docs parity gate:
   - support tier dili tüm SSOT yüzeylerinde tek anlamlı mı?

## DoD

1. `claude-code-cli` lane için tek support-tier verdict üretildi
2. kararın gerekçesi gate bazında yazılı
3. docs/status/issue yüzeyleri aynı kararı taşıyor
4. `PB-6` umbrella'da bir sonraki aktif hat tek issue ile bırakıldı
