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

**Stub adapter discipline (recompute-not-trust corollary).** Per iter-2 absorb (F3), AST import scan + `live_capability` flag trust is **insufficient** — runtime bypass via dynamic import / shell-out / env-var leak is still possible. Stub purity is enforced at THREE layers, with runtime kill-switches dominant:

1. **Static layer (AST scan, advisory):** ast-walk the harness modules and reject any import of `requests`, `httpx`, `urllib.request`, `urllib3`, `socket`, `openai`, `anthropic`, `google.generativeai`, `aiohttp`, `boto3`, `paramiko`, `subprocess`, `cloud SDK` modules. Advisory because dynamic import (`importlib.import_module`) bypasses static scan.
2. **Runtime kill-switch layer (dominant):** tests monkey-patch the harness execution context to fail-closed on any of:
   - `socket.socket.__init__` → raise `SupportWideningError("runtime network access forbidden in smoke harness")`
   - `http.client.HTTPConnection.__init__` → raise
   - `urllib.request.urlopen` → raise
   - `urllib.request.OpenerDirector.open` → raise
   - `requests.request` / `requests.Session.send` / `requests.adapters.HTTPAdapter.send` → raise
   - `httpx.Client.send` / `httpx.AsyncClient.send` → raise
   - `subprocess.Popen.__init__` / `subprocess.run` / `subprocess.call` / `subprocess.check_output` / `subprocess.check_call` → raise
   - `os.system` / `os.popen` → raise
   - `eval` / `exec` invocations inside harness module path → raise (sys.audit hook `exec` / `compile`)
   - Any `os.environ.get` call where the key matches regex `(?i)(api[_-]?key|secret|token|password|credential)` → raise (whitelist of allowed config keys, e.g. `WORKSPACE_ROOT`)
   - `importlib.import_module` invocations whose target name matches the forbidden list above → raise
3. **Runtime declaration layer:** harness module's first action asserts `live_adapter_execution=false` at runtime and raises `SupportWideningError` if any stub adapter declares `live_capability=True`.

Harness output never contains a `live_call_made: true` or equivalent claim. The v1 schema enforces `simulated_only: const true` and `live_call_made: const false` so any forged "we made live calls" payload is schema-invalid (recompute-not-trust corollary).

**Out of scope for E-3-2:** running the harness in CI (E-3-3), the supersession PR's live evidence (Epic 9).

### E-3-3 — Advisory CI matrix scaffolding (`support-matrix-smoke.yml`, opt-in)

**Risk:** medium (new workflow file; opt-in label trigger; **does not become a required check**).
**Deliverables:**
- `.github/workflows/support-matrix-smoke.yml`:
  - Trigger (corrected per iter-2 absorb F4 — GitHub Actions `pull_request` has **no native `labels:` filter** at trigger level):
    ```yaml
    on:
      pull_request:
        types: [opened, labeled, synchronize, reopened]
      workflow_dispatch:
    ```
  - **Job-level label gate** (per F4 — only way to filter by label correctly):
    ```yaml
    jobs:
      smoke:
        if: contains(github.event.pull_request.labels.*.name, 'support-matrix-smoke')
        # ... matrix definition below
    ```
  - **No `push` trigger on `main`.** **No `repository_dispatch`.** **No `schedule`.**
  - Job matrix dimension placeholders: `surface_class: [provider, python_version, os_platform, db_backend, deployment_topology]`; per-class job invokes `scripts/run_support_smoke.py --surface <class>` and uploads the v1 evidence artifact as a GitHub Actions artifact (NOT to GHCR, NOT to a public registry).
  - `continue-on-error: true` per matrix cell so a stub gap in one surface does not block PR merges that opt into the label.
  - Output: per-class evidence artifact attached to the run + a top-level summary comment on the PR (advisory, non-fatal).
