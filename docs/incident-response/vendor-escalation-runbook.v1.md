# Vendor Escalation Runbook (V5 Epic 6 E-6-6b)

> **Operator-owned external handoff.** **No vendor SLA promise.** **No
> customer notification authority.** This runbook walks the operator
> through vendor outage escalation for the 8 documented vendors. The
> agent prepared this contract; the operator opens tickets, logs case
> IDs, and updates the incident timeline. ao-kernel does NOT communicate
> with end-user customers about vendor outages; that decision is an
> operator + legal-counsel determination.
>
> Three guard flags (`support_widening`, `production_platform_claim`,
> `live_adapter_execution`) remain `const false`.

## 1. Source of Truth

| File | Role |
|---|---|
| [`vendor-escalation-matrix.v1.json`](vendor-escalation-matrix.v1.json) | Canonical 8-vendor matrix |
| [`../../ao_kernel/defaults/schemas/vendor-escalation-matrix.schema.v1.json`](../../ao_kernel/defaults/schemas/vendor-escalation-matrix.schema.v1.json) | Schema (Draft 2020-12) |
| [`severity-matrix.v1.json`](severity-matrix.v1.json) | E-6-6 SEV-1/2/3 cross-reference |
| [`incident-template.v1.md`](incident-template.v1.md) | Post-mortem timeline target |

## 2. Vendor Categories

| Category | Vendors |
|---|---|
| `llm_provider` | Anthropic (Claude), OpenAI, Google Gemini, xAI (Grok), DeepSeek, Qwen (Alibaba) |
| `container_registry` | GHCR |
| `package_index` | PyPI |

Other categories enumerated in the schema (`embedding_provider`,
`telemetry_backend`) are placeholders for future slices and currently
have no committed entries.

## 3. Standard Workflow

Every vendor row exposes 3–5 standardized steps. The operator runs them
in order:

1. **Verify** the outage via the vendor's status page (mandatory first
   step).
2. **Capture** the relevant request ID, endpoint, region, or other
   reproducible artifact.
3. **Open** a support ticket via the vendor's portal (URL in the
   matrix).
4. **Log** the case ID in the incident timeline
   (`incident-template.v1.md` post-mortem template).
5. **Escalate** to the account manager only if the SEV-1 ticket is
   unacknowledged after 15 minutes — and only if the account manager
   contact is operator-provisioned outside this repo.

## 4. Severity Mapping

The `applicable_severity` field on each vendor cross-validates with the
E-6-6 severity matrix tier IDs (`SEV-1`, `SEV-2`, `SEV-3`). Per Codex
019e84c6 absorb, every vendor row's `applicable_severity` MUST be a
subset of `{SEV-1, SEV-2, SEV-3}` — enforced by the schema enum and the
invariant test.

| Severity | Typical vendor incidents |
|---|---|
| SEV-1 | `api_outage`, `account_lockout` blocking production traffic |
| SEV-2 | `model_degradation`, `rate_limit_spike` partially degrading SLO |
| SEV-3 | `billing_dispute`, observability-only signals |

Currently no vendor entry maps to `SEV-3` — the matrix is conservative
(only `SEV-1` + `SEV-2`). SEV-3 cases are operator-observable internal
signals that do NOT require vendor handoff.

## 5. PII Boundary

- `account_manager_contact` is **always** the constant
  `"operator_provisioned"`. Real account manager email, phone, or
  Slack handle is NEVER committed.
- The operator stores actual contact details outside this repo (Vault,
  password manager, operator-private wiki).
- Per HARD RULE Kullanıcı Aktif Credential'ına Dokunma YASAK (2026-04-29),
  no real human identifier ships in this matrix.

## 6. Stop and contact owner if

- A vendor row's status page returns 404 (URL drift; matrix MUST be
  updated in a new PR before reliance)
- The vendor changes the support portal URL (matrix update required)
- An incident requires a customer notification — escalate to legal
  counsel + operator owner before any external communication
- A new vendor needs to be added — extend the matrix with a follow-up
  PR; do NOT improvise during incident response
- The vendor SLA terms are referenced in any external claim — STOP; this
  matrix does NOT promise vendor SLA

## 7. References

- E-6-6 incident response playbook: `README.md` §6.6 "Vendor Escalation
  Boundary"
- E-6-6 severity matrix: `severity-matrix.v1.json`
- Operator runbooks: `../operator-runbooks/README.md`
- HARD RULE Tam Otonom Önerme (2026-05-28)
- HARD RULE Kullanıcı Aktif Credential'ına Dokunma YASAK (2026-04-29)
- HARD RULE Cross-AI Peer Review (2026-05-05, 2026-05-14)
- Codex thread (E-6-6 incident plan-time): `019e83c3`
- Codex thread (E-6-6b vendor escalation post-impl): pending
