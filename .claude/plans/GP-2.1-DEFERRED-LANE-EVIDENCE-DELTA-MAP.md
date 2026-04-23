# GP-2.1 — Deferred Lane Evidence-Delta Map

**Status:** Active  
**Date:** 2026-04-23  
**Tracker:** [#331](https://github.com/Halildeu/ao-kernel/issues/331)  
**Parent program:** `.claude/plans/GP-2-DEFERRED-SUPPORT-LANES-REPRIORITIZATION.md`

## Amaç

`PUBLIC-BETA` içinde deferred kalan lane'leri kanıt boşluğu bazında sıralamak
ve ilk dar runtime slice'ı tek anlamlı seçmek.

## Authoritative Inputs

1. `docs/PUBLIC-BETA.md` (Deferred + Known Bugs satırları)
2. `docs/SUPPORT-BOUNDARY.md` (support tier ve deferred sınırı)
3. `docs/KNOWN-BUGS.md` (operator lane kırıkları)
4. `python3 scripts/truth_inventory_ratchet.py --output json` (truth/debt queue)

## Deferred Lane Evidence-Delta Tablosu

| Lane | Mevcut kanıt | Eksik kanıt (delta) | Risk | Promotion önkoşulu | Sıra |
|---|---|---|---|---|---|
| Adapter-path `cost_usd` reconcile | `PB-5` closeout ile docs parity + internal hook varlığı doğrulandı | transport/adaptör katmanında deterministic maliyet reconcile davranışını pinleyen integration test + evidence assertion paketi yok | Orta | side-effect üretmeyen maliyet kanıtı + behavior test + docs parity | **Now** |
| `gh-cli-pr` tam E2E remote PR açılışı | preflight + live-write probe + rollback guard mevcut; operator runbook'lar var | disposable sandbox dışı ortamda güvenli create->verify->rollback zincirini üretim şartlarında tekrar eden kanıt yok | Yüksek | disposable repo policy + rollback drill + incident runbook rehearsal | **Next** |
| `bug_fix_flow` release closure | workflow-level guard (`AO_KERNEL_ALLOW_GH_CLI_PR_LIVE_WRITE=1`) ve metadata/evidence parity güçlendirildi | gerçek adapter lane ile E2E release closure güvence kanıtı, `gh-cli-pr` live write güvenilirliğiyle bağlı | Yüksek | `gh-cli-pr` E2E lane olgunluğu + bug_fix_flow integration kanıtı | **Later** |
| `DEMO-SCRIPT-SPEC` üç-adapter akışın canlı support'e alınması | dosya roadmap/spec olarak işaretli, compatibility stub korunuyor | production support boundary için runtime-backed adapter zinciri ve operasyonel runbook yok | Düşük/Orta | spec'i canlı claim'e çevirecek ayrı ürünleşme kararı | **Later (spec-only)** |

## Ordering Kararı

1. **Now:** `Adapter-path cost_usd reconcile` lane'i için dar runtime/evidence completeness slice aç.
2. **Next:** `gh-cli-pr` full E2E live remote PR opening lane'i disposable guard ve rollback kanıtıyla tekrar değerlendir.
3. **Later:** `bug_fix_flow` release closure ve `DEMO-SCRIPT-SPEC` widening kararları, yukarıdaki lane sonuçlarına bağlı yürütülür.

## First Runtime Slice Adayı

- **Aday:** `GP-2.2` altında `cost_usd` reconcile completeness tranche'i
- **Sınır:** support boundary widening yok; amaç yalnız runtime/evidence parity gap'i kapatmak
- **Başarı ölçütü:**
  1. deterministic reconcile testleri
  2. evidence payload içinde `cost_usd` uyum kanıtı
  3. PUBLIC-BETA deferred satır notunun güncellenebilir hale gelmesi
