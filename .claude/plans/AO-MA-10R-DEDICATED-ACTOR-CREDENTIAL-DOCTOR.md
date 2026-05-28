# AO-MA-10r - Dedicated Actor Credential Doctor

**Status:** implemented fail-closed
**Date:** 2026-05-29
**Parent:** AO-MA-10 low-risk autonomous merge lane
**Support impact:** none
**Production platform claim:** false
**Live adapter execution:** false

## Purpose

AO-MA-10r verifies the last credential prerequisite before AO-MA-10q executes
the low-risk autonomous merge smoke. It proves that a named environment
variable authenticates GitHub CLI as the expected dedicated non-admin merge
actor.

This is not release authority. Release authority remains the repo-owned
`ao-release-gate` required checks plus GitHub ruleset enforcement.

## Script

```text
scripts/ao_ma10r_dedicated_actor_credential_doctor.py
```

Default token environment variable:

```text
GLADYATORE_LAB_GH_TOKEN
```

The doctor never accepts token values as CLI arguments and never records token
values, token prefixes, token hashes, or credential paths. It sets `GH_TOKEN`
only inside the subprocess environment for read-only GitHub API calls.

## Command

```bash
GLADYATORE_LAB_GH_TOKEN=<redacted> \
  python3 scripts/ao_ma10r_dedicated_actor_credential_doctor.py \
    --output /tmp/ao-ma10r.json \
    --format text
```

Without the token environment variable, the doctor exits fail-closed with:

```text
dedicated_actor_token_env_missing
```

## Checks

The doctor performs read-only checks:

- `gh api user` -> actor identity is `gladyatore-lab`;
- `gh api repos/Halildeu/ao-kernel` -> actor has write or maintain, but not
  admin;
- `gh api repos/Halildeu/ao-kernel/pulls?state=open&per_page=1` -> actor can
  read pull-request state.

## Completion Criteria

AO-MA-10r is ready only when it emits `credential_ready` with:

- `token_value_recorded=false`;
- `mutations_performed=false`;
- `actor.matches_expected=true`;
- `repository_access.admin_permission_observed=false`;
- `repository_access.can_merge_without_admin=true`;
- `repository_access.can_read_pull_requests=true`;
- all guard flags false.

After AO-MA-10r passes, AO-MA-10q may be executed with the same token
environment variable to collect the real no-human autonomous merge smoke.