- `tests/test_support_matrix_smoke_workflow.py` — YAML invariants per iter-2 absorb F4:
  - Trigger uses `pull_request: types: [opened, labeled, synchronize, reopened]` + `workflow_dispatch` ONLY; no `push`, no `repository_dispatch`, no `schedule`.
  - Job has `if: contains(github.event.pull_request.labels.*.name, 'support-matrix-smoke')` gate (label filter at job level, NOT trigger level).
  - No `secrets:` keys referenced; no `environment:` binding.
  - **Workflow / job / check-run name collision invariant (corrected):** previous "no required-check status published" was inaccurate — every workflow run inevitably produces a check-run on the PR. The correct invariant is:
    1. The workflow `name:` field MUST NOT equal any name in the required-contexts set of any branch protection ruleset (CI reads the ruleset list via `gh api repos/{owner}/{repo}/rulesets` + per-ruleset detail; asserts `support-matrix-smoke` and any job-id-derived check name absent from `required_status_checks.contexts[]`).
    2. The workflow MUST NOT be added to any branch protection ruleset by this slice (CI test computes the ruleset SHA before/after the slice diff and rejects any ruleset diff).
    3. Job names (which determine check-run names) MUST NOT collide with any name in `.github/workflows/test.yml`, `ao-release-gate-*.yml`, `ao-autonomous-merge-executor.yml`, `publish.yml`, etc. (substring + exact match scan).
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
  - **Operator authority block** — explicit operator GitHub login + commit-message authorization phrase + commit verification required. Per iter-2 absorb F6, `operator_authority.operator_github_login` MUST NOT appear in `implementer_provider.github_login` OR any entry of `reviewer_providers[].github_login` (strict disjointness; schema-allOf enforced).
  - **Cross-AI consensus block** — at least two reviewers from **distinct providers** per ADR-0004 (e.g. Codex + Mavis), each emitting AGREE on the same plan digest; same-provider review insufficient regardless of session/thread/subagent distinctness. Per iter-2 absorb F6, `reviewer_providers[]` entries MUST be pairwise distinct (no duplicate provider) AND `implementer_provider` MUST NOT appear in `reviewer_providers[]` (strict disjointness; schema-allOf enforced).
  - **Evidence block** — for every surface class being widened, a v2-schema evidence artifact backed by `evidence_class: live` (NOT `simulated`), with per-class minimum thresholds (provider: 3+ live integration tests passing across 7 consecutive days; Python: full pytest matrix green on 3.11/3.12/3.13 and any added version; OS: smoke per added platform; DB: pgvector backend round-trip on test corpus; topology: isolation test passing).
  - **Evidence-pack bind block (per iter-2 absorb F5 — closes replay / stale artifact / TOCTOU / reviewer drift / denominator manipulation):** every v2 evidence artifact MUST bind the following identity fields, each independently re-derivable and checkable:
    - `plan_digest` — SHA256 of the plan doc at plan-time (recomputed at validator time from `.claude/plans/EPIC-9-SUPERSESSION-PR-PLAN.md` HEAD blob; mismatch rejects).
    - `final_diff_digest` — SHA256 of the merged diff at post-impl (recomputed from `git diff <base>..<merge-commit>`; mismatch rejects).
    - `pr_head_sha` — 40-hex commit SHA matched to GitHub API `/pulls/{n}.head.sha`; mismatch rejects.
    - `workflow_run_ids[]` — array of GitHub Actions run IDs that produced the evidence; validator queries `/actions/runs/{id}` and verifies status=completed, conclusion=success, head_sha matches.
    - `artifact_sha256[]` — per-artifact SHA256 array; validator re-hashes downloaded artifact bytes and matches; any drift rejects.
    - `time_window_boundaries` — `{start, end}` ISO-8601 timestamps for any 7-day window evidence; validator verifies window length >= 7 days AND end <= now AND no artifact in `artifact_sha256[]` is timestamped outside this window (TOCTOU + stale replay closure).
    - `reviewer_identity_hashes[]` — per reviewer; SHA256 of `{provider, github_login, thread_id}` triple. Validator asserts pairwise distinct (no duplicate identity); duplicate reviewer identity rejects.
    - `verdict_completeness_proof` — `{verdicts_received_total: int, verdicts_claimed_in_consensus: int, negative_verdicts_present: bool}`. Validator asserts `verdicts_received_total == verdicts_claimed_in_consensus` (denominator integrity) AND, if `negative_verdicts_present=true`, validator MUST find the negative verdict explicitly listed in `provider_verdicts[]` (filtered-negative-verdict closure).
  - **Recompute-not-trust block** — every evidence artifact's `consensus_*` and `widening_authorized` fields re-derived from raw inputs by the E-3-6 validator and matched against the producer's claim; any drift rejects.
  - **Rollback block** — explicit rollback decision tree (revert tag, revert flag, revert evidence artifact) recorded in the PR body.
- A machine-checkable assertion list (`ao_kernel/defaults/widening-supersession-checklist.v1.json`) the validator consumes. Per F5, every assertion entry has explicit `recompute_strategy` AND `bind_fields[]` listing which evidence-pack bind fields the assertion depends on.
- `tests/test_widening_supersession_checklist.py` — schema-validates the checklist file and asserts that the assertion list is non-empty and that each assertion has an explicit `recompute_strategy` field. Plus negative tests per F5: stale replay (validator rejects evidence whose `time_window_boundaries.end < (now - max_age)`); duplicate reviewer identity (validator rejects if two entries in `reviewer_identity_hashes[]` are equal); filtered negative verdict (validator rejects if `verdict_completeness_proof.negative_verdicts_present=true` but no negative entry in `provider_verdicts[]`); denominator manipulation (validator rejects if `verdicts_received_total != len(provider_verdicts)`); 7-day timing window race (validator rejects if window is < 7 days OR any artifact timestamp falls outside the window).
- Plan doc record at `.claude/plans/EPIC-3-E-3-5-SUPERSESSION-CONSENSUS-PROTOCOL.md`.

**Out of scope for E-3-5:** running the supersession PR itself (Epic 9); flipping the flag (operator + Epic 9).

### E-3-6 — Recompute-not-trust validator (`scripts/validate_widening_evidence.py`)

**Risk:** low (pure module + CLI; no mutation).
**Deliverables:**
- `scripts/validate_widening_evidence.py --evidence <path> [--strict]`. CLI thin wrapper. **Epic 3 scope: v1-only** (per iter-2 absorb F1 — no v2 acceptance path in Epic 3).
- `ao_kernel/_internal/support_widening/validator.py` — pure module: given a v1 evidence artifact, re-derive every `consensus_*` field from raw inputs (per-call records, per-test outcomes, per-provider verdicts), assert `support_widening: false` literal, and reject any drift.
  - **v1-only fail-closed (per iter-2 absorb F1):** this Epic 3 validator module REJECTS any v2 input with reason `unsupported_future_schema_in_epic_3`. There is **no `widening_authorized: true` acceptance path** in this module, latent or otherwise. The v2 schema + the validator extension that accepts `widening_authorized: true` is built as a **separate module** (`ao_kernel/_internal/support_widening/validator_v2.py`) introduced **only** by the Epic 9 operator-bound supersession PR, behind the operator authority gate. Epic 3 module + Epic 9 module are physically separate files; Epic 3 cannot accidentally call into v2 acceptance because the v2 module does not exist in the Epic 3 codebase.
  - **Bind-field verification (per iter-2 absorb F5):** for v1 artifacts, validator recomputes `plan_digest` from the referenced plan doc HEAD blob, `artifact_sha256[]` from disk reads, and rejects any drift; v1 artifacts that lack the bind fields are accepted (v1 evidence is *infrastructure*, not authorization), but any v1 artifact that *does* carry bind fields must satisfy them.
  - **Self-review prevention (per iter-2 absorb F6):** for any artifact carrying `operator_authority`, `implementer_provider`, `reviewer_providers`, validator asserts the three fields are pairwise disjoint at the `github_login` level AND `reviewer_providers[]` entries are pairwise distinct at the `provider` level AND `implementer_provider.provider` is not in `reviewer_providers[].provider`. Any violation rejects.
