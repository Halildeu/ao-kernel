# ao-kernel NIST CSF 2.0 Operator Usage Runbook (V5 Epic 6 E-6-3e)

> **Documentation only.** **Voluntary framework, no certification.** This
> runbook helps an operator deploying ao-kernel use the NIST CSF 2.0
> Function/Category reference mapping as part of their own risk
> management program. It is NOT a CSF Profile, NOT an Implementation
> Tier assessment, NOT an Implementation Plan, NOT a Subcategory
> deep-dive, and NOT a certification document.

## 1. Scope

This runbook accompanies:

- [`nist-csf-control-mapping.v1.json`](nist-csf-control-mapping.v1.json) - canonical SSOT
- [`nist-csf-control-mapping.v1.md`](nist-csf-control-mapping.v1.md) - generated render
- `../../ao_kernel/defaults/schemas/nist-csf-control-mapping.schema.v1.json` - schema

The repo baseline ships:

- 6 Functions (GV, ID, PR, DE, RS, RC)
- 22 Categories total
- 2 categories `documented` (RS.MA, RS.AN - evidence surface only, NOT operating effectiveness)
- 5 categories `partial` (GV.PO, ID.AM, ID.IM, DE.CM, DE.AE - limited evidence surface)
- 15 categories `out_of_scope` (operator-owned organizational, infrastructure, or program responsibilities)

## 2. NIST CSF 2.0 is a Voluntary Framework

NIST Cybersecurity Framework 2.0 is a voluntary risk management
framework published by NIST (US Department of Commerce). There is no
NIST CSF certification program. NIST does NOT issue CSF assessment
attestations. CISA does NOT attest CSF maturity. Statements such as
`CSF-compliant`, `CSF certified`, `NIST validated`, or `fully
implements CSF` are public claim risks and prohibited in this repo's
artifacts.

## 3. Functions, Categories, and Subcategories

NIST CSF 2.0 organizes cybersecurity outcomes into:

- 6 Functions (GOVERN, IDENTIFY, PROTECT, DETECT, RESPOND, RECOVER)
- 22 Categories (this slice)
- 106 Subcategories (NOT in this slice; out-of-scope E-6-3e-2)

This slice ships only Function- and Category-level reference. Operator
that needs Subcategory-level mapping should wait for E-6-3e-2 or
perform that mapping internally.

## 4. Implementation Tiers (operator-owned)

NIST CSF 2.0 defines 4 Implementation Tiers:

- Partial
- Risk Informed
- Repeatable
- Adaptive

The repo declares `ao_kernel_claims_tier: "none"` and
`tier_assessment_operator_owned: true`. ao-kernel does NOT assess
itself at any Tier. Tier assessment is an organizational maturity
characterization, NOT a software characterization. Operator + risk
management leadership determine Tier through their own assessment
process.

## 5. CSF Profiles (operator-owned)

A CSF Profile is an organizational construct: a `Current Profile`
(what the organization is doing today) and a `Target Profile` (what
the organization aims to do). The repo declares
`ao_kernel_is_organization: false`, `no_csf_profile_in_repo: true`,
and `operator_csf_profile_owner: true`. ao-kernel cannot have a
Profile because it is not an organization; only operators can build
Profiles.

## 6. How to Use This Mapping in Your CSF Profile

When operator builds their organizational CSF Profile, this mapping
can be referenced as follows:

1. For `documented` and `partial` categories, the operator may reference
   ao-kernel evidence surfaces (e.g., PR #801 incident response
   playbook) as input to their `Current Profile` assessment. **Evidence
   surface != operating effectiveness**; the operator's own assessment
   of operating effectiveness is independent.

2. For `out_of_scope` categories, the mapping is silent. Operator must
   reference their own infrastructure, IAM, HR, BCP/DR, and program
   evidence for those categories.

3. The mapping does NOT prescribe Tier or Profile content. Operator
   chooses Tier and Profile based on organizational risk appetite and
   the Profile creation workflow.

## 7. Public Claim Discipline

Do NOT publish or distribute claims using any of the 18 prohibited
tokens enumerated in
[`nist-csf-control-mapping.v1.json`](nist-csf-control-mapping.v1.json)
under `prohibited_claims`. The scanner enforces this on Markdown
prose. Tier names (`partial`, `risk_informed`, `repeatable`,
`adaptive`) and Profile terms (`current_profile`, `target_profile`)
appear only in disclosure tables and code spans; their use in prose
sentences is a public-claim risk and is forbidden.

Do NOT use contract-construction language such as
`organization shall`, `tier achieved`, `profile complete`,
`framework adopted`, `matured to`, `assessment confirms` in this
runbook or in any related repo artifact. These are operator + counsel
territory.

## 8. Cross-AI Peer Review Trail

Per HARD RULE Cross-AI Peer Review (2026-05-05, 2026-05-14):

- Implementer Anthropic Claude -> Reviewer OpenAI Codex.
- Plan-time consensus required for any change to the NIST CSF schema
  or rendered Markdown.
- Codex iter chain audit trail in
  [`../../.claude/plans/EPIC-6-E6-3E-NIST-CSF-MAPPING.md`](../../.claude/plans/EPIC-6-E6-3E-NIST-CSF-MAPPING.md).

## 9. Out-of-scope follow-up slices

| ID | Slice |
|---|---|
| E-6-3e-2 | 106 Subcategory deep-dive |
| E-6-3e-3 | Operator CSF Profile creation workshop |
| E-6-3e-4 | Implementation Tier assessment guide |
| E-6-3e-5 | NIST SP 800-53 control mapping (separate framework) |

## 10. References

- Source catalog: [`nist-csf-control-mapping.v1.json`](nist-csf-control-mapping.v1.json)
- Generated render: [`nist-csf-control-mapping.v1.md`](nist-csf-control-mapping.v1.md)
- Schema: [`../../ao_kernel/defaults/schemas/nist-csf-control-mapping.schema.v1.json`](../../ao_kernel/defaults/schemas/nist-csf-control-mapping.schema.v1.json)
- E-6-3 SOC2/ISO compliance overview: [`README.md`](README.md)
- E-6-3b HIPAA mapping reference: PR #809
- E-6-3c GDPR DPIA operator template: PR #810
- E-6-3d PCI-DSS control reference mapping: PR #811
- NIST CSF 2.0 official page: https://www.nist.gov/cyberframework
- HARD RULE Cross-AI Peer Review (2026-05-05, 2026-05-14)
- HARD RULE Uzun Vadeli Kalici Cozum (2026-05-27)
- Codex thread `019e8516` (2-iter REVISE -> AGREE)
