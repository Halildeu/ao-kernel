# AO-MA-4 — Parallel Worktree Runner

**Status:** ready for PR / no support widening
**Branch:** `codex/ao-ma-4-parallel-worktree-runner`
**Decision artifact:** `ao_ma_4_parallel_worktree_runner_no_worker_execution`
**Parent:** AO-MA-1 §8 phased plan slice AO-MA-4
**Support impact:** none

## Purpose

AO-MA-1 §8 plan'da AO-MA-4 = "Parallel worktree runner with file ownership
enforcement and conflict detection." AO-MA-3 (PR #645, merged `af30353`)
artifact emit ediyor. AO-MA-4 onları okur ve **parallel worktree spawn**
sürecini başlatır.

**Kritik invariantlar:**

- **No LLM call**, **no agent execution**, **no worker_result.v1 üretimi**
  (Codex iter-1 absorb — worker producer rolünde değiliz)
- **No GitHub write**, no branch protection mutation
- Per-worker file ownership: post-diff `verify_diff()` authoritative
  (`actual_changed_files ⊆ declared_write_set`)
- Manifest hash mismatch, cross-ref mismatch, base sync mismatch → fail-closed
- Branch conflict (existing branch with different HEAD) → fail-closed
- Empty declared write set → spawn fail-closed (AO-MA-3 sentinel detection)

## Codex istişare

Thread `019e666f-94c8-75a3-9a55-164f54d3bddf` iter-1 REVISE absorbed:

- ✅ `worker_result.v1` AO-MA-4'ün ürettiği DEĞİL (producer = Worker, schema requires actual data)
- ✅ Post-diff `actual ⊆ declared` SUBSET (eşit değil; declared ama dokunulmamış dosya ihlal değil)
- ✅ `runner_report.v1.json` için ayrı schema + tests (drift önlemi)
- ✅ File ownership: **B authoritative** (`verify_diff()` post-write check); A opsiyonel uyarı (per-worktree pre-commit hook); C yok (chroot overkill)
- ✅ Worktree path: AO-MA-3 assignment default + `--worktree-base <path>` override + `AO_MA_WORKTREE_BASE` env fallback
- ✅ `.ao/orchestration/` gitignore'a ekle veya repo-dışı sibling default
- ✅ Branch conflict fail-closed (auto-suffix `-N` YOK)
- ✅ Idempotency strict: branch adı + HEAD == base_sha + worktree git registry + worktree clean + runner_report match
- ✅ Conflict detection defense-in-depth: manifest hash + cross-ref + base sync mismatch fail
- ✅ Base sync: rebase YOK; assignment `base_sha` ≠ `origin/main` ise `manifest_stale` fail; orchestrator yeniden çalıştırılmalı
- ✅ CLI: `ao-kernel orchestration spawn --manifest <path>` + ayrı `ao-kernel orchestration cleanup --manifest <path>`
- ✅ Cleanup: dirty worktree → fail; branch silme default değil, `--delete-branches` ile + clean/merged/base-only doğrulama

## Module layout

```
ao_kernel/orchestration/
  worker_runner.py            # WorkerRunner (parse manifest, spawn worktrees, verify_diff)
  runner_report_writer.py     # runner_report.v1 emit + SHA256 hash chain
  cli_handlers.py             # extend: cmd_orchestration_spawn, cmd_orchestration_cleanup

ao_kernel/defaults/schemas/
  ao-ma-runner-report.schema.v1.json   # NEW: drift önlemi

.gitignore                    # .ao/orchestration/ ignore (nested worktree → primary dirty olmasın)

tests/
  test_orchestration_worker_runner.py       # ~15 test
  test_orchestration_runner_report.py        # ~6 test
  test_orchestration_cli_spawn.py            # ~5 test
  test_orchestration_cli_cleanup.py          # ~4 test
```

## Public API (ao_kernel/orchestration)

