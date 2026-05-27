# AO-MA-5 — Integrator Policy (operator-runnable assembly plan; no remote write)

**Status:** plan-time iter-4 AGREE absorbed (Codex thread `019e6850-3579-7261-ae2a-c96d393157cc`; iter-1 REVISE → iter-2 PARTIAL → iter-3 PARTIAL → iter-4 AGREE). Ready for schema-extension PR.
**Branch:** `codex/ao-ma-5-integrator-policy`
**Decision artifact:** `ao_ma_5_integrator_policy_local_emit_no_remote_write`
**Parent:** AO-MA-1 §8 phased plan slice AO-MA-5
**Support impact:** none

## Purpose

AO-MA-1 §8 plan'da AO-MA-5 = "Integrator policy: accepted/rejected worker outputs, conflict reports, single PR assembly." AO-MA-4 (PR #648, merged `fbc55b07`) parallel worktree runner artefact üretiyor. AO-MA-5 onları okur, **policy decision** alır (accept / reject / not_integratable), **integration_report.v1.json** emit eder, ve **operator-runnable command plan** (no remote write) sunar.

**Codex iter-1 absorb (REVISE → kabul edilmiş tasarım daraltması):**

AO-MA-5 v1 yalnız **integration report + accept/reject + conflict/evidence policy**. **Remote PR assembly OUT of scope**:
- AO-MA-5 v1 `git push` YAPMAZ
- AO-MA-5 v1 `gh pr create` YAPMAZ
- AO-MA-5 v1 yeni "integrator branch" oluşturup local merge dahi yapmaz (v1.1+ scope candidate)
- AO-MA-5 v1 yalnız: read artifacts → policy decide → emit integration_report.v1.json → print operator-runnable command plan

**Kritik invariantlar:**

- **No agent execution**, **no LLM call** (AO-MA-5 deterministic policy)
- **No GitHub write** (no `git push`, no `gh pr create`, no `gh api PUT`)
- **No branch protection mutation**
- **No release authority** (`integration_report.release_authority` schema const = `"ao-release-gate+github-ruleset"` — AO-MA-5 NOT release authority)
- Worker accept gate strict: worker_result + review_verdict (AGREE) + verification_report (passed) **üçü birden zorunlu** (Codex iter-1 Crit-D)
- Eksik review/verify → worker `not_integratable` (Codex iter-1 Crit-E pending), NOT rejected
- Conflict (same file in two accepted workers) → conflict report + escalate operator (Codex iter-1 CF3)
- `guard_flags` always literal `false` (support_widening / production_platform_claim / live_adapter_execution)

## Codex istişaresi

Thread `019e6850-3579-7261-ae2a-c96d393157cc` iter-1 REVISE absorbed (kabul edilen kararlar):

| # | Konu | Codex önerisi | Absorbed karar |
|---|---|---|---|
| 1 | Slice ordering | C (placeholder-but-safe) | ✅ AO-MA-5 v1 skeleton; review/verify ref'leri optional schema field ama semantik olarak missing=not_integratable; AO-MA-6/7 land ettiğinde wired-up |
| 2 | Worker producer | W3 (yeni slice AO-MA-4.5) | ✅ AO-MA-4.5 "Worker invocation + result emit" yeni slice; AO-MA-5'in dependency; bu plan AO-MA-5'ten ÖNCE wired olmasa bile AO-MA-5 v1 worker_result.v1 missing'i fail-closed handle eder |
| 3 | PR assembly | PR-C (rapor + operator command plan, no push) | ✅ AO-MA-5 v1 sadece local emit + operator-runnable command plan; remote write strictly out of scope |
| 4 | Accept/reject | Crit-D + Crit-E | ✅ Accept: worker_result valid + review AGREE + verify pass (üçü birden); Missing evidence: not_integratable (pending) |
| 5 | Conflict | CF3 (operator escalate) | ✅ Last-writer-wins ASLA; conflict varsa ilgili worker'ları accepted yapma + operator escalate |
| 6 | CLI surface | `integrate --manifest <path>` + extras | ✅ Subcommand `integrate`; runner_report derive from manifest dir; optional explicit refs |
| 7 | Module layout | `integrator.py` + `integration_report_writer.py` | ✅ AO-MA-4 worker_runner pattern follow |

### 5 must_close_before_impl — absorb kararları

