# GPP-2q - Deployable Policy Webhook Runtime

**Status:** closeout candidate
**Date:** 2026-04-28
**Authority:** `origin/main` at `963b210`
**Issue:** [#529](https://github.com/Halildeu/ao-kernel/issues/529)
**Branch:** `codex/gpp-2q-policy-webhook-runtime`
**Worktree:** `/Users/halilkocoglu/Documents/ao-kernel-gpp-2q-policy-webhook-runtime`
**Program head:** `GPP-2` blocked on hosted policy service deployment/configuration
**Support impact:** none
**Runtime impact:** no live adapter call; no `AO_CLAUDE_CODE_CLI_AUTH`
reference; no protected workflow dispatch

## 1. Purpose

GPP-2p added the webhook service boundary, but intentionally stopped before a
hosted runtime could receive GitHub deliveries and post deployment protection
reviews. GPP-2 still needs a deployable service wrapper that can run behind the
`ao-kernel-live-adapter-gate` GitHub App webhook.

Decision:

```text
policy_webhook_runtime_ready_service_not_deployed
```

This slice makes the repo-owned policy service deployable. It does not deploy a
public endpoint, configure a webhook URL, read secret values back, dispatch the
protected workflow, invoke `claude`, widen support, or claim production-platform
readiness.

## 2. Implemented Surface

Code:

1. `ao_kernel/live_adapter_gate_policy_runtime.py`
   - exposes `policy_runtime_wsgi_app` / `application` as a WSGI entrypoint;
   - serves `GET /healthz`;
   - accepts `POST /github/deployment-protection`;
   - reads the webhook secret from `AO_LIVE_ADAPTER_GATE_WEBHOOK_SECRET`;
   - reads GitHub App auth config from `AO_GITHUB_APP_ID` plus either
     `AO_GITHUB_APP_PRIVATE_KEY_PEM` or `AO_GITHUB_APP_PRIVATE_KEY_PATH`;
   - verifies signed GitHub deliveries through the existing GPP-2p service;
   - extracts the GitHub App installation id from the webhook payload;
   - mints an installation access token with a GitHub App JWT;
   - posts the approved or rejected deployment protection callback review;
   - returns only redacted runtime status, never token/private key/secret
     material.
2. `pyproject.toml`
   - adds optional extra `ao-kernel[policy-service]` for `PyJWT[crypto]`.
3. `tests/test_live_adapter_gate_policy_runtime.py`
   - covers approved callback posting for verified closed context;
   - covers rejected callback posting for raw fail-closed webhook payloads;
   - covers missing installation id;
   - covers GitHub App token/callback POST flow without secret echo;
   - covers missing optional dependency reporting;
   - covers WSGI health and bad-signature responses.

## 3. Runtime Contract

Hosted service configuration must provide these environment variables:

```text
AO_LIVE_ADAPTER_GATE_WEBHOOK_SECRET
AO_GITHUB_APP_ID
AO_GITHUB_APP_PRIVATE_KEY_PEM
```

or:

```text
AO_GITHUB_APP_PRIVATE_KEY_PATH
```

Optional:

```text
AO_GITHUB_API_URL
AO_POLICY_SERVICE_MAX_BODY_BYTES
```

The deployment target must install:

```bash
pip install "ao-kernel[policy-service]"
```

Then run a WSGI server against:

```text
ao_kernel.live_adapter_gate_policy_runtime:application
```

The GitHub App webhook URL should point to:

```text
https://<host>/github/deployment-protection
```

The service remains fail-closed:

1. invalid or missing webhook signatures return blocked status;
2. non-`deployment_protection_rule` events return blocked status;
3. malformed JSON returns blocked status;
4. missing installation id blocks callback posting;
5. GitHub token or callback POST failures block the runtime result;
6. policy rejection still posts an explicit `rejected` review when GitHub auth
   is available.

## 4. Current Decision

Resolved by this slice:

1. repo-owned WSGI entrypoint exists for the GitHub App webhook;
2. callback POST execution is implemented with GitHub App installation auth;
3. runtime responses are redacted and do not echo secrets;
4. optional dependency requirements are explicit;
5. fail-closed runtime behavior is covered by tests.

Still blocked:

1. no public hosted endpoint is deployed;
2. GitHub App webhook URL has not been configured to the hosted endpoint;
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

Deploy the WSGI runtime behind the `ao-kernel-live-adapter-gate` GitHub App
webhook and configure the app with:

1. webhook URL `/github/deployment-protection`;
2. webhook secret matching `AO_LIVE_ADAPTER_GATE_WEBHOOK_SECRET`;
3. GitHub App id and private key material stored only in the hosting platform's
   secret manager;
4. `ao-kernel[policy-service]` installed so JWT signing works.

Only after that service is expected to respond should the protected workflow
evidence slice be rerun from `main`.

## 6. Validation

```bash
pytest -q tests/test_live_adapter_gate_policy_runtime.py tests/test_live_adapter_gate_policy_service.py
python3 -m ruff check ao_kernel/live_adapter_gate_policy_runtime.py tests/test_live_adapter_gate_policy_runtime.py pyproject.toml
python3 -m mypy ao_kernel/live_adapter_gate_policy_runtime.py
python3 -m json.tool .claude/plans/gpp_status.v1.json
pytest -q tests/test_live_adapter_gate_policy_runtime.py tests/test_live_adapter_gate_policy_service.py tests/test_gpp_next.py
python3 scripts/gpp_next.py
git diff --check
```

Expected closeout decision:

```text
policy_webhook_runtime_ready_service_not_deployed
```

Recorded closeout decision:

```text
policy_webhook_runtime_ready_service_not_deployed
```
