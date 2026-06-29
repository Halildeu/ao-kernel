## Summary

<!-- 1-2 sentences: what changed and why. Avoid closure/production claims unless the release authority evidence supports them. -->

## Delivery metadata

<!--
Machine-readable reviewer input. Keep this block current; a follow-up gate will
parse it against `pr-delivery-metadata.schema.v1.json`.
-->

```yaml
Issue: <#123 or N/A>
Tracked by: <#123 or N/A>
Work package: <AO-MA/GPP/Epic id or N/A>
Risk class: <low|normal|high|governance|critical-fix>
Release authority impact: <none|ao-release-gate-input-only|ao-release-gate-logic|github-ruleset|support-tier-or-claim>
Critical-Fix: no
```

## Scope

- Issue:
- Work package:
- Why now:
- Files / surfaces changed:

## Boundary declaration

<!--
At least one item must be selected. If `none of the above` is selected, every
other item must remain unselected. Credential material must never be copied into
the PR body, comments, logs, or evidence artifacts.
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

## Cross-AI review evidence

<!--
AI review is evidence only. Release authority remains `ao-release-gate` plus
GitHub branch protection. For high-risk/governance-sensitive PRs, reviewers must
be provider-separated from the implementer and the repo-owned gate must pass.
-->

```yaml
Implementer provider: <openai|anthropic|minimax|human|other>
Reviewer provider(s): <openai|anthropic|minimax|human|other|N/A>
Review artifact(s): <PR comment URL, evidence path, or N/A>
Verdict: <AGREE|REVISE|BLOCK|N/A>
Same-provider exception: N/A
```

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
