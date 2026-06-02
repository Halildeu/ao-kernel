# ao-kernel License Compliance Policy + Dependency Inventory (V5 Epic 6 E-6-4)

> **Not legal counsel.** **Not legal advice.** **Operator responsibility.**
> This package provides a schema-backed SPDX license-tier policy and a
> deterministic per-component dependency inventory generated from a
> CycloneDX 1.5 SBOM. It is **not** a legal compliance determination,
> **not** an audit attestation, and **not** a certification statement.
> The three guard flags (`support_widening`, `production_platform_claim`,
> `live_adapter_execution`) remain `const false`.
>
> **Operator owns** license obligation interpretation, vendor license
> review, source-distribution compliance, NOTICE/attribution generation,
> and any remediation decisions. ao-kernel ships the policy framework
> and machine-readable report only.

## 1. Source of Truth

| File | Role |
|---|---|
| [`license-compliance-policy.v1.json`](license-compliance-policy.v1.json) | Canonical policy (manually authored SSOT) |
| [`../../ao_kernel/defaults/schemas/license-compliance-policy.schema.v1.json`](../../ao_kernel/defaults/schemas/license-compliance-policy.schema.v1.json) | Policy JSON Schema (Draft 2020-12) |
| [`dependency-license-inventory.v1.json`](dependency-license-inventory.v1.json) | Generated inventory (SBOM + policy → report) |
| [`../../ao_kernel/defaults/schemas/dependency-license-inventory.schema.v1.json`](../../ao_kernel/defaults/schemas/dependency-license-inventory.schema.v1.json) | Inventory JSON Schema (Draft 2020-12) |
| [`dependency-license-inventory.v1.md`](dependency-license-inventory.v1.md) | Markdown summary (generated) |
| [`../../scripts/generate_license_inventory.py`](../../scripts/generate_license_inventory.py) | Deterministic generator |

### Authority Boundary — Distinct from Runtime Policy

This package is **distinct from** the runtime
[`ao_kernel/defaults/policies/policy_license.v1.json`](../../ao_kernel/defaults/policies/policy_license.v1.json)
capability policy. The compliance policy here applies to **third-party
dependency SPDX identifiers** discovered via SBOM; the runtime policy
applies to **ao-kernel's own license-check capability** at request time.

## 2. SPDX Tier Classification

The policy declares three tiers (mutually exclusive per
`test_tiers_mutually_exclusive`):

| Tier | Semantics | Example SPDX identifiers |
|---|---|---|
| `allow` | Permissive license; policy check passes | `MIT`, `BSD-2-Clause`, `BSD-3-Clause`, `Apache-2.0`, `ISC`, `0BSD`, `Zlib`, `Unlicense` |
| `review` | Requires operator review (legal counsel decision) | `LGPL-2.1-only/or-later`, `LGPL-3.0-only/or-later`, `MPL-2.0`, `EPL-1.0/2.0`, `CDDL-1.0`, `PSF-2.0` |
| `deny` | Strong copyleft; default-block | `GPL-2.0-only/or-later`, `GPL-3.0-only/or-later`, `AGPL-3.0-only/or-later`, `SSPL-1.0` |

## 3. SPDX Expression Handling (v1 simple-identifier-only)

Per Codex 019e83df F1 absorb, v1 supports **simple SPDX identifier match
only**. The following cases all fall to **`review_required`** — no false
"pass" claim is permitted:

| Case | Review reason |
|---|---|
| `license.id` present, in policy `review` tier | `policy_review_tier` |
| `license.expression` (e.g. `MIT OR Apache-2.0`) | `unsupported_expression` |
| SPDX expression with `WITH` exception (e.g. `Apache-2.0 WITH LLVM-exception`) | `unsupported_exception` |
| `license.id` starts with `LicenseRef-` | `license_ref` |
| `license.id` is `NOASSERTION` | `noassertion` |
| `license.id` is `NONE` | `none_declared` |
| `license.name` only (no `id`) | `unresolved_name` |
| `license.url` only (no `id` or `name`) | `unresolved_url` |
| `licenses` field missing from component | `missing_license` |
| `license.id` not present in any policy tier | `unknown_identifier` |
| Multiple `license` entries per component | `unsupported_expression` |

