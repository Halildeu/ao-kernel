# ao-kernel NIST CSF Function / Category Reference Mapping (V5 Epic 6 E-6-3e)

> **Documentation only.** **NIST CSF is a voluntary risk management
> framework.** **NIST does NOT operate a CSF certification program.** No
> AOC, no audit report, no CISA attestation. ao-kernel claims no
> Implementation Tier and ships no organizational CSF Profile. The
> three V5 guard flags (`support_widening`, `production_platform_claim`,
> `live_adapter_execution`) remain `const false`, and three CSF-scoped
> guard flags (`csf_certification_claim_allowed`,
> `csf_tier_claim_allowed`, `csf_profile_claim_allowed`) also remain
> `const false`.
>
> This document is a Function/Category reference mapping only; it is
> NOT a 106-Subcategory deep-dive, NOT a Profile (Current/Target), NOT
> an Implementation Tier assessment, and NOT an implementation plan.
> Operator owns risk management strategy, organizational context,
> Profile creation, and any external claim.
>
> Generated from
> [`nist-csf-control-mapping.v1.json`](nist-csf-control-mapping.v1.json);
> do not edit this rendered document by hand. Regenerate via
> `python scripts/render_nist_csf_docs.py`.

**Framework version:** `NIST-CSF-2.0`

## CSF Tier Disclosure

- `ao_kernel_claims_tier`: `none`
- `tier_assessment_operator_owned`: `true`
- `available_tiers` (disclosure only; not claimed):
  - `partial`
  - `risk_informed`
  - `repeatable`
  - `adaptive`

## CSF Profile Disclosure

- `ao_kernel_is_organization`: `false`
- `no_csf_profile_in_repo`: `true`
- `operator_csf_profile_owner`: `true`

## Functions (GV / ID / PR / DE / RS / RC)

### `GV` - GOVERN

- **Function status:** `partial`

#### `GV.OC` - Organizational Context

- **Status:** `out_of_scope`
- **Rationale:** Organizational context (mission, stakeholders, legal requirements) is operator program responsibility. ao-kernel ships no organizational context surface.
- **Operator boundary:** Operator owns mission alignment, stakeholder mapping, and legal/regulatory environment determination per NIST CSF 2.0 GV.OC.
- **Evidence refs:**
  - (no repo evidence ref; operator-owned)

#### `GV.RM` - Risk Management Strategy

- **Status:** `out_of_scope`
- **Rationale:** Risk management strategy is operator program responsibility. ao-kernel ships no risk management strategy surface.
- **Operator boundary:** Operator owns risk appetite, risk tolerance, risk hierarchy, and enterprise risk strategy per NIST CSF 2.0 GV.RM.
- **Evidence refs:**
  - (no repo evidence ref; operator-owned)

#### `GV.RR` - Roles, Responsibilities, and Authorities

- **Status:** `out_of_scope`
- **Rationale:** Organizational roles and authorities are operator program responsibility. ao-kernel ships no role/authority surface.
- **Operator boundary:** Operator owns role definitions, responsibilities matrix, and authority delegations per NIST CSF 2.0 GV.RR.
- **Evidence refs:**
  - (no repo evidence ref; operator-owned)

#### `GV.PO` - Policy

- **Status:** `partial`
- **Rationale:** Repo evidence surface for development governance: ADRs and HARD RULEs in CLAUDE.md. This is NOT an organizational security policy framework and NOT an operating control attestation.
- **Operator boundary:** Operator owns organizational policy framework, policy publication cadence, employee acknowledgment, and policy exception management per NIST CSF 2.0 GV.PO.
- **Evidence refs:**
  - **DOC** `CLAUDE.md` - Project HARD RULEs and decision discipline (_evidence surface only; not operating effectiveness_)

#### `GV.OV` - Oversight

- **Status:** `out_of_scope`
- **Rationale:** Cybersecurity oversight is operator board/leadership responsibility. ao-kernel ships no oversight surface.
- **Operator boundary:** Operator owns board reporting, executive review cadence, and oversight performance measurement per NIST CSF 2.0 GV.OV.
- **Evidence refs:**
  - (no repo evidence ref; operator-owned)

#### `GV.SC` - Supply Chain Risk Management

- **Status:** `out_of_scope`
- **Rationale:** Supply chain risk management is operator program responsibility. ao-kernel ships dependency manifests as evidence surface but operator owns supplier risk assessment.
- **Operator boundary:** Operator owns supplier risk assessment, third-party security assessments, vendor SLA review, and supply chain incident response per NIST CSF 2.0 GV.SC.
- **Evidence refs:**
  - (no repo evidence ref; operator-owned)

### `ID` - IDENTIFY

- **Function status:** `partial`

#### `ID.AM` - Asset Management

