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

## Portable product commands

The metadata contract is now exposed through `ao-kernel`, not only through this
repository's PR template:

```bash
ao-kernel pr-metadata schema
ao-kernel pr-metadata template
ao-kernel pr-metadata validate --body-file pr-body.md
ao-kernel pr-metadata validate --body-file pr-body.md --output json
```

`validate` exits `0` only when the PR body contains a fenced
`json pr-delivery-metadata` block that validates against the bundled schema. It
exits non-zero for missing, malformed, or schema-invalid metadata.

The release gate also carries a sanitized `untrusted_pr_delivery_metadata`
summary in its payload when the GitHub Actions workflow supplies the PR body.
Metadata-only PR body gate: this is the metadata-only PR body gate surface for
this release. It is diagnostic only, not enforcement. PR-author text never
becomes release authority and never weakens trusted diff/API/GPP checks.

## What the PR template must declare

Every PR should expose the following fields in a predictable form:

- primary issue and optional `tracked_by` issue;
- work package identifier;
- risk class;
- release-authority impact;
- critical-fix flag;
- boundary declaration;
- cross-AI review evidence summary;
- validation evidence;
- merge and post-merge cleanup notes.

The canonical form is a single fenced `json pr-delivery-metadata` block. Human
mirror sections may remain in the template for reviewer scanning, but the product
validator and release-gate diagnostic read only the JSON block.

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

The JSON block uses `"critical_fix": false`. YAML boolean parsing is no longer
part of the machine-readable contract.

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

1. PR template and schema contract. Done.
2. Portable `ao-kernel pr-metadata` schema/template/validate commands. Done.
3. Metadata-only release-gate diagnostic from GitHub API PR body. Done.
4. Merge-to-issue evidence workflow.
5. Lightweight issue/board helper CLI.
6. Critical-fix trailer and label automation.

Each step should be a separate PR so the gate remains observable and reversible.
