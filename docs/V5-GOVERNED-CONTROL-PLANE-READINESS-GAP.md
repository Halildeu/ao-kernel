# V5 / Governed Control-Plane Readiness Gap Plan

**Status:** current-state planning note / not release authority  
**Date:** 2026-06-25  
**Authority inputs:**

- `.claude/plans/V5-FULL-PRODUCTION-PROMOTION-ROADMAP.md`
- `.claude/plans/V5-PRODUCTION-READINESS-MATRIX-BLOCKER.md`
- `.claude/plans/EPIC-9-PR-XFINAL-SUPERSESSION-CLOSEOUT.md`
- `scripts/repo_intelligence_tier_promotion_readiness.py --output json`
- `scripts/repo_intelligence_tier_promotion_readiness.py --output json --evidence-manifest .claude/plans/RI-7-EVIDENCE-MANIFEST.v1.json`

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

The readiness tool has two intentionally different modes.

Without an evidence manifest, the tool remains fail-closed and currently
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

These blockers are expected when no evidence manifest is supplied. They must
not be bypassed by documentation-only edits.

With the committed RI-7 evidence manifest, the same tool currently returns:

```bash
python3 scripts/repo_intelligence_tier_promotion_readiness.py \
  --output json \
  --evidence-manifest .claude/plans/RI-7-EVIDENCE-MANIFEST.v1.json
```

```text
decision: ready_for_operator_promotion_decision
overall_status: ready_for_operator_decision
promotion_blockers: []
support_widening: false
production_platform_claim: false
live_adapter_execution: false
```

That manifest-backed ready state means the RI-7 evidence package is prepared
for a later operator-bound promotion decision PR. It does not itself authorize
support widening, a production-platform claim, live adapter execution, a
`v5.0.0` tag, or publication.

Manifest-backed coverage for the completed agent-preparable RI-7 rows:

| Former next-work row | Manifest key | Current value |
|---|---|---:|
| Guardrail hardening matrix evidence | `guardrail_hardening_matrix` | `true` |
| Vector backend E2E evidence | `vector_backend_e2e_evidence` | `true` |
| Wheel-installed scan/index/query smoke | `scan_index_query_packaging_smoke` | `true` |
| Cross-lane production matrix gap inventory | `cross_lane_production_matrix_evidence` | `true` |
| GP-5.9 reclassification + support-boundary transition draft | `gp59_reclassification_plan` / `support_boundary_transition_plan` | `true` / `true` |

No agent-only RI-7 evidence rows remain open in this document. Any boundary
change after this point is a separate operator-bound decision, not an
autonomous evidence-gathering slice.

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
| 2 | Governed-control-plane v4.x release checklist | Agent planning only | `docs/V4-GOVERNED-CONTROL-PLANE-RELEASE-CHECKLIST.md` records packaging, docs, changelog, version, and publish preflight without tag/publish or guard flips. |
| 3 | Repo-intelligence promotion decision PR | Operator-bound | Consumes the manifest-backed readiness report and explicitly chooses promotion or non-promotion. No autonomous guard flip. |
| 4 | Separate major-release supersession, if ever desired | Operator-bound | Explicitly renames the release target as governed control-plane GA; no general-purpose production-platform claim unless separately authorized. |

## v5.0.0 Release No-Go

The active release plan is **not** a v5.0.0 release/tag/publish plan. A
v5.0.0 tag or publish remains blocked unless a future operator-bound
supersession explicitly reopens that path and passes `ao-release-gate`.

The current safe release preparation surface is:

1. keep all three guard flags false;
2. prepare a conservative v4.x governed-control-plane release checklist;
3. keep #997 fail-closed until real MiniMax `AGREE` evidence exists;
4. treat the RI-7 manifest-backed ready state as input to a later
   operator-bound decision, not as autonomous release authority;
5. avoid public wording that can be read as a general-purpose production
   platform claim.

Any workflow, PR, or release note that attempts to tag or publish v5.0.0 from
the current autonomous lane is out of scope for this plan.

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
2. `docs(release): prepare governed-control-plane v4.x release checklist`.
3. `decision(ri): operator-bound repo-intelligence promotion or non-promotion
   decision`, if the operator chooses to consume the manifest-backed
   `ready_for_operator_decision` report.

None of these slices should tag, publish, widen support, claim production
platform readiness, or execute live adapters.