- **Status:** `partial`
- **Rationale:** Repo evidence surface for software bill of materials (E-6-1 SBOM). This is partial asset inventory for ao-kernel software components only; it is NOT a complete operator asset inventory and NOT an operating control attestation.
- **Operator boundary:** Operator owns deployment-time asset inventory, hardware inventory, data flow inventory, and asset criticality determination per NIST CSF 2.0 ID.AM.
- **Evidence refs:**
  - **DOC** `docs/compliance/control-evidence-catalog.v1.json` - E-6-3 evidence catalog (SBOM index) (_evidence surface only; not operating effectiveness_)

#### `ID.RA` - Risk Assessment

- **Status:** `out_of_scope`
- **Rationale:** Organizational risk assessment is operator program responsibility. ao-kernel ships no risk assessment surface.
- **Operator boundary:** Operator owns risk assessment methodology, risk register, risk treatment plan, and risk acceptance per NIST CSF 2.0 ID.RA.
- **Evidence refs:**
  - (no repo evidence ref; operator-owned)

#### `ID.IM` - Improvement

- **Status:** `partial`
- **Rationale:** Repo evidence surface for application-layer security improvement: E-6-1 SBOM + E-6-2 vulnerability scanning + E-6-5 CodeQL SAST. This is NOT a complete cybersecurity improvement program and NOT an operating control attestation.
- **Operator boundary:** Operator owns continuous improvement program, lessons-learned integration, and improvement priority determination per NIST CSF 2.0 ID.IM.
- **Evidence refs:**
  - **DOC** `docs/compliance/control-evidence-catalog.v1.json` - E-6-3 evidence catalog (SBOM + vuln scan + SAST) (_evidence surface only; not operating effectiveness_)

### `PR` - PROTECT

- **Function status:** `out_of_scope`

#### `PR.AA` - Identity Management, Authentication, and Access Control

- **Status:** `out_of_scope`
- **Rationale:** Identity, authentication, and access control are operator IAM responsibility. ao-kernel ships no IAM surface.
- **Operator boundary:** Operator owns IAM design, MFA enforcement, credential lifecycle, access reviews, and least-privilege enforcement per NIST CSF 2.0 PR.AA.
- **Evidence refs:**
  - (no repo evidence ref; operator-owned)

#### `PR.AT` - Awareness and Training

- **Status:** `out_of_scope`
- **Rationale:** Security awareness and training are operator HR program responsibility. ao-kernel ships no awareness/training surface.
- **Operator boundary:** Operator owns awareness training curriculum, training cadence, and effectiveness measurement per NIST CSF 2.0 PR.AT.
- **Evidence refs:**
  - (no repo evidence ref; operator-owned)

#### `PR.DS` - Data Security

- **Status:** `out_of_scope`
- **Rationale:** Data security controls (encryption at rest, key management, data classification) are operator infrastructure responsibility. ao-kernel ships no data-security operating surface.
- **Operator boundary:** Operator owns data classification, encryption at rest, key management, data loss prevention, and data secure-disposal per NIST CSF 2.0 PR.DS.
- **Evidence refs:**
  - (no repo evidence ref; operator-owned)

#### `PR.PS` - Platform Security

- **Status:** `out_of_scope`
- **Rationale:** Platform security (OS hardening, secure boot, configuration management) is operator infrastructure responsibility. ao-kernel ships no platform-security surface.
- **Operator boundary:** Operator owns OS/platform hardening baseline, secure boot, configuration management, and patch cadence per NIST CSF 2.0 PR.PS.
- **Evidence refs:**
  - (no repo evidence ref; operator-owned)

#### `PR.IR` - Technology Infrastructure Resilience

- **Status:** `out_of_scope`
- **Rationale:** Infrastructure resilience (HA architecture, capacity planning, segmentation) is operator infrastructure responsibility.
- **Operator boundary:** Operator owns HA architecture, capacity planning, network segmentation, and resilience testing per NIST CSF 2.0 PR.IR.
- **Evidence refs:**
  - (no repo evidence ref; operator-owned)

### `DE` - DETECT

- **Function status:** `partial`

#### `DE.CM` - Continuous Monitoring

- **Status:** `partial`
- **Rationale:** Repo evidence surface for application-layer observability: E-5-3 distributed tracing + E-5-3b consultation tracing. This is limited application-layer telemetry only; it is NOT enterprise SIEM, NOT network monitoring, and NOT an operating control attestation.
- **Operator boundary:** Operator owns enterprise SIEM, log aggregation, network monitoring, endpoint detection, and monitoring policy per NIST CSF 2.0 DE.CM.
- **Evidence refs:**
  - **DOC** `docs/sli-catalog.v1.json` - E-5-4 SLI catalog (application-layer observability index) (_evidence surface only; not operating effectiveness_)

#### `DE.AE` - Adverse Event Analysis

