# V5 Epic 8 E-8-3: Operator Runbook

> **Risk class:** conservative low-risk (docs-only)
> **Implementer:** Anthropic Claude / **Reviewer:** OpenAI Codex (post-impl)

## 1. Scope

Operator-owned playbook for five production scenarios: rollback, tag
revert, pause/graceful stop, emergency stop, incident triage. Complements
E-8-1 deployment guide + E-6-6 incident response playbook + E-6-6b vendor
escalation matrix.

**In scope:**
- `docs/OPERATOR-RUNBOOK.md` (10 sections)
- 15 invariant tests

**Out of scope (ZERO TOUCH):**
- `.github/workflows/*`
- E-6-6 incident response playbook content (referenced, not modified)
- E-6-6b vendor escalation matrix (referenced, not modified)
- Any guard flag flip (3 const false unchanged)

## 2. Five Operator Scenarios

| § | Scenario | Coverage |
|---|---|---|
| 2 | Rollback | Standalone pip pin + Docker tag swap + k8s rollout undo |
| 3 | Tag revert | PyPI yank + CHANGELOG mark + SBOM update + postmortem |
| 4 | Pause / Graceful stop | SIGTERM + Docker stop --time 60 + k8s scale --replicas=0 |
| 5 | Emergency stop | Revoke credentials + force-stop + evidence snapshot + recovery |
| 6 | Incident triage tree | Decision tree: governance → emergency; data → pause; SLI → rollback; else dashboards |

## 3. Test Sections (15 invariants)

| Section | Count | Focus |
|---|---|---|
| 1. Presence/structure | 6 | Runbook exists + 5 scenarios + incident triage tree |
| 2. Claim discipline | 4 | 3 guard flags const false + no positive claim (whitespace-flat scanner) + operator-bound supersession + no flag flip in prose |
| 3. Cross references | 4 | E-6-6 + E-5-2/3/4 + operator-owned scenarios + deployment guide |
| 4. Governance | 1 | ZERO TOUCH `.github/workflows/` |

## 4. References

- E-8-1 production deployment guide (PR #815 pipeline)
- E-6-6 incident response playbook (merged)
- E-6-6b vendor escalation matrix (merged)
- V5 roadmap
- HARD RULE Cross-AI Peer Review + No Fake Work + Uzun Vadeli
