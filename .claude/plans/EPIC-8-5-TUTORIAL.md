# V5 Epic 8 E-8-5: Build Your Own AO-MA-SPM Program Tutorial

> **Risk class:** conservative low-risk (docs-only)
> **Implementer:** Anthropic Claude / **Reviewer:** OpenAI Codex (post-impl)

## 1. Scope

7-step tutorial walking through AO-MA-SPM program bootstrap on ao-kernel.
Uses canned stub workers; live LLM provider calls remain gated behind
`live_adapter_execution=true` flag flip (E-2-1).

**In scope:**
- `docs/TUTORIAL-BUILD-AO-MA-SPM-PROGRAM.md` (12 sections; 7 numbered steps)
- 16 invariant tests

**Out of scope (ZERO TOUCH):**
- `.github/workflows/*`
- Live provider call enablement (operator-bound supersession, E-2-1)
- Any guard flag flip

## 2. Seven Steps

| Step | Topic |
|---|---|
| 1 | Initialize workspace (`ao-kernel init` + `doctor`) |
| 2 | Define first slice (SLICE-001) |
| 3 | Plan-time cross-AI consensus (Anthropic + OpenAI distinct providers per ADR-0004) |
| 4 | Implement against stub worker (ADR-0003 import-only contract) |
| 5 | Verify evidence (timeline + replay) |
| 6 | Open PR (single-AI baseline evidence + supersession pair for high-risk paths) |
| 7 | Operator approval gate (`ao-ma-plan-approval` GitHub Environment, E-1-1 wiring) |

## 3. Test Sections (16 invariants)

| Section | Count | Focus |
|---|---|---|
| 1. Presence/structure | 7 | Tutorial exists + 7 steps each covered |
| 2. Claim discipline | 4 | 3 guard flags const false + no positive claim + supersession + no live provider authorization |
| 3. Cross references | 4 | ADR-0003/0004 + E-8-1 + E-8-3 + E-1-1 |
| 4. Governance | 1 | ZERO TOUCH `.github/workflows/` |

## 4. References

- E-8-1 deployment guide (PR #815)
- E-8-3 operator runbook (PR #816)
- ADR-0003 native import-only contract
- ADR-0004 cross-AI peer review HARD RULE
- E-1-1 GitHub Environment ao-ma-plan-approval (merged)
- E-2-1 future slice: live_adapter_execution flag flip authority
