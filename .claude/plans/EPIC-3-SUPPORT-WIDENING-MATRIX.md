# Epic 3 — Support Widening Matrix (Infrastructure)

**Risk:** critical (epic-level, due to eventual `support_widening` flag flip outside this epic) · **Slice risk:** all low/medium (additive, opt-in, flag-preserving)
**Parent roadmap:** `.claude/plans/V5-FULL-PRODUCTION-PROMOTION-ROADMAP.md` §Epic 3
**Status:** PROPOSED (plan-only; no slice has been opened yet)
**Visibility:** GitHub Milestone "v5.0.0" → Issue "Epic 3 — Support widening" (mirror; NOT authority)
**Authority:** this plan doc + `.claude/plans/` JSONL evidence + `ao-release-gate`; GitHub project is one-way mirror per V5 §7

---

## 1. Scope + Non-Goal Statement

**Scope (what this epic DOES).** Epic 3 ships *infrastructure* that makes a future support-widening promotion **decidable** with real evidence: a versioned evidence schema (`support_widening_evidence.v1.json`), per-surface smoke harness scaffolding that produces evidence artifacts in library mode against stub adapters, an **opt-in advisory** GitHub Actions workflow that runs the harness across surface classes without mutating any required check, a surface inventory document that names the current "narrow stable" boundary and what each future widening dimension requires, a cross-AI consensus protocol for the eventual operator-bound supersession PR, and a deterministic recompute-not-trust validator that re-derives consensus fields from the evidence inputs.

**Non-goal (what this epic explicitly does NOT do).**

- **No slice in this epic flips the `support_widening` guard flag.** Every artifact this epic emits pins `support_widening: false` as a JSON Schema `const false` value AND re-asserts the same pin at module level (ADR-0002 recompute-not-trust pattern).
- **No slice in this epic flips `live_adapter_execution` or `production_platform_claim`.** The smoke harness uses stub adapters only; no real provider HTTP calls, no live secrets, no protected environment dispatch.
- **The flip itself is gated by a separate operator-bound supersession PR** (Epic 9 / PR-Xfinal in the V5 roadmap), which uses a *different* schema version (`support_widening_evidence.v2.json`) and carries an explicit operator authorization block. No v1 artifact, no matter how many evidence dimensions it carries, can authorize the flip.
- **No mutation of existing required workflows.** `.github/workflows/test.yml`, `ao-autonomous-merge-executor.yml`, `ao-release-gate-*.yml`, `live-adapter-gate.yml`, `bc1-protected-live-adapter-attestation.yml`, `bc10-real-adapter-usage-cost.yml`, `publish.yml`, and `ao-ma-11a-plan-approval.yml` are read-only for this epic. Epic 3 *adds* a new advisory workflow (`support-matrix-smoke.yml`) on a label-trigger; it does not mutate any existing required check, does not change any branch protection ruleset, does not add bypass actors, and does not gain required status.
- **No public claim change.** README, badges, and `docs/SUPPORT-BOUNDARY.md` stable-baseline language stay unchanged. The surface inventory doc this epic adds (E-3-4) describes *current* narrow stable + *future* widening prerequisites; it does not announce any widening.

**Boundary restatement.** Epic 3 is *plumbing* for widening. The widening *itself* — flipping the flag, publishing a wider support claim, accepting bug reports against a wider matrix — is a separate operator-bound act outside this epic.

---

## 2. Slice Breakdown

Six additive, opt-in slices. Each slice is independently mergeable, carries its own cross-AI plan-time consultation, and produces its own evidence + invariant test set. Sequence below is the recommended order but only E-3-1 is a hard prerequisite for the others.

### E-3-1 — Support widening evidence schema (`support_widening_evidence.v1.json`)

**Risk:** low (schema + module + invariant tests; no workflows touched).
**Deliverables:**
- `ao_kernel/defaults/schemas/support-widening-evidence.schema.v1.json` (Draft 2020-12, `additionalProperties: false`).
- `ao_kernel/_internal/support_widening/evidence.py` — pure module: `parse_v1(payload, *, schema)`, `recompute_v1(payload)`, `verify_v1(payload, *, on_disk_refs)`. No I/O at the boundary; all on-disk reads pass through the verifier and re-hash from disk (ADR-0002 pattern).
- CLI handler `ao-kernel support-widening evidence validate <path>` and `--recompute` flag (read-only, no mutation).
- `tests/test_support_widening_evidence_v1.py` — schema + module + CLI invariants (see §6 minimum count).
- Plan doc record at `.claude/plans/EPIC-3-E-3-1-EVIDENCE-SCHEMA.md` (decision record per AO-MA pattern).

