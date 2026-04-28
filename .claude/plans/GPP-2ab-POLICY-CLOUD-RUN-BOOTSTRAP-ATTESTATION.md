# GPP-2ab - Policy Cloud Run Bootstrap Attestation

**Status:** closeout candidate
**Date:** 2026-04-28
**Authority:** `origin/main` at `02a4b7e`
**Issue:** [#549](https://github.com/Halildeu/ao-kernel/issues/549)
**Branch:** `codex/gpp-2ab-policy-cloud-run-bootstrap-attest`
**Worktree:** `/Users/halilkocoglu/Documents/ao-kernel-gpp-2ab-policy-cloud-run-bootstrap-attest`
**Program head:** `GPP-2` blocked on hosted policy service bootstrap/configuration
**Support impact:** none
**Runtime impact:** no Cloud Run deployment, no GitHub callback post, no
protected workflow dispatch, no live adapter call

## 1. Purpose

GPP-2t added the autonomous Cloud Run deployment path for the policy service,
but the next repeatable question was whether the repository has the non-secret
variable handles required before dispatching that workflow. This slice adds a
metadata-only bootstrap attestation for those handles.

Decision:

```text
policy_cloud_run_bootstrap_attestation_tool_ready_variables_missing
```

This slice creates the bootstrap attestation tool. It does not prove Google
Cloud Workload Identity, service-account permissions, Artifact Registry,
Secret Manager objects, Cloud Run hosting, GitHub App webhook configuration, a
deployment protection callback post, live adapter execution, support widening,
or production-platform readiness.

## 2. Implemented Surface

Code and docs:

1. `scripts/policy_service_cloud_run_bootstrap_attest.py`
   - collects GitHub repository variable metadata with
     `gh variable list --json name,updatedAt`;
   - records only variable names, presence, and update timestamps;
   - ignores any variable `value` fields present in fixtures;
   - writes `policy-service-cloud-run-bootstrap-attestation.v1.json`;
   - exits non-zero with `--fail-on-blocked` when required handles are missing.
2. `tests/test_policy_service_cloud_run_bootstrap_attest.py`
   - pins metadata-only behavior, missing-variable blocking, CLI rendering, and
     no-secret/no-live-operation guardrails.
3. `deploy/live-adapter-gate-policy-service/README.md`
   - documents the bootstrap attestation before Cloud Run deployment.
4. `docs/LIVE-ADAPTER-GATE-PROVISIONING-RUNBOOK.md`
   - records how to run and interpret the attestation.

## 3. Metadata Contract

Required repository variables:

```text
GCP_PROJECT_ID
GCP_WORKLOAD_IDENTITY_PROVIDER
GCP_SERVICE_ACCOUNT
GCP_CLOUD_RUN_REGION
GCP_ARTIFACT_REGISTRY_LOCATION
GCP_ARTIFACT_REGISTRY_REPOSITORY
POLICY_SERVICE_NAME
AO_GITHUB_APP_ID
AO_POLICY_SERVICE_WEBHOOK_SECRET_NAME
AO_GITHUB_APP_PRIVATE_KEY_SECRET_NAME
```

Optional repository variables:

```text
AO_POLICY_SERVICE_WEBHOOK_SECRET_VERSION
AO_GITHUB_APP_PRIVATE_KEY_SECRET_VERSION
```

The two `*_SECRET_NAME` variables are Secret Manager object names, not secret
values. A `metadata_ready` attestation means only that these repository
variable handles are visible by metadata. It is not cloud trust evidence.

Current live metadata observation on 2026-04-28:

```text
overall_status=blocked
finding_code=policy_cloud_run_bootstrap_missing_repository_variables
```

The live repository metadata check reported all required handles missing. Do
not dispatch the Cloud Run deploy workflow until those handles are provisioned
and a new attestation reports `overall_status=metadata_ready`.

## 4. Trust Boundary

The attestation intentionally does not use:

```text
gcloud secrets versions access
secrets.*
AO_CLAUDE_CODE_CLI_AUTH
```

It also does not deploy, dispatch, or post:

```text
Cloud Run deployment
GitHub deployment protection callback
.github/workflows/live-adapter-gate.yml
live adapter execution
```

## 5. Current Decision

Resolved by this slice:

1. a repo-owned metadata-only attestation exists for the Cloud Run deploy
   workflow's required repository variable handles;
2. missing required handles produce `overall_status=blocked`;
3. present required handles produce `overall_status=metadata_ready`;
4. fixture values are ignored and are not serialized into evidence;
5. the artifact records no secret value readback, no Cloud Run deployment, no
   GitHub callback post, no live adapter execution, no support widening, and
   no production-platform claim.

Still blocked:

1. required GitHub repository variable handles are currently missing;
2. Google Cloud OIDC trust is not proven;
3. Google service-account permissions are not proven;
4. Artifact Registry and Secret Manager objects are not proven;
5. Cloud Run hosting evidence is not present;
6. the GitHub App webhook URL is not proven configured to a hosted endpoint;
7. no real GitHub deployment callback review has been posted by the hosted
   service;
8. no new protected workflow evidence artifacts exist after policy response.

Still closed:

1. `live_execution_allowed=false`;
2. `support_widening=false`;
3. `production_platform_claim=false`.

## 6. Validation

```bash
python3 -m json.tool .claude/plans/gpp_status.v1.json
pytest -q tests/test_policy_service_cloud_run_bootstrap_attest.py tests/test_policy_service_deploy_workflow.py tests/test_gpp_next.py
python3 -m ruff check scripts/policy_service_cloud_run_bootstrap_attest.py tests/test_policy_service_cloud_run_bootstrap_attest.py tests/test_policy_service_deploy_workflow.py tests/test_gpp_next.py
python3 scripts/gpp_next.py
git diff --check
```

Expected closeout decision:

```text
policy_cloud_run_bootstrap_attestation_tool_ready_variables_missing
```

Recorded closeout decision:

```text
policy_cloud_run_bootstrap_attestation_tool_ready_variables_missing
```
