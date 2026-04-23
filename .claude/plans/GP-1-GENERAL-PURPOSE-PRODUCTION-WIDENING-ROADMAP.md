# GP-1 — General-Purpose Production Widening Program

**Status:** Active  
**Date:** 2026-04-23  
**Tracker:** [#316](https://github.com/Halildeu/ao-kernel/issues/316)  
**Execution mode:** Kapsam disiplini, tek aktif runtime tranche

## Amaç

`PB-9` closeout sonrası, dar ama kanıtlı Public Beta yüzeyinden
genel amaçlı production widening kararlarını kontrollü ve ölçülebilir
kapılarla yürütmek.

Bu programın amacı bir release'te agresif widening yapmak değildir.
Amaç, widening'i yalnız kanıt zinciri tamamlandığında açmaktır.

## Başlangıç Gerçeği

1. `PB-9` kapanmıştır; karar notu
   `.claude/plans/PB-9.4-PRODUCTION-CLAIM-DECISION-CLOSEOUT.md`.
2. Current verdict: `stay_beta_operator_managed`.
3. Public support boundary hâlâ dardır:
   - shipped baseline: deterministic `review_ai_flow + codex-stub`
   - operator-managed beta: `claude-code-cli`, `gh-cli-pr` preflight/live-write probe,
     `PRJ-KERNEL-API` write-side actions
   - deferred: `bug_fix_flow` release closure, full E2E live remote PR opening

## Gate Modeli (Non-Negotiable)

1. **G1 — Truth parity:** docs/runtime/tests/CI aynı support sınırını söyler.
2. **G2 — Rehearsal repeatability:** lane smoke paketleri tekrar üretilebilir.
3. **G3 — Side-effect safety:** write/live lane guard + rollback zinciri fail-closed.
4. **G4 — Evidence completeness:** karar için gereken artefaktlar eksiksiz.
5. **G5 — Governance enforcement:** required CI + branch protection bypass edilmez.
6. **G6 — Decision record:** her widening/stay kararı yazılı ve issue/PR bağlıdır.

## Tranche Sırası

### `GP-1.1` — Widening authority map and entry gates (Completed)

- Issue: [#315](https://github.com/Halildeu/ao-kernel/issues/315)
- Hedef: hangi yüzey hangi gate seti olmadan promote edilemez, bunu
  authoritative tabloya bağlamak.
- Ana çıktı: tek anlamlı entry-gate kontratı + tranche sıralaması.
- Kapanış kanıtı:
  - PR: [#317](https://github.com/Halildeu/ao-kernel/pull/317)
  - Merge commit: `9c4ca53`

### `GP-1.2` — `gh-cli-pr` live-write disposable contract (Completed)

- Issue: [#318](https://github.com/Halildeu/ao-kernel/issues/318)
- Hedef: disposable sandbox + create->verify->rollback zincirini production-grade
  karar seviyesinde doğrulamak.
- Ana çıktı: `promote_candidate` veya `stay_preflight` kararı.
- Karar notu:
  - `.claude/plans/GP-1.2-GH-CLI-PR-LIVE-WRITE-DISPOSABLE-DECISION.md`
- Karar: `stay_preflight`

### `GP-1.3` — `bug_fix_flow` release-closure re-evaluation (Completed)

- Issue: [#322](https://github.com/Halildeu/ao-kernel/issues/322)
- Hedef: `bug_fix_flow` deferred sınırını yeniden değerlendirmek.
- Ana çıktı: support boundary satırı için promote/stay kararı.
- Karar notu:
  - `.claude/plans/GP-1.3-BUG-FIX-FLOW-RELEASE-CLOSURE-DECISION.md`
- Karar: `stay_deferred`

### `GP-1.4` — Extension promotion tranche (`PRJ-CONTEXT-ORCHESTRATION`) (Active)

- Issue: [#324](https://github.com/Halildeu/ao-kernel/issues/324)
- Hedef: contract-only extension için runtime ownership / handler readiness kanıtı.
- Ana çıktı: `promotion_candidate` veya `stay_contract_only`.

### `GP-1.5` — Program closeout decision (Planned)

- Issue: `pending`
- Hedef: program sonunda widening etkisini tek closeout notunda sabitlemek.
- Ana çıktı: updated support boundary + tracker closeout.

## Başarı Kriterleri

1. **BC-1** GP-1.1 sonrası widening giriş koşulları tartışmasızdır.
2. **BC-2** write/live lane kararları smoke + behavior test + docs parity ile verilir.
3. **BC-3** deferred satırlar yalnız yazılı karar notuyla değişir.
4. **BC-4** program kapanışında support boundary kişi yargısı ile değil gate kanıtı ile güncellenir.

## Risk Register

| Risk | Etki | Önlem |
|---|---|---|
| Scope creep | Yüksek | tranche dışı runtime değişikliği blokla |
| Fake green smoke | Yüksek | helper + behavior tests + CI üçlü kanıt şartı |
| Overclaim drift | Yüksek | PUBLIC-BETA / SUPPORT-BOUNDARY parity zorunlu |
| Side-effect lane yanlış promote | Yüksek | disposable+rollback gate geçmeden widening yok |

## Program Kapanış Koşulu

1. `GP-1.1..GP-1.5` için karar kayıtları tamamlanır.
2. `POST-BETA-CORRECTNESS-EXPANSION-STATUS.md` aktif hattı kapatır.
3. Tracker [#316](https://github.com/Halildeu/ao-kernel/issues/316) kapanır.