- `ao_kernel/_internal/support_widening/validator_v2.py` — **explicitly absent in Epic 3 codebase**. Created only by Epic 9 supersession PR with operator authority gate, distinct schema (`support_widening_evidence.schema.v2.json`), and separate import path. Epic 3 CI invariant test asserts `validator_v2.py` does not exist in the tree.
- `tests/test_widening_evidence_validator.py` — invariants per iter-2 absorb:
  - Forged producer claims rejected (consensus drift).
  - v1 always fails-closed on `widening_authorized: true` regardless of producer flags.
  - v2 input → rejected with `unsupported_future_schema_in_epic_3` reason code (F1).
  - Validator module does NOT import `validator_v2` (AST scan); `validator_v2.py` does NOT exist in tree (file-existence test) (F1).
  - Self-review prevention: artifact with `operator_authority.github_login == implementer_provider.github_login` rejects (F6).
  - Self-review prevention: artifact with `implementer_provider.github_login` in `reviewer_providers[].github_login` rejects (F6).
  - Duplicate reviewer provider: artifact with `reviewer_providers: [{provider: "anthropic", ...}, {provider: "anthropic", ...}]` rejects (F6).
  - Bind-field drift: artifact with `plan_digest` not matching recomputed plan doc SHA256 rejects (F5).
  - Bind-field drift: artifact with `artifact_sha256[i]` not matching on-disk SHA256 of referenced artifact rejects (F5).
- Plan doc record at `.claude/plans/EPIC-3-E-3-6-RECOMPUTE-VALIDATOR.md`.

**Validator anti-patterns it rejects** (ADR-0002 informed):
- Producer wrote `consensus_status: agree` but raw `provider_verdicts[]` contains a `revise`. → Reject.
- Producer wrote `widening_authorized: true` on v1 schema. → Reject (v1 const false invariant; Epic 3 module rejects ALL widening_authorized:true regardless of schema version).
- Producer fed v2 artifact to Epic 3 validator. → Reject with `unsupported_future_schema_in_epic_3`; only Epic 9 supersession PR's `validator_v2.py` accepts v2.
- Producer wrote `simulated_only: true` but evidence artifact contains a `live_call_made: true` field. → Reject (mutually exclusive).
- Producer wrote `reviewer_providers: ["anthropic", "anthropic"]`. → Reject (ADR-0004 distinct-provider rule; F6 disjoint enforcement).
- Producer wrote `operator_authority.github_login == reviewer_providers[0].github_login`. → Reject (F6 self-review prevention).
- Producer wrote `plan_digest: <stale-sha>` not matching current plan doc. → Reject (F5 replay closure).

**Out of scope for E-3-6:** flipping any flag, running any live calls, any GitHub mutation, accepting any v2 input.

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

**v1 vs v2 separation (per iter-2 absorb F1, hardened):** the *only* way to legitimately emit `support_widening: true` is via the *future* v2 schema (`support_widening_evidence.schema.v2.json`), which is introduced *only* by the Epic 9 operator-bound supersession PR. Epic 3 ships v1 only; v2 is out of scope.

The separation is enforced at **THREE structural layers** in Epic 3:

1. **Schema layer:** Epic 3 schema (`support_widening_evidence.schema.v1.json`) has `support_widening: const false` AND `schema_version: const "support_widening_evidence.v1"`. No Epic 3 artifact can carry `schema_version: "support_widening_evidence.v2"` because Epic 3 ships only the v1 schema file.
2. **Module layer (Epic 3):** the Epic 3 validator module (`ao_kernel/_internal/support_widening/validator.py`) is **v1-only fail-closed** — it rejects any input where `schema_version != "support_widening_evidence.v1"` with reason code `unsupported_future_schema_in_epic_3`. It contains NO `widening_authorized: true` acceptance code path, latent or otherwise.
3. **File-existence layer:** the Epic 3 codebase does **not** ship `validator_v2.py` or `support_widening_evidence.schema.v2.json`. The v2 acceptance code physically does not exist in Epic 3's tree (CI invariant test: `assert not Path("ao_kernel/_internal/support_widening/validator_v2.py").exists()` and same for v2 schema). The v2 validator module + v2 schema are introduced only by the Epic 9 operator-bound supersession PR, behind the operator authority gate and ADR-0004 cross-AI distinct-provider review.

This three-layer separation is the structural reason no Epic 3 slice — including E-3-6 — can flip the flag even by mistake. Even an adversarial Epic 3 contributor who modifies the validator module to accept v2 would be blocked by (a) absence of v2 schema in tree, (b) CI invariant rejecting v2-acceptance code paths in `validator.py`, and (c) the cross-AI distinct-provider review on the slice PR catching the structural violation.

