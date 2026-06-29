## Summary

<!-- 1-2 sentences: what changed and why. Avoid closure/production claims unless the release authority evidence supports them. -->

## Delivery metadata

<!--
Machine-readable reviewer input. This single JSON block is validated by
`ao-kernel pr-metadata validate --body-file ...` against
`pr-delivery-metadata.schema.v1.json`.

PR-authored metadata is evidence/diagnostic input only. Release authority
remains the repo-owned `ao-release-gate` required check plus GitHub branch
protection; the gate derives risk from trusted API/diff context, not from this
PR body declaration.
-->

```json pr-delivery-metadata
{
  "boundary_declaration": {
    "boundary_cross": false,
    "credential_read": false,
    "credential_write": false,
    "none_of_the_above": true,
    "state_mutation_production": false,
    "state_mutation_test": false,
    "user_approval_evidence": "N/A",
    "user_communication": false
  },
  "critical_fix": false,
  "cross_ai_review": {
    "implementer_provider": "openai",
    "review_artifacts": [
      "N/A"
    ],
    "reviewer_providers": [
      "anthropic"
    ],
    "same_provider_exception": "N/A",
    "verdict": "N/A"
  },
  "issue": "N/A",
  "release_authority_impact": "none",
  "risk_class": "normal",
  "tracked_by": "N/A",
  "work_package": "AO-MA-or-GPP-id"
}
```

## Scope

- Issue:
- Work package:
- Why now:
- Files / surfaces changed:

## Boundary declaration (human mirror)

<!--
Keep this section aligned with the JSON block above. The validator reads the
JSON block; this mirror is for reviewer scanning only. Credential material must
never be copied into the PR body, comments, logs, or evidence artifacts.
-->

This PR includes:

- [ ] credential-read
- [ ] credential-write
- [ ] state-mutation (test/sandbox)
- [ ] state-mutation (production)
- [ ] boundary-cross
- [ ] user-communication
- [ ] none of the above

User/operator approval evidence: `<link or N/A>`

## Cross-AI review evidence (human mirror)

<!--
Keep this section aligned with the JSON block above. AI review is evidence only.
Release authority remains `ao-release-gate` plus GitHub branch protection. For
high-risk/governance-sensitive PRs, reviewers must be provider-separated from the
implementer and the repo-owned gate must pass.
-->

## Validation

- [ ] Relevant tests:
- [ ] Smoke or packaging proof (if required):
- [ ] Docs or status updated:
- [ ] Deferred risks noted:

## Governance checks

- [ ] Branch is short-lived and based on fresh `main`
- [ ] No unrelated dirty files were included
- [ ] If stacked: retarget + diff re-check completed
- [ ] Required check impact reviewed (`lint`, `test (3.11)`, `test (3.12)`, `test (3.13)`, `coverage`, `typecheck`, `packaging-smoke`, `ao-release-gate`)
- [ ] If governance changed: `.github/REPO-GOVERNANCE.md` updated
- [ ] No support widening, production-platform claim, live-adapter execution, ruleset bypass, or admin merge is introduced unless an explicit operator-bound supersession PR authorizes it

## Merge notes

- [ ] Merge method chosen deliberately (`squash` for normal PRs; `merge commit` only for stacked PRs when needed)
- [ ] Post-merge cleanup/evidence path is clear
