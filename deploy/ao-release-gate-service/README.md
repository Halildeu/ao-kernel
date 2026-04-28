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

## Local No-Secret Smoke

The local container smoke only builds the image and checks `/healthz`. It does
not configure GitHub App secrets, receive GitHub webhooks, post check-runs,
merge pull requests, change branch protection, or execute a live adapter.

```bash
python3 scripts/ao_release_gate_container_smoke.py \
  --image ao-kernel-ao-release-gate-service:smoke \
  --build-timeout-seconds 600
```