---

## 6. Test Invariants per Slice

**Minimum count: 6 invariant tests per slice; minimum 2 per slice must be `no_guard_flip` invariants** asserting both (a) the artifact literal contains `support_widening: false`, and (b) no code path in the slice mutates the flag.

### E-3-1 minimums (6+ per slice; expanded per iter-2 absorb F2)
- BLK-no_guard_flip-1: schema `support_widening` is `const false`; mutation of the schema fails schema-validation test.
- BLK-no_guard_flip-2: `evidence.py` module raises `SupportWideningError` if any caller passes a payload with `support_widening: true`.
- BLK-schema-strict-recursive (F2): `additionalProperties: false` AND `unevaluatedProperties: false` at EVERY nested object node (root, `evidence_dimensions`, every per-class shape under `allOf`/`if/then`, every `$defs` node, every nested object inside `recompute_inputs`). Test walks the schema AST and asserts the closure property holds at every node. Unknown field at any depth → schema-invalid.
- BLK-schema-no-remote-ref (F2): test asserts no `$ref` value in the schema starts with `http://` or `https://`; all refs are local fragment references (`#/$defs/...`).
- BLK-recompute-inputs-no-shadow-widening (F2): test asserts no key inside `recompute_inputs` (recursive) matches regex `(?i)(support[_-]?widening|widening[_-]?authorized|live[_-]?adapter[_-]?execution|production[_-]?platform[_-]?claim|github[_-]?write[_-]?authorized)` — `recompute_inputs` MUST NOT be a shadow widening surface.
- BLK-recompute-validator: producer flag re-derived from raw fields; drift rejected.
- BLK-register-authority: `register_authority` `const "evidence_record_only"`; module rejects anything else.
- BLK-cli-readonly: CLI `validate` and `--recompute` perform no file mutation; assertion via tmpdir + before/after stat.

### E-3-2 minimums (6+ per slice; expanded per iter-2 absorb F3)
- BLK-no_guard_flip-1: every harness emit path produces `support_widening: false` literal (test loads emitted JSON, asserts on the string value).
- BLK-no_guard_flip-2: stub adapter import test (advisory) — `ast`-walk the harness modules, assert no `requests`, `httpx`, `urllib.request`, `urllib3`, `socket`, `openai`, `anthropic`, `google.generativeai`, `aiohttp`, `boto3`, `paramiko`, `subprocess` live-network imports.
- BLK-runtime-kill-switch-network (F3, dominant): test wraps harness execution with monkey-patches that make `socket.socket.__init__`, `http.client.HTTPConnection.__init__`, `urllib.request.urlopen`, `urllib.request.OpenerDirector.open`, `requests.request`, `requests.Session.send`, `requests.adapters.HTTPAdapter.send`, `httpx.Client.send`, `httpx.AsyncClient.send` raise `SupportWideningError` on any call; harness invocation MUST complete successfully (no network attempted). Any kill-switch raise → test fails.
- BLK-runtime-kill-switch-subprocess (F3): test patches `subprocess.Popen.__init__`, `subprocess.run`, `subprocess.call`, `subprocess.check_output`, `subprocess.check_call`, `os.system`, `os.popen` to raise on any call; harness completes without invocation.
- BLK-runtime-kill-switch-secrets (F3): test patches `os.environ.get` to raise if key matches regex `(?i)(api[_-]?key|secret|token|password|credential)` (with explicit whitelist of allowed config keys like `WORKSPACE_ROOT`, `CI`, `PYTHONPATH`); harness completes without forbidden env reads.
- BLK-runtime-kill-switch-dynamic-import (F3): test patches `importlib.import_module` to raise if target name matches the forbidden network/secret module list; harness completes without forbidden dynamic imports. Also `sys.audit` hook for `compile` / `exec` events fails the test if harness path triggers them.
- BLK-no_live_call: runtime assertion in `harnesses/__init__.py` raises if any adapter declares `live_capability=True`.
- BLK-library-mode: harness asserts `workspace_root=None` (library mode); `.ao/` filesystem snapshot before/after is byte-identical.
- BLK-simulated-only: every emitted artifact carries `simulated_only: true`; `live_call_made` field is absent or `false`.
- BLK-schema-conformance: every emitted artifact is schema-valid against `support_widening_evidence.schema.v1.json`.

