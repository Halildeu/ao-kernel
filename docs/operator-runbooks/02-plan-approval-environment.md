# Runbook 02 — Plan-Approval Environment (AO-MA-11A-2)

> **Agent-prepared only.** This runbook directs the operator to configure
> the `ao-ma-plan-approval` GitHub environment. The operator does NOT
> dispatch the plan-approval workflow; the dispatcher is the agent /
> automation, and the approver is the required reviewer in this
> environment.

## Prerequisites

- Repository admin permissions on `Halildeu/ao-kernel`
- A non-author user account available as a required reviewer
- PR #758 (plan-approval gate) and PR #792 (env-wired workflow) merged

## Steps

1. Open Repository Settings → Environments → "New environment".
2. Name (exact): `ao-ma-plan-approval`.
3. Add a required reviewer:
   - At least one non-author user (recommended: `Halildeu`)
   - The reviewer must be different from the workflow dispatcher
4. Wait timer: `0`.
5. Deployment branches: keep default; this environment does NOT need a
   branch restriction in v1.
6. Environment secrets: **leave empty in v1**. No env-scoped secrets are
   required.
7. Save the environment.

## Verification

- Repository Settings → Environments lists `ao-ma-plan-approval`
- At least one required reviewer is shown
- Wait timer = `0`
- No environment secrets are present
- The next dispatched plan-approval workflow run pauses on the manual
  reviewer gate

## Rollback

- Removing the environment makes future plan-approval dispatches fail
  immediately. Recreate with the same name + reviewer to restore.

## Stop and contact owner if

- The intended reviewer is also the workflow author (self-review attempt;
  not supported by the v1 contract)
- The required reviewer count is `0` after Save
- The environment name is not exactly `ao-ma-plan-approval` (typo)
- An environment secret was accidentally added

## Notes

- **The operator does NOT dispatch the plan-approval workflow.** The
  dispatcher is the agent / automation; the operator's role is environment
  configuration plus UI approval.
- Self-review (dispatcher = approver) is NOT supported by the workflow
  contract; UI dispatch by the operator is therefore disabled.

## References

- `.github/workflows/ao-ma-11a-plan-approval.yml`
- `.claude/plans/AO-MA-11A-2-PLAN-APPROVAL-GATE.md`
- Codex thread `019e84c6`