```python
from ao_kernel.orchestration import WorkerRunner, RunnerReportWriter

runner = WorkerRunner(repo_root=Path("."), worktree_base=None)
report = runner.spawn(manifest_path=Path(".ao/orchestration/<id>/manifest.v1.json"))
# report: dict matching ao-ma-runner-report.v1 schema

runner.verify_diff(assignment_id="...")
# returns RunnerVerificationResult (subset check)

runner.cleanup(manifest_path=..., delete_branches=False)
# returns dict {removed_worktrees, kept_branches, kept_dirty}
```

## CLI surface

```bash
# Spawn parallel worktrees from an AO-MA-3 manifest
ao-kernel orchestration spawn \
  --manifest .ao/orchestration/<id>/manifest.v1.json \
  [--worktree-base /path/to/external/sibling] \
  [--dry-run]

# Cleanup
ao-kernel orchestration cleanup \
  --manifest .ao/orchestration/<id>/manifest.v1.json \
  [--delete-branches]
```

## runner_report.v1.json schema (yeni)

Required fields:
- `schema_version`: `"ao-ma-runner-report.v1"`
- `task_graph_id`
- `manifest_sha256`
- `base_sha` (origin/main current; must equal task graph base_sha)
- `generated_at` (UTC ISO)
- `conflict_check`: `pass | failed_overlap | failed_manifest_stale`
- `base_sync_check`: `pass | failed_base_mismatch`
- `workers`: array of:
  - `assignment_ref`: relative path to agent_assignment-*.v1.json
  - `assignment_sha256`: from manifest
  - `task_id`, `branch`, `planned_worktree`, `actual_worktree`
  - `status`: `prepared | skipped_existing_idempotent | failed_branch_exists_mismatch | failed_worktree_exists_mismatch | failed_empty_write_set | failed_base_mismatch`
  - `reason`: short string
  - `expected_worker_result_path`: e.g. `<worktree>/worker_result.v1.json` (NOT created; downstream worker will write)
- `guard_flags`: {support_widening, production_platform_claim, live_adapter_execution: false}

## Forbidden actions (none touched)

- No `gpp_status.v1.json` mutation
- No `scripts/gp5_platform_claim_decision.py` mutation
- No `ao_kernel/defaults/policies/` mutation
- No `.github/workflows/` mutation
- No branch protection / ruleset mutation (AO-MA-1 §9)
- No `ao_kernel/` public SDK signature break
- `support_widening`, `production_platform_claim`, `live_adapter_execution` always false
- **No agent execution, no LLM call, no GitHub write, no worker_result.v1 creation**

## Test Coverage (~30 test)

| File | Scenario |
|---|---|
| test_orchestration_worker_runner.py | manifest parse, manifest hash verify, cross-ref verify, base sync verify, branch creation, worktree creation idempotent, empty write set spawn fail, branch exists mismatch fail, worktree exists mismatch fail, declared write set canonical validation, verify_diff actual⊆declared pass, verify_diff actual⊄declared fail, dry-run no FS side effect, multiple workers parallel, rename/delete diff ownership |
| test_orchestration_runner_report.py | report schema valid, manifest_sha256 matches, base_sync_check states, conflict_check states, guard flags closed, multiple worker statuses |
| test_orchestration_cli_spawn.py | CLI spawn happy path, --manifest required, --worktree-base override, --dry-run, exit code on conflict |
| test_orchestration_cli_cleanup.py | cleanup removes clean worktrees, refuses dirty worktrees, --delete-branches kicks in only with clean/merged, idempotent on already-cleaned |

## Downstream

AO-MA-4 tamamlandığında:
- Operator (sen) `ao-kernel orchestration plan ...` + `ao-kernel orchestration spawn ...` ile parallel worktree'ler hazırlar
- Bu noktada **manuel** worker spawn yapabilir (AO-MA-3 + AO-MA-4 manuel pipeline)
- AO-MA-5 integrator policy → conflict resolution + single PR
- AO-MA-6 reviewer loop + bounded REVISE = "ping-pong"
- AO-MA-7 verifier lane
- AO-MA-8 end-to-end smoke shadow mode
- AO-MA-9 GPP-2D required-check entegrasyonu
