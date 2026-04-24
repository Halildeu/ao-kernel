# GP-3.1 — Claude Code CLI Prerequisite Truth Refresh

**Status:** Completed on `main`
**Date:** 2026-04-24
**Tracker:** [#388](https://github.com/Halildeu/ao-kernel/issues/388)
**Parent tracker:** [#386](https://github.com/Halildeu/ao-kernel/issues/386)
**Lane:** `claude-code-cli` read-only governed workflow

## Purpose

Refresh the current operator-environment truth for the `claude-code-cli` lane
before any production-certified support claim is considered.

This is not a support widening. It only answers whether the local prerequisite
chain is currently available enough to proceed to the next evidence gate.

## Scope

Included:

1. Claude Code binary discovery.
2. Claude Code auth status.
3. Real prompt access smoke.
4. Bundled manifest invocation smoke.
5. Governed read-only workflow smoke.
6. Evidence/artifact materialization checks performed by the smoke helper.

Excluded:

1. No runtime code change.
2. No version bump, tag, or publish.
3. No production-certified support promotion.
4. No `gh-cli-pr` live-write promotion.
5. No general-purpose production platform claim.

## Commands

```bash
python3 scripts/claude_code_cli_smoke.py --output json --timeout-seconds 30
python3 scripts/claude_code_cli_workflow_smoke.py --output json --timeout-seconds 60 --cleanup
```

## Live Evidence

| Check | Result | Notes |
|---|---|---|
| preflight exit code | `0` | helper returned success |
| preflight `overall_status` | `pass` | all prerequisite checks passed |
| binary/version | `pass` | `claude version: 2.1.87 (Claude Code)` |
| auth status | `pass` | logged in via `claude.ai`; API-key env fallback not present |
| prompt access | `pass` | real `claude -p` prompt smoke passed |
| manifest invocation | `pass` | bundled manifest smoke passed |
| workflow exit code | `0` | helper returned success |
| workflow `overall_status` | `pass` | governed read-only workflow smoke passed |
| workflow id | `governed_review_claude_code_cli` | read-only governed review lane |
| workflow run id | `01407154-b7a1-4b44-8b66-6b37a23fd02d` | temp workspace smoke run |
| final state | `completed` | workflow reached completed state |
| evidence events | `pass` | required events present |
| `review_findings` artifact | `pass` | artifact materialized and schema-valid |
| adapter log | `pass` | redacted adapter log present |

The workflow smoke used `--cleanup`; the helper verified the evidence and
artifact checks before cleaning up the temporary workspace.

## Decision

`claude-code-cli` prerequisites are currently available in this operator
environment.

The lane may proceed to `GP-3.2` governed workflow repeatability, but it remains
`Beta (operator-managed)` until later gates prove repeatability, failure-mode
behavior, evidence completeness, docs parity, runbook coverage, and support
boundary fit.

## Support Boundary Impact

No support boundary widening.

Current support tier remains:

1. `claude-code-cli`: `Beta (operator-managed)`
2. production-certified read-only claim: not yet granted
3. stable shipped baseline: unchanged

## Next Gate

`GP-3.2` should prove repeatability instead of relying on one successful smoke.
At minimum it should define and run a bounded repeatability contract for the
governed read-only workflow, then record whether the lane is stable enough to
advance to failure-mode testing.
