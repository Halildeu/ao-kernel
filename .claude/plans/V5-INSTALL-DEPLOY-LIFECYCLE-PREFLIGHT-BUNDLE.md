# V5 Install Deploy Lifecycle Preflight Bundle

**Status:** current-state preflight evidence / not final release authority
**Work package:** E-9-1
**Parent matrix:** `.claude/plans/V5-PRODUCTION-READINESS-MATRIX-BLOCKER.md`
**Schema:** `ao_kernel/defaults/schemas/v5-install-deploy-lifecycle-preflight-bundle.schema.v1.json`
**Fixture:** `tests/fixtures/epic9/v5-install-deploy-lifecycle-preflight.current.json`

This document records the current state of the
`install_deploy_lifecycle_smoke` dimension in the V5 production-readiness
matrix. It binds the existing install, deployment, operator-runbook, Helm,
publish workflow, and migration-guide evidence into one machine-checkable
preflight artifact.

## Non-Authority Boundary

This bundle does not authorize:

- support widening;
- production platform claims;
- live adapter execution;
- final v5.0.0 release tagging or publishing;
- opening PR-Xfinal;
- treating local packaging smoke or docs tests as release-artifact smoke;
- treating Helm render/runbook evidence as a production deployment claim.

The current bundle pins `final_release_bound=false`,
`support_widening=false`, `production_platform_claim=false`, and
`live_adapter_execution=false`.

## Current Preflight Evidence

| Surface | Current evidence | Boundary |
|---|---|---|
| Standalone install smoke | `scripts/packaging_smoke.py`, `.github/workflows/test.yml`, `tests/test_ri7_scan_index_query_packaging_smoke_invariant.py` | proves wheel-installed smoke and repo-intelligence CLI packaging path; not bound to a v5.0.0 release artifact |
| Deployment guide | `docs/PRODUCTION-DEPLOYMENT-GUIDE.md`, `tests/test_production_deployment_guide.py` | covers standalone, Docker, and Kubernetes patterns while explicitly keeping guard flags false |
| Operator runbooks | `docs/OPERATOR-RUNBOOK.md`, `docs/operator-runbooks/README.md`, `docs/operator-runbooks/operator-action-checklist.v1.json`, `tests/test_operator_runbook.py`, `tests/test_operator_runbooks.py` | records operator-owned rollback, tag revert, pause, emergency stop, incident, and publishing actions; not executed by agents |
| Helm lifecycle | `deploy/helm/ao-kernel/templates/deployment.yaml`, `deploy/helm/ao-kernel/tests/deployment_test.yaml`, `docs/HELM-TESTING.md` | render/test surface is present and default-safe; operator-run Helm plugin smoke is not CI release evidence |
| Publish lifecycle | `.github/workflows/publish.yml`, `tests/test_publish_workflow.py`, `docs/operator-runbooks/01-pypi-publish.md` | publish workflow has tag guard, trusted-publishing environment, and strict dist globs; no v5.0.0 tag or publish evidence yet |
| Migration guide | `docs/MIGRATION-V5.md`, `tests/test_migration_v5_doc.py` | planned upgrade/downgrade path and guard-flag discipline are documented; v5.0.0 remains unreleased |

## Residual Missing Evidence

PR-Xfinal remains blocked for this dimension until a later operator-bound
supersession provides:

- v5.0.0 tag evidence;
- PyPI publish evidence for the v5.0.0 release artifact;
- final standalone install smoke against that release artifact;
- final Docker or container image smoke bound to that release artifact;
- final Kubernetes/Helm deploy lifecycle smoke bound to the promoted artifact;
- rollback and downgrade smoke from the promoted artifact back to the supported
  baseline.

This is intentionally a preflight artifact. It makes the existing
install/deploy lifecycle surface auditable without changing the production
claim gate.
