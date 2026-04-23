# PB-6.5 — Ops Readiness Gates for Widened Lanes

**Status:** Active  
**Date:** 2026-04-23  
**Parent:** `PB-6`  
**Parent issue:** [#243](https://github.com/Halildeu/ao-kernel/issues/243)  
**Active issue:** [#275](https://github.com/Halildeu/ao-kernel/issues/275)

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

## Ops Gate Matrisi (PB-6.5 Çıktısı)

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

## DoD

1. lane bazlı ops readiness gate tablosu finalize edildi
2. her lane için verdict tekilleşti:
   - `stay_beta_operator_managed` veya
   - `promotion_candidate_with_ops_gates` veya
   - `stay_deferred`
3. widening implementation açılacaksa bir sonraki slice tek issue + tek DoD ile
   tanımlandı
4. status SSOT ve umbrella issue güncellendi

## İlk Yürütüm Sırası

1. `docs/OPERATIONS-RUNBOOK.md`, `docs/KNOWN-BUGS.md`, `docs/ROLLBACK.md`,
   `docs/PUBLIC-BETA.md`, `docs/SUPPORT-BOUNDARY.md` parity taraması
2. lane bazlı readiness checklist'in mevcut kanıtla doldurulması
3. açık ops gap'ler için dar kapsamlı follow-up slice önerisi
