# V5 Security/SBOM/License Preflight Bundle

**Status:** current-state preflight evidence / not final release authority
**Work package:** E-9-1
**Parent matrix:** `.claude/plans/V5-PRODUCTION-READINESS-MATRIX-BLOCKER.md`
**Schema:** `ao_kernel/defaults/schemas/v5-security-sbom-license-preflight-bundle.schema.v1.json`
**Fixture:** `tests/fixtures/epic9/v5-security-sbom-license-preflight.current.json`

This document records the current state of the `security_sbom_license_scans`
dimension in the V5 production-readiness matrix. It binds existing committed
security workflows, SBOM tooling, and license-compliance inventory into one
machine-checkable preflight artifact.

## Non-Authority Boundary

This bundle does not authorize:

- support widening;
- production platform claims;
- live adapter execution;
- final release tagging or publishing;
- opening PR-Xfinal;
- treating advisory security workflows as required release checks.

The current bundle pins `final_release_bound=false`, `support_widening=false`,
`production_platform_claim=false`, and `live_adapter_execution=false`.

## Current Preflight Evidence

| Surface | Current evidence | Boundary |
|---|---|---|
| CodeQL | `.github/workflows/codeql.yml` | configured advisory workflow; not final release-bound evidence |
| Trivy | `.github/workflows/trivy.yml` | configured advisory workflow; exit code remains advisory |
| SBOM | `scripts/generate_sbom.py`, `tests/test_sbom_generation.py`, `tests/fixtures/sample-sbom.cdx.json` | generator and validation exist; no final v5 release SBOM artifact yet |
| License compliance | `docs/license-compliance/license-compliance-policy.v1.json`, `docs/license-compliance/dependency-license-inventory.v1.json` | deny count is zero, but review-required entries still require operator disposition |

## Residual Missing Evidence

PR-Xfinal remains blocked for this dimension until a later operator-bound
supersession provides:

- final v5 release-bound SBOM artifact;
- final release-bound license inventory generated from that release SBOM;
- final security scan evidence bundle bound to the PR-Xfinal merge candidate;
- operator disposition for review-required license entries.

This is intentionally a preflight artifact. It makes the existing security
surface auditable without changing the production claim gate.
