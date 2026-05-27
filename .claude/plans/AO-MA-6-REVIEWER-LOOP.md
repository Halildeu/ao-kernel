# AO-MA-6 — Reviewer artifact intake + schema-valid verdict emit + bounded REVISE guard (no LLM call)

**Status:** plan-time iter-3 AGREE absorbed (Codex thread `019e6923-7a82-7dd0-b2e0-fd99a8b3b03f`; iter-1 PARTIAL → iter-2 PARTIAL → iter-3 AGREE, `ready_for_impl: true`). Implementation in progress.
**Branch:** `codex/ao-ma-6-reviewer-loop`
**Decision artifact:** `ao_ma_6_reviewer_artifact_intake_no_llm_call_v1`
**Parent:** AO-MA-1 §8 phased plan slice AO-MA-6
**Support impact:** none

## Purpose

AO-MA-1 §8 plan AO-MA-6 = "Reviewer loop contract and bounded REVISE handling." AO-MA-5 v1 (PR #654 merged `45c9fdb`) Integrator review_verdict.v1.json'u tüketiyor; AO-MA-6 onu **üretir** (producer slice).

**Codex iter-1 PARTIAL absorb (kabul edilmiş tasarım daraltması):**

AO-MA-6 v1 **NO LLM call** (skeleton). Yalnız:
- Reviewer artifact intake (explicit CLI paths)
- Schema-valid `review_verdict.v1.json` emit
- Bounded REVISE guard (max_revise_rounds aşımında BLOCK)
- Cross-provider fail-closed enforcement
- Source boundary fail-closed (only allowed_sources)

**LLM execution OUT of v1** — `--llm-driven` flag YOK, feature-gated bile değil. AO-MA-5'te `dry_run` symbol'u kaldırma kararı gibi: v1'de wet-mode kavramı olmaz. Future slice (AO-MA-6.5 veya v1.1+) için "LLM execution driver later" notu.

**Critical invariants:**

- **No LLM call**, no `subprocess` import, no `gh` / `git push` execute
- **No GitHub write** — review_verdict.v1.json local emit only
- **No PR/GitHub fetch in v1** — explicit paths only (`--diff-path`, `--ci-results`, etc.)
- **No AO-MA-5 modification** in this PR — AO-MA-6 only adds reviewer producer; integrator stays as-is
- **Cross-provider enforcement** — `reviewer.provider != implementer.provider` fail-closed; implementer identity from `worker_result.worker.provider` (NOT user-supplied)
- **Source boundary** — `allowed_sources` derived from CLI paths provided (pr_diff, issue_acceptance, repo_ssot, ci_results, artifact_chain, finding_context); user cannot inject hidden sources
- **Bounded REVISE** — `--prior-review-verdict <path>` repeatable; **AO-MA-6 reviewer (producer)** counts REVISE entries (where `task_graph_id == manifest.task_graph_id` AND `reviewed_task_id == --task-id`) vs `task_graph.review_policy.max_revise_rounds`; when count `>= budget` AND current verdict is `REVISE`, emitted verdict is forced to `BLOCK` (only `REVISE` is overridden — `AGREE` and `BLOCK` pass through unchanged). AO-MA-5 integrator stays consumer-only.
- `guard_flags` always literal `false`

## Codex istişaresi

Thread `019e6923-7a82-7dd0-b2e0-fd99a8b3b03f` iter-1 PARTIAL absorbed.

| # | Codex önerisi | Absorbed karar |
|---|---|---|
| 1 | LLM boundary L1 (no LLM call v1) | ✅ AO-MA-6 v1 skeleton only |
| 2 | No `--llm-driven` flag | ✅ Wet-mode kavramı yok |
| 3 | Bounded REVISE R3 primary, R1 defensive | ✅ Orchestrator replans; AO-MA-6 enforces budget on input |
| 4 | No `revise_count` schema extension | ✅ Count via `--prior-review-verdict` files |
| 5 | Explicit paths, no PR/GitHub fetch | ✅ All inputs are file paths |
| 6 | Module layout ok + maybe review_context.py later | ✅ ao_kernel/orchestration/reviewer.py + review_verdict_writer.py + cli_handlers.py |
| 7 | Cross-provider fail-closed + implementer from worker_result | ✅ Static check at reviewer init |

### 7 must_close_before_impl (Codex iter-1 + iter-2 absorb hedefleri)

1. **v1 scope adı:** "Reviewer artifact intake + schema-valid verdict emit + bounded REVISE guard (no LLM call)" — title + PR title + CLI help.
2. **LLM execution OUT pin:** plan doc + HARD RULE pin tests (`test_reviewer_module_has_no_subprocess_import`, `test_reviewer_module_has_no_llm_call_literals` — no `llm_call`, `AoKernelClient`, `client.llm_call` strings in reviewer.py).
3. **`--prior-review-verdict` REVISE count algorithm:** count entries where `verdict == "REVISE"` AND `task_graph_id == manifest.task_graph_id` AND `reviewed_task_id == --task-id` (defensive cross-ref).
4. **Max-aşımı semantik (Codex iter-2 must_close #1 correction):** budget = `task_graph.review_policy.max_revise_rounds`. If `len(prior_revise_entries) >= budget` AND current `--verdict == "REVISE"`, output is FORCED to `BLOCK` (only `REVISE` is overridden — `AGREE` allows accept, `BLOCK` stays as `BLOCK`). Rationale: `max_revise_rounds` prevents endless ping-pong; if implementer fixed the issue and reviewer agrees, budget is not the right gate.
5. **PR/GitHub fetch OUT:** plan doc + CLI surface (no `--pr <url>`); future helper `collect-review-context` separate slice.
6. **Same-provider fail-closed + implementer identity source:** `--worker-result <task_id>=<path>` REQUIRED; reviewer reads `worker_result.worker` block; cross-checks `worker_result.worker.provider != reviewer.provider`; if equal → IntegratorError-style exit 2.
7. **AO-MA-5 untouched:** this PR adds NEW files; no edits to `ao_kernel/orchestration/integrator.py` or `integration_report_writer.py` or the AO-MA-5 schema.

## Module layout

```
ao_kernel/orchestration/
  reviewer.py                       # Reviewer class + ReviewInputs/ReviewDecision dataclasses
  review_verdict_writer.py          # emit + schema validate + atomic write
  cli_handlers.py                   # extend: cmd_orchestration_review

# (review_context.py optional helper if context parsing grows; v1 inlines)
```

## CLI surface (Codex iter-1 önerisi)

```bash
ao-kernel orchestration review \
  --manifest <path>                                       # AO-MA-3 manifest.v1.json (required)
  --task-id <id>                                          # which task this review covers (required)
  --worker-result <task_id>=<path>                        # required (≥1): implementer identity source
  --reviewer-agent-id <id>                                # required
  --reviewer-provider <openai|anthropic|minimax|google|local|tool>  # required, fail-closed if matches implementer
  --reviewer-session-id <id>                              # required
  --verdict AGREE|REVISE|BLOCK                            # required (single verdict)
  --findings-json <path>                                  # required (findings[] strict schema; see below)
  [--diff-path <path>]                                    # PR diff or git diff snapshot
  [--acceptance-criteria-path <path>]                     # task.acceptance_criteria evidence
  [--repo-ssot <path>]                                    # repo SSOT excerpt consulted
  [--ci-results <path>]                                   # CI output consulted
  [--artifact-chain <path>]                               # related AO-MA artifacts consulted
  [--prior-review-verdict <path> ...]                     # repeatable; for REVISE budget count
  [--output <path>]                                       # default: <manifest_dir>/workers/<task_id>/review_verdict.v1.json
  [--format text|json]                                    # default: text
```

`allowed_sources` is **derived** from which optional paths were provided (NOT user-supplied). `reviewed_artifacts` is derived from `--worker-result` + all evidence paths + `--prior-review-verdict` files.

**`--findings-json` strict schema (Codex iter-2 must_close #3):** the file must be a top-level JSON array whose items conform to the AO-MA-2 `ao-ma-review-verdict.schema.v1.json::$defs.finding` shape — `additionalProperties=false`, required `severity` (enum `info|warning|blocking`) + `title` + `body`; optional `file` (AO-MA path) + `line` (positive int). The CLI does NOT transform `text → body` or accept extra fields. Validation failure → exit 2.

**`--worker-result` full schema + cross-ref (Codex iter-2 must_close #2 + iter-1 must_close #6):** the supplied path is validated against the full `ao-ma-worker-result.schema.v1.json` AND `worker_result.task_graph_id == manifest.task_graph_id` AND `worker_result.task_id == --task-id` AND the CLI mapping key (`<task_id>` in `<task_id>=<path>`) equals the payload `task_id`. Then `reviewer.provider` is compared against `worker_result.worker.provider`; equal → cross-provider violation exit 2.

## Exit code matrix

| Outcome | exit |
|---|---|
| review_verdict.v1.json emitted successfully | 0 |
| Cross-provider violation (reviewer.provider == implementer.provider) | 2 |
| Missing required input (manifest / worker-result / verdict / findings) | 2 |
| Schema validation failure on input (worker_result invalid) | 2 |
| Schema validation failure on output emit | 3 |
| Bounded REVISE budget hit + verdict argument was REVISE → output forced to BLOCK | 0 (emitted; budget enforcement is operator-actionable downstream) |

## Test coverage plan

| Test | Cover |
|---|---|
| `test_review_happy_path_emits_schema_valid_verdict` | AGREE with full evidence paths |
| `test_review_revise_with_prior_verdicts_under_budget` | REVISE allowed when count < max |
| `test_review_revise_at_budget_forces_block` | Codex iter-1 R3 must_close #4 |
| `test_review_revise_over_budget_forces_block` | safety margin |
| `test_review_block_passes_through` | direct BLOCK verdict |
| `test_review_cross_provider_violation_exit_2` | reviewer.provider == implementer.provider |
| `test_review_missing_worker_result_exit_2` | required input |
| `test_review_invalid_worker_result_schema_exit_2` | input schema validation |
| `test_review_allowed_sources_derived_from_paths_only` | source boundary |
| `test_review_reviewed_artifacts_derived_not_user_input` | source boundary |
| `test_review_cross_ref_task_graph_id_matches_manifest` | trust boundary |
| `test_review_cross_ref_prior_verdicts_same_task_id` | budget count safety |
| `test_reviewer_module_has_no_subprocess_import` | HARD RULE static |
| `test_reviewer_module_has_no_llm_call_literals` | HARD RULE static |
| `test_reviewer_module_has_no_gh_or_git_push_literals` | HARD RULE static |
| `test_cli_review_exit_codes_matrix` | exit codes per §matrix |
| `test_cli_review_does_not_call_subprocess` | HARD RULE behavioural |
| `test_review_emits_to_default_path_under_workers_subdir` | path convention |
| `test_review_no_pr_url_argument_in_cli` | --pr OUT of v1 |
| `test_review_no_llm_driven_argument_in_cli` | --llm-driven OUT of v1 |
| `test_review_does_not_modify_ao_ma_5_modules` | AO-MA-5 untouched |
| `test_review_findings_json_shape_validation` | findings[] strict AO-MA-2 `$defs.finding` shape |
| `test_review_findings_json_rejects_text_field` | iter-2 nice-to-have: text-field schema drift early catch |
| `test_review_findings_json_rejects_extra_property` | additionalProperties=false enforcement |
| `test_review_findings_json_rejects_missing_severity_or_title_or_body` | required fields |
| `test_review_findings_json_rejects_invalid_severity_enum` | severity enum |
| `test_review_worker_result_mapping_key_must_match_payload_task_id` | iter-2 nice-to-have: CLI mapping cross-ref |
| `test_review_budget_ignores_prior_verdicts_from_other_graph_or_task` | iter-2 nice-to-have: defensive cross-ref |
| `test_review_agree_overrides_budget_concern` | iter-2 must_close #1: AGREE passes through |
| `test_review_budget_diagnostic_includes_requested_vs_emitted` | iter-2 nice-to-have: operator visibility |

Minimum 22 tests.

## Hard stops

- No LLM call (no `subprocess` to `claude`/`codex`/`gpt`, no `AoKernelClient.llm_call`)
- No GitHub write (no `git push`, no `gh pr create`, no `gh api PUT`)
- No PR/GitHub fetch (no `gh pr view`, no `git fetch origin` for review context)
- No branch protection mutation
- No workflow file change
- No AO-MA-5 module edits
- `guard_flags`: all literal false
- `release_authority` field NOT in review_verdict.v1 (only in integration_report.v1)

## Dependencies + risks

**Dependencies:**
- AO-MA-5 v1 PR #654 merged ✅ (consumer ready for review_verdict.v1)
- AO-MA-2 review_verdict.v1 schema ✅ (already exists, no extension needed)
- AO-MA-3 task_graph.review_policy.max_revise_rounds ✅ (already exists)

**Risks:**
- AO-MA-6 v1 always-no-LLM means external reviewer (human or external Codex/GPT) writes the verdict. If operator workflow expects automated reviewer, v1 is just a "validation layer" not full automation. Plan doc explicit about this scope.
- `--prior-review-verdict` REVISE count requires operator to pass past round files; if operator forgets, budget enforcement bypassed. Defensive: scan default convention directory `<manifest_dir>/workers/<task_id>/review_verdict.v1.json` history? v1 minimum: explicit `--prior-review-verdict` only; doc emphasizes operator responsibility.

## Acceptance for AO-MA-6 v1

- ✅ Reviewer class implements input → policy → emit pipeline (no LLM call)
- ✅ ReviewDecision dataclass (overall_status + report + diagnostics + has_budget_exceeded)
- ✅ CLI subcommand `review` lands
- ✅ 22+ tests pass (incl. HARD RULE pin tests, cross-provider, source boundary, REVISE budget)
- ✅ Codex cross-AI review iter-N AGREE
- ✅ ruff + mypy clean
- ✅ no LLM call / no PR fetch / no gh write asserted by test + plan doc + code review
- ✅ AO-MA-5 modules untouched (no edits to integrator.py / integration_report_writer.py / schemas)
