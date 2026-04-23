# PB-8.3 — bug_fix_flow Release Closure Promotion

**Status:** Active  
**Date:** 2026-04-23  
**Tracker:** [#288](https://github.com/Halildeu/ao-kernel/issues/288)  
**Active issue:** [#291](https://github.com/Halildeu/ao-kernel/issues/291)

## 1. Amaç

`bug_fix_flow` lane'ini deferred support sınırından çıkarma kararını
runtime + test + smoke + docs kanıtına dayalı olarak vermek.

Bu slice sonunda tek karar üretilir:

1. `promote` (support boundary genişler), veya
2. `stay_deferred` (gerekçesi ve eksik kapılar yazılı kapanır).

## 2. Kapsam

1. `bug_fix_flow` workflow zinciri:
   - `compile_context`
   - `invoke_coding_agent`
   - `preview_diff`
   - `ci_gate`
   - `await_approval`
   - `apply_patch`
   - `open_pr`
2. `open_pr` adımı için evidence completeness:
   - artifact alanları
   - `events.jsonl` sinyalleri
   - retry/denied/failure path davranışı
3. Side-effect safety ve rollback güvenliği:
   - live side-effect lane için explicit guard
   - disposable/rollback koşullarının workflow düzeyinde doğrulanması
4. Release closure kararı için docs/status parity:
   - `docs/PUBLIC-BETA.md`
   - `docs/SUPPORT-BOUNDARY.md`
   - `.claude/plans/POST-BETA-CORRECTNESS-EXPANSION-STATUS.md`

## 3. Kapsam Dışı

1. `gh-cli-pr` lane'in bağımsız promotion rework'ü (`PB-8.1` dışında kalan
   yeni kapsam)
2. `PRJ-KERNEL-API` write-side yeni action ekleme (`PB-8.2` sonrası)
3. Yeni adapter ekleme/promotion
4. Geniş refactor veya unrelated docs temizliği

## 4. Kabul Kapıları (DoD)

1. Workflow düzeyinde davranış kanıtı:
   - en az 1 tam başarı zinciri (`approval -> apply_patch -> open_pr`)
   - en az 1 deny/failure zinciri (`policy/approval/adapter` kaynaklı)
2. Evidence completeness:
   - `open_pr` artifact zorunlu alanları testle pinli
   - `policy_checked` / `policy_denied` / `pr_opened` olayları beklenen
     semantikte
3. Side-effect safety:
   - live-write lane explicit opt-in ve rollback guard'ı dışında
     açılamıyor
4. Docs/runtime parity:
   - support boundary metni yalnız canlı kanıtlanan davranışı söylüyor
5. Tek karar:
   - `promote` veya `stay_deferred` net olarak yazılı

## 5. Implementasyon Dilimleri

### T1 — Baseline Truth + Gap Inventory

1. Mevcut `bug_fix_flow` runtime/test/evidence gerçekliğini yeniden doğrula.
2. Mevcut testlerin zayıf assertion noktalarını çıkar.
3. Karar kapısını bloklayan minimum teknik gap listesi üret.

### T2 — Runtime/Test Closure

1. Gerekli runtime guard değişikliklerini dar kapsamla uygula.
2. Behavior-first testlerle başarı + negatif path'leri pinle.
3. Evidence payload alanlarını ve event sırasını regressions'a karşı kilitle.

### T3 — Smoke + Decision + Parity

1. İlgili smoke/targeted test komutlarını çalıştır.
2. Kararı (`promote`/`stay_deferred`) issue + status + docs yüzeyine işle.
3. Deferred kalanlar için net sonraki hat notu bırak.

## 6. Zorunlu Komut Seti

Minimum CI öncesi doğrulama:

```bash
python3 -m pytest -q tests/test_multi_step_driver_integration.py -k "bug_fix_flow or open_pr"
python3 -m pytest -q tests/benchmarks/test_governed_bugfix.py
python3 -m pytest -q tests/test_executor_policy_rollout_v311_p2.py
python3 scripts/gh_cli_pr_smoke.py --output json
```

Runtime side-effect guard değişirse:

```bash
python3 scripts/gh_cli_pr_smoke.py --mode live-write --output json
```

## 7. Riskler ve Azaltım

| Risk | Etki | Azaltım |
|---|---|---|
| Mock ağırlıklı testle fake green | Yüksek | behavior-first negatif path + smoke birlikte zorunlu |
| `open_pr` side-effect regressions | Yüksek | explicit opt-in + rollback guard + failure testleri |
| Docs/runtime drift | Orta | karar sonrası aynı PR'da docs parity zorunlu |
| Scope creep | Orta | yalnız bug_fix_flow release closure alanı |

## 8. Çıkış Kriteri

`PB-8.3` ancak şu durumda kapanır:

1. karar tekilleşti (`promote`/`stay_deferred`),
2. kararın teknik kanıtı test + smoke ile bağlı,
3. support boundary metinleri kararla birebir hizalı.

## 9. Baseline Snapshot (2026-04-23)

Çalıştırılan komutlar ve sonuç:

```bash
python3 -m pytest -q tests/test_multi_step_driver_integration.py -k "real_codex_stub_with_mocked_ci_and_open_pr_completes_full_flow"
python3 -m pytest -q tests/benchmarks/test_governed_bugfix.py tests/benchmarks/test_governed_review.py
python3 -m pytest -q tests/test_executor_policy_rollout_v311_p2.py
python3 scripts/gh_cli_pr_smoke.py --output json
```

Özet:

1. `bug_fix_flow` mock sidecar integration testi yeşil (approval/apply/open_pr
   artifact zinciri mevcut).
2. Benchmark lane yeşil (`10 passed`), fakat `governed_bugfix` tek başına
   çalıştırıldığında scorecard primary-scenario kuralı nedeniyle fail olur;
   baseline komutu iki dosya birlikte koşmalıdır.
3. Policy rollout test paketi yeşil (`11 passed`).
4. `gh-cli-pr` preflight smoke geçiyor (`overall_status=pass`,
   repo=`Halildeu/ao-kernel`).

Başlangıç gap notları:

1. Workflow-level `open_pr` invocation hâlen doğrudan `gh pr create` kontratı
   ile çalışır; disposable/live-write rollback guard'ı smoke helper'da var,
   workflow runtime kontratında enforce edilmiş tek kapı değildir.
2. `bug_fix_flow` için gerçek `gh-cli-pr` side-effect + rollback davranışını
   workflow zincirinde pinleyen dar integration testi eksik.
3. Release-closure kararı için docs/status parity güncellemesi yalnız karar
   çıktıktan sonra yapılacak; bu dilimde false-promotion önlemek için
   `stay_deferred` seçeneği açık tutulur.

T2 progress update (2026-04-23):

1. [#297](https://github.com/Halildeu/ao-kernel/pull/297) merge edildi:
   `open_pr` failure metadata artık generic fallback altında kaybolmuyor.
2. Bu dilimde bir sonraki closure adımı olarak workflow-level live-write guard
   açıldı: `gh-cli-pr` `open_pr` side effect'i yalnız
   `AO_KERNEL_ALLOW_GH_CLI_PR_LIVE_WRITE=1` explicit opt-in ile çalışır.
3. Guard davranışı, başarı/failure zinciri ve benchmark full-flow yolu
   behavior-first testlerle pinlenecek; ardından T3 karar/parity turuna
   geçilecek.

T3 closeout update (2026-04-23):

1. [#298](https://github.com/Halildeu/ao-kernel/pull/298) merge edildi:
   workflow-level `open_pr` guard runtime'a alındı ve integration/benchmark
   testleri yeni explicit opt-in kontratına hizalandı.
2. Final decision: `stay_deferred`.
   - `bug_fix_flow` lane'inde side-effect risk azaltımı ve evidence parity
     kapanmış olsa da disposable/live rollback zinciri workflow runtime support
     contract'ında promoted seviyeye çıkmadı.
3. Decision parity:
   - `docs/PUBLIC-BETA.md` + `docs/SUPPORT-BOUNDARY.md` deferred satırları
     `PB-8.3` verdict'i ile hizalandı.
4. Sonraki aktif hat: `PB-8.4` support widening closeout.
