# PR-B7.1 Implementation Plan v2 — Minimal Follow-up

**Minor release adayı v3.2.1. B7 v1 deferred item'larının 3'ü; 2 büyük item FAZ-C'ye taşındı.**

**Head SHA**: `ca361f2` (v3.2.0). Base: `main`. Active branch: `claude/tranche-b-pr-b7.1`.

---

## v2 absorb summary (Codex CNS-20260418-040 iter-1 REVISE — 5 blocker + 5 warning)

Codex v1 planını 5 katmanda runtime gap tespit etti. Savunulabilir scope: sadece **runtime LOC=0** tutulan dokümantasyon + benchmark-only shim işleri. Runtime integration gerektiren iki büyük item (full bundled bugfix + real full mode) **FAZ-C scope'una** taşındı.

| # | v1 bulgu | v2 karar |
|---|---|---|
| B1 | Bundled `bug_fix_flow` E2E: `_load_pending_patch_content()` `record.intent.payload.patches[step_name]`'den okuyor; seed düz string geçiyor → patch plumbing runtime integration gap | **FAZ-C'ye taşındı** (PR-C1 adayı: patch plumbing + input_envelope + policy_loader injection birlikte ele alınır) |
| B2 | Bench policy override file'ı etkisiz — `build_driver` Executor'a `policy_loader` vermez; bundled kullanılır | **FAZ-C'ye taşındı** (bench policy injection = Executor surface değişikliği) |
| B3 | `cost_usd` reconcile **B2 gap gerçek** — adapter transport sadece `time_seconds`; cost_usd yalnız `governed_call` → `post_response_reconcile` hattında | **v2 scope içi — benchmark-only shim** (açıkça mock-katmanı olarak etiketli; runtime gap labeled) |
| B4 | Full mode input_envelope gap: Executor `task_prompt+run_id` veriyor; manifestler `context_pack_ref` bekliyor; secret flow `env_allowlist` değil `secrets.allowlist_secret_ids + exposure_modes=['env']` | **FAZ-C'ye taşındı** (secret flow + input_envelope builder'ı FAZ-C'de ele alınır) |
| B5 | Full-mode env namespace `AO_BENCHMARK_GH_TOKEN` manifest parity DEĞİL — gerçek `GH_TOKEN` / `ANTHROPIC_API_KEY` contract | **FAZ-C'ye taşındı** (B4 ile birlikte) |

### v2 absorb warnings

| # | v1 warning | v2 karar |
|---|---|---|
| W1 | cf8b30e zaten missing-payload testi unskip + docs §3.2 pin etmiş | C3 → sadece CHANGELOG note (yeni behavior yok; temizlik) |
| W2 | "CI auto-picks up" mekanizması = pytest discovery; özel glob yok | Recipe §9 wording "pytest discovery otomatik bulur" olarak netleşir |
| W3 | ci_pytest happy-path için dummy `test_smoke.py` gerekliliği — ancak B7.1 v2'de full bugfix drop edildiğinden moot | Moot (full bugfix FAZ-C) |
| W4 | gh-cli-pr pr_url assertion convenience, contract değil | Moot (full bugfix FAZ-C) |
| W5 | Bundled worktree policy zaten git/python/pytest içerir; asıl blocker patch plumbing + env flow | Moot (full bugfix FAZ-C) |

### Codex Q answers → v2 kararlar

- **Q1** (record_spend shim vs integration): Benchmark-only shim, clearly labeled comment + docstring.
- **Q2** (policy override file vs inline): Moot — full bugfix FAZ-C.
- **Q3** (full-mode CI): Moot — full mode FAZ-C.
- **Q4** (env namespace): Moot — full mode FAZ-C.

---

## 1. Amaç (v2 daralmış)

B7 v1 "deferred" etiketlerinin **docs-level** temizliği + benchmark harness'in `cost_usd` axis drain'i **mock-layer shim** ile ispatlanabilir hale getirilmesi:

