# PR-B6 Implementation Plan v4 — Review AI + Commit AI Workflow Runtime (thin, driver-owned)

**Tranche B PR 6/9** — post CNS-20260417-033 iter-3 PARTIAL verdict. v3 iter-2 bulgularını kapadı (4/4 absorbe: on_failure string, AdapterInvocationFailedError translation, adapter_returned invariant, `_LEGAL_CATEGORIES` parity). iter-3 kalan 1 blocker + 1 temizlik:

- **Blocker**: `capability_output_refs` driver'da üretildikten sonra completion write path'lerine (`_record_step_completion` ilk-attempt + `_update_placeholder_to_completed` retry-success, multi_step_driver.py:1012 + :1204) nasıl taşınacağı pinlenmedi. Her iki helper bugün yalnız `output_ref` taşıyor → retry-success map'i sessizce düşebilir.
- **Temizlik**: Stale "schema widen" dili commit DAG + bazı acceptance/notlarda kaldı (v3 doğru olarak "schema DEĞİŞMEZ" dedi).

v4 iki residual'ı pinler.

**Head SHA:** `59ae712` (PR-B2 merge sonrası). Base branch: `main`. Active branch: `claude/tranche-b-pr-b6`.

**v3 key absorb (CNS-033 iter-2):**

- **iter-2 B1 (Yüksek) — `on_failure` schema string enum**: v2 örneği `on_failure: {"strategy": "fail"}` obje verdi; schema `enum: ["transition_to_failed", "retry_once", "escalate_to_human"]` string bekliyor (workflow-definition.schema.v1.json:132). Driver de string karşılaştırıyor (multi_step_driver.py:947). v3 fix: her step için `on_failure: "transition_to_failed"` (§2.5 güncel commit_ai_flow).

- **iter-2 B2 (Yüksek) — `AdapterInvocationFailedError` catch ekle**: v2'de `invocation_failed` kategorisi planda ama translation yoktu. `invoke_cli`/`invoke_http` transport failures'ı `AdapterInvocationFailedError` olarak raise ediyor (errors.py:81); mevcut driver yalnız `PolicyViolationError` + stale fencing yakalıyor. v3 `_run_adapter_step` catch eklenir:
  ```python
  except AdapterInvocationFailedError as exc:
      # Codex iter-2 semantic pin:
      # - timeout/http_timeout → category=timeout
      # - subprocess_crash → category=adapter_crash
      # - kalan transport-layer → category=invocation_failed
      category = (
          "timeout" if exc.reason in ("timeout", "http_timeout")
          else "adapter_crash" if exc.reason == "subprocess_crash"
          else "invocation_failed"
      )
      raise _StepFailed(
          reason=f"adapter invocation failed: {exc!s}",
          attempt=attempt,
          category=category,
          code=exc.reason.upper() if exc.reason else "INVOCATION_FAILED",
      ) from exc
  ```

- **iter-2 B3 (Orta) — `adapter_returned` payload ACCEPTANCE KALDIR**: v2 §3 + §5 bu emit'i istiyordu; ama gerçek `adapter_returned` event executor içinde, driver materialization'dan ÖNCE emit ediliyor (executor.py:429). Executor invariant korunacaksa bu madde **kaldırılır**. v3 §3 + §5 revize: capability_output_refs sadece `step_record` içinde persist; `adapter_returned` evidence payload DOKUNULMAZ.

- **iter-2 B4 (Düşük, çözüldü) — `_LEGAL_CATEGORIES` parity drift mevcut**: Schema `error.category.enum` 10 value = `{timeout, invocation_failed, output_parse_failed, policy_denied, budget_exhausted, adapter_crash, approval_denied, ci_failed, apply_conflict, other}` (workflow-run.schema.v1.json:404-414). `_LEGAL_CATEGORIES` runtime set 8 value = `{timeout, policy_denied, adapter_error (!), budget_exhausted, ci_failed, apply_conflict, approval_denied, other}` — **`adapter_error` schema'da yok** (drift!); `invocation_failed`/`output_parse_failed`/`adapter_crash` runtime'da yok. v3 fix: `_LEGAL_CATEGORIES` schema ile birebir sync (`adapter_error` kaldırılır; 3 missing eklenir). Parity test **ZORUNLU** (§5 acceptance).

- **BENCHMARK-SUITE narrative temizliği**: "output_ref = review artifact" narrative legacy ship etmemiş (sadece doc drift). v3 "deprecated" dili kullanmaz; cümle direkt silinir, yerine capability_output_refs pin'i.

**v2 key absorb (CNS-033 iter-1) — v3'te hâlâ geçerli:**

