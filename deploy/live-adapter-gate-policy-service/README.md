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
