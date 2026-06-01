# ao-kernel HIPAA Control Mapping (V5 Epic 6 E-6-3b)

> **Documentation only.** **Not certified.** **Not audited.** ao-kernel
> does NOT process PHI; this mapping is a control-reference document, not
> a HIPAA compliance claim. The three guard flags (`support_widening`,
> `production_platform_claim`, `live_adapter_execution`) remain
> `const false`. Operator MUST consult legal counsel before any external
> claim. **No BAA template** is shipped in this repository.
>
> Generated from
> [`hipaa-control-mapping.v1.json`](hipaa-control-mapping.v1.json); do
> not edit this rendered document by hand. Regenerate via
> `python scripts/render_hipaa_mapping.py`.

**Framework version:** `HIPAA-2003-amended-2013`

## PHI Handling Disclosure

- `ao_kernel_processes_phi`: `false`
- `no_phi_in_repo`: `true`
- `operator_phi_handler_decision`: `true`

## Sections

### Administrative Safeguards (§164.308)

- **Section status:** `mixed`
- **Rationale:** Nine administrative safeguard standards; ao-kernel maps a small subset to repo evidence surfaces (governance ADRs + cross-AI peer review + incident playbook). Other standards remain operator-owned because they require organizational role assignment, workforce training, contingency planning, and business associate contracting.

#### `§164.308(a)(1)` — Security Management Process

- **Status:** `documented`
- **Rationale:** Repo ships governance ADRs and HARD RULE policies that describe security management posture (Pre-Production Full Authority, Cross-AI Peer Review, No Fake Work). Risk analysis program effectiveness is operator-owned.
- **Operator boundary:** Organization-level risk analysis, sanction policy, and information system activity review are operator-owned.
- **Evidence refs:**
  - **DOC** `CLAUDE.md` — Project-level governance posture reference (_documentation only_)

#### `§164.308(a)(2)` — Assigned Security Responsibility

- **Status:** `out_of_scope`
- **Rationale:** Organizational security role assignment is operator-owned.
- **Operator boundary:** Operator designates the security official responsible for HIPAA Security Rule.
- **Evidence refs:**
  - (no repo evidence ref; operator-owned)

#### `§164.308(a)(3)` — Workforce Security

- **Status:** `out_of_scope`
- **Rationale:** Workforce authorization, supervision, and termination are operator-owned HR functions.
- **Operator boundary:** Operator owns workforce clearance and termination procedures.
- **Evidence refs:**
  - (no repo evidence ref; operator-owned)

#### `§164.308(a)(4)` — Information Access Management

- **Status:** `out_of_scope`
- **Rationale:** Access authorization, establishment, and modification are operator-owned.
- **Operator boundary:** Operator owns access management policy and PHI access provisioning.
- **Evidence refs:**
  - (no repo evidence ref; operator-owned)

#### `§164.308(a)(5)` — Security Awareness and Training

- **Status:** `out_of_scope`
- **Rationale:** Workforce security training is operator-owned.
- **Operator boundary:** Operator delivers security awareness training to its workforce.
- **Evidence refs:**
  - (no repo evidence ref; operator-owned)

#### `§164.308(a)(6)` — Security Incident Procedures

- **Status:** `documented`
- **Rationale:** E-6-6 incident response playbook documents the incident management surface (severity matrix + escalation policy + post-mortem template + scenario runbooks). Actual incident execution and HIPAA-specific PHI breach analysis are operator-owned.
- **Operator boundary:** Operator executes incident response, performs PHI breach analysis, and determines HIPAA Breach Notification triggers.
- **Evidence refs:**
  - **PR** `PR #801` — E-6-6 incident response playbook merged (_merge audit trail_)

#### `§164.308(a)(7)` — Contingency Plan

- **Status:** `out_of_scope`
- **Rationale:** Data backup, disaster recovery, and emergency mode operation are operator-owned BCP functions.
- **Operator boundary:** Operator owns BCP, DR plan, and contingency procedures.
- **Evidence refs:**
  - (no repo evidence ref; operator-owned)

#### `§164.308(a)(8)` — Evaluation

- **Status:** `documented`
- **Rationale:** Cross-AI peer review HARD RULE and CI gate document a non-technical evaluation surface for repo-level security posture. Periodic technical and non-technical evaluation of HIPAA Security Rule compliance is operator-owned.
- **Operator boundary:** Operator performs periodic HIPAA Security Rule evaluations.
- **Evidence refs:**
  - **HARD_RULE** `Cross-AI Peer Review (2026-05-05)` — Cross-provider review discipline (_governance rule_)

#### `§164.308(b)` — Business Associate Contracts and Other Arrangements

- **Status:** `out_of_scope`
- **Rationale:** Business Associate Agreements (BAA) are operator-owned contractual instruments. ao-kernel does NOT ship a BAA template.
- **Operator boundary:** Operator negotiates and executes BAAs with covered entities and downstream business associates.
- **Evidence refs:**
  - (no repo evidence ref; operator-owned)

### Physical Safeguards (§164.310)

- **Section status:** `applicable`
- **Rationale:** Four physical safeguard standards covering facility access, workstation use and security, and device/media controls. All four are operator-owned at the hosting and workstation layer; ao-kernel ships no physical infrastructure.

#### `§164.310(a)` — Facility Access Controls