| # | Item | Scope | LOC |
|---|---|---|---|
| 1 | `cost_usd` benchmark-only reconcile shim | Mock dispatcher `cost_actual.cost_usd` → run_state budget axis `.remaining` decrement; benchmark-only labeled | ~80 |
| 2 | Walker contract docs pin | cf8b30e absorb'un final note'u CHANGELOG'da | ~20 |
| 3 | New-scenario recipe | `docs/BENCHMARK-SUITE.md §9` step-by-step 6 adım | ~100 |

### Kapsam özeti

- `tests/benchmarks/mock_transport.py` — shim: envelope `cost_actual.cost_usd` → state.v1.json `budget.cost_usd.remaining` decrement (after dispatcher return, before _cli_dispatcher tuple return).
- `tests/benchmarks/assertions.py` — `assert_cost_consumed(run_state, axis, min_consumed=0.0)` helper.
- `tests/benchmarks/test_governed_review.py` — `TestCostReconcile` class (1 happy test).
- `docs/BENCHMARK-SUITE.md` — §9 recipe + §8.3 "deferred" list update (FAZ-C items explicit).
- `CHANGELOG.md` — `[Unreleased]` PR-B7.1 entry.

- Yeni evidence kind: **0**.
- Yeni core dep: 0.
- **Runtime LOC: 0** (benchmark harness + docs only; shim clearly label'ed "benchmark-only").

---

## 2. Scope İçi

### 2.1 `cost_usd` benchmark-only shim (`mock_transport.py`)

**Codex B3 absorb**: B2 integration gap explicit. Mock dispatcher envelope'un `cost_actual.cost_usd` alanını okur; `run_state.v1.json` budget `cost_usd` axis `remaining`'ini decrement eder.

```python
# tests/benchmarks/mock_transport.py — extension inside _cli_dispatcher
def _maybe_consume_budget(
    workspace_root: Path,
    run_id: str,
    envelope: Mapping[str, Any],
) -> None:
    """BENCHMARK-ONLY SHIM. Real cost_usd reconcile path lives in
    ao_kernel.cost.middleware.post_response_reconcile, which is
    only called from ao_kernel.llm.governed_call. The adapter
    transport path (invoke_cli/invoke_http) does not reconcile
    cost_usd — only time_seconds. Until that integration gap is
    closed (FAZ-C), this shim is what lets benchmark assertions
    observe cost_usd drain."""
    cost_usd = (envelope.get("cost_actual") or {}).get("cost_usd")
    if cost_usd is None:
        return
    state_path = workspace_root / ".ao" / "runs" / run_id / "state.v1.json"
    if not state_path.is_file():
        return
    state = json.loads(state_path.read_text(encoding="utf-8"))
    axis = (state.get("budget") or {}).get("cost_usd")
    if not isinstance(axis, dict):
        return
    remaining = float(axis.get("remaining", 0.0)) - float(cost_usd)
    axis["remaining"] = max(0.0, remaining)
    state["revision"] = run_revision(state)
    state_path.write_text(
        json.dumps(state, indent=2, sort_keys=True),
        encoding="utf-8",
    )
```

**Test**: `tests/benchmarks/test_governed_review.py::TestCostReconcile::test_cost_usd_drained`.

### 2.2 Walker contract CHANGELOG pin

cf8b30e post-impl absorb'u `docs/BENCHMARK-SUITE.md §3.2` pin etti + `test_missing_review_findings_fails_workflow` unskip edildi. B7.1'de **sadece CHANGELOG `[Unreleased]` PR-B7.1** içinde explicit "docs §3.2 reconciled with runtime (B7 v1 post-impl cf8b30e)" notu.

Kod değişikliği YOK.

### 2.3 New-scenario recipe (`docs/BENCHMARK-SUITE.md §9`)

6 adım:

```markdown
## 9. Adding a New Benchmark Scenario

1. **Workflow definition**: Bundled workflow varsa doğrudan
   kullan; yoksa `tests/benchmarks/fixtures/workflows/` altına
   `<scenario>_bench.v1.json` ekle (`governed_bugfix_bench` pattern).
2. **Canned envelopes**: `tests/benchmarks/fixtures/` altına
   `<scenario>_envelopes.py` — happy + error variant(s). Envelope
   shape adapter manifest'inin `output_envelope` + `output_parse`
   contract'ını takip eder.
3. **Test module**: `tests/benchmarks/test_<scenario>.py` +
   `TestHappyPath` + `TestTransportError` class'ları. Mock
   `(scenario_id, adapter_id, attempt)` key pattern.
4. **Assertions**: `tests/benchmarks/assertions.py` helpers
   (`assert_workflow_completed`, `assert_capability_artifact`,
   `assert_cost_consumed`, `assert_review_score`, `assert_budget_axis_seeded`).
5. **Local run**: `pytest tests/benchmarks/test_<scenario>.py -q`.
6. **CI**: `benchmark-fast` job `pytest tests/benchmarks/ -q`
   çalıştırır; pytest discovery yeni dosyayı otomatik bulur,
   workflow delta gerekmez.
```

### 2.4 `docs/BENCHMARK-SUITE.md §8.3` deferred list update

v1'de "deferred to B7.1" idi; şimdi 2 item explicit FAZ-C etiketlenir:

- Full bundled `bug_fix_flow` E2E → **FAZ-C PR-C1** (patch plumbing + input_envelope + policy_loader injection)
- Real-adapter full mode → **FAZ-C PR-C2** (secret flow + context_pack_ref + env namespace manifest parity)

### 2.5 CHANGELOG `[Unreleased]` PR-B7.1

- `tests/benchmarks/mock_transport.py` shim — `cost_usd` drain (labeled benchmark-only; B2 integration gap deferred to FAZ-C).
- `assertions.py::assert_cost_consumed` helper.
- `test_governed_review.py::TestCostReconcile` (1 test).
- `docs/BENCHMARK-SUITE.md §3.2` runtime contract pin (cf8b30e echo) + §8.3 FAZ-C deferred list + §9 recipe.

---

## 3. Write Order (2-commit DAG)

1. **C1**: shim + helper + reconcile test (~140 LOC)
2. **C2**: docs §9 recipe + §8.3 update + §3.2 note + CHANGELOG (~90 LOC)

**Toplam ~230 LOC** (tests + docs; **runtime LOC = 0**).

---

## 4. Design Trade-offs (v2)

| Seçim | Alternatif | Gerekçe |
|---|---|---|
| Shim labeled "benchmark-only" | Runtime integration | B2 gap FAZ-C'de; scope creep avoid |
| `cost_usd` axis `.remaining` direct mutate | `record_spend` çağrısı (ledger append) | Benchmark evidence trail yerine run_state only — shim hedefi |
| CHANGELOG echo (new docs §3.2 edit yok) | Docs §3.2 rewrite | Tutarsızlık yaratmaz; cf8b30e final |
| Recipe 6-step inline | Separate file | Benchmark docs tek merkezde |

---

## 5. Acceptance Checklist

### Shim
- [ ] `mock_transport._maybe_consume_budget` envelope `cost_actual.cost_usd` okur
- [ ] Run state `budget.cost_usd.remaining` decrement edilir (non-negative clamp)
- [ ] Shim clearly label — docstring "BENCHMARK-ONLY" + FAZ-C reference
- [ ] `state["revision"]` yeniden hesaplanır (`run_revision()`)

### Helper + test
- [ ] `assert_cost_consumed(run_state, axis, min_consumed=0.0)` → limit - remaining >= min_consumed
- [ ] `TestCostReconcile::test_cost_usd_drained` happy path: consumed > 0 after governed_review

### Docs
- [ ] `docs/BENCHMARK-SUITE.md §9` 6-step recipe visible
- [ ] `§8.3` deferred list explicit FAZ-C-routed for full bugfix + real full mode
- [ ] `§3.2` missing-key runtime-docs alignment referenced to cf8b30e

### Regression
- [ ] B7 v1 tests (6/6 pass) preserved
- [ ] Main suite 2135 pass unchanged
- [ ] Ruff + mypy clean
- [ ] `_KINDS == 27`

---

## 6. Risk Register (v2)

| Risk | L | I | Mitigation |
|---|---|---|---|
| R1 Shim state.v1.json schema-invalid write | L | M | Re-validate via `run_revision()`; load_run round-trip test |
| R2 Shim race with driver state writes | L | L | Dispatcher runs sequentially under test; no concurrency |
| R3 Assertion false-positive (no spend reported in envelope) | L | L | Happy envelopes already carry `cost_actual.cost_usd` |
| R4 Recipe staleness after FAZ-C | M | L | Recipe marks "live for B7 v1 patterns; FAZ-C may extend" |
| R5 CHANGELOG echoing may confuse readers (dupe docs pin) | L | L | Explicit cross-reference to cf8b30e |

---

## 7. Scope Dışı (B7.1 v2 → FAZ-C)

- **Full bundled `bug_fix_flow` E2E** (patch plumbing + input_envelope builder + workspace policy loader injection) → **FAZ-C PR-C1**
- **Real-adapter full mode** (context_pack_ref + secret flow via `secrets.allowlist_secret_ids` + manifest env parity) → **FAZ-C PR-C2**
- **`cost_usd` runtime integration** (adapter transport path reconcile; B2 gap closure) → **FAZ-C PR-C3**
- Cross-class cost routing — FAZ-C stratejik
- Merge-patch policy-sim (RFC 7396) — FAZ-C
- Full `Executor.run_step` dry-run — FAZ-C
- Vision/audio registry — FAZ-C/D

---

## 8. Cross-PR Conflict Resolution (v2)

- **B2**: benchmark `cost_usd` shim B2 runtime integration gap'ini maskelemez; shim label + docstring açıkça gap'e referans.
- **B4**: orthogonal.
- **B5**: metric families benchmark output tüketebilir (FAZ-C'de metric assertion eklenebilir).
- **B6**: review_ai_flow + bug_fix_flow contract'larına dokunmaz.
- **B7 v1**: extend only (test + docs delta).

---

## 9. Codex iter-2 için açık soru: YOK

v1'deki 4 Q Codex iter-1'de cevaplandı ve v2 absorb edildi (2 FAZ-C'ye, 2 moot). Yeni Q yok.

---

## 10. Audit Trail

| Iter | Date | Verdict |
|---|---|---|
| v1 (Claude draft) | 2026-04-18 | Pre-Codex iter-1 submit |
| **iter-1** (CNS-20260418-040, thread `019d9f63`) | 2026-04-18 | **REVISE** — 5 blocker (2 büyük item runtime gap, 3 contract yanlışı); 5 warning + Q1-Q4 cevap |
| **v2 (iter-1 absorb)** | 2026-04-18 | Pre-iter-2 submit (scope halved; 2 item FAZ-C-bound) |
| iter-2 | TBD | AGREE expected |

### Plan revision history

| Ver | Change |
|---|---|
| v1 | 5 B7 v1 deferred item; 3-commit ~630 LOC; full bundled bugfix E2E + real full mode + cost reconcile + walker pin + recipe |
| **v2** | **iter-1 REVISE absorb** (scope trim): 2 büyük item (full bundled bugfix + real full mode) FAZ-C'ye; `cost_usd` reconcile **benchmark-only shim** olarak labeled; walker pin cf8b30e echo (new behavior yok); recipe 6-step. 2-commit ~230 LOC; runtime LOC=0. |

**Status**: Plan v2 hazır. Codex thread `019d9f63` iter-2 submit için hazır. AGREE beklenir.
