# V5 Epic 7 E-7-3: Memory Profiling Harness

> **Risk class:** conservative low-risk (stdlib only; library mode + stub workload)
> **Implementer:** Anthropic Claude / **Reviewer:** OpenAI Codex (post-impl)

## 1. Scope

CLI harness using stdlib `tracemalloc` for memory profiling. Zero
extras dependency. Library mode + stub workload + `live_adapter_execution=false`.

**In scope:**
- `scripts/run_memory_profile.py` (~180 LOC; argparse + tracemalloc + JSON report)
- 15 invariant tests

**Out of scope (ZERO TOUCH):**
- `.github/workflows/*`
- Optional profiler imports (`mprof`, `memray`, `scalene`, `objgraph` — explicit invariant test)
- Live provider client imports
- `.ao/` workspace writes
- Any guard flag flip

## 2. Report Schema

`memory-profile-report.v1` with: iterations_requested/completed,
retain_every, retained_count, duration_seconds_actual, rss_kib
(start/end/delta), traced_kib (current/peak), top_allocations (filename
+ lineno + size_kib + count), python_version, platform, pid, 3 guard
flags const false.

## 3. CLI Usage

```bash
# CI-safe smoke
python scripts/run_memory_profile.py --iterations 200 --top 10 --json-out -

# Operator slow-leak hunt
python scripts/run_memory_profile.py \
    --iterations 100000 \
    --retain-every 100 \
    --top 25 \
    --json-out reports/memprof-leak-hunt.json
```

`--retain-every N` retains every Nth workload object to simulate slow
leak; `0` = release all.

## 4. Test Sections (15 invariants)

| Section | Count | Focus |
|---|---|---|
| 1. Harness presence + structure | 4 | File + --help + import + docstring zero-extra constraint |
| 2. Run report contract | 7 | Small iter + RSS/traced + top_allocations rows + retain_every count + 3 guard flags + file output + invalid --top exit 2 |
| 3. CI safety | 3 (+1 governance) | Default iter 200 + no live provider imports + no optional profiler imports + ZERO TOUCH workflows |

## 5. References

- E-7 baseline (PR #805)
- E-7-x regression gate (PR #806)
- E-7-2 stress harness (PR #819)
- E-7-5 pgvector backend (future slice)
- HARD RULE Cross-AI Peer Review + No Fake Work + Uzun Vadeli
