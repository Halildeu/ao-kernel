# V5 Epic 7: Performance Baseline + Regression Threshold Policy

> **Cross-AI plan-time AGREE** — Codex thread `019e8410` (4 iters: REVISE×3 → AGREE)
> **Implementer:** Anthropic Claude / **Reviewer:** OpenAI Codex
> **Risk class:** conservative low-risk (docs/schemas/scripts/tests only; no runtime; no workflows)

## 1. Scope

Schema-backed performance baseline + regression threshold policy for the
existing PR-B7 benchmark suite. **Policy definition only**, not a CI
hard-fail gate (E-7a `enforcement_mode: advisory`).

**In scope:**
- 3 JSON Schemas (Draft 2020-12): scenario catalog + baseline + threshold
- 3 artifacts: catalog (workflow_id source-of-truth) + baseline (mode-filtered, candidate) + threshold (advisory)
- `scripts/promote_baseline.py` — deterministic catalog-join promoter
- 10-section operator README (runbook + update cadence + investigation)
- 45 invariant tests

**Out of scope (ZERO TOUCH per Codex absorb):**
- `tests/test_scorecard_schema.py` (existing scorecard schema test)
- `ao_kernel/defaults/schemas/scorecard.schema.v1.json` (existing schema)
- `tests/benchmarks/` (existing PR-B7 suite)
- `ao_kernel/_internal/scorecard/` (collector, compare, render)
- `.github/workflows/test.yml` benchmark-fast job
- Runtime performance optimization
- p95 / median / repeated sampling / statistical aggregation (E-7h)
- CI required-check promotion (E-7x track)

## 2. Codex Iter Chain (4 iters)

### iter-1 plan-time REVISE — 5 BLOCKER

| ID | Issue | Resolution |
|---|---|---|
| E7-GATE-SEMANTICS | "CI hard fail" + "no workflow change" contradiction; current scorecard is advisory | E-7a = `enforcement_mode: advisory` policy definition only; CI red is future E-7x slice |
| E7-P95-MISMATCH | Current scorecard has `duration_ms` single-run, no p95 field | `primary_metric: duration_ms` + `statistic: single_run`; p95 deferred to E-7h |
| E7-THRESHOLD-DEFAULTS | 10%/5% too aggressive against single-run CI samples | 20%/30% conservative defaults (matches existing repo scorecard policy) |
| E7-SCENARIO-CATALOG-FILE | Q7 file list missing scenario catalog artifact | Added `performance-scenario-catalog.v1.json` + schema |
| E7-BASELINE-SCHEMA | Baseline manifest needs its own schema, not just threshold | Added `performance-baseline.schema.v1.json` |

### iter-2 plan-time REVISE — 1 BLOCKER

| ID | Issue | Resolution |
|---|---|---|
| E7-WORKFLOW-ID-SOURCE | Scorecard does not carry `workflow_id`; promote script cannot read it | Catalog is source-of-truth for `workflow_id`; script joins by `source_scorecard_scenario` |

### iter-3 plan-time REVISE — 1 BLOCKER

| ID | Issue | Resolution |
|---|---|---|
| E7-BASELINE-CATALOG-MODE-FILTER | Catalog includes full_mode_smoke (advisory); fast baseline can't cover it | Cross-validation: baseline IDs = catalog entries where `mode == benchmark_mode AND enforcement == 'policy_threshold'` |

### iter-4 AGREE + ready_for_impl:true + must_close_findings:[]

4 non-blocking impl notes:
- Empty selection: `exit 2` without `--allow-empty` (operator opt-in)
- Baseline schema `minItems: 1` correct for E-7a fast committed baseline
- Claim scanner allowlist: `not_sla`, `not SLA` are explicitly allowed
- Scanner runs across all docs/performance artifacts

## 3. Implementation Artifacts

| File | LOC | Purpose |
|---|---|---|
| `ao_kernel/defaults/schemas/performance-scenario-catalog.schema.v1.json` | ~60 | Catalog schema (workflow_id pinned per scenario) |
| `ao_kernel/defaults/schemas/performance-baseline.schema.v1.json` | ~110 | Baseline schema (candidate + sample_count + variance) |
| `ao_kernel/defaults/schemas/performance-regression-threshold.schema.v1.json` | ~120 | Threshold schema (advisory enforcement) |
| `docs/performance/performance-scenario-catalog.v1.json` | ~40 | 3 scenarios (governed_review + governed_bugfix + full_mode_smoke) |
| `docs/performance/baseline.v1.json` | ~55 | 2 scenarios (fast mode policy_threshold entries) |
| `docs/performance/performance-regression-threshold.v1.json` | ~55 | global_defaults 20%/30% + per-scenario overrides |
| `docs/performance/README.md` | ~180 | 10-section operator runbook |
| `scripts/promote_baseline.py` | ~210 | Deterministic catalog-join promoter |
| `tests/test_performance_baseline.py` | ~520 | 45 invariants |
| `.claude/plans/EPIC-7-PERFORMANCE-BASELINE.md` | this | Plan doc + Codex chain |