### E-3-3 minimums (6+ per slice; corrected per iter-2 absorb F4)
- BLK-no_guard_flip-1: workflow YAML grep for `support_widening: true` literal — must not appear.
- BLK-no_guard_flip-2: assertion list of files MUST NOT be modified by this workflow: `.github/workflows/test.yml`, `ao-autonomous-merge-executor.yml`, `ao-release-gate-container-publish.yml`, `ao-release-gate-deploy-cloud-run.yml`, `bc1-protected-live-adapter-attestation.yml`, `bc10-real-adapter-usage-cost.yml`, `live-adapter-gate.yml`, `publish.yml`, `ao-ma-11a-plan-approval.yml`, `ao-ma-11e-2b-mirror-sync.yml`, `policy-container-publish.yml`, `policy-service-deploy-cloud-run.yml`, `ao-ma10q-dedicated-actor-smoke.yml`. CI test `git diff --stat origin/main -- <paths>` MUST be empty.
- BLK-trigger-correct (F4): workflow trigger is `pull_request: types: [opened, labeled, synchronize, reopened]` + `workflow_dispatch` ONLY; no `push`, no `repository_dispatch`, no `schedule`. Test parses workflow YAML and asserts exact trigger shape. **No `labels:` filter at trigger level** (GitHub Actions does not support it; previous design assumed it incorrectly).
- BLK-job-label-gate (F4): jobs in this workflow MUST carry `if: contains(github.event.pull_request.labels.*.name, 'support-matrix-smoke')` job-level gate (label filtering happens at job, not trigger). Test parses workflow YAML and asserts every job carries this `if:` expression (or equivalent label-match expression).
- BLK-no-ruleset-collision (F4): workflow `name:` value and every job-id-derived check-run name MUST NOT appear in any branch protection ruleset's `required_status_checks.contexts[]`. Test queries `gh api repos/{owner}/{repo}/rulesets` + per-ruleset detail, parses contexts, asserts no collision. The previous "no required-check status published" invariant is REMOVED (incorrect — workflow inevitably produces a check-run); replaced by this collision invariant.
- BLK-no-ruleset-mutation (F4): the slice PR diff MUST NOT modify any branch protection ruleset. Test asserts `gh api` ruleset listing SHA before and after the slice diff is identical (no ruleset added, removed, or modified).
- BLK-no-job-name-collision (F4): job names in this workflow MUST NOT exact-match or substring-match any job name in `.github/workflows/test.yml`, `ao-autonomous-merge-executor.yml`, `ao-release-gate-*.yml`, `publish.yml`. Test parses all referenced workflow files and asserts the disjoint property.
- BLK-permissions-minimal: workflow `permissions:` block contains only `contents: read` and `pull-requests: write`; no `actions: write`, `id-token: write`, `packages: write`, `deployments: write`.
- BLK-no-secrets: workflow YAML contains no `secrets.` expression and no `environment:` binding.

### E-3-4 minimums (6+ per slice; expanded per iter-2 absorb F7)
- BLK-no_guard_flip-1 (F7, expanded forbidden-language regex): doc text MUST NOT contain ANY of the following, case-insensitive, outside fenced code blocks or quoted-reference contexts. Test compiles a regex set and asserts no match:
  - `production-ready` / `production ready`
  - `production safe` / `production-safe`
  - `production certified` / `production-certified`
  - `production grade` / `production-grade`
  - `fully supported` / `fully-supported`
  - `GA` (word-boundary; case-sensitive uppercase to avoid false matches in "garbage" etc.)
  - `generally available`
  - `officially supported`
  - `stable support`
  - `beta exit`
  - `supported today`
  - `ready for production`
- BLK-no_guard_flip-2: doc text MUST contain the verbatim disclaimer paragraph: "This inventory does not announce any widening; it names what would be required if widening were authorized."
- BLK-mirror-discipline: doc references `docs/SUPPORT-BOUNDARY.md` §1.1 (ST-2 freeze) and does not re-claim the boundary itself.
- BLK-surface-completeness: doc lists all five surface classes (provider, python_version, os_platform, db_backend, deployment_topology).
- BLK-prerequisite-completeness: each surface section names the prerequisite evidence count/type per the v1 schema's per-class `allOf`.
- BLK-no-tier-mutation: `docs/SUPPORT-BOUNDARY.md` and `docs/PUBLIC-BETA.md` are NOT modified by this slice (CI `git diff --stat` empty).

### E-3-5 minimums (6+ per slice; expanded per iter-2 absorb F5+F6)
- BLK-no_guard_flip-1: checklist JSON `support_widening: false` literal present at top level.
- BLK-no_guard_flip-2: checklist JSON contains `widening_flip_authority: "operator_bound_supersession_pr_only"` and explicit "this checklist alone does not authorize the flip" assertion.
- BLK-operator-authority-required: checklist assertion list includes `operator_authority_block_present` with `required: true`.
- BLK-cross-ai-distinct-provider: checklist assertion list requires `reviewer_providers[]` to satisfy ADR-0004 distinct-provider rule.
- BLK-evidence-class-live: checklist assertion list requires `evidence_class: live` for every surface widening (NOT `simulated`).
- BLK-recompute-strategy-present: every assertion in the list has an explicit `recompute_strategy` field; validator test rejects checklist with any assertion missing this field.
- BLK-bind-fields-required (F5): every assertion in the list MUST also have a `bind_fields[]` field naming which evidence-pack bind fields (`plan_digest`, `final_diff_digest`, `pr_head_sha`, `workflow_run_ids`, `artifact_sha256`, `time_window_boundaries`, `reviewer_identity_hashes`, `verdict_completeness_proof`) the assertion depends on. Empty `bind_fields` rejected.
- BLK-stale-replay-rejected (F5, negative test): test feeds the checklist a synthetic evidence pack whose `time_window_boundaries.end` is older than `now - 90 days`; assertion list MUST trigger reject (stale-replay closure).
- BLK-duplicate-reviewer-identity-rejected (F5, negative test): test feeds synthetic pack where two entries in `reviewer_identity_hashes[]` are equal; checklist MUST trigger reject.
- BLK-filtered-negative-verdict-rejected (F5, negative test): test feeds pack with `verdict_completeness_proof.negative_verdicts_present: true` but `provider_verdicts[]` carries only `agree` entries; checklist MUST trigger reject.
- BLK-denominator-manipulation-rejected (F5, negative test): test feeds pack with `verdict_completeness_proof.verdicts_received_total: 3` but `len(provider_verdicts) == 2`; checklist MUST trigger reject.
- BLK-7day-window-race-rejected (F5, negative test): test feeds pack with `time_window_boundaries` length < 7 days OR an artifact timestamp outside the window; checklist MUST trigger reject.
- BLK-disjoint-identities-required (F6): checklist requires `operator_authority.github_login`, `implementer_provider.github_login`, and every `reviewer_providers[].github_login` to be pairwise distinct; same-login overlap rejects.
- BLK-disjoint-providers-required (F6): checklist requires `reviewer_providers[].provider` entries pairwise distinct AND `implementer_provider.provider` not in `reviewer_providers[].provider`; overlap rejects.

