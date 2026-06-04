# V5 Bypassless Release Governance Preflight Bundle

**Status:** current-state preflight / not promotion authority
**Work package:** E-9-1
**Dimension:** `bypassless_release_governance` (production readiness matrix dimension 9)
**Parent blocker:** `.claude/plans/V5-PRODUCTION-READINESS-MATRIX-BLOCKER.md`
**Schema:** `ao_kernel/defaults/schemas/v5-bypassless-governance-preflight-bundle.schema.v1.json`
**Fixture:** `tests/fixtures/epic9/v5-bypassless-governance-preflight.current.json`

This bundle records the merge-governance controls that are **already active** in
the current repository, binding them into one machine-checkable current-state
artifact for the Gate C (`production_platform_claim`) readiness matrix. Unlike
support/surface dimensions, bypassless governance is not a future widening — the
controls below are in force today. The bundle keeps the dimension `partial`
because the final ruleset source-pin and required-check uniqueness evidence are
bound to the future operator PR-Xfinal.

## Non-Authority Boundary

This document and fixture do not authorize:

- support widening;
- production platform claims;
- live adapter execution;
- partial guard-flag flips;
- v5.0.0 tag or publish;
- branch-protection or ruleset relaxation;
- opening PR-Xfinal.

All three guard flags remain `const false`. AI output is evidence only. Release
authority remains the repo-owned `ao-release-gate` required checks plus the
GitHub branch ruleset.

## Current-State Governance Controls (active today)

| Control | Current state | Verifiable source |
|---|---|---|
| `ao-release-gate` required checks source-pinned | active | branch ruleset requires `ao-release-gate-technical` + `ao-release-gate-review` |
| Empty bypass actors | active | branch ruleset `bypass_actors` count is 0 |
| Autonomous merge trail for low-risk changes | active | low-risk PRs merge via local AI review evidence + `operator_may_merge`, no `--admin` |
| Cross-provider review for guarded changes | active | high-risk PRs carry provider-distinct (`implementer != reviewer`) cross-AI AGREE evidence |

Governance source documents: `.github/REPO-GOVERNANCE.md`,
`.claude/plans/PRODUCTION-HARDENING-PROGRAM-STATUS.md`,
`.claude/plans/gpp_status.v1.json`.

## Residual Evidence Bound to PR-Xfinal

The dimension stays incomplete until the future operator-bound PR-Xfinal supplies:

1. PR-Xfinal pre-merge and post-merge ruleset source-pin SHA-256 evidence;
2. final required-check name uniqueness and source-collision evidence bound to
   PR-Xfinal (same-name external check runs cannot satisfy the gate).

## Mirror Issues

`#775`, `#776`, `#782`, `#895` — GitHub issues are a visibility mirror; repo
artifacts remain the SSOT.
