# V5 Docs and Runbooks Preflight Bundle

**Status:** current-state preflight evidence / not final release authority
**Work package:** E-9-1
**Parent matrix:** `.claude/plans/V5-PRODUCTION-READINESS-MATRIX-BLOCKER.md`
**Schema:** `ao_kernel/defaults/schemas/v5-docs-runbooks-preflight-bundle.schema.v1.json`
**Fixture:** `tests/fixtures/epic9/v5-docs-runbooks-preflight.current.json`

This document records the current state of the `docs_runbooks` dimension in
the V5 production-readiness matrix. It binds deployment, operator, rollback,
API-reference, migration, incident-response, and vendor-escalation evidence
into one machine-checkable preflight artifact.

## Non-Authority Boundary

This bundle does not authorize:

- support widening;
- production platform claims;
- live adapter execution;
- final PR-Xfinal claim-language sync;
- v5.0.0 release notes publication;
- final v5.0.0 runbook update;
- hosted API docs publication;
- treating docs tests as release-artifact evidence.

The current bundle pins `final_claim_language_synced=false`,
`final_release_notes_present=false`, `v5_runbook_finalized=false`,
`support_widening=false`, `production_platform_claim=false`, and
`live_adapter_execution=false`.

## Current Preflight Evidence

| Surface | Current evidence | Boundary |
|---|---|---|
| Deployment guide | `docs/PRODUCTION-DEPLOYMENT-GUIDE.md`, `tests/test_production_deployment_guide.py` | covers standalone, Docker, and Kubernetes patterns while keeping guard flags false |
| Operator runbook | `docs/OPERATOR-RUNBOOK.md`, `tests/test_operator_runbook.py` | covers rollback, tag revert, pause, emergency stop, and incident triage; operator-bound supersession remains required |
| Operator action runbooks | `docs/operator-runbooks/README.md`, `docs/operator-runbooks/operator-action-checklist.v1.json`, `ao_kernel/defaults/schemas/operator-action-checklist.schema.v1.json`, `tests/test_operator_runbooks.py` | records operator-required actions without agent execution or committed credential material |
| Rollback procedure | `docs/ROLLBACK-RUNBOOK.md`, `docs/ROLLBACK.md` | documents archive-tag recovery, no destructive history rewrite, operator ruleset authority, and forward fix or revert PR discipline |
| API reference | `docs/api/README.md`, `docs/api/conf.py`, `docs/api/index.rst`, `tests/test_sphinx_api_reference_scaffold.py` | Sphinx scaffold exists and excludes private/live-provider surfaces; build and hosted docs remain operator decisions |
| Migration guide | `docs/MIGRATION-V5.md`, `tests/test_migration_v5_doc.py` | planned v5 path and downgrade pin exist; the release is not shipped |
| Incident response | `docs/incident-response/README.md`, severity matrix/schema, escalation policy, incident template, `tests/test_incident_response_playbook.py` | process contract only; not a contractual SLA and no live dispatch |
| Vendor escalation | `docs/incident-response/vendor-escalation-matrix.v1.json`, `docs/incident-response/vendor-escalation-runbook.v1.md`, `tests/test_vendor_escalation_matrix.py` | operator-owned external handoff; no vendor SLA promise and no committed PII/contact material |

## Residual Missing Evidence

PR-Xfinal remains blocked for this dimension until a later operator-bound
supersession provides:

- final v5.0.0 release notes;
- final PR-Xfinal claim-language sync;
- final v5.0.0 runbook update;
- hosted API docs publication decision;
- operator-attested final docs review.

This is intentionally a preflight artifact. It makes the existing docs and
runbook surface auditable without changing the production claim gate.
