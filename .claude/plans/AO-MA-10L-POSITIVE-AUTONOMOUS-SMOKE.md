# AO-MA-10l - Positive Low-Risk Autonomous Merge Smoke

**Status:** implemented fail-closed, blocked in live runtime until the
dedicated non-admin merge actor is active
**Date:** 2026-05-28
**Parent:** AO-MA-10 low-risk autonomous merge lane
**Support impact:** none
**Production platform claim:** false
**Live adapter execution:** false

## Purpose

AO-MA-10l adds the missing end-to-end smoke orchestrator for the low-risk
autonomous merge lane. The orchestrator does not replace release authority. It
only sequences the already recorded authority chain:

```text
AO-MA-10a0 readiness -> AO-MA-10a1 eligibility -> disposable PR ->
required checks -> AO-MA-10c merge-agent
```

AI provider output remains evidence only. The release authority remains the
repo-owned `ao-release-gate` required checks plus the GitHub ruleset.

## Script

```text
scripts/ao_ma10l_autonomous_smoke.py
```

Default mode is read-only. It collects A0/A1 and exits with
`ready_for_smoke_dry_run` only when the live GitHub state is already compatible
with a low-risk autonomous merge smoke.

Execute mode requires:

```text
--execute --confirmation AO-MA-10L-EXECUTE
```

Even in execute mode it stops before any GitHub write when A0/A1 is blocked.

## Live Blocker

Current live GitHub auth still observes `Halildeu` with admin permission. That
means the smoke remains blocked by:

```text
unexpected_merge_actor
merge_actor_admin_permission_observed
dedicated_merge_actor_not_confirmed
```

The smoke becomes runnable when the active `gh` runtime is authenticated as the
dedicated non-admin merge actor:

```text
gladyatore-lab
permission: write
admin: false
```

## Execute Flow

When A0/A1 are ready and explicit confirmation is present, the orchestrator:

1. creates a unique `codex/ao-ma10l-smoke-*` branch from `main`;
2. creates one low-risk file under
   `docs/evidence/ao-ma-10l-autonomous-smoke/`;
3. opens a disposable PR;
4. waits for required checks, including `ao-release-gate-technical` and
   `ao-release-gate-review`;
5. refreshes A0/A1;
6. delegates the actual merge to `scripts/ao_ma10c_merge_agent.py`.

The only merge command still lives inside AO-MA-10c:

```text
gh pr merge <pr> --repo Halildeu/ao-kernel --squash --delete-branch
```

AO-MA-10l never constructs an admin merge command and never mutates rulesets,
branch protection, CODEOWNERS, GPP status, support boundaries, or live adapter
configuration.

## Result Artifact

Schema:

```text
ao_kernel/defaults/schemas/ao-ma-10l-autonomous-smoke-result.schema.v1.json
```

The artifact records:

- expected actor and branch;
- disposable smoke path;
- A0/A1 decisions;
- created PR metadata;
- required-check observation;
- AO-MA-10c merge-agent result;
- whether any mutation occurred;
- final fail-closed decision.

## Completion Criteria

The low-risk autonomous lane is proven only when AO-MA-10l produces a `merged`
artifact where:

- actor is the dedicated non-admin merge actor;
- A0 is `ready_for_dry_run`;
- A1 is `ready_for_low_risk_dry_run`;
- required checks pass;
- AO-MA-10c reports `merged`;
- no admin bypass, bypass actor, support widening, production platform claim,
  or live adapter execution occurs.
