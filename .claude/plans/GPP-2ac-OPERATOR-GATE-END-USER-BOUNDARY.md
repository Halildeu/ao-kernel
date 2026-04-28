# GPP-2ac - Operator Gate and End-User Onboarding Boundary

**Status:** closeout candidate
**Date:** 2026-04-28
**Authority:** `origin/main` at `14608b2`
**Issue:** [#551](https://github.com/Halildeu/ao-kernel/issues/551)
**Branch:** `codex/gpp-2ac-end-user-boundary`
**Worktree:** `/Users/halilkocoglu/Documents/ao-kernel-gpp-2ac-end-user-boundary`
**Program head:** `GPP-2` remains blocked on operator-owned hosted callback
evidence
**Support impact:** none
**Runtime impact:** no Cloud Run deployment, no GitHub callback post, no
protected workflow dispatch, no live adapter call

## 1. Purpose

GPP-2t and GPP-2ab made the deployment-protection policy service deployable,
but they also exposed a product boundary problem: asking every product user to
create Cloud Run, a vault, a webhook endpoint, a GitHub App private key, and a
deployment protection service would make onboarding too complex.

This slice records the boundary. The GPP-2 policy service is operator-owned
platform infrastructure. End users must not self-host it to use the product.
GPP-2 stays blocked until the operator-owned service has hosted callback
evidence.

Decision:

```text
operator_owned_gate_end_user_onboarding_boundary_recorded_no_support_widening
```

## 2. Boundary

Operator-owned platform infrastructure:

1. `ao-kernel-live-adapter-gate` GitHub App deployment protection policy
   service hosting.
2. Webhook secret storage and GitHub App private-key storage.
3. GitHub deployment protection callback authority.
4. Hosted endpoint health evidence and callback review evidence.
5. Any Cloud Run, Artifact Registry, Secret Manager, or equivalent hosting
   bootstrap chosen by the operator.

End-user onboarding:

1. install the product's GitHub App or equivalent product connector;
2. select repositories;
3. optionally add explicit repo-local configuration such as `.ao/config.yml`;
4. use repo-intelligence features through read-only, explicit, auditable
   workflow surfaces.

Not allowed:

1. require a product end user to create a Cloud Run project;
2. require a product end user to manage a vault or secret manager;
3. require a product end user to paste or host a GitHub App private key;
4. require a product end user to expose a deployment-protection webhook;
5. treat a product end-user account as release authority.

## 3. Current Evidence

The current metadata-only bootstrap check remains blocked:

```text
overall_status: blocked
missing_repository_variables: GCP_PROJECT_ID, GCP_WORKLOAD_IDENTITY_PROVIDER, GCP_SERVICE_ACCOUNT
cloud_oidc_bootstrap_attested: false
cloud_run_deploy_executed: false
secret_value_readback: false
github_callback_post: false
live_adapter_execution: false
support_widening: false
production_platform_claim: false
```

That evidence is operator bootstrap evidence only. It does not become a user
setup checklist, and it does not block read-only repo-intelligence onboarding
design work that avoids live-adapter execution and support widening.

## 4. Product Direction

The next product-facing path is repo intelligence, not asking users to host the
GPP-2 gate. GPP-5 can proceed only within these boundaries:

1. explicit opt-in ingestion;
2. read-only workflow context surfaces;
3. no hidden root export, MCP feed, or context compiler auto-feed;
4. no live adapter execution;
5. no support widening or production-platform claim.

This keeps GitHub in the loop: the user-facing product still uses GitHub App
installation, repository selection, repository permissions, workflow evidence,
and branch/protection signals. GitHub is not bypassed. The difference is that
the deployment-protection service is platform infrastructure operated for the
product, not infrastructure each customer must assemble.

## 5. Current Decision

Resolved by this slice:

1. GPP-2 gate hosting is operator-owned platform infrastructure;
2. end-user onboarding must not require Cloud Run, vault, webhook, or GitHub
   App private-key setup;
3. repo-intelligence product onboarding may be prioritized as read-only and
   explicit opt-in work while GPP-2 remains blocked;
4. GitHub remains the integration and governance surface for install, repo
   selection, permissions, workflow evidence, and branch/protection state.

Still blocked:

1. Google Cloud OIDC trust is not proven;
2. Secret Manager objects are not proven;
3. hosted policy service evidence is not present;
4. the GitHub App webhook URL is not proven configured to a hosted endpoint;
5. no real GitHub deployment callback review has been posted by the hosted
   service;
6. no new protected workflow evidence artifacts exist after policy response.

Still closed:

1. `live_execution_allowed=false`;
2. `support_widening=false`;
3. `production_platform_claim=false`.

## 6. Validation

```bash
python3 -m json.tool .claude/plans/gpp_status.v1.json
python3 -m pytest tests/test_gpp_next.py -q
python3 -m ruff check tests/test_gpp_next.py
python3 scripts/gpp_next.py
git diff --check
```

Expected closeout decision:

```text
operator_owned_gate_end_user_onboarding_boundary_recorded_no_support_widening
```

Recorded closeout decision:

```text
operator_owned_gate_end_user_onboarding_boundary_recorded_no_support_widening
```
