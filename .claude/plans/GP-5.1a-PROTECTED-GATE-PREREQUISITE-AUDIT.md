# GP-5.1a - Protected Gate Prerequisite Audit

**Status:** Closeout candidate
**Date:** 2026-04-24
**Authority:** `origin/main` at `7580303`
**Parent tracker:** [#424](https://github.com/Halildeu/ao-kernel/issues/424)
**Slice issue:** [#429](https://github.com/Halildeu/ao-kernel/issues/429)
**Branch:** `codex/gp5-1a-protected-gate-audit`
**Worktree:** `/Users/halilkocoglu/Documents/ao-kernel-gp5-1a`
**Decision:** `blocked_unattested_keep_operator_beta`

## Purpose

Record the project-owned protected live-adapter gate prerequisites before any
workflow binding, secret usage, live `claude` invocation, or support widening.

This slice answers one narrow question: can the next protected gate slice rely
on an attested GitHub environment and project-owned Claude Code credential
today?

## Scope

1. Inspect current GitHub environment inventory.
2. Inspect whether the required secret handle is attested as metadata.
3. Verify the existing live-adapter gate still emits blocked evidence and does
   not read secrets or run a live adapter.
4. Update the GP-5 roadmap and execution status.

## Non-Goals

1. No GitHub environment creation.
2. No repository or environment secret value creation.
3. No secret value read, print, commit, or storage.
4. No workflow `environment:` binding.
5. No live `claude` / `claude-code-cli` invocation.
6. No support boundary widening.

## Audit Evidence

### GitHub environment inventory

Command:

```bash
gh api repos/Halildeu/ao-kernel/environments \
  --jq '{total_count, environments: [.environments[] | {name, protection_rules, deployment_branch_policy}]}'
```

Observed result:

```json
{
  "total_count": 1,
  "environments": [
    {
      "name": "pypi",
      "protection_rules": [],
      "deployment_branch_policy": null
    }
  ]
}
```

Decision:

| Required environment | Status |
|---|---|
| `ao-kernel-live-adapter-gate` | `absent / not_attested` |

### Secret handle metadata

Repository-level lookup:

```bash
gh secret list --repo Halildeu/ao-kernel --json name,updatedAt \
  --jq '[.[] | select(.name == "AO_CLAUDE_CODE_CLI_AUTH")]'
```

Observed result:

```json
[]
```

Environment-level lookup:

```bash
gh secret list \
  --repo Halildeu/ao-kernel \
  --env ao-kernel-live-adapter-gate \
  --json name,updatedAt \
  --jq '[.[] | select(.name == "AO_CLAUDE_CODE_CLI_AUTH")]'
```

Observed result:

```text
HTTP 404: Not Found
```

Decision:

| Required secret handle | Status |
|---|---|
| `AO_CLAUDE_CODE_CLI_AUTH` repository secret | `absent / not_attested` |
| `AO_CLAUDE_CODE_CLI_AUTH` environment secret | `blocked` because the environment is absent |

### Current workflow safety posture

Current workflow:

```text
.github/workflows/live-adapter-gate.yml
```

Observed properties:

1. trigger is `workflow_dispatch`;
2. no `environment:` binding exists;
3. no `secrets.` references exist;
4. no `pull_request_target` trigger exists;
5. the workflow emits design-only contract artifacts.

### Blocked evidence artifact check

Command:

```bash
python3 scripts/live_adapter_gate_contract.py \
  --output json \
  --report-path /tmp/gp5-1a-live-adapter-gate-contract.v1.json \
  --evidence-path /tmp/gp5-1a-live-adapter-gate-evidence.v1.json \
  --environment-contract-path /tmp/gp5-1a-live-adapter-gate-environment-contract.v1.json \
  --rehearsal-decision-path /tmp/gp5-1a-live-adapter-gate-rehearsal-decision.v1.json \
  --target-ref main \
  --reason gp5-1a-prerequisite-audit \
  --requested-by codex \
  --event-name local-audit \
  --head-sha 7580303f697f7be95321a711fcfc9684531af08a
```

Observed artifact statuses:

| Artifact | Status | Key finding |
|---|---|---|
| `live-adapter-gate-contract.v1.json` | `blocked` | `live_gate_not_implemented` |
| `live-adapter-gate-evidence.v1.json` | `blocked` | `live_gate_protected_environment_not_attested` |
| `live-adapter-gate-environment-contract.v1.json` | `blocked` | `live_gate_protected_environment_not_attested` |
| `live-adapter-gate-rehearsal-decision.v1.json` | `blocked_no_rehearsal` | `live_gate_rehearsal_blocked_missing_protected_prerequisites` |

The blocked artifact path remains the correct behavior. It is not a live
adapter success signal.

## Decision

`GP-5.1a` closes as `blocked_unattested_keep_operator_beta`.

The project cannot start `GP-5.1b` workflow binding yet because the required
environment and credential handle are not attested. The right next action is an
out-of-band repo administration step, not a code change:

1. create or designate protected environment `ao-kernel-live-adapter-gate`;
2. configure required reviewers and branch/ref restrictions;
3. configure project-owned credential handle `AO_CLAUDE_CODE_CLI_AUTH` in that
   environment;
4. provide metadata-only attestation that the environment and handle exist;
5. then open `GP-5.1b` to bind the workflow while preserving blocked semantics
   for missing prerequisites.

## Support Boundary Impact

No support widening.

`claude-code-cli` remains `Beta (operator-managed)`. Local Claude Code auth or
operator smoke success is still not project-owned production-certified support.

## Next Slices

1. `GP-5.3a` can proceed independently: repo-intelligence retrieval evidence
   quality contract.
2. `GP-5.3b` can proceed independently: stdout/manual agent context handoff
   contract.
3. `GP-5.1b` is blocked until protected environment and credential handle
   attestation exists.

## Validation

Required validation for this slice:

1. `git diff --check`
2. `python3 -m ao_kernel doctor`
3. `python3 scripts/live_adapter_gate_contract.py ...`
4. PR CI
