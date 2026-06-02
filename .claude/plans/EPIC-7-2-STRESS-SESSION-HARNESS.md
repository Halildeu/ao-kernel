# V5 Epic 7 E-7-2: Long-Running Session Stress Harness

> **Risk class:** conservative low-risk (library-mode + stub LLM only)
> **Implementer:** Anthropic Claude / **Reviewer:** OpenAI Codex (post-impl)

## 1. Scope

Opt-in CLI harness that drives a stress loop over configurable
iteration count + wall-clock budget while recording memory + duration
deltas. Library mode only (no `.ao/` workspace write); stub LLM route
(no live provider call); `live_adapter_execution=false` preserved.

**In scope:**
- `scripts/run_stress_session.py` (~140 LOC) with `run()` + `main()` + CLI args
- 13 invariant tests covering harness structure + run-report contract + CI-safety

**Out of scope (ZERO TOUCH):**
- `.github/workflows/*` (24h+ profile is operator-invoked, not scheduled)
- Real provider client imports (`anthropic`, `openai`, `requests`, `httpx`, etc.)
- `.ao/` workspace writes
- Any guard flag flip
- Memory profiler dependency (mprof is E-7-3)

## 2. Report Schema

```json
{
  "schema_version": "stress-session-report.v1",
  "iterations_requested": <int>,
  "iterations_completed": <int>,
  "duration_seconds_budget": <float|null>,
  "duration_seconds_actual": <float>,
  "rss_kib_start": <int>,
  "rss_kib_end": <int>,
  "rss_kib_delta": <int>,
  "python_version": "X.Y.Z",
  "platform": "darwin|linux|...",
  "pid": <int>,
  "live_adapter_execution": false,
  "support_widening": false,
  "production_platform_claim": false
}
```

`rss_kib_*` from `resource.getrusage` (POSIX-portable normalized to KiB).

## 3. CLI Usage

```bash
# CI-safe smoke
python scripts/run_stress_session.py --iterations 50 --json-out -

# Operator 24h+ profile (long-running)
python scripts/run_stress_session.py \
    --iterations 100000000 \
    --duration-seconds 86400 \
    --json-out reports/stress-24h.json
```

The harness exits as soon as either iteration count or budget is reached.

## 4. Test Sections (13 invariants)

| Section | Count | Focus |
|---|---|---|
| 1. Harness presence + module structure | 4 | File exists + `--help` exit 0 + clean import + docstring pins guard flag constraints |
| 2. Run report contract | 6 | Small iter returns report + RSS/duration recorded + 3 guard flags const false + file output + duration budget short-circuit + invalid iterations exits 2 |
| 3. CI safety | 3 | Safe default iter count (50) + no live provider imports (`anthropic`/`openai`/`requests` blocked) + ZERO TOUCH `.github/workflows/` |

## 5. References

- E-7 performance baseline (PR #805 merged)
- E-7-x regression gate tooling (PR #806 merged)
- E-7-3 memory profiling (next slice, mprof harness)
- E-7-5 pgvector backend impl (future slice)
- HARD RULE Cross-AI Peer Review + No Fake Work + Uzun Vadeli
