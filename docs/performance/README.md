# ao-kernel Performance Baseline + Regression Threshold Policy (V5 Epic 7)

> **Not SLA.** **Single-run candidate baseline.** **Operator-tunable.** This
> package defines a schema-backed performance baseline + regression
> threshold policy for the existing PR-B7 benchmark suite. It is a
> **policy definition**, not a CI hard-fail gate. Future slice **E-7x**
> may promote the policy from `enforcement_mode: advisory` to
> `manual_block` / `ci_block_candidate`. The three guard flags
> (`support_widening`, `production_platform_claim`,
> `live_adapter_execution`) remain `const false`.
>
> **Local/operator smoke is not production evidence.** Repo baseline
> values are derived from a single CI run; flake/variance is acknowledged
> and noted in `policy_disclaimer.variance_disclaimer`. Repeated
> sampling, p95/median collection, and statistical aggregation are out of
> scope for E-7a (see **E-7h** follow-up slice).
>
> **No SLA wording.** No `production SLA`. No `contractual SLA`. No
> `guaranteed performance`. Operator owns baseline update cadence +
> threshold tuning.

## 1. Source of Truth

| File | Role |
|---|---|
| [`performance-scenario-catalog.v1.json`](performance-scenario-catalog.v1.json) | Canonical scenario list (id, test_module, workflow_id, mode, enforcement) |
| [`performance-regression-threshold.v1.json`](performance-regression-threshold.v1.json) | Threshold policy (advisory enforcement; per-scenario override; global defaults) |
| [`baseline.v1.json`](baseline.v1.json) | Generated baseline (mode-filtered; `candidate_baseline: true`) |
| [`../../ao_kernel/defaults/schemas/performance-scenario-catalog.schema.v1.json`](../../ao_kernel/defaults/schemas/performance-scenario-catalog.schema.v1.json) | Catalog JSON Schema |
| [`../../ao_kernel/defaults/schemas/performance-baseline.schema.v1.json`](../../ao_kernel/defaults/schemas/performance-baseline.schema.v1.json) | Baseline JSON Schema |
| [`../../ao_kernel/defaults/schemas/performance-regression-threshold.schema.v1.json`](../../ao_kernel/defaults/schemas/performance-regression-threshold.schema.v1.json) | Threshold JSON Schema |
| [`../../scripts/promote_baseline.py`](../../scripts/promote_baseline.py) | Deterministic catalog-join baseline promoter |

## 2. Scenario Catalog

The catalog is the **source-of-truth for workflow_id** — the existing
benchmark scorecard does not carry workflow_id, so the script joins
catalog entries to scorecard rows by `source_scorecard_scenario`.

| id | mode | enforcement | source_scorecard_scenario | workflow_id |
|---|---|---|---|---|
| `governed_review` | fast | policy_threshold | governed_review | review_ai_flow |
| `governed_bugfix` | fast | policy_threshold | governed_bugfix | governed_bugfix_bench |
| `full_mode_smoke` | full | advisory_only | governed_review | review_ai_flow |

## 3. Baseline Generation Rule (mode + enforcement filter)

Codex 019e8410 absorb:

- **Include** in baseline: catalog entries where `mode == --benchmark-mode`
  AND `enforcement == "policy_threshold"`
- **Skip** from baseline: entries where `enforcement == "advisory_only"`
  OR `mode != --benchmark-mode`

For the committed `--benchmark-mode fast` baseline this yields 2 entries
(`governed_review` + `governed_bugfix`); `full_mode_smoke` is
intentionally skipped because its enforcement is advisory-only and its
mode is `full`.

### Empty selection policy

If the filter yields zero scenarios, `promote_baseline.py` exits 2
("nothing to promote for this mode"). The `--allow-empty` flag opts into
writing an empty baseline (operator-managed advanced workflows). The
E-7a committed fast baseline always has ≥1 entry per the catalog.

## 4. Threshold Policy (advisory enforcement)

| Field | Value | Notes |
|---|---|---|
| `enforcement_mode` | `advisory` | E-7a is policy definition only; CI red is future E-7x |
| `global_defaults.warn_threshold_pct` | `20.0` | Conservative; matches existing repo scorecard default |
| `global_defaults.hard_fail_threshold_pct` | `30.0` | Conservative; matches existing repo scorecard default |
| Per-scenario override | per-scenario | `enforcement_override: "advisory_only"` for `full_mode_smoke` |

