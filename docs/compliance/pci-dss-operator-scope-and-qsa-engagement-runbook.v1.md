# ao-kernel PCI-DSS Operator Scope and QSA Engagement Runbook (V5 Epic 6 E-6-3d)

> **Documentation only.** **Not a PCI-DSS assessment.** **Not legal or
> assessor advice.** This runbook helps an operator deploying ao-kernel
> determine whether and how PCI-DSS applies to their deployment and how
> to engage a Qualified Security Assessor (QSA). It is NOT a Self-
> Assessment Questionnaire (SAQ), NOT an Attestation of Compliance
> (AOC), NOT a Report on Compliance (ROC), and NOT an ASV scan report.

## 1. Scope

This runbook accompanies:

- [`pci-dss-control-mapping.v1.json`](pci-dss-control-mapping.v1.json) - canonical SSOT
- [`pci-dss-control-mapping.v1.md`](pci-dss-control-mapping.v1.md) - generated render
- `../../ao_kernel/defaults/schemas/pci-dss-control-mapping.schema.v1.json` - schema

The repo baseline ships:

- 0 requirements `documented`
- 3 requirements `partial` (Req 6, 10, 11 - repo evidence surface only)
- 7 requirements `out_of_scope` (Req 1, 2, 5, 7, 8, 9, 12 - operator infrastructure)
- 2 requirements `not_applicable` (Req 3, 4 - no PAN, no CHD transmission in repo)

ao-kernel does NOT process cardholder data (CHD), does NOT process
sensitive authentication data (SAD), has NO PAN in this repo, has NO
CDE in this repo, and is NOT in PCI-DSS scope at the repo level.
Operator deployment determines whether any CDE exists, what its
boundaries are, and what assessment path applies.

## 2. Operator CDE Scoping (prerequisite to any PCI work)

Before considering SAQ selection or QSA engagement, operator must
perform CDE scoping:

1. Identify systems that store, process, or transmit cardholder data
2. Identify systems connected to those CDE systems (connected-to scope)
3. Identify systems that could impact the security of CDE
4. Document the scope boundary (network, virtualization, identity)
5. Validate the boundary via segmentation testing

ao-kernel ships no CDE scoping conclusion. Operator owns scoping and
its periodic revalidation (PCI-DSS v4.0.1 Req 12.5.1.1, where
applicable).

## 3. SAQ Selection (operator decides)

PCI-DSS v4.0.1 publishes SAQ types A, A-EP, B, B-IP, C, C-VT, D for
Merchants, D for Service Providers, and P2PE. The repo baseline ships
all 9 type slugs as available labels; the JSON instance does NOT
indicate eligibility. Operator + QSA determine eligibility per:

- Merchant level (1-4) determined by annual transaction volume
- Acceptance channels (e-commerce, MOTO, card-present, P2PE-validated)
- Outsourcing model (full outsourcing to PCI-DSS-assessed third-party
  providers vs. partial outsourcing)
- Service provider status (third-party SaaS handling PAN on behalf of a
  merchant)

This runbook does NOT determine which SAQ applies, does NOT determine
merchant level, and does NOT validate eligibility. Operator must
consult with their acquiring bank and engage a QSA.

## 4. QSA Engagement Workflow (operator)

When CDE scoping is complete and SAQ selection determined, operator
engages a QSA via the PCI SSC Approved Companies list. Typical
workflow:

1. Internal pre-readiness gap analysis (operator + internal infosec)
2. RFP issued to multiple QSA companies
3. QSA selection and engagement letter
4. Onboarding + scope reaffirmation
5. Walkthrough + evidence collection
6. Assessment fieldwork
7. Report writing (AOC, optionally ROC for Level 1)
8. Submission to acquiring bank

This runbook does NOT engage QSAs, does NOT issue RFPs, does NOT
produce assessment evidence, and does NOT replace any step of the QSA
engagement workflow.

## 5. ASV Scan Workflow (operator)

PCI-DSS v4.0.1 Req 11.3.2 requires quarterly external vulnerability
scans by an Approved Scanning Vendor (ASV) for in-scope external IPs.
Operator workflow:

