# RI-6.4 - Repo Intelligence Read-Only Rehearsal Refresh

**Status:** closeout candidate
**Date:** 2026-04-27
**Authority:** `origin/main` at `f8b634f`
**Issue:** [#507](https://github.com/Halildeu/ao-kernel/issues/507)
**Branch:** `codex/ri6-4-read-only-rehearsal`
**Worktree:** `/Users/halilkocoglu/Documents/ao-kernel-ri6-4-read-only-rehearsal`
**Prior opt-in PR:** [#506](https://github.com/Halildeu/ao-kernel/pull/506)
**Support impact:** none
**Production claim impact:** none
**Runtime impact:** no real adapter execution

## 1. Purpose

Refresh the deterministic read-only repo-intelligence rehearsal so it records
the RI-6.3 explicit workflow opt-in validation result as governed evidence.

The rehearsal chain remains:

```text
deterministic repo query fixture
-> explicit Markdown handoff
-> explicit opt-in validation
-> review_ai_flow with codex-stub
-> review_findings artifact
-> evidence timeline
```

This slice does not add hidden prompt injection, does not expose MCP, does not
feed `context_compiler`, does not perform root export, does not call a real
adapter, and does not widen support.

Expected guard state remains:

```text
support_widening=false
production_platform_claim=false
live_adapter_execution_allowed=false
GPP-2=blocked
```

## 2. Behavior Changes

`scripts/gp5_read_only_rehearsal.py` now validates the generated Markdown
handoff with:

```python
validate_repo_intelligence_workflow_opt_in(...)
```

before running the installed `review_ai_flow + codex-stub` demo.

The rehearsal report now records:

| Evidence | Field |
|---|---|
| Handoff digest | `repo_intelligence_handoff.markdown_sha256` |
| Opt-in validation result | `repo_intelligence_opt_in_validation.status` |
| Source metadata | `repo_intelligence_opt_in_validation.source_metadata` |
| Safety boundary | `repo_intelligence_opt_in_validation.safety` |
| Adapter identity | `workflow_rehearsal.adapter_id=codex-stub` |
| Final workflow state | `workflow_rehearsal.final_state` |
| Review artifact path | `workflow_rehearsal.review_findings_artifact_path` |
| Evidence timeline path | `workflow_rehearsal.evidence_timeline_path` |
| No write-side claim | `workflow_rehearsal.write_side_workflow_support_implied=false` |
| No real adapter | `workflow_rehearsal.real_adapter_called=false` |
| No remote side effect | `workflow_rehearsal.remote_side_effects=false` |

If explicit opt-in validation is not accepted, the rehearsal report becomes:

```text
overall_status=blocked
decision=blocked_read_only_rehearsal_no_support_widening
blocked_reason=repo_intelligence_opt_in_validation_not_accepted
```

## 3. Schema Refresh

The `gp5-read-only-rehearsal-report` schema now requires:

1. `repo_intelligence_opt_in_validation`;
2. `write_side_workflow_support_implied=false`;
3. `real_adapter_called=false`;
4. `review_findings_artifact_path`;
5. `evidence_timeline_path`.

For passing reports, the schema requires accepted opt-in validation, completed
workflow state, and non-empty artifact/timeline paths. For blocked reports,
the demo command may be empty because fail-closed validation can stop before
the workflow is invoked.

## 4. Files Changed

| File | Change |
|---|---|
| `scripts/gp5_read_only_rehearsal.py` | Adds opt-in validation and richer rehearsal evidence fields. |
| `ao_kernel/defaults/schemas/gp5-read-only-rehearsal-report.schema.v1.json` | Requires validation, artifact, timeline, no-real-adapter, and no-write-support fields. |
| `tests/test_gp5_read_only_rehearsal.py` | Covers accepted validation, blocked validation, artifact/timeline parsing, and schema validity. |
| `.claude/plans/RI-6.4-REPO-INTELLIGENCE-READ-ONLY-REHEARSAL.md` | Records this closeout candidate. |

## 5. Validation

Startup and program checks:

```bash
git status --short --branch
git rev-list --left-right --count HEAD...origin/main
bash .claude/scripts/ops.sh preflight
python3 scripts/gpp_next.py
```

Focused tests:

```bash
pytest -q tests/test_gp5_read_only_rehearsal.py
```

Result:

```text
7 passed
```

Related repo-intelligence tests:

```bash
pytest -q tests/test_gp5_read_only_rehearsal.py tests/test_repo_intelligence_workflow_opt_in_contract.py tests/test_repo_intelligence_context_pack_builder.py
```

Result:

```text
23 passed
```

Full-rehearsal aggregation regression:

```bash
pytest -q tests/test_gp5_full_production_rehearsal.py tests/test_gp5_read_only_rehearsal.py
```

Result:

```text
14 passed
```

Real deterministic rehearsal:

```bash
python3 scripts/gp5_read_only_rehearsal.py --output json
```

Observed result:

```text
overall_status=pass
decision=pass_read_only_rehearsal_no_support_widening
repo_intelligence_opt_in_validation.status=accepted
workflow_rehearsal.final_state=completed
workflow_rehearsal.adapter_id=codex-stub
workflow_rehearsal.real_adapter_called=false
workflow_rehearsal.remote_side_effects=false
workflow_rehearsal.write_side_workflow_support_implied=false
```

Static and guard checks:

```bash
python3 -m ruff check scripts/gp5_read_only_rehearsal.py tests/test_gp5_read_only_rehearsal.py
git diff --check
python3 scripts/gpp_next.py
```

## 6. Exit Decision

Decision:

```text
repo_intelligence_read_only_rehearsal_refreshed_no_support_widening
```

Closeout conditions:

| Condition | Status |
|---|---|
| Explicit handoff digest is recorded | satisfied |
| Explicit opt-in validation is recorded | satisfied |
| Adapter identity is recorded | satisfied |
| Review artifact path is recorded | satisfied |
| Evidence timeline path is recorded | satisfied |
| Final workflow state is recorded | satisfied |
| Fail-closed validation rehearsal is covered by tests | satisfied |
| Real adapter execution | not performed |
| Remote side effects | not performed |
| Write-side workflow support implied | not performed |
| Support widening | not performed |
| Production platform claim | not performed |
| Live adapter execution | not performed |
| GPP-2 blocked state | preserved |
