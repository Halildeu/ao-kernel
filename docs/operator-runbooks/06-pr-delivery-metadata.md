# PR Delivery Metadata Contract

This runbook records the `ao-kernel` adaptation of the stronger delivery
discipline used in `platform-k8s-gitops`. It improves PR handoff quality without
changing release authority.

## Authority boundary

- AI output is evidence, not release authority.
- Release authority remains the repo-owned `ao-release-gate` required checks
  plus GitHub branch protection.
- Low-risk autonomous merge remains valid only for changes that satisfy the
  existing eligibility checks.
- High-risk and governance-sensitive changes remain fail-closed unless the
  repo-owned gate receives valid cross-provider review evidence.
- This contract does not authorize support widening, production-platform claim,
  live-adapter execution, ruleset bypass actors, or admin merge.

## What the PR template must declare

Every PR should expose the following fields in a predictable form:

- primary issue and optional `Tracked by` issue;
- work package identifier;
- risk class;
- release-authority impact;
- critical-fix flag;
- boundary declaration;
- cross-AI review evidence summary;
- validation evidence;
- merge and post-merge cleanup notes.

The future metadata gate can parse this body and validate it against
`ao_kernel/defaults/schemas/pr-delivery-metadata.schema.v1.json`.

## `Tracked by` versus `Closes`

Use `Closes #N` only when the PR merge itself satisfies the issue acceptance
criteria.

Use `Tracked by #N` when the issue must remain open after merge for post-merge
verification, live evidence, manual operator checks, or release smoke.

## Boundary declaration semantics

The boundary declaration separates ordinary code changes from changes that may
touch credentials, state mutation, user communication, or boundary-crossing
actions.

If `none of the above` is selected, every other boundary item must remain
unchecked and user/operator approval evidence must be `N/A`.

If the PR includes credential read/write, production state mutation,
boundary-crossing behavior, or user communication, user/operator approval
evidence must not be `N/A`.

The template's `Critical-Fix: no` value is intended to be parsed with YAML boolean semantics, where `no` maps to `false`.

## Cross-AI evidence semantics

Cross-AI review fields identify provider separation and review artifacts. They
do not replace `ao-release-gate`. For high-risk PRs, the release gate remains
responsible for deciding whether the evidence is sufficient.

When the verdict is `AGREE`, `REVISE`, or `BLOCK`, the metadata must include at
least one reviewer provider and at least one review artifact. `N/A` is reserved
for low-risk or not-yet-reviewed PRs.

The schema rejects same-provider implementer/reviewer overlap unless
`same_provider_exception` records an explicit exception. The release gate still
decides whether any exception is acceptable for the PR risk class.

## Adoption sequence

1. PR template and schema contract.
2. Metadata-only PR body gate.
3. Merge-to-issue evidence workflow.
4. Lightweight issue/board helper CLI.
5. Critical-fix trailer and label automation.

Each step should be a separate PR so the gate remains observable and reversible.
