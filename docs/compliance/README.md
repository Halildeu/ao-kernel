# ao-kernel Compliance Posture Documentation (V5 Epic 6 E-6-3)

> **Not certified.** **Not audited.** **Documentation only.** This package
> provides a control-reference mapping and evidence index — not an audit
> attestation, certification statement, or compliance claim. The three guard
> flags (`support_widening`, `production_platform_claim`,
> `live_adapter_execution`) remain `const false`. Operator owns audit
> engagement, certification scope, and regulatory determination.
>
> **Local/operator smoke is not production evidence.** Repo-owned control
> surface presence does not constitute control operation effectiveness;
> that determination is operator and auditor responsibility.
>
> **No vendor SLA terms; no customer compliance promise; no regulatory
> disclosure authority.**

## 0. Disclaimer

This package contains:

- A schema-backed control-reference catalog
  ([`control-evidence-catalog.v1.json`](control-evidence-catalog.v1.json))
- Deterministic Markdown renders for SOC2 Trust Service Categories and
  ISO 27001:2022 Annex A
- An invariant test suite enforcing wording discipline and structural
  parity

This package does NOT contain:

- Compliance claims (`we comply with`, `soc2 compliant`, `iso compliant`,
  `meets soc2`, `meets iso 27001`, `certification-ready`, `audit-ready`)
- Certification or attestation statements (`certified`, `audited` — only
  used in negation prose: "Not certified", "Not audited")
- Vendor questionnaire response templates
- Pen-test reports
- Audit report templates
- Customer compliance commitment language

## 1. Source of Truth

The canonical source of truth is
[`control-evidence-catalog.v1.json`](control-evidence-catalog.v1.json),
validated by
[`../../ao_kernel/defaults/schemas/control-evidence-catalog.schema.v1.json`](../../ao_kernel/defaults/schemas/control-evidence-catalog.schema.v1.json).

Two Markdown renders are deterministically generated from the catalog:

| File | Framework |
|---|---|
| [`soc2-trust-services-criteria-mapping.v1.md`](soc2-trust-services-criteria-mapping.v1.md) | SOC2 Trust Service Categories (CC1–CC9 + A/C/PI/P) |
| [`iso-27001-controls-mapping.v1.md`](iso-27001-controls-mapping.v1.md) | ISO 27001:2022 Annex A (A.5–A.18) |

Regenerate via `python scripts/render_compliance_docs.py`. The drift test
(`test_drift_committed_matches_generated`) asserts byte-equal parity
between the rendered files and the canonical catalog.

## 2. Status Enum

Each control declares one of four `ao_kernel_status` values:

| Status | Meaning |
|---|---|
| `documented` | Repo evidence surface documented (artifact present; not an audit claim) |
| `partial` | Some repo evidence surface plus explicit operator-owned gap |
| `out_of_scope` | Operator-owned domain; no repo evidence surface |
| `not_applicable` | Control does not apply to ao-kernel's repo scope |

Status `documented` means **artifact present in repo**, not **control
operating effectively**. Audit-level effectiveness determination is
operator and auditor responsibility.

## 3. SOC2 Coverage Summary (13 entries)

| Tier | Status |
|---|---|
| CC1 Control Environment | `documented` |
| CC2 Communication and Information | `partial` |
| CC3 Risk Assessment | `partial` |
| CC4 Monitoring Activities | `partial` |
| CC5 Control Activities | `partial` |
| CC6 Logical and Physical Access | `partial` |
| CC7 System Operations | `partial` |
| CC8 Change Management | `partial` |
| CC9 Risk Mitigation | `partial` |
| A Availability | `partial` (uptime SLI explicitly out of scope in v1) |
| C Confidentiality | `partial` |
| PI Processing Integrity | `partial` |
| P Privacy | `out_of_scope` |

See full per-control detail in
[`soc2-trust-services-criteria-mapping.v1.md`](soc2-trust-services-criteria-mapping.v1.md).

### 3.5 HIPAA Mapping Reference (E-6-3b extension)

