# V5 Epic 6 E-6-3e: NIST CSF 2.0 Function/Category Reference Mapping

> **Cross-AI plan-time AGREE** — Codex thread `019e8516` (2 iters: REVISE → AGREE)
> **Implementer:** Anthropic Claude / **Reviewer:** OpenAI Codex
> **Risk class:** conservative low-risk (additive; ZERO TOUCH E-6-3/b/c/d)

## 1. Scope

Schema-backed NIST CSF 2.0 Function/Category reference mapping —
**voluntary** framework, NO certification program. Additive to E-6-3
(PR #802 MERGED), E-6-3b HIPAA (PR #809), E-6-3c GDPR DPIA (PR #810),
E-6-3d PCI-DSS (PR #811). Compliance suite tamamlama (4. ve son slice).

**In scope:**
- 6 Functions + 22 Categories
- Function/Category schema + canonical JSON + Markdown render
- Operator usage runbook + voluntary framework characterization
- 54 invariant tests
- README §3.8 NIST CSF reference link

**Out of scope (ZERO TOUCH):**
- E-6-3 SOC2/ISO catalog + E-6-3b HIPAA + E-6-3c GDPR + E-6-3d PCI artifacts
- 106 Subcategory deep-dive (E-6-3e-2)
- CSF Profile creation (Current/Target) (E-6-3e-3)
- Implementation Tier assessment (E-6-3e-4)
- NIST SP 800-53 (separate framework) (E-6-3e-5)
- Real risk register, customer attestation, contract template language

## 2. Codex Iter Chain

### iter-1 plan-time REVISE — 5 BLOCKER

| ID | Issue | Resolution |
|---|---|---|
| F1 | Status distribution too optimistic (3-5 documented) | Conservative: 2 documented (RS.MA + RS.AN, E-6-6 evidence) + 5 partial + 15 out_of_scope |
| F2 | `minItems=maxItems=6` does not enforce exact per-function category sets | Per-function category sets (GV=6, ID=3, PR=5, DE=2, RS=4, RC=2, total=22) enforced via tests; schema 6 contains for function_id |
| F3 | `function_status: documented` confusion | Test invariant: documented only if all categories documented; out_of_scope only if all out_of_scope; mixed → partial (GV/ID/DE/RS partial; PR/RC out_of_scope) |
| F4 | Token list missed Tier/Profile/attestation variants | Two-layer scanner: 18 exact prohibited tokens + 5 regex patterns (Tier 1-4, named tier, current/target profile, framework achieved, maturity achieved) |
| F5 | Zero-touch claim relies on file presence assumption | `git diff --name-only origin/main...HEAD` (3-dot) allowlist diff; separate zero-touch tests skip with reason if sibling slice files not yet in base |

### iter-2 absorb AGREE + ready_for_impl:true + must_close_findings:[]

6 implementation guardrails (all enforced):

- Markdown title: "Function / Category Reference Mapping" (NOT "control mapping")
- documented evidence rows: "evidence surface only; not operating effectiveness"
- partial categories: evidence_refs minItems=1 via schema allOf if/then
- Tier names + Current/Target Profile terms only in code spans
- diff allowlist uses 3-dot form `origin/main...HEAD`
- Zero-touch HIPAA/GDPR/PCI tests skip if sibling files absent

## 3. Implementation Artifacts

| File | LOC | Purpose |
|---|---|---|
| `ao_kernel/defaults/schemas/nist-csf-control-mapping.schema.v1.json` | ~200 | Draft 2020-12 + root 6 const pins + 6 const-false guard flags + 6 const-true disclaimers + Tier disclosure + Profile disclosure + 6 functions contains + status-driven evidence_refs cardinality |
| `docs/compliance/nist-csf-control-mapping.v1.json` | ~270 | Canonical SSOT (6 functions + 22 categories) |
| `docs/compliance/nist-csf-control-mapping.v1.md` | ~190 | Generated Markdown (byte-equal drift-tested) |
| `docs/compliance/nist-csf-operator-usage-runbook.v1.md` | ~110 | Operator runbook (voluntary framework + Tiers/Profiles operator-owned) |
| `docs/compliance/README.md` | +22 lines | §3.8 NIST CSF reference |
| `scripts/render_nist_csf_docs.py` | ~140 | Deterministic JSON → Markdown |
| `tests/test_nist_csf_mapping.py` | ~590 | 54 invariants |
| `.claude/plans/EPIC-6-E6-3E-NIST-CSF-MAPPING.md` | this | Plan doc + Codex chain |

## 4. Coverage (6 Functions + 22 Categories)

| Function | Status | Categories |
|---|---|---|
| GV GOVERN | `partial` | GV.OC + GV.RM + GV.RR + GV.PO (partial) + GV.OV + GV.SC |
| ID IDENTIFY | `partial` | ID.AM (partial) + ID.RA + ID.IM (partial) |
| PR PROTECT | `out_of_scope` | PR.AA + PR.AT + PR.DS + PR.PS + PR.IR |
| DE DETECT | `partial` | DE.CM (partial) + DE.AE (partial) |
| RS RESPOND | `partial` | RS.MA (documented) + RS.AN (documented) + RS.CO + RS.MI |
| RC RECOVER | `out_of_scope` | RC.RP + RC.CO |

**Distribution:** 2 documented + 5 partial + 15 out_of_scope + 0 not_applicable.

## 5. Public Claim Discipline

**6 disclaimer fields const true** (`csf_disclaimer`):
- `not_nist_certified` + `no_nist_csf_certification_program`
- `not_nist_audited` + `not_cisa_attested`
- `documentation_only` + `operator_csf_profile_decision`

**6 guard flags const false**: 3 V5 + 3 CSF-scoped
(`csf_certification_claim_allowed`, `csf_tier_claim_allowed`,
`csf_profile_claim_allowed`).

**CSF Tier disclosure**: `ao_kernel_claims_tier: const "none"` +
`tier_assessment_operator_owned: const true` + 4 available_tiers
{partial, risk_informed, repeatable, adaptive}.

**CSF Profile disclosure**: `ao_kernel_is_organization: const false` +
`no_csf_profile_in_repo: const true` + `operator_csf_profile_owner: const true`.

**18 exact prohibited tokens** (Markdown prose word-boundary):
`NIST CSF certified`, `CSF-compliant`, `fully implements CSF`,
`CSF Profile complete`, `Implementation Tier achieved`, `CSF audit`,
`NIST validated`, `CISA approved`, `CSF maturity level`, etc.

**5 regex prohibited patterns**:
- `Tier 1-4` prose claim
- Named tier `(partial|risk informed|repeatable|adaptive) tier` claim
- `current/target profile` prose claim
- `framework adopted/matured/achieved`
- `maturity score/level/achieved`

**6 contract-construction patterns forbidden**:
`organization shall`, `tier achieved`, `profile complete`,
`framework adopted`, `matured to`, `assessment confirms`.

## 6. Test Sections (54 invariants)

| Section | Count | Focus |
|---|---|---|
| 1. Schema validity | 12 | Draft 2020-12 + additionalProperties:false + root 6 const + 6 guard + 6 disclaimer + Tier + Profile + 6 functions contains + category_id pattern + status enum + evidence_ref claim_boundary + prohibited 18 |
| 2. Schema negative | 5 | 2 guard flips + documented without evidence + out_of_scope with evidence + bad category_id |
| 3. Function/category content | 8 | Instance validates + 6 functions + 22 categories total + per-function exact sets + status distribution (2/5/15/0) + function_status derivation + RS.MA documented + DE.AE partial wording |
| 4. Tier/Profile discipline | 5 | No Tier 1-4 prose + no named tier prose + no profile prose + Tier disclosure pins + Profile disclosure pins |
| 5. Wording discipline | 5 | 18 prohibited tokens word-boundary + 2 regex prohibited (framework/maturity) + 6 contract patterns + token parity + RS function status partial in Markdown |
| 6. Drift / governance | 6 | Markdown byte-equal + allowlist diff (3-dot) + E-6-3 zero-touch + E-6-3b zero-touch (skip if absent) + E-6-3c zero-touch + E-6-3d zero-touch |
| 7. Cross-validation | 4 | README §3.8 link + anchor targets exist + voluntary framework characterization + runbook usage sections present |
| 8. Governance | 3 | 6 guard flags const false instance + 6 disclaimer const true instance + documented ≤ 2 bound |

## 7. Out-of-scope follow-up slices (4)

| ID | Slice |
|---|---|
| E-6-3e-2 | 106 Subcategory deep-dive |
| E-6-3e-3 | Operator CSF Profile creation workshop |
| E-6-3e-4 | Implementation Tier assessment guide |
| E-6-3e-5 | NIST SP 800-53 control mapping (separate framework) |

## 8. References

- E-6-3 SOC2/ISO compliance: PR #802 MERGED
- E-6-3b HIPAA mapping: PR #809
- E-6-3c GDPR DPIA template: PR #810
- E-6-3d PCI-DSS mapping: PR #811
- E-6-6 incident response playbook: PR #801 MERGED
- HARD RULE Cross-AI Peer Review (2026-05-05, 2026-05-14)
- HARD RULE Uzun Vadeli Kalıcı Çözüm (2026-05-27)
- Codex thread `019e8516` (2-iter REVISE → AGREE)
- NIST CSF 2.0: https://www.nist.gov/cyberframework
- V5 roadmap: `.claude/plans/V5-FULL-PRODUCTION-PROMOTION-ROADMAP.md`
