# Benchmark Suite — Governed Review + Governed Bugfix

**Status:** FAZ-B PR-B0 contract pin (docs skeleton). Runtime implementation: PR-B6 (review AI workflow + review_ai_flow runtime) + PR-B7 (benchmark suite runner + scenarios).

## 1. Overview

The benchmark suite exercises two governed end-to-end flows and scores them objectively. The goal is not raw model performance — it is to detect policy regressions, contract drift, and replay non-determinism in the ao-kernel runtime itself.

Two scenarios ship:

| Scenario | Workflow | Capability matrix | Runtime PR |
|---|---|---|---|
| `governed_bugfix` | [`bug_fix_flow.v1.json`](../ao_kernel/defaults/workflows/bug_fix_flow.v1.json) (PR-A2 existing) | `read_repo` + `write_diff` + `run_tests` | PR-A (baseline shipped) |
| `governed_review` | `review_ai_flow.v1.json` (PR-B0 contract pin, PR-B6 runtime) | `read_repo` + `review_findings` (NEW) | PR-B6 |

Both run under `tests/benchmarks/` with a shared runner (PR-B7). The `review_ai_flow` workflow definition ships in PR-B0 commit 4 so B0 acceptance tests can validate its schema compliance; step-level runtime (adapter dispatch, artifact materialisation) is PR-B6 scope.

## 2. Typed Artifact Contract (`governed_review`)

`governed_review` requires objective scoring. Rather than string-comparing natural-language output, the benchmark consumes a typed artifact: `review-findings.schema.v1.json`.

### 2.1 Artifact Shape

```json
{
  "schema_version": "1",
  "findings": [
    {
      "file": "ao_kernel/executor/adapter_invoker.py",
      "line": 497,
      "severity": "warning",
      "message": "JSONPath subset check does not distinguish missing path from null value.",
      "suggestion": "Raise AdapterOutputParseError with missing-path sentinel; see PR-B0 edge case contracts."
    }
  ],
  "summary": "Reviewed 3 files; found 1 warning; suggested 1 change.",
  "score": 0.85
}
```

Severity enum is closed: `error | warning | info | note` (4 values). `critical` was considered and rejected in [CNS-20260416-028v2 iter-2 W7](../.ao/consultations/CNS-20260416-028v2.consensus.md) — adding a value that does not trigger a distinct policy/gate behaviour only inflates taxonomy.

`score` is optional, real in `[0.0, 1.0]`, caller-defined semantics (e.g., reviewer self-confidence).

### 2.2 Transport