A separate HIPAA control-reference mapping lives at
[`hipaa-control-mapping.v1.json`](hipaa-control-mapping.v1.json) (rendered
as [`hipaa-control-mapping.v1.md`](hipaa-control-mapping.v1.md)).

The HIPAA mapping enumerates 5 sections (Administrative + Physical +
Technical Safeguards + Privacy Rule + Breach Notification). ao-kernel
does NOT process PHI; Privacy Rule and Breach Notification are
`section_status: "not_applicable"`. Technical Safeguards are
`out_of_scope` because ePHI controls are operator-owned.

The mapping ships its own schema, prohibited-claims scanner, and PHI/BAA
scanner; it is **not** an extension of the SOC2/ISO catalog and does
NOT modify any E-6-3 contract.

### 3.6 GDPR DPIA Operator Template Reference (E-6-3c extension)

A separate GDPR DPIA operator template lives at
[`gdpr-dpia-template.v1.json`](gdpr-dpia-template.v1.json) (rendered as
[`gdpr-dpia-template.v1.md`](gdpr-dpia-template.v1.md)), with the
operator runbook in
[`gdpr-dpia-operator-runbook.v1.md`](gdpr-dpia-operator-runbook.v1.md).

The template enumerates 7 sections (Metadata + trigger assessment;
Systematic Description; Necessity and Proportionality; Risks;
Mitigation; Consultation; Decision and Approval). ao-kernel does NOT
process personal data, is NOT a data controller, and is NOT a data
processor in v1; the repo baseline ships all Section A fields as
`<no-personal-data-in-repo-baseline>` and all Section C risks as
`risk_status: "not_applicable"`.

The template ships its own schema and prohibited-claims scanner; it
is **not** an extension of the SOC2/ISO catalog and does NOT modify
any E-6-3 contract. This template does NOT determine lawful basis,
controller/processor role, transfer mechanism, DPA filing need, or
data subject notice content; Article 36 prior consultation
determination remains operator + DPO/counsel responsibility.

### 3.7 PCI-DSS Control Reference Mapping (E-6-3d extension)

A separate PCI-DSS v4.0.1 control reference mapping lives at
[`pci-dss-control-mapping.v1.json`](pci-dss-control-mapping.v1.json)
(rendered as
[`pci-dss-control-mapping.v1.md`](pci-dss-control-mapping.v1.md)),
with the operator scope/QSA engagement runbook in
[`pci-dss-operator-scope-and-qsa-engagement-runbook.v1.md`](pci-dss-operator-scope-and-qsa-engagement-runbook.v1.md).

The mapping enumerates 12 requirements (Req 1-12). ao-kernel does
NOT process cardholder data (CHD), does NOT process sensitive
authentication data (SAD), has NO PAN in this repo, has NO CDE in
this repo, and is NOT in PCI-DSS scope at the repo level. The
mapping ships its own schema, prohibited-claims scanner, and PAN/SAD
sample scanner; it is **not** an extension of the SOC2/ISO catalog
and does NOT modify any E-6-3 contract. This mapping is NOT an AOC,
NOT a ROC, NOT a SAQ, NOT an ASV scan report, and NOT a pen-test
report.

## 4. ISO 27001 Annex A Coverage Summary (14 areas)

| Annex A area | Status |
|---|---|
| A.5 Information security policies | `out_of_scope` |
| A.6 Organization of information security | `out_of_scope` |
| A.7 Human resources security | `out_of_scope` |
| A.8 Asset management | `partial` |
| A.9 Access control | `out_of_scope` |
| A.10 Cryptography | `out_of_scope` |
| A.11 Physical and environmental security | `out_of_scope` |
| A.12 Operations security | `partial` |
| A.13 Communications security | `out_of_scope` |
| A.14 System acquisition, development, and maintenance | `partial` |
| A.15 Supplier relationships | `partial` |
| A.16 Information security incident management | `partial` |
| A.17 Information security aspects of business continuity | `out_of_scope` |
| A.18 Compliance | `partial` |

See full per-control detail in
[`iso-27001-controls-mapping.v1.md`](iso-27001-controls-mapping.v1.md).

## 5. Operator Boundary

