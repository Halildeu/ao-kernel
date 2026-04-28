# GPP-2aa - AO Release Gate Autonomous Deploy Path

**Issue:** [#547](https://github.com/Halildeu/ao-kernel/issues/547)
**Decision:** `ao_release_gate_autonomous_deploy_path_ready_service_not_bootstrapped`
**Date:** 2026-04-28
**Support widening:** false
**Production platform claim:** false
**Live adapter execution:** false

## Decision

GPP-2aa adds a repo-owned autonomous Cloud Run deploy path for the
`ao-release-gate` check-run service image. The workflow can deploy a trusted
immutable image tag after the `Publish AO Release Gate Container` workflow
succeeds on `main`, or by explicit trusted `workflow_dispatch`.

This is a deploy automation path only. It does not prove that Google Cloud OIDC
bootstrap exists, it does not configure the GitHub App webhook URL, it does not
post check-runs, it does not collect real PR evidence, it does not change branch
protection, it does not merge pull requests, it does not run a live adapter, it
does not widen support, and it does not claim production readiness.

## Added Surface

1. `.github/workflows/ao-release-gate-deploy-cloud-run.yml`
   - runs only after trusted `main` publication or explicit
     `workflow_dispatch`;
   - uses GitHub OIDC (`id-token: write`) for Google Cloud auth;
   - reads cloud resource names and secret object names from repository
     variables;
   - pulls the immutable GHCR image tag
     `ghcr.io/halildeu/ao-kernel-ao-release-gate-service:sha-<commit>`;
   - mirrors that immutable image to Google Artifact Registry;
   - deploys Cloud Run with public ingress for GitHub webhook delivery;
   - binds runtime secrets by Secret Manager name/version, not by secret value;
   - health-checks `GET /healthz`;
   - uploads `ao-release-gate-deploy.v1.json` and `healthz.json` evidence.

2. `tests/test_ao_release_gate_deploy_workflow.py`
   - pins trusted trigger scope, OIDC auth, immutable image flow, health
     evidence, and security guardrails.

3. `deploy/ao-release-gate-service/README.md`
   - records the Cloud Run variable and Secret Manager contract.

## Trust Boundary

The workflow intentionally does not use:

```text
secrets.*
AO_CLAUDE_CODE_CLI_AUTH
gcloud secrets versions access
pull_request
pull_request_target
gh pr merge
branch protection update APIs
```

The hosted service receives only runtime GitHub App materials that Cloud Run
resolves from Secret Manager:

```text
AO_RELEASE_GATE_WEBHOOK_SECRET
AO_GITHUB_APP_ID
AO_GITHUB_APP_PRIVATE_KEY_PEM
```

Repository variables such as `AO_RELEASE_GATE_WEBHOOK_SECRET_NAME` and
`AO_RELEASE_GATE_GITHUB_APP_PRIVATE_KEY_SECRET_NAME` are secret object names,
not secret values.

## Bootstrap Contract

The deploy workflow is autonomous only after this external machine-trust
bootstrap exists:

1. Google Cloud Workload Identity Provider trusts this repository's GitHub OIDC
   identity for the deploy workflow.
2. The configured Google service account can push to the selected Artifact
   Registry repository and deploy the selected Cloud Run service.
3. Google Secret Manager contains the release-gate webhook secret and GitHub
   App private key under the configured secret object names.
4. The Cloud Run service can access those secrets at runtime.
5. The `ao-release-gate` GitHub App webhook URL points at:

```text
https://<cloud-run-service-url>/github/ao-release-gate
```

Secret values must not be pasted into issues, PRs, logs, chat, MCP prompts, or
repository files.

## Evidence Contract

A successful deploy workflow uploads:

```text
ao-release-gate-deploy.v1.json
healthz.json
```

The deployment evidence records:

```text
status=ao_release_gate_deployed_health_checked
secret_value_readback=false
check_run_post=false
real_pr_evidence=false
branch_protection_cutover=false
merge_authority_enabled=false
live_adapter_execution=false
support_widening=false
production_platform_claim=false
```

This evidence proves a hosted health endpoint for the `ao-release-gate`
revision. It is not enough to grant release authority. GPP-2 remains blocked
until the GitHub App webhook is configured to this URL, real PR dry-run
check-run evidence is collected, branch protection or rulesets require
`ao-release-gate`, and the deployment-protection policy service is also
hosted/configured with protected callback evidence.

## Current Decision

Resolved by this slice:

1. repo-owned autonomous deploy workflow exists for `ao-release-gate`;
2. deploy authentication is OIDC-based, not a committed cloud key;
3. PR/fork contexts cannot run the deploy job;
4. immutable GHCR image tags remain the source of deployed revisions;
5. runtime secrets are passed by Secret Manager reference only;
6. deploy evidence records no secret readback, no check-run POST, no branch
   protection cutover, no merge authority, and no live adapter execution.

Still blocked:

1. cloud OIDC/service-account/Secret Manager bootstrap is not attested by this
   PR;
2. no Cloud Run deployment run has completed from `main` in this slice;
3. the `ao-release-gate` GitHub App webhook URL is not proven configured to the
   Cloud Run endpoint;
4. no real PR dry-run check-run has been posted by the hosted service;
5. branch protection/rulesets do not yet require `ao-release-gate`;
6. the deployment-protection policy service still needs hosted callback
   evidence before live-adapter runtime work can continue.

Still closed:

1. `merge_authority_enabled=false`;
2. `live_execution_allowed=false`;
3. `support_widening=false`;
4. `production_platform_claim=false`.

## Validation

```bash
python3 -m json.tool .claude/plans/gpp_status.v1.json
pytest -q tests/test_ao_release_gate_deploy_workflow.py tests/test_ao_release_gate_container_publish_workflow.py tests/test_gpp_next.py
python3 -m ruff check tests/test_ao_release_gate_deploy_workflow.py tests/test_ao_release_gate_container_publish_workflow.py tests/test_gpp_next.py
actionlint .github/workflows/ao-release-gate-deploy-cloud-run.yml .github/workflows/ao-release-gate-container-publish.yml
python3 scripts/gpp_next.py
git diff --check
```

Recorded closeout decision:

```text
ao_release_gate_autonomous_deploy_path_ready_service_not_bootstrapped
```
