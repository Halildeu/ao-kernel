# GP-5.4a — Governed Read-Only Workflow Rehearsal

**Issue:** [#441](https://github.com/Halildeu/ao-kernel/issues/441)
**Parent tracker:** [#424](https://github.com/Halildeu/ao-kernel/issues/424)
**Status:** closeout candidate

## Purpose

Run the first governed read-only workflow rehearsal without widening production
support. The slice verifies that repo-intelligence-shaped context can be
supplied only as explicit operator-visible input while the shipped workflow
path remains `review_ai_flow + codex-stub`.

## Scope Boundary

Included:

1. deterministic repo-intelligence Markdown handoff fixture;
2. wheel-installed temporary virtualenv execution;
3. `examples/demo_review.py --intent-file <handoff>` workflow run;
4. schema-backed machine-readable rehearsal report;
5. tests for the report contract and fail-closed decision behavior.

Excluded:

1. production-certified real adapter promotion;
2. `context_compiler` auto-feed;
3. MCP repo-intelligence tool;
4. root export;
5. remote side effects or write-side patch application.

## Decision

`pass_read_only_rehearsal_no_support_widening`

The rehearsal may pass only when the wheel-installed demo reaches
`final_state=completed`. A pass does not promote repo intelligence, `codex-stub`,
or the governed workflow to production-certified general-purpose automation.

## Evidence Contract

Command:

```bash
python3 scripts/gp5_read_only_rehearsal.py --output json
```

The command emits `gp5_read_only_workflow_rehearsal_report` validated by
`gp5-read-only-rehearsal-report.schema.v1.json`.

Required report facts:

1. `support_widening=false`;
2. `repo_intelligence_handoff.mode=explicit_operator_markdown`;
3. `hidden_injection=false`;
4. `mcp_tool_used=false`;
5. `root_export_used=false`;
6. `context_compiler_auto_feed=false`;
7. `workflow_rehearsal.execution_mode=wheel_installed_temp_venv`;
8. `workflow_rehearsal.final_state=completed`;
9. `workflow_rehearsal.remote_side_effects=false`.

## Limitations

The repo-intelligence handoff is a deterministic contract fixture, not a live
vector retrieval run. It proves the explicit handoff boundary and workflow
execution path together, not semantic correctness of arbitrary repo retrieval.

For that reason the report records a `repo_query_command_contract` rather than
claiming that live `repo query` was executed in this slice.

The adapter remains `codex-stub`. This is still not a production real-adapter
support claim.

## Next Gate

After GP-5.4a, the next unblocked slice is `GP-5.5a` controlled patch/test
design. `GP-5.1b` remains blocked until protected live-adapter gate attestation
exists.