Per [CNS-20260416-028v2 B4'''' resolution](../.ao/consultations/CNS-20260416-028v2.consensus.md), the artifact travels:

```
adapter envelope.review_findings        # free-form field in open envelope body
         ↓
adapter_invoker._invocation_from_envelope walks output_parse rules    [B0: shipped]
         ↓ (json_path extract → schema_ref validate)
InvocationResult.extracted_outputs["review_findings"] = {...}          [B0: shipped]
         ↓
MultiStepDriver._run_adapter_step reads extracted_outputs               [B6: shipped]
         ↓
artifacts.write_capability_artifact() per capability                    [B6: shipped]
         ↓
step_record.capability_output_refs = {capability: ref}                  [B6: shipped]
```

**Stage note (PR-B6 shipped 2026-04-17).** B0 shipped the **upper half** (rule walker, typed validation, `InvocationResult.extracted_outputs` population) covered by `tests/test_executor_adapter_invoker.py::TestOutputParseExtraction`. PR-B6 ships the **lower half** — but **driver-owned** rather than executor-owned:

- `MultiStepDriver._run_adapter_step` iterates `invocation_result.extracted_outputs` (after `exec_result.step_state == "completed"`).
- For each `(capability, payload)`, calls `artifacts.write_capability_artifact(run_dir, step_id, attempt, capability, payload)`.
- Collected refs persist as `step_record.capability_output_refs: map<capability, run-relative path>` (additive schema widen; pre-B6 records parse cleanly without the field).
- Executor stays **schema-agnostic** — `_normalize_invocation_for_artifact()` and `ExecutionResult` are unchanged.
- **`step_record.capability_output_refs` is the B6-guaranteed surface** for per-capability typed artifacts (populated whenever the walker extracted non-empty payloads).
- **`step_record.output_ref` is a legacy / non-guaranteed surface** for the driver-managed adapter path. Pre-B6 the executor wrote the normalized invocation artifact via `write_artifact()` but did NOT thread the resulting `output_ref` through `ExecutionResult` — driver completion helpers see an absent field and persist nothing. B6 preserves this pre-existing behavior (empty stays empty on the adapter path). If a future PR (FAZ-C or dedicated follow-up) wants `output_ref` populated for adapter steps, `ExecutionResult` must gain an `output_ref` field — that is NOT B6 scope.
- Artifact write failure fails-closed: `_StepFailed(category="output_parse_failed")` → standard PR-A4b step_failed handler.

Two hard invariants (enforced by B0 code, not just pinned by docs):

- **Adapter contract `output_envelope` is NOT touched.** The envelope stays a closed shape; the capability payload lives in a free-form field and schema validation happens after extraction, not on the envelope itself.
- **Extraction is transport-layer, not orchestrator-layer.** `adapter_invoker` owns the rule walker; `Executor` is schema-agnostic and will just forward the artifact it receives once B6 wires the lower half.

Contract surface for capability-aware extraction is the NEW `output_parse` rule on the adapter manifest (§3).

## 3. Adapter `output_parse` Rule (NEW Contract Surface)

`output_parse` is a NEW top-level contract surface on `agent-adapter-contract.schema.v1.json`. It is NOT an extension of the existing `response_parse` field — `response_parse` handles HTTP transport parsing (body → envelope); `output_parse` handles capability-specific typed payload extraction (envelope → schema-validated payload). Two separate contract layers that happen to share vocabulary.

### 3.1 Rule Shape

```jsonc
{
  "output_parse": {
    "rules": [
      {
        "json_path": "$.review_findings",
        "capability": "review_findings",
        "schema_ref": "review-findings.schema.v1.json"
      }
    ]
  }
}
```

- **`json_path`** — mandatory. Uses the PR-A3 JSONPath subset (`$.key(.key)*`, no indices, no wildcards). Points into the adapter envelope body.
- **`capability`** — optional. If present, must be one of `capabilities[]`. The extractor keys results by capability name in `InvocationResult.extracted_outputs`.
- **`schema_ref`** — optional. If present, the extracted payload is validated against the named schema (bundled path first, workspace override second). Validation failure raises `AdapterOutputParseError`.

Adapters that do not declare `output_parse` are unaffected; the field is net-new and optional.

### 3.2 Edge Case Contracts (B0 pins for B6 runtime)

| Edge case | Contract | Error surface |
|---|---|---|
| Multiple rules target the same `capability` | Invalid manifest, fail-closed at manifest load-time | `AdapterManifestCorruptedError` |
| `schema_ref` resolves to no schema (not bundled, not in workspace override) | Fail-closed; preferred at load-time, worst case at invocation | `AdapterManifestCorruptedError` (load-time) or `AdapterOutputParseError` → workflow `error.category=output_parse_failed` (invocation) |
| `json_path` resolves but payload is JSON `null` | Schema decides whether the value itself is rejected. Separately, the rule walker keys results into `InvocationResult.extracted_outputs` **only when the extracted value is a `Mapping`**; a `null` payload that the schema accepts therefore passes validation and is NOT stored (extracted_outputs stays empty for that capability), rather than being written as `None`. Rationale: downstream `artifacts.write_artifact()` expects dict-shaped JSON payloads; a keyed `None` would be indistinguishable from "capability not extracted" for readers. Adapters that need to communicate "reviewed with no findings" should return a valid `review-findings` object with `findings: []`, not a null payload. | `AdapterOutputParseError` only if `schema_ref` rejects `null`; silent non-storage otherwise |
| `json_path` does not resolve (key absent in envelope) | Fail-closed — `AdapterOutputParseError` → `error.category=output_parse_failed` | Same as schema failure |
| Envelope contains a capability payload field but the manifest has no `output_parse` rule for it | Silently ignored — extraction is opt-in | (none) |

Rationale for silent-ignore on unregistered payloads: extraction must be a positive, opt-in signal from the manifest. An adapter returning extra fields an operator has not wired up should not produce warning spam or surprise failures.

## 4. Runner

```bash
pytest tests/benchmarks/ --benchmark-mode=fast
pytest tests/benchmarks/ --benchmark-mode=full
```

- `fast` — mock adapters return canned envelopes; deterministic, fast, runs in CI. Default.
- `full` — invokes real adapters (Claude Code CLI, Codex stub, or others configured at the workspace). Expected to be ops-only; not a CI gate.

Both modes exercise the full `MultiStepDriver` + `Executor.run_step` + `adapter_invoker` chain — the mock in `fast` mode is at the subprocess boundary, not at the orchestrator boundary, so extraction and artifact write are real.

## 5. Success Criteria

### 5.1 `governed_bugfix`

- `workflow_completed` evidence event fires.
- All adapter invocations return envelopes with `status: "ok"`.
- CI gate passes (PR-A4a `run_pytest` + `run_ruff` return `pass`).
- `cost_usd` axis stays within the seeded budget.

### 5.2 `governed_review`

- `workflow_completed` evidence event fires.
- Adapter returns an envelope with `status: "ok"` AND an `output_parse`-extractable payload that validates against `review-findings.schema.v1.json`.
- `step_record.capability_output_refs["review_findings"]` points at a non-empty, schema-valid `review-findings` artifact (PR-B6 B6-guaranteed surface). `output_ref` is legacy/non-guaranteed on the adapter path and may be absent — benchmarks MUST read from `capability_output_refs`.
- `cost_usd` axis stays within the seeded budget.
- **Objective scoring:** the benchmark harness inspects `findings.severity` distribution and optional `score`; caller-supplied threshold decides pass/fail.

## 6. Adapter Capability Matrix

| Capability | `governed_bugfix` | `governed_review` | Source |
|---|---|---|---|
| `read_repo` | required | required | existing |
| `write_diff` | required | — | existing |
| `run_tests` | required | — | existing |
| `review_findings` | — | required | NEW (PR-B0 enum delta) |

No new capability is required for `governed_bugfix`; `review_findings` is the single new capability introduced in PR-B0 (reflected in both `agent-adapter-contract.schema::$defs/capability_enum` and `workflow-definition.schema::$defs/capability_enum`).

## 7. Cross-References

- Schemas: [`review-findings.schema.v1.json`](../ao_kernel/defaults/schemas/review-findings.schema.v1.json), [`agent-adapter-contract.schema.v1.json`](../ao_kernel/defaults/schemas/agent-adapter-contract.schema.v1.json) (capability_enum + output_parse), [`workflow-definition.schema.v1.json`](../ao_kernel/defaults/schemas/workflow-definition.schema.v1.json) (capability_enum parity)
- Bundled workflow: `ao_kernel/defaults/workflows/review_ai_flow.v1.json` (PR-B0 commit 4 — contract pin only)
- Transport layer: [ADAPTERS.md](ADAPTERS.md) (PR-A existing), [EVIDENCE-TIMELINE.md](EVIDENCE-TIMELINE.md)
- Adversarial review: [CNS-20260416-028v2 consensus](../.ao/consultations/CNS-20260416-028v2.consensus.md) §B3 (typed artifact contract), §B3''' (extraction via output_parse), §B4'''' (layer pin)

## 8. Document Status

Skeleton in PR-B0 commit 1. Concrete runner example, scoring-threshold case study, and adapter stub recipes for `governed_review` land in PR-B0 commit 5 (docs final pass) + PR-B6/B7 runtime.
