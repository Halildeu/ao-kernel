# AO-MA-SPM Roadmap Status (insan-okur tracking aynası)

> **Bu dosya nedir:** Operatörün "planda neredeyim?" sorusunun insan-okur cevabı. Makine-okur ikizi: `.claude/plans/ao_ma_status.v1.json` (SSOT). Bu md ondan türer; çelişirse **JSON SSOT esastır** ve `python3 scripts/ao_ma_next.py` drift bildirir.
> **Otorite notu:** Bu dosya da JSON da **tracking index'tir, governance authority DEĞİL** — master plan + merged artifact'lar + ao-release-gate otoritedir.
> **Program SSOT:** `.claude/plans/AO-MA-SPM-MASTER-PLAN.md`. **Statü kaynağı:** AO-MA-11E-1.

## Nasıl bakılır

```bash
python3 scripts/ao_ma_next.py            # özet + sıradaki izinli iş + drift kontrolü
python3 scripts/ao_ma_next.py --next-only  # sadece sıradaki aksiyon
python3 scripts/ao_ma_next.py --format json
```

`ao_ma_next.py` pure-read'dir: shell-out yok, GitHub yok, network yok. Drift varsa exit≠0 (fail-closed: otonomi durdurulur + eskalasyon).

## İlerleme (2026-06-04)

- **Fazlar:** 5/7 done (71%). Tamamlanan:
  **AO-MA-11I**, **AO-MA-11H**, **AO-MA-11F**, **AO-MA-4.6**,
  **AO-MA-11G**. Aktif follow-up fazları: **AO-MA-11A** +
  **AO-MA-11E** (in_progress).
- **Dilimler (slices):** 7/9 merged (78%).
- **Current phase / slice:** `AO-MA-11G` / `AO-MA-11G-1`
  (core slice landed). `progress_estimates.phases.next_phase_id = null`;
  remaining work is demand-driven follow-up, not a new core phase.

## Faz Tablosu

| Faz | Başlık | Statü | Dilimler |
|---|---|---|---|
| **AO-MA-11A** | Plan Consensus + Tek Operatör Onay Kapısı | 🟡 in_progress | 11A-1 ✅ merged, 11A-2 ⬜ not_started |
| **AO-MA-11E** | GitHub-Native Operator Tracking Mirror | 🟡 in_progress | 11E-1 ✅ merged, 11E-2 ⬜ not_started |
| **AO-MA-11I** | Autonomous Run Governor | 🟢 done | 11I-1 ✅ merged (#762) |
| **AO-MA-11H** | Notification & Escalation | 🟢 done | 11H-1 ✅ merged (#763) |
| **AO-MA-11F** | Test/Öneri/Güncelleme Evidence Registers | 🟢 done | 11F-1 ✅ merged (#765) |
| **AO-MA-4.6** | Native Worker Result Import (import-only) | 🟢 done | 4.6-1 ✅ merged (#766) |
| **AO-MA-11G** | SPM Quality Profile Hardening | 🟢 done | 11G-1 ✅ merged (#767) |

## Dilim Tablosu

| Dilim | Statü | Risk | Consensus | Approval | PR | Açıklama |
|---|---|---|---|---|---|---|
| AO-MA-11A-1 | ✅ merged | critical | agreed | approved | #758 | plan_consensus validator + 2 schema |
| AO-MA-11A-2 | ⬜ not_started | high | not_started | not_requested | — | GitHub Environment required-reviewer wiring |
| AO-MA-11E-1 | ✅ merged | critical | agreed | not_requested | #760 | derived tracking SSOT + schema + ao_ma_next + roadmap + drift core |
| AO-MA-11E-2 | ⬜ not_started | high | not_started | not_requested | — | GitHub Projects/Milestone/Issue one-way sync + live drift |
| AO-MA-11I-1 | ✅ merged | critical | agreed | not_requested | #762 | PAUSE kill-switch + budget cap + safe-stop |
| AO-MA-11H-1 | ✅ merged | high | agreed | not_requested | #763 | Mavis chat + GitHub-native notification, `blocked_notification_failed` safe-stop |
| AO-MA-11F-1 | ✅ merged | normal | agreed | not_requested | #765 | test/suggestion/update evidence registers + slice closeout + evidence bundle |
| AO-MA-4.6-1 | ✅ merged | high | agreed | not_requested | #766 | native worker result import-only: schema-validate + provenance-bind (no call) |
| AO-MA-11G-1 | ✅ merged | normal | agreed | not_requested | #767 | ADR template + ISO 25010 profile + changelog discipline |

## Değişmezler (her dilimde korunur)

`support_widening` / `production_platform_claim` / `live_adapter_execution` = **FALSE** · `release_authority` = ao-release-gate + GitHub ruleset · `--admin` YASAK · risk downgrade YASAK · GitHub mirror tek-yön (authority değil).

## Sıradaki

1. **AO-MA-11A-2** — GitHub Environment `ao-ma-plan-approval`
   required-reviewer wiring. High-risk follow-up; demand-driven.
2. **AO-MA-11E-2** — GitHub Projects/Milestone/Issue one-way sync +
   anchor injection + live drift checker. High-risk follow-up; demand-driven.
3. **AO-MA-11G-2 follow-up set** — CI/pre-commit changelog enforcement,
   AO-MA-4.6 dogfooding, retro ADR cross-AI revalidation, and
   CHANGELOG/pyproject allowlist widening. These are follow-up hardening
   slices; SON FAZ core capabilities are already landed.
4. Guard flags stay false: no support widening, no production platform claim,
   no live adapter execution. Release authority remains repo-owned
   `ao-release-gate` + GitHub ruleset, not this tracking mirror.

> Bu md, `ao_ma_status.v1.json` her güncellendiğinde elle senkronlanır.
> 11E-2 sonrası GitHub mirror otomatik akar. Tek gerçek = JSON SSOT; bu md
> onun okunabilir görünümü.
