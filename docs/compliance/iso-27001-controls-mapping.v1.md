# ISO 27001:2022 Annex A — Control-Reference Mapping (V5 Epic 6 E-6-3)

> **Not certified.** **Not audited.** **Documentation only.** This document is
> a control-reference mapping and evidence index, not an audit attestation,
> certification statement, or compliance claim. Operator owns audit engagement,
> certification scope, and regulatory determination. The three guard flags
> (`support_widening`, `production_platform_claim`, `live_adapter_execution`)
> remain `const false`. Generated from
> [`control-evidence-catalog.v1.json`](control-evidence-catalog.v1.json); do
> not edit this rendered document by hand. Regenerate via
> `python scripts/render_compliance_docs.py`.
>
> **Local/operator smoke is not production evidence.** Repo-owned control
> surface presence does not constitute control operation effectiveness; that
> determination is operator and auditor responsibility.

**Framework version:** `ISO-27001-2022`

This document maps ao-kernel repo artifacts to ISO 27001:2022 Annex A control areas (A.5 through A.18). It is a control-reference mapping, not an audit attestation.

## Control-Reference Mapping

| Control | Name | Status | Operator Boundary |
|---|---|---|---|
| `A.5` | Information security policies | `out_of_scope` | Operator owns information security policy authorship and approval |
| `A.6` | Organization of information security | `out_of_scope` | Operator owns role definition and segregation-of-duties matrix |
| `A.7` | Human resources security | `out_of_scope` | Operator owns hiring, training, and termination procedures |
| `A.8` | Asset management | `partial` | Operator owns physical asset inventory and organizational ownership records |
| `A.9` | Access control | `out_of_scope` | Operator owns access control policy, provisioning, and review |
| `A.10` | Cryptography | `out_of_scope` | Operator owns TLS, KMS, and key rotation |
| `A.11` | Physical and environmental security | `out_of_scope` | Operator owns datacenter and physical environment controls |
| `A.12` | Operations security | `partial` | Operator owns live monitoring deployment and operational change board |
| `A.13` | Communications security | `out_of_scope` | Operator owns network segmentation and transport encryption |
| `A.14` | System acquisition, development, and maintenance | `partial` | Operator owns production maintenance cadence and post-deploy verification |
| `A.15` | Supplier relationships | `partial` | Operator owns vendor contract, SLA review, and supplier risk assessment |
| `A.16` | Information security incident management | `partial` | Operator owns incident on-call rotation, customer notification, tabletop exer... |
| `A.17` | Information security aspects of business continuity | `out_of_scope` | Operator owns BCP, DR plan, and RTO/RPO target setting |
| `A.18` | Compliance | `partial` | Operator owns auditor engagement, certification scope, and regulatory determi... |

## Per-Control Details

### `A.5` — Information security policies

- **Status:** `out_of_scope`
- **Rationale:** Organization-level information security policy is operator-owned.
- **Operator boundary:** Operator owns information security policy authorship and approval.
- **Evidence refs:**
  - (no repo evidence ref; operator-owned)

### `A.6` — Organization of information security

- **Status:** `out_of_scope`
- **Rationale:** Organization-level role definition is operator-owned.
- **Operator boundary:** Operator owns role definition and segregation-of-duties matrix.
- **Evidence refs:**
  - (no repo evidence ref; operator-owned)

### `A.7` — Human resources security

- **Status:** `out_of_scope`
- **Rationale:** Human resources controls are operator-owned.
- **Operator boundary:** Operator owns hiring, training, and termination procedures.
- **Evidence refs:**
  - (no repo evidence ref; operator-owned)

### `A.8` — Asset management

- **Status:** `partial`
- **Rationale:** SBOM generator (E-6-1a) documents software asset inventory; physical and organizational asset management is operator-owned.
- **Operator boundary:** Operator owns physical asset inventory and organizational ownership records.
- **Evidence refs:**
  - **PR** `PR #795` — E-6-1a SBOM generator (CycloneDX 1.5) (_merge audit trail_)

### `A.9` — Access control

