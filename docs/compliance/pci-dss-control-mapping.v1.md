# ao-kernel PCI-DSS Control Reference Mapping (V5 Epic 6 E-6-3d)

> **Documentation only.** **Not certified.** **No AOC.** **No ROC.**
> **No SAQ filed.** **No ASV scan.** ao-kernel does NOT process cardholder
> data (CHD), does NOT process sensitive authentication data (SAD), has
> NO PAN in this repo, and has NO CDE (Cardholder Data Environment). The
> three V5 guard flags (`support_widening`, `production_platform_claim`,
> `live_adapter_execution`) remain `const false`, and three PCI-scoped
> guard flags (`cde_claim_allowed`, `qsa_assessment_claim_allowed`,
> `saq_filing_claim_allowed`) also remain `const false`. Operator MUST
> engage a Qualified Security Assessor (QSA) before any external PCI
> claim.
>
> This document is a control-reference mapping only; it is NOT an
> Attestation of Compliance, NOT a Report on Compliance, NOT a
> Self-Assessment Questionnaire, NOT an ASV scan report, and NOT a
> penetration test report. Operator owns CDE scoping, QSA engagement,
> SAQ selection, ASV vendor selection, and any PCI control operation.
>
> Generated from
> [`pci-dss-control-mapping.v1.json`](pci-dss-control-mapping.v1.json);
> do not edit this rendered document by hand. Regenerate via
> `python scripts/render_pci_dss_docs.py`.

**Framework version:** `PCI-DSS-v4.0.1`

## Cardholder Data Handling Disclosure

- `ao_kernel_processes_chd`: `false`
- `ao_kernel_processes_sad`: `false`
- `no_pan_in_repo`: `true`
- `no_cde_in_repo`: `true`
- `operator_cde_decision`: `true`

## SAQ Applicability

- `repo_baseline_saq`: `none`
- `operator_determines`: `true`
- `available_saq_types` (machine slug + display label):
  - `saq_a` - SAQ A
  - `saq_a_ep` - SAQ A-EP
  - `saq_b` - SAQ B
  - `saq_b_ip` - SAQ B-IP
  - `saq_c` - SAQ C
  - `saq_c_vt` - SAQ C-VT
  - `saq_d_merchant` - SAQ D for Merchants
  - `saq_d_service_provider` - SAQ D for Service Providers
  - `saq_p2pe` - SAQ P2PE

## Requirements (Req 1-12)

### Req 1 - Install and Maintain Network Security Controls

- **Status:** `out_of_scope`
- **Rationale:** Network security controls (firewalls, segmentation) are operator infrastructure responsibility. ao-kernel ships no network-layer surface; no repo evidence of CDE segmentation, firewall ruleset, or network monitoring.
- **Operator boundary:** Operator owns CDE network architecture, segmentation testing, firewall ruleset review cadence, and change control for all PCI-DSS Req 1 sub-requirements.
- **Evidence refs:**
  - (no repo evidence ref; operator-owned)

### Req 2 - Apply Secure Configurations to All System Components

- **Status:** `out_of_scope`
- **Rationale:** Secure baseline configurations for CDE system components are operator infrastructure responsibility. ao-kernel ships application code; OS hardening, vendor default removal, and CIS benchmark adherence are operator-owned.
- **Operator boundary:** Operator owns system component inventory, hardened baseline definition, vendor default removal, and configuration drift detection for all PCI-DSS Req 2 sub-requirements.
- **Evidence refs:**
  - (no repo evidence ref; operator-owned)

### Req 3 - Protect Stored Account Data

- **Status:** `not_applicable`
- **Rationale:** ao-kernel does not store cardholder data (CHD) or sensitive authentication data (SAD). The repo has no_pan_in_repo and no_cde_in_repo per chd_handling_disclosure. Operator deployment determines whether any CDE storage exists.
- **Operator boundary:** Operator owns all CHD/SAD storage architecture, encryption at rest, key management, retention, and secure deletion for all PCI-DSS Req 3 sub-requirements.
- **Evidence refs:**
  - (no repo evidence ref; operator-owned)

