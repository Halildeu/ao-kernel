# Runbook 04 — Mirror-Sync Apply Environment (AO-MA-11E-2b)

> **Agent-prepared only.** This runbook directs the operator to configure
> the `ao-ma-mirror-sync` GitHub environment used by the apply job of
> `.github/workflows/ao-ma-11e-2b-mirror-sync.yml`. The agent does NOT
> dispatch the apply workflow on the operator's behalf.

## Prerequisites

- Repository admin permissions on `Halildeu/ao-kernel`
- A non-author user account available as a required reviewer
- **Action 3** (PAT secret seed) completed; the secret
  `REPO_GH_PAT_PROJECTS_RW` is present

## Steps

1. Open Repository Settings → Environments → "New environment".
2. Name (exact): `ao-ma-mirror-sync`.
3. Add a required reviewer:
   - At least one non-author user
   - The reviewer must be able to verify the dry-run report digest
4. Wait timer: `0`.
5. Deployment branches: keep default; v1 does NOT need a branch
   restriction.
6. Environment secrets: **leave empty in v1**. The repo-level secret
   `REPO_GH_PAT_PROJECTS_RW` is consumed by the workflow directly.
7. Save the environment.

## Verification

- Repository Settings → Environments lists `ao-ma-mirror-sync`
- At least one required reviewer is shown
- Wait timer = `0`
- No environment-scoped secrets are present
- Re-running `gh secret list --repo Halildeu/ao-kernel` still shows
  `REPO_GH_PAT_PROJECTS_RW`

## Apply dispatch dependency chain (informational)

Apply runs are dispatched by the agent / automation. The apply job
requires all three prerequisites simultaneously:

1. The repo secret `REPO_GH_PAT_PROJECTS_RW` is set (Action 3)
2. The environment `ao-ma-mirror-sync` is configured (Action 4)
3. An accepted dry-run report digest from a prior workflow run is
   referenced by the dispatch inputs

This runbook covers prerequisite (2). The operator does NOT dispatch
apply directly.

## Rollback

- Removing the environment makes future apply dispatches fail
  immediately. Recreate with the same name + reviewer to restore.

## Stop and contact owner if

- The intended reviewer is also the workflow dispatcher (self-review
  attempt; not supported)
- The environment name is not exactly `ao-ma-mirror-sync` (typo)
- An environment secret was accidentally added
- Required reviewer count is `0` after Save
- Action 3 has not yet been completed (PAT secret missing)

## References

- `.github/workflows/ao-ma-11e-2b-mirror-sync.yml`
- Runbook 03 (PAT secret seed) — prerequisite
- Codex thread `019e84c6`
