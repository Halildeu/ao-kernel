# GPP-2o - Deployment Protection Policy Decision Core

**Status:** closeout candidate
**Date:** 2026-04-28
**Authority:** `origin/main` at `3297cc2`
**Issue:** [#525](https://github.com/Halildeu/ao-kernel/issues/525)
**Branch:** `codex/gpp-2o-policy-decision-core`
**Worktree:** `/Users/halilkocoglu/Documents/ao-kernel-gpp-2o-policy-decision-core`
**Program head:** `GPP-2` blocked on policy service deployment/configuration
**Support impact:** none
**Runtime impact:** no live adapter call; no secret context use

## 1. Purpose

GPP-2n proved that the protected workflow reaches
`ao-kernel-live-adapter-gate`, but the GitHub App deployment-protection service
did not return a decision. This slice adds the repo-owned decision core that a
GitHub App webhook or equivalent policy service can call before reviewing the
deployment callback.

Decision:

```text
policy_decision_core_ready_service_not_deployed
```

This slice does not deploy a webhook, does not call GitHub's deployment review
API, does not invoke `claude`, does not reference
`secrets.AO_CLAUDE_CODE_CLI_AUTH`, does not read secret values, does not widen
support, and does not claim production-platform readiness.

## 2. Implemented Surface

Code:

1. `ao_kernel/live_adapter_gate_policy.py`
   - extracts GitHub `deployment_protection_rule` webhook-shaped fields;
   - requires service-enriched verified context before approval;
   - rejects missing, malformed, wrong repository, wrong environment, wrong
     event, wrong ref, missing SHA, missing callback URL, missing workflow
     identity, pull-request context, missing prerequisite attestation, live
     execution signals, support widening signals, or production-claim signals;
   - emits `approve_contract_gate` only for the design-only protected gate path;
   - always emits `live_execution_allowed=false`,
     `support_widening_allowed=false`, and
     `production_platform_claim_allowed=false`.
2. `scripts/live_adapter_gate_policy_decision.py`
   - reads a webhook/enriched payload JSON;
   - writes `live-adapter-gate-policy-decision.v1.json`;
   - renders JSON or text for local validation;
   - optionally exits non-zero on reject with `--fail-on-reject`.
3. `tests/test_live_adapter_gate_policy.py`
   - covers the contract-only approval path;
   - covers raw webhook fail-closed behavior;
   - covers wrong repo/ref, missing callback, live execution signal, and
     pull-request context rejection;
   - covers CLI artifact writing.

## 3. Policy Interpretation

Raw GitHub webhook fields are intentionally not enough for approval. The
deployment-protection service must enrich the payload with verified context
from trusted sources before it can produce `approve_contract_gate`.

Required approved context:

1. repository is `Halildeu/ao-kernel`;
2. environment is `ao-kernel-live-adapter-gate`;
3. event is `workflow_dispatch`;
4. ref normalizes to `main`;
5. SHA is present;
6. deployment callback URL is present and usable;
7. workflow identity is `Live Adapter Gate` or
   `.github/workflows/live-adapter-gate.yml`;
8. no pull-request context is present;
9. protected prerequisite attestation is ready;
10. `live_execution_allowed=false`;
11. `support_widening_allowed=false`;
12. `production_platform_claim_allowed=false`.

Any missing or non-matching input produces `reject`. That rejection is a valid
fail-closed policy response, but it does not complete GPP-2. GPP-2 still needs
a deployed/configured GitHub App webhook that posts the decision to GitHub's
deployment-protection review callback and then new protected workflow evidence
from `main`.

## 4. Current Decision

Resolved by this slice:

1. repo-owned deterministic policy decision core exists;
2. local CLI can evaluate webhook/enriched payloads;
3. raw/unverified deployment-protection payloads reject fail-closed;
4. contract-only approval remains explicitly separate from live adapter
   execution.

Still blocked:

1. no repo-owned webhook server is deployed or configured behind the installed
   GitHub App;
2. no GitHub deployment callback review has been posted by the policy service;
3. no new protected workflow evidence artifacts exist after policy response;
4. live adapter execution remains disabled.

Still closed:

1. `live_execution_allowed=false`;
2. `support_widening=false`;
3. `production_platform_claim=false`.

## 5. Next Required Action

Deploy or configure the `ao-kernel-live-adapter-gate` GitHub App
deployment-protection policy service so it:

1. receives `deployment_protection_rule` callbacks;
2. enriches the payload with trusted workflow/prerequisite context;
3. evaluates that context with `ao_kernel.live_adapter_gate_policy` or an
   equivalent fail-closed policy;
4. posts an explicit approved/rejected result to the deployment callback URL;
5. records response evidence without secret value exposure.

Only after that service is expected to respond should the protected workflow
evidence slice be rerun from `main`.

## 6. Validation

```bash
python3 -m json.tool .claude/plans/gpp_status.v1.json
pytest -q tests/test_live_adapter_gate_policy.py
pytest -q tests/test_gpp_next.py
python3 scripts/gpp_next.py
git diff --check
```

Expected closeout decision:

```text
policy_decision_core_ready_service_not_deployed
```

Recorded closeout decision:

```text
policy_decision_core_ready_service_not_deployed
```