> **Threshold defaults rationale.** Codex 019e8410 absorb: a 10%/5%
> threshold pair is too aggressive against single-run CI samples and
> would generate flaky false positives. The 20%/30% pair matches the
> existing repo scorecard policy default and acknowledges variance via
> `variance_disclaimer`. Future tightening requires repeated sampling
> (E-7h slice).

## 5. Promote Workflow (operator command)

```bash
python scripts/promote_baseline.py \
    --scorecard benchmark_scorecard.v1.json \
    --scenario-catalog docs/performance/performance-scenario-catalog.v1.json \
    --out docs/performance/baseline.v1.json \
    --source-git-sha "$(git rev-parse --short HEAD)" \
    --source-git-ref refs/heads/main \
    --benchmark-mode fast \
    --python-version 3.13 \
    --runner-os ubuntu-latest \
    --generated-at "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
```

Operator-only opt-in flags:

- `--allow-empty` — permit empty baseline (advanced)
- `--dry-run` — render JSON to stdout without writing the output file

**Determinism:** `--generated-at` is required; the script never reads
the wall clock. Same input + same `--generated-at` → byte-equal output.

## 6. Update Cadence (operator-owned)

The committed baseline is a **single-run candidate** snapshot. Operator
update cadence:

- **Quarterly review** recommended (operator-owned schedule)
- **Re-promote** after major dependency upgrade (Python, jsonschema,
  tenacity, runtime libs)
- **Re-promote** after benchmark scorecard schema bump
- **Do NOT auto-update on every main commit** — staleness disclosure
  is preferred over auto-promotion (avoids hidden drift)

The `generated_from` block makes baseline age visible
(`generated_at` + `source_git_sha`). Operators decide when staleness
warrants a refresh; CI does **not** fail on baseline staleness.

## 7. Regression Investigation Runbook

When a head benchmark exceeds `warn_threshold_pct`:

1. **Confirm the delta**. Pull the head scorecard from the PR's
   `scorecard-${{ github.sha }}` artifact and compare against
   `baseline.v1.json[scenarios][].metric.value`.
2. **Check for flake**. Re-run the workflow once. Single-run baseline
   means variance is normal; a single spike does not imply regression.
3. **Correlate dependencies**. Recent `pyproject.toml`, lockfile, or
   runtime adapter change?
4. **Inspect OTEL traces** (if E-5-1 is wired) for slowdown attribution.
5. **Operator decision**: promote new baseline, accept regression with
   ADR, or revert offending PR.

When a head benchmark exceeds `hard_fail_threshold_pct`:

- E-7a `enforcement_mode: advisory`: warning only; no CI red.
- Future E-7x `enforcement_mode: ci_block_candidate`: PR blocked until
  fix or baseline promotion.

## 8. Out of Scope (E-7 follow-up slices)

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

## 9. Wording Discipline

Forbidden in this package (claim scanner enforced):

- `we guarantee X ms`
- `production SLA`
- `contractual SLA`
- `guaranteed performance`

Allowed (machine-result wording):

- `regression detected`
- `warn threshold exceeded`
- `policy threshold breach`
- `candidate baseline updated`
- `single-run candidate baseline`
- `not SLA` / `not_sla` (schema field name + disclaimer)

The phrases `not SLA` and `not_sla` are explicitly **allowed** because
they are negation disclaimers (Codex 019e8410 absorb).

## 10. References

- V5 roadmap: [`../../.claude/plans/V5-FULL-PRODUCTION-PROMOTION-ROADMAP.md`](../../.claude/plans/V5-FULL-PRODUCTION-PROMOTION-ROADMAP.md)
- Existing benchmark suite: `tests/benchmarks/` (PR-B7 v3.5/v3.7)
- Existing scorecard schema: `ao_kernel/defaults/schemas/scorecard.schema.v1.json` (ZERO TOUCH)
- Existing scorecard schema test: `tests/test_scorecard_schema.py` (ZERO TOUCH)
- E-5-1 OTEL tunables: PR #791 MERGED
- E-5-4 SLI/SLO catalog: PR #799 MERGED
- HARD RULE Cross-AI Peer Review (2026-05-05, 2026-05-14)
- HARD RULE Uzun Vadeli Kalıcı Çözüm (2026-05-27)
- Codex cross-AI plan-time AGREE: thread `019e8410` (4 iters: REVISE/REVISE/REVISE/AGREE)