- **Status:** `out_of_scope`
- **Rationale:** Datacenter and facility access is operator-owned.
- **Operator boundary:** Operator owns facility access policy, badge management, and visitor logs.
- **Evidence refs:**
  - (no repo evidence ref; operator-owned)

#### `§164.310(b)` — Workstation Use

- **Status:** `out_of_scope`
- **Rationale:** Workstation usage policy is operator-owned.
- **Operator boundary:** Operator owns workstation use policy for workforce members handling PHI.
- **Evidence refs:**
  - (no repo evidence ref; operator-owned)

#### `§164.310(c)` — Workstation Security

- **Status:** `out_of_scope`
- **Rationale:** Physical workstation security is operator-owned.
- **Operator boundary:** Operator owns physical workstation safeguards.
- **Evidence refs:**
  - (no repo evidence ref; operator-owned)

#### `§164.310(d)` — Device and Media Controls

- **Status:** `out_of_scope`
- **Rationale:** Device disposal, re-use, and media accountability are operator-owned.
- **Operator boundary:** Operator owns device lifecycle and media accountability procedures.
- **Evidence refs:**
  - (no repo evidence ref; operator-owned)

### Technical Safeguards (§164.312)

- **Section status:** `applicable`
- **Rationale:** Five technical safeguard standards covering access control, audit controls, integrity, authentication, and transmission security. All five are operator-owned at the ePHI layer; ao-kernel does NOT process PHI and ships no ePHI control. Repo evidence surfaces such as JSONL audit trails and SHA256 manifests address artifact-level audit and integrity only and are NOT ePHI control claims.

#### `§164.312(a)` — Access Control

- **Status:** `out_of_scope`
- **Rationale:** ePHI access control (unique user identification, emergency access, automatic logoff, encryption/decryption) is operator-owned. ao-kernel does NOT implement ePHI access control.
- **Operator boundary:** Operator owns ePHI access control implementation.
- **Evidence refs:**
  - (no repo evidence ref; operator-owned)

#### `§164.312(b)` — Audit Controls

- **Status:** `out_of_scope`
- **Rationale:** Repo evidence surface only (JSONL append-only audit log + SHA256 integrity manifest) for repo artifacts. This is NOT an ePHI audit control operation claim. Operator deploys the actual ePHI audit infrastructure.
- **Operator boundary:** Operator owns ePHI audit control infrastructure.
- **Evidence refs:**
  - (no repo evidence ref; operator-owned)

#### `§164.312(c)` — Integrity

- **Status:** `out_of_scope`
- **Rationale:** Repo artifact integrity manifests (SHA256) cover committed artifact integrity only. This is NOT an ePHI data integrity control claim. Operator owns ePHI data integrity at rest and in transit.
- **Operator boundary:** Operator owns ePHI data integrity controls.
- **Evidence refs:**
  - (no repo evidence ref; operator-owned)

#### `§164.312(d)` — Person or Entity Authentication

- **Status:** `out_of_scope`
- **Rationale:** ePHI authentication is operator-owned at the auth/SSO layer.
- **Operator boundary:** Operator owns authentication implementation.
- **Evidence refs:**
  - (no repo evidence ref; operator-owned)

#### `§164.312(e)` — Transmission Security

- **Status:** `out_of_scope`
- **Rationale:** ePHI transmission security (TLS, integrity, encryption) is operator-owned at the transport layer.
- **Operator boundary:** Operator owns transmission security at the TLS and transport layer.
- **Evidence refs:**
  - (no repo evidence ref; operator-owned)

### Privacy Rule (§164.500-534)

- **Section status:** `not_applicable`
- **Rationale:** ao-kernel does NOT process PHI. The HIPAA Privacy Rule applies to covered entities and business associates handling PHI; ao-kernel is not a PHI handler. If the operator handles PHI, the Privacy Rule applies to the operator and is the operator's responsibility.

(No controls listed; section is `not_applicable`.)

### Breach Notification (§164.402-414)

- **Section status:** `not_applicable`
- **Rationale:** ao-kernel does NOT process PHI and is not a covered entity or business associate under HIPAA. HIPAA Breach Notification applies to PHI breaches; if the operator handles PHI, breach determination, notification (individual, HHS, media as applicable), and timeline tracking are operator and operator legal-counsel responsibilities.

(No controls listed; section is `not_applicable`.)

## Prohibited Public Claims (scanner-enforced)

The following tokens are forbidden in any non-disclaimer prose across the HIPAA mapping artifacts. The token list lives in the JSON catalog under `prohibited_claims` and is enforced by `test_no_prohibited_hipaa_claim_language`.

- `hipaa compliant`
- `hipaa-compliant`
- `hipaa certified`
- `hipaa-certified`
- `phi-safe`
- `baa-ready`
- `we comply with hipaa`
- `hipaa-grade`
- `fully hipaa`
- `guaranteed phi protection`

## References

- Source catalog: [`hipaa-control-mapping.v1.json`](hipaa-control-mapping.v1.json)
- Schema: [`../../ao_kernel/defaults/schemas/hipaa-control-mapping.schema.v1.json`](../../ao_kernel/defaults/schemas/hipaa-control-mapping.schema.v1.json)
- E-6-3 SOC2/ISO compliance overview: [`README.md`](README.md)
- E-6-6 incident response playbook: PR #801 MERGED
- Codex cross-AI plan-time AGREE: thread `019e84ee` (2 iters: REVISE → AGREE)
