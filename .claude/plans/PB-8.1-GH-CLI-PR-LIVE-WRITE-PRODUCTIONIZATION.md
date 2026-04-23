# PB-8.1 — gh-cli-pr Live-Write Productionization

**Status:** Active  
**Date:** 2026-04-23  
**Parent:** [#288](https://github.com/Halildeu/ao-kernel/issues/288)  
**Issue:** [#289](https://github.com/Halildeu/ao-kernel/issues/289)

## Amaç

`gh-cli-pr` lane'ini preflight/readiness seviyesinden, kontrollü ve
kanıtlanabilir bir live-write support adayına taşımak.

Bu tranche support tier'ını otomatik widen etmez; widening kararı ancak
DoD kapıları geçtiğinde ve docs parity güncellendiğinde verilir.

## Kapsam

1. live-write mode için explicit opt-in guard sözleşmesi
2. disposable repo/branch guard zorunluluğu
3. create -> verify -> rollback(close) zinciri
4. evidence payload'ta create/rollback sonucunun zorunlu kaydı
5. deny/fail path'lerde fail-closed semantik

## Kapsam Dışı

1. `bug_fix_flow` support widening
2. `PRJ-KERNEL-API` write-side action implementation
3. `PUBLIC-BETA` genel support tier metnini PB-8.4 öncesi genişletmek

## İş Paketleri

### Slice A — Contract netleştirme

1. `scripts/gh_cli_pr_smoke.py` live-write guard parametrelerinin
   zorunlu kombinasyonunu fail-closed hale getir
2. live-write mode için açık precondition denetimleri ekle:
   - allow flag
   - disposable keyword
   - head/base varlığı
3. her precondition fail'i için ayrı ve makinece okunur reason code üret

### Slice B — Evidence/rollback kesinliği

1. create success sonrası rollback(close) adımını zorunlu akışa bağla
2. rollback fail durumunu ayrı check olarak evidence raporuna yaz
3. keep-open seçeneğini explicit ve riskli-operasyon olarak işaretle

### Slice C — Test matrisi ve smoke

1. `tests/test_gh_cli_pr_smoke.py` içine behavior-first matris:
   - preflight pass
   - live-write opt-in yok => blocked
   - disposable guard fail => blocked
   - create fail path => fail-closed
   - rollback fail path => fail-closed / flagged
2. operator smoke çıktısını text+json formatında pinle

### Slice D — Docs/status parity

1. `POST-BETA-CORRECTNESS-EXPANSION-STATUS.md` PB-8.1 sonuç kaydı
2. `docs/SUPPORT-BOUNDARY.md` ve `docs/PUBLIC-BETA.md` lane notu güncelleme
3. widening açılmazsa açık `stay_deferred` veya `stay_beta_operator_managed`
   kararı yaz

## DoD

1. Live-write lane için pozitif/negatif/durum matrisi testli.
2. Create/rollback zinciri evidence üzerinde ayrı check'lerle görünür.
3. Guard ihlalleri fail-closed reason code ile dönüyor.
4. Status/docs/runtime aynı kararı söylüyor.

## Zorunlu Kanıt Komutları

```bash
pytest -q tests/test_gh_cli_pr_smoke.py
python3 scripts/gh_cli_pr_smoke.py --output json
python3 scripts/gh_cli_pr_smoke.py --mode live-write --output json
```

Gerekirse controlled disposable ortamda:

```bash
python3 scripts/gh_cli_pr_smoke.py \
  --mode live-write \
  --allow-live-write \
  --head <branch> \
  --base <branch> \
  --require-disposable-keyword sandbox \
  --output json
```

## Riskler

| Risk | Etki | Önlem |
|---|---|---|
| yanlış repo'da live-write side-effect | Yüksek | disposable guard + explicit opt-in |
| rollback adımı başarısız | Yüksek | rollback sonucu zorunlu evidence + fail state |
| helper smoke green ama gerçek davranış zayıf | Orta | behavior-first test matrix |
| docs/runtime karar drift'i | Orta | D diliminde zorunlu parity güncellemesi |

## Çıkış Kararı

Tranche sonunda yalnız iki karar geçerlidir:

1. `promotion_candidate` (widening ayrı tranche'ta açılır)
2. `stay_deferred` (eksik kapılar ve nedenleri açık yazılır)
