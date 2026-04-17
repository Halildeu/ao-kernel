# Session Handoff — 2026-04-17 FAZ-B Progress (post PR-B6)

**Handoff sebebi**: Bugünkü oturum PR-B1, docfix, PR-B2, PR-B6'yı merge etti. Şimdi devredilecek aşamada: B5 planı Codex iter-1'e hazır; B3/B4 başlanmadı; paralel 1 session ve 1 chip açık.

## Main durumu

- **Branch**: `main`
- **HEAD**: `24cda5e` (PR-B6 merge commit)
- **PyPI**: v3.1.0 LIVE (v3.2.0 target FAZ-B sonunda)
- **Test**: 1890 passed / 3 skipped (B6 sonrası baseline)

## Bugün merge edilen PR'lar (kronolojik)

| # | PR | Commit | Scope | Test delta |
|---|---|---|---|---|
| 1 | #96 PR-B0 | fbf7229 | foundation: docs + schemas + dormant policies | — (önceki session) |
| 2 | #97 PR-B1 | 8ade379 | coordination runtime (lease/fencing/takeover) | önceki session +119 |
| 3 | #98 docfix | 5779609 | stale_after + B5 OTEL scope | bu oturum (docs-only) |
| 4 | **#99 PR-B2** | 59ae712 | cost runtime (catalog + ledger + governed_call) | +126 net |
| 5 | **#101 PR-B6** | 24cda5e | review/commit AI workflow runtime (thin, driver-owned) | +62 net |

## Ayrı session'da çalışan işler

### PR #100 — B2 e2e tests (çalışıyor)

- Spawn_task chip ile açıldı (PR-B2 post-merge concerns: mock transport e2e + injected_messages roundtrip + concurrent writer CAS race)
- Ayrı Claude session'ının sorumluluğu: kendi CI + post-impl review + merge
- **Kullanıcıya iş YOK** — izlemek yeterli (`gh pr view 100`). Müdahale yalnız CI hard-fail + session tıkandığında.

### Spawn_task chip (kullanıcı tıklarsa başlar)

**Adapter-path `output_ref` persistence** (B6 post-impl Codex iter-2 Q3 follow-up):
- Pre-B6'dan beri adapter step'lerde `step_record.output_ref` absent
- Executor `write_artifact()` çağırıyor ama `ExecutionResult`'a thread etmiyor
- Fix: `ExecutionResult` + `output_ref`/`output_sha256` optional fields + driver wire + docs + tests
- NOT B7 auto-scope; explicit follow-up
- Chip prompt'u: `"Add adapter-path output_ref persistence via ExecutionResult"`
- Otomatik B7 scope DEĞİL (Codex explicit).

## Hazır planlar (Codex iter-1 bekliyor)

### `.claude/plans/PR-B5-IMPLEMENTATION-PLAN.md` — v2, ~1876 LOC

- Metrics export (Prometheus textfile + `[metrics]` extra)
- B5 background agent v1 draft'ı revize etti → v2 pre-submit
- 7 code-level hata düzeltildi, 3 scope genişletme (cost_usd + usage_missing metrics, fail-closed corrupt JSONL, EvidenceSourceCorruptedError)
- 5 açık Codex sorusu
- Beklenen ilk iter: **PARTIAL**
- Thread: yeni CNS-20260417-035 açılacak

## Kalan FAZ-B PR'ları

| PR | Status | Bağımlılık | Not |
|---|---|---|---|
| **B5** | Plan v2 hazır | — | Codex iter-1 → AGREE → impl. Paralel lane candidate. |
| **B3** | Scope clear | B2 (merged) | Cost-aware routing. 48h smoke window Codex advisory'siydi ama B2 stabil. |
| **B4** | Scope clear | — | Policy simulation harness. Bağımsız. |
| **B7** | Scope clear | B1 + B2 + B6 (tümü merged) | Benchmark runner + governed_review scoring. |
| **B8** | Sonunda | all | v3.2.0 release + CHANGELOG final + tag. |

**Sıralama önerisi** (Codex CNS-030 iter-1 advisory):
`B5 paralel + B3 → B4 → B7 → B8`. B3/B4 bağımsız, paralel de olabilir.

## Aktif Codex MCP threads

Gelecek oturumda `codex-reply` için threadId'ler saklı:

| Thread | Konu | Son verdict |
|---|---|---|
| 019d9528-... | CNS-029 PR-B1 plan-time (expired) | MERGED |
| 019d97b8-... | CNS-029 PR-B1 post-impl (expired) | MERGED |
| 019d9a27 | PR-B1 iter-4+5 verify | MERGED |
| 019d9aa8 | CNS-031 PR-B2 plan-time | AGREE (7 iter) |
| 019d9be4 | CNS-032 PR-B2 post-impl | AGREE (3 iter) |
| 019d9c27 | CNS-033 PR-B6 plan-time | AGREE (4 iter) |
| 019d9ccd | CNS-034 PR-B6 post-impl | AGREE (3 iter) |

Yeni iş için yeni thread; aynı iş için `codex-reply` + threadId.

## Kritik yeni kurallar (bu oturumda eklendi)

Global `~/.claude/CLAUDE.md` güncellendi:

1. **Plan Consensus Autonomy**: Codex ile plan-time AGREE sağlandığında **kullanıcıya plan onayı SORMA, direkt impl**. Stratejik sapma hariç. (User feedback: "plan onaylarını bana sorma codex ile istişare ediyorsun zaten")

