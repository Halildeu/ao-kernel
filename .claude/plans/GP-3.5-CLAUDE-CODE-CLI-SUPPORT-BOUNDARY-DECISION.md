# GP-3.5 — Claude Code CLI Support-Boundary Decision

**Status:** Completed decision
**Date:** 2026-04-24
**Tracker:** [#396](https://github.com/Halildeu/ao-kernel/issues/396)
**Parent tracker:** [#386](https://github.com/Halildeu/ao-kernel/issues/386)
**Lane:** `claude-code-cli` read-only governed workflow

## Purpose

Decide whether the `claude-code-cli` governed read-only lane can move from
`Beta (operator-managed)` to a production-certified read-only support claim
after `GP-3.1` through `GP-3.4`.

## Verdict

**Decision:** `keep_operator_beta`

The lane is useful, evidence-backed, and fail-closed enough for
operator-managed beta usage, but it is not promoted to
production-certified read-only support in this gate.

## Decision Inputs

| Gate | Result | Promotion impact |
|---|---|---|
| `GP-3.1` prerequisite truth | preflight and workflow smoke passed | positive, but environment-specific |
| `GP-3.2` repeatability | three independent governed workflow smoke runs passed | positive, but still operator-environment bound |
| `GP-3.3` failure-mode matrix | missing binary/auth/prompt/timeout/malformed output/policy deny paths classified fail-closed | positive |
| `GP-3.4` evidence completeness | event order, artifact contents, schema, redaction, and live smoke evidence recorded | positive |
| Known bugs | `KB-001` and `KB-002` remain open for the lane | blocks production-certified support |
| CI feasibility | live `claude-code-cli` execution is not CI-managed | blocks production-certified support |
| Cost/usage evidence | adapter-path `cost_usd` / token usage remains explicit non-claim | blocks broader production claim |

## Fresh Evidence

Preflight command:

```bash
python3 scripts/claude_code_cli_smoke.py --output json --timeout-seconds 30
```

Result:

1. exit code `0`
2. `overall_status="pass"`
3. `binary_path="/Users/halilkocoglu/.nvm/versions/node/v22.22.2/bin/claude"`
4. `claude --version`: `2.1.87 (Claude Code)`
5. `auth_status`: `loggedIn=True`, `authMethod="claude.ai"`
6. `prompt_access`: pass
7. `manifest_invocation`: pass
8. `api_key_env_present=false`

Governed workflow command:

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
| run id | `25af3707-9f8b-497f-bdb1-32cd82e7cd52` |
| `event_order` | pass |
| `review_findings_schema` | pass |
| `review_findings_contents` | pass |
| adapter log redaction leaks | `[]` |

The helper used `--cleanup`; checks were evaluated before the temporary
workspace was removed.

## Why Not Promote

`promote_read_only` is rejected for this gate.

1. The lane depends on an external `claude` PATH binary, local Claude Code
   session auth, and real prompt access that cannot be guaranteed by the
   package itself.
2. `KB-001` remains open: `claude auth status` may be green while real
   `claude -p` prompt access is blocked. The helper catches this, but the
   existence of the bug keeps the lane operator-managed.
3. `KB-002` remains open: long-lived token fallback has shown invalid bearer
   token behavior. Session auth remains the supported operator path.
4. CI does not run a live `claude-code-cli` governed workflow because it would
   require external account state. Production-certified support needs either a
   CI-managed live-adapter gate or an explicit release-gate equivalent.
5. Adapter-path `cost_usd` and token usage completeness remain outside this
   lane's public support claim.

`defer` is also rejected. The lane has enough evidence to stay documented and
usable as operator-managed beta: current preflight passes, governed workflow
smoke passes, repeatability exists, failure modes are classified, and evidence
checks are behavior-tested.

## Support Boundary Impact

No support boundary widening.

Current tier after this decision:

1. `claude-code-cli`: `Beta (operator-managed)`
2. production-certified read-only: not granted
3. stable shipped baseline: unchanged
4. default shipped demo: `review_ai_flow + codex-stub`

Operator usage remains valid only when the authoritative helpers pass:

```bash
python3 scripts/claude_code_cli_smoke.py --output text --timeout-seconds 30
python3 scripts/claude_code_cli_workflow_smoke.py --output text --timeout-seconds 60
```

## Next Gate

`GP-3.6` should close the GP-3 parent program with one of two outcomes:

1. close the program with `claude-code-cli` retained as operator-managed beta;
2. open a new, explicitly scoped promotion lane only if the missing
   CI-managed/release-gate live adapter contract is designed first.

No runtime slice should infer production-certified support from this decision.