- **iter-1 B1 (Yüksek) — Commit AI walker kontratı: OBJECT payload + commit_ai_flow full schema**: Walker `adapter_invoker.py:72,605` sadece `Mapping` payload'larını `extracted_outputs`'a alıyor. Draft v1 "plain text commit message" + string fixture placeholder önermişti → walker empty döndürür. v2 fix: `commit_message` capability payload **object-shape** (`{schema_version, subject, body?, breaking_change?, trailers?[]}`, schema v2'de zaten object-shape ama fixture + narrative revize). Ayrıca `commit_ai_flow.v1.json` zorunlu schema alanlarını taşımalı: `default_policy_refs`, `created_at`, step-level `on_failure` (workflow-definition.schema.v1.json gereği).

- **iter-1 B2 (Yüksek) — Driver error plumbing: ExecutionResult.invocation_result üstünden materialization + error-category ya widen ya "other"a düşür**:
  - `ExecutionResult` ZATEN `invocation_result: InvocationResult | None` taşıyor (executor.py:72). `InvocationResult.extracted_outputs` walker tarafından dolduruluyor. Yani **yeni field EKLENMEZ**; driver `exec_result.invocation_result.extracted_outputs` üstünden erişir.
  - `_run_adapter_step` capability-artifact-write failure + output-parse-walker failure için `_StepFailed` translation EKLENMELİ.
  - `_LEGAL_CATEGORIES` (multi_step_driver.py:1588) mevcut: `{timeout, policy_denied, adapter_error, budget_exhausted, ci_failed, apply_conflict, approval_denied, other}`. v2 seçimleri:
    - **Option A**: `_LEGAL_CATEGORIES`'e `output_parse_failed` + `invocation_failed` ekle (schema-workflow-run error.category enum'u da widen). Daha explicit kategori.
    - **Option B**: `_legal_error_category` fallback "other" davranışını kabul et; `error.details` ile match et acceptance.
    - **Seçim: Option A** — plan v1'in acceptance maddesi "error.category=output_parse_failed" açıkça istiyor; narrative'e sadık kal. **v3 iter-2 tespit**: workflow-run schema `error.category.enum` ZATEN 10 kategori taşıyor (`invocation_failed`, `output_parse_failed`, `adapter_crash` mevcut — workflow-run.schema.v1.json:404-414). Schema widen GEREKSİZ; yalnız runtime `_LEGAL_CATEGORIES` parity sync gerekli.

- **iter-1 B3 (Orta) — Strategy B driver-owned, executor silent (contract rewrite explicit)**:
  - `_normalize_invocation_for_artifact()` **DEĞİŞMEZ** — executor schema-agnostic invariant korunur (BENCHMARK-SUITE.md:65 pin).
  - Capability artifact materialization LOOP **`MultiStepDriver._run_adapter_step`** içinde. Driver `exec_result.invocation_result.extracted_outputs` üstünden iterate eder → `write_capability_artifact()` çağırır → `step_record.capability_output_refs` map'ini CAS append ile doldurur.
  - **B0 contract rewrite**: review-findings.schema.v1.json narrative + BENCHMARK-SUITE.md review_findings lower-half pin "step_record.output_ref → review_findings artifact" idi. v2'de bu explicit rewrite: **main `output_ref` hâlâ normalize edilmiş invocation artifact; capability artifact'lar ayrı `capability_output_refs` map'inde**. BENCHMARK-SUITE.md + review-findings.schema.v1.json narrative güncellenir.

- **iter-1 B4 (Düşük) — Header SHA refresh**: `5779609` → `59ae712` (PR-B2 merge sonrası).

