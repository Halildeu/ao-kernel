# Epic 9 PR-Xfinal Pre-Supersession Checklist

> ## ⚠️ SUPERSEDED (2026-06-07) — historical only, NOT an active route
>
> This 18-condition all-or-none checklist is **superseded by an explicit operator
> decision** to keep ao-kernel a CLI-only governed control-plane. It is **no
> longer an active prerequisite contract** and **does not gate any future work**.
> No Epic 9 PR-Xfinal all-or-none guard-flag flip will be opened. The three guard
> flags remain const false as the final state, and **no guard flag flip is
> authorized** by this document.
>
> **Everything below this banner is HISTORICAL RECORD ONLY.** Any "future Epic 9
> PR-Xfinal must satisfy …" / "must fail closed …" language below describes a path
> that will **not** be taken and must not be read as an active requirement.
> See `.claude/plans/EPIC-9-PR-XFINAL-SUPERSESSION-CLOSEOUT.md` and
> `tests/fixtures/epic9/epic9-xfinal-supersession-decision.current.json`.

**Status:** SUPERSEDED (historical only) · ~~recorded / prerequisite artifact only~~
**Slice:** E-2-7
**Parent plan:** `.claude/plans/EPIC-2-LIVE-ADAPTER-EXECUTION.md`
**Schema:** `ao_kernel/defaults/schemas/pre_supersession_checklist.schema.v1.json`
**Authority:** Epic 9 PR-Xfinal only

This document records the prerequisite checklist that a future Epic 9
PR-Xfinal must satisfy before any all-or-none V5 promotion supersession PR can
be opened or merged. E-2-7 is infrastructure-only: it does not authorize live
adapter execution, support widening, production platform claims, or any guard
flag flip.

The matching schema pins:

- `guard_flip_authority = "epic_9_only"`
- `all_conditions_required = true`
- `support_widening = false`
- `production_platform_claim = false`
- `live_adapter_execution = false`
- `live_adapter_execution_current_state = false`

The future Epic 9 supersession schema owns any proposal-state field. This E-2-7
artifact only defines the required checklist and the current closed guard state.

## Required Conditions

All 18 conditions below are mandatory. A future PR-Xfinal with any unmet
condition must fail closed and must not merge.

1. **Operator authority block** — explicit operator authorization for the Epic 9 PR-Xfinal live-adapter guard enablement, recorded as an exact PR commit/comment string.
2. **Cross-AI consensus 2-way minimum** — Codex (OpenAI) and Mavis (MiniMax) provider-distinct AGREE evidence for the supersession decision.
3. **7-day live test window** — bounded operator dispatch window with per-call audit aggregate and pinned cost evidence.
4. **Cost ceiling enforced plus breach evidence plus rollback path** — soft and hard breach behavior are proven and rollback is documented.
5. **All required CI green** — required and advisory checks are green; red advisory checks are not ignored.
6. **Public claim language sync** — badge, README, project board, and public wording remain deferred until the flip is confirmed.
7. **Operator-bound rollback procedure** — tag revert path and workflow pause procedure are documented.
8. **Secret rotation completion** — fresh provider API keys and revoke/rotation audit entries exist for every allowlisted provider.
9. **Pricing source freshness** — pricing source snapshot is no older than 30 days and is SHA-256 pinned.
10. **Workflow content SHA pin plus base SHA plus head SHA** — workflow content hashes and supersession base/head commit SHAs are pinned in the evidence artifact and squash message.
11. **Protected environment reviewer proof** — GitHub Environment `live-adapter-flip` protected reviewer approval and environment secret scope evidence are captured.
12. **Provider/model allowlist** — provider/model pairs available during the flip are explicitly allowlisted and all other pairs fail closed.
13. **Provider SLA ToS data-retention region policy proof** — SLA, Terms, data-retention, and region-policy URL snapshots are SHA-256 pinned per provider.
14. **Budget overrun follow-up issue automation** — hard breach or cumulative spend above 80 percent of ceiling auto-creates a GitHub follow-up issue.
15. **Branch-protection ruleset source-pin drift check** — pre-merge and post-merge ruleset SHA-256 evidence matches.
16. **Required-check name/source collision check** — required check names are unique and source-pinned; same-name external check runs cannot satisfy the gate.
17. **Post-window deauthorization plus secret scope removal** — after the bounded window, operator authority expires and secret environment scope is removed.
18. **Audit retention plus tamper evidence** — per-call audit JSONL is retained for at least 90 days and each row is linked by a SHA-256 chain.

## Checklist Artifact Semantics

The JSON artifact validated by `pre_supersession_checklist.schema.v1.json`
contains one item for each condition above. Each item carries:

- `name`
- `status`, either `unmet` or `met`
- `evidence_ref`, either a URI or `null`
- `attestor`, either a string or `null`

For this E-2-7 slice, the reference state is expected to be all `unmet`; it is
a prerequisite contract, not the future Epic 9 evidence package. Epic 9
PR-Xfinal is responsible for supplying the evidence refs and attestors.

## Non-Authority Boundary

This document and its schema are not release authority. They are an input to a
future operator-bound Epic 9 supersession decision. Current release authority
continues to be the repo-owned `ao-release-gate` required check plus GitHub
branch protection for ordinary repository merges.
