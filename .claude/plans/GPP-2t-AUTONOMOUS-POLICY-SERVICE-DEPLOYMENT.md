# GPP-2t - Autonomous Policy Service Deployment Path

**Status:** closeout candidate
**Date:** 2026-04-28
**Authority:** `origin/main` at `02a4b7e`
**Issue:** [#535](https://github.com/Halildeu/ao-kernel/issues/535)
**Branch:** `codex/gpp-2t-autonomous-policy-deploy`
**Worktree:** `/Users/halilkocoglu/Documents/ao-kernel-gpp-2t-autonomous-policy-deploy`
**Program head:** `GPP-2` blocked on hosted policy service bootstrap/configuration
**Support impact:** none
**Runtime impact:** no live adapter call; no protected workflow dispatch; no
GitHub deployment callback post in this slice

## 1. Purpose

GPP-2s made the policy service image publishable to GHCR. The next blocker was
manual/public hosting. This slice adds a repo-owned autonomous deploy path for
the policy service so a trusted `main` image can be deployed, health-checked,
and evidenced without treating a manual UI host as the operating model.

Decision:

```text
policy_service_autonomous_deploy_path_ready_service_not_bootstrapped
```

This slice creates the deploy automation path. It does not prove that the cloud
trust bootstrap exists, does not configure the GitHub App webhook URL by reading
GitHub App secrets in Actions, does not post a live deployment protection
callback, does not run the live adapter, and does not widen support.

## 2. Implemented Surface

Deploy assets:

1. `.github/workflows/policy-service-deploy-cloud-run.yml`
   - triggers from successful trusted `Publish Policy Container` workflow runs
     on `main` or trusted manual dispatch;
   - uses GitHub OIDC (`id-token: write`) to authenticate to Google Cloud;
   - reads only repository variables for cloud resource names and secret object
     names;
   - pulls the immutable GHCR image tag for the source SHA;
   - mirrors that immutable image to Google Artifact Registry;
   - deploys the image to Cloud Run with public ingress for GitHub webhook
     delivery;
   - binds runtime secrets by Secret Manager name/version, not by secret value;
   - checks `GET /healthz`;
   - uploads `policy-service-deploy.v1.json` evidence.
2. `tests/test_policy_service_deploy_workflow.py`
   - pins the OIDC/Cloud Run path, immutable image flow, health evidence, and
     security guardrails.
3. `deploy/live-adapter-gate-policy-service/README.md`
   - documents required repository variables and secret-manager name contract.
4. `docs/LIVE-ADAPTER-GATE-PROVISIONING-RUNBOOK.md`
   - records the autonomous deploy path and the evidence interpretation.

## 3. Trust Boundary

The workflow intentionally does not use:

```text
secrets.*
AO_CLAUDE_CODE_CLI_AUTH
gcloud secrets versions access
pull_request
pull_request_target
```

It also does not dispatch:

```text
.github/workflows/live-adapter-gate.yml
```

The policy service gets only the GitHub App runtime materials that Cloud Run
resolves from Secret Manager at runtime:

```text
AO_LIVE_ADAPTER_GATE_WEBHOOK_SECRET
AO_GITHUB_APP_ID
AO_GITHUB_APP_PRIVATE_KEY_PEM
```

Repository variables such as `AO_POLICY_SERVICE_WEBHOOK_SECRET_NAME` and
`AO_GITHUB_APP_PRIVATE_KEY_SECRET_NAME` are secret object names, not secret
values.

## 4. Bootstrap Contract

The automation is autonomous after the following machine-trust bootstrap exists:

1. Google Cloud Workload Identity Provider trusts this repository's GitHub OIDC
   identity for the deploy workflow.
2. The configured Google service account can push to the selected Artifact
   Registry repository and deploy the selected Cloud Run service.
3. Google Secret Manager contains the webhook secret and GitHub App private key
   under the configured secret object names.
4. The Cloud Run service can access those secrets at runtime.
5. The GitHub App webhook URL points at:

```text
https://<cloud-run-service-url>/github/deployment-protection
```

The bootstrap can be performed by infrastructure automation outside this repo,
but the secret values must not be pasted into issues, PRs, logs, chat, MCP
prompts, or repository files.

## 5. Evidence Contract

A successful deploy workflow uploads:

```text
policy-service-deploy.v1.json
healthz.json
```

The deployment evidence records:

```text
status=policy_service_deployed_health_checked
secret_value_readback=false
live_adapter_execution=false
github_callback_post=false
support_widening=false
production_platform_claim=false
```

This evidence proves a hosted health endpoint for the policy service revision.
It is not enough to unblock live adapter execution. GPP-2 remains blocked until
a later protected workflow evidence slice confirms that the GitHub App service
receives a real `deployment_protection_rule` delivery and posts an explicit
deployment protection callback review.

## 6. Current Decision

Resolved by this slice:

1. repo-owned autonomous deploy workflow exists;
2. deploy authentication is OIDC-based, not a committed cloud key;
3. PR/fork contexts cannot run the deploy job;
4. immutable GHCR image tags remain the source of deployed revisions;
5. runtime secrets are passed by Secret Manager reference only;
6. deploy evidence records no secret readback and no live adapter execution.

Still blocked:

1. cloud OIDC/service-account/Secret Manager bootstrap is not attested by this
   PR;
2. no Cloud Run deployment run has completed from `main` in this slice;
3. GitHub App webhook URL is not proven configured to the Cloud Run endpoint;
4. no real GitHub deployment callback review has been posted by the hosted
   service;
5. no new protected workflow evidence artifacts exist after policy response.

Still closed:

1. `live_execution_allowed=false`;
2. `support_widening=false`;
3. `production_platform_claim=false`.

## 7. Validation

```bash
python3 -m json.tool .claude/plans/gpp_status.v1.json
pytest -q tests/test_policy_service_deploy_workflow.py tests/test_policy_container_publish_workflow.py tests/test_gpp_next.py
python3 -m ruff check tests/test_policy_service_deploy_workflow.py tests/test_policy_container_publish_workflow.py tests/test_gpp_next.py
actionlint .github/workflows/policy-service-deploy-cloud-run.yml .github/workflows/policy-container-publish.yml
python3 scripts/gpp_next.py
git diff --check
```

Expected closeout decision:

```text
policy_service_autonomous_deploy_path_ready_service_not_bootstrapped
```

Recorded closeout decision:

```text
policy_service_autonomous_deploy_path_ready_service_not_bootstrapped
```
