# AO-MA-10h Multi-Work-Package Governance Migration (2026-06-02)

## Problem (sistemik bug)

`ao_kernel/defaults/schemas/ao-ma-10-high-risk-supersession-evidence.schema.v1.json`
pinned `work_package` to `const "AO-MA-10h"`.

The trusted-base workflow (`.github/workflows/test.yml::reviewed_wp`)
dynamically derives `REVIEW_WORK_PACKAGE` from the per-PR root
`local-ai-review-evidence.v1.json::work_package`, and the script
`scripts/ao_ma10_high_risk_supersession_evidence.py` already accepts this
identifier via `--review-work-package`. But the script then hardcoded
`"work_package": "AO-MA-10h"` in the emitted artifact, and the schema's
const blocked any other identifier from validating.

Result: **21 open PRs** (#824–#899) failed `ao-release-gate-review` with
`deny_missing_evidence` because they could not produce a conforming
high-risk supersession evidence artifact bound to their own work_package.
This blocks the autonomous review chain governance gate fundamentally:
high-risk PRs must either (a) get a current-head non-author human review,
or (b) supply schema-valid supersession evidence — and only (a) was
reachable.

This is a HARD RULE — Governance/Sistemik Bug case (2026-05-05): fix the
underlying schema/code drift before the next high-risk PR rebases, instead
of admin-bypassing each blocked PR individually.

## Two design options weighed (plan-time Codex thread `019e88c9`)

### Option A — Multi-file active index (heavyweight)

- New file `ao_kernel/defaults/ao-ma-10-high-risk-supersession-active.v1.json`
  with an explicit per-WP opt-in list.
- Schema v2 with `work_package` pattern + cross-reference check against the
  active index.
- Requires operator preapproval for every new work_package.

### Option B — Lenient schema with canonical pattern (chosen)

- Schema v1 patched in place: `work_package` becomes `string` +
  `pattern: "^[A-Z][A-Z0-9]*(?:-[A-Za-z0-9][A-Za-z0-9._]*)*$"` +
  `minLength: 3` + `maxLength: 80`.
- Script: `"work_package": review_work_package` (dynamic, from the
  `--review-work-package` CLI argument supplied by the workflow).
- Backward compat: `"AO-MA-10h"` still matches the pattern; legacy
  evidence/tests continue to validate.

## Why Option B (Codex verdict + adversarial reasoning)

Codex AGREE (`019e88c9-27ec-7b53-af2d-b91b46128e0e`):

> "Option B doğru tasarım. `work_package` burada release authority veya
> permission boundary değil; PR'e bağlanan review/evidence kimliği. Mevcut
> authority zinciri `ao-release-gate+github-ruleset`, context binding, path
> allowlist, provider distinctness, unanimous AGREE, freshness ve guard
> flag const `false` kontrolleriyle kapanıyor. Bu yüzden `AO-MA-10h`
> const'u güvenlik sağlamıyor; sadece dinamik work package kullanan PR'lerde
> conforming artifact üretimini kırıyor."

The post-migration authority chain remains the same fail-closed surface:

| Authority surface | Enforcement | Migration impact |
| --- | --- | --- |
| `release_authority` const | `ao-release-gate+github-ruleset` | unchanged |
| `ai_output_release_authority` const | `false` | unchanged |
| `guard_flags.support_widening` const | `false` | unchanged |
| `guard_flags.production_platform_claim` const | `false` | unchanged |
| `guard_flags.live_adapter_execution` const | `false` | unchanged |
| `secrets_recorded` const | `false` | unchanged |
| `mutations_performed` const | `false` | unchanged |
| `consensus_status` const | `AGREE` | unchanged |
| Required reviewer providers | `[openai, anthropic]` (distinct, pair-required) | unchanged |
| Context binding | head_sha, diff_digest, changed_files, refs, repo, high_risk_changed_paths | unchanged |
| Freshness | `max_age_seconds` window, `status=fresh` | unchanged |
| Path allowlist | Per-PR `allowed_path_prefixes` | unchanged |
| State-at-landing binding mode | `added` / `modified` strict, `unchanged` immutable | unchanged |
| Raw reviewer evidence pair-presence | Both files required on PR head | unchanged |
| `work_package` field | `const "AO-MA-10h"` → `pattern` matching workflow regex | **only field widened** |

Substitution attack analysis: a malicious PR proposing
`work_package: "EVIL-WP"` cannot bypass any defense — the workflow binds
the supersession artifact to the live PR's head_sha + diff_digest +
changed_files + refs + repo + high_risk_changed_paths; the schema enforces
guard-flag closure; cross-provider distinct AGREE is mandatory; the path
allowlist scopes mutations; freshness pins recency.

Rebinding stale evidence is blocked: the runtime builder validates per-PR
context binding with three modes (`added`, `modified`, `unchanged`) and the
immutable property checks in
`scripts/ao_ma10_high_risk_supersession_evidence.py::_provider_verdict_from_raw_review`
enforce reviewer independence, secret closure, guard flags, tests +
secret_scan check pass, and no forbidden findings — perpetually.

Option A's explicit allowlist would add a new ledger that the migration's
problem statement does not require: per-PR authority is already enforced
without needing an "approved-WP" preapproval list. Adding one means new
rebase coordination, new drift source, new governance ceremony — for zero
new defensive value in the current authority model.

## Scope of changes (this PR)

| File | Change | Notes |
| --- | --- | --- |
| `ao_kernel/defaults/schemas/ao-ma-10-high-risk-supersession-evidence.schema.v1.json` | `work_package` const → pattern + min/max length | Matches workflow regex |
| `scripts/ao_ma10_high_risk_supersession_evidence.py` | `"work_package": "AO-MA-10h"` → `"work_package": review_work_package` (dynamic from CLI arg) | Defense-in-depth: `_validate_work_package()` pre-check |
| `tests/test_ao_release_gate.py` | `_high_risk_supersession_evidence` helper gains `work_package` kwarg (default `"AO-MA-10h"` for back-compat) | No fixture deprecation |
| `tests/test_ao_ma10h_multi_work_package_schema.py` | NEW — 36 invariants pinning migration | See below |
| `.claude/plans/AO-MA-10h-MULTI-WORK-PACKAGE-MIGRATION.md` | NEW — this plan doc | |
| `.claude/plans/AO-MA-10h-MULTI-WORK-PACKAGE-MIGRATION.v1.json` | NEW — evidence artifact | |
| `ao-ma-10-high-risk-reviews/AO-MA-10h-multi-work-package-migration/{openai,anthropic,minimax}.local-ai-review-evidence.v1.json` | NEW — cross-AI 3-way review evidence | |

## New invariants (`tests/test_ao_ma10h_multi_work_package_schema.py`)

36 tests organized as:

1. Schema shape: `work_package` no longer `const "AO-MA-10h"`; pattern +
   length bounds pinned; matches workflow regex verbatim.
2. Accepted identifiers: 10 canonical real-world ao-kernel WPs validate.
3. Rejected identifiers: 12 malformed shapes rejected by both schema and
   pre-check.
4. Pre-check ↔ schema parity: `WORK_PACKAGE_PATTERN.pattern` ≡ schema
   pattern.
5. Authority surface unchanged: all 9 const/required boundaries still
   pinned (repo, planning_only, release_authority, ai_output_release_authority,
   consensus_status, max_revise_rounds, escalation_action, secrets_recorded,
   mutations_performed, plus 3 guard flags + provider distinctness pair).
6. Builder dynamic emission: 4 work_packages round-trip; source-guard
   prevents reintroducing hardcoded `"AO-MA-10h"`.
7. Required-field preservation: `work_package` still in `required[]`.

## Operator follow-up (separate dispatch)

After this PR merges, the 21 currently-blocked open PRs need supersession
evidence regenerated. Two options:

- **Automatic (recommended)**: Trigger a workflow dispatch that loops the
  21 PR numbers and reruns CI; the trusted-base workflow will now generate
  conforming evidence for each PR's own `work_package`.
- **Per-PR commit (fallback)**: Each PR can commit
  `ao-ma-10-high-risk-reviews/{openai,anthropic}.local-ai-review-evidence.v1.json`
  with the correct `work_package` and re-trigger CI.

Either path requires the OpenAI + Anthropic raw reviewer evidence files on
the PR's head (already in place for many PRs; missing ones are flagged by
the workflow's pair-presence step which is already fail-closed).

## Hard-rule compliance

- HARD RULE Governance/Sistemik Bug (2026-05-05): sistemik fix önce (this
  PR); 21 rebases follow naturally.
- HARD RULE Cross-AI Peer Review (2026-05-05/2026-05-14): provider-level
  3-way (Codex + Anthropic + Mavis fallback) for high-risk schema +
  ao_release_gate-adjacent change. Evidence files committed.
- HARD RULE Admin Merge YASAK (2026-05-05): no `--admin` flag; CI must be
  fully green before squash merge.
- HARD RULE Uzun Vadeli Kalıcı Çözüm (2026-05-27): pattern-based
  enforcement is monotonic (future WPs auto-conform); machine-enforced;
  passes adversarial review.
- HARD RULE No Fake Work (2026-04-25): real Codex AGREE verdict, real
  pytest run (215 affected tests + 6191 full-suite pass), real lint clean,
  real mypy clean, real cross-AI evidence files.
- HARD RULE Continuous Autonomous Mode (2026-04-25): plan-time Codex
  AGREE → impl direct, no operator check-back.
- Guard flag invariants: `support_widening`, `production_platform_claim`,
  `live_adapter_execution` all stay const `false` (pinned by 9 new
  invariant tests).
