# GPP-2p - Deployment Protection Policy Webhook Service Scaffold

**Status:** closeout candidate
**Date:** 2026-04-28
**Authority:** `origin/main` at `c762523`
**Issue:** [#527](https://github.com/Halildeu/ao-kernel/issues/527)
**Branch:** `codex/gpp-2p-policy-webhook-service`
**Worktree:** `/Users/halilkocoglu/Documents/ao-kernel-gpp-2p-policy-webhook-service`
**Program head:** `GPP-2` blocked on policy service deployment/configuration
**Support impact:** none
**Runtime impact:** no live adapter call; no secret context use; no GitHub
callback POST from tests or default CLI

## 1. Purpose

GPP-2o added a deterministic deployment-protection policy decision core.
GPP-2 still needs a service boundary that can receive GitHub App webhooks,
verify the delivery, restrict the event type, evaluate the policy, and prepare
the GitHub custom deployment protection review callback.

Decision:

```text
policy_webhook_service_scaffold_ready_service_not_deployed
```

This slice does not deploy a webhook, does not call GitHub's deployment review
API, does not invoke `claude`, does not reference
`secrets.AO_CLAUDE_CODE_CLI_AUTH`, does not read secret values, does not widen
support, and does not claim production-platform readiness.

## 2. Implemented Surface

Code:

1. `ao_kernel/live_adapter_gate_policy_service.py`
   - verifies GitHub webhook `X-Hub-Signature-256` values using HMAC-SHA256;
   - accepts only `X-GitHub-Event: deployment_protection_rule`;
   - rejects malformed JSON before policy evaluation;
   - calls `ao_kernel.live_adapter_gate_policy` for the decision;
   - builds the GitHub callback request shape:
     `POST {deployment_callback_url}` with `environment_name`, `state`, and
     `comment`;
   - never performs the network POST itself.
2. `scripts/live_adapter_gate_policy_service_smoke.py`
   - reads a local webhook/enriched payload fixture;
   - verifies or locally signs fixture delivery headers;
   - writes `live-adapter-gate-policy-service-callback-request.v1.json`;
   - supports unsigned fixture evaluation only behind
     `--allow-unsigned-fixture`.
3. `tests/test_live_adapter_gate_policy_service.py`
   - pins the official GitHub HMAC-SHA256 example vector;
   - covers missing signature, wrong event, malformed JSON, raw webhook reject,
     verified-context approval, and CLI artifact writing.

## 3. Policy Interpretation

The service scaffold deliberately separates these concerns:

1. webhook authenticity;
2. GitHub App event scope;
3. JSON payload shape;
4. policy decision;
5. callback request construction;
6. runtime callback posting.

Only the first five are implemented by this repo slice. Runtime deployment
must attach the webhook secret and GitHub App authentication outside the repo
and execute the returned callback request. That external deployment remains the
current GPP-2 blocker.

The scaffold can produce a rejected callback request for a valid, signed
`deployment_protection_rule` payload even when policy context is missing. That
is intentional: a service should respond explicitly with `rejected` instead of
leaving GitHub Actions waiting indefinitely.

## 4. Current Decision

Resolved by this slice:

1. webhook signature verification is deterministic and fail-closed;
2. non-`deployment_protection_rule` events fail before policy evaluation;
3. malformed JSON fails before policy evaluation;
4. valid raw callbacks can produce an explicit rejected callback request;
5. verified closed context can produce an approved contract-gate callback
   request;
6. local smoke tooling emits a callback artifact without network side effects.

Still blocked:

1. no hosted webhook endpoint is deployed;
2. no webhook secret is configured in a runtime service;
3. no GitHub App installation token or equivalent app auth is configured in a
   runtime service;
4. no deployment callback review has been posted by the service;
5. no new protected workflow evidence artifacts exist after policy response;
6. live adapter execution remains disabled.

Still closed:

1. `live_execution_allowed=false`;
2. `support_widening=false`;
3. `production_platform_claim=false`.

## 5. Next Required Action

Deploy or configure the `ao-kernel-live-adapter-gate` GitHub App
deployment-protection policy service so it:

1. receives `deployment_protection_rule` callbacks;
2. verifies `X-Hub-Signature-256` with a runtime webhook secret;
3. enriches the payload with trusted workflow/prerequisite context;
4. evaluates that context with the repo-owned policy modules;
5. attaches GitHub App authentication outside the repo;
6. posts the callback request to `deployment_callback_url`;
7. records response evidence without secret value exposure.

Only after that service is expected to respond should the protected workflow
evidence slice be rerun from `main`.

## 6. Validation

```bash
python3 -m json.tool .claude/plans/gpp_status.v1.json
pytest -q tests/test_live_adapter_gate_policy_service.py
pytest -q tests/test_live_adapter_gate_policy.py tests/test_live_adapter_gate_policy_service.py tests/test_gpp_next.py
python3 -m ruff check ao_kernel/live_adapter_gate_policy_service.py scripts/live_adapter_gate_policy_service_smoke.py tests/test_live_adapter_gate_policy_service.py tests/test_gpp_next.py
python3 -m mypy ao_kernel/live_adapter_gate_policy_service.py scripts/live_adapter_gate_policy_service_smoke.py
python3 scripts/gpp_next.py
git diff --check
```

Expected closeout decision:

```text
policy_webhook_service_scaffold_ready_service_not_deployed
```

Recorded closeout decision:

```text
policy_webhook_service_scaffold_ready_service_not_deployed
```