### Req 4 - Protect Cardholder Data with Strong Cryptography During Transmission

- **Status:** `not_applicable`
- **Rationale:** ao-kernel does not transmit cardholder data over open public networks. The repo has no_pan_in_repo and no CHD transmission surface. Operator deployment determines whether any CHD transmission occurs.
- **Operator boundary:** Operator owns TLS configuration, cipher suite policy, certificate management, and end-to-end CHD transmission protections for all PCI-DSS Req 4 sub-requirements.
- **Evidence refs:**
  - (no repo evidence ref; operator-owned)

### Req 5 - Protect All Systems and Networks from Malicious Software

- **Status:** `out_of_scope`
- **Rationale:** Anti-malware solution selection, deployment, and signature update cadence are operator OS-layer responsibility. ao-kernel ships no anti-malware surface and makes no AV/EDR evidence claim.
- **Operator boundary:** Operator owns OS-layer anti-malware deployment, signature update cadence, and exception management for all PCI-DSS Req 5 sub-requirements.
- **Evidence refs:**
  - (no repo evidence ref; operator-owned)

### Req 6 - Develop and Maintain Secure Systems and Software

- **Status:** `partial`
- **Rationale:** Repo evidence surface for secure software development practices: dependency vulnerability scanning (E-6-2 Dependabot/Trivy/Snyk), SAST (E-6-5 CodeQL), and software bill of materials (E-6-1 SBOM). This is NOT a CDE secure SDLC claim, NOT a change management attestation, and NOT a PCI control operation. Operator owns CDE-specific SDLC, change approval workflow, code review for CDE components, and PCI-DSS Req 6 compliance.
- **Operator boundary:** Operator owns CDE-specific secure SDLC processes, change management for PCI-scoped systems, and Req 6 control operation; ao-kernel artifacts are advisory evidence surface only.
- **Evidence refs:**
  - **DOC** `docs/compliance/control-evidence-catalog.v1.json` - E-6-3 evidence catalog (SOC2 CC8 change management overlap)

### Req 7 - Restrict Access to System Components and Cardholder Data by Business Need to Know

- **Status:** `out_of_scope`
- **Rationale:** Role-based access control for CDE system components and cardholder data is operator IAM responsibility. ao-kernel ships no IAM surface and makes no access-policy claim for any operator deployment.
- **Operator boundary:** Operator owns IAM design, role definitions, access reviews, joiner-mover-leaver workflow, and least-privilege enforcement for all PCI-DSS Req 7 sub-requirements.
- **Evidence refs:**
  - (no repo evidence ref; operator-owned)

### Req 8 - Identify Users and Authenticate Access to System Components

- **Status:** `out_of_scope`
- **Rationale:** User identification, authentication (MFA), credential lifecycle, and session management are operator IAM responsibility. ao-kernel ships no authentication surface.
- **Operator boundary:** Operator owns identity provider selection, MFA enforcement, credential rotation, session timeout policy, and shared-account elimination for all PCI-DSS Req 8 sub-requirements.
- **Evidence refs:**
  - (no repo evidence ref; operator-owned)

### Req 9 - Restrict Physical Access to Cardholder Data

- **Status:** `out_of_scope`
- **Rationale:** Physical access controls for facilities housing CDE systems are operator facility responsibility. ao-kernel ships no physical-security surface.
- **Operator boundary:** Operator owns physical access policy, badge management, visitor logs, media handling, and on-site media destruction for all PCI-DSS Req 9 sub-requirements.
- **Evidence refs:**
  - (no repo evidence ref; operator-owned)

### Req 10 - Log and Monitor All Access to System Components and Cardholder Data