## 4. Schema Summary

### performance-scenario-catalog.v1
- Source-of-truth for `workflow_id` (scorecard doesn't carry it)
- Per-scenario: `id`, `test_module`, `workflow_id`, `source_scorecard_scenario`, `primary_metric (const duration_ms)`, `mode (fast|full)`, `may_skip_on_prereq_miss`, `enforcement (policy_threshold|advisory_only)`

### performance-baseline.v1
- `candidate_baseline: const true`, `sample_count: const 1`, `variance_profile: const "single_ci_run"`
- `generated_from` 7 metadata fields (scorecard_schema_version + git_sha + git_ref + benchmark_mode + python_version + runner_os + generated_at)
- Per-scenario: `metric { name: duration_ms, unit: ms, value, statistic: single_run }` + `status (pass|fail)` + `cost_source enum` + `workflow_id`

### performance-regression-threshold.v1
- `enforcement_mode enum {advisory, manual_block, ci_block_candidate}` (E-7a=advisory)
- `policy_disclaimer` 3 const true (not_sla + operator_tunable + single_run_candidate_baseline)
- `baseline_ref` pattern-pinned
- `global_defaults` + per-scenario override (warn/hard thresholds + applies_to_modes + action_on_missing)

## 5. Test Sections (45 invariants)

| Section | Count | Focus |
|---|---|---|
| 1. Schema validity | 8 | Draft 2020-12 + additionalProperties:false + const pins + enums |
| 2. Schema negative | 4 | Reject guard flip / unknown enforcement / candidate=false / unknown override |
| 3. Catalog content | 4 | Validates + workflow_id pin + full_mode advisory + no duplicates |
| 4. Baseline content | 5 | Validates + generated_from metadata + candidate invariants + scenarios non-empty + duration_ms metric |
| 5. Threshold content | 5 | Validates + advisory mode + baseline_ref + 20%/30% defaults + warn<hard Python invariant |
| 6. Cross-validation | 6 | Mode+enforcement filter match + threshold subset + full_mode null/advisory + scenario mode parity + claim scanner |
| 7. Promote script | 4 | Constants pinned + fast selects 2 + full selects 0 + deterministic + exit 2 on empty |
| 8. Zero-touch governance | 2 | Existing scorecard schema test present + existing schema file present |
| 9. README discipline | 3 | 10 numbered sections + guard flags mention + mode filter doc |

## 6. Defaults Rationale

| Metric | warn | hard | Reasoning |
|---|---|---|---|
| duration_ms (governed_review) | 20% | 30% | Matches existing repo scorecard policy default; single-run flake risk acknowledged |
| duration_ms (governed_bugfix) | 20% | 30% | Same baseline |
| duration_ms (full_mode_smoke) | null | null | Advisory-only; may skip on prereq miss |

10%/5% pair would generate flaky false positives against single-run CI
samples. Future tightening requires E-7h statistical collector.

## 7. Out-of-scope follow-up slices (8)

| ID | Slice |
|---|---|
| E-7b | Concurrency stress test |
| E-7c | Memory profile baseline |
| E-7d | Large-corpus benchmark |
| E-7e | Multi-provider performance comparison |
| E-7f | Cost p95 baseline (composes with E-5-4 budget pattern) |
| E-7g | Operator performance dashboard (Grafana panel) |
| E-7h | Statistical collector (repeated sampling, median/p95, variance model) |
| E-7x | CI required-check promotion track (`advisory` → `manual_block` → `ci_block_candidate`) |

## 8. References

- Existing PR-B7 benchmark suite: `tests/benchmarks/` (v3.5/v3.7)
- Existing scorecard schema: `ao_kernel/defaults/schemas/scorecard.schema.v1.json` (ZERO TOUCH)
- Existing scorecard schema test: `tests/test_scorecard_schema.py` (ZERO TOUCH)
- E-5-1 OTEL tunables: PR #791 MERGED
- E-5-4 SLI/SLO catalog: PR #799 MERGED
- HARD RULE Cross-AI Peer Review (2026-05-05, 2026-05-14)
- HARD RULE Uzun Vadeli Kalıcı Çözüm (2026-05-27)
- Codex thread `019e8410` (4-iter REVISE×3 → AGREE)