1. Identify external-facing CDE IPs
2. Engage an ASV via PCI SSC Approved Companies list
3. Schedule quarterly scans
4. Remediate findings
5. Obtain ASV passing scan report

ao-kernel ships no ASV evidence and does NOT produce ASV reports.
Repo-level vulnerability scanning (E-6-2 Dependabot/Trivy/Snyk) is
application-layer dependency scanning and is NOT an ASV scan.

## 6. Penetration Testing (operator)

PCI-DSS v4.0.1 Req 11.4 requires annual external + internal pen-tests
and tests after significant infrastructure or application changes,
plus segmentation testing for service providers. Operator workflow:

1. Engage a qualified penetration tester
2. Scope the test (external, internal, segmentation, application)
3. Execute the test
4. Remediate findings + retest critical issues

Repo-level SAST (E-6-5 CodeQL) is static analysis and is NOT a
penetration test.

## 7. Public Claim Discipline

Do NOT publish or distribute claims using any of the 32 prohibited
tokens enumerated in
[`pci-dss-control-mapping.v1.json`](pci-dss-control-mapping.v1.json)
under `prohibited_claims`. The scanner enforces this on Markdown
prose. Operator's own assessment results, AOC, and any external
claim are entirely operator and QSA responsibility and are outside
this repo and outside this scanner.

Do NOT use contract-construction language such as `merchant shall`,
`service provider shall`, `AOC shall`, `assessor shall`, `QSA shall`,
`we have completed`, `has been assessed`, `validated by`, `the parties
agree`, or `assessment confirms` in this runbook or in any related
repo artifact. These are operator + counsel territory.

## 8. Cross-AI Peer Review Trail

Per HARD RULE Cross-AI Peer Review (2026-05-05, 2026-05-14):

- Implementer Anthropic Claude -> Reviewer OpenAI Codex.
- Plan-time consensus required for any change to the PCI-DSS schema or
  rendered Markdown.
- Codex iter chain audit trail in
  [`../../.claude/plans/EPIC-6-E6-3D-PCI-DSS-MAPPING.md`](../../.claude/plans/EPIC-6-E6-3D-PCI-DSS-MAPPING.md).

## 9. Out-of-scope follow-up slices

| ID | Slice |
|---|---|
| E-6-3d-2 | Operator CDE scoping worksheet (prerequisite) |
| E-6-3d-3 | SAQ-A operator fill guide (NOT actual SAQ) |
| E-6-3d-4 | ASV scan operator playbook (NOT scan execution) |
| E-6-3d-5 | QSA engagement RFP template (operator) |
| E-6-3d-6 | P2PE solution evaluation checklist (operator) |

## 10. References

- Source catalog: [`pci-dss-control-mapping.v1.json`](pci-dss-control-mapping.v1.json)
- Generated render: [`pci-dss-control-mapping.v1.md`](pci-dss-control-mapping.v1.md)
- Schema: [`../../ao_kernel/defaults/schemas/pci-dss-control-mapping.schema.v1.json`](../../ao_kernel/defaults/schemas/pci-dss-control-mapping.schema.v1.json)
- E-6-3 SOC2/ISO compliance overview: [`README.md`](README.md)
- E-6-3b HIPAA mapping reference: PR #809
- E-6-3c GDPR DPIA operator template: PR #810
- PCI Security Standards Council: https://www.pcisecuritystandards.org/
- HARD RULE Cross-AI Peer Review (2026-05-05, 2026-05-14)
- HARD RULE Uzun Vadeli Kalici Cozum (2026-05-27)
- Codex thread `019e850a` (2-iter REVISE -> AGREE)

## 11. SAQ Source Note

The 9 SAQ display labels in the JSON instance (SAQ A, A-EP, B, B-IP, C,
C-VT, D for Merchants, D for Service Providers, P2PE) are baseline
references from PCI-DSS v4.0.1 publication scope. The JSON schema does
NOT pin the display labels (drift-risk avoidance); the schema pins only
the 9 machine slugs. Operator should re-confirm display labels against
the current PCI SSC v4.0.1 publication when filling in any SAQ-related
material.