- **Status:** `out_of_scope`
- **Rationale:** Logical access control is operator-owned.
- **Operator boundary:** Operator owns access control policy, provisioning, and review.
- **Evidence refs:**
  - (no repo evidence ref; operator-owned)

### `A.10` — Cryptography

- **Status:** `out_of_scope`
- **Rationale:** Cryptographic controls are operator-owned at transport layer.
- **Operator boundary:** Operator owns TLS, KMS, and key rotation.
- **Evidence refs:**
  - (no repo evidence ref; operator-owned)

### `A.11` — Physical and environmental security

- **Status:** `out_of_scope`
- **Rationale:** Physical security is operator-owned at hosting layer.
- **Operator boundary:** Operator owns datacenter and physical environment controls.
- **Evidence refs:**
  - (no repo evidence ref; operator-owned)

### `A.12` — Operations security

- **Status:** `partial`
- **Rationale:** Incident response playbook (E-6-6), monitoring surface (E-5-1/2/3/4/5), and SBOM/scanning (E-6-1/2/5) document operations security artifacts.
- **Operator boundary:** Operator owns live monitoring deployment and operational change board.
- **Evidence refs:**
  - **PR** `PR #801` — E-6-6 incident response playbook (_merge audit trail_)

### `A.13` — Communications security

- **Status:** `out_of_scope`
- **Rationale:** Communications security is operator-owned at transport layer.
- **Operator boundary:** Operator owns network segmentation and transport encryption.
- **Evidence refs:**
  - (no repo evidence ref; operator-owned)

### `A.14` — System acquisition, development, and maintenance

- **Status:** `partial`
- **Rationale:** Cross-AI peer review HARD RULE plus CI gate plus ADR-as-record plus invariant tests document a system development surface.
- **Operator boundary:** Operator owns production maintenance cadence and post-deploy verification.
- **Evidence refs:**
  - **HARD_RULE** `Cross-AI Peer Review (2026-05-05)` — Implementer != reviewer provider discipline (_governance rule_)

### `A.15` — Supplier relationships

- **Status:** `partial`
- **Rationale:** LLM provider vendor list is implicit in adapter registry; supplier contracts are operator-owned.
- **Operator boundary:** Operator owns vendor contract, SLA review, and supplier risk assessment.
- **Evidence refs:**
  - **SOURCE** `ao_kernel/defaults/` — Adapter registry (provider list) (_repo source artifact_)

### `A.16` — Information security incident management

- **Status:** `partial`
- **Rationale:** E-6-6 incident response playbook documents incident management surface; real incident org, notification, tabletop exercise, postmortem cadence are operator-owned.
- **Operator boundary:** Operator owns incident on-call rotation, customer notification, tabletop exercise schedule, and postmortem distribution cadence.
- **Evidence refs:**
  - **PR** `PR #801` — E-6-6 incident response playbook documentation (_merge audit trail_)

### `A.17` — Information security aspects of business continuity

- **Status:** `out_of_scope`
- **Rationale:** Business continuity is operator-owned.
- **Operator boundary:** Operator owns BCP, DR plan, and RTO/RPO target setting.
- **Evidence refs:**
  - (no repo evidence ref; operator-owned)

### `A.18` — Compliance

- **Status:** `partial`
- **Rationale:** This control-reference mapping documents a compliance documentation surface; certification, audit engagement, and regulatory determination are operator-owned.
- **Operator boundary:** Operator owns auditor engagement, certification scope, and regulatory determination.
- **Evidence refs:**
  - **DOC** `docs/compliance/README.md` — Compliance posture documentation index (_documentation only_)

## References

- Source catalog: [`control-evidence-catalog.v1.json`](control-evidence-catalog.v1.json)
- Schema: [`../../ao_kernel/defaults/schemas/control-evidence-catalog.schema.v1.json`](../../ao_kernel/defaults/schemas/control-evidence-catalog.schema.v1.json)
- Compliance overview: [`README.md`](README.md)
- Codex cross-AI plan-time AGREE: thread `019e83d1` (2 iters: REVISE → AGREE)