**Codex naming tercihi kabul**: `capability_output_refs` > `extracted_output_refs` (walker implementation detail schema'ya sızmasın).

**Docs strateji**: `docs/WRITE-LITE-FLOWS.md` **açılmaz**. BENCHMARK-SUITE.md + ADAPTERS.md (varsa; yoksa lazım değil) güncelleme yeterli.

## 1. Amaç

B0 contract pin (review_ai_flow.v1.json + typed artifact kontratı) + B0/A3 walker runtime (extracted_outputs populated) + B6 driver-owned materialization = disk'te schema-valid typed artifact per capability. İkincil: commit AI write-lite flow yeni bundled workflow olarak ship.

**Out of scope (thin B6, Codex advisory):**
- `tests/benchmarks/` runner → B7
- `governed_review` scoring (severity threshold, score gate) → B7
- `price-catalog` lookup + derived `cost_usd` → B7
- Actual `git commit` application → operator downstream

### Kapsam özeti

| Katman | Dosya | LOC (est.) |
|---|---|---|
| Artifact helper | `ao_kernel/executor/artifacts.py` delta (`write_capability_artifact()`) | ~60 |
| Driver capability materialization | `ao_kernel/executor/multi_step_driver.py` delta (`_run_adapter_step` loop + `_LEGAL_CATEGORIES` widen + error plumbing) | ~90 delta |
| Workflow-run schema | `workflow-run.schema.v1.json` step_record `capability_output_refs` (additive only; error.category enum zaten 10 value taşıyor — schema DEĞİŞMEZ) | ~15 delta |
| Commit message schema | `commit-message.schema.v1.json` (NEW) | ~70 |
| Bundled commit_ai_flow | `commit_ai_flow.v1.json` (full schema compliance) | ~90 |
| Capability enum delta | `agent-adapter-contract.schema.v1.json` + `workflow-definition.schema.v1.json` `+commit_message` | ~10 delta |
| Codex-stub manifest | `+commit_message` output_parse rule | ~10 delta |
| Fixture | codex_stub emits commit_message object | ~30 delta |
| Docs | `BENCHMARK-SUITE.md` + review-findings narrative update | ~80 delta |
| Tests | `test_executor_b6_runtime.py` (~20 test) | ~350 |
| CHANGELOG | `[Unreleased]` PR-B6 | ~45 |
| **Toplam** | 4 delta + 2 yeni + 1 fixture delta + ~20 test | **~855 satır** (v1 ~800'dü; driver error plumbing delta ile ~55 yukarı) |

- Yeni evidence kind: 0 (`_KINDS` dokunulmaz; **`adapter_returned` payload da dokunulmaz** — executor invariant korunur, capability_output_refs yalnız step_record'da persist; v3 iter-2 B3 absorb)
- Yeni adapter capability: **1** (`commit_message`)
- Yeni core dep: 0
- Yeni bundled workflow: 1 (`commit_ai_flow`)
- Executor delta: **0** (invariant korunur — schema-agnostic)
- Hard dep: B1 (merged #97) — B6 fencing entry'sine dokunmaz; B2 (merged #99) — cost pipeline'a dokunmaz

## 2. Scope İçi

### 2.1 `ao_kernel/executor/artifacts.py` — `write_capability_artifact()` helper

```python
def write_capability_artifact(
    run_dir: Path,
    step_id: str,
    attempt: int,
    capability: str,
    payload: Mapping[str, Any],
) -> tuple[str, str]:
    """Write a per-capability typed artifact: {run_dir}/artifacts/
    {step_id}-{capability}-attempt{n}.json

    Returns (run_relative_path, sha256_hex).

    Naming: same pattern as existing write_artifact (PR-A4b):
    atomic tmp+fsync+rename, fsync on parent dir. Only the filename
    template changes (capability-key suffix).
    """
```

Implementation mirrors existing `write_artifact()`. Path: `{run_dir}/artifacts/{step_id}-{capability}-attempt{n}.json`. SHA-256 over canonical JSON.

### 2.2 `ao_kernel/executor/multi_step_driver.py::_run_adapter_step` delta

**Mevcut flow**: `exec_result = self._executor.run_step(...)` → `invocation_result = exec_result.invocation_result` (or None) → `_build_step_record_completed(...)`.

**v2 delta** (driver-owned capability materialization; executor dokunulmaz):

```python
# After exec_result returned, BEFORE building step_record:
capability_output_refs: dict[str, str] = {}
extracted = (
    exec_result.invocation_result.extracted_outputs
    if exec_result.invocation_result is not None
    else {}
)
for capability, payload in extracted.items():
    try:
        cap_ref, _cap_sha = write_capability_artifact(
            run_dir=run_dir,
            step_id=step_id,
            attempt=attempt,
            capability=capability,
            payload=payload,
        )
        capability_output_refs[capability] = cap_ref
    except Exception as exc:
        # Artifact write failure = fail-closed (plan §5 invariant).
        raise _StepFailed(
            reason=(
                f"capability artifact write failed for {capability!r}: "
                f"{exc!s}"
            ),
            attempt=attempt,
            category="output_parse_failed",  # NEW category (Option A)
            code="CAPABILITY_ARTIFACT_WRITE_FAILED",
        ) from exc
```

Output-parse walker failure (upstream `adapter_invoker._walk_output_parse`) → fenceable error; driver maps:

```python
# Caught in _run_adapter_step try/except chain (where stale fencing +
# PolicyViolation currently handled):
except AdapterOutputParseError as exc:
    raise _StepFailed(
        reason=f"output_parse walker failed: {exc!s}",
        attempt=attempt,
        category="output_parse_failed",  # NEW
        code="OUTPUT_PARSE_FAILED",
    ) from exc
```

Existing `_StepFailed` handler emits `step_failed` evidence + CAS `step_record.state="failed"` (PR-A4b pattern). No change needed in `_handle_step_failure()` — category threading is automatic.

**Capability ref completion plumbing (v4 iter-3 absorb)**:

`capability_output_refs` map'i `_run_adapter_step` içinde üretildikten sonra **iki completion write path**'ine explicit taşınır — map'in retry-success dahil hiçbir path'te düşmemesi zorunludur:

1. **İlk-attempt success** (`_record_step_completion`, multi_step_driver.py:1012): `capability_output_refs` parametresi eklenir; mutator `step_record["capability_output_refs"] = refs` yazar (map boşsa absent kalır — additive schema field, `additionalProperties: false` respected).
2. **Retry-success** (`_update_placeholder_to_completed`, multi_step_driver.py:1204): aynı parametre + aynı mutator pattern.

Her iki helper'ın imzası eş zamanlı widen edilir; `_run_adapter_step` çağrı sitelerinde `capability_output_refs=capability_output_refs` (boş map veya dolu) thread edilir. Regression test `test_capability_refs_persist_across_retry` (§5 zorunlu) ikincil attempt'te map'in step_record'dan düşmediğini doğrular.

### 2.3 Workflow-run schema delta + `_LEGAL_CATEGORIES` parity sync

**Schema delta (ADDITIVE — `step_record`):**

```jsonc
// step_record additive:
"capability_output_refs": {
  "type": "object",
  "patternProperties": {
    "^[a-z][a-z0-9_]{0,63}$": {"type": "string", "minLength": 1}
  },
  "additionalProperties": false,
  "description": "Map<capability, run-relative artifact path>. Per-capability typed artifacts written by MultiStepDriver from invocation_result.extracted_outputs. Absent for pre-B6 runs and non-output_parse adapters. PR-B6 additive widen."
}
```

**`error.category.enum` — DEĞİŞMEZ** (schema zaten 10 kategori taşıyor; `invocation_failed`/`output_parse_failed`/`adapter_crash` mevcut — workflow-run.schema.v1.json:404-414).

**`_LEGAL_CATEGORIES` runtime parity sync (v3 iter-2 B4 absorb)**:

Mevcut (multi_step_driver.py:1588) — **drift**:
```python
_LEGAL_CATEGORIES = {
    "timeout", "policy_denied", "adapter_error",  # ← "adapter_error" schema'da YOK
    "budget_exhausted", "ci_failed", "apply_conflict",
    "approval_denied", "other",
}
```

v3 güncel (schema ile birebir):
```python
_LEGAL_CATEGORIES = {
    "timeout",
    "invocation_failed",      # NEW: transport-layer fail (adapter invoke)
    "output_parse_failed",    # NEW: walker/artifact-write fail
    "policy_denied",
    "budget_exhausted",
    "adapter_crash",          # NEW: subprocess crash
    "approval_denied",
    "ci_failed",
    "apply_conflict",
    "other",
}
# 10 value — schema error.category.enum ile birebir
```

`adapter_error` runtime'dan **kaldırılır** (schema'da yok; `_legal_error_category` fallback "other"a düşüyordu zaten — narrative drift). Parity test `test_error_category_parity` zorunludur (§5 acceptance): `_LEGAL_CATEGORIES == set(schema.error.category.enum)`.

**`invocation_failed` semantic pin (Codex iter-2 öneri)**:

| `AdapterInvocationFailedError.reason` | `_StepFailed.category` |
|---|---|
| `timeout` / `http_timeout` | `timeout` |
| `subprocess_crash` | `adapter_crash` |
| kalan (transport, envelope, etc.) | `invocation_failed` |

### 2.4 `commit-message.schema.v1.json` (NEW, object-shape)

```jsonc
{
  "$id": "urn:ao:commit-message:v1",
  "type": "object",
  "additionalProperties": false,
  "required": ["schema_version", "subject"],
  "properties": {
    "schema_version": {"type": "string", "const": "1"},
    "subject": {"type": "string", "minLength": 1, "maxLength": 72},
    "body": {"type": "string"},
    "breaking_change": {"type": "boolean", "default": false},
    "trailers": {
      "type": "array",
      "items": {"type": "string"},
      "description": "Conventional Commits trailers (Co-Authored-By, Signed-off-by, etc.)"
    }
  },
  "description": "Typed artifact for commit_message capability. PR-B6 ships commit AI that emits this payload; operator downstream applies actual git commit."
}
```

Walker `_walk_output_parse` Mapping payload alır → extracted_outputs'a koyar ✓.

### 2.5 `commit_ai_flow.v1.json` (bundled, FULL schema compliance)

```jsonc
{
  "$schema": "urn:ao:workflow-definition:v1",
  "workflow_id": "commit_ai_flow",
  "workflow_version": "1.0.0",
  "display_name": "Commit AI Flow",
  "description": "Context compile → commit-message generation adapter → typed artifact (commit-message.schema.v1.json). B6 runtime for master plan item #20 (write-lite). Actual git commit application is operator-downstream; bundled flow produces the typed artifact only. expected_adapter_refs declares codex-stub for deterministic CI.",
  "created_at": "2026-04-17T00:00:00+00:00",
  "default_policy_refs": [
    "ao_kernel/defaults/policies/policy_worktree_profile.v1.json"
  ],
  "steps": [
    {
      "step_name": "compile_context",
      "actor": "ao-kernel",
      "operation": "context_compile",
      "on_failure": "transition_to_failed"
    },
    {
      "step_name": "invoke_commit_agent",
      "actor": "adapter",
      "adapter_id": "codex-stub",
      "required_capabilities": ["read_repo", "commit_message"],
      "on_failure": "transition_to_failed"
    }
  ],
  "expected_adapter_refs": ["codex-stub"],
  "required_capabilities": ["read_repo", "commit_message"],
  "tags": ["commit", "message", "write-lite"]
}
```

Cross-ref test commit 4'te pin edilir.

### 2.6 Adapter capability enum widen (`+commit_message`)

```diff
// agent-adapter-contract.schema.v1.json + workflow-definition.schema.v1.json
  "capabilities[*].enum": [
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

### 2.7 Codex-stub manifest + fixture delta

**Manifest** (codex-stub.manifest.v1.json):
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

**Fixture** (codex_stub.py envelope delta):
```python
{
    # ... existing review_findings field ...
    "commit_message": {
        "schema_version": "1",
        "subject": "chore: stub commit",
        "body": "",
        "breaking_change": False,
        "trailers": [],
    },
}
```

Object-shape; walker Mapping'i extracted_outputs'a alır.

### 2.8 Docs deltas

- `docs/BENCHMARK-SUITE.md` §2.2 Transport tablosu: "B6: runtime" satırları "shipped (PR-B6)". Review AI lower-half now-complete notu + capability_output_refs map narrative.
- `docs/BENCHMARK-SUITE.md` §... review_findings artifact location narrative: step_record.output_ref hâlâ invocation artifact (normalize edilmiş); per-capability artifact'lar `step_record.capability_output_refs[capability]` üstünden.
- review-findings.schema.v1.json description/comments update: artifact location revize.
- **Yeni docs dosyası YOK** (Codex advisory).

### 2.9 Test stratejisi

Yeni file `tests/test_executor_b6_runtime.py` (~20 test):
- **Review flow roundtrip (6)**: driver run → codex-stub invoke → extracted_outputs popule → capability artifact disk'te + SHA match + schema validate + step_record.capability_output_refs["review_findings"] = path
- **Commit flow roundtrip (4)**: commit_message object-shape için aynı
- **Backward compat (3)**: output_parse-less adapter, pre-B6 run kaydı, empty extracted
- **Fail-closed (4)**: schema validation fail → category=output_parse_failed; disk write fail → category=output_parse_failed; walker fail → category=output_parse_failed; LEGAL_CATEGORIES widen regression
- **Bundled contract (3)**: commit_ai_flow.v1.json schema-valid + cross-ref codex-stub + commit-message.schema.v1.json schema-valid

## 3. Write Ordering

Single `MultiStepDriver._run_adapter_step` invocation:

```
[driver]
  ↓ exec_result = executor.run_step(...)           # executor silent (invariant)
  ↓ invocation_result = exec_result.invocation_result
  ↓ extracted = invocation_result.extracted_outputs (or {})
  ↓ for capability, payload in extracted.items():
  ↓   cap_ref = write_capability_artifact(...)    # driver-owned
  ↓   capability_output_refs[capability] = cap_ref
  ↓ step_record.capability_output_refs = capability_output_refs
  ↓ save step_record CAS (existing append)
  ↓ # NOTE: adapter_returned event emit DRIVER'DA DEĞİL; executor içinde
  ↓ # materialization'dan ÖNCE emit ediliyor (executor.py:429).
  ↓ # v3 iter-2 B3 absorb: executor invariant korunur; adapter_returned
  ↓ # payload DOKUNULMAZ. capability_output_refs yalnız step_record'da.
[driver returns to _main_loop]
```

**Fail-closed anchors**:
- Capability artifact write fail → `_StepFailed(category="output_parse_failed", code="CAPABILITY_ARTIFACT_WRITE_FAILED")`
- Walker fail (upstream `AdapterOutputParseError`) → `_StepFailed(category="output_parse_failed", code="OUTPUT_PARSE_FAILED")`
- Adapter invocation fail (`AdapterInvocationFailedError`) → `_StepFailed(category=timeout|adapter_crash|invocation_failed, code=<reason.upper()>)` — Codex iter-2 semantic pin (§2.3 tablosu)
- Normalize invocation artifact write unchanged (PR-A4b path)

**Fail-open**: mevcut `adapter_returned` evidence emission'ı (executor internal) DOKUNULMAZ; payload değiştirilmez.

## 4. DAG — 5-commit Shipping Structure (Codex-revised)

1. **Commit 1: helper + unit tests** (~120 LOC)
   - `ao_kernel/executor/artifacts.py::write_capability_artifact` helper
   - `tests/test_artifacts_capability.py` (~8 unit test: atomic write, SHA-256, schema-agnostic payload, parent dir create)

2. **Commit 2: driver capability materialization + _LEGAL_CATEGORIES widen + error plumbing** (~250 LOC)
   - `ao_kernel/executor/multi_step_driver.py::_run_adapter_step` delta (capability loop + AdapterOutputParseError translation)
   - `ao_kernel/executor/multi_step_driver.py::_LEGAL_CATEGORIES` + `output_parse_failed`, `invocation_failed`
   - `ao_kernel/defaults/schemas/workflow-run.schema.v1.json` step_record `capability_output_refs` (additive; error.category enum DEĞİŞMEZ — v3 iter-2 tespit)
   - Tests: `tests/test_executor_b6_runtime.py::TestDriverMaterialization` (~6 test: roundtrip, error plumbing, backward compat pre-B6 runs)

3. **Commit 3: commit_message capability + schema + codex-stub + fixture** (~180 LOC)
   - `ao_kernel/defaults/schemas/commit-message.schema.v1.json` (NEW)
   - `agent-adapter-contract.schema.v1.json` + `workflow-definition.schema.v1.json` capability_enum `+commit_message`
   - `ao_kernel/defaults/adapters/codex-stub.manifest.v1.json` output_parse 2. rule
   - `ao_kernel/fixtures/codex_stub.py` envelope delta (object-shape commit_message)
   - Tests: `tests/test_executor_b6_runtime.py::TestCommitMessageCapability` (~3 test)

4. **Commit 4: commit_ai_flow bundled + cross-ref test** (~130 LOC)
   - `ao_kernel/defaults/workflows/commit_ai_flow.v1.json` (full-compliant)
   - `tests/test_executor_b6_runtime.py::TestBundledContractCrossRef` (~2 test: schema-valid, codex-stub capabilities cover)

5. **Commit 5: integration + docs + CHANGELOG** (~175 LOC)
   - Review + commit end-to-end integration tests (~5 test)
   - `docs/BENCHMARK-SUITE.md` update (lower-half shipped + capability_output_refs narrative)
   - `docs/COORDINATION.md` sighted? (gerekirse ADAPTERS.md update — v2'de bağımsız kontrol)
   - `review-findings.schema.v1.json` description update
   - `CHANGELOG.md [Unreleased]` PR-B6 entry

## 5. Acceptance Checklist

### Executor invariant (CRITICAL)

- [ ] `_normalize_invocation_for_artifact()` **DEĞİŞMEZ** — executor schema-agnostic
- [ ] `ExecutionResult` imza **DEĞİŞMEZ** (yeni field yok)
- [ ] `run_step()` capability artifact loop YAPMIYOR (driver-owned)

### Driver-owned materialization

- [ ] `MultiStepDriver._run_adapter_step` `exec_result.invocation_result.extracted_outputs` üstünden loop
- [ ] Her capability için `write_capability_artifact(run_dir, step_id, attempt, capability, payload)` → path
- [ ] `step_record.capability_output_refs = {capability: path, ...}` CAS append ile persist
- [ ] **v4 iter-3 absorb — completion plumbing**: `capability_output_refs` hem `_record_step_completion()` (ilk-attempt) HEM `_update_placeholder_to_completed()` (retry-success) helper'larına explicit parametre olarak taşınır; her iki mutator `step_record["capability_output_refs"] = refs` yazar (empty map absent)
- [ ] **v4 iter-3 absorb — regression test `test_capability_refs_persist_across_retry`**: retry-success senaryosunda map step_record'dan düşmemeli
- [ ] **v3 iter-2 B3 absorb — `adapter_returned` evidence payload DOKUNULMAZ**: executor invariant korunur; capability_output_refs yalnız step_record'da, evidence event'te DEĞİL

### Error plumbing (v3 iter-2 B2+B4 absorb)

- [ ] `_LEGAL_CATEGORIES` runtime set schema `error.category.enum` ile **birebir sync**: `{timeout, invocation_failed, output_parse_failed, policy_denied, budget_exhausted, adapter_crash, approval_denied, ci_failed, apply_conflict, other}` — 10 value
- [ ] `adapter_error` runtime'dan **kaldırıldı** (schema'da yoktu; narrative drift fix)
- [ ] **Parity test ZORUNLU** — `test_error_category_parity`: `_LEGAL_CATEGORIES == set(schema.error.category.enum)`
- [ ] `workflow-run.schema.v1.json::error.category.enum` DEĞİŞMEZ (schema zaten 10 value taşıyor)
- [ ] Artifact write failure → `_StepFailed(category="output_parse_failed", code="CAPABILITY_ARTIFACT_WRITE_FAILED")` translation
- [ ] `AdapterOutputParseError` from walker → `_StepFailed(category="output_parse_failed", code="OUTPUT_PARSE_FAILED")`
- [ ] **`AdapterInvocationFailedError` catch + `_StepFailed` translation** (v3 iter-2 B2):
  - `reason in ("timeout", "http_timeout")` → `category="timeout"`
  - `reason == "subprocess_crash"` → `category="adapter_crash"`
  - else → `category="invocation_failed"`
- [ ] Existing `_handle_step_failure()` emits `step_failed` + CAS step_record.state="failed" (PR-A4b path unchanged)

### Commit AI (v2 B1 absorb)

- [ ] `commit-message.schema.v1.json` schema-valid + object-shape (schema_version + subject required)
- [ ] `commit_ai_flow.v1.json` full schema compliance: `default_policy_refs`, `created_at` present; step `on_failure` **string enum** (`"transition_to_failed"`, v3 iter-2 B1 absorb) — obje DEĞİL
- [ ] codex-stub fixture emits `commit_message` as OBJECT (not string)
- [ ] codex-stub manifest output_parse 2 rules (review_findings + commit_message)
- [ ] Walker accepts commit_message payload (Mapping check passes)
- [ ] Adapter capability enum `+commit_message` in 2 schemas (agent-adapter-contract + workflow-definition). Not: bu workflow-run error.category enum'uyla karıştırılmasın — o ikincisi v3 iter-2 tespitiyle DEĞİŞMEZ.

### Naming (Codex tercih)

- [ ] Field name `capability_output_refs` (not `extracted_output_refs`)
- [ ] Pattern `^[a-z][a-z0-9_]{0,63}$` for capability keys

### Strategy B explicit rewrite (v2 B3 absorb)

- [ ] **`step_record.output_ref` CNS-034 iter-2 clarification**: adapter path'te **empty-stays-empty** (pre-B6 davranışı korunur — executor `write_artifact()` çağırıyor ama `ExecutionResult`'a thread etmiyor, driver persist etmez). B6 bu davranışı DEĞİŞTİRMEZ. Adapter-path `output_ref` persistence B6 scope DIŞI; gerçek ihtiyaç için dedicated follow-up + `ExecutionResult` widen gerek.
- [ ] `step_record.capability_output_refs` **B6-guaranteed** surface per-capability artifact'lar için
- [ ] Per-capability artifact'lar `step_record.capability_output_refs[capability]` üstünden (B6-guaranteed)
- [ ] BENCHMARK-SUITE.md narrative update ile B0 contract rewrite'ı explicit
- [ ] review-findings.schema.v1.json description update (artifact location clarify)

### Review AI roundtrip

- [ ] MultiStepDriver run + codex-stub invoke → `review_findings` capability artifact disk'te
- [ ] SHA-256 match + schema validate
- [ ] step_record.capability_output_refs["review_findings"] = run-relative path

### Commit AI roundtrip

- [ ] Aynı, commit_message için
- [ ] Object-shape payload (walker Mapping check passes)

### Backward compat

- [ ] output_parse-less adapter (gh-cli-pr) → extracted_outputs empty, step_record.capability_output_refs absent veya `{}`
- [ ] pre-B6 run kaydı (capability_output_refs field olmadan) replay-uyumlu
- [ ] Pre-B6 fixture (string commit_message placeholder) walker'da empty döndürür (regression not — B6 revize fixture object-shape)

### PR-A4b regression

- [ ] `test_executor_integration.py` green (retry_once step_record append pattern korunur)
- [ ] `_run_adapter_step` imza değişimi PolicyViolationError + ClaimStaleFencingError translation path'lerini bozmaz

### B1 regression

- [ ] Fencing kwargs'lı run yeşil; step_failed flow korunur

### PR-A5 evidence manifest

- [ ] `generate_manifest` scan'i yeni capability artifact'ları `artifacts/**/*.json` glob'ıyla kapsar (otomatik, kod delta yok)
- [ ] Capability artifact'larının SHA-256 manifest'te deterministic

### Schema deltas regression

- [ ] Pre-B6 workflow-run kayıtları `capability_output_refs` olmadan parse edilir (additive field)
- [ ] Pre-B6 workflow-run kayıtları mevcut error.category enum değerleriyle parse edilir (additive widen)

## 6. Risk Register (v2)

| Risk | Seviye | Mitigation |
|---|---|---|
| Driver error-category plumbing bugün acceptance'ı taşıyamıyor (v2 absorb) | **Orta (Çözüldü)** | `_LEGAL_CATEGORIES` widen + explicit `_StepFailed` translation |
| Strategy B B0 contract/docs drift — "output_ref = review_findings artifact" narrative artık yanlış | **Orta (v2 absorb)** | BENCHMARK-SUITE.md + review-findings.schema.v1.json narrative güncellemesi commit 5'te pin'lendi |
| Commit-message payload shape + çift manifest drift (bundled + test fixture manifesti senkron tutulmazsa cross-ref sessizce ayrışır) | **Orta** | commit 3'te aynı commit'te her iki manifest + fixture sync; cross-ref test commit 4'te guard |
| Walker empty döndürür fixture string placeholder ise | **Yüksek → Düşük (v2 absorb)** | Fixture object-shape commit 3'te pin'lendi; schema-valid |
| `_normalize_invocation_for_artifact` imza değişimi PR-A4b test'leri kırar | **Düşük (v2 invariant)** | İmza DEĞİŞMEZ (v2 invariant); executor silent korunur |
| Per-capability artifact file explosion (manifest scan maliyeti) | **Düşük** | Tipik case 1-2 capability per step; PR-A5 glob zaten `**/*.json` tarıyor |
| Schema widening backward compat regression | **Düşük** | Field optional + enum additive; mevcut `additionalProperties: false` respected |
| Commit AI "operation vs capability" yanlış modelleme | **Orta → Low (v2 absorb)** | Adapter + capability + output_parse yaklaşımı Codex iter-1'de onaylı; alternatifler rejekte |
| B7 scope creep (benchmark B6'ya sızma) | **Orta** | Codex advisory'a sadık; acceptance'ta governed_review deferred |
| Fail-closed chain B1 fencing'e karışır | **Düşük** | Fencing entry run_step başında; walker fail step_failed emit sonrası |

## 7. Codex iter-1 Absorb Summary

| CNS-033 iter-1 finding | v2 absorption | Plan section |
|---|---|---|
| B1 (Yüksek) Commit AI walker ihlali + commit_ai_flow schema eksik | Object-shape payload pin + full schema compliance | §2.4, §2.5, §2.7 |
| B2 (Yüksek) Driver error plumbing eksik | `_LEGAL_CATEGORIES` widen + explicit `_StepFailed` translation | §2.2, §2.3, §5 |
| B3 (Orta) Strategy B driver-owned (executor silent pin) | Executor invariant korunur; materialization driver'da | §2.2, §5 Critical |
| B4 (Düşük) Header SHA stale | 59ae712 güncel | (header) |
| Naming: `capability_output_refs` | Absorbed | §5, §2.3 |
| `docs/WRITE-LITE-FLOWS.md` yaratma | Absorbed (yaratılmayacak) | §2.8 |
| DAG split (5 commit) | C1 helper → C2 driver wiring + error plumbing → C3 commit_message → C4 commit_ai_flow → C5 integration + docs | §4 |

## 8. Audit Trail

### CNS iterations

| Iter | Date | Verdict | Absorbed |
|---|---|---|---|
| v1 (Plan subagent draft) | 2026-04-17 | N/A | Scope thin advisory (CNS-030) |
| v1 → iter-1 | 2026-04-17 | REVISE | CNS-033 iter-1: walker kontratı, driver error plumbing, executor invariant, naming, SHA refresh |
| v2 → iter-2 | 2026-04-17 | PARTIAL | CNS-033 iter-2: on_failure schema, AdapterInvocationFailedError translation, adapter_returned invariant çakışması, `_LEGAL_CATEGORIES` parity drift |
| v3 → iter-3 | 2026-04-17 | PARTIAL | CNS-033 iter-3: capability_output_refs completion plumbing (2 helper'a explicit taşıma), stale widen dili temizliği |
| v4 → iter-4 | TBD | TBD | v4 submit (same thread 019d9c27) — AGREE bekleniyor |

### Plan revision history

| Version | Date | Change |
|---|---|---|
| v1 | 2026-04-17 | Plan subagent-generated draft; thin scope; ~800 LOC target |
| v2 | 2026-04-17 | CNS-033 iter-1 absorb: driver-owned materialization (executor silent invariant), commit_message object-shape, `_LEGAL_CATEGORIES` widen, full commit_ai_flow schema compliance, `capability_output_refs` naming, Strategy B contract rewrite narrative; ~855 LOC |
| v3 | 2026-04-17 | CNS-033 iter-2 absorb: `on_failure` schema string enum (obje yerine), `AdapterInvocationFailedError` catch + 3-case translation, `adapter_returned` payload acceptance kaldırıldı (executor invariant korunur), `_LEGAL_CATEGORIES` schema ile birebir parity (`adapter_error` kaldır; 3 missing ekle), parity test zorunlu; delta ~80 LOC; ~935 LOC toplam |
| v4 | 2026-04-17 | CNS-033 iter-3 absorb: `capability_output_refs` completion plumbing — `_record_step_completion` + `_update_placeholder_to_completed` helper imzaları explicit parametre ile widen; retry-success path guard test (`test_capability_refs_persist_across_retry`); stale "schema widen" dili 3 noktada temizlendi; delta ~30 LOC (çoğu test + docstring); ~965 LOC toplam |

## 9. Remaining Questions for Codex iter-2

Plan v2 Codex iter-1'in tüm kritik bulgularını absorbe etti. Iter-2'de netleştirilecek kalan konular:

1. **`_LEGAL_CATEGORIES` widen Option A seçildi**: `output_parse_failed` + `invocation_failed` eklendi. `invocation_failed` benim değil Codex önerisiydi — `adapter_error` zaten var; bu iki kategori birbirine yakın mı, yoksa `invocation_failed` daha geniş bir üst-kategori mi? Eğer üst-kategori rolü oynayacaksa net semantic pin (örn: `invocation_failed` = adapter invoke öncesi/sonrası envelope hatası; `adapter_error` = adapter içi sonuç hatası) gerekli.

2. **Schema widening sırası**: `error.category.enum` widen WORKFLOW-run schema'da; `_LEGAL_CATEGORIES` runtime set'i Python'da. Bu iki source-of-truth'u tek bir test ile senkronize etmek gerekir mi (örn: test'te `_LEGAL_CATEGORIES == set(schema.error.category.enum)`)? Drift guard.

3. **BENCHMARK-SUITE.md narrative rewrite**: "review_findings lower-half" anlatımı güncellenirken, "step_record.output_ref → review_findings artifact" cümlesi tamamen kaldırılıyor mu, yoksa "deprecated, see capability_output_refs" dip notu eklenir mi?

## 10. Resolved Positions (v2 lock)

Impl başlarken aşağıdakiler kararlaştı:

1. Executor `_normalize_invocation_for_artifact()` + `ExecutionResult` DEĞİŞMEZ (invariant)
2. Capability artifact materialization DRIVER-OWNED (`MultiStepDriver._run_adapter_step`)
3. Commit AI = adapter + `commit_message` capability + typed artifact (`commit-message.schema.v1.json`)
4. Commit message payload OBJECT-shape (walker Mapping check)
5. `_LEGAL_CATEGORIES` runtime set schema `error.category.enum` ile birebir parity sync (`adapter_error` kaldır; `invocation_failed`/`output_parse_failed`/`adapter_crash` ekle); schema DEĞİŞMEZ (zaten 10 value)
6. Field name `capability_output_refs` (walker-implementation-detail sızmasın)
7. Strategy B explicit contract rewrite: BENCHMARK-SUITE + review-findings narrative update
8. Yeni docs file YOK (`WRITE-LITE-FLOWS.md` yaratılmaz)
9. 5-commit DAG split (Codex-revised)
10. B7 scope dışı (benchmark runner, scoring, cost seed)

---

**Next step**: kullanıcı onayı → Codex MCP thread `019d9c27` aynı thread üzerinden `codex-reply` ile iter-2 submit. Beklenen verdict: AGREE / ready_for_impl=true (yüksek bulgular tam absorbe; executor invariant pin'lendi; full schema compliance; DAG Codex-revised).