### E-3-6 minimums (6+ per slice; expanded per iter-2 absorb F1+F5+F6)
- BLK-no_guard_flip-1: validator on v1 input always rejects any `support_widening: true` or `widening_authorized: true` claim regardless of producer flags.
- BLK-no_guard_flip-2: validator does not mutate any input file (read-only); assertion via tmpdir + checksum before/after.
- BLK-v2-rejected-in-epic-3 (F1): validator REJECTS any input with `schema_version: "support_widening_evidence.v2"` with reason code `unsupported_future_schema_in_epic_3`. No v2 acceptance code path exists in Epic 3 validator module.
- BLK-v2-validator-module-absent (F1): test asserts `ao_kernel/_internal/support_widening/validator_v2.py` does NOT exist in the Epic 3 tree (file-existence check).
- BLK-v2-schema-absent (F1): test asserts `ao_kernel/defaults/schemas/support-widening-evidence.schema.v2.json` does NOT exist in the Epic 3 tree.
- BLK-validator-no-v2-import (F1): AST scan of `validator.py` asserts no import or string-literal mention of `validator_v2`, `schema.v2`, or `widening_authorized = True` acceptance branches.
- BLK-forged-consensus-rejected: validator rejects producer-claimed `consensus_status: agree` when raw `provider_verdicts[]` contains a `revise`.
- BLK-same-provider-rejected (F6): validator rejects artifact with `reviewer_providers: [{provider:"anthropic",...}, {provider:"anthropic",...}]` (ADR-0004; duplicate provider).
- BLK-implementer-in-reviewer-rejected (F6): validator rejects artifact where `implementer_provider.provider` appears in `reviewer_providers[].provider` (self-review at provider level).
- BLK-operator-login-collision-rejected (F6): validator rejects artifact where `operator_authority.operator_github_login` equals `implementer_provider.github_login` OR any `reviewer_providers[].github_login` (self-review at identity level).
- BLK-mutually-exclusive: validator rejects artifact with both `simulated_only: true` and `live_call_made: true`.
- BLK-plan-digest-drift-rejected (F5): validator rejects artifact with `plan_digest` not matching the recomputed SHA256 of the referenced plan doc HEAD blob.
- BLK-artifact-sha-drift-rejected (F5): validator rejects artifact with any `artifact_sha256[i]` not matching the on-disk SHA256 of the referenced artifact file.

Per CLAUDE.md test-quality gate (conftest AST-based BLK rules): assertions are concrete (no `assert callable(x)`, no `assert True`); negative cases use `pytest.raises(SupportWideningError)` not bare `except: pass`.

---

## 7. Schema Design Notes — `support_widening_evidence.v1`

### Top-level constraints

- `$schema`: `https://json-schema.org/draft/2020-12/schema`
- `$id`: `urn:ao:support-widening-evidence:v1`
- `title`: `Support Widening Evidence (v1, infrastructure-only)`
- `type`: `object`
- `additionalProperties`: `false`
- `unevaluatedProperties`: `false`

### Recursive closure (per iter-2 absorb F2 — required at EVERY nested node)

**Every** object node in the schema — root, `evidence_dimensions`, every per-class shape under `allOf`/`if/then`, every `$defs` entry, every nested object inside `recompute_inputs`, every supersession bind-field group — MUST carry:

- `type: object`
- `additionalProperties: false`
- `unevaluatedProperties: false` (closes `allOf`/`oneOf`/`anyOf`/`if/then/else` keyword-evaluation bypass paths that `additionalProperties` alone does not)

Test invariant (E-3-1 BLK-schema-strict-recursive) walks the schema AST and asserts the closure property at every node. Failure mode this prevents: a producer adding a top-level unknown field is rejected by `additionalProperties:false`, but a producer adding an unknown field inside an `allOf` branch that defines its own object — without `unevaluatedProperties:false` — would slip through. The recursive closure pin closes the gap.

### Remote `$ref` FORBIDDEN (per iter-2 absorb F2)

The schema MUST NOT contain any `$ref` value starting with `http://` or `https://`. All references are local fragment refs (`#/$defs/...`). Test invariant (E-3-1 BLK-schema-no-remote-ref) walks the schema and asserts the property. Failure mode this prevents: an attacker who can control a remote schema endpoint could alter the validation contract at validation time (TOCTOU); local-only refs make the schema contract immutable after the wheel ships.

### `recompute_inputs` shadow-widening guard (per iter-2 absorb F2)

`recompute_inputs` is intended to carry the raw fields from which `consensus_*` fields are re-derived. It MUST NOT be a back-door widening surface. Schema constraints:

- `recompute_inputs` is `type: object`, `additionalProperties: false`, `unevaluatedProperties: false`.
- No key inside `recompute_inputs` (recursive) may match the forbidden-widening regex `(?i)(support[_-]?widening|widening[_-]?authorized|live[_-]?adapter[_-]?execution|production[_-]?platform[_-]?claim|github[_-]?write[_-]?authorized)`.
- Test invariant (E-3-1 BLK-recompute-inputs-no-shadow-widening) walks the `recompute_inputs` schema and asserts no forbidden key name appears at any depth.

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

