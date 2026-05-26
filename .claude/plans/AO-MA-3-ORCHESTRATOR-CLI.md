# AO-MA-3 — Local Orchestrator CLI

**Status:** ready for PR / no support widening
**Branch:** `codex/ao-ma-3-orchestrator-cli`
**Decision artifact:** `ao_ma_3_local_orchestrator_cli_no_agent_spawn`
**Parent:** AO-MA-1 §8 phased plan slice AO-MA-3
**Support impact:** none

## Purpose

AO-MA-1 §8 plan'da AO-MA-3 = "Local orchestrator CLI that reads SSOT and
emits a task graph **without spawning agents yet**." Bu slice runtime'a giriş
noktası: orchestrator user goal'u okur, slice'lara ayırır, dependency kurar,
risk class atar, ve `task_graph.v1` + `agent_assignment.v1` artifact'ları
üretir (AO-MA-2 schemas ile validated).

**Hard stop:** worker spawn YOK, LLM call YOK, agent execution YOK. Sadece
artifact üretimi. Worker spawning AO-MA-4'te gelir.

## Authority

GPP-9 closed under `keep_narrow_stable_runtime`. Bu slice:
- `support_widening_allowed=false`
- `production_platform_claim_allowed=false`
- `live_adapter_execution_allowed=false`

Tamamı değişmez. AO-MA-1 §9 hard stops korunur.

## Codex istişare

Thread `019e6645-fafe-7690-9d47-ca60fdaffee0` plan-time iter-1 REVISE absorbed:

- ✅ Konum: `ao_kernel/orchestration/orchestrator.py` (yeni dizin); `coordination/` lease/fencing tabanı kalır
- ✅ CLI: canonical `ao-kernel orchestration plan --goal ...`; `scripts/ao_orchestrator.py` thin wrapper
- ✅ Storage: `.ao/orchestration/<task-graph-id>/`
- ✅ Deterministic `task_graph_id` — hash-based reproducible
- ✅ `base_sha` 40-char `origin/main`
- ✅ Artifact hash/manifest — `.ao/orchestration/<id>/manifest.v1.json`
- ✅ Overlap/conflict fail-closed — iki worker aynı dosyaya yazamaz
- ✅ Free-form goal'dan dosya/slice uydurmaz — path/slice declaration yoksa **tek konservatif task** üret
- ✅ Risk classification genişletilmiş liste (aşağı)

## Module layout

```
ao_kernel/orchestration/
  __init__.py                     # Public API: Orchestrator, build_task_graph
  orchestrator.py                 # Core logic (Pure-Python, no LLM)
  risk_classifier.py              # Risk class heuristic
  task_graph_builder.py           # Task graph + assignment construction
  artifact_writer.py              # JSON write + manifest + hash

scripts/
  ao_orchestrator.py              # Thin CLI wrapper (calls ao_kernel.cli)

ao_kernel/cli.py                  # subcommand 'orchestration' added

tests/
  test_orchestration_orchestrator.py
  test_orchestration_risk_classifier.py
  test_orchestration_artifact_writer.py
  test_orchestration_cli.py
```

## Risk Classification (genişletilmiş)

`high-risk` path pattern'ları:

| Pattern | Sebep |
|---|---|
| `.github/**` | Workflow, ruleset, app config |
| `CODEOWNERS`, `AGENTS.md`, `CLAUDE.md` | Governance principal |
| `.claude/plans/GPP-*`, `.claude/plans/AO-GATE*`, status docs | Program SSOT |
| `.claude/plans/gpp_status.v1.json` | Machine-readable governance |
| `ao_kernel/ao_release_gate*.py` | Release authority code |
| `ao_kernel/live_adapter_gate*.py` | Live adapter gate code |
| `scripts/ao_release_gate*.py` | Release gate scripts |
| `scripts/local_gpp_gate*.py` | Local gate scripts |
| `scripts/live_adapter_gate*.py` | Live adapter scripts |
| `ao_kernel/defaults/policies/**` | Policy SSOT |
| `ao_kernel/defaults/schemas/*gate*.json` | Gate schemas |
| `ao_kernel/defaults/schemas/ao-ma-*.schema.v1.json` | AO-MA artifact contracts |
| `deploy/**`, `deploy/*gate*`, `deploy/internal-gate-host/**` | Deployment surface |
| Secret/Vault/GitHub-App/Cloud-Run wiring | Secret boundary |
| `tests/test_*gate*.py`, `tests/test_gpp_*.py` | Gate/GPP test surface |