This conservative policy ensures **no SPDX expression false negative**
slips through as `pass`.

## 4. Unknown License Handling

`unknown_handling: "review"` — unknown SPDX identifiers fall to
`review_required` (fail-closed review, not fail-closed deny). This
preserves V5 discipline:

- `allow` would be an unsafe overclaim
- `deny` would be a legal overclaim (some unknowns may be legitimate)
- `review` requires explicit operator decision

For hard CI/release gating, the operator can invoke the generator with
`--fail-on-review` to convert `review_required` into a non-zero exit.

## 5. Report Status Enum

Each generated inventory declares one of four `report_status` values:

| Status | Meaning | CLI exit |
|---|---|---|
| `pass_no_deny_matches` | Zero deny matches, zero reviews | 0 |
| `review_required` | One or more components require review (no deny matches) | 0 (or 1 with `--fail-on-review`) |
| `blocked_by_deny_license` | One or more components match the deny tier | 1 |
| `invalid_input` | SBOM bom_format is not CycloneDX | 1 |

## 6. ao-kernel Own License

ao-kernel itself is licensed under **MIT** (see [`../../LICENSE`](../../LICENSE)).
The policy `ao_kernel_license` field pins this for cross-validation against
the LICENSE file.

## 7. Wording Discipline

Per Codex 019e83df H4 absorb, the following claim language is forbidden in
this package:

- `legally compliant`
- `license-safe`
- `legal approved`
- `fully compliant`
- `compliant with [X]`
- `satisfies [X] obligations`
- `we comply with`

Allowed wording (machine-result, not legal claim):

- `policy check passed` (only when `pass_no_deny_matches`)
- `review required` (when `review_required`)
- `policy result`
- `policy tier`
- `dependency license inventory`
- `report status`
- `deny-tier match`

## 8. Generator Determinism

Per Codex 019e83df F5 absorb:

- **No wall-clock timestamps** (`generated_at`, `timestamp`, `created_at` all
  prohibited)
- Components sorted stably by `(name, version, purl, bom_ref)`
- Canonical JSON: `json.dumps(sort_keys=True, indent=2) + "\n"`
- Source provenance: `source_sbom_sha256` + `source_policy_sha256` recorded
- Generator metadata: `generator_name` + `generator_version` const-pinned

Byte-equal drift test (`test_inventory_drift_byte_equal`) asserts that the
committed inventory matches a freshly generated inventory exactly.

## 9. Out of Scope (E-6-4 follow-up slices)

| ID | Slice |
|---|---|
| E-6-4b | Full SPDX expression interpreter (parser for `A OR B`, `A AND B`, `A WITH X`) |
| E-6-4c | NOTICE / attribution file generation (license obligation tracking) |
| E-6-4d | SPDX exception handling (e.g. `LLVM-exception`, `Classpath-exception-2.0`) |
| E-6-4e | Source code distribution compliance (operator) |
| E-6-4f | License remediation runbook (manual replacement decisions) |
| E-6-4g | Vendor license review workflow (operator-context) |
| E-6-4h | SPDX catalog snapshot/version pinning automation |
| E-6-4i | CI/release gate wiring for `--fail-on-review` |
| E-6-4j | Legacy `policy_license.v1.json` runtime migration (if needed) |
| E-6-4k | License text packaging for distribution |

## 10. References

- V5 roadmap: [`../../.claude/plans/V5-FULL-PRODUCTION-PROMOTION-ROADMAP.md`](../../.claude/plans/V5-FULL-PRODUCTION-PROMOTION-ROADMAP.md)
- E-6-1a SBOM generator: PR #795 MERGED
- E-6-3 SOC2/ISO compliance: PR #802 (pipeline)
- E-6-6 incident response: PR #801 (pipeline)
- HARD RULE Cross-AI Peer Review (2026-05-05, 2026-05-14)
- SPDX License List: https://spdx.org/licenses/ (v3.24 pinned in policy)
- CycloneDX 1.5 specification: https://cyclonedx.org/specification/overview/
- Codex thread `019e83df` (2-iter REVISE → AGREE)