- **Status:** `partial`
- **Rationale:** Repo evidence surface for application-level observability (E-5-3 distributed tracing + E-5-3b consultation tracing). This is NOT CDE logging, NOT cardholder data access audit, NOT a PCI control operation. Operator owns CDE logging architecture, log retention, SIEM, audit trail integrity, and time-sync per PCI-DSS Req 10.
- **Operator boundary:** Operator owns CDE log source enumeration, retention duration policy, SIEM correlation rules, audit trail integrity controls, and time synchronization per PCI-DSS Req 10 sub-requirements.
- **Evidence refs:**
  - **DOC** `docs/sli-catalog.v1.json` - E-5-4 SLI catalog (application-layer observability index)

### Req 11 - Test Security of Systems and Networks Regularly

- **Status:** `partial`
- **Rationale:** Repo evidence surface for application-layer security testing (E-6-2 Dependabot/Trivy/Snyk + E-6-5 CodeQL SAST). This is NOT ASV scan, NOT penetration test, NOT segmentation test, NOT a PCI control operation. Operator owns ASV engagement, quarterly external scans, internal vulnerability management, segmentation testing, and pen-test cadence per PCI-DSS Req 11.
- **Operator boundary:** Operator owns ASV vendor engagement, external scan cadence, internal vuln remediation workflow, segmentation testing, and pen-test scope/cadence per PCI-DSS Req 11 sub-requirements.
- **Evidence refs:**
  - **DOC** `docs/compliance/control-evidence-catalog.v1.json` - E-6-3 evidence catalog (SOC2 CC7 system operations overlap)

### Req 12 - Support Information Security with Organizational Policies and Programs

- **Status:** `out_of_scope`
- **Rationale:** Organizational information security policy, risk assessment, incident response plan, and security awareness training are operator program responsibility. ao-kernel ships no organizational policy surface.
- **Operator boundary:** Operator owns information security policy framework, annual risk assessment, security awareness training, incident response plan, and third-party management for all PCI-DSS Req 12 sub-requirements.
- **Evidence refs:**
  - (no repo evidence ref; operator-owned)

## Prohibited Public Claims (scanner-enforced)

The following tokens are forbidden in any non-disclaimer prose across the PCI-DSS mapping artifacts. The token list lives in the JSON catalog under `prohibited_claims` and is enforced by `test_no_prohibited_pci_claim_language`.

- `PCI-compliant`
- `PCI compliant`
- `PCI-DSS compliant`
- `PCI DSS compliant`
- `PCI-DSS-compliant`
- `PCI certified`
- `PCI-certified`
- `PCI-DSS certified`
- `PCI-DSS-certified`
- `PCI validated`
- `PCI-validated`
- `PCI-DSS validated`
- `fully PCI-DSS`
- `fully PCI`
- `we comply with PCI-DSS`
- `we comply with PCI`
- `PCI compliance`
- `PCI-DSS compliance`
- `PCI-DSS Level 1`
- `PCI-DSS Level 2`
- `PCI-DSS-approved`
- `PA-DSS compliant`
- `QSA-approved`
- `QSA validated`
- `AOC-ready`
- `ROC-ready`
- `SAQ-A ready`
- `SAQ-D ready`
- `SAQ eligible`
- `eligible for SAQ A`
- `PCI ready`
- `PCI-ready`

## References

- Source catalog: [`pci-dss-control-mapping.v1.json`](pci-dss-control-mapping.v1.json)
- Schema: [`../../ao_kernel/defaults/schemas/pci-dss-control-mapping.schema.v1.json`](../../ao_kernel/defaults/schemas/pci-dss-control-mapping.schema.v1.json)
- Operator runbook: [`pci-dss-operator-scope-and-qsa-engagement-runbook.v1.md`](pci-dss-operator-scope-and-qsa-engagement-runbook.v1.md)
- E-6-3 SOC2/ISO compliance overview: [`README.md`](README.md)
- E-6-3b HIPAA mapping reference: PR #809
- E-6-3c GDPR DPIA operator template: PR #810
- Codex cross-AI plan-time AGREE: thread `019e850a` (2 iters: REVISE -> AGREE)
