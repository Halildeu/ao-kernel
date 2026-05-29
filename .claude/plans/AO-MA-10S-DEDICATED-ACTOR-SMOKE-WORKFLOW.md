# AO-MA-10s - Dedicated Actor Smoke Workflow

**Parent:** AO-MA-10 low-risk autonomous merge lane

**Status:** Implemented fail-closed

**Workflow:** `.github/workflows/ao-ma10q-dedicated-actor-smoke.yml`

## Purpose

AO-MA-10s removes the remaining local-shell dependency from AO-MA-10q. The
dedicated non-admin merge actor token is read from the GitHub repository secret
`GLADYATORE_LAB_GH_TOKEN`, not from a local operator shell. The optional
governance token is read from `AO_GOVERNANCE_GH_TOKEN` for
branch-protection/ruleset readiness APIs only. Disposable low-risk PR
production and merge execution both stay bound to the dedicated non-admin actor
token. A Codex or Claude operator may dispatch the workflow, but the merge
authority remains the repo-owned `ao-release-gate` checks plus GitHub ruleset
enforcement, and the merge actor must still be `gladyatore-lab`.

This does not make the lane complete by itself. It makes the final smoke
repeatable from GitHub Actions:

```text
workflow_dispatch -> AO-MA-10r credential doctor -> AO-MA-10q runner
  -> AO-MA-10l disposable smoke -> AO-MA-10c merge-agent
```

## Safety Contract

- trigger is `workflow_dispatch` only;
- dispatch must run from `refs/heads/main`;
- no `pull_request` or `pull_request_target` secret path is introduced;
- workflow `GITHUB_TOKEN` has only `contents: read`;
- the dedicated actor token is only bound as an environment variable;
- the governance token is only bound as an environment variable and may be used
  only for readiness reads;
- disposable PR production and merge execution remain bound to the dedicated
  non-admin merge actor token;
- AO-MA-10q fails closed if delegated AO-MA-10l evidence reports a producer
  that is not the merge actor;
- token values are never echoed, printed, committed, or uploaded;
- execute mode still requires `AO-MA-10L-EXECUTE`;
- all evidence is uploaded as an Actions artifact;
- guard flags stay false:
  - `support_widening=false`
  - `production_platform_claim=false`
  - `live_adapter_execution=false`

## Dispatch Modes

Dry-run mode:

```bash
gh workflow run ao-ma10q-dedicated-actor-smoke.yml \
  --repo Halildeu/ao-kernel \
  --ref main \
  -f mode=dry-run
```

Execute mode:

```bash
gh workflow run ao-ma10q-dedicated-actor-smoke.yml \
  --repo Halildeu/ao-kernel \
  --ref main \
  -f mode=execute \
  -f confirmation=AO-MA-10L-EXECUTE
```

## Completion Criteria

AO-MA-10s is ready when the workflow exists, validates with tests, and fails
closed if `GLADYATORE_LAB_GH_TOKEN` is not configured.

The low-risk no-human merge lane is complete only when an execute-mode run
produces:

- AO-MA-10r `credential_ready`;
- AO-MA-10q `merged`;
- AO-MA-10l disposable PR merged;
- AO-MA-10c merge-agent result `merged`;
- live GitHub evidence that the merge actor is `gladyatore-lab`, not
  `Halildeu`;
- required `ao-release-gate-technical` and `ao-release-gate-review` checks
  remain source-pinned and passing.
