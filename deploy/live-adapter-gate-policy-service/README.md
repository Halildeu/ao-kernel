# Live Adapter Gate Policy Service Container

This container packages the GPP-2q WSGI runtime for the GitHub App deployment
protection policy service.

It is not a live-adapter runner. It only hosts:

```text
ao_kernel.live_adapter_gate_policy_runtime:application
```

## Build

```bash
docker build \
  -f deploy/live-adapter-gate-policy-service/Dockerfile \
  -t ao-kernel-live-adapter-gate-policy-service:local \
  .
```

## Published Image

The repository publication workflow builds this same Dockerfile, runs the
no-secret `/healthz` smoke, and publishes trusted non-PR builds to GHCR:

```text
ghcr.io/halildeu/ao-kernel-live-adapter-gate-policy-service:sha-<commit>
ghcr.io/halildeu/ao-kernel-live-adapter-gate-policy-service:main
```

Use the immutable `sha-<commit>` tag for hosted deployments whenever possible.
If the hosting provider cannot pull the package anonymously, configure a GHCR
read token through that provider's secret manager. Do not bake registry tokens
or runtime secrets into the image.

## Autonomous Cloud Run Deployment

The repository also contains a trusted, non-PR deployment workflow:

```text
.github/workflows/policy-service-deploy-cloud-run.yml
```

That workflow is designed to run after the policy container publish workflow
completes successfully on `main`, or by trusted manual dispatch. It uses
GitHub OIDC to authenticate to Google Cloud, mirrors the immutable GHCR image
to Artifact Registry, deploys the policy service to Cloud Run, verifies
`GET /healthz`, and uploads a deployment evidence artifact.

Required repository variables for that workflow:

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

The two `*_SECRET_NAME` variables are secret-manager object names, not secret
values. The workflow must not read back secret values. It passes those names to
Cloud Run so the hosted service receives runtime secrets from Secret Manager.

To provision those repository variables without using the GitHub UI, generate a
local template, fill it with non-secret values, dry-run it, then apply it:

```bash
python3 scripts/policy_service_cloud_run_repo_variables.py \
  --write-template /tmp/policy-service-cloud-run-repo-variables.json
```

```bash
python3 scripts/policy_service_cloud_run_repo_variables.py \
  --config-json /tmp/policy-service-cloud-run-repo-variables.json \
  --dry-run \
  --output text
```

```bash
python3 scripts/policy_service_cloud_run_repo_variables.py \
  --config-json /tmp/policy-service-cloud-run-repo-variables.json \
  --output text
```

The tool validates required handles, rejects unknown variables, refuses common
credential-shaped values, and sends values to `gh variable set` through stdin so
they are not placed in the command line or rendered in stdout. Do not put
webhook secrets, private keys, tokens, or `AO_CLAUDE_CODE_CLI_AUTH` in that
JSON file.

The deployed public GitHub App webhook URL has this shape:

```text
https://<cloud-run-service-url>/github/deployment-protection
```

The deploy workflow does not dispatch the protected live-adapter workflow, post
GitHub deployment protection callbacks itself, or run a live adapter. It only
deploys and health-checks the webhook service.

Before dispatching or relying on this deploy path, run the metadata-only
bootstrap attestation:

```bash
python3 scripts/policy_service_cloud_run_bootstrap_attest.py \
  --artifact-path /tmp/policy-service-cloud-run-bootstrap-attestation.v1.json \
  --output text \
  --fail-on-blocked
```

That attestation checks only GitHub repository variable handles with
`gh variable list --json name,updatedAt`. It does not read variable values,
does not access Secret Manager, does not prove Google Cloud Workload Identity
or Cloud Run permissions, does not deploy the service, and does not post a
GitHub deployment protection callback. Missing repository variables mean the
Cloud Run deployment must stay blocked.

## Runtime

Required hosting secrets:

```text
AO_LIVE_ADAPTER_GATE_WEBHOOK_SECRET
AO_GITHUB_APP_ID
AO_GITHUB_APP_PRIVATE_KEY_PEM
```

or:

```text
AO_GITHUB_APP_PRIVATE_KEY_PATH
```

Optional runtime settings:

```text
PORT
WEB_CONCURRENCY
WEB_THREADS
WEB_TIMEOUT
AO_GITHUB_API_URL
AO_POLICY_SERVICE_MAX_BODY_BYTES
```

The public GitHub App webhook URL must route to:

```text
POST /github/deployment-protection
```

The container health endpoint is:

```text
GET /healthz
```

Do not pass `AO_CLAUDE_CODE_CLI_AUTH` to this service. The protected live
adapter credential remains unavailable to the policy service until a later GPP
slice explicitly permits live execution.

## Local No-Secret Smoke

The local container smoke only builds the image and checks `/healthz`. It does
not configure GitHub App secrets, receive GitHub webhooks, post callback
reviews, dispatch the protected workflow, or execute a live adapter.

```bash
python3 scripts/live_adapter_gate_policy_container_smoke.py \
  --image ao-kernel-live-adapter-gate-policy-service:smoke \
  --build-timeout-seconds 600
```