ao-kernel ships **repo artifacts + evidence references**. The following
domains are explicitly operator-owned and out of repo scope:

- Auditor engagement, certification scope determination, attestation
- Authentication, SSO, MFA, access provisioning, key management
- Transport encryption, TLS, cryptographic key custody
- Physical security, datacenter controls, environmental controls
- HR (hiring, training, termination)
- BCP, DR plan, RTO/RPO target setting
- Vendor contract negotiation, supplier SLA review
- Privacy program (DPIA, ROPA, data subject rights)
- Regulatory disclosure determination (GDPR, HIPAA, jurisdiction-specific)
- Live deployment evidence, customer notification, tabletop exercises
- Incident on-call rotation, postmortem distribution cadence

## 6. Wording Discipline

The catalog declares a `prohibited_claims` array enforced by
`test_no_compliance_claim_language`. Forbidden tokens (rendered as inline
code to keep the scanner clean — these are documentation of the discipline,
not active claims):

- `we comply with`
- `soc2 compliant`
- `iso compliant`
- `meets soc2`
- `meets iso 27001`
- `certification-ready`
- `audit-ready`
- `certified` (allowed only in negation prose)
- `audited` (allowed only in negation prose)
- `control implemented`

**Negation bypass scope:** Only the `certified` and `audited` tokens may
appear in negation prose ("Not certified", "Not audited", "non-certified",
"never audited"). All other forbidden tokens fail unconditionally.

## 7. Evidence Reference Types

Each control declares a `evidence_refs` array of typed evidence pointers:

| Type | Format | Example |
|---|---|---|
| `pr` | `PR #<id>` | `PR #799` |
| `adr` | `ADR-<id>` | `ADR-0029` |
| `hard_rule` | `<name> (<date>)` | `Cross-AI Peer Review (2026-05-05)` |
| `doc` | repo path | `docs/sli-catalog.v1.json` |
| `test` | repo path | `tests/test_compliance_documentation.py` |
| `source` | repo path | `ao_kernel/ao_release_gate.py` |

`test_evidence_refs_paths_exist` asserts that `doc`, `test`, and `source`
references point to existing repo paths. `pr` and `hard_rule` refs are
format-validated.

## 8. Cross-AI Peer Review Discipline

Per HARD RULE Cross-AI Peer Review (2026-05-05, 2026-05-14):

- Implementer Anthropic Claude → Reviewer OpenAI Codex (this PR).
- Plan-time consensus required for any change to the catalog schema or
  the rendered Markdown contracts.
- Codex iter chain audit trail in
  [`../../.claude/plans/EPIC-6-E6-3-SOC2-ISO-COMPLIANCE-DOCS.md`](../../.claude/plans/EPIC-6-E6-3-SOC2-ISO-COMPLIANCE-DOCS.md).

## 9. Out of Scope (E-6-3 follow-up slices)

| ID | Slice |
|---|---|
| E-6-3b | HIPAA mapping (US healthcare) |
| E-6-3c | GDPR DPIA template (operator-owned) |
| E-6-3d | PCI-DSS mapping |
| E-6-3e | NIST CSF mapping |
| E-6-3f | Vendor security questionnaire response (operator-owned, context-specific) |
| E-6-3g | SOC2 Type II audit engagement runbook (operator action) |
| E-6-3h | ISO Statement of Applicability operator template (operator action) |

## 10. References

- V5 roadmap: [`../../.claude/plans/V5-FULL-PRODUCTION-PROMOTION-ROADMAP.md`](../../.claude/plans/V5-FULL-PRODUCTION-PROMOTION-ROADMAP.md)
- E-5-4 catalog: [`../sli-catalog.v1.json`](../sli-catalog.v1.json) (PR #799)
- E-5-5 alerts (post PR #800): `docs/alertmanager/` directory
- E-6-6 incident response (post PR #801): `docs/incident-response/` directory
- HARD RULE Cross-AI Peer Review (2026-05-05, 2026-05-14)
- HARD RULE Workspace Tooling (2026-05-27)
- Codex cross-AI plan-time AGREE: thread `019e83d1` (2 iters: REVISE → AGREE)