### Disjoint-identity invariants (per iter-2 absorb F6 — for v2 supersession; v1 carries no `operator_authority` so vacuous in v1 but documented here for forward consistency)

For any artifact (current v1 vacuously, future v2 actively) carrying `operator_authority`, `implementer_provider`, `reviewer_providers`, schema-level `allOf` invariants:

1. `operator_authority.github_login` MUST NOT equal `implementer_provider.github_login`.
2. `operator_authority.github_login` MUST NOT appear in `reviewer_providers[].github_login`.
3. `implementer_provider.github_login` MUST NOT appear in `reviewer_providers[].github_login`.
4. `reviewer_providers[]` entries MUST be pairwise distinct at `github_login` (no duplicate reviewer identity).
5. `implementer_provider.provider` MUST NOT appear in `reviewer_providers[].provider` (ADR-0004 distinct-provider rule at the provider level).
6. `reviewer_providers[].provider` entries MUST be pairwise distinct (no two reviewers from same provider).

These invariants close the operator-self-review attack surface: an operator who is also an implementer or a reviewer cannot fulfill both roles in the same artifact; reviewers from the same provider cannot multiply-attest the same artifact.

### Mirror with existing patterns

The schema mirrors the field set and discipline of `ao-ma-10-evidence-bundle.schema.v1.json` (3-guard const false + register_authority + ai_output_release_authority pattern) and `ri7-cross-lane-production-matrix-evidence.schema.v1.json` (per-class evidence dimensions), so reviewers familiar with those schemas can read this one without re-deriving the conventions.

---

## 8. Pre-supersession-PR Gate Checklist (what Epic 9 PR must satisfy to flip the flag)

This is the *future* checklist that the operator-bound Epic 9 supersession PR will satisfy. Captured here so Epic 3's deliverables (E-3-5 + E-3-6) are aligned with what the actual flip will require.

1. **Operator authority block** (with iter-2 absorb F6 disjoint-identity enforcement)
   - PR squash message carries `Operator-Authorization: I authorize the support_widening flip` (exact phrase, grep-checkable).
   - Operator GitHub login matches the configured operator (`Halildeu`) and the PR is authored or merged by that login.
   - Commit verification required (GPG-signed or GitHub-verified squash).
   - **Self-review prevention (F6):** operator GitHub login MUST NOT appear as implementer or any reviewer for this artifact (validator-enforced disjointness; schema allOf invariant).

2. **Cross-AI consensus** (ADR-0004; with iter-2 absorb F6 enforcement)
   - At least two distinct-provider reviewers (e.g. Codex + Mavis) emit AGREE on the same plan digest.
   - Anthropic-only review insufficient; same-provider review insufficient regardless of session/thread distinction.
   - PR squash message carries `Reviewer-1: <provider> <thread-id>` + `Reviewer-2: <provider> <thread-id>` with distinct provider names.
   - **Reviewer disjointness (F6):** `reviewer_providers[].github_login` pairwise distinct (no duplicate identity); `reviewer_providers[].provider` pairwise distinct (no duplicate provider); `implementer_provider.provider` not in `reviewer_providers[].provider`. Validator rejects on any violation.

3. **Evidence pack** (uses v2 schema; v1 insufficient; iter-2 absorb F5 bind-fields required)
   - For *each* surface class being widened in this supersession: a v2 evidence artifact backed by `evidence_class: live` (NOT `simulated`).
   - **Evidence-pack bind fields (F5, ALL required):**
     - `plan_digest` — SHA256 of the supersession PR's plan doc at plan-time (validator recomputes from HEAD blob; mismatch rejects).
     - `final_diff_digest` — SHA256 of the merged diff at post-impl (validator recomputes from `git diff <base>..<merge-commit>`; mismatch rejects).
     - `pr_head_sha` — 40-hex commit SHA matched to GitHub API `/pulls/{n}.head.sha`; mismatch rejects.
     - `workflow_run_ids[]` — array of GitHub Actions run IDs (validator queries `/actions/runs/{id}`, verifies status=completed, conclusion=success, head_sha matches).
     - `artifact_sha256[]` — per-artifact SHA256 array (validator re-hashes downloaded artifact bytes; drift rejects).
     - `time_window_boundaries` — `{start, end}` ISO-8601 (validator verifies length >= 7 days, end <= now, no artifact timestamped outside window).
     - `reviewer_identity_hashes[]` — per reviewer SHA256 of `{provider, github_login, thread_id}` (validator asserts pairwise distinct; duplicate identity rejects).
     - `verdict_completeness_proof` — `{verdicts_received_total, verdicts_claimed_in_consensus, negative_verdicts_present}` (validator asserts denominator integrity AND, if `negative_verdicts_present=true`, the negative entry is explicitly present in `provider_verdicts[]`).
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

---

## 14. Iter-2 Absorb Summary (Codex thread `019e87a0` iter-1 REVISE → iter-2)

This section maps each Codex iter-1 finding (F1..F7) to the specific sections updated in this plan revision. Iter-1 verdict: REVISE, `ready_for_impl=false`, 6 blocker + 1 non-blocker.

