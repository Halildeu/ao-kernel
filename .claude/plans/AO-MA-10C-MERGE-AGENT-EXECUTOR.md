# AO-MA-10c - Merge Agent Executor

**Status:** implemented as fail-closed dry-run/executor
**Date:** 2026-05-28
**Parent:** AO-MA-10 low-risk autonomous merge lane
**Support impact:** none
**Production platform claim:** false
**Live adapter execution:** false

## Purpose

AO-MA-10c adds the merge-agent executor surface required for no-human
low-risk merge operation. The executor is not release authority. It performs a
normal GitHub merge only after deterministic repo-owned gates are already
satisfied.

The authority chain remains:

```text
local/process evidence -> ao-release-gate required checks -> GitHub ruleset -> merge agent executor
```

AI output remains evidence only.

## Historical Live Blocker

Earlier live readiness runs observed `Halildeu` with admin permission. The
merge-agent executor correctly blocked that path with:

```text
unexpected_merge_actor
merge_actor_admin_permission_observed
dedicated_merge_actor_not_confirmed
```

The `gladyatore-lab` fine-grained PAT path later proved repository write and
non-admin identity but failed both GitHub CLI GraphQL merge and REST pull merge
with `HTTP 403 Resource not accessible by personal access token`. The current
no-human workflow path therefore uses the repo-owned GitHub Actions executor
(`github-actions[bot]`) through `github.token`; the release authority remains
the required `ao-release-gate` checks plus GitHub ruleset.

## Executor Contract

The executor is implemented in:

```text
scripts/ao_ma10c_merge_agent.py
```

It is dry-run by default. Execute mode requires:

1. `--execute`
2. `--confirmation AO-MA-10C-EXECUTE`
3. fresh AO-MA-10a0 readiness snapshot
4. AO-MA-10a1 eligibility result `ready_for_low_risk_dry_run`
5. authenticated actor equals the configured expected merge executor
6. actor has `write`, not `admin`
7. PR is open, not draft, base `main`, merge state clean
8. all live required checks pass

The only merge command it may construct is the REST pull-request merge endpoint:

```text
gh api repos/Halildeu/ao-kernel/pulls/<pr>/merge \
  --method PUT \
  -f merge_method=squash \
  -f sha=<observed-head-sha>
```

After a successful merge it may delete the same-repository PR head ref through
the REST git-ref endpoint. Branch cleanup failure is warning-only; the merge
result remains tied to the repo-owned required checks and GitHub ruleset.

The executor must not construct admin bypass, bypass actors, GraphQL
`mergePullRequest`, ruleset mutation, or native auto-merge enablement.

## Result Artifact

The result schema is bundled at:

```text
ao_kernel/defaults/schemas/ao-ma-10c-merge-agent-result.schema.v1.json
```

The artifact records:

- actor identity and permission
- readiness/eligibility decisions
- live PR state
- required-check status
- merge command argv
- branch delete argv/error when applicable
- whether a merge command was attempted
- whether mutation occurred
- fail-closed blockers

## Non-Goals

This slice does not:

- authenticate an operator shell as release authority
- perform a live merge
- alter CODEOWNERS
- alter branch protection or rulesets
- add bypass actors
- widen support
- claim production platform readiness
- execute live adapters

## Next Slice

After the runtime is authenticated as the configured merge executor:

```text
AO-MA-10l positive disposable low-risk autonomous merge smoke
```

That smoke is the first point where a no-human merge can be proven end to end.
