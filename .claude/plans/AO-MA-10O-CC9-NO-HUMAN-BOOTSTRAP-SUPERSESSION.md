# AO-MA-10O - CC-9 No-Human Bootstrap Supersession

**Status:** proposed / inactive until merged
**Date:** 2026-05-28
**Tracker:** https://github.com/Halildeu/ao-kernel/issues/683
**Depends on:** PR #682 and PR #684 landing first
**Supersedes:** `PROGRAM-CHANGE-CONTROL.md` CC-9, narrowly and only for
AO-MA-10 live autonomous merge enforcement cutover
**Support impact:** none
**Production platform claim:** false
**Live adapter execution:** false

## Purpose

AO-MA-10O removes the last human-only bootstrap dependency from the autonomous
merge lane plan without weakening release authority.

The current CC-9 rule says branch ruleset and branch-protection mutation is
operator-only. That is safe as a default, but it prevents the project from
reaching the user-requested end state:

```text
low-risk PR -> repo-owned checks -> agent normal merge -> no human approval
```

This supersession authorizes exactly one constrained no-human bootstrap path so
the repository can install the live enforcement model itself.

## Authority Model

AI output remains evidence, not release authority.

Release authority after cutover is still:

```text
ao-release-gate-technical + ao-release-gate-review + GitHub enforcement
```

The bootstrap agent is not a release authority. It is a narrow settings
executor that may apply only the exact live GitHub configuration described in
this record.

## Activation Preconditions

The no-human bootstrap path is inactive unless all of the following are true:

1. PR #682 is merged.
2. PR #684 is merged.
3. This AO-MA-10O supersession PR is merged.
4. `main` is clean and synced to `origin/main`.
5. `python3 scripts/gpp_next.py` still reports:
   - `support_widening_allowed: false`
   - `production_platform_claim_allowed: false`
   - `live_adapter_execution_allowed: false`
6. A read-only pre-change snapshot is collected by
   `scripts/ao_ma10_github_readiness_snapshot.py`.
7. The bootstrap script runs in dry-run mode and produces the expected plan
   before any `--apply`; the same dry-run plan must be passed back through
   `--accepted-dry-run-plan`.

## Allowed Mutation Surface

Only `scripts/ao_ma10o_no_human_bootstrap.py --apply` may perform the
superseded CC-9 mutation, and only for repository `Halildeu/ao-kernel`.

The script may call GitHub write APIs only for:

1. ruleset `16803733` on the default branch:
   - preserve `deletion`
   - preserve `non_fast_forward`
   - preserve `bypass_actors=[]`
   - require `ao-release-gate-technical` with `integration_id=15368`
   - require `ao-release-gate-review` with `integration_id=15368`
2. Classic branch protection on `main`:
   - remove `required_pull_request_reviews`
   - preserve classic required status checks:
     - `lint`
     - `test (3.11)`
     - `test (3.12)`
     - `test (3.13)`
     - `coverage`
     - `typecheck`
     - `packaging-smoke`
   - preserve `enforce_admins=true`

The script must refuse to run when:

- the repository differs from `Halildeu/ao-kernel`;
- the branch differs from `main`;
- the working tree is not clean `main` synced with `origin/main`;
- PR #682 or PR #684 is not merged;
- the AO-MA-10O supersession is not present on synced `main`;
- `gpp_next.py` does not keep all three guard flags false;
- `--apply` does not include `--accepted-dry-run-plan`;
- the ruleset id differs from `16803733`;
- the ruleset does not target `main` or `~DEFAULT_BRANCH`;
- the current ruleset has non-empty `bypass_actors`;
- either release-authority check cannot be source-pinned to integration id
  `15368`;
- the classic CI checks are absent from branch protection;
- the operator attempts to add any bypass actor;
- the operator attempts to remove classic CI requirements;
- the operator attempts to set support widening, production platform claim, or
  live adapter execution.

## Required Evidence

The bootstrap script must emit and retain:

1. pre-change readiness snapshot;
2. dry-run mutation plan passed back through `--accepted-dry-run-plan`;
3. exact ruleset patch payload;
4. exact branch-protection review removal intent;
5. post-change readiness snapshot;
6. diff of the two snapshots;
7. statement that `bypass_actors=[]`;
8. statement that no `--admin` merge or bypass actor was used.

## Post-Bootstrap Smoke

After the settings cutover:

1. Create a disposable low-risk PR and prove it merges without native human
   review.
2. Create a high-risk positive PR and prove valid OpenAI + Anthropic evidence
   makes `ao-release-gate-review` pass.
3. Create a high-risk negative PR and prove missing/stale/REVISE/same-provider
   evidence fails closed.
4. Record AO-MA-10m activation evidence with PR URLs, check-run URLs, merge
   actor, and before/after snapshots.

## Hard Stops

- No mutation before PR #682, PR #684, and this supersession are merged.
- No `--admin` merge.
- No ruleset bypass actors.
- No removal of classic CI requirements.
- No support widening.
- No production platform claim.
- No live adapter execution.
- No testai/smee/deployment-protection callback dependency.
- No treating Claude, Codex, MiniMax, or any model output as release authority.

## Exit Criteria

AO-MA-10O is complete when:

1. this supersession is merged;
2. `scripts/ao_ma10o_no_human_bootstrap.py --dry-run` passes from `main`;
3. the script applies the cutover once with `--apply`;
4. post-change snapshot proves both release-authority checks are required and
   source-pinned;
5. low-risk direct merge smoke succeeds with no human approval;
6. high-risk positive and negative smoke are recorded;
7. issue #683 is updated with final activation evidence.
