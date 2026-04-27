# GPP-2n - Protected Workflow Evidence

**Status:** closeout candidate
**Date:** 2026-04-28
**Authority:** `origin/main` at `ac5a128`
**Issue:** [#523](https://github.com/Halildeu/ao-kernel/issues/523)
**Branch:** `codex/gpp-2n-protected-workflow-evidence`
**Worktree:** `/Users/halilkocoglu/Documents/ao-kernel-gpp-2n-protected-workflow-evidence`
**Program head:** `GPP-2` protected workflow evidence collected fail-closed
**Support impact:** none
**Runtime impact:** protected workflow dispatch only; no live adapter call

## 1. Purpose

Collect the first protected workflow evidence after GPP-2m bound
`.github/workflows/live-adapter-gate.yml` to `ao-kernel-live-adapter-gate`.

Decision:

```text
protected_workflow_evidence_fail_closed_policy_response_missing
```

This slice dispatches the manual workflow from `main`, observes the protected
environment gate, and records the result. It does not invoke `claude`, does not
reference `secrets.AO_CLAUDE_CODE_CLI_AUTH`, does not read secret values, does
not widen support, and does not claim production-platform readiness.

## 2. Dispatch Evidence

Startup checks:

```bash
git status --short --branch
# ## main...origin/main

git rev-list --left-right --count HEAD...origin/main
# 0 0

bash .claude/scripts/ops.sh preflight
# Preflight clean

python3 scripts/gpp_next.py
# Current WP: GPP-2 - Protected Live-Adapter Gate Runtime Binding
# Current status: bound
# Support widening allowed: false
# Production platform claim allowed: false
# Live adapter execution allowed: false
```

Workflow dispatch:

```bash
gh workflow run 'Live Adapter Gate' \
  --repo Halildeu/ao-kernel \
  --ref main \
  -f reason='GPP-2n protected workflow evidence collection; no live adapter execution' \
  -f target_ref=main \
  -f adapter_lane=claude-code-cli
```

Run metadata:

```text
run_id: 25020015357
run_url: https://github.com/Halildeu/ao-kernel/actions/runs/25020015357
workflow_name: Live Adapter Gate
event: workflow_dispatch
head_sha: ac5a1282348cfa2d1a7cfedba3a3f48a5f3f178d
created_at: 2026-04-27T21:16:59Z
environment: ao-kernel-live-adapter-gate
job_id: 73277880393
job_name: live-adapter-gate-contract
```

Initial protected-gate observation:

```text
run_status: waiting
run_conclusion: none
job_status: waiting
job_conclusion: none
job_steps: []
deployment_id: 4503862042
deployment_statuses: waiting, waiting
pending_deployment_environment: ao-kernel-live-adapter-gate
pending_deployment_current_user_can_approve: false
pending_deployment_reviewers: []
artifact_download: no valid artifacts found to download
```

Bounded observation after roughly two minutes:

```text
run_status: waiting
job_status: waiting
job_steps: []
updated_at: 2026-04-27T21:17:02Z
```

Cleanup:

```bash
gh run cancel 25020015357 --repo Halildeu/ao-kernel
```

Final run state after cancellation:

```text
run_status: completed
run_conclusion: cancelled
job_status: completed
job_conclusion: cancelled
job_completed_at: 2026-04-27T21:19:59Z
run_updated_at: 2026-04-27T21:20:04Z
deployment_statuses: error, waiting, waiting
```

## 3. Interpretation

The protected workflow binding is active: GitHub created a deployment for
`ao-kernel-live-adapter-gate` and held the job before any workflow step ran.
Because no deployment protection app approval arrived, the job remained
`waiting`, no artifacts were produced, and the current user could not manually
approve it through the pending deployment API.

This is correct fail-closed behavior. It proves the protected environment is
on the execution path and that the workflow does not fall through to unguarded
execution.

It is not sufficient runtime evidence for GPP-2 completion because:

1. no app approval, denial, or policy explanation was returned;
2. no workflow step executed;
3. no `live-adapter-gate-*.json` artifacts were produced;
4. no `claude-code-cli` preflight ran;
5. no live adapter ran.

## 4. Current Decision

`GPP-2` is blocked again, but for a narrower reason than before.

Resolved:

1. protected environment exists;
2. admin bypass is disabled;
3. branch policy includes `main`;
4. deployment protection app rule is attached and enabled;
5. `AO_CLAUDE_CODE_CLI_AUTH` exists as an environment secret handle;
6. workflow is bound to `ao-kernel-live-adapter-gate`;
7. workflow dispatch reaches the protected environment gate.

Blocked:

1. the deployment protection app/policy service did not return a decision;
2. protected workflow artifacts were not produced;
3. live adapter execution remains disabled.

Still closed:

1. `live_execution_allowed=false`;
2. `support_widening=false`;
3. `production_platform_claim=false`.

## 5. Next Required Action

Activate or configure the `ao-kernel-live-adapter-gate` GitHub App deployment
protection policy service so it handles protected deployment callbacks and
returns an explicit approve, deny, timeout, or failure result.

If that service is repo-owned, it must be implemented through a dedicated
issue, branch, PR, and evidence record. If it is external/admin-owned, record
the external action and rerun protected workflow evidence after it is active.

Do not repeatedly dispatch the protected workflow until the policy service is
expected to respond. Repeated waiting runs add noise but no new evidence.

## 6. Validation

```bash
python3 -m json.tool .claude/plans/gpp_status.v1.json
pytest -q tests/test_gpp_next.py
python3 scripts/gpp_next.py
python3 scripts/live_adapter_gate_attest.py --artifact-path /tmp/gpp-2n-attestation.json --output text
git diff --check
```

Expected closeout decision:

```text
protected_workflow_evidence_fail_closed_policy_response_missing
```

Recorded closeout decision:

```text
protected_workflow_evidence_fail_closed_policy_response_missing
```