Risk class: `low` (default) → `normal` → `high` (yukarıdaki path'lerden biri tetiklerse) → `critical` (multiple high-risk path).

## Public API (ao_kernel/orchestration)

```python
from ao_kernel.orchestration import Orchestrator, build_task_graph

orch = Orchestrator(repo_root=Path("."), ssot=SSOTPaths.default())
graph = orch.build_task_graph(goal="...", declared_paths=None)
# graph: TaskGraph object; valid against ao-ma-task-graph.v1 schema
assignments = orch.assign(graph)
# assignments: list[AgentAssignment]; valid against ao-ma-agent-assignment.v1
manifest = orch.emit(graph, assignments, output_dir=Path(".ao/orchestration/<id>"))
# manifest: .ao/orchestration/<id>/manifest.v1.json with SHA256 of each artifact
```

## CLI surface

```bash
ao-kernel orchestration plan \
  --goal "extend local-ai-review-evidence schema with verifier role" \
  --output-dir .ao/orchestration \
  [--declared-paths path1 path2 ...] \
  [--ssot-agents AGENTS.md --ssot-status .claude/plans/gpp_status.v1.json]

# Output:
# .ao/orchestration/ao-ma-2026-05-27-abc1234/task_graph.v1.json
# .ao/orchestration/ao-ma-2026-05-27-abc1234/agent_assignment-task-001.v1.json
# .ao/orchestration/ao-ma-2026-05-27-abc1234/manifest.v1.json
# stdout: task graph summary + path printout
```

Thin wrapper script:

```bash
python scripts/ao_orchestrator.py --goal "..."
# equivalent to: ao-kernel orchestration plan --goal "..."
```

## Determinism

`task_graph_id` deterministic:

```python
sha256(
    goal_normalized + base_sha + declared_paths_sorted + utc_date_yyyymmdd
).hexdigest()[:7]
# → ao-ma-2026-05-27-abc1234
```

Aynı goal + base_sha + declared paths + same UTC day → aynı id.

## Conflict / Overlap Fail-Closed

Multi-slice graph'ta worker write set'leri **disjoint** olmalı. Overlap tespit edildiğinde:

- Orchestrator hata verir (RuntimeError + finding code `ao_ma_3_worker_overlap_detected`)
- Artifact üretilmez
- CLI exit code 1

Konservatif default: declared_paths verilmediğinde tek task üret (multiple slice tahmini risk).

## Test Coverage (~18 test)

| Test | Senaryo |
|---|---|
| `test_orchestrator_init_with_default_ssot` | Default SSOT paths |
| `test_build_task_graph_emits_schema_valid` | Output AO-MA-2 schema valid |
| `test_task_graph_id_deterministic` | Aynı input → aynı id |
| `test_task_graph_id_changes_with_goal` | Farklı goal → farklı id |
| `test_task_graph_id_changes_with_base_sha` | Farklı base_sha → farklı id |
| `test_risk_low_for_test_only_change` | tests/foo.py → low |
| `test_risk_high_for_workflow_change` | .github/workflows/x.yml → high |
| `test_risk_high_for_gate_script_change` | scripts/ao_release_gate*.py → high |
| `test_risk_high_for_gpp_status_change` | gpp_status.v1.json → high |
| `test_risk_critical_for_multi_high_paths` | 3+ high path → critical |
| `test_no_declared_paths_emits_single_task` | Konservatif default |
| `test_multi_slice_disjoint_write_sets_pass` | Valid multi-slice |
| `test_multi_slice_overlap_fails_closed` | Same file → RuntimeError |
| `test_assignment_branch_pattern_matches_schema` | branch regex valid |
| `test_artifact_writer_emits_manifest` | manifest.v1.json with SHA256 |
| `test_artifact_writer_paths_under_output_dir` | No path escape |
| `test_cli_plan_subcommand_writes_artifacts` | end-to-end CLI test |
| `test_cli_plan_exits_nonzero_on_overlap` | overlap fail-closed CLI |
| `test_guard_flags_always_false` | support_widening etc. always false |

## Forbidden actions (none touched)

- No `gpp_status.v1.json` mutation
- No `scripts/gp5_platform_claim_decision.py` mutation
- No `ao_kernel/defaults/policies/` mutation
- No `.github/workflows/` mutation
- No branch protection / ruleset mutation (plan §9 hard stop)
- No `ao_kernel/` public SDK signature break
- `support_widening`, `production_platform_claim`, `live_adapter_execution` hepsi false
- **No agent spawning, no LLM call, no worker execution** (AO-MA-3 §6 explicit no-op)
- AO-MA-1 §9 hard stops korunur

## Cross-AI peer review

- Plan-time: Codex thread `019e6645` iter-1 REVISE → absorbed
- Implementer: Claude (Anthropic)
- Reviewer: Codex (OpenAI) — post-impl iter sonrası
- Evidence: `local-ai-review-evidence.v1.json` (cross-provider verified)

## Downstream

AO-MA-3 tamamlandığında:
- Orchestrator artifact üretebilir (task_graph + assignments + manifest)
- Worker spawn YOK — AO-MA-4 başlatır
- AO-MA-4 worktree runner artifact'ları okur, gerçek worker spawn eder
- AO-MA-5 integrator policy, AO-MA-6 reviewer loop, AO-MA-7 verifier, AO-MA-8 smoke, AO-MA-9 GPP-2D entegrasyon
