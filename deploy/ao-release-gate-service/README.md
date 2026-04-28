# AO Release Gate Service Container

This container packages the GPP-2w WSGI runtime for the `ao-release-gate`
GitHub App check-run service.

It is not a merge runner and it is not a live-adapter runner. It only hosts:

```text
ao_kernel.ao_release_gate_runtime:application
```

## Build

```bash
docker build \
  -f deploy/ao-release-gate-service/Dockerfile \
  -t ao-kernel-ao-release-gate-service:local \
  .
```

## Published Image

The repository publication workflow builds this same Dockerfile, runs the
no-secret `/healthz` smoke, and publishes trusted non-PR builds to GHCR:

```text
ghcr.io/halildeu/ao-kernel-ao-release-gate-service:sha-<commit>
ghcr.io/halildeu/ao-kernel-ao-release-gate-service:main
```

Use the immutable `sha-<commit>` tag for hosted deployments whenever possible.
If the hosting provider cannot pull the package anonymously, configure a GHCR
read token through that provider's secret manager. Do not bake registry tokens
or runtime secrets into the image.

## Runtime

Required hosting secrets:

```text
AO_RELEASE_GATE_WEBHOOK_SECRET
AO_GITHUB_APP_ID
AO_GITHUB_APP_PRIVATE_KEY_PEM
```

or:

```text
AO_GITHUB_APP_PRIVATE_KEY_PATH
```

Operator-owned internal hosts may resolve the same runtime secrets from the
ao-kernel secrets provider interface instead of injecting secret values
directly. Configure a supported provider such as `vault_stub` or
`hashicorp_vault` with provider-local credentials, then pass secret ids:

```text
SECRETS_PROVIDER=hashicorp_vault
VAULT_ADDR=<operator vault URL>
VAULT_TOKEN=<operator vault token>
VAULT_SECRET_MOUNT=secret
AO_RELEASE_GATE_WEBHOOK_SECRET_ID=gpp2/release-gate/webhook-secret
AO_GITHUB_APP_PRIVATE_KEY_PEM_ID=gpp2/github/private-key-pem
```

For local operator rehearsals, `SECRETS_PROVIDER=vault_stub` reads
`.secrets/vault.json` from the service working directory. That file is local
operator material and must not be committed or copied into PRs, issues, logs,
or chat.

Optional runtime settings:

```text
PORT
WEB_CONCURRENCY
WEB_THREADS
WEB_TIMEOUT
AO_GITHUB_API_URL
AO_RELEASE_GATE_GPP_STATUS_PATH
AO_RELEASE_GATE_MAX_BODY_BYTES
```

The public GitHub App webhook URL must route to:

```text
POST /github/ao-release-gate
```

The container health endpoint is:

```text
GET /healthz
```

Do not pass `AO_CLAUDE_CODE_CLI_AUTH` to this service. The release gate posts
dry-run check-runs only after it is explicitly hosted and configured with
GitHub App runtime secrets; this container package alone is not release
authority and does not change branch protection.

The internal vault path changes only how runtime secret values are resolved by
the operator-owned hosted service. It does not remove the need for a public
HTTPS route that GitHub can reach, a configured GitHub App webhook URL, real PR
dry-run check-run evidence, and a later branch-protection/ruleset cutover.

## Autonomous Cloud Run Deployment

The repository deploy workflow can mirror the immutable GHCR image into Google
Artifact Registry, deploy it to Cloud Run, health-check `/healthz`, and upload
deploy evidence:

```text
.github/workflows/ao-release-gate-deploy-cloud-run.yml
```

Required repository variables:

```text
GCP_PROJECT_ID
GCP_WORKLOAD_IDENTITY_PROVIDER
GCP_SERVICE_ACCOUNT
GCP_CLOUD_RUN_REGION
GCP_ARTIFACT_REGISTRY_LOCATION
GCP_ARTIFACT_REGISTRY_REPOSITORY
RELEASE_GATE_SERVICE_NAME
AO_RELEASE_GATE_GITHUB_APP_ID
AO_RELEASE_GATE_WEBHOOK_SECRET_NAME
AO_RELEASE_GATE_GITHUB_APP_PRIVATE_KEY_SECRET_NAME
```

Optional repository variables:

```text
AO_RELEASE_GATE_WEBHOOK_SECRET_VERSION
AO_RELEASE_GATE_GITHUB_APP_PRIVATE_KEY_SECRET_VERSION
```

`AO_RELEASE_GATE_WEBHOOK_SECRET_NAME` and
`AO_RELEASE_GATE_GITHUB_APP_PRIVATE_KEY_SECRET_NAME` are Secret Manager object
names, not secret values. The workflow must not read those values back. Cloud
Run resolves them at runtime into:

```text
AO_RELEASE_GATE_WEBHOOK_SECRET
AO_GITHUB_APP_PRIVATE_KEY_PEM
```

To provision those repository variables without using the GitHub UI, generate a
local template, fill it with non-secret values, dry-run it, then apply it:

```bash
python3 scripts/ao_release_gate_cloud_run_repo_variables.py \
  --write-template /tmp/ao-release-gate-cloud-run-repo-variables.json
```

```bash
python3 scripts/ao_release_gate_cloud_run_repo_variables.py \
  --config-json /tmp/ao-release-gate-cloud-run-repo-variables.json \
  --dry-run \
  --output text
```

```bash
python3 scripts/ao_release_gate_cloud_run_repo_variables.py \
  --config-json /tmp/ao-release-gate-cloud-run-repo-variables.json \
  --output text
```

The tool validates required handles, rejects unknown variables, refuses common
credential-shaped values, and sends values to `gh variable set` through stdin so
they are not placed in the command line or rendered in stdout. Do not put
webhook secrets, private keys, tokens, or `AO_CLAUDE_CODE_CLI_AUTH` in that
JSON file.

Before dispatching or relying on the deploy workflow, run the metadata-only
bootstrap attestation:

```bash
python3 scripts/ao_release_gate_cloud_run_bootstrap_attest.py \
  --artifact-path /tmp/ao-release-gate-cloud-run-bootstrap-attestation.v1.json \
  --output text \
  --fail-on-blocked
```

That attestation checks only GitHub repository variable handles with
`gh variable list --json name,updatedAt`. It does not read variable values,
does not access Secret Manager, does not prove Google Cloud Workload Identity
or Cloud Run permissions, does not deploy the service, does not post a
check-run, and does not change branch protection. Missing repository variables
mean the Cloud Run deployment must stay blocked.

The deploy workflow proves only that the service revision is hosted and
`GET /healthz` responds. It does not prove that the GitHub App webhook URL is
configured, does not post a check-run, does not collect real PR evidence, does
not change branch protection, and does not enable merge authority.

## Local No-Secret Smoke

The local container smoke only builds the image and checks `/healthz`. It does
not configure GitHub App secrets, receive GitHub webhooks, post check-runs,
merge pull requests, change branch protection, or execute a live adapter.

```bash
python3 scripts/ao_release_gate_container_smoke.py \
  --image ao-kernel-ao-release-gate-service:smoke \
  --build-timeout-seconds 600
```
