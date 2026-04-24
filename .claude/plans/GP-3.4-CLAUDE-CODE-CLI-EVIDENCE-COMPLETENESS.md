# GP-3.4 — Claude Code CLI Evidence Completeness

**Status:** Completed on main
**Date:** 2026-04-24
**Tracker:** [#394](https://github.com/Halildeu/ao-kernel/issues/394)
**Parent tracker:** [#386](https://github.com/Halildeu/ao-kernel/issues/386)
**Lane:** `claude-code-cli` read-only governed workflow

## Purpose

Close the evidence completeness gate for the `claude-code-cli` read-only
governed workflow lane before any support-boundary promotion decision.

This gate verifies that a successful workflow smoke carries enough audit
surface to be useful: final state, required events, canonical event order,
artifact materialization, artifact schema/content, adapter log presence, and
redaction checks.

## Scope

Included:

1. Event order verification for the canonical governed workflow sequence.
2. Semantic `review_findings` artifact content verification.
3. Adapter log redaction negative coverage.
4. Live smoke proof with the widened evidence check set.
5. Operator-facing runbook wording for the widened evidence checks.
6. Explicit cost/usage non-claim for this lane.

Excluded:

1. No stable support widening.
2. No version bump, tag, or publish.
3. No production-certified support promotion.
4. No CI-required live `claude-code-cli` execution.
5. No adapter-path `cost_usd` public support claim.

## Evidence Checks

The governed workflow smoke now verifies this check set:

| Check | Meaning | Failure code |
|---|---|---|
| `final_state` | workflow record reached `completed` | implicit check detail |
| `evidence_events` | required event kinds exist | `evidence_events_missing` |
| `event_order` | required event kinds appear in canonical order | `evidence_event_order_invalid` |
| `review_findings_artifact` | `review_findings` capability output materialized | `review_findings_artifact_missing` |
| `adapter_log` | adapter log exists and has no secret-like leak | `adapter_log_missing_or_unredacted` |
| `review_findings_schema` | artifact validates against `review-findings.schema.v1.json` | `review_findings_schema_invalid` / `review_findings_artifact_not_json` |
| `review_findings_contents` | artifact has `schema_version`, list `findings`, and non-empty `summary` | `review_findings_contents_invalid` |

## Live Smoke Evidence

Command:

```bash
python3 scripts/claude_code_cli_workflow_smoke.py --output json --timeout-seconds 60 --cleanup
```

Result:

| Field | Value |
|---|---|
| exit code | `0` |
| `overall_status` | `pass` |
| `preflight_status` | `pass` |
| final state | `completed` |
| workflow id | `governed_review_claude_code_cli` |
| run id | `d269c4f7-78d5-4773-b609-a0891513e464` |
| adapter log records | `1` |
| adapter log redaction leaks | `[]` |
| `review_findings.schema_version` | `1` |
| `review_findings.findings_count` | `0` |
| `review_findings.summary_present` | `true` |

The helper used `--cleanup`; checks were evaluated before the temporary
workspace was removed.

## Test Delta

Three behavior assertions were added:

1. successful evidence verification now includes `event_order` and
   `review_findings_contents`;
2. out-of-order required events fail with `evidence_event_order_invalid`;
3. adapter log secret-like output fails with
   `adapter_log_missing_or_unredacted`.

## Validation

```bash
python3 scripts/claude_code_cli_workflow_smoke.py --output json --timeout-seconds 60 --cleanup
python3 -m pytest -q tests/test_claude_code_cli_workflow_smoke.py tests/test_claude_code_cli_smoke.py tests/test_cli_entrypoints.py tests/test_doctor_cmd.py
python3 -m ruff check ao_kernel/real_adapter_workflow_smoke.py tests/test_claude_code_cli_workflow_smoke.py
python3 -m ao_kernel doctor
git diff --check
```

Results:

1. workflow smoke: `overall_status="pass"`, final state `completed`;
2. targeted tests: `26 passed, 1 skipped`;
3. ruff: all checks passed;
4. doctor: `8 OK, 1 WARN, 0 FAIL`;
5. diff check: clean.

## Cost / Usage Non-Claim

This lane does not claim adapter-path `cost_usd` or token usage completeness.
The governed workflow smoke records adapter/evidence correctness only.

Adapter-path cost/usage public support remains outside this promotion lane and
must not be inferred from a passing GP-3.4 smoke.

## Decision

The evidence completeness gate is sufficiently covered to move to `GP-3.5`
support-boundary decision.

This does not promote the lane. It only proves the current smoke evidence is
complete enough for a promotion decision to be evaluated in the next gate.

## Support Boundary Impact

No support boundary widening.

Current support tier remains:

1. `claude-code-cli`: `Beta (operator-managed)`
2. production-certified read-only claim: not yet granted
3. stable shipped baseline: unchanged

## Next Gate

`GP-3.5` should decide one of:

1. `promote_read_only`
2. `keep_operator_beta`
3. `defer`

The decision must reconcile all previous GP-3 gates, docs/support matrix,
runbook wording, known bugs, and CI feasibility.
