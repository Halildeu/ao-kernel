# GPP-2g - GitHub-Native Release Authority and Claude MCP Consultation

**Issue:** [#493](https://github.com/Halildeu/ao-kernel/issues/493)
**Date:** 2026-04-26
**Program head:** `GPP-2` remains blocked
**Decision:** `github_native_release_authority_selected_claude_mcp_advisory`
**Support impact:** none
**Runtime impact:** none

## Purpose

This record closes the ambiguity between two separate controls:

1. the independent release authority required to unlock protected live-adapter
   credentials; and
2. the advisory Claude Code + ao-kernel MCP consultation path used when a
   roadmap-first-stage decision or review/fix loop needs an external
   architecture reviewer.

These controls are not interchangeable. Claude/MCP consultation can recommend
or challenge a plan, but it cannot approve live adapter credentials, release
gates, support widening, or production-platform claims.

## Decision

The first independent release gate model for `GPP-2` is:

```text
GitHub-native release authority
```

The required release authority is a GitHub environment required reviewer or
team on `ao-kernel-live-adapter-gate`, with self-review prevented or controlled
by an equivalent future mechanism. The reviewer/team represents release
authority. It is not an application end-user account.

The alternate models from `GPP-2f` stay valid fallback options:

1. GitHub App deployment protection rule;
2. OIDC-backed external secret broker.

They are not selected for the first provisioning path because they add more
infrastructure before the current blocked gate has even proven the basic
environment reviewer and credential-handle contract.

## Current Blocking State

`GPP-2` remains blocked after this record.

The protected environment is partially provisioned:

1. `ao-kernel-live-adapter-gate` exists.
2. Admin bypass is disabled.
3. Deployment branch policy is restricted to `main`.

The gate still lacks:

1. required reviewer/team protection with self-review prevention or equivalent
   control;
2. `AO_CLAUDE_CODE_CLI_AUTH` as an environment secret handle;
3. a fresh `scripts/live_adapter_gate_attest.py` artifact with all checks
   passing.

## Claude MCP Consultation Protocol

Claude Code may be used as an advisory reviewer through the ao-kernel MCP
server only under the following trigger conditions:

1. roadmap first-stage plan validation before starting a new major GPP work
   package;
2. post-implementation review returns `RED` or a ship-blocking architecture
   disagreement;
3. the same review loop reaches three or more `REVISE` iterations without
   convergence;
4. a GPP governance, protected-gate, support-boundary, or production-claim
   decision needs a second architecture opinion;
5. a review fix would exceed the approved WP scope and needs an explicit
   split/defer decision.

The consultation path is advisory only. It must not:

1. mutate repo state;
2. write ao-kernel memory or canonical decisions;
3. read, print, transform, or validate secret values;
4. approve `AO_CLAUDE_CODE_CLI_AUTH` handling;
5. approve `--equivalent-release-gate-approved`;
6. widen support;
7. authorize production-platform claims;
8. replace GitHub required reviewers, deployment protection, or external secret
   broker controls.

## Allowed MCP Surface

Default allowed tools for Claude/MCP consultation:

1. `mcp__ao-kernel__ao_workspace_status`;
2. `mcp__ao-kernel__ao_policy_check`;
3. `mcp__ao-kernel__ao_quality_gate`;
4. `mcp__ao-kernel__ao_memory_read`, only for read-only context retrieval;
5. `mcp__ao-kernel__ao_llm_route`, only in dry-run or non-mutating analysis
   mode if needed by a future explicit consultation contract.

Forbidden tools and behaviors:

1. `mcp__ao-kernel__ao_memory_write`;
2. `mcp__ao-kernel__ao_llm_call`;
3. any MCP or built-in tool invocation that writes files, opens PRs, changes
   GitHub settings, writes secrets, or mutates canonical program state;
4. any prompt or tool payload containing credential material.

Claude Code built-in tools must be constrained by the operator command for
consultation runs. A future helper may automate this, but until then the
operator must not treat a broad Claude Code session as an MCP-only consultation.

## Reference Command Shape

The minimum safe command shape is:

```bash
claude -p \
  --strict-mcp-config \
  --allowedTools mcp__ao-kernel__ao_workspace_status,mcp__ao-kernel__ao_policy_check,mcp__ao-kernel__ao_quality_gate \
  --mcp-config '{"mcpServers":{"ao-kernel":{"command":"python3","args":["-m","ao_kernel","mcp","serve"]}}}' \
  -- '<read-only consultation prompt>'
```

If `ao_memory_read` is required, add it explicitly and record why in the issue
or PR summary. Do not add `ao_memory_write` or `ao_llm_call`.

## Next Provisioning Step

The next admin/provisioning action stays external to this PR:

1. configure GitHub-native required reviewer/team protection on
   `ao-kernel-live-adapter-gate`;
2. set `AO_CLAUDE_CODE_CLI_AUTH` under that environment without reading back
   the secret value;
3. run `scripts/live_adapter_gate_attest.py` and require all checks to pass
   before `GPP-2` runtime binding starts.

## Exit State

This slice closes as
`github_native_release_authority_selected_claude_mcp_advisory_no_support_widening`.

It selects the first release-gate model and records the consultation protocol.
It does not unblock `GPP-2`, does not run a live adapter, does not change
secrets, and does not widen support.
