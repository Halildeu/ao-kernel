# SOC2 Trust Service Categories — Control-Reference Mapping (V5 Epic 6 E-6-3)

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

**Framework version:** `SOC2-2017`

This document maps ao-kernel repo artifacts to SOC2 Trust Service Categories (Common Criteria CC1-CC9 plus the four TSC categories: Availability, Confidentiality, Processing Integrity, Privacy). It is a control-reference mapping, not an audit attestation.

## Control-Reference Mapping

| Control | Name | Status | Operator Boundary |
|---|---|---|---|
| `CC1` | Control Environment | `documented` | Organization-level control environment effectiveness is operator-owned |
| `CC2` | Communication and Information | `partial` | Operator owns end-user communication, training program, and external informat... |
| `CC3` | Risk Assessment | `partial` | Enterprise risk assessment program operator-owned |
| `CC4` | Monitoring Activities | `partial` | Ongoing management monitoring and review cadence is operator-owned |
| `CC5` | Control Activities | `partial` | Operational control effectiveness is operator-owned audit subject |
| `CC6` | Logical and Physical Access | `partial` | Operator owns authn/SSO/MFA, key management, and physical access controls |
| `CC7` | System Operations | `partial` | Live deployment, scrape target provisioning, and alert delivery operator-owned |
| `CC8` | Change Management | `partial` | Operator owns production deployment change-control board and post-deploy veri... |
| `CC9` | Risk Mitigation | `partial` | Operator owns vendor risk program and supply-chain incident response |
| `A` | Availability (Trust Service Category) | `partial` | No uptime SLI in v1 (uptime_status |
| `C` | Confidentiality (Trust Service Category) | `partial` | Operator owns data classification, key management, and storage encryption |
| `PI` | Processing Integrity (Trust Service Category) | `partial` | Operator owns business-process integrity outside repo runtime |
| `P` | Privacy (Trust Service Category) | `out_of_scope` | Operator privacy program owns DPIA, ROPA, and data subject rights workflow |

## Per-Control Details

### `CC1` — Control Environment

- **Status:** `documented`
- **Rationale:** Repo ships governance ADRs and HARD RULE policies that describe a control environment posture.
- **Operator boundary:** Organization-level control environment effectiveness is operator-owned.
- **Evidence refs:**
  - **DOC** `CLAUDE.md` — Project-level control environment policy reference (_documentation only_)
  - **HARD_RULE** `Pre-Production Full Authority (2026-04-29)` — Governance posture HARD RULE (_governance rule_)

### `CC2` — Communication and Information

- **Status:** `partial`
- **Rationale:** ADRs, runbooks, and migration guides document internal communication posture; org training/comms is operator-owned.
- **Operator boundary:** Operator owns end-user communication, training program, and external information channel.
- **Evidence refs:**
  - **DOC** `docs/MIGRATION-V5.md` — Migration documentation surface (_documentation only_)

### `CC3` — Risk Assessment

- **Status:** `partial`
- **Rationale:** Plan-time cross-AI peer review process and risk matrices in ADRs document a risk assessment surface.
- **Operator boundary:** Enterprise risk assessment program operator-owned.
- **Evidence refs:**
  - **HARD_RULE** `Cross-AI Peer Review (2026-05-05)` — Risk assessment via cross-provider review (_governance rule_)

### `CC4` — Monitoring Activities

- **Status:** `partial`
- **Rationale:** CI gate, ao-release-gate, SLI/SLO catalog, and Alertmanager rule templates document a monitoring surface.
- **Operator boundary:** Ongoing management monitoring and review cadence is operator-owned.
- **Evidence refs:**
  - **DOC** `docs/sli-catalog.v1.json` — SLI/SLO catalog (E-5-4) (_documentation only_)
  - **PR** `PR #799` — E-5-4 SLI/SLO catalog merged (_merge audit trail_)
  - **PR** `PR #800` — E-5-5 Alertmanager rule templates (_merge audit trail_)

### `CC5` — Control Activities

- **Status:** `partial`
- **Rationale:** ao-release-gate decision pipeline and invariant test suites document a repo-level control activity surface.
- **Operator boundary:** Operational control effectiveness is operator-owned audit subject.
- **Evidence refs:**
  - **SOURCE** `ao_kernel/ao_release_gate.py` — Release-gate decision pipeline source (_repo source artifact_)
  - **PR** `PR #793` — RG-019e830d evidence finding taxonomy (_merge audit trail_)

### `CC6` — Logical and Physical Access

- **Status:** `partial`
- **Rationale:** Repo enforces secret-scan and no-secret-in-PR-body conventions; SSO, MFA, authn, and physical access are operator-owned.
- **Operator boundary:** Operator owns authn/SSO/MFA, key management, and physical access controls.
- **Evidence refs:**
  - **HARD_RULE** `No Fake Work / No Cosmetic Operations (2026-04-25)` — Secret discipline governance (_governance rule_)

### `CC7` — System Operations

- **Status:** `partial`
- **Rationale:** OTEL tracing tunables (E-5-1), W3C trace context (E-5-3a), Alertmanager templates (E-5-5), and incident playbook (E-6-6) document a system operations surface.
- **Operator boundary:** Live deployment, scrape target provisioning, and alert delivery operator-owned.
- **Evidence refs:**
  - **PR** `PR #791` — E-5-1 OTEL prod tunables (_merge audit trail_)
  - **PR** `PR #797` — E-5-3a W3C tracing primitives (_merge audit trail_)
  - **PR** `PR #801` — E-6-6 incident response playbook (_merge audit trail_)

### `CC8` — Change Management

- **Status:** `partial`
- **Rationale:** Cross-AI peer review HARD RULE plus CI gate plus ao-release-gate plus ADR-as-record document a strong change-management surface.
- **Operator boundary:** Operator owns production deployment change-control board and post-deploy verification.
- **Evidence refs:**
  - **HARD_RULE** `Cross-AI Peer Review (2026-05-05)` — Implementer != reviewer provider discipline (_governance rule_)
  - **HARD_RULE** `Admin Merge YASAK (2026-05-05)` — Governance bypass prohibition (_governance rule_)
  - **HARD_RULE** `CI Kirmiziyken Merge YASAK (2026-05-17)` — Required-check enforcement (_governance rule_)

### `CC9` — Risk Mitigation

- **Status:** `partial`
- **Rationale:** SBOM generator (E-6-1a), CodeQL workflow (E-6-5), Trivy fs scanner (E-6-2), and ao-release-gate document a vulnerability-mitigation surface.
- **Operator boundary:** Operator owns vendor risk program and supply-chain incident response.
- **Evidence refs:**
  - **PR** `PR #795` — E-6-1a SBOM generator (_merge audit trail_)
  - **PR** `PR #796` — E-6-5 CodeQL workflow (_merge audit trail_)
  - **PR** `PR #798` — E-6-2 Dependabot + Trivy (_merge audit trail_)

### `A` — Availability (Trust Service Category)

- **Status:** `partial`
- **Rationale:** SLI/SLO catalog (E-5-4) and Alertmanager templates (E-5-5) document an availability monitoring surface; uptime SLI is explicitly out of scope in v1.
- **Operator boundary:** No uptime SLI in v1 (uptime_status.in_scope=false). No live operator deployment evidence. No BCP ownership.
- **Evidence refs:**
  - **DOC** `docs/sli-catalog.v1.json` — uptime_status.in_scope=false; availability gap documented (_documentation only_)

### `C` — Confidentiality (Trust Service Category)

- **Status:** `partial`
- **Rationale:** Repo enforces secret-scan and no-secret-in-PR-body discipline; data classification and operator storage are out of scope.
- **Operator boundary:** Operator owns data classification, key management, and storage encryption.
- **Evidence refs:**
  - **HARD_RULE** `No Fake Work / No Cosmetic Operations (2026-04-25)` — Secret discipline governance (_governance rule_)

### `PI` — Processing Integrity (Trust Service Category)

- **Status:** `partial`
- **Rationale:** Schema validation (jsonschema Draft 2020-12 across all artifact types) and evidence trail (JSONL append-only) document a processing-integrity surface.
- **Operator boundary:** Operator owns business-process integrity outside repo runtime.
- **Evidence refs:**
  - **SOURCE** `ao_kernel/_internal/evidence/` — JSONL evidence writer with SHA256 integrity manifest (_repo source artifact_)

### `P` — Privacy (Trust Service Category)

- **Status:** `out_of_scope`
- **Rationale:** ao-kernel runtime does not process repo-owned PII; operator privacy program owns DPIA, records of processing, and data subject rights.
- **Operator boundary:** Operator privacy program owns DPIA, ROPA, and data subject rights workflow.
- **Evidence refs:**
  - **HARD_RULE** `Kullanici Aktif Credential'ina Dokunma YASAK (2026-04-29)` — User credential / personal data discipline (_governance rule_)

## References

- Source catalog: [`control-evidence-catalog.v1.json`](control-evidence-catalog.v1.json)
- Schema: [`../../ao_kernel/defaults/schemas/control-evidence-catalog.schema.v1.json`](../../ao_kernel/defaults/schemas/control-evidence-catalog.schema.v1.json)
- Compliance overview: [`README.md`](README.md)
- Codex cross-AI plan-time AGREE: thread `019e83d1` (2 iters: REVISE → AGREE)