**Schema highlights** (see §7 for the full design):
- `schema_version: const "support_widening_evidence.v1"` — exact pin; v2 is the supersession schema.
- `support_widening: const false` — schema-level pin; module re-asserts at runtime.
- `surface_class` enum (`provider | python_version | os_platform | db_backend | deployment_topology`) with per-class required evidence dimensions encoded via `allOf` / `oneOf`.
- `register_authority: const "evidence_record_only"` — schema-level confirmation this artifact is not release authority.
- `github_write_authorized: const false`.
- `live_adapter_execution: const false`; `production_platform_claim: const false`.

**Out of scope for E-3-1:** harness execution (E-3-2), CI wiring (E-3-3), supersession schema v2 (Epic 9).

### E-3-2 — Per-surface smoke harness scaffolding (library-mode, stub adapters)

**Risk:** low/medium (new script + per-class harness modules; library-mode only; no live calls).
**Deliverables:**
- `scripts/run_support_smoke.py --surface <provider|python_version|os_platform|db_backend|deployment_topology> [--evidence-out <path>]`.
- `ao_kernel/_internal/support_widening/harnesses/` — one module per surface class. Each harness:
  - Uses **stub adapters** that conform to provider/backend interfaces but never make network calls (mirrors the existing `ao_kernel/_internal/providers/` stub conventions).
  - Executes library-mode workflows only (`workspace_root=None`); no `.ao/` mutation, no JSONL evidence side-effects beyond the artifact this script emits.
  - Emits a `support_widening_evidence.v1` artifact via the E-3-1 module with `support_widening: false` literal in every emit path.
- `tests/test_run_support_smoke_<surface>.py` per surface (5 tests; one per surface class).
- Plan doc record at `.claude/plans/EPIC-3-E-3-2-SMOKE-HARNESS.md`.

**Stub adapter discipline (recompute-not-trust corollary):**
- Stub adapters MUST NOT carry network sockets, real API keys, or live secret env-var lookups. The harness module's first action is to assert `live_adapter_execution=false` at runtime and raise `SupportWideningError` if any stub adapter declares live capability.
- Harness output never contains a `live_call_made: true` or equivalent claim. The v1 schema enforces `simulated_only: const true` so any forged "we made live calls" payload is schema-invalid.

**Out of scope for E-3-2:** running the harness in CI (E-3-3), the supersession PR's live evidence (Epic 9).

### E-3-3 — Advisory CI matrix scaffolding (`support-matrix-smoke.yml`, opt-in)

**Risk:** medium (new workflow file; opt-in label trigger; **does not become a required check**).
**Deliverables:**
- `.github/workflows/support-matrix-smoke.yml`:
  - Trigger: `pull_request` filtered to `labels: ['support-matrix-smoke']` AND `workflow_dispatch`. **No push trigger on `main`.** **No required-check status published.**
  - Job matrix dimension placeholders: `surface_class: [provider, python_version, os_platform, db_backend, deployment_topology]`; per-class job invokes `scripts/run_support_smoke.py --surface <class>` and uploads the v1 evidence artifact as a GitHub Actions artifact (NOT to GHCR, NOT to a public registry).
  - `continue-on-error: true` per matrix cell so a stub gap in one surface does not block PR merges that opt into the label.
  - Output: per-class evidence artifact attached to the run + a top-level summary comment on the PR (advisory).
- `tests/test_support_matrix_smoke_workflow.py` — YAML invariants: opt-in trigger, no required-check name, no `repository_dispatch`, no `secrets:` keys referenced, no `environment:` binding.
- Plan doc record at `.claude/plans/EPIC-3-E-3-3-CI-MATRIX.md`.

**Mutation guards (CLAUDE.md §17 + V5 §10 PR-X2 conventions):**
- The workflow MUST NOT alter `.github/workflows/test.yml`, any `ao-release-gate-*.yml`, `ao-autonomous-merge-executor.yml`, `publish.yml`, or branch protection rulesets. CI test (`tests/test_support_matrix_smoke_workflow.py`) asserts no unintended file diffs in those paths via a recompute-not-trust check that re-reads the listed paths and rejects any change unless the slice PR explicitly opts in (which E-3-3 does not).
- The new workflow does not request `permissions: write-all`; only `contents: read` + `pull-requests: write` for the advisory PR comment, no more.

**Out of scope for E-3-3:** promoting this workflow to a required check (Epic 9 supersession-only), running real provider live calls (Epic 2 + Epic 9 supersession-only).

### E-3-4 — Surface inventory document (`docs/SUPPORT-SURFACE-INVENTORY.md`)