| Finding | Severity | Category | Sections updated in iter-2 |
|---|---|---|---|
| **F1** — E-3-6 validator latent `widening_authorized: true` acceptance path | blocker (high) | v1/v2 separation | §2 E-3-6 (v1-only fail-closed; `validator_v2.py` explicitly absent; AST scan invariant); §5 Guard-flag Invariants (three-layer separation: schema + module + file-existence); §6 E-3-6 test invariants (BLK-v2-rejected-in-epic-3, BLK-v2-validator-module-absent, BLK-v2-schema-absent, BLK-validator-no-v2-import) |
| **F2** — v1 schema strictness root-only; bypass via `allOf`/`if/then`/`$ref`/nested/`recompute_inputs` | blocker (high) | schema recursive closure | §7 Schema Design Notes (recursive closure section: `additionalProperties:false` + `unevaluatedProperties:false` at every node; remote `$ref` FORBIDDEN; `recompute_inputs` shadow-widening guard); §6 E-3-1 test invariants (BLK-schema-strict-recursive, BLK-schema-no-remote-ref, BLK-recompute-inputs-no-shadow-widening) |
| **F3** — Smoke harness stub purity relies on AST scan + flag trust; runtime bypass possible | blocker (high) | runtime kill-switch | §2 E-3-2 stub adapter discipline (three-layer: static AST, runtime kill-switch dominant, runtime declaration); §6 E-3-2 test invariants (BLK-runtime-kill-switch-network, BLK-runtime-kill-switch-subprocess, BLK-runtime-kill-switch-secrets, BLK-runtime-kill-switch-dynamic-import) |
| **F4** — `support-matrix-smoke.yml` label trigger semantics wrong; "no required-check published" incorrect | blocker (medium) | workflow + collision invariant | §2 E-3-3 (correct trigger `pull_request: types: [opened, labeled, synchronize, reopened]` + `workflow_dispatch`; job-level `if: contains(...)` gate; workflow/job name collision invariant replaces incorrect "no required-check status" claim); §6 E-3-3 test invariants (BLK-trigger-correct, BLK-job-label-gate, BLK-no-ruleset-collision, BLK-no-ruleset-mutation, BLK-no-job-name-collision) |
| **F5** — Recompute validator + checklist do not cover replay/stale/TOCTOU/identity drift/denominator | blocker (high) | evidence-pack bind fields | §2 E-3-5 (evidence-pack bind block with 8 bind fields: `plan_digest`, `final_diff_digest`, `pr_head_sha`, `workflow_run_ids[]`, `artifact_sha256[]`, `time_window_boundaries`, `reviewer_identity_hashes[]`, `verdict_completeness_proof`); §2 E-3-6 (bind-field verification module); §6 E-3-5 negative tests (BLK-stale-replay-rejected, BLK-duplicate-reviewer-identity-rejected, BLK-filtered-negative-verdict-rejected, BLK-denominator-manipulation-rejected, BLK-7day-window-race-rejected); §6 E-3-6 test invariants (BLK-plan-digest-drift-rejected, BLK-artifact-sha-drift-rejected); §8 Pre-supersession-PR Gate Checklist evidence-pack bind fields section |
| **F6** — Operator self-review prevention not machine-checkable | blocker (medium) | disjoint identity invariants | §2 E-3-5 (operator authority block + cross-AI consensus block; disjointness requirements); §2 E-3-6 (self-review prevention module); §7 Schema Design Notes (disjoint-identity invariants section: 6 `allOf` invariants); §6 E-3-5 test invariants (BLK-disjoint-identities-required, BLK-disjoint-providers-required); §6 E-3-6 test invariants (BLK-same-provider-rejected, BLK-implementer-in-reviewer-rejected, BLK-operator-login-collision-rejected); §8 Pre-supersession-PR Gate Checklist self-review prevention items |
| **F7** — Surface inventory forbidden-language regex too narrow | non-blocker (medium) | expanded language regex | §6 E-3-4 test invariants (BLK-no_guard_flip-1 expanded to 12-variant regex set: production-ready / production safe / production certified / production grade / fully supported / GA / generally available / officially supported / stable support / beta exit / supported today / ready for production) |

**Total findings absorbed:** 7/7 (6 blocker + 1 non-blocker).

**Plan structure invariants preserved:** 13 original sections retained in identical order; this §14 added as new appendix. No section deleted, no scope expanded beyond iter-1 finding closures.

**Cross-cutting iter-2 hardening principles applied:**

1. **Three-layer separation everywhere** — schema constraint + module discipline + file-existence/absence invariant. Applied to v1/v2 (F1) and recursive closure (F2).
2. **Runtime kill-switches dominate static checks** — F3 demotes AST scan to advisory, promotes monkey-patched runtime fail-closed to dominant.
3. **Bind everything; trust nothing** — F5 evidence-pack bind fields make every "did this really happen" question independently recomputable. Producer claims without bind support are inert.
4. **Disjoint roles at every layer** — F6 disjointness applied at schema (`allOf`), module (validator), and process (checklist) layers. Operator-as-implementer-as-reviewer attack surface closed.
5. **Public-claim language is regex-fenced** — F7 forbidden-language set expanded to cover paraphrase variants the original set missed.

**Iter-2 verdict (next):** awaiting Codex iter-2 review. If AGREE + `ready_for_impl=true`, E-3-1 evidence schema slice may open (V5 §Epic 3 PR-1 sequencing). If REVISE, absorb iter-3 and continue.

**No-Fake-Work attestation (HARD RULE 2026-04-25):** iter-1 verdict was real REVISE (Codex MCP thread `019e87a0`); iter-2 absorb covers each of F1..F7 by section; iter-2 verdict will be recorded as real Codex output. No aspirational AGREE fabrication.
