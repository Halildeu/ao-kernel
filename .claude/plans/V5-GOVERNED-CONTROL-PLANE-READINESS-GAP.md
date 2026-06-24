# V5 / Governed Control-Plane Readiness Gap Plan

**Status:** current-state planning note / not release authority  
**Date:** 2026-06-25  
**Authority inputs:**

- `.claude/plans/V5-FULL-PRODUCTION-PROMOTION-ROADMAP.md`
- `.claude/plans/V5-PRODUCTION-READINESS-MATRIX-BLOCKER.md`
- `.claude/plans/EPIC-9-PR-XFINAL-SUPERSESSION-CLOSEOUT.md`
- `scripts/repo_intelligence_tier_promotion_readiness.py --output json`

## Non-Authority Boundary

This document does not authorize:

- support widening;
- production platform claims;
- live adapter execution;
- opening the historical all-or-none PR-Xfinal path;
- tagging or publishing `v5.0.0`;
- replacing `ao-release-gate` or GitHub branch protection as release authority.

The current repo-owned authority remains the `ao-release-gate` required check
plus GitHub branch protection. AI review output is evidence only.

## Current Decision

The historical `v5.0.0` general-purpose production-platform promotion path is
not the active path. It was superseded by the E-9-1 / PR-Xfinal closeout
decision: ao-kernel remains a CLI-only, operator-mediated governed
control-plane. The three guard flags remain false by design:

| Guard flag | Current state | Meaning |
|---|---:|---|
| `support_widening` | `false` | No support-tier expansion is authorized. |
| `production_platform_claim` | `false` | No general-purpose production platform claim is authorized. |
| `live_adapter_execution` | `false` | ao-kernel does not call provider APIs directly. |

The safe release framing is therefore:

- **Preferred:** v4.x minor release for governed control-plane hardening and
  consumer onboarding.
- **Not open now:** `v5.0.0` tag/publish.
- **Only possible later:** a major release explicitly renamed as a governed
  control-plane GA, with changelog/PyPI/docs stating that all three guard flags
  remain false and that no production-platform promotion happened.

## Current Readiness Tool Output

`scripts/repo_intelligence_tier_promotion_readiness.py --output json` currently
returns:

```text
decision: blocked_operator_bound_evidence_required
overall_status: blocked
support_widening: false
production_platform_claim: false
live_adapter_execution: false
```

The blocking gates are:

1. `explicit_operator_authorization`
2. `general_purpose_platform_claim_authorization`
3. `guardrail_hardening_matrix`
4. `vector_backend_e2e_evidence`
5. `scan_index_query_packaging_smoke`
6. `operator_verified_runtime_semantics`
7. `cross_lane_production_matrix_evidence`
8. `gp59_reclassification_plan`
9. `support_boundary_transition_plan`

These blockers are expected under the current governed-control-plane decision.
They must not be bypassed by documentation-only edits.

## Related Open Blocker: High-Risk Provider Separation

PR `#997` implements the high-risk provider-separation hardening for issue
`#985`, but it is intentionally fail-closed until real MiniMax review evidence
exists.

Current accepted state:

- normal CI checks pass;
- `ao-release-gate` fails because MiniMax evidence is `BLOCK`, not `AGREE`;
- the MiniMax toolchain is not currently producing real review evidence in the
  local environment;
- this must not be converted into a fake MiniMax `AGREE`.

The correct completion path for `#985` is:

1. fix MiniMax credentials/tooling outside the repository;
2. produce a real MiniMax review for the exact PR scope;
3. replace the `BLOCK` evidence with real `AGREE`;
4. let `ao-release-gate` pass normally;
5. merge through the repo-owned gate, without admin bypass.

## Next Safe Work Order

| Order | Work | Owner boundary | Exit condition |
|---:|---|---|---|
| 1 | MiniMax provider/tooling unblock for `#997` | Operator/environment + agent verification | Real MiniMax `AGREE` evidence replaces `BLOCK`; `ao-release-gate` passes. |
| 2 | Guardrail hardening matrix evidence | Agent can prepare; operator verifies semantics | Matrix covers AST/chunk edges, namespace isolation, stale cleanup, no-root-write, no-auto-feed, and no-MCP exposure. |
| 3 | Vector backend E2E evidence | Agent + configured backend | Explicit write, stale cleanup, namespace isolation, read-only query validation, and fail-closed missing-backend paths are proven. |
| 4 | Wheel-installed scan/index/query smoke | Agent | Smoke runs outside the source checkout and records fail-closed missing-backend behavior. |
| 5 | Cross-lane production matrix gap inventory | Agent planning only | Evidence gaps across real adapter, read-only E2E, controlled write-side, remote PR write, rollback, cost, and release governance are enumerated without claiming readiness. |
| 6 | GP-5.9 reclassification + support-boundary transition draft | Agent planning only | Draft identifies blockers removed, retained, or replaced; it does not change live support tier. |
| 7 | Release decision PR | Operator-bound | Chooses v4.x governed-control-plane minor or a separately authorized renamed major. No autonomous tag/publish. |

## Explicit Stop Conditions

Stop and do not open a release/tag/publish PR if any of these are true:

- any guard flag would need to change from `false`;
- `ao-release-gate` is red or bypassed;
- MiniMax evidence is missing, synthetic, or `BLOCK`;
- readiness blockers are being waived by wording instead of evidence;
- the release note could be read as a general-purpose production platform claim;
- the release requires live provider API calls by ao-kernel.

## Practical Next PRs

Recommended follow-up slices:

1. `fix(#985): replace fail-closed MiniMax blocker with real MiniMax evidence`
   after the external MiniMax credential/tooling issue is resolved.
2. `docs(readiness): record guardrail hardening matrix evidence plan`.
3. `test(readiness): add wheel-installed scan/index/query smoke harness`.
4. `docs(release): prepare governed-control-plane v4.x release checklist`.

None of these slices should tag, publish, widen support, claim production
platform readiness, or execute live adapters.