**1. integration_report pending/reason representation.** AO-MA-2 schema (`ao-ma-integration-report.v1`) `accepted_worker_results` + `rejected_worker_results` + `conflicts[]` + `release_authority` + `guard_flags` taşıyor; "pending" veya "not_integratable" için açık alan YOK. Options:

- **5a. Schema extension PR (governance migration):** AO-MA-2 schema'sına `pending_worker_results: path_list` + `worker_decisions[]` (worker-level decision rationale array) ekle. Ayrı governance PR. AO-MA-5 v1 bunu DEPEND eder.
- **5b. Encode within `conflicts[]`:** Mevcut `conflicts[]` struct'unu genişletmek (her conflict'in `kind: overlap | not_integratable | evidence_missing` olur). Schema permissive olduğu için backward-compat.
- **5c. Hybrid:** AO-MA-5 v1 `rejected_worker_results`'a hem reddedilenleri hem pending'leri koy + ayrı `conflicts[]` entry'sinde reason encode. Audit zayıflar.

**Karar (iter-2 önerisi): 5a (schema extension governance PR önce).** AO-MA-5 v1 PR'ı schema extension PR'ına depend eder. Sıralı zincir: schema extension PR → AO-MA-5 v1 PR. Audit trail temiz, gelecek AO-MA-6/7 de bu extension'ı tüketir.

