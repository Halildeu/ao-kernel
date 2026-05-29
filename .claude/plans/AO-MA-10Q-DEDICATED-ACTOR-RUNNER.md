# AO-MA-10q - Dedicated Actor Runner

**Status:** implemented fail-closed
**Date:** 2026-05-29
**Parent:** AO-MA-10 low-risk autonomous merge lane
**Support impact:** none
**Production platform claim:** false
**Live adapter execution:** false

## Purpose

AO-MA-10q removes the remaining ad-hoc shell wrapper step from the low-risk
autonomous merge smoke. It runs AO-MA-10l through a temporary GitHub CLI wrapper
that is scoped to the dedicated non-admin merge actor.

The runner does not replace release authority. AI provider output remains evidence only.
Release authority remains the repo-owned `ao-release-gate` required checks plus
GitHub ruleset enforcement.

## Script

```text
scripts/ao_ma10q_dedicated_actor_runner.py
```

Default token environment variable:

```text
GLADYATORE_LAB_GH_TOKEN
```

Optional governance-read token environment variable:

```text
AO_GOVERNANCE_GH_TOKEN
```

The runner never accepts token values on CLI arguments. It only accepts the
name of an environment variable and creates temporary `0700` wrappers:

```text
GH_TOKEN="${GLADYATORE_LAB_GH_TOKEN}" exec gh "$@"
GH_TOKEN="${AO_GOVERNANCE_GH_TOKEN}" exec gh "$@"
```

The output artifact records neither the token value nor the temporary wrapper
path.

## Dry-Run Command

```bash
GLADYATORE_LAB_GH_TOKEN=<redacted> \
AO_GOVERNANCE_GH_TOKEN=<redacted> \
  python3 scripts/ao_ma10q_dedicated_actor_runner.py \
    --output /tmp/ao-ma10q.json \
    --format text
```

Without the token environment variable, the runner exits fail-closed with:

```text
dedicated_actor_token_env_missing
```

## Execute Command

```bash
GLADYATORE_LAB_GH_TOKEN=<redacted> \
AO_GOVERNANCE_GH_TOKEN=<redacted> \
  python3 scripts/ao_ma10q_dedicated_actor_runner.py \
    --output /tmp/ao-ma10q.json \
    --execute \
    --confirmation AO-MA-10L-EXECUTE \
    --format text
```

AO-MA-10q delegates all live GitHub sequencing to AO-MA-10l:

```text
AO-MA-10q dedicated actor wrapper + governance/producer wrapper -> AO-MA-10l smoke -> AO-MA-10c merge-agent
```

AO-MA-10l still performs A0/A1 readiness checks, required check observation,
and AO-MA-10c merge delegation. If those checks fail, AO-MA-10q records the
blockers and does not turn AI review into release authority.

AO-MA-10q gives the delegated AO-MA-10l subprocess the full AO-MA-10l polling
window plus a bounded grace period: `timeout_seconds + max(60, poll_seconds * 4)`.
A subprocess timeout is caught and recorded as a fail-closed
`smoke_command_timeout` blocker so the workflow always uploads a diagnostic
artifact instead of ending with an uncaught traceback.

The governance wrapper has two bounded roles from AO-MA-10l's perspective:

1. read-only branch-protection/ruleset readiness APIs that fine-grained
   non-admin merge actor tokens cannot access;
2. disposable low-risk PR production (`base_ref_read`, `branch_create`,
   `file_create`, `pr_create`) when the dedicated non-admin actor token cannot
   create refs.

Required-check polling and merge execution continue to use the dedicated actor
wrapper. The producer wrapper is not release authority and cannot satisfy the
AO-MA-10c merge-agent actor assertion.

## Result Artifact

Schema:

```text
ao_kernel/defaults/schemas/ao-ma-10q-dedicated-actor-runner-result.schema.v1.json
```

The artifact records:

- expected actor and token environment variable name;
- producer token environment variable name and wrapper role;
- whether execute mode was requested;
- whether a temporary wrapper was created;
- sanitized AO-MA-10l command shape;
- embedded AO-MA-10l smoke result;
- final fail-closed decision.

## Completion Criteria

The no-human low-risk merge path is proven only when AO-MA-10q produces a
`merged` artifact where:

- token value is not recorded;
- wrapper path is not recorded;
- actor is the dedicated non-admin merge actor;
- any split PR producer is not treated as release authority;
- AO-MA-10l reports `merged`;
- required checks pass;
- no admin bypass, ruleset mutation, branch-protection mutation, support
  widening, production platform claim, or live adapter execution occurs.
