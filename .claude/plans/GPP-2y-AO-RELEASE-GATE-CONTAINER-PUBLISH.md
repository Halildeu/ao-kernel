# GPP-2y - AO Release Gate Container Publish Path

**Issue:** [#545](https://github.com/Halildeu/ao-kernel/issues/545)
**Decision:** `ao_release_gate_publish_path_ready_no_support_widening`
**Date:** 2026-04-28
**Support widening:** false
**Production platform claim:** false
**Live adapter execution:** false

## Decision

GPP-2y adds a repo-owned GHCR publication path for the `ao-release-gate`
check-run service container. Pull requests and codex branches build and run the
no-secret `/healthz` smoke without pushing. Trusted `main` or manual
`workflow_dispatch` runs can publish immutable `sha-<commit>` tags and the
moving `main` tag for hosted deployments.

This is a deploy artifact path only. It does not host the service, configure
the GitHub App webhook URL, post check-runs, change branch protection, merge
PRs, run a live adapter, widen support, or claim production readiness.
It does not unblock GPP-2 and does not authorize human-free merges.

## Added Surface

1. `.github/workflows/ao-release-gate-container-publish.yml`
   - builds `deploy/ao-release-gate-service/Dockerfile`;
   - tags the image as
     `ghcr.io/halildeu/ao-kernel-ao-release-gate-service:sha-<commit>`;
   - runs `scripts/ao_release_gate_container_smoke.py --skip-build` before
     any image push;
   - builds and smokes PR/codex branch changes without pushing;
   - pushes only for `refs/heads/main` or explicit `workflow_dispatch`;
   - adds the moving `:main` tag only for `refs/heads/main`;
   - uses `github.token` with `packages: write`, not `secrets.*`;
   - does not reference `AO_CLAUDE_CODE_CLI_AUTH`, webhook secrets, GitHub App
     private keys, or live adapter credentials.

2. `deploy/ao-release-gate-service/README.md`
   - records GHCR image tags;
   - records runtime-only GitHub App secret names;
   - records `POST /github/ao-release-gate`;
   - states that the package does not change branch protection or grant
     release authority.

3. `tests/test_ao_release_gate_container_publish_workflow.py`
   - pins GHCR image naming, no-secret smoke execution, trusted-event publish
     gating, and live credential exclusions.

## Image Contract

Trusted `main` or manual publication can produce:

```text
ghcr.io/halildeu/ao-kernel-ao-release-gate-service:sha-<commit>
ghcr.io/halildeu/ao-kernel-ao-release-gate-service:main
```

Hosted deployments should prefer immutable `sha-<commit>` tags. If the hosting
platform cannot pull the package anonymously, the host must receive a GHCR read
token through its secret manager. Registry credentials must not be committed or
baked into the image.

The image still requires runtime host configuration for:

```text
AO_RELEASE_GATE_WEBHOOK_SECRET
AO_GITHUB_APP_ID
AO_GITHUB_APP_PRIVATE_KEY_PEM
```

or:

```text
AO_GITHUB_APP_PRIVATE_KEY_PATH
```

Do not pass `AO_CLAUDE_CODE_CLI_AUTH` to this container. The release-gate
service is not a live-adapter runner and is not merge authority until a later
explicit branch-protection/ruleset cutover is approved after real PR evidence.

## Remaining Blockers

GPP-2 remains blocked after this work because:

1. The `ao-release-gate` image publication path exists, but no public hosted
   endpoint is deployed.
2. The `ao-release-gate` GitHub App webhook URL/runtime secret configuration is
   not yet proven on a real delivery.
3. No real PR dry-run check-run evidence has been collected.
4. Branch protection/rulesets do not yet require `ao-release-gate`.
5. The deployment-protection policy service for
   `ao-kernel-live-adapter-gate` is still not publicly hosted/configured and
   still has no protected workflow callback evidence.

## Next Allowed Action

Deploy the published `ao-release-gate` image or equivalent container package to
a public hosting platform, configure runtime secret-manager values, collect real
PR dry-run check-run evidence, and only then consider a branch-protection or
ruleset cutover. The deployment-protection policy service must also still be
hosted/configured before protected live-adapter workflow evidence is rerun.
