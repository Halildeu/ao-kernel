# Epic 9 PR-Xfinal — Supersession Closeout

**Status:** superseded by operator decision (not failed, not deferred)
**Work package:** E-9-1
**Decision date:** 2026-06-07
**Machine-readable decision:** `tests/fixtures/epic9/epic9-xfinal-supersession-decision.current.json`
**Decision schema:** `ao_kernel/defaults/schemas/epic9-xfinal-supersession-decision.schema.v1.json`
**Source authority:** `.claude/plans/RI-7.8c-FINAL-PROMOTE-DECISION.v1.json` + `.claude/plans/gpp_status.v1.json`
**Cross-AI review:** implementer `anthropic` / reviewer `openai` (Codex thread `019ea0f0`)

## 1. What this closes

The Epic 9 PR-Xfinal path was designed as an **all-or-none atomic flip** of the
three guard flags — `live_adapter_execution`, `support_widening`,
`production_platform_claim` — culminating in a `v5.0.0` "general-purpose
production platform" claim. This closeout records that **that path is superseded**
by an explicit operator decision.

This is a **conscious product-boundary change, not an engineering escape and not
a deferral**. The all-or-none flip is not "blocked pending evidence" anymore; it
is **out of scope** because the product's intended shape changed.

## 2. The operator decision

The operator clarified (2026-06-07) the actual operating model:

> "ao-kernel olabilir ama işleri aylık CLI aboneliği ile yapacağım"
> "projemi bitirince diğer projelerimi yapmak için diğer repolara kuracağım"

In English: ao-kernel is the **governance control-plane**; the actual AI work is
done by Claude / Codex / Mavis through **their own monthly CLI subscriptions**
(native interfaces). ao-kernel itself never makes programmatic provider API
calls. ao-kernel is finished as a control-plane and then **installed into other
repos** (`pip install ao-kernel`) to govern other projects.

This is identical to the documented core goal: ao-kernel governs the autonomous
multi-AI flow; it is not a runtime that calls provider APIs;
`live_adapter_execution` stays false.

## 3. Final guard-flag state (unchanged, by design)

| Flag | Final state | Meaning |
|---|---|---|
| `live_adapter_execution` | **false** | ao-kernel does not call provider APIs; AIs use their own CLI subscriptions |
| `support_widening` | **false** | narrow stable support boundary kept |
| `production_platform_claim` | **false** | no general-purpose production platform claim |

These match RI-7.8c (operator non-promotion, cli-only) and GPP-9
(`keep_narrow_stable_runtime`). No flag is flipped by this closeout.

## 4. Allowed claims vs forbidden claims

**Allowed** (proven by the consumer acceptance smoke, PyPI `4.1.0`, fresh venv,
no API key):

- installable governed control-plane;
- fail-closed policy engine;
- self-hosted JSONL evidence trail;
- governed context pipeline;
- API-keyless consumer use.

**Forbidden** (must not appear in public docs, README, badges, release notes):

- general-purpose production platform;
- autonomous provider API execution;
- active support widening;
- active live adapter runtime;
- "all-or-none V5 production promotion satisfied".

## 5. Reinterpretation of existing artifacts (not deletion)

The prior artifacts are **retained as historical evidence** and **reinterpreted**,
not removed:

- `tests/fixtures/epic9/xfinal-readiness-blocker.current.json` — read as
  **superseded / not applicable** under the CLI-only decision; no longer an
  active "blocked pending flip" gate.
- `.claude/plans/EPIC-9-PR-Xfinal-PRE-SUPERSESSION-CHECKLIST.md` — the
  18-condition all-or-none checklist is **no longer the active path**; retained
  as a historical contract.
- `tests/fixtures/epic9/v5-production-readiness-matrix.current.json` — the
  9-dimension matrix stays **partial by design**; completion is no longer a
  target under this decision.
- `.claude/plans/V5-FULL-PRODUCTION-PROMOTION-ROADMAP.md` — reframed as a
  **matured governed control-plane** roadmap (see its superseded banner).

## 6. Release implication

- Release **only as a governed control-plane**, never as a production-platform
  promotion.
- **v4.x minor preferred** for the "governed control-plane readiness / consumer
  onboarding" release. The historical "V5" label is tied to the all-or-none
  production flip, so publishing `v5.0.0` now risks being misread as "production
  platform promotion happened".
- A `v5.0.0` **major** is acceptable later **only if** explicitly renamed (e.g.
  "Governed Control-Plane GA"), with the three guard flags stated false in the
  changelog / PyPI / docs, justified by "public contract/framing stabilized" —
  not by any production-platform claim.

## 7. Non-authority boundary

This document and its machine-readable decision are **evidence only**. They are
not a release note and not public production-claim authority. Release authority
remains the repo-owned `ao-release-gate` required check plus GitHub branch
protection. No guard flag flip is authorized here.

## 8. Next safe actions

1. Reframe `.claude/plans/V5-FULL-PRODUCTION-PROMOTION-ROADMAP.md` to the
   governed-control-plane framing (superseded banner added).
2. Write the consumer onboarding guide for installing ao-kernel into other repos
   (within this corrected boundary).
3. Add one operator-mediated cross-repo smoke to back the "ready for other
   repos" usage-model claim (context/evidence produced + a CLI-subscription
   run recorded to the evidence trail; not a provider API call).
4. Optional: clean up or explicitly document the `doctor` extension-truth WARN.
5. Release decision: v4.x minor (governed control-plane readiness).
