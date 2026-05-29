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
variable authenticates GitHub CLI as the expected merge executor.

This is not release authority. Release authority remains the repo-owned
`ao-release-gate` required checks plus GitHub ruleset enforcement.

## Script

```text
scripts/ao_ma10r_dedicated_actor_credential_doctor.py
```

Default token environment variable for workflow-owned runs:

```text
AO_MERGE_GITHUB_TOKEN
```

The GitHub Actions smoke workflow passes the repo-owned executor explicitly:

```text
--token-env AO_MERGE_GITHUB_TOKEN
--expected-actor github-actions[bot]
```

The doctor never accepts token values as CLI arguments and never records token
values, token prefixes, token hashes, or credential paths. It sets `GH_TOKEN`
only inside the subprocess environment for GitHub API calls.

When the expected actor is `github-actions[bot]`, the token is an integration
token rather than a user token. GitHub returns `Resource not accessible by
integration` for user-shaped endpoints such as `gh api user`, and may do the
same for repository permission introspection. AO-MA-10r treats those endpoint
shapes as expected integration-token behavior, records warnings, requires
pull-request API read access, and leaves the actual merge write proof to the
AO-MA-10q runner. This keeps the doctor from rejecting the repo-owned
`github.token` before the fail-closed merge path can be exercised.

By default the doctor remains read-only. In execute-mode smoke runs the
workflow passes `--branch-write-probe`, which creates and immediately deletes a
temporary `codex/ao-ma10r-token-probe-*` branch. This proves the exact write
path AO-MA-10l needs before the smoke attempts to create its disposable PR.

## Command

```bash
AO_MERGE_GITHUB_TOKEN=<redacted> \
  python3 scripts/ao_ma10r_dedicated_actor_credential_doctor.py \
    --output /tmp/ao-ma10r.json \
    --format text
```

Without the token environment variable, the doctor exits fail-closed with:

```text
dedicated_actor_token_env_missing
```

## Checks

The doctor always performs read-only checks:

- `gh api user` -> actor identity matches the configured expected actor;
- `gh api repos/Halildeu/ao-kernel` -> actor has write or maintain, but not
  admin;
- `gh api repos/Halildeu/ao-kernel/pulls?state=open&per_page=1` -> actor can
  read pull-request state.

For `github-actions[bot]` integration tokens, the first two endpoints may be
unavailable by GitHub design. In that mode AO-MA-10r records
`github_user_endpoint_unavailable_for_integration_token` and
`repository_permission_endpoint_unavailable_for_integration_token` as warnings
instead of blockers, while keeping pull-request read access mandatory.

With `--branch-write-probe`, the doctor additionally:

- reads `refs/heads/main`;
- creates a temporary `codex/ao-ma10r-token-probe-*` branch;
- deletes that temporary branch;
- fails closed with `branch_write_probe_create_failed`,
  `branch_write_probe_base_ref_read_failed`, or
  `branch_write_probe_cleanup_failed` if any step fails.

By default the branch-write probe uses the same merge executor token. When
AO-MA-10q is running with a split disposable PR producer, pass:

```text
--branch-write-probe-token-env AO_GOVERNANCE_GH_TOKEN
```

That proves the producer token can create/delete the disposable smoke branch
without making that producer release authority. The merge executor identity,
required-check polling, and merge-agent execution remain bound to the configured
merge executor token.

## Completion Criteria

AO-MA-10r is ready only when it emits `credential_ready` with:

- `token_value_recorded=false`;
- `mutations_performed=false` for read-only mode, or `true` only when
  `--branch-write-probe` successfully creates and deletes the temporary branch;
- `actor.matches_expected=true`;
- `repository_access.admin_permission_observed=false`;
- `repository_access.can_merge_without_admin=true`;
- `repository_access.can_read_pull_requests=true`;
- `branch_write_probe.create_result=created` and
  `branch_write_probe.delete_result=deleted` when execute mode requests the
  branch-write probe;
- `branch_write_probe.token_role` is `merge_actor` for same-token probes or
  `producer` for split disposable PR producer probes;
- all guard flags false.

After AO-MA-10r passes, AO-MA-10q may be executed with the same token
environment variable to collect the real no-human autonomous merge smoke.