**Risk:** low (docs-only; no runtime impact).
**Deliverables:**
- `docs/SUPPORT-SURFACE-INVENTORY.md` — narrative companion to `docs/SUPPORT-BOUNDARY.md`. Sections:
  1. **Current narrow stable boundary** (read from `docs/SUPPORT-BOUNDARY.md` §1.1 and restated here, not re-claimed): what providers/Python/OS/DB are supported *today* under "narrow stable runtime".
  2. **Surface dimensions inventoried for future widening**: provider (e.g. Mistral, Cohere, Llama via HuggingFace), Python (3.10 backward compat decision), OS (Windows desktop, macOS Apple Silicon, Linux ARM64), DB backend (pgvector — extra pinned today, no backend), deployment topology (single-tenant container, k8s Helm, multi-tenant SaaS).
  3. **What each widening dimension requires** (from the v1 schema's per-class evidence list — *prerequisites*, not promises): N live integration tests, full pytest matrix, smoke per platform, round-trip per backend, isolation test per topology.
  4. **Boundary disclaimer**: this inventory **does not announce** any widening; it names what would be required *if* widening were authorized. Mirrors `docs/SUPPORT-BOUNDARY.md` §1.1 language: "ST-2 stable boundary freeze" stays in effect until the operator-bound supersession PR (Epic 9) explicitly opens a dimension.
- `tests/test_support_surface_inventory_doc.py` — `pytest` assertions: file exists, contains the disclaimer paragraph verbatim, does not contain any "production-ready" / "fully supported" / "GA" claim language outside quoted-reference contexts.
- Plan doc record at `.claude/plans/EPIC-3-E-3-4-SURFACE-INVENTORY.md`.

**Out of scope for E-3-4:** any change to `docs/SUPPORT-BOUNDARY.md` §1.1 freeze language (Epic 9 supersession-only); any change to `docs/PUBLIC-BETA.md` tier rows (Epic 9 supersession-only).

### E-3-5 — Cross-AI consensus protocol for the final supersession PR

**Risk:** low (process + checklist + machine-checkable assertion list; no runtime code).
**Deliverables:**
- `.claude/plans/EPIC-3-E-3-5-SUPERSESSION-CONSENSUS-PROTOCOL.md` — checklist that the **future** Epic 9 supersession PR must satisfy *before* the flag flip is permitted. Structure:
  - **Operator authority block** — explicit operator GitHub login + commit-message authorization phrase + commit verification required.
  - **Cross-AI consensus block** — at least two reviewers from **distinct providers** per ADR-0004 (e.g. Codex + Mavis), each emitting AGREE on the same plan digest; same-provider review insufficient regardless of session/thread/subagent distinctness.
  - **Evidence block** — for every surface class being widened, a v2-schema evidence artifact backed by `evidence_class: live` (NOT `simulated`), with per-class minimum thresholds (provider: 3+ live integration tests passing across 7 consecutive days; Python: full pytest matrix green on 3.11/3.12/3.13 and any added version; OS: smoke per added platform; DB: pgvector backend round-trip on test corpus; topology: isolation test passing).
  - **Recompute-not-trust block** — every evidence artifact's `consensus_*` and `widening_authorized` fields re-derived from raw inputs by the E-3-6 validator and matched against the producer's claim; any drift rejects.
  - **Rollback block** — explicit rollback decision tree (revert tag, revert flag, revert evidence artifact) recorded in the PR body.
- A machine-checkable assertion list (`ao_kernel/defaults/widening-supersession-checklist.v1.json`) the validator consumes.
- `tests/test_widening_supersession_checklist.py` — schema-validates the checklist file and asserts that the assertion list is non-empty and that each assertion has an explicit `recompute_strategy` field.
- Plan doc record at `.claude/plans/EPIC-3-E-3-5-SUPERSESSION-CONSENSUS-PROTOCOL.md`.

**Out of scope for E-3-5:** running the supersession PR itself (Epic 9); flipping the flag (operator + Epic 9).

### E-3-6 — Recompute-not-trust validator (`scripts/validate_widening_evidence.py`)

**Risk:** low (pure module + CLI; no mutation).
**Deliverables:**
- `scripts/validate_widening_evidence.py --evidence <path> [--checklist <path>] [--strict]`. CLI thin wrapper.
- `ao_kernel/_internal/support_widening/validator.py` — pure module: given an evidence artifact (v1 or v2), re-derive every `consensus_*` field from raw inputs (per-call records, per-test outcomes, per-provider verdicts), and reject any drift. On v1 input, the validator additionally asserts `support_widening: false` literal; on v2 input, it consumes the E-3-5 checklist and verifies every assertion holds **before** honoring any `widening_authorized: true` claim.
- `tests/test_widening_evidence_validator.py` — invariants: forged producer claims rejected, v1 always fails-closed on widening claim, v2 only passes when checklist holds end-to-end.
- Plan doc record at `.claude/plans/EPIC-3-E-3-6-RECOMPUTE-VALIDATOR.md`.

**Validator anti-patterns it rejects** (ADR-0002 informed):
- Producer wrote `consensus_status: agree` but raw `provider_verdicts[]` contains a `revise`. → Reject.
- Producer wrote `widening_authorized: true` on v1 schema. → Reject (v1 const false invariant; v2 only).
- Producer wrote `widening_authorized: true` on v2 with operator authority block missing or operator GitHub login not matching the configured operator. → Reject.
- Producer wrote `simulated_only: true` but evidence artifact contains a `live_call_made: true` field. → Reject (mutually exclusive).
- Producer wrote `reviewer_providers: ["anthropic", "anthropic"]` for a v2 supersession artifact. → Reject (ADR-0004 distinct-provider rule).

**Out of scope for E-3-6:** flipping any flag, running any live calls, any GitHub mutation.

---

## 3. Risk Class per Slice

| Slice | Slice risk | Epic-aggregate risk source |
|---|---|---|
| E-3-1 Evidence schema | low | flag-pinning patterns are well-tested; schema is fully `const`-locked |
| E-3-2 Smoke harness | low/medium | stub adapter discipline is the only failure surface |
| E-3-3 CI matrix (advisory) | medium | NEW workflow file; explicit no-mutation invariants on existing required checks; opt-in trigger only |
| E-3-4 Surface inventory doc | low | docs-only; disclaimer test prevents language drift |
| E-3-5 Consensus protocol | low | docs + JSON checklist; no runtime impact |
| E-3-6 Recompute validator | low | pure module + CLI; no mutation |

**Epic-aggregate risk** is *critical* because Epic 3 is the runway to the operator-bound supersession PR (Epic 9) that eventually flips the flag. **Individual slice risk** is at most medium because each slice is additive, opt-in, and flag-preserving. The high-risk act (the flip itself) is *outside this epic*, gated by Epic 9 + operator authorization + ADR-0004 cross-AI consensus + E-3-6 recompute validation.

---

## 4. Cross-AI Consensus Protocol per Slice

Per ADR-0004 (cross-AI implementer ≠ reviewer at the **provider** level), every Epic 3 slice follows the standard two-gate pattern:

| Gate | Provider rule | Action |
|---|---|---|
| **Plan-time CNS** | Implementer (Claude) opens consultation; reviewer from distinct provider (Codex or Mavis) | AGREE → direct impl (Plan Consensus Autonomy); REVISE → absorb + iter |
| **Post-impl review** | Same distinct-provider reviewer reviews the impl diff | AGREE → normal squash merge (no `--admin`); REVISE → fix iter; RED → escalate to operator |

**Distinct-provider matrix for Epic 3** (implementer most likely Claude):

| Slice | Recommended reviewer provider(s) |
|---|---|
| E-3-1 Evidence schema | Codex (schema strict-mode review strength) |
| E-3-2 Smoke harness | Codex or Mavis (any distinct provider; harness adversarial review for stub-purity) |
| E-3-3 CI matrix workflow | Codex (workflow YAML review strength); strict on no-mutation invariants |
| E-3-4 Surface inventory doc | Mavis or Codex (any distinct provider) |
| E-3-5 Consensus protocol | Codex AND Mavis (two distinct providers, because this slice defines the future supersession protocol itself; double cross-AI is appropriate) |
| E-3-6 Recompute validator | Codex (recompute-not-trust pattern review strength; ADR-0002 author chain) |

PR squash messages MUST carry `Implementer: <provider> (session/thread <id>)` + `Reviewer: <provider> (session/thread <id>)` block per ADR-0004; the audit grep is part of the merge contract.

---

## 5. Guard-flag Invariants

Every artifact this epic emits — schema-validated JSON, plan doc YAML front-matter, harness output, validator output — MUST satisfy:

| Flag | Required value in every Epic 3 artifact | Enforcement |
|---|---|---|
| `support_widening` | `false` (`const false` in schema; re-asserted at module level per ADR-0002) | E-3-1 schema; E-3-2/3/4/5/6 module-level assertion + invariant test |
| `live_adapter_execution` | `false` (`const false`) | E-3-2 harness stub-only; runtime assertion in `harnesses/__init__.py` |
| `production_platform_claim` | `false` (`const false`) | E-3-1 schema; mirrored in plan doc YAML front-matter for every slice record |
| `register_authority` | `"evidence_record_only"` (`const`) | E-3-1 schema; mirrored in plan doc YAML front-matter |
| `github_write_authorized` | `false` (`const false`) | E-3-1 schema; mirrored in plan doc YAML front-matter (E-3-3 workflow does not perform any GitHub mutation beyond an advisory PR comment) |

**Recompute discipline** (ADR-0002): for every slice, the validator (E-3-6 once it lands; per-slice invariant test before then) re-asserts these flags at runtime by reading the artifact from disk and re-deriving the verdict, rather than trusting the producer's serialized claim.

**v1 vs v2 separation**: the *only* way to legitimately emit `support_widening: true` is via the *future* v2 schema (`support_widening_evidence.schema.v2.json`), which is introduced *only* by the Epic 9 operator-bound supersession PR. Epic 3 ships v1 only; v2 is out of scope. This separation is the structural reason no Epic 3 slice can flip the flag even by mistake.

---

## 6. Test Invariants per Slice

**Minimum count: 6 invariant tests per slice; minimum 2 per slice must be `no_guard_flip` invariants** asserting both (a) the artifact literal contains `support_widening: false`, and (b) no code path in the slice mutates the flag.

### E-3-1 minimums (6+)
- BLK-no_guard_flip-1: schema `support_widening` is `const false`; mutation of the schema fails schema-validation test.
- BLK-no_guard_flip-2: `evidence.py` module raises `SupportWideningError` if any caller passes a payload with `support_widening: true`.
- BLK-schema-strict: `additionalProperties: false` at every nested object; unknown field rejected.
- BLK-recompute-validator: producer flag re-derived from raw fields; drift rejected.
- BLK-register-authority: `register_authority` `const "evidence_record_only"`; module rejects anything else.
- BLK-cli-readonly: CLI `validate` and `--recompute` perform no file mutation; assertion via tmpdir + before/after stat.

### E-3-2 minimums (6+)
- BLK-no_guard_flip-1: every harness emit path produces `support_widening: false` literal (test loads emitted JSON, asserts on the string value).
- BLK-no_guard_flip-2: stub adapter import test — `ast`-walk the harness modules, assert no `requests`, `httpx`, `urllib.request`, `socket`, `openai`, `anthropic`, etc. live-network imports.
- BLK-no_live_call: runtime assertion in `harnesses/__init__.py` raises if any adapter declares `live_capability=True`.
- BLK-library-mode: harness asserts `workspace_root=None` (library mode); `.ao/` filesystem snapshot before/after is byte-identical.
- BLK-simulated-only: every emitted artifact carries `simulated_only: true`; `live_call_made` field is absent or `false`.
- BLK-schema-conformance: every emitted artifact is schema-valid against `support_widening_evidence.schema.v1.json`.

### E-3-3 minimums (6+)
- BLK-no_guard_flip-1: workflow YAML grep for `support_widening: true` literal — must not appear.
- BLK-no_guard_flip-2: assertion list of files MUST NOT be modified by this workflow: `.github/workflows/test.yml`, `ao-autonomous-merge-executor.yml`, `ao-release-gate-container-publish.yml`, `ao-release-gate-deploy-cloud-run.yml`, `bc1-protected-live-adapter-attestation.yml`, `bc10-real-adapter-usage-cost.yml`, `live-adapter-gate.yml`, `publish.yml`, `ao-ma-11a-plan-approval.yml`, `ao-ma-11e-2b-mirror-sync.yml`, `policy-container-publish.yml`, `policy-service-deploy-cloud-run.yml`, `ao-ma10q-dedicated-actor-smoke.yml`. CI test `git diff --stat origin/main -- <paths>` MUST be empty.
- BLK-opt-in-trigger: workflow triggers only on `pull_request` with label `support-matrix-smoke` AND `workflow_dispatch`; no `push`, no `repository_dispatch`, no `schedule`.
- BLK-no-required-check: workflow does not register itself as required in any branch protection ruleset (test reads the ruleset list via `gh api` in CI dry-run mode and asserts absence).
- BLK-permissions-minimal: workflow `permissions:` block contains only `contents: read` and `pull-requests: write`; no `actions: write`, `id-token: write`, `packages: write`, `deployments: write`.
- BLK-no-secrets: workflow YAML contains no `secrets.` expression and no `environment:` binding.

### E-3-4 minimums (6+)
- BLK-no_guard_flip-1: doc text MUST NOT contain "support widening enabled", "fully supported", "GA", "production-ready" outside fenced code blocks or quoted-reference contexts.
- BLK-no_guard_flip-2: doc text MUST contain the verbatim disclaimer paragraph: "This inventory does not announce any widening; it names what would be required if widening were authorized."
- BLK-mirror-discipline: doc references `docs/SUPPORT-BOUNDARY.md` §1.1 (ST-2 freeze) and does not re-claim the boundary itself.
- BLK-surface-completeness: doc lists all five surface classes (provider, python_version, os_platform, db_backend, deployment_topology).
- BLK-prerequisite-completeness: each surface section names the prerequisite evidence count/type per the v1 schema's per-class `allOf`.
- BLK-no-tier-mutation: `docs/SUPPORT-BOUNDARY.md` and `docs/PUBLIC-BETA.md` are NOT modified by this slice (CI `git diff --stat` empty).

### E-3-5 minimums (6+)
- BLK-no_guard_flip-1: checklist JSON `support_widening: false` literal present at top level.
- BLK-no_guard_flip-2: checklist JSON contains `widening_flip_authority: "operator_bound_supersession_pr_only"` and explicit "this checklist alone does not authorize the flip" assertion.
- BLK-operator-authority-required: checklist assertion list includes `operator_authority_block_present` with `required: true`.
- BLK-cross-ai-distinct-provider: checklist assertion list requires `reviewer_providers[]` to satisfy ADR-0004 distinct-provider rule.
- BLK-evidence-class-live: checklist assertion list requires `evidence_class: live` for every surface widening (NOT `simulated`).
- BLK-recompute-strategy-present: every assertion in the list has an explicit `recompute_strategy` field; validator test rejects checklist with any assertion missing this field.

### E-3-6 minimums (6+)
- BLK-no_guard_flip-1: validator on v1 input always rejects any `support_widening: true` claim regardless of producer flags.
- BLK-no_guard_flip-2: validator does not mutate any input file (read-only); assertion via tmpdir + checksum before/after.
- BLK-forged-consensus-rejected: validator rejects producer-claimed `consensus_status: agree` when raw `provider_verdicts[]` contains a `revise`.
- BLK-same-provider-rejected: validator rejects v2 supersession artifact with `reviewer_providers: ["anthropic", "anthropic"]` (ADR-0004).
- BLK-mutually-exclusive: validator rejects artifact with both `simulated_only: true` and `live_call_made: true`.
- BLK-operator-mismatch-rejected: validator rejects v2 artifact with `operator_authority.operator_github_login` not matching the configured operator login.

Per CLAUDE.md test-quality gate (conftest AST-based BLK rules): assertions are concrete (no `assert callable(x)`, no `assert True`); negative cases use `pytest.raises(SupportWideningError)` not bare `except: pass`.

---

## 7. Schema Design Notes — `support_widening_evidence.v1`

### Top-level constraints

- `$schema`: `https://json-schema.org/draft/2020-12/schema`
- `$id`: `urn:ao:support-widening-evidence:v1`
- `title`: `Support Widening Evidence (v1, infrastructure-only)`
- `type`: `object`
- `additionalProperties`: `false`

### Required top-level fields

```
schema_version          const "support_widening_evidence.v1"
artifact_kind           const "support_widening_evidence"
generated_at            string format=date-time
repo                    string pattern="^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$"
surface_class           enum ["provider", "python_version", "os_platform", "db_backend", "deployment_topology"]
support_widening        const false
production_platform_claim  const false
live_adapter_execution  const false
register_authority      const "evidence_record_only"
github_write_authorized const false
simulated_only          const true
live_call_made          const false
evidence_dimensions     object (required, additionalProperties: false; per-class shape via allOf below)
reviewer_providers      array minItems=0 (Epic 3 evidence is INFRASTRUCTURE; per-slice review trail recorded separately)
recompute_inputs        object (required) — raw inputs from which any consensus/aggregation field MUST be re-derivable
```

### Per-surface required dimensions (encoded via `allOf` + `if/then`)

| `surface_class` | `evidence_dimensions` shape (v1 minimum) |
|---|---|
| `provider` | `{integration_tests: {count: int >= 0}, stub_adapter_ids: [string], note: string}` — v1 records stub-tests; v2 requires `live_integration_tests.count >= 3` |
| `python_version` | `{matrix: [string subset of ["3.11", "3.12", "3.13"]], pytest_passed: boolean}` — v1 records library-mode; v2 requires full matrix green |
| `os_platform` | `{platform: enum ["linux-x86_64","linux-arm64","macos-x86_64","macos-arm64","windows-amd64"], smoke_passed: boolean}` — v1 stub; v2 requires smoke per added platform |
| `db_backend` | `{backend: enum ["sqlite_in_memory", "pgvector", "future_other"], round_trip_passed: boolean}` — v1 stub for pgvector (backend not yet implemented); v2 requires real round-trip |
| `deployment_topology` | `{topology: enum ["library", "single_tenant_container", "k8s_helm", "multi_tenant_saas"], isolation_passed: boolean}` — v1 stub; v2 requires isolation test |

### Why `const false` cannot be bypassed in v1

JSON Schema `const false` makes any other value schema-invalid; the E-3-1 module additionally re-asserts the same pin at runtime (ADR-0002 recompute-not-trust corollary). To legitimately emit `support_widening: true`, a producer must use a *different* schema (`support_widening_evidence.schema.v2.json`), which is introduced by the Epic 9 operator-bound supersession PR and not by this epic. Schema separation makes the policy structurally enforceable rather than process-dependent.

### Mirror with existing patterns

The schema mirrors the field set and discipline of `ao-ma-10-evidence-bundle.schema.v1.json` (3-guard const false + register_authority + ai_output_release_authority pattern) and `ri7-cross-lane-production-matrix-evidence.schema.v1.json` (per-class evidence dimensions), so reviewers familiar with those schemas can read this one without re-deriving the conventions.

---

## 8. Pre-supersession-PR Gate Checklist (what Epic 9 PR must satisfy to flip the flag)

This is the *future* checklist that the operator-bound Epic 9 supersession PR will satisfy. Captured here so Epic 3's deliverables (E-3-5 + E-3-6) are aligned with what the actual flip will require.

1. **Operator authority block**
   - PR squash message carries `Operator-Authorization: I authorize the support_widening flip` (exact phrase, grep-checkable).
   - Operator GitHub login matches the configured operator (`Halildeu`) and the PR is authored or merged by that login.
   - Commit verification required (GPG-signed or GitHub-verified squash).

2. **Cross-AI consensus** (ADR-0004)
   - At least two distinct-provider reviewers (e.g. Codex + Mavis) emit AGREE on the same plan digest.
   - Anthropic-only review insufficient; same-provider review insufficient regardless of session/thread distinction.
   - PR squash message carries `Reviewer-1: <provider> <thread-id>` + `Reviewer-2: <provider> <thread-id>` with distinct provider names.

3. **Evidence pack** (uses v2 schema; v1 insufficient)
   - For *each* surface class being widened in this supersession: a v2 evidence artifact backed by `evidence_class: live` (NOT `simulated`).
   - Per-class minimum thresholds:
     - `provider`: 3+ live integration tests across 7 consecutive days; per-call usage/cost evidence aggregated.
     - `python_version`: full pytest matrix green on 3.11/3.12/3.13 + any added version.
     - `os_platform`: per-platform smoke passed under real OS runner.
     - `db_backend`: pgvector backend round-trip on a representative test corpus; schema-validated result.
     - `deployment_topology`: isolation test passing for multi-tenant SaaS topology if claimed.

4. **Recompute-not-trust verification** (E-3-6 validator)
   - Validator re-derives every `consensus_*` and `widening_authorized` field from raw inputs; drift rejects.
   - Producer's `widening_authorized: true` honored only after validator AGREE.

5. **CI green** (CLAUDE.md HARD RULE 2026-05-17)
   - All required checks green; no `--admin` bypass; no failing advisory check left red.
   - Existing required checks (`.github/workflows/test.yml`, `ao-release-gate-*`, etc.) unchanged.

6. **Rollback decision tree**
   - PR body explicitly states: revert tag procedure, flag revert procedure (v3 schema rollback path), evidence artifact retention policy.
   - Rollback triggers documented (regression, post-flip bug report, cost overrun).

7. **Public claim language sync**
   - README badge update permitted *only* after the flag flip merges; not in the same PR as the flip (Codex iter-1 invariant #8 of V5 §9).
   - `docs/SUPPORT-BOUNDARY.md` §1.1 freeze paragraph updated to name the dimensions added.
   - `docs/PUBLIC-BETA.md` tier rows updated; `docs/SUPPORT-SURFACE-INVENTORY.md` (from E-3-4) updated to reflect the now-active widening.

8. **Mirror discipline** (V5 §7)
   - GitHub Milestone "v5.0.0" Epic 3 issue closed by the supersession PR; mirror digest written back to manifest.

If any of (1)–(7) is missing or fails, the validator rejects the artifact and the flag flip MUST NOT proceed even if the PR is otherwise mergeable.

---

## 9. PR Sequencing for Epic 3

Each slice = one issue + one short-lived branch + one PR + one decision record per CLAUDE.md §17 and AGENTS.md.

| Slice | Branch prefix | Worktree | Predecessor | Independent? |
|---|---|---|---|---|
| E-3-1 | `codex/epic3-e1-evidence-schema` | dedicated | none (Epic 3 entry slice) | yes (others depend on this schema being merged) |
| E-3-2 | `codex/epic3-e2-smoke-harness` | dedicated | E-3-1 merged | depends on E-3-1 schema |
| E-3-3 | `codex/epic3-e3-ci-matrix` | dedicated | E-3-2 merged | depends on E-3-2 harness script |
| E-3-4 | `codex/epic3-e4-surface-inventory` | dedicated | E-3-1 (references schema dimensions) | parallel with E-3-3 OK |
| E-3-5 | `codex/epic3-e5-consensus-protocol` | dedicated | E-3-1 | parallel with E-3-3/4 OK |
| E-3-6 | `codex/epic3-e6-recompute-validator` | dedicated | E-3-1 + E-3-5 (consumes checklist) | last; consumes 1 and 5 |

Recommended order: **E-3-1 → (E-3-2 ∥ E-3-4 ∥ E-3-5) → E-3-3 → E-3-6**. Each PR uses merge-commit method per CLAUDE.md §19 if stacked; squash if independent. No `--admin` per CLAUDE.md global HARD RULE 2026-05-05.

---

## 10. Out-of-Scope (for Epic 3)

- The flag flip itself (Epic 9 supersession-only).
- `support_widening_evidence.schema.v2.json` (Epic 9 supersession-only).
- Real provider live integration tests (Epic 2 + Epic 9 supersession-only).
- Promoting `support-matrix-smoke.yml` to a required check (Epic 9 supersession-only).
- Updates to `docs/SUPPORT-BOUNDARY.md` tier rows or `docs/PUBLIC-BETA.md` freeze language (Epic 9 supersession-only).
- README badge or public claim change (Epic 9 supersession-only).
- Branch protection ruleset modifications (Epic 9 + operator).
- Adding bypass actors to any ao-release-gate ruleset (forbidden per gpp_status.v1.json `forbidden_actions`).
- pgvector backend implementation (V5 roadmap Epic 7 §E-7-5; Epic 3 schema accepts pgvector as a dimension but does not implement the backend).
- Windows / macOS Apple Silicon / Linux ARM64 platform support (V5 roadmap Epic 3 §E-3-2-E-3-5 outside this *infrastructure* epic; those are Epic 9 supersession-only acts).

---

## 11. Living Files (touched by this epic, in addition to deliverables in §2)

- `.claude/plans/V5-FULL-PRODUCTION-PROMOTION-ROADMAP.md` — Epic 3 status row updated as each slice closes.
- `.claude/plans/EPIC-3-SUPPORT-WIDENING-MATRIX.md` — this plan doc; updated when a slice closes.
- `.claude/plans/EPIC-3-E-3-{1..6}-*.md` — six slice decision records (one per slice).
- `ao_kernel/defaults/schemas/support-widening-evidence.schema.v1.json` — added by E-3-1.
- `ao_kernel/defaults/widening-supersession-checklist.v1.json` — added by E-3-5.
- `ao_kernel/_internal/support_widening/` — new internal package (E-3-1 evidence module, E-3-2 harnesses, E-3-6 validator).
- `scripts/run_support_smoke.py` — added by E-3-2.
- `scripts/validate_widening_evidence.py` — added by E-3-6.
- `.github/workflows/support-matrix-smoke.yml` — added by E-3-3 (advisory, opt-in).
- `docs/SUPPORT-SURFACE-INVENTORY.md` — added by E-3-4.
- `tests/test_support_widening_*.py` — six test files (one per slice).

NOT touched by this epic: all files listed in §6 E-3-3 BLK-no_guard_flip-2 (existing required workflows + branch protection rulesets).

---

## 12. Cross-AI Review for THIS Plan Doc

Implementer: Claude (Anthropic). Reviewer: Codex (OpenAI) — distinct provider per ADR-0004 + CLAUDE.md HARD RULE 2026-05-14. Plan-time consultation MUST AGREE before any slice opens.

Suggested CNS payload for this plan:
- Subject: "Epic 3 — Support widening matrix infrastructure plan adversarial review"
- Ask: "Identify any path by which an Epic 3 slice could (a) flip `support_widening`, (b) flip `live_adapter_execution`, (c) mutate an existing required workflow, (d) pass review without distinct-provider reviewer, (e) emit an evidence artifact whose recompute fails. Identify any missing invariant, any schema gap, any test gap."

---

## 13. References

- `.claude/plans/V5-FULL-PRODUCTION-PROMOTION-ROADMAP.md` — parent roadmap §Epic 3 + §6 guard flag flip authority path + §7 mirror discipline
- `.claude/plans/GENERAL-PURPOSE-PRODUCTION-PROMOTION-STATUS.md` — GPP program closure under `keep_narrow_stable_runtime`
- `.claude/plans/gpp_status.v1.json` — machine-readable program state; `support_widening_allowed: false` + forbidden_actions list
- `.claude/plans/adr/ADR-0002-fail-closed-recompute-not-trust.md` — recompute-not-trust invariant; E-3-1 and E-3-6 directly apply
- `.claude/plans/adr/ADR-0004-cross-ai-implementer-reviewer-distinct-provider.md` — distinct-provider review at the **provider** level
- `.claude/plans/adr/ADR-0001-ao-ma-spm-program-adoption.md` — SPM program framing
- `.claude/plans/adr/ADR-0005-keep-a-changelog-per-pr-discipline.md` — changelog discipline (each Epic 3 slice carries `[Unreleased]` entry or chore opt-out)
- `~/.claude/projects/-Users-halilkocoglu-Documents-ao-kernel/memory/feedback_v35_codex_two_gate.md` — two-gate (plan-time + post-impl) discipline
- `ao_kernel/defaults/schemas/ao-ma-10-evidence-bundle.schema.v1.json` — schema field/pattern reference (3-guard const false + register_authority pattern)
- `ao_kernel/defaults/schemas/ri7-cross-lane-production-matrix-evidence.schema.v1.json` — per-class evidence dimension pattern reference
- `docs/SUPPORT-BOUNDARY.md` — current narrow stable boundary; §1.1 ST-2 freeze language
- `docs/PUBLIC-BETA.md` — tier rows; not modified by Epic 3
- CLAUDE.md §17 (Branch discipline), §19 (Stacked PR merge protocol), §21 (GPP Agent Operating Contract); global HARD RULEs: 2026-05-05 (Admin Merge YASAK), 2026-05-14 (Cross-AI provider level), 2026-05-17 (CI Kırmızıyken Merge YASAK), 2026-05-27 (Uzun Vadeli Kalıcı Çözüm Tercih Edilir)
- AGENTS.md — agent operating contract; `support_widening=true` only via GPP full matrix + explicit closeout (Epic 9)