- **Status:** `partial`
- **Rationale:** Repo evidence surface for adverse-event tracing context: E-5-3 distributed tracing supports event correlation. This is application-layer tracing only; it is NOT incident detection automation and NOT an operating control attestation.
- **Operator boundary:** Operator owns incident detection rules, alert triage, threat intelligence integration, and adverse-event analysis program per NIST CSF 2.0 DE.AE.
- **Evidence refs:**
  - **DOC** `docs/sli-catalog.v1.json` - E-5-4 SLI catalog (event correlation index) (_evidence surface only; not operating effectiveness_)

### `RS` - RESPOND

- **Function status:** `partial`

#### `RS.MA` - Incident Management

- **Status:** `documented`
- **Rationale:** Repo evidence surface for incident response playbook (E-6-6 PR #801): documented incident management workflow with roles, triage, communications, and post-incident review. This is evidence surface only; not operating effectiveness.
- **Operator boundary:** Operator owns incident response team, on-call rotation, communication channels, and live incident command per NIST CSF 2.0 RS.MA.
- **Evidence refs:**
  - **PR** `PR #801` - E-6-6 incident response playbook (_evidence surface only; not operating effectiveness_)

#### `RS.AN` - Incident Analysis

- **Status:** `documented`
- **Rationale:** Repo evidence surface for incident analysis: E-6-6 incident response playbook + E-5-3 distributed tracing for forensic correlation. This is evidence surface only; not operating effectiveness.
- **Operator boundary:** Operator owns incident forensic investigation, scope determination, root-cause analysis, and analysis quality per NIST CSF 2.0 RS.AN.
- **Evidence refs:**
  - **PR** `PR #801` - E-6-6 incident response playbook (analysis section) (_evidence surface only; not operating effectiveness_)

#### `RS.CO` - Incident Response Reporting and Communication

- **Status:** `out_of_scope`
- **Rationale:** Incident response reporting and external communication are operator program responsibility (customer notification, regulator notification, public disclosure).
- **Operator boundary:** Operator owns external communication, customer notification, regulator disclosure, and stakeholder reporting per NIST CSF 2.0 RS.CO.
- **Evidence refs:**
  - (no repo evidence ref; operator-owned)

#### `RS.MI` - Incident Mitigation

- **Status:** `out_of_scope`
- **Rationale:** Incident mitigation actions (containment, eradication) require operator deployment context; ao-kernel ships no live mitigation surface.
- **Operator boundary:** Operator owns containment actions, eradication, threat mitigation, and live mitigation effectiveness measurement per NIST CSF 2.0 RS.MI.
- **Evidence refs:**
  - (no repo evidence ref; operator-owned)

### `RC` - RECOVER

- **Function status:** `out_of_scope`

#### `RC.RP` - Incident Recovery Plan Execution

- **Status:** `out_of_scope`
- **Rationale:** Incident recovery plan execution is operator BCP/DR responsibility. ao-kernel ships no recovery execution surface.
- **Operator boundary:** Operator owns recovery plan, RTO/RPO targets, backup/restore procedures, and recovery testing per NIST CSF 2.0 RC.RP.
- **Evidence refs:**
  - (no repo evidence ref; operator-owned)

#### `RC.CO` - Incident Recovery Communication

- **Status:** `out_of_scope`
- **Rationale:** Incident recovery communication is operator program responsibility. ao-kernel ships no recovery communication surface.
- **Operator boundary:** Operator owns recovery communication plan, stakeholder updates, and service restoration messaging per NIST CSF 2.0 RC.CO.
- **Evidence refs:**
  - (no repo evidence ref; operator-owned)

## Prohibited Public Claims (scanner-enforced)

The following tokens are forbidden in any non-disclaimer prose across the NIST CSF mapping artifacts. The token list lives in the JSON catalog under `prohibited_claims` and is enforced by `test_no_prohibited_csf_claim_language`.

- `NIST CSF certified`
- `NIST-certified`
- `NIST CSF compliant`
- `CSF compliant`
- `CSF-compliant`
- `fully implements CSF`
- `CSF Profile complete`
- `Target Profile complete`
- `Current Profile complete`
- `Target Profile achieved`
- `Implementation Tier achieved`
- `CSF audit`
- `CSF attested`
- `NIST validated`
- `CISA approved`
- `CISA validated`
- `CSF maturity level`
- `CSF maturity score`

## References

- Source catalog: [`nist-csf-control-mapping.v1.json`](nist-csf-control-mapping.v1.json)
- Schema: [`../../ao_kernel/defaults/schemas/nist-csf-control-mapping.schema.v1.json`](../../ao_kernel/defaults/schemas/nist-csf-control-mapping.schema.v1.json)
- Operator runbook: [`nist-csf-operator-usage-runbook.v1.md`](nist-csf-operator-usage-runbook.v1.md)
- E-6-3 SOC2/ISO compliance overview: [`README.md`](README.md)
- E-6-3b HIPAA mapping reference: PR #809
- E-6-3c GDPR DPIA operator template: PR #810
- E-6-3d PCI-DSS control reference mapping: PR #811
- Codex cross-AI plan-time AGREE: thread `019e8516` (2 iters: REVISE -> AGREE)
