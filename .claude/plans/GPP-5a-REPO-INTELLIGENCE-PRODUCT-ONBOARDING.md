# GPP-5a - Repo-Intelligence Product Onboarding Contract

**Issue:** [#553](https://github.com/Halildeu/ao-kernel/issues/553)

**Decision:** `repo_intelligence_product_onboarding_contract_ready_no_support_widening`

**Status:** completed / no support widening

**Date:** 2026-04-28

## Scope

Define the product-facing repo-intelligence onboarding contract while GPP-2
remains blocked. This slice does not start live-adapter runtime binding, host
gate services, configure branch protection, or widen support.

## Decision

Repo-intelligence onboarding for product users is limited to:

1. Install the GitHub App.
2. Select the repositories the app may inspect.
3. Optionally add repo-local configuration at an approved `.ao/*` path.

The following remain operator-owned platform infrastructure and must not be
required from product users:

1. Cloud Run project or service hosting.
2. Vault, Secret Manager, or secret broker setup.
3. Webhook endpoint hosting.
4. GitHub App private-key handling.
5. `ao-release-gate` check-run service hosting.
6. Deployment-protection policy service hosting.
7. Branch-protection cutover.

## Evidence

This work package adds:

1. Runtime validator:
   `ao_kernel/_internal/repo_intelligence/product_onboarding.py`
2. Public facade:
   `ao_kernel.repo_intelligence.validate_repo_intelligence_product_onboarding`
3. Contract schema:
   `ao_kernel/defaults/schemas/repo-intelligence-product-onboarding.schema.v1.json`
4. Behavior tests:
   `tests/test_repo_intelligence_product_onboarding.py`

The validator accepts only a read-only, explicit opt-in onboarding shape. It
blocks end-user Cloud Run, vault, webhook, private-key, deployment-protection
service, and release-gate service requirements. It also blocks hidden prompt
injection, MCP exposure, root export requirements, context-compiler auto-feed,
implicit vector/artifact writes, live-adapter execution, support widening, and
production platform claims.

## Non-Goals

1. No GitHub App installation automation is added in this slice.
2. No GitHub API calls are made by the validator.
3. No repository artifacts are written by the validator.
4. No workflow runtime ingestion or context compiler wiring is enabled.
5. No GPP-2 deployment-protection or release-gate hosting evidence is claimed.

## Exit Decision

`repo_intelligence_product_onboarding_contract_ready_no_support_widening`

GPP-5 can continue from this contract into explicit read-only workflow
integration, but GPP-2 remains blocked and the program still forbids support
widening or production platform claims until a later explicit promotion
decision.
