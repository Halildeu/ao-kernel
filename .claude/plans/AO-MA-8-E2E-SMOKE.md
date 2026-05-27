# AO-MA-8 — End-to-end autonomous low-risk smoke (shadow mode; evidence class)

**Status:** plan-time iter-1 REVISE + iter-2 REVISE + iter-3 REVISE + iter-4 REVISE absorb (Codex thread `019e6a30-1f93-7482-bf5d-bc089d974f26`). Iter-5 AGREE pending (double-docstring + tracking hygiene closed).
**Branch:** `codex/ao-ma-8-end-to-end-smoke`
**Decision artifact:** `ao_ma_8_e2e_smoke_evidence`
**Parent:** AO-MA-1 §8 phased plan slice AO-MA-8
**Support impact:** none

## Purpose

AO-MA-1 §8 plan row AO-MA-8 = "End-to-end autonomous low-risk smoke in shadow mode, with no branch-protection change. Class: **evidence**." This slice consumes the AO-MA-3/4/6/7/5 runtime surface that already merged on `main`; it does not extend it.

**Codex iter-1 absorb (kabul edilmiş tasarım):**

1. **Option A (pure pytest)** — NO new CLI subcommand, NO `WorkerRunner --mock-implementer` flag. Shadow evidence slice must not widen the runtime surface.
2. **Mock worker = local test helper / fixture** (Codex iter-1 must_close #1) — worker_result.v1.json fixture written via a small in-file helper (no shared `MockImplementer` class until a second slice needs it).
3. **AO-MA-4.5 surrogate explicit** — pipeline order is `AO-MA-3 → AO-MA-4 → AO-MA-4.5 (mock surrogate worker_result emit) → AO-MA-6 → AO-MA-7 → AO-MA-5`. The AO-MA-1 §8 plan reserves AO-MA-4.5 as the worker_result producer slice; AO-MA-8 names the surrogate explicitly so the chain does not look like a missing step.
4. **Cross-provider HARD RULE preserved** — implementer=`anthropic`, reviewer=`openai`, verifier=`tool` (no-LLM deterministic). No bypass.
5. **Evidence authority = `integration_report.v1.json`** — already schema-backed (ao-ma-integration-report.v1) with `accepted_worker_results` + `rejected_worker_results` + `conflicts` + `assembly_plan` + closed guard flags. Optional `.claude/plans/AO-MA-8-E2E-SMOKE-EVIDENCE.v1.json` is a **receipt**, not authority — test reads it as an invariant.
6. **Shadow mode pin definitions** (Codex iter-1 must_close #4 — replace vague "no PR / no auto-merge" with explicit pins):
   - `tmp_repo_only=true`
   - `synthetic_origin_main=true`
   - `github_write=false`
   - `git_push=false`
   - `gh_pr_create=false`
   - `auto_merge=false`
   - `branch_protection_change=false`
   - `gpp_status_mutation=false`
   - `assembly_plan_executed=false`
   - `support_widening=false`
   - `production_platform_claim=false`
   - `live_adapter_execution=false`

## Pipeline order

```
AO-MA-3   Orchestrator.plan()              → task_graph.v1.json + manifest.v1.json
AO-MA-4   WorkerRunner.spawn()             → runner_report.v1.json + per-task worktree
AO-MA-4.5 mock surrogate (local helper)    → worker_result.v1.json (in worker's worktree dir)
AO-MA-6   Reviewer.review(verdict=AGREE)   → review_verdict.v1.json
AO-MA-7   Verifier.verify(provider=tool)   → verification_report.v1.json
AO-MA-5   Integrator.integrate()           → integration_report.v1.json + assembly_plan[]
```

Each stage assertion:

| Stage | Outcome assertion |
|---|---|
| orchestrator_plan | task_graph + manifest schema-valid; ≥1 task |
| worker_runner_spawn | runner_report status `prepared`; worktree exists; branch matches manifest |
| mock_implementer | worker_result schema-valid; cross-ref with task_graph + manifest; **head_sha = real local commit SHA** (Codex iter-1 nice-to-have #1); **actual_changed_files == `git diff --name-only base_sha..HEAD` exact** (Codex iter-2 must_close #2 — non-empty, declared dosya gerçekten değişti) |
| reviewer_review | review_verdict.v1 schema-valid; verdict AGREE; budget not forced |
| verifier_verify | verification_report.v1 schema-valid; overall_pass=True; failed_checks empty; secret_scan.passed; scope_check.passed; all guard_flags closed |
| integrator_integrate | integration_report.v1 schema-valid; **`IntegrationDecision.overall_status == "all_accepted"`** (Codex iter-2 must_close #1 — enum, NOT "accepted"); `len(report["accepted_worker_results"]) == 1`; `len(report["rejected_worker_results"]) == 0`; `report["conflicts"] == []`; `len(report["assembly_plan"]) >= 1`; all guard_flags closed |

## Mock implementer fixture (M1 pattern, local helper) — non-empty commit (Codex iter-2 must_close #2)

**Pattern:** declared_write_set'teki gerçek bir dosyayı değiştir (e.g. `src/a.py` → ekstra satır), `git add` + `git commit`, sonra `head_sha = git rev-parse HEAD` ve `actual_changed_files = git diff --name-only base_sha..HEAD`. `--allow-empty` YASAK — artifact chain o yolla zayıflar. worker_result.json commit'ten sonra yazılır ki actual_changed_files schema-valid ve gerçeği yansıtsın.

```python
def _emit_mock_worker_result(
    *,
    worktree_dir: Path,
    task_graph_id: str,
    task_id: str,
    declared: list[str],
    base_sha: str,
) -> tuple[Path, str, list[str]]:
    """AO-MA-4.5 surrogate: modify a real file from declared_write_set,
    commit (NO --allow-empty), capture head_sha via rev-parse + actual
    changed file list via ``git diff --name-only base_sha..HEAD``, then
    write a schema-valid worker_result.v1.json into the spawned worktree's
    ``<manifest_dir>/workers/<task_id>/`` directory AFTER the commit.
    Returns ``(worker_result_path, head_sha, actual_changed_files)``.

    No LLM call. No GitHub fetch. Test-harness subprocess (git add/commit/
    rev-parse/diff) allowed per the subprocess boundary in Hard stops.
    """
    payload = {
        "schema_version": "ao-ma-worker-result.v1",
        "task_graph_id": task_graph_id,
        "task_id": task_id,
        "assignment_id": f"{task_graph_id}-{task_id}",
        "worker": {
            "agent_id": f"claude-{task_id}",
            "agent_type": "implementer",
            "provider": "anthropic",          # cross-provider HARD RULE
            "session_id": f"ao-ma-8-smoke-{task_graph_id}",
        },
        "base_ref": "refs/heads/main",
        "base_sha": base_sha,
        "head_ref": f"codex/ao-ma-{task_graph_id}/{task_id}",
        "head_sha": head_sha,                  # REAL local SHA
        "declared_write_set": declared,
        "actual_changed_files": actual_changed,
        "summary": "AO-MA-8 e2e smoke surrogate implementer",
        "tests_run": [{"command": "pytest", "outcome": "pass"}],
        "known_gaps": [],
        "no_secret_attestation": {"secrets_recorded": False},
        "guard_flags": {
            "support_widening": False,
            "production_platform_claim": False,
            "live_adapter_execution": False,
        },
    }
    ...
```

## Evidence receipt (committed; not authority)

`.claude/plans/AO-MA-8-E2E-SMOKE-EVIDENCE.v1.json` — committed alongside the test for audit hygiene. Pure descriptive receipt; **authority remains `integration_report.v1.json`** the test produces at runtime.

```json
{
  "schema_version": "ao-ma-8-e2e-smoke-evidence.v1",
  "artifact_kind": "ao_ma_8_e2e_smoke_evidence",
  "decision": "ao_ma_8_e2e_smoke_ready",
  "support_widening": false,
  "production_platform_claim": false,
  "live_adapter_execution": false,
  "pipeline_order": [
    "orchestrator_plan",
    "worker_runner_spawn",
    "mock_implementer_aoma45_surrogate",
    "reviewer_review",
    "verifier_verify",
    "integrator_integrate"
  ],
  "shadow_mode_pins": {
    "tmp_repo_only": true,
    "synthetic_origin_main": true,
    "github_write": false,
    "git_push": false,
    "gh_pr_create": false,
    "auto_merge": false,
    "branch_protection_change": false,
    "gpp_status_mutation": false,
    "assembly_plan_executed": false,
    "support_widening": false,
    "production_platform_claim": false,
    "live_adapter_execution": false
  },
  "expected_invariants": {
    "decision_overall_status": "all_accepted",
    "report_conflicts_length": 0,
    "report_accepted_worker_results_length": 1,
    "report_rejected_worker_results_length": 0,
    "report_assembly_plan_length_min": 1,
    "guard_flags_closed": true
  },
  "cross_provider_chain": {
    "implementer": "anthropic",
    "reviewer": "openai",
    "verifier": "tool"
  },
  "authority_artifact": "integration_report.v1.json",
  "guard_flags": {
    "support_widening": false,
    "production_platform_claim": false,
    "live_adapter_execution": false
  }
}
```

Codex iter-1 nice-to-have #2 absorb: **the test reads this receipt and asserts the runtime integration_report matches the expected_invariants** (so the receipt cannot drift unnoticed from real behaviour).

## Test plan (~16 assertions)

`tests/test_ao_ma_8_e2e_smoke.py` (new file):

| Test | Cover |
|---|---|
| `test_ao_ma_8_e2e_smoke_pipeline_emits_accepted_integration_report` | Full happy path: 6 stages + `IntegrationDecision.overall_status == "all_accepted"` + report shape (accepted_worker_results=1, rejected_worker_results=0, conflicts=[], assembly_plan≥1) |
| `test_ao_ma_8_e2e_smoke_worker_result_uses_real_local_head_sha` | head_sha matches `git rev-parse HEAD` in worktree (no placeholder) |
| `test_ao_ma_8_e2e_smoke_actual_changed_files_matches_git_diff_exactly` | Codex iter-2 must_close #2: real file commit + `git diff --name-only base_sha..HEAD` exact set-equality with `worker_result.actual_changed_files` |
| `test_ao_ma_8_e2e_smoke_cross_provider_chain_intact` | implementer=anthropic, reviewer=openai, verifier=tool |
| `test_ao_ma_8_e2e_smoke_verifier_overall_pass_no_failed_checks` | verifier.verify().overall_pass=True; failed_checks=[] |
| `test_ao_ma_8_e2e_smoke_reviewer_agree_not_force_blocked` | review_decision.emitted_verdict=AGREE; budget_forced_block=False |
| `test_ao_ma_8_e2e_smoke_integration_report_assembly_plan_length` | assembly_plan ≥ 1 entry |
| `test_ao_ma_8_e2e_smoke_integration_report_conflict_count_zero` | conflicts=[] |
| `test_ao_ma_8_e2e_smoke_all_guard_flags_closed_in_chain` | manifest + task_graph + worker_result + review_verdict + verification_report + integration_report all guard_flags={False,False,False} |
| `test_ao_ma_8_e2e_smoke_no_assembly_plan_executed` | assembly_plan persisted but NOT invoked (no git push / no gh pr create) — assert by side-effect absence |
| `test_ao_ma_8_e2e_smoke_evidence_receipt_matches_runtime_artifact` | Read `.claude/plans/AO-MA-8-E2E-SMOKE-EVIDENCE.v1.json`; assert each expected_invariant matches runtime integration_report |
| `test_ao_ma_8_e2e_smoke_no_gpp_status_mutation` | gpp_status.v1.json byte-identical pre/post pipeline |
| `test_ao_ma_8_e2e_smoke_no_branch_protection_or_workflow_mutation` | `.github/workflows/`, `gpp_status`, scripts/gp5_platform_claim_decision unchanged after pipeline |
| `test_ao_ma_8_runtime_modules_have_no_new_subprocess_imports` | Static AST check: AO-MA-5/6/7 pure-data modules + verifier + integrator + reviewer subprocess-free (subprocess boundary per Hard stops — test harness git allowed; runtime not) |
| `test_ao_ma_8_smoke_no_new_runtime_cli_subcommand_added` | static check: `ao_kernel/orchestration/cli_handlers.py` doesn't gain a new subparser in this PR |
| `test_ao_ma_8_evidence_receipt_schema_valid` | new schema valid + receipt parses |

## New schema (receipt; not authority)

`ao_kernel/defaults/schemas/ao-ma-8-e2e-smoke-evidence.schema.v1.json` — Draft 2020-12, `additionalProperties: false`, `const` pinned where applicable. Lightweight, single-purpose; not in the AO-MA-2 schema family chain.

## Hard stops (HARD RULE pins)

- No new CLI subcommand added by this PR (static check)
- No `WorkerRunner --mock-implementer` flag (static check)
- No LLM call (no test fixture imports `AoKernelClient` or `llm_call`)
- **Subprocess boundary** (Codex iter-2 must_close #3): test harness `subprocess` calls allowed ONLY for git setup/commit/rev-parse (`_git_init_repo`, `git add`, `git commit`, `git rev-parse`, `git diff --name-only`). NO subprocess in:
  - new runtime modules
  - any CLI subcommand handler
  - WorkerRunner flag
  - AO-MA-5/6/7 pure-data modules (verify by `git diff` post-PR — unchanged)
- No GitHub write / no PR fetch / no `gh pr create` / no `git push`
- No edits to AO-MA-2/3/4/5/6/7 runtime modules
- No `gpp_status.v1.json` mutation
- No branch-protection / ruleset mutation
- No assembly_plan execution
- `release_authority` field NOT in evidence receipt schema

## PR scope allowlist (Codex iter-2 nice-to-have #4)

This PR's diff is restricted to:

1. `.claude/plans/AO-MA-8-E2E-SMOKE.md` (this plan doc)
2. `.claude/plans/AO-MA-8-E2E-SMOKE-EVIDENCE.v1.json` (receipt)
3. `ao_kernel/defaults/schemas/ao-ma-8-e2e-smoke-evidence.schema.v1.json` (receipt schema)
4. `tests/test_ao_ma_8_e2e_smoke.py` (test file)
5. `local-ai-review-evidence.v1.json` (cross-AI review trail)

NO runtime orchestration module changes. NO CLI handler changes. Static check pin: `test_ao_ma_8_pr_scope_only_touches_allowlisted_files`.

## Branch freshness (Codex iter-2 must_close #4)

Feature worktree must be up-to-date with `origin/main` before commit. Plan author runs `git fetch origin main && git merge --ff-only origin/main` (or rebase) so the diff base is fresh; otherwise `branch_freshness` release-gate check fails-closed in CI.

## Nice-to-have absorbtions (Codex iter-2)

- **Reviewer pr_diff from real git diff** (iter-2 nice-to-have #1): Test reuses the worker's worktree `git diff base_sha..HEAD` output as the reviewer's `--diff-path` artifact (instead of an inert stub). Makes `allowed_sources=["pr_diff"]` truthful.
- **Verifier explicit gpp_status_path** (iter-2 nice-to-have #2): Test passes an explicit `gpp_status_path` (synthesized under **tmp repo root** — i.e. `<tmp_repo>/.claude/plans/gpp_status.v1.json` — so the verifier's `artifact_hashes` repo-relative recording works; Codex iter-3 nice-to-have #3 absorb) to `Verifier.verify()` so artifact_hashes records it deterministically. Does NOT exercise the default `<repo>/.claude/plans/gpp_status.v1.json` auto-discovery path — that drift goes to a separate follow-up if/when it surfaces.
- **16-test single shared pipeline fixture reuse** (iter-2 nice-to-have #3): All 16 assertions run against a **single shared pipeline fixture** (built once via pytest fixture); 16 separate pipeline invocations would be wasteful + flaky. Test perf < 5s target.

## Acceptance for AO-MA-8 v1

- ✅ Pipeline test file lands (`tests/test_ao_ma_8_e2e_smoke.py`) with ≥12 tests
- ✅ Evidence receipt file lands (`.claude/plans/AO-MA-8-E2E-SMOKE-EVIDENCE.v1.json`)
- ✅ Evidence schema lands (`ao_kernel/defaults/schemas/ao-ma-8-e2e-smoke-evidence.schema.v1.json`)
- ✅ Cross-AI Codex iter-N AGREE
- ✅ ruff + mypy clean
- ✅ Full test suite no regression
- ✅ Shadow mode pins all asserted (no PR, no auto-merge, no GitHub write, no gpp mutation)
- ✅ Receipt-vs-runtime parity invariant pin
- ✅ AO-MA-1 §8 plan row AO-MA-8 marked complete — **separate closure slice / follow-up PR** (this PR does NOT edit `.claude/plans/AO-MA-1-MULTI-AGENT-ORCHESTRATION-DESIGN.md`; row closure stays out of scope to keep the PR diff narrow per allowlist)
