# GPP-2s - Policy Container Image Publish Path

**Status:** closeout candidate
**Date:** 2026-04-28
**Authority:** `origin/main` at `27b2b3f`
**Issue:** [#533](https://github.com/Halildeu/ao-kernel/issues/533)
**Branch:** `codex/gpp-2s-policy-image-publish`
**Worktree:** `/Users/halilkocoglu/Documents/ao-kernel-gpp-2s-policy-image-publish`
**Program head:** `GPP-2` blocked on hosted policy service deployment/configuration
**Support impact:** none
**Runtime impact:** no live adapter call; no GitHub App webhook URL
configuration; no runtime secret value readback

## 1. Purpose

GPP-2r made the policy service container-buildable, but a hosting provider
still needed either local build steps or a repo-owned published image artifact.
This slice adds a no-secret GHCR publication path for the policy service image
without deploying it or configuring the GitHub App webhook URL.

Decision:

```text
policy_container_publish_path_ready_service_not_hosted
```

This slice creates a deploy artifact path only. It does not run a public
service, set webhook URLs, read runtime secrets back, dispatch the protected
workflow, invoke a live adapter, widen support, or claim production-platform
readiness.

## 2. Implemented Surface

Code and deploy assets:

1. `.github/workflows/policy-container-publish.yml`
   - builds `deploy/live-adapter-gate-policy-service/Dockerfile`;
   - tags the image as
     `ghcr.io/halildeu/ao-kernel-live-adapter-gate-policy-service:sha-<commit>`;
   - runs the existing no-secret container `/healthz` smoke with
     `--skip-build`;
   - pushes only for trusted non-PR events;
   - adds the moving `:main` tag only for `refs/heads/main`;
   - uses `github.token` with `packages: write`, not `secrets.*`;
   - does not reference `AO_CLAUDE_CODE_CLI_AUTH`, webhook secrets, GitHub App
     private keys, or live adapter credentials.
2. `tests/test_policy_container_publish_workflow.py`
   - pins GHCR image naming, no-secret smoke execution, PR no-push gating, and
     live credential exclusions.
3. `deploy/live-adapter-gate-policy-service/README.md`
   - documents the GHCR image tags and registry-token boundary.
4. `docs/LIVE-ADAPTER-GATE-PROVISIONING-RUNBOOK.md`
   - records the image publication step and hosted-deploy pull guidance.

## 3. Image Contract

Trusted main/manual builds publish:

```text
ghcr.io/halildeu/ao-kernel-live-adapter-gate-policy-service:sha-<commit>
ghcr.io/halildeu/ao-kernel-live-adapter-gate-policy-service:main
```

Hosted deployments should prefer the immutable `sha-<commit>` tag. If the
hosting platform cannot pull the package anonymously, the host must receive a
GHCR read token through its secret manager. Registry credentials must not be
committed or baked into the image.

The image still requires runtime host configuration for:

```text
AO_LIVE_ADAPTER_GATE_WEBHOOK_SECRET
AO_GITHUB_APP_ID
AO_GITHUB_APP_PRIVATE_KEY_PEM
```

or:

```text
AO_GITHUB_APP_PRIVATE_KEY_PATH
```

Do not pass `AO_CLAUDE_CODE_CLI_AUTH` to this container. The policy service is
not a live-adapter runner.

## 4. Current Decision

Resolved by this slice:

1. repo-owned GHCR image publication path exists;
2. PRs build and smoke the image without pushing;
3. trusted non-PR events can push an immutable image tag;
4. `main` builds can push a moving `main` tag;
5. image publication stays separate from runtime secret handling.

Still blocked:

1. no public hosted endpoint is deployed;
2. GitHub App webhook URL has not been configured to a hosted endpoint;
3. hosted runtime secrets have not been configured by an approved secret path;
4. no live GitHub deployment callback review has been posted by the hosted
   service;
5. no new protected workflow evidence artifacts exist after policy response;
6. live adapter execution remains disabled.

Still closed:

1. `live_execution_allowed=false`;
2. `support_widening=false`;
3. `production_platform_claim=false`.

## 5. Next Required Action

Deploy the GHCR image or equivalent container package to a public hosting
platform and configure the `ao-kernel-live-adapter-gate` GitHub App webhook URL
to the hosted `/github/deployment-protection` endpoint. Runtime secrets must be
supplied only through the hosting provider's secret manager or secret-file
mount.

Only after that service is expected to respond should the protected workflow
evidence slice be rerun from `main`.

## 6. Validation

```bash
python3 -m json.tool .claude/plans/gpp_status.v1.json
pytest -q tests/test_policy_container_publish_workflow.py tests/test_gpp_next.py
python3 -m ruff check tests/test_policy_container_publish_workflow.py
actionlint .github/workflows/policy-container-publish.yml
python3 scripts/gpp_next.py
git diff --check
```

The image publication workflow itself is validated by PR CI as a build and
no-secret smoke. Publishing happens only after merge or manual trusted
dispatch.

Expected closeout decision:

```text
policy_container_publish_path_ready_service_not_hosted
```

Recorded closeout decision:

```text
policy_container_publish_path_ready_service_not_hosted
```
