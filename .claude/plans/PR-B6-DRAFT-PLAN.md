# PR-B6 Draft Plan v1 — Review AI + Commit AI Workflow Runtime (thin scope)

**Tranche B PR 6/9** — post CNS-20260417-030 iter-1 `thin B6` advisory. Codex verdict: "B6 yalnızca review_ai_flow runtime alt yarısı, extracted_outputs → artifact write, ve write-lite review/commit step'leri olsun; benchmark ve maliyet seed'i B7'ye kalsın."

**Draft key positions (iter-1 için Codex'e soracak):**
- **Scope thin:** B6 = review_ai_flow runtime lower half + commit AI write-lite step, ~800 LOC target.
- **Benchmark runner + governed_review scoring:** B7'ye; B6 sadece artifact üretimini + step_record wiring'i sağlar.
- **Cost seed fixture (tokens_*, cost_usd price mapping):** B7'ye; B6 mevcut `cost_actual` pass-through ile yetinir.
- **Commit AI kontrat yüzeyi açık soru:** `operation` enum closed + `commit_write` capability olmadığı için "commit AI" write-lite'ı tam nerede oturacak? Draft pozisyonu: **yeni bir `operation` eklemek yok**, commit AI bir **adapter step** olarak (text output → commit-message artifact, ao-kernel commit uygulamaz) modellenir. Alt ayrıntı Codex'e Q1.

## Bağlam — Kod Yüzeyinde Bulunanlar

| Yapı | B0'da Ship Oldu mu? | B6'da Yapılacak |
|---|---|---|
| `ao_kernel/defaults/workflows/review_ai_flow.v1.json` | ✅ (3 step: compile_context + invoke_review_agent + await_acknowledgement) | Dokunma — mevcut kontrat pin'i |
| `ao_kernel/defaults/schemas/review-findings.schema.v1.json` | ✅ | Dokunma |
| `agent-adapter-contract.schema::capabilities[] +review_findings` | ✅ | Dokunma |
| `workflow-definition.schema::capability_enum +review_findings` | ✅ | Dokunma |
| `adapter_invoker._walk_output_parse()` + `InvocationResult.extracted_outputs` | ✅ (PR-A3/B0) — walker + tests yeşil | Dokunma |
| `codex-stub.manifest.v1.json` output_parse rule | ✅ | Dokunma |
| `ao_kernel/fixtures/codex_stub.py` → emits `review_findings` | ✅ | Dokunma |
| **Executor lower-half: extracted_outputs → artifact write** | ❌ | **YAPILACAK (B6 core)** |
| **step_record.output_ref dolumuna extracted_outputs dahil** | ❌ | **YAPILACAK** |
| `commit_ai_flow.v1.json` bundled workflow | ❌ (grep = empty) | **YAPILACAK** |
| `commit-message.schema.v1.json` typed artifact | ❌ | **YAPILACAK (Q1'ye bağlı)** |
| `tests/benchmarks/` runner | ❌ | B7 scope |

**Gerçek B6 gap (mevcut kodda)** — `ao_kernel/executor/executor.py::_normalize_invocation_for_artifact` satır 695-719:

```python
def _normalize_invocation_for_artifact(invocation_result, *, adapter_id):
    return {
        "adapter_id": adapter_id,
        "status": invocation_result.status,
        "diff": invocation_result.diff,
        # ... (extracted_outputs YOK)
    }
```

Walker `InvocationResult.extracted_outputs` doldurur; normalize edici bu field'ı artifact payload'una koymaz → disk'te kayıp. B6 fix: normalize edicinin `extracted_outputs` dahil etmesi + (opsiyonel) her capability için ayrı artifact yazımı.

## 1. Amaç

B0 contract pin'i (review_ai_flow.v1.json + typed artifact kontratı) ve B0/A3 walker runtime'ını (extracted_outputs populated) sonuca bağla:
1. **Review AI lower half:** extracted_outputs → `step_record.output_ref` ile disk'te schema-valid typed artifact.
2. **Commit AI write-lite workflow:** yeni `commit_ai_flow.v1.json` bundled workflow + typed artifact schema + codex-stub fixture payload.
3. **Bundled workflow acceptance tests** — schema parse + cross-ref valid + end-to-end codex-stub driver run.

**Out of scope (thin B6):**
- `tests/benchmarks/` runner, scoring harness, `--benchmark-mode=fast|full` → B7
- `price-catalog` lookup + `cost_usd` computation in artifact → B7 (B6 sadece `cost_actual` pass-through)
- `score` threshold gate wiring → B7
- Full `governed_review`/`governed_bugfix` scenario fixtures → B7

### Kapsam özeti (est.)

| Katman | Modül | Satır (est.) |
|---|---|---|
| Executor normalize edici | `ao_kernel/executor/executor.py` delta (`_normalize_invocation_for_artifact` + adapter_returned payload) | ~25 delta |
| Capability artifact writer | `ao_kernel/executor/artifacts.py` delta (yeni `write_capability_artifact()` helper) | ~60 |
| MultiStepDriver wiring | `ao_kernel/executor/multi_step_driver.py` delta (`_run_adapter_step` → adapter ekstra artifact output_ref'leri set eder; step_record.extracted_output_refs alanı) | ~50 delta |
| Workflow-run schema genişletme | `ao_kernel/defaults/schemas/workflow-run.schema.v1.json` step_record delta: yeni opsiyonel `extracted_output_refs: map<capability, ref>` | ~15 delta |
| Bundled: commit_ai_flow | `ao_kernel/defaults/workflows/commit_ai_flow.v1.json` | ~70 |
| Schema: commit-message | `ao_kernel/defaults/schemas/commit-message.schema.v1.json` (Q1 onayına bağlı) | ~70 |
| Schema delta: capability_enum +`commit_message` (Q1'e bağlı) | `agent-adapter-contract.schema.v1.json` + `workflow-definition.schema.v1.json` | ~10 delta |
| Adapter: codex-stub manifest output_parse genişletme | `codex-stub.manifest.v1.json` (Q1'e bağlı — 2. rule) | ~10 delta |
| Fixture: codex_stub emits commit_message | `ao_kernel/fixtures/codex_stub.py` delta | ~25 delta |
| Docs | `docs/BENCHMARK-SUITE.md` lower-half shipped note + new `docs/WRITE-LITE-FLOWS.md` (opsiyonel, review + commit flow operatör notu) | ~80 |
| Tests | `test_executor_b6_runtime.py` (extracted_outputs → artifact roundtrip + commit flow driver run + schema cross-ref) | ~320 |
| CHANGELOG | `[Unreleased]` PR-B6 entry | ~40 |
| **Toplam** | 5 delta + 2 yeni bundled + 1-2 yeni schema + 1 fixture delta + ~18 test | **~700-825 satır (target ~800)** |

- Yeni evidence kind: 0 (mevcut `adapter_returned` payload genişler)
- Yeni adapter capability: 0 veya 1 (**Q1'e bağlı** — `commit_message` eklenirse)
- Yeni core dep: 0
- Yeni schema: 1 (commit-message) veya 0 (Q1'e bağlı)
- Yeni bundled workflow: 1 (commit_ai_flow)
- Hard dep: B1 (merged #97) — B6 B1 fencing entry'sine dokunmaz; B1 scope-dışı §589 satırında "Review AI workflow runtime" eklenmiş.

## 2. Scope İçi

### 2.1 Executor → Artifact Write (Review AI lower half)

**Mevcut durum** (`ao_kernel/executor/executor.py:695-719`):

```python
def _normalize_invocation_for_artifact(invocation_result, *, adapter_id):
    return {
        "adapter_id": adapter_id,
        "status": invocation_result.status,
        "diff": invocation_result.diff,
        "error": invocation_result.error,
        "finish_reason": invocation_result.finish_reason,
        "commands_executed": list(invocation_result.commands_executed or ()),
        "cost_actual": invocation_result.cost_actual,
        "stdout_tail_ref": getattr(invocation_result, "stdout_tail_ref", None),
        "stderr_tail_ref": getattr(invocation_result, "stderr_tail_ref", None),
    }
```

**B6 delta — Strateji B "per-capability artifact" (önerilen):**

Her capability için ayrı `{step_id}-{capability}-attempt{n}.json` artifact yazılır. Toplanan output_ref'ler `step_record.extracted_output_refs` map'ine gider; ana `step_record.output_ref` mevcut normalize edilmiş invocation artifact'ine işaret etmeye devam eder (backward compat).

```python
# ao_kernel/executor/artifacts.py — yeni public helper
def write_capability_artifact(
    run_dir: Path, step_id: str, attempt: int,
    capability: str, payload: Mapping[str, Any],
) -> tuple[str, str]:
    """{run_dir}/artifacts/{step_id}-{capability}-attempt{n}.json kanonik yaz.

    Naming: write_artifact pattern'ı aynı (atomic tmp+fsync+rename +
    fsync dir); sadece filename şablonu capability-key'li.
    """
```

**Executor._run_adapter_step delta** (satır 419-447 civarı):

```python
# write_artifact sonrası (mevcut satır 427):
extracted_refs: dict[str, str] = {}
for capability, payload in invocation_result.extracted_outputs.items():
    cap_ref, _cap_sha = write_capability_artifact(
        run_dir=run_dir, step_id=step_id_for_events,
        attempt=attempt, capability=capability, payload=payload,
    )
    extracted_refs[capability] = cap_ref

# adapter_returned payload genişle:
returned = emit_event(
    ..., payload={
        ...,
        "output_ref": output_ref,
        "output_sha256": output_sha256,
        "extracted_output_refs": extracted_refs,  # NEW
        "attempt": attempt,
    },
    ...
)
```

**Rationale — neden Strateji B (per-capability) Strateji A (inline extracted_outputs) yerine?**
- Her capability'nin kendi SHA-256 + manifest entry'si olur → replay determinism ayrı ayrı doğrulanır
- Schema-valid payload tek başına lookup edilir; operatör debug için `cat artifacts/step-x-review_findings-attempt1.json` çalışır
- PR-A5 evidence manifest `artifacts/**/*.json` glob'ıyla otomatik kapsar — ekstra kod yok
- Workflow-run.schema step_record genişletme minimal (yeni map field)

### 2.2 Workflow-run Schema Genişletme

`workflow-run.schema.v1.json::step_record` içine:

```jsonc
"extracted_output_refs": {
  "type": "object",
  "patternProperties": {
    "^[a-z][a-z0-9_]{0,63}$": {"type": "string", "minLength": 1}
  },
  "additionalProperties": false,
  "description": "Map<capability, run-relative path>. Her capability için yazılmış typed artifact'in run-relative pointer'ı. Sadece adapter_invoker.output_parse rule walker'ı extract ettikleri için dolduruluyor; pre-FAZ-B run'lar için absent. B0 walker ships; B6 dolumu."
}
```

**Schema delta risk:** Bu field mevcut run kayıtlarında absent olduğu için backward compat. CAS mutator her artifact yazımından sonra step_record'a key ekler.

### 2.3 Commit AI Workflow — Write-lite

**Q1'e kadar tentative design** (Codex onayına bağlı):

Yaklaşım: Commit AI **adapter** (LLM) step, çıktı olarak plain text commit message'ı typed artifact olarak `output_parse` rule ile extract edilir. **Ao-kernel `git commit` uygulamaz** — operator workflow'un sonunda (veya başka bir non-B6 step'te) commit message'ı kullanır. Bu mevcut `commit_write NOT a capability` invariant'ını (agent-adapter-contract.schema.v1.json:38-39) ihlal etmez.

**`commit_ai_flow.v1.json` (bundled — minimal 2-step):**

```jsonc
{
  "$schema": "urn:ao:workflow-definition:v1",
  "workflow_id": "commit_ai_flow",
  "workflow_version": "1.0.0",
  "display_name": "Commit AI Flow",
  "description": "Context compile -> commit-message generation adapter -> typed artifact (commit-message.schema.v1.json). B6 runtime for master plan item #20 (write-lite). Operator/next-step integration (actual git commit application) is out of scope; the bundled workflow only produces the typed commit-message artifact. expected_adapter_refs declares codex-stub for deterministic CI; workspaces can override.",
  "steps": [
    {
      "step_name": "compile_context",
      "actor": "ao-kernel",
      "operation": "context_compile"
    },
    {
      "step_name": "invoke_commit_agent",
      "actor": "adapter",
      "adapter_id": "codex-stub",
      "required_capabilities": ["read_repo", "commit_message"]
    }
  ],
  "expected_adapter_refs": ["codex-stub"],
  "required_capabilities": ["read_repo", "commit_message"],
  "tags": ["commit", "message", "write-lite"]
}
```

**`commit-message.schema.v1.json` (NEW typed artifact):**

```jsonc
{
  "$id": "urn:ao:commit-message:v1",
  "type": "object",
  "required": ["schema_version", "subject"],
  "properties": {
    "schema_version": {"const": "1"},
    "subject": {"type": "string", "minLength": 1, "maxLength": 72},
    "body": {"type": "string"},
    "breaking_change": {"type": "boolean", "default": false},
    "trailers": {
      "type": "array",
      "items": {"type": "string"},
      "description": "Conventional Commits trailers (Co-Authored-By, Signed-off-by, ...)"
    }
  },
  "additionalProperties": false
}
```

**Capability enum delta (agent-adapter-contract + workflow-definition):**

```diff
  "enum": [
    "read_repo",
    "write_diff",
    "run_tests",
    "open_pr",
    "human_interrupt",
    "stream_output",
-   "review_findings"
+   "review_findings",
+   "commit_message"
  ]
```

**codex-stub manifest delta — 2. output_parse rule:**

```jsonc
"output_parse": {
  "rules": [
    {"json_path": "$.review_findings", "capability": "review_findings",
     "schema_ref": "review-findings.schema.v1.json"},
    {"json_path": "$.commit_message", "capability": "commit_message",
     "schema_ref": "commit-message.schema.v1.json"}
  ]
}
```

**codex_stub fixture delta** — envelope'a `commit_message` field ekle (stabil placeholder `"chore: stub commit"`).

### 2.4 Adapter_returned Event Payload Schema

`evidence_emitter._KINDS` dokunulmaz (0 yeni kind). `adapter_returned` payload'una `extracted_output_refs: object` eklenir — mevcut kind'ın payload shape'i zaten free-form.

### 2.5 Backward Compat & Dormant-Gate

- Walker B0'dan beri çalışıyor → pre-B6 run kayıtlarında `extracted_outputs` hep empty; `extracted_output_refs` step_record key'i de absent (optional field).
- Opt-in: adapter manifest'te `output_parse` yoksa (örn. `gh-cli-pr`) → extracted_outputs empty → B6 delta no-op. Backward compat 100%.
- CLAUDE.md §2 fail-closed: capability artifact write **başarısız olursa** (disk full, schema mismatch) → `AdapterOutputParseError` **fırlat** (fail-closed, run `error.category=output_parse_failed`). Evidence emission side-channel değil; invariant bu.
- CLAUDE.md §2 fail-open: `adapter_returned` evidence emit ekstra payload ile başarısız olursa mevcut `try/except` wrapper zaten swallow eder.

### 2.6 Test Stratejisi

Yeni file: `tests/test_executor_b6_runtime.py` (~18 test):
- **Review flow roundtrip (6):** driver run → codex-stub invoke → extracted_outputs popule → capability artifact yazılır → SHA-256 match → schema validate → step_record.extracted_output_refs["review_findings"] = path.
- **Commit flow roundtrip (4):** aynı, commit_message için.
- **Backward compat (3):** `output_parse`-lı olmayan adapter + pre-B6 run kaydı + empty extracted_outputs.
- **Fail-closed (3):** schema mismatch → run.state=failed + error.category=output_parse_failed; disk write error → fırlat.
- **Bundled contract (2):** `commit_ai_flow.v1.json` schema-valid + cross-ref codex-stub ile geçerli.

Mevcut `test_pr_b0_contracts.py::test_bundled_review_ai_flow_cross_ref_valid_against_bundled_adapters` pattern'ı takip edilir.

### 2.7 Docs Deltas

- `docs/BENCHMARK-SUITE.md` §2.2 Transport tablosu: "B6: runtime" satırlarının hepsi "shipped (PR-B6 commit <sha>)" olarak işaretlenir; lower-half now-complete notu.
- `docs/WRITE-LITE-FLOWS.md` NEW (opsiyonel, Codex'e Q5'te sorarız) — review + commit flow operatör rehberi, write-lite kategorisinin genel tanıtımı.

## 3. Write Order (5-commit DAG)

| Step | İçerik | Risk |
|---|---|---|
| 1 | `artifacts.write_capability_artifact()` helper + unit tests | Düşük |
| 2 | `executor._normalize_invocation_for_artifact` + `_run_adapter_step` capability artifact loop + workflow-run schema genişletme | Orta |
| 3 | `commit-message.schema.v1.json` + capability_enum +commit_message (2 schema) + codex-stub manifest 2. rule + fixture emit delta | Düşük |
| 4 | `commit_ai_flow.v1.json` bundled workflow + cross-ref test | Düşük |
| 5 | Integration tests (review + commit roundtrip) + backward compat + fail-closed + docs + CHANGELOG | Orta |

**Commit DAG:**
```
commit 1: artifacts helper + unit tests          (Step 1)
commit 2: executor normalize + schema + delta tests   (Step 2)
commit 3: commit-message schema + enum delta + codex-stub + fixture  (Step 3)
commit 4: commit_ai_flow bundled + contract tests     (Step 4)
commit 5: integration + docs + CHANGELOG         (Step 5)
```

Her commit kendi dep zincirini kapatır; Step 2 B6'nın en yüksek riski (executor değişimi — mevcut PR-A4b multi_step_driver pattern'ını korumalı).

## 4. Scope Dışı (PR-B7+)

| Alan | PR |
|---|---|
| `tests/benchmarks/` runner + `--benchmark-mode=fast|full` | B7 |
| `governed_review` scoring (severity threshold, score gate) | B7 |
| `governed_bugfix` scenario | B7 |
| `price-catalog` lookup in `cost_actual` | B7 |
| `cost_usd` derived field in artifact | B7 |
| v3.2.0 release packaging | B8 |
| Actual `git commit` application (commit AI output consumption) | FAZ-C+ (operator owns) |
| OTEL bridge in artifact trace | stretch / FAZ-C+ |

## 5. Acceptance Checklist

- [ ] `ao_kernel/executor/artifacts.py::write_capability_artifact()` atomic tmp+fsync+rename (mevcut `write_artifact` pattern mirror)
- [ ] `executor._normalize_invocation_for_artifact` invocation_result'ın `extracted_outputs` field'ını artifact payload'a DAHIL ETMEZ (tekil artifact per-capability yazılır, kaynağa inline gömmez)
- [ ] `_run_adapter_step`: her extracted_output capability için `write_capability_artifact` call + path biriktir
- [ ] `adapter_returned` event payload'ında `extracted_output_refs: {capability: ref}` field'ı (map boş ise absent veya `{}`)
- [ ] `step_record.extracted_output_refs` schema-valid (opsiyonel field); mevcut run'lar backward compat
- [ ] **Review AI roundtrip:** MultiStepDriver run + codex-stub invoke → `review_findings` capability artifact disk'te + schema-valid + step_record.extracted_output_refs["review_findings"] dolu
- [ ] **Commit AI roundtrip:** aynı, commit_message için
- [ ] **Schema validate:** commit-message.schema.v1.json + commit_ai_flow.v1.json + capability_enum parity drift test
- [ ] **Backward compat — `output_parse`-less adapter:** gh-cli-pr gibi extracted_outputs empty, step_record.extracted_output_refs absent veya `{}`
- [ ] **Backward compat — pre-B6 run replay:** eski run kaydı `extracted_output_refs` field'ı olmadan parse edilir
- [ ] **Fail-closed — schema validation failure:** capability artifact schema mismatch → walker `AdapterOutputParseError` (mevcut B0 davranış korunur); ekstra artifact write aşamasında fail → walker'dan önce raise
- [ ] **Fail-closed — disk write failure:** `write_capability_artifact` OSError → workflow.state=failed + error.category=output_parse_failed
- [ ] **Evidence manifest integration:** PR-A5 `generate_manifest` scan'i yeni capability artifact'ları `artifacts/**/*.json` glob'ıyla kapsar (otomatik)
- [ ] **B1 regression:** fencing kwargs'lı run yeşil; step_failed flow korunur
- [ ] **PR-A4b driver regression:** mevcut `test_executor_integration.py` yeşil; retry_once step_record append pattern'ı korunur
- [ ] **PR-A5 evidence replay:** capability artifact'larının SHA-256 manifest'te deterministic
- [ ] `governed_review` benchmark **deferred test** (dormant marker + B7 reference)
- [ ] CHANGELOG `[Unreleased]` → FAZ-B PR-B6; v3.2.0 release notes B8'e bırakılır
- [ ] ruff + mypy strict clean; test baseline + ~18 new test

## 6. Risk Register

| Risk | Seviye | Mitigation |
|---|---|---|
| `_normalize_invocation_for_artifact` imza değişimi PR-A4b test'leri kırar | Düşük | Ekstra parametre yok; return shape genişlemez (extracted_outputs dahil edilmez). Walker path'i ayrı. |
| Per-capability artifact file explosion (manifest scan maliyeti) | Düşük | Tipik case 1-2 capability per step; eski glob zaten `**/*.json` tarıyor, marjinal maliyet |
| `step_record.extracted_output_refs` schema widening backward compat regression | Düşük | Field optional; mevcut `additionalProperties: false` zaten step_record'da var — schema delta sadece yeni anahtar eklemek |
| Commit AI "operation vs capability" yanlış modellendi | **Orta (Q1 açık)** | Draft: adapter+output_parse yaklaşımı seçildi; Codex'e soruluyor. Alternatif: yeni `operation=commit_message` (actor=ao-kernel) — ama bu LLM invoke ao-kernel responsibility olur, FAZ-B ilkelerine aykırı |
| Codex-stub fixture payload'a `commit_message` eklemek review_ai test'leri kırar | Düşük | Fixture envelope'ı free-form; yalnızca `output_parse` tarafından extract edilen field'lar adresslenir |
| Adapter_returned payload'ın genişlemesi replay determinism'i bozar | Düşük | `replay_safe=False` zaten ayar — non-deterministic payload değişimi normal (PR-A3 convention) |
| B7 scope creep (benchmark runner B6'ya sızma) | **Orta** | Codex advisory'a sadık kal; Acceptance checklist'te `governed_review` deferred olarak işaretli |
| Fail-closed chain (walker error → run.failed → cleanup) B1 fencing'e karışır | Düşük | Fencing entry `run_step` başında; walker hata olan path step_failed emit sonrası → B1 mevcut path'e uyar |
| `adapter_invoker._walk_output_parse` B0'dan gelen edge case (null payload → Mapping değil → key'e eklenmez) yeni artifact write'a etki | Düşük | Mevcut kontrat: `Mapping` olmayan payload extracted_outputs'a girmez → B6 loop empty extracted için no-op. Doc'ta pin. |

## 7. Dep & Resolved Positions

| Field | Value |
|---|---|
| Plan version | **v1 (draft)** |
| Predecessor chain | — (new; post CNS-20260417-030 iter-1 `thin B6` advisory) |
| Head SHA | `5779609` (pre-B2 docfix) |
| Base branch | `main` |
| Target branch | `claude/tranche-b-pr-b6` (yet to create) |
| FAZ-B master ref | `.claude/plans/FAZ-B-MASTER-PLAN.md` line 40 (B6 scope) |
| Hard deps merged | B0 (#96 contract pin) + B1 (#97 coordination runtime) |
| Soft deps | — (B2 cost, B3 routing, B4 sim, B5 metrics hepsi paralel/bağımsız) |
| Active CNS thread | CNS-20260417-030 (draft will resume in iter-2) |
| Backward compat guards | Pre-B0 run kayıtları + non-`output_parse` adapter'lar + PR-A4b driver; B6 delta strictly additive |

## 8. Acceptance for iter-1 → Plan v1 Submit

Plan v1 iter-1'e Codex'ten aşağıdaki yanıtları bekliyor. Alıntılanmayan pozisyonlar draft'ta kilitlenir.

## 9. Açık Sorular (Codex iter-1'e)

**Q1 — Commit AI kontrat yüzeyi (en kritik).** Mevcut `agent-adapter-contract.schema::capabilities[]` enum `commit_write` kabul etmiyor ("git commit and branch operations are ao-kernel's responsibility"). Ve `operation` enum closed, `commit_message` yok. Draft pozisyonum: commit AI'ı **adapter step + yeni `commit_message` capability + `output_parse`-extracted typed artifact (`commit-message.schema.v1.json`)** olarak modelle; ao-kernel `git commit` uygulamaz (operator downstream kullanır). **Bu doğru mı, yoksa alternative: (a) commit AI'ı ao-kernel `operation` olarak ekle + LLM invoke ao-kernel'da — ama bu `[coding]` sorumluluk ayrımını bozar; (b) commit AI'ı tamamen scope-out yap ve B6'yı sadece review AI'a daralt?**

**Q2 — Per-capability artifact file strategy vs inline.** `InvocationResult.extracted_outputs` disk'e yazılırken iki pattern var: (A) mevcut `output_ref` artifact'ine inline JSON field olarak göm, (B) her capability için ayrı `{step_id}-{capability}-attempt{n}.json` dosya yaz + step_record'da map<capability, ref>. Draft: **B** seçildi (replay determinism, schema validation ayrı, PR-A5 evidence manifest otomatik kapsar). **Onay?** Eğer A tercih edilirse workflow-run.schema delta farklı olacak (extracted_output_refs yerine inline field).

**Q3 — B6 `docs/WRITE-LITE-FLOWS.md` yeni docs dosyası vs mevcut docs'a inline.** Write-lite flow'ları (review + commit) anlatan bir operatör dökümanı gerek mi, yoksa `docs/BENCHMARK-SUITE.md` lower-half shipped notu yeterli mi? Draft: opsiyonel, küçük scope. **Codex'in tercihi?**

**Q4 — extracted_output_refs field naming.** `step_record.extracted_output_refs: map<capability, ref>` naming tutarlı mı mevcut `output_ref` (singular) ile? Alternative: `capability_output_refs`, `typed_output_refs`. Draft: `extracted_output_refs` (walker sözcüğünden devamlılık için). **Onay?**

**Q5 — Thin scope doğrulaması.** Codex advisory "benchmark ve maliyet seed'i B7'ye" dedi. Draft B7 scope dışı listesi: benchmark runner + `governed_review` scoring + `price-catalog` lookup + `cost_usd` compute. **B6'da cost yansımalı bir şey kalmalı mı (örn. `extracted_output_refs` artifact'ine cost_actual kopyası)?** Draft: hayır, mevcut `output_ref` (normalize invocation artifact'i) zaten `cost_actual` taşıyor — B6 değişiklik yok.

## 10. Audit Trail

| Field | Value |
|---|---|
| Plan version | v1 (DRAFT — bu dosya) |
| Predecessor | N/A (ilk draft) |
| Head SHA | `5779609` |
| Active CNS thread | CNS-20260417-030 (iter-1 advisory verdict: "thin B6"; iter-2 plan v1 AGREE bekleniyor) |
| Previous CNS threads | — |
| Scope thin advisory absorb | Codex: "B6 = review_ai_flow runtime lower half + extracted_outputs artifact write + write-lite review/commit; benchmark + cost seed → B7" (full-fidelity absorbed) |
| B7 boundary | Codex explicit: benchmark runner + score scoring + cost price lookup B7'de |
| Infra reuse | `write_artifact()` (PR-A4b), `_walk_output_parse` (PR-A3/B0), `InvocationResult.extracted_outputs` (B0), codex-stub manifest (B0), `_normalize_invocation_for_artifact` (PR-A4b) |
| B0/B1 regression guards | `TestOutputParseExtraction` + `TestBundledCodexStubEndToEnd` (B0) + `test_coordination_*` (B1) + `test_executor_integration` (PR-A4b) |

**Status:** Draft v1. Codex'e iter-1 submit (Q1-Q5'e yanıt + blocker/workstream veto hakkı).
