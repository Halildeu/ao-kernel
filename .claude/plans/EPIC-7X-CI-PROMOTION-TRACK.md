# V5 Epic 7x: CI Required-Check Promotion Track

> **Cross-AI plan-time AGREE** — Codex thread `019e84b7` (2 iters: REVISE → AGREE)
> **Implementer:** Anthropic Claude / **Reviewer:** OpenAI Codex
> **Implementation kickoff gate:** PR #805 (E-7a) merged ✅ (main commit 505885b)
> **Risk class:** conservative low-risk (schemas/script/tests; no workflow flip)

## 1. Scope

Tooling for the future `advisory → manual_block → ci_block_candidate`
enforcement promotion. **E-7x-1 + E-7x-2 only:** policy-aware regression
comparison module + thin CLI gate. **E-7x-3 (workflow `continue-on-error: false`
flip) is a separate governance PR.**

**In scope:**
- `regression-comparison-result.schema.v1.json` (replay-ready evidence)
- `ao_kernel/_internal/scorecard/regression.py` (policy-aware wrapper; reuses compare.py)
- `scripts/regression_gate.py` (thin CLI; ≤80 LOC body; policy-driven exit)
- `tests/test_regression_gate.py` (33 invariants)

**Out of scope (ZERO TOUCH):**
- `.github/workflows/test.yml` (scorecard job remains `continue-on-error: true`)
- `tests/test_scorecard_schema.py`, `ao_kernel/defaults/schemas/scorecard.schema.v1.json`
- `ao_kernel/_internal/scorecard/compare.py` (read-only reuse target)
- E-7a artifacts (`docs/performance/*`) — read-only consumers
- `tests/benchmarks/*` (existing PR-B7 suite)

## 2. Codex Iter Chain

### iter-1 plan-time REVISE — 5 BLOCKER

| ID | Issue | Resolution |
|---|---|---|
| F1 checkout_drift | E-7a (#805) not yet merged; worktree lacks baseline | Implementation deferred until PR #805 merge → resolved 2026-06-01 |
| F2 exit_semantics | Policy-driven exit semantics needed | advisory=0; manual_block=1 on hard_fail; ci_block_candidate=1 on warn+hard_fail; --strict-mode override |
| F3 metric_direction | pct_change only correct for higher_is_worse | Direction enum + edge cases (baseline_zero, missing, unit_mismatch, non-numeric → skip with reason codes) |
| F4 schema_under_specified | Result artifact missing replay/audit fields | 12 compared_from fields + counts + claim_boundary 4 const true |
| F5 module_boundary | Don't duplicate compare.py | regression.py imports compare.py; gate script is thin CLI |

### iter-2 absorb AGREE + ready_for_impl:false_until_805_merged + must_close_findings:[]

2 implementation-time pins (now enforced):
- Unknown `enforcement_mode` is fail-closed (ValueError) — never silently exit 0
- `skip_reason` is single canonical nullable enum (not duplicated in `reasons[]`)

## 3. Implementation Artifacts

| File | LOC | Purpose |
|---|---|---|
| `ao_kernel/defaults/schemas/regression-comparison-result.schema.v1.json` | ~145 | Draft 2020-12 schema |
| `ao_kernel/_internal/scorecard/regression.py` | ~280 | Policy-aware wrapper module |
| `scripts/regression_gate.py` | ~85 | Thin CLI |
| `tests/test_regression_gate.py` | ~430 | 33 invariants |
| `.claude/plans/EPIC-7X-CI-PROMOTION-TRACK.md` | this | Plan + Codex chain |

## 4. Exit Semantics Matrix

| enforcement_mode | warn | hard_fail | --advisory-mode | --strict-mode |
|---|---|---|---|---|
| `advisory` | 0 | 0 | 0 | 1 on warn+hard_fail |
| `manual_block` | 0 | 1 | 0 | 1 on warn+hard_fail |
| `ci_block_candidate` | 1 | 1 | 0 | 1 on warn+hard_fail |

`--strict-mode` emits stderr banner: "operator-local only; NOT CI required-check evidence."

## 5. Metric Direction + Skip Reason Codes

| Direction | pct_change formula |
|---|---|
| `higher_is_worse` | `(head - baseline) / baseline * 100` |
| `lower_is_worse` | `(baseline - head) / baseline * 100` |

Negative pct_change → `status="pass"` + `is_improvement=true`.

Skip reason enum (8 codes): `missing_baseline`, `missing_head`, `advisory_only`,
`mode_mismatch`, `baseline_zero`, `missing_baseline_value`, `unit_mismatch`,
`invalid_metric_type`.

## 6. Test Sections (33 invariants)

| Section | Count | Focus |
|---|---|---|
| 1. Schema validity | 6 | Draft 2020-12 + additionalProperties + const pins + 8-enum skip_reason |
| 2. Schema negative | 3 | Reject guard flip + unknown status + unknown enforcement |
| 3. Comparison logic | 5 | warn + hard_fail + improvement + missing_head + observed_extra |
| 4. Exit semantics | 4 | advisory/manual_block/ci_block_candidate + strict override |
| 5. Fail-closed enforcement | 2 | Unknown mode → ValueError; unknown override → ValueError |
| 6. Catalog filter | 3 | full_mode_smoke skipped; benchmark_mode recorded; enforcement_mode_resolved recorded |
| 7. Module boundary | 3 | regression.py imports compare.py; thin CLI ≤200 LOC; script imports module |
| 8. Provenance | 3 | 4×SHA256 recorded + generated_at + counts consistency |
| 9. CLI E2E | 2 | Exit 0 no regression; --strict-mode banner + exit 1 on warn |
| 10. Governance | 2 | No .github/workflows + compare.py untouched |

## 7. Out-of-scope follow-up slices (5)

| ID | Slice |
|---|---|
| E-7x-3 | Workflow `continue-on-error: false` flip (governance PR) |
| E-7x-4 | enforcement_mode governance transition gate (advisory → manual_block → ci_block_candidate; operator-approved) |
| E-7x-5 | compare.py `>=` vs `>` semantic fix |
| E-7x-6 | PR comment poster (result → GitHub comment) |
| E-7x-7 | Multi-baseline trend comparison |

## 8. References

- E-7a baseline + threshold: PR #805 MERGED (main commit 505885b)
- Existing compare.py: `ao_kernel/_internal/scorecard/compare.py` (read-only reuse)
- HARD RULE Cross-AI Peer Review (2026-05-05, 2026-05-14)
- HARD RULE Uzun Vadeli Kalıcı Çözüm (2026-05-27)
- Codex thread `019e84b7` (2-iter REVISE → AGREE)
