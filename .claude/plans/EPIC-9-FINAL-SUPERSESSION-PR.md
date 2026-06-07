# Epic 9 PR-Xfinal — Final Supersession Draft Guardrail

> ## ⚠️ SUPERSEDED (2026-06-07) — historical only, NOT an active route
>
> The future PR-Xfinal **all-or-none guard-flag flip** described in this draft is
> **superseded by an explicit operator decision** to keep ao-kernel a CLI-only
> governed control-plane. It is **not** the path forward and **must not be
> opened**. The three guard flags remain const false as the final state, and
> **no guard flag flip is authorized** by this document.
>
> **Everything below this banner is HISTORICAL RECORD ONLY.** Any "future
> operator-bound PR-Xfinal", "Final promotion authority belongs only to …", or
> "Only after all three gates …" language below describes a path that will
> **not** be taken and must not be read as an active route or requirement.
> See `.claude/plans/EPIC-9-PR-XFINAL-SUPERSESSION-CLOSEOUT.md` and
> `tests/fixtures/epic9/epic9-xfinal-supersession-decision.current.json`.

**Status:** SUPERSEDED (see banner) · ~~draft / not ready to open~~
**Work package:** E-9-1
**Parent roadmap:** `.claude/plans/V5-FULL-PRODUCTION-PROMOTION-ROADMAP.md`
**Current blocker artifact schema:** `ao_kernel/defaults/schemas/epic9-xfinal-readiness-blocker.schema.v1.json`
**Current blocker fixture:** `tests/fixtures/epic9/xfinal-readiness-blocker.current.json`
**Production matrix blocker:** `.claude/plans/V5-PRODUCTION-READINESS-MATRIX-BLOCKER.md`

This document records the shape and current readiness boundary for the future
Epic 9 PR-Xfinal. It closes the roadmap reference gap without opening the final
promotion path. The repository remains in the GPP-9 `keep_narrow_stable_runtime`
state until a later operator-bound supersession PR supplies complete evidence.

## Non-Authority Boundary

This document is not a supersession PR, not a release note, and not public
production-claim authority. It does not authorize:

- support widening;
- production platform claims;
- live adapter execution;
- partial guard-flag flips;
- v5.0.0 tag or publish;
- branch-protection or ruleset relaxation.

AI output remains evidence only. Release authority remains the repo-owned
`ao-release-gate` required check plus GitHub branch protection for ordinary
repository merges. Final promotion authority belongs only to a future
operator-bound PR-Xfinal after all gates below are complete.

## Current Readiness Verdict

PR-Xfinal is **not ready to open**.

| Gate | Current status | Blocking evidence class |
|---|---|---|
| `live_adapter_execution` | not ready | Epic 9 pre-supersession checklist conditions remain unmet |
| `support_widening` | not ready | future support-widening live evidence pack missing |
| `production_platform_claim` | not ready | 9-dimensional V5 production readiness matrix incomplete; current blocker artifact recorded in `.claude/plans/V5-PRODUCTION-READINESS-MATRIX-BLOCKER.md` |

The v1 blocker artifact intentionally pins:

- `pr_xfinal_open_allowed: false`
- `support_widening: false`
- `production_platform_claim: false`
- `live_adapter_execution: false`
- `partial_flip_allowed: false`
- `all_or_none_atomic_flip: true`

## Open Issue Binding

The current blocker state is mirrored by these GitHub issues:

- `#775` — Epic 2 live adapter execution enablement
- `#776` — Epic 3 support widening enablement
- `#782` — Epic 9 final promotion decision
- `#895` — E-9-1 final operator-bound PR-Xfinal

GitHub issues are a visibility mirror. Repo artifacts remain the SSOT.

## Required Gate A — Live Adapter Execution

The future PR-Xfinal cannot proceed until the Epic 9 pre-supersession checklist
has all 18 mandatory conditions marked `met` with evidence refs and attestors.
At minimum this includes:

1. exact operator authority block;
2. provider-distinct cross-AI consensus;
3. bounded 7-day live test window;
4. cost ceiling, breach evidence, and rollback path;
5. secret rotation completion;
6. protected environment reviewer proof;
7. provider/model allowlist;
8. pricing-source freshness;
9. branch-protection source-pin drift check;
10. post-window deauthorization and secret-scope removal;
11. audit retention plus tamper evidence.

The E-2-7 checklist artifact is prerequisite infrastructure only. It does not
authorize a live run.

## Required Gate B — Support Widening

The future PR-Xfinal cannot proceed until support widening has a complete live
evidence pack for every surface being widened. The current E-3-5/E-3-6 chain
provides process and validator infrastructure only.

Required future evidence includes:

1. operator authorization phrase `AUTHORIZE_SUPPORT_WIDENING_SUPERSESSION`;
2. live evidence-class artifacts;
3. seven-day evidence window;
4. per-surface or per-class evidence aggregate;
5. provider-distinct final AGREE verdicts;
6. plan digest, final diff digest, and PR head SHA binding;
7. raw verdict transcript artifact binding.

The v1 widening evidence-pack schema keeps `widening_authorized` false.

## Required Gate C — Production Platform Claim

The future PR-Xfinal cannot proceed until the V5 production-readiness matrix is
complete across the roadmap's nine dimensions:

1. public support matrix;
2. protected real provider live calls;
3. cost, rate, and circuit-breaker evidence;
4. observability production tunables;
5. security, SBOM, and license scans;
6. install and deploy lifecycle smoke;
7. multi-tenancy isolation;
8. docs and runbooks;
9. bypassless `ao-release-gate` and GitHub ruleset trail.

Current-state tracking for this gate is recorded by
`v5-production-readiness-matrix-blocker.schema.v1.json` and
`tests/fixtures/epic9/v5-production-readiness-matrix.current.json`. The v1
blocker pins `matrix_complete=false`, `pr_xfinal_open_allowed=false`, and all
three guard flags false.

Only after all three gates are complete may a future PR-Xfinal bind the evidence
refs, record the exact operator authorization, update public claim language,
prepare v5.0.0 release notes, and perform the all-or-none guard-flag transition.

## Forbidden Until Future Supersession

Until a future PR-Xfinal is ready and explicitly operator-authorized, agents
must not:

- open a final promotion PR;
- change any of the three guard flags;
- claim production readiness in public docs;
- publish v5.0.0 as a production promotion;
- accept partial flip proposals;
- treat this draft as release authority.

## Next Safe Actions

1. Keep `#895` blocked.
2. Continue live-adapter execution evidence work under `#775`.
3. Continue support-widening evidence work under `#776`.
4. Keep `#782` planned until both evidence gates and the production matrix are complete.
5. Replace this v1 blocker artifact only through a later operator-bound PR that
   supplies complete evidence and passes `ao-release-gate`.