**Schema extension önerisi (Codex iter-2 absorb — must_close #3 expand shape + reason_code enum):**

```json
"pending_worker_results": {
  "$ref": "#/$defs/path_list",
  "description": "Worker results valid ama review_verdict.v1 ya da verification_report.v1 missing/inconclusive olduğu için integrate edilmeyenler. Schema-level fail-closed; operator karar verir veya AO-MA-6/7 land sonrası re-run."
},
"worker_decisions": {
  "type": "array",
  "items": {
    "type": "object",
    "additionalProperties": false,
    "required": ["task_id", "worker_result_ref", "decision", "reason_code"],
    "properties": {
      "task_id": {
        "type": "string",
        "pattern": "^[a-z0-9][a-z0-9._-]{1,80}$"
      },
      "worker_result_ref": {
        "description": "Path to the worker_result.v1.json file consulted, or null when worker_result missing (Codex iter-3 absorb must_close #2: null distinguishes from a real file named 'missing').",
        "oneOf": [
          {"$ref": "#/$defs/path"},
          {"type": "null"}
        ]
      },
      "decision": {
        "type": "string",
        "enum": ["accept", "reject", "not_integratable"]
      },
      "reason_code": {
        "type": "string",
        "enum": [
          "accepted_full_evidence",
          "missing_worker_result",
          "missing_review_verdict",
          "missing_verification_report",
          "review_revise",
          "review_block",
          "verification_failed",
          "actual_write_set_overlap",
          "guard_flag_violation",
          "schema_invalid"
        ]
      },
      "evidence_refs": {
        "type": "array",
        "items": {"type": "string"},
        "description": "Optional: paths to review_verdict.v1 + verification_report.v1 + worker_result.v1 consulted (for audit)."
      }
    }
  }
},
"assembly_plan": {
  "type": "array",
  "description": "Operator-runnable command plan (data, not shell strings). Optional artifact field so audit trail captures what the integrator suggested.",
  "items": {
    "type": "object",
    "additionalProperties": false,
    "required": ["argv", "operator_only", "side_effect"],
    "properties": {
      "argv": {
        "type": "array",
        "items": {"type": "string"},
        "minItems": 1,
        "description": "argv-form command (no shell interpolation). Branch/path strings must come from already-validated AO-MA-2 artifacts."
      },
      "cwd": {"type": "string"},
      "operator_only": {"type": "boolean", "const": true},
      "side_effect": {
        "type": "string",
        "enum": ["local_git_merge", "remote_pr_create", "local_branch_create", "local_worktree_remove"]
      },
      "requires_clean_worktree": {"type": "boolean"},
      "note": {"type": "string"}
    }
  }
}
```

**Reason code semantics (Codex iter-2 enum, iter-3 corrections):**
- `accepted_full_evidence` — worker_result valid + review AGREE + verify pass (predicate below)
- `missing_worker_result` — expected_worker_result_path empty / not found
- `missing_review_verdict` — no review_verdict.v1 for this task_id
- `missing_verification_report` — no verification_report.v1 for this task_id
- `review_revise` — `review_verdict.verdict == "REVISE"` (worker needs another iter)
- `review_block` — `review_verdict.verdict == "BLOCK"` (per AO-MA-2 schema enum: AGREE | REVISE | BLOCK; "RED" was incorrect in iter-2 draft)
- `verification_failed` — verification_report pass predicate fails (see below)
- `actual_write_set_overlap` — accepted worker's actual_changed_files overlaps another accepted worker
- `guard_flag_violation` — worker_result.guard_flags has any non-False value
- `schema_invalid` — worker_result.v1.json fails Draft202012Validator

**Verification pass predicate (Codex iter-3 absorb — must_close #1: ground in actual AO-MA-2 schema):**

`ao-ma-verification-report.v1` schema'da top-level `passed` alanı YOK. Pass predicate concrete:

```python
def verification_passed(report: dict) -> bool:
    return (
        report.get("failed_checks", []) == []
        and report.get("scope_check", {}).get("passed") is True
        and report.get("secret_scan", {}).get("passed") is True
        and all(cmd.get("outcome") != "fail" for cmd in report.get("commands", []))
        and report.get("guard_flags", {}).get("support_widening") is False
        and report.get("guard_flags", {}).get("production_platform_claim") is False
        and report.get("guard_flags", {}).get("live_adapter_execution") is False
    )
```

**`commands[].outcome == "skipped" policy`:** skipped commands non-failing but not sufficient. Pass requires NO fail outcomes AND failed_checks empty. Skipped allowed only if the other invariants hold.

**Test pin:** `test_integrate_verification_pass_predicate_uses_existing_schema_fields` — fixture'da skipped+pass mix, skipped+fail mix, fail-only, all-pass, **skipped-only**; predicate doğrulaması. **`skipped`-only policy (Codex iter-4 nice-to-have absorb):** skipped-only commands list → predicate **True** if all other invariants (failed_checks empty, scope_check.passed, secret_scan.passed, guard_flags False) hold. Rationale: skipped commands are non-failing; sufficiency comes from the other gates, not from commands list length. Test fixture pins both directions explicitly.

**2. Worker result producer slice naming.** **AO-MA-4.5** (Codex önerisi). Plan: "AO-MA-4.5: Worker invocation + result emit". AO-MA-5 v1 önce land edebilir (bu sıra MIT) AMA worker_result.v1 input'u olmadan integration_report her zaman empty/not_integratable olur. AO-MA-5 v1 doc bunu açıkça not eder: "downstream of AO-MA-4.5; until that slice lands, integration_report.v1 always shows not_integratable for all workers". Bu pragmatik — AO-MA-5 v1'i AO-MA-4.5 ile sıralı land etmek operator workflow disiplini için OK.

**3. HARD RULE pin (no git push, no gh pr create) — Codex iter-2 absorb: kill `dry_run` symbol entirely.**

- Integrator class signature has **no `dry_run` parameter** (was iter-2 must_close #1: "dry_run" implies wet-mode exists; AO-MA-5 v1 has no wet mode concept at all)
- Integrator class has **no remote-write / local-merge capability** code paths: no `subprocess` import, no `git push` / `gh` / `git merge` / `git worktree add` / `git branch -b` strings, no shell-out helpers
- Integrator is pure data: load artifacts → policy decide → return decision object
- CLI handler maps decision object → exit code + stdout/stderr (no shell-out either)
- Test fixtures (static + behavioural):
  - `test_integrator_module_has_no_subprocess_import` (AST scan)
  - `test_integrator_module_has_no_gh_or_git_push_literals` (text scan: no `gh `, `git push`, `git merge`, `git worktree add`, `git branch -b`, `git checkout -b`)
  - `test_cli_integrate_does_not_call_subprocess_on_policy_path` (CLI handler subprocess monkey-patch reject)
  - `test_integrate_does_not_create_branch_or_worktree` (real git fixture: state unchanged after integrate)
  - `test_operator_plan_is_data_not_executed` (decision.operator_plan is structured data, not shell strings)

**4. AO-MA-5 v1 scope adı.** **"Integration report + accept/reject + conflict/evidence policy (operator-runnable assembly plan; no remote write)"**. Plan doc title + PR title + CLI help text bunu yansıtır.

**5. CLI exit semantics + emit guarantee — Codex iter-2 absorb: tighten the "always emit" claim.**

CLI exit codes:

| Durum | exit code | integration_report emit? |
|---|---|---|
| All workers accepted, no conflict, no not_integratable | 0 | ✅ yes |
| Any worker not_integratable (missing evidence) | 1 (operator needs to act) | ✅ yes |
| Any worker rejected (worker_result invalid / verify failed / review REVISE) | 1 | ✅ yes |
| Any conflict (overlap between accepted workers) | 1 | ✅ yes |
| Manifest envelope invalid / task_graph_id cross-ref fail / runner_report schema invalid | 2 (operator error) | ❌ NO (trust boundary failed; diagnostic stderr only) |
| Integration emit failure (FS write / schema validation on emit) | 3 (runtime error) | ❌ NO (emit failed) |

**Codex iter-2 absorb (iter-3 tightened wording):** Emit guarantee is **conditional** on the trust boundary (manifest envelope + task_graph_id cross-ref + runner_report schema + at least one worker entry decision) being valid. When the trust boundary IS valid, `integration_report.v1.json` is always written — accepted / rejected / not_integratable / conflict outcomes ALL produce a report. When the trust boundary is INVALID (manifest envelope fails, task_graph_id cross-ref fails, runner_report missing/schema-invalid), no report is written — fail-closed instead of emit a misleading report. Exit code 2/3 surfaces operator action via stderr message only.

**`assembly_plan` producer invariant (Codex iter-3 nice-to-have absorb):** schema-level `assembly_plan` is optional (backward-compat), but the AO-MA-5 producer always writes it when the trust boundary is valid. Test pin: `test_integrate_emits_assembly_plan_data` asserts the field is present in every emit.

**API/CLI separation — Codex iter-2 absorb (must_close #5):**

- `Integrator.integrate(...)` returns a `IntegrationDecision` dataclass (decision + report dict + operator plan)
- `Integrator.integrate(...)` **does NOT raise** for not_integratable / rejected / conflict — these are normal decision states
- `Integrator.integrate(...)` raises `IntegratorError` only for true I/O / schema-load failures
- CLI handler (`cmd_orchestration_integrate`) maps `IntegrationDecision` to exit code per the matrix above
- Unit tests can call `Integrator.integrate(...)` directly and assert decision state without subprocess/CLI gymnastics

## Module layout

```
ao_kernel/orchestration/
  integrator.py                  # Integrator class: load → decide → emit (no git, no gh)
  integration_report_writer.py   # emit + schema validate + atomic write
  cli_handlers.py                # extend: cmd_orchestration_integrate

ao_kernel/defaults/schemas/
  ao-ma-integration-report.schema.v1.json  # MODIFIED in schema extension PR (must_close_5a)
                                            # AO-MA-5 v1 PR DEPENDS on schema extension PR
```

## CLI surface

```bash
ao-kernel orchestration integrate \
  --manifest <path>                                # AO-MA-3 manifest.v1.json (required)
  [--runner-report <path>]                         # default: <manifest_dir>/runner_report.v1.json
  [--worker-result <path> ...]                     # default: per worker entry's expected_worker_result_path
  [--review-verdict <path> ...]                    # default: convention-located (<base_dir>/<task_id>/review_verdict.v1.json)
  [--verification-report <path> ...]               # default: convention-located
  [--repo-root <path>]                             # default: cwd
  [--format text|json]                             # default: text
```

CLI exits per §5 exit semantics. `integration_report.v1.json` written to `<manifest_dir>/integration_report.v1.json`.

## Test coverage plan

| Test | Cover |
|---|---|
| `test_integrate_accepts_3_of_3_workers_full_evidence` | Crit-D happy path |
| `test_integrate_not_integratable_when_review_missing` | Crit-E missing evidence (`missing_review_verdict`) |
| `test_integrate_not_integratable_when_verify_missing` | Crit-E (`missing_verification_report`) |
| `test_integrate_not_integratable_when_worker_result_missing` | Crit-E (`missing_worker_result`) |
| `test_integrate_rejects_when_review_revise` | Hard reject (`review_revise`) |
| `test_integrate_rejects_when_review_block` | Hard reject (`review_block`) |
| `test_integrate_rejects_when_verify_failed` | Hard reject (`verification_failed`) |
| `test_integrate_rejects_when_worker_result_guard_flag_violation` | Hard reject (`guard_flag_violation`) |
| `test_integrate_rejects_when_worker_result_schema_invalid` | Hard reject (`schema_invalid`) |
| `test_integrate_conflict_two_accepted_workers_same_file` | CF3 escalate (`actual_write_set_overlap`) |
| `test_integrate_manifest_envelope_validation` | AO-MA-4 pattern (envelope before fields) |
| `test_integrate_runner_report_schema_validation` | trust boundary |
| `test_integrate_pending_workers_emit_in_pending_list` | schema extension wire |
| `test_integrate_emits_assembly_plan_data` | assembly_plan structured (argv list, no shell strings) |
| `test_integrate_exit2_does_not_write_misleading_integration_report` | iter-2 absorb (trust boundary fail → no emit) |
| `test_integrator_module_has_no_subprocess_import` | iter-2 HARD RULE pin (AST static) |
| `test_integrator_module_has_no_gh_or_git_push_literals` | iter-2 HARD RULE pin (text static) |
| `test_cli_integrate_does_not_call_subprocess_on_policy_path` | iter-2 HARD RULE pin (monkey-patch reject) |
| `test_integrate_does_not_create_branch_or_worktree` | iter-2 HARD RULE pin (real git fixture; state unchanged) |
| `test_operator_plan_is_data_not_executed` | iter-2 HARD RULE pin (assembly_plan argv-form not shell-string) |
| `test_integrator_integrate_returns_decision_object_not_raises_for_not_integratable` | iter-2 API/CLI split |
| `test_cli_integrate_exit_codes` | §5 exit semantics matrix |
| `test_integrate_verification_pass_predicate_uses_existing_schema_fields` | iter-3 must_close #1 (predicate concrete) |
| `test_worker_result_ref_is_null_when_missing` | iter-3 must_close #2 (null vs "missing" sentinel) |

Minimum 24 tests. Real git fixture for any worktree-based assertion.

**Static literal scope clarification (Codex iter-3 nice-to-have):** Static `no_subprocess_import` / `no_gh_or_git_push_literals` tests target **only implementation modules** (`ao_kernel/orchestration/integrator.py`, `ao_kernel/orchestration/integration_report_writer.py`, and the `cmd_orchestration_integrate` handler region of `cli_handlers.py`). Schema files, plan docs, test fixtures, and the text renderer for `assembly_plan` may legitimately mention `git`, `gh`, `remote_pr_create` etc. — they're data names, not executable paths.

## Hard stops

- No support widening
- No production_platform_claim
- No live_adapter_execution
- No agent execution (no LLM call)
- No GitHub write (no git push, no gh pr create, no gh api PUT)
- No branch protection mutation
- No workflow file change
- `release_authority` schema const enforces non-release-authority

## Dependencies + risks

**Dependencies:**
- **Schema extension PR (must_close_5a + iter-2 must_close_3) MUST land before AO-MA-5 v1.** Schema-only governance PR. Also includes:
  - AO-MA-1 phased plan amendment: insert "**AO-MA-4.5** | Worker invocation + result emit (LLM-driven scope: write `worker_result.v1`). | code + tests" between AO-MA-4 and AO-MA-5 rows (Codex iter-2 must_close #4 absorb — canonical reflection)
- AO-MA-4.5 Worker invocation slice CAN land in parallel (AO-MA-5 v1 fail-closed handles missing worker_result.v1 via `missing_worker_result` reason_code)
- AO-MA-6 + AO-MA-7 wired-up later; AO-MA-5 v1 gracefully not_integratable until then via `missing_review_verdict` + `missing_verification_report`

**Risks:**
- Schema extension PR governance review extra round-trip
- AO-MA-5 v1 hep `not_integratable` döndürebilir AO-MA-4.5 + AO-MA-6 + AO-MA-7 land etmeden — bu beklenen davranış, plan doc'ta açıkça not edilmeli
- CLI exit-1 semantics CI'da fail görünür; bu intentional (operator action surface)

## Acceptance for AO-MA-5 v1

- ✅ Schema extension PR merged (pending_worker_results + worker_decisions + assembly_plan + AO-MA-1 phased plan amendment for AO-MA-4.5)
- ✅ Integrator class implements load → decide → emit pipeline (pure data; no shell-out)
- ✅ `IntegrationDecision` dataclass: `overall_status`, `report`, `assembly_plan`, `diagnostics`, `has_conflicts`, `has_rejections`, `has_pending` (Codex iter-3 note 6 absorb; `exit_code` computed by CLI layer, NOT in core)
- ✅ CLI subcommand `integrate` lands
- ✅ **24+ tests** pass (incl. HARD RULE pin tests + iter-3 must_close pins)
- ✅ Codex cross-AI review iter-N AGREE
- ✅ ruff + mypy clean
- ✅ no git push / no gh pr create asserted by test + plan doc + code review
- ✅ `assembly_plan` always present in emitted integration_report when trust boundary valid (producer invariant)
