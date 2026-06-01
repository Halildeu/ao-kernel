# ao-kernel GDPR DPIA Operator Runbook (V5 Epic 6 E-6-3c)

> **Documentation only.** **Not legal advice.** This runbook describes
> how an operator deploying ao-kernel can fill in the schema-backed
> DPIA template. It does NOT determine lawful basis, controller/processor
> role, transfer mechanism, DPA filing need, or data subject notice
> content. Article 36 prior consultation determination remains operator
> and DPO/counsel responsibility.

## 1. Scope

This runbook accompanies:

- [`gdpr-dpia-template.v1.json`](gdpr-dpia-template.v1.json) — canonical SSOT
- [`gdpr-dpia-template.v1.md`](gdpr-dpia-template.v1.md) — generated render
- `../../ao_kernel/defaults/schemas/gdpr-dpia-template.schema.v1.json` — schema

The repo baseline ships with all personal-data fields set to
`<no-personal-data-in-repo-baseline>` and all Section C risks
`risk_status: "not_applicable"`. ao-kernel does NOT process personal
data; operator deployment determines whether DPIA is required and what
the actual content should be.

## 2. When is a DPIA Required?

Article 35(3) GDPR enumerates baseline triggers. Operator MUST
independently assess all of:

- (a) Systematic and extensive profiling with legal/significant effects
- (b) Large-scale processing of special categories of data (Article 9)
  or criminal conviction data (Article 10)
- (c) Systematic monitoring of publicly accessible areas on a large scale

Article 35(4) requires operators to also check the published list of
processing operations subject to mandatory DPIA from the relevant
supervisory authority.

**Repo baseline:** `repo_baseline_triggered = false` (the repo itself
does not perform any of these operations).

**Operator baseline assessment:** required regardless of repo baseline
(`operator_must_assess_art35_3 = true`,
`operator_must_check_supervisory_authority_lists = true`).

## 3. How to Fill the Template

### 3.1 Section 0 — Metadata + Trigger Assessment

Replace each placeholder with operator-provided value. Do NOT commit
real personal data, real DPO names, or real supervisory authority
correspondence into a public repository.

| Placeholder | Replace With |
|---|---|
| `<operator-controller-name>` | Legal entity name of the data controller |
| `<operator-dpo-contact>` | DPO contact reference (role + contact channel, no PII) |
| `<operator-supervisory-authority>` | Identifier of the competent supervisory authority |

Trigger assessment booleans should be updated **only after** operator
counsel/DPO review. Do not flip `repo_baseline_triggered` to `true`
in this repo; that flag describes the repo, not operator deployment.

### 3.2 Section A — Systematic Description

Each field should describe operator's actual processing once known.
Until then, leave as `<no-personal-data-in-repo-baseline>` or
`<operator-to-describe-...>`. Required Article 35(7) coverage:

- Processing operations + purposes
- Categories of data subjects + personal data
- Recipients + transfers + retention
- Systems + processors/subprocessors
- Data flow summary

### 3.3 Section B — Necessity and Proportionality

Document why the processing is necessary, why it is proportionate to
the purpose, and how data minimization is enforced. Lawful basis
consideration is operator + counsel territory; this template does NOT
determine lawful basis.

### 3.4 Section C — Risks

The repo baseline lists 6 risk categories all `risk_status:
"not_applicable"`. Operator should change `risk_status` to
`identified`, `mitigated`, or
`residual_high_risk_requires_art36_review` and provide non-null
`likelihood`, `severity`, `risk_score`, and `mitigation` for each
applicable risk.

Schema enforces this conditional: applicable risks REQUIRE all four
fields; `not_applicable` risks REQUIRE all four to be null.

### 3.5 Section D — Mitigation Measures

Operator-owned technical and organizational measures (TOMs).
ao-kernel ships no transport encryption, key management, or access
control surface; those measures are entirely operator-owned.

### 3.6 Section E — Consultation Evidence

Three consultation status fields, each with enum:

- `not_applicable_repo_baseline` (default)
- `operator_to_determine` (during operator DPIA workflow)
- `completed_operator_reference` (operator may attach reference
  identifier, NOT consultation content)
- `not_required_operator_assessment` (after operator + DPO review)

GDPR Article 35(2) DPO advice is sought "where designated"; Article
35(9) data subject views are sought "where appropriate"; Article 36
prior consultation with the supervisory authority is required when
residual high risk remains after mitigation.

### 3.7 Section F — Decision and Approval

Operator decision record, decision date, approver role, and review
cadence. This is operator's decision record, not repo approval.

## 4. Public Claim Discipline

Do NOT publish or distribute claims using any of the 22+ prohibited
tokens enumerated in
[`gdpr-dpia-template.v1.json`](gdpr-dpia-template.v1.json) under
`prohibited_claims`. The scanner enforces this on Markdown prose.
Operator's own DPIA publication channels are outside this repo and
outside this scanner.

## 5. Cross-AI Peer Review Trail

Per HARD RULE Cross-AI Peer Review (2026-05-05, 2026-05-14):

- Implementer Anthropic Claude → Reviewer OpenAI Codex.
- Plan-time consensus required for any change to the GDPR DPIA schema
  or rendered Markdown.
- Codex iter chain audit trail in
  [`../../.claude/plans/EPIC-6-E6-3C-GDPR-DPIA-TEMPLATE.md`](../../.claude/plans/EPIC-6-E6-3C-GDPR-DPIA-TEMPLATE.md).

## 6. Out-of-scope follow-up slices

| ID | Slice |
|---|---|
| E-6-3c-2 | ROPA (Records of Processing Activities) template |
| E-6-3c-3 | DPA counsel checklist (NOT contract template) |
| E-6-3c-4 | Data subject rights workflow (operator) |
| E-6-3c-5 | Breach notification GDPR Article 33-34 runbook |
| (E-6-3c-6 reserved) | Transfer Impact Assessment (international transfers) |

## 7. References

- Source catalog: [`gdpr-dpia-template.v1.json`](gdpr-dpia-template.v1.json)
- Generated render: [`gdpr-dpia-template.v1.md`](gdpr-dpia-template.v1.md)
- Schema: [`../../ao_kernel/defaults/schemas/gdpr-dpia-template.schema.v1.json`](../../ao_kernel/defaults/schemas/gdpr-dpia-template.schema.v1.json)
- E-6-3 SOC2/ISO compliance overview: [`README.md`](README.md)
- E-6-3b HIPAA mapping reference: PR #809
- HARD RULE Cross-AI Peer Review (2026-05-05, 2026-05-14)
- HARD RULE Uzun Vadeli Kalıcı Çözüm (2026-05-27)
- Codex thread `019e84fb` (2-iter REVISE -> AGREE)
- EDPB Guidelines on DPIA: https://edpb.europa.eu/