2. **İş Yapış Şekli — Agentic Paralelizm**:
   - Background Agent proaktif (Codex beklerken)
   - `spawn_task` out-of-scope findings
   - Paralel Codex thread'leri (bağımsız konular)
   - Multi-agent single-message spawn
   - `claude-code-guide` subagent meta-sorular
   - `Explore` subagent geniş codebase
   - `xhigh` effort karmaşık planlama (Opus 4.7 özelliği)

## Locked invariants (önceki + bu oturum)

### PR-B1 (coordination)
- 7 public API dormant gate
- B2v3 exact-equality fencing
- B3v3 forward-only reconcile
- W1v5 no-emit executor entry (driver owns step_failed)
- Evidence `_KINDS` 18→24

### PR-B2 (cost)
- `policy.enabled=true` + `budget.cost_usd` yoksa → `CostTrackingConfigError`
- Legacy budget aggregate-only stays aggregate-only (iter-2 absorb)
- `tokens_output=None` → OMIT; aggregate always emitted
- CAS retry fixed 3 (`update_run(max_retries=3)`)
- Streaming FAZ-C deferred
- MCP `ao_run_id/ao_step_id/ao_attempt` prefix
- Evidence `_KINDS` 24→27

### PR-B6 (review+commit AI)
- Executor schema-agnostic (`ExecutionResult` + `_normalize_invocation_for_artifact` DEĞİŞMEZ)
- Capability materialization driver-owned
- `capability_output_refs` B6-guaranteed; `output_ref` adapter-path legacy empty-stays-empty
- `_LEGAL_CATEGORIES` ⊆ schema error.category.enum (parity test zorunlu)
- `commit_write` prohibition preserved (commit AI = message artifact)
- `commit_message` object-shape (walker Mapping check)
- `on_failure` string enum
- `adapter_returned` evidence payload DOKUNULMAZ

## Tekrar açılmaması gereken kararlar (reference)

- D1-D14 mimari kararlar (project_decisions.md)
- Codex niche positioning: "self-hosted governance + evidence control-plane for AI coding agents"
- FAZ-B 9-PR plan (TRANCHE-STRATEGY-V2.md)
- Plan-first + CNS adversarial iter süreci (mandatory)
- Post-impl Codex review iki ayrı kapıdır

## Gelecek oturum için ilk adımlar

1. **Kullanıcıya yön sor**:
   - "B5 ile paralel devam (plan v2 hazır, Codex iter-1 gönderilecek)?"
   - "B3 critical path ile serial devam?"
   - "B4 bağımsız lane?"
   - "Adapter output_ref persistence chip'i tıklandı mı?" (kullanıcı tıkladıysa ayrı session çalışıyor)

2. **PR #100 durumu kontrol**: `gh pr view 100 --json state,mergedAt` — merge olduysa ana track temiz.

3. **Eğer B5 seçilirse**: 
   - Yeni branch: `git checkout main && git pull && git checkout -b claude/tranche-b-pr-b5`
   - Codex MCP yeni thread (`CNS-20260417-035`)
   - Plan v2 submit (`.claude/plans/PR-B5-IMPLEMENTATION-PLAN.md`)
   - Iter loop AGREE'ye kadar → impl (5-commit DAG, ~850 runtime LOC + 520 test + 220 Grafana)

4. **Eğer B3 seçilirse**:
   - Plan draft yok; scratch'tan başlanmalı
   - B2 cost runtime'a sıkı bağımlı (cost-aware routing `llm.resolve_route` delta)
   - Scope: `ao_kernel/cost/routing.py` + `policy_cost_tracking.routing_by_cost.enabled` knob aktivasyonu

5. **Eğer B4 seçilirse**:
   - Plan draft yok
   - Bağımsız lane; `ao_kernel/policy_sim/` yeni package
   - Scope: dry-run policy change → deny/allow diff; Codex CNS-031 iter-1'de "no side-effects kontratı şüpheli" uyarısı vardı → plan-first süreçte dikkat

## Dosya referansları (bu oturum)

- **Planlar**: `.claude/plans/PR-B6-IMPLEMENTATION-PLAN.md` (v4 AGREE, merged), `.claude/plans/PR-B5-IMPLEMENTATION-PLAN.md` (v2 hazır), `.claude/plans/PR-B2-IMPLEMENTATION-PLAN.md` (v7 merged), `.claude/plans/PR-B5-DRAFT-PLAN.md` (subagent v1, superseded)
- **Docs (güncel)**: `docs/COST-MODEL.md`, `docs/METRICS.md`, `docs/BENCHMARK-SUITE.md`, `docs/COORDINATION.md`
- **Memory**: `~/.claude/projects/-Users-halilkocoglu-Documents-ao-kernel/memory/project_origin.md`, `MEMORY.md`
- **Global rules**: `~/.claude/CLAUDE.md`

## Bu oturumda öğrenilen dersler

1. **Plan v1'de kod okuma disiplini**: Codex her iter'de bir katman daha derin kod okuması yapar. İlk iter summary-level, son iter inter-caller API-level mismatch yakalar. Plan v1'de gerçek kodu satır-level okumak iter sayısını azaltır.

2. **Plan consensus autonomy**: Kullanıcı feedback "plan onayı sorma" — Codex AGREE sağlandığında direkt impl.

3. **Paralel agentic pattern**: Single message'da multi-agent spawn + spawn_task + Codex reply birlikte kullanılır; sadece foreground/sequential çalışmak boşa zamandır.

4. **Codex MCP thread saklı**: `codex-reply` ile aynı thread devam; yeni konu → yeni thread.

5. **Opus 4.7 active**: Commit message'larda görünür. 1M context + xhigh effort + improved SWE-bench uygun kullanım.
