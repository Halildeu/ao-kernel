# V5 Production Readiness Matrix Blocker

**Status:** current-state blocker / not production authority
**Work package:** E-9-1
**Parent plan:** `.claude/plans/V5-FULL-PRODUCTION-PROMOTION-ROADMAP.md`
**Schema:** `ao_kernel/defaults/schemas/v5-production-readiness-matrix-blocker.schema.v1.json`
**Fixture:** `tests/fixtures/epic9/v5-production-readiness-matrix.current.json`

This document records the current state of the production-platform-claim gate
for the future Epic 9 PR-Xfinal. It makes the roadmap's 9-dimensional
production-readiness matrix machine-checkable while keeping the current
decision fail-closed.

## Non-Authority Boundary

This document and its fixture do not authorize:

- support widening;
- production platform claims;
- live adapter execution;
- opening PR-Xfinal;
- partial guard-flag flips;
- v5.0.0 release/tag/publish.

The current blocker artifact pins `matrix_complete=false`,
`pr_xfinal_open_allowed=false`, `support_widening=false`,
`production_platform_claim=false`, and `live_adapter_execution=false`.

## Current Verdict

The V5 production readiness matrix is **not complete**.

| Dimension | Current status | Reason PR-Xfinal remains blocked |
|---|---|---|
| public support matrix | partial | final v5 public support tier and claim-language sync missing |
| protected real provider live calls | not_ready | 7-day live window and protected environment evidence missing |
| cost/rate/circuit breaker evidence | partial | live cost/breach/rollback evidence missing |
| observability production tunables | partial | final claim-bound observability/alerting evidence missing |
| security/SBOM/license scans | partial | current preflight bundle exists; final release-bound SBOM/license/security bundle missing |
| install/deploy lifecycle smoke | partial | v5.0.0 tag/publish and release-artifact smoke missing |
| multi-tenancy isolation | not_ready | tenant isolation and per-tenant quota/cost evidence missing |
| docs/runbooks | partial | final claim/release wording and runbook updates missing |
| bypassless release governance | partial | PR-Xfinal source-pin/collision evidence missing |

## Relationship To PR-Xfinal

Gate C in `.claude/plans/EPIC-9-FINAL-SUPERSESSION-PR.md` requires the full
9-dimensional production readiness evidence matrix. This blocker artifact is
the current-state v1 form of that gate: it records what exists, what is missing,
and why the production platform claim guard cannot be enabled yet.

A later operator-bound PR-Xfinal may replace this blocker only after all
dimensions can be proven complete with evidence refs and attestors. Until then,
the only safe action is evidence collection under the existing issue refs:

- `#775` live adapter execution;
- `#776` support widening;
- `#782` final promotion decision;
- `#895` all-or-none PR-Xfinal.

## Current Evidence Bundle Cross-Refs

The `security_sbom_license_scans` dimension now has a current-state
security/SBOM/license preflight bundle:

- `.claude/plans/V5-SECURITY-SBOM-LICENSE-PREFLIGHT-BUNDLE.md`
- `tests/fixtures/epic9/v5-security-sbom-license-preflight.current.json`

That bundle binds CodeQL, Trivy, SBOM tooling, and license inventory evidence
without treating them as final release-bound evidence.
