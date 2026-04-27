# GPP-2r - Policy Webhook Container Deploy Package

**Status:** closeout candidate
**Date:** 2026-04-28
**Authority:** `origin/main` at `132ad14`
**Issue:** [#531](https://github.com/Halildeu/ao-kernel/issues/531)
**Branch:** `codex/gpp-2r-policy-container`
**Worktree:** `/Users/halilkocoglu/Documents/ao-kernel-gpp-2r-policy-container`
**Program head:** `GPP-2` blocked on hosted policy service deployment/configuration
**Support impact:** none
**Runtime impact:** no live adapter call; no GitHub App webhook URL
configuration; no secret value readback

## 1. Purpose

GPP-2q added a deployable WSGI runtime, but the repo still lacked a concrete
container deployment package that a hosting platform can run without inventing
local packaging steps. GPP-2 remains blocked because there is still no public
hosted endpoint configured behind the GitHub App webhook.

Decision:

```text
policy_webhook_container_ready_service_not_hosted
```

This slice makes the service container-buildable and locally health-checkable.
It does not deploy to a public host, configure the GitHub App webhook URL, read
secret values back, dispatch the protected workflow, invoke a live adapter,
widen support, or claim production-platform readiness.

## 2. Implemented Surface

Code and deploy assets:

1. `deploy/live-adapter-gate-policy-service/Dockerfile`
   - builds from `python:3.13-slim`;
   - installs `ao-kernel[policy-service]`;
   - runs `gunicorn` against
     `ao_kernel.live_adapter_gate_policy_runtime:application`;
   - exposes port `8000`;
   - adds a container health check for `/healthz`;
   - runs as a non-root user.
2. `.dockerignore`
   - keeps git metadata, caches, build artifacts, coverage, and logs out of
     the build context.
3. `pyproject.toml`
   - adds `gunicorn` to the `policy-service` optional extra.
4. `scripts/live_adapter_gate_policy_container_smoke.py`
   - builds the container image;
   - runs it on a loopback-only random host port;
   - checks `GET /healthz`;
   - bounds Docker build/run waits with explicit timeouts;
   - reports no secret readback, no GitHub callback POST, and no live adapter
     execution.
5. `tests/test_live_adapter_gate_policy_container.py`
   - pins the Dockerfile runtime entrypoint and no-live-secret boundary;
   - pins container smoke defaults.
6. `.github/workflows/test.yml`
   - runs the no-secret container build and `/healthz` smoke in CI.

## 3. Container Contract

Build:

```bash
docker build \
  -f deploy/live-adapter-gate-policy-service/Dockerfile \
  -t ao-kernel-live-adapter-gate-policy-service:local \
  .
```

No-secret local health smoke:

```bash
python3 scripts/live_adapter_gate_policy_container_smoke.py \
  --image ao-kernel-live-adapter-gate-policy-service:smoke \
  --build-timeout-seconds 600
```

Hosted service configuration still must provide:

```text
AO_LIVE_ADAPTER_GATE_WEBHOOK_SECRET
AO_GITHUB_APP_ID
AO_GITHUB_APP_PRIVATE_KEY_PEM
```

or:

```text
AO_GITHUB_APP_PRIVATE_KEY_PATH
```

The public GitHub App webhook URL must route to:

```text
POST /github/deployment-protection
```

Do not pass `AO_CLAUDE_CODE_CLI_AUTH` to this container. The policy service is
not a live-adapter runner.

## 4. Current Decision

Resolved by this slice:

1. repo-owned container build package exists;
2. hosted WSGI command is explicit and repeatable;
3. no-secret container health smoke exists with bounded Docker waits and CI
   execution;
4. optional server dependency is explicit;
5. deploy runbook documents container usage.

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

Deploy the container to a public hosting platform and configure the
`ao-kernel-live-adapter-gate` GitHub App webhook URL to the hosted
`/github/deployment-protection` endpoint. Runtime secrets must be supplied only
through the hosting provider's secret manager or secret-file mount.

Only after that service is expected to respond should the protected workflow
evidence slice be rerun from `main`.

## 6. Validation

Local validation passed:

```bash
python3 -m json.tool .claude/plans/gpp_status.v1.json
pytest -q tests/test_live_adapter_gate_policy_container.py tests/test_gpp_next.py
python3 -m ruff check ao_kernel/ tests/ scripts/live_adapter_gate_policy_container_smoke.py
python3 -m mypy ao_kernel/ scripts/live_adapter_gate_policy_container_smoke.py
python3 scripts/gpp_next.py
git diff --check
```

Container build/health validation is wired into GitHub Actions as
`policy-container-smoke`:

```bash
python3 scripts/live_adapter_gate_policy_container_smoke.py \
  --image ao-kernel-live-adapter-gate-policy-service:ci \
  --build-timeout-seconds 600 \
  --timeout-seconds 90
```

Local Docker Desktop validation on this workstation was attempted with a short
timeout and failed while resolving Docker Hub metadata for `python:3.13-slim`;
the bounded timeout behavior is now explicit. This local Docker pull failure is
not protected workflow evidence and does not post GitHub deployment callback
reviews.

Expected closeout decision:

```text
policy_webhook_container_ready_service_not_hosted
```

Recorded closeout decision:

```text
policy_webhook_container_ready_service_not_hosted
```
