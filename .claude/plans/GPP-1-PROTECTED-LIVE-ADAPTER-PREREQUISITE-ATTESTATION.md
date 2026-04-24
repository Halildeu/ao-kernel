# GPP-1 - Protected Live-Adapter Prerequisite Attestation

**Status:** closeout candidate
**Date:** 2026-04-25
**Parent tracker:** [#470](https://github.com/Halildeu/ao-kernel/issues/470)
**Slice issue:** [#472](https://github.com/Halildeu/ao-kernel/issues/472)
**Branch:** `codex/gpp1-live-adapter-prereq-attestation`
**Worktree:** `/Users/halilkocoglu/Documents/ao-kernel-gpp1-live-adapter-prereq-attestation`
**Base authority:** `origin/main` at `f3823be`
**Decision:** `blocked_attestation_missing`
**Support impact:** none
**Release impact:** none

## 1. Purpose

Attest whether the project-owned protected live-adapter prerequisites exist
before `ao-kernel` binds the live adapter workflow to protected credentials or
promotes `claude-code-cli` beyond `Beta (operator-managed)`.

This slice is deliberately no-widening. It does not create GitHub secrets, read
secret values, bind a workflow environment, run `claude`, or claim production
real-adapter support.

## 2. Required Prerequisites

| Prerequisite | Required value | Status |
|---|---|---|
| Protected GitHub environment | `ao-kernel-live-adapter-gate` | Not attested |
| Project-owned credential handle | `AO_CLAUDE_CODE_CLI_AUTH` | Not attested |
| Fork-safe trigger path | no fork-triggered live secret access | Current design-only workflow remains safe |
| Live workflow binding | only after prerequisite attestation | Blocked |

## 3. Live Evidence

Commands were run from `origin/main`/GPP-1 branch state on 2026-04-25.

### GitHub Environments

Command:

```bash
gh api repos/Halildeu/ao-kernel/environments \
  --jq '.environments[]? | {name, protection_rules: (.protection_rules|length), deployment_branch_policy}'
```

Observed output:

```json
{"deployment_branch_policy":null,"name":"pypi","protection_rules":0}
```

Decision: the required environment `ao-kernel-live-adapter-gate` is not
present.

### Repository Secrets

Command:

```bash
gh secret list --repo Halildeu/ao-kernel
```

Observed output: empty.

Decision: the required repository secret handle `AO_CLAUDE_CODE_CLI_AUTH` is not
attested.

### Environment Secrets

Command:

```bash
gh secret list --env ao-kernel-live-adapter-gate --repo Halildeu/ao-kernel
```

Observed output:

```text
failed to get secrets: HTTP 404: Not Found
```

Decision: the required environment does not exist, so environment-scoped secret
attestation is also absent.

### Workflow Safety Inspection

Command:

```bash
rg -n "environment:|secrets\.|pull_request_target|pull_request|workflow_dispatch|AO_CLAUDE_CODE_CLI_AUTH|ao-kernel-live-adapter-gate" \
  .github/workflows/live-adapter-gate.yml
```

Observed output:

```text
4:  workflow_dispatch:
```

Decision: the current workflow is still manual/design-only. It does not bind a
GitHub environment, does not reference secrets, and does not run on pull request
events.

### Existing Schema-Backed Gate Contract

Command:

```bash
python3 scripts/live_adapter_gate_contract.py \
  --output json \
  --report-path /tmp/gpp1-live-adapter-gate-contract.v1.json \
  --evidence-path /tmp/gpp1-live-adapter-gate-evidence.v1.json \
  --environment-contract-path /tmp/gpp1-live-adapter-gate-environment-contract.v1.json \
  --rehearsal-decision-path /tmp/gpp1-live-adapter-gate-rehearsal-decision.v1.json \
  --target-ref main \
  --reason gpp1-prerequisite-attestation \
  --requested-by codex \
  --event-name local-attestation \
  --head-sha f3823beb16cb7476312516e5c72140b06dca6965
```

Key observed fields:

```text
environment contract:
overall_status=blocked
finding_code=live_gate_protected_environment_not_attested
live_execution_allowed=False
support_widening=False
protected_environment.name=ao-kernel-live-adapter-gate
required_secrets=AO_CLAUDE_CODE_CLI_AUTH

rehearsal decision:
overall_status=blocked
finding_code=live_gate_rehearsal_blocked_missing_protected_prerequisites
live_execution_allowed=False
live_rehearsal_attempted=False
support_widening=False
prerequisites=protected_environment_attestation:not_attested,project_owned_credential:not_attested,protected_live_preflight:blocked,governed_workflow_smoke:blocked
```

Decision: existing machine-readable contract already models the correct blocked
state; GPP-1 records the current live attestation result rather than adding a
new runtime helper.

## 4. Exit Decision

`GPP-1` exits as:

```text
blocked_attestation_missing
```

Reasons:

1. Required protected environment `ao-kernel-live-adapter-gate` is absent.
2. Required credential handle `AO_CLAUDE_CODE_CLI_AUTH` is not attested at
   repository scope.
3. Environment-scoped secret attestation cannot exist because the environment
   itself returns `404`.
4. The live-adapter workflow is still design-only and intentionally has no
   secret or environment binding.

## 5. Support Boundary

No support widening.

`ao-kernel` remains a narrow stable governed runtime. `claude-code-cli` remains
`Beta (operator-managed)`. A green `live-adapter-gate` workflow still means
blocked/design-only artifacts were emitted, not that a project-owned real
adapter ran.

## 6. What Unblocks GPP-2

`GPP-2` must not start until a future operator/admin step provides fresh
attestation that:

1. GitHub environment `ao-kernel-live-adapter-gate` exists.
2. Its protection settings match the protected gate contract.
3. Credential handle `AO_CLAUDE_CODE_CLI_AUTH` or an explicitly approved
   replacement exists at repository or environment scope.
4. Fork-triggered contexts cannot read that credential.

Only after those are true should a new slice bind
`.github/workflows/live-adapter-gate.yml` to the protected environment and
attempt a live protected adapter rehearsal.

## 7. Non-Goals

1. No GitHub environment creation.
2. No repository or environment secret value creation.
3. No secret value readback.
4. No `environment:` workflow binding.
5. No `claude` execution.
6. No production adapter certification.
7. No release, tag, or publish.

## 8. Validation

Local validation for this slice:

1. `git diff --check`
2. `python3 -m ao_kernel version`
3. `python3 -m ao_kernel doctor`
4. `pytest -q tests/test_live_adapter_gate_contract.py tests/test_gp5_platform_claim_decision.py`
5. live GitHub environment inventory command
6. live GitHub secret list command
7. workflow safety grep

