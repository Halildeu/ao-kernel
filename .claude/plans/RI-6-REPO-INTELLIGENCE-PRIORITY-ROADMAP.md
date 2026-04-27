# RI-6 - Repo Intelligence Priority Roadmap

**Status:** draft roadmap slice
**Date:** 2026-04-27
**Authority:** `origin/main`
**Issue:** [#499](https://github.com/Halildeu/ao-kernel/issues/499)
**Branch:** `codex/ri-roadmap-prioritization`
**Worktree:** `/Users/halilkocoglu/Documents/ao-kernel-ri-roadmap-prioritization`
**Program constraint:** `GPP-2` remains blocked
**Support impact:** none
**Production claim impact:** none

## 1. Purpose

Prioritize repo-intelligence work with a written, trackable roadmap while the
general-purpose production promotion program remains blocked at `GPP-2`.

This roadmap is not a support-widening decision. It does not claim
repo-intelligence production workflow integration, does not unblock live adapter
runtime binding, and does not change the current product verdict:

```text
support_widening=false
production_platform_claim=false
live_adapter_execution_allowed=false
```

## 2. Current Boundary

Repo intelligence is available today as Beta / experimental surfaces:

1. `repo scan` creates deterministic local `.ao/context/` artifacts.
2. `repo index --dry-run` creates a deterministic vector write plan only.
3. `repo index --write-vectors` is explicit-write Beta and requires exact
   confirmation, backend configuration, and embedding credentials.
4. `repo query` is read-only retrieval over a configured vector backend.
5. `repo query --output markdown` is the supported explicit handoff format.
6. `repo export-plan` is preview-only and writes only
   `.ao/context/repo_export_plan.json`.
7. `repo export` is confirmed create-only root export for selected targets.

The current boundary deliberately excludes:

1. automatic prompt injection;
2. a repo-intelligence MCP tool;
3. hidden `context_compiler` auto-feed;
4. automatic root authority export;
5. live real-adapter execution;
6. remote PR write support;
7. arbitrary production repository write support;
8. a general-purpose production platform claim.

## 3. Roadmap Principles

1. Every slice must be narrow, written, testable, and fail-closed.
2. Every slice must preserve `GPP-2` blocked status unless protected live-adapter
   prerequisites are independently attested by the GPP process.
3. Runtime integration must be explicit opt-in, never hidden injection.
4. Metadata must travel with context: source path, line range, source hash,
   namespace, freshness, and support tier.
5. Missing metadata, stale sources, hash mismatch, unknown namespace, path
   escape, or disabled config must produce `blocked` or `fail`, not fake pass.
6. Support tier wording must move with behavior and tests.

## 4. Phase Board

| Phase | Status | Goal | Support impact |
|---|---|---|---|
| `RI-6.0` | This slice | Written priority roadmap | none |
| `RI-6.1` | Proposed | Repo-intelligence evidence refresh | none |
| `RI-6.2` | Proposed | Explicit handoff hardening | Beta wording only if docs need clarification |
| `RI-6.3` | Proposed | Workflow opt-in input contract implementation | no production claim |
| `RI-6.4` | Proposed | Deterministic read-only workflow rehearsal refresh | no production claim |
| `RI-6.5` | Proposed | MCP read-only design gate, no implementation by default | none |
| `RI-6.6` | Proposed | Context compiler opt-in design gate, no auto-feed | none |
| `GPP-5` | Future / gated | Repo-intelligence workflow integration candidate | requires explicit GPP slice |
| `GPP-6` | Future / gated | Read-only production E2E with real adapter | blocked on GPP-2/GPP-4 |

## 5. RI-6.1 - Evidence Refresh

**Goal:** Reconfirm the current repo-intelligence Beta surfaces from a clean
checkout and installed-package path where practical.

**Scope:**

1. Run `repo scan` on the repository.
2. Run `repo index --dry-run`.
3. Run `repo export-plan`.
4. Run `repo export` only in an isolated fixture or temporary workspace where
   create-only root writes are safe.
5. Record expected fail-closed behavior for `repo query` when vector backend or
   embedding configuration is absent.

**Out of scope:**

1. Live vector writes unless an explicit throwaway backend is configured.
2. MCP tool registration.
3. `context_compiler` feed.
4. Root writes in the primary checkout.
5. Support widening.

**Acceptance criteria:**

1. Each command has a captured JSON/text result or an explicit blocked reason.
2. Generated artifacts validate against their schemas where schemas exist.
3. Source artifacts remain under `.ao/context/` except confirmed create-only
   root export in an isolated test workspace.
4. `support_widening=false` remains true in all relevant reports.
5. `python3 scripts/gpp_next.py` still reports `GPP-2` as blocked.

**Validation:**

```bash
python3 -m ao_kernel repo scan --project-root . --output json
python3 -m ao_kernel repo index --project-root . --workspace-root .ao --dry-run --output json
python3 -m ao_kernel repo export-plan --project-root . --workspace-root .ao --targets codex,agents --output json
python3 -m ao_kernel doctor
python3 scripts/gpp_next.py
```

## 6. RI-6.2 - Explicit Handoff Hardening

**Goal:** Make `repo query --output markdown` stronger as an agent-readable,
operator-visible handoff without making it an automatic workflow integration.

**Scope:**

1. Ensure the Markdown handoff carries source paths, line ranges, source hashes,
   namespace, freshness state, support tier, and command provenance.
2. Keep the `## Handoff Contract` section explicit and visible.
3. Improve stale-source, hash mismatch, missing metadata, path escape, and
   namespace mismatch diagnostics if gaps are found.
4. Add or refresh focused tests for the Markdown contract.

**Out of scope:**

1. Hidden prompt injection.
2. MCP exposure.
3. `context_compiler` auto-feed.
4. Root export.
5. Semantic correctness claims for arbitrary coding tasks.

**Acceptance criteria:**

1. A valid handoff is self-contained enough for an operator to paste as visible
   agent input.
2. A stale or incomplete handoff fails closed.
3. Tests prove the handoff is stdout-only and read-only.
4. Support docs continue to mark the surface as Beta / explicit handoff only.

## 7. RI-6.3 - Workflow Opt-In Input Contract

**Goal:** Move from manual paste-only handoff toward explicit workflow input,
without hidden runtime injection.

**Proposed model:**

```json
{
  "repo_intelligence_context": {
    "enabled": true,
    "source": "explicit_handoff_file",
    "require_fresh": true,
    "expected_namespace": "repo_chunk::<project_identity>::<embedding_space>::",
    "support_tier": "beta_explicit_handoff"
  }
}
```

**Scope:**

1. Consume a user-provided handoff file or intent field only when explicitly
   enabled.
2. Validate metadata before workflow execution.
3. Record the handoff digest and validation result in evidence.
4. Preserve existing workflows when the option is absent or disabled.

**Out of scope:**

1. Automatic discovery of repo-intelligence artifacts.
2. Automatic prompt injection.
3. MCP tool use.
4. `context_compiler` feed.
5. Real adapter execution.

**Acceptance criteria:**

1. Disabled config is a no-op.
2. Valid explicit config is accepted and recorded.
3. Stale, missing, hash-mismatched, or unknown-namespace context fails closed.
4. Evidence includes context digest and source metadata.
5. Support boundary remains Beta / explicit opt-in.

## 8. RI-6.4 - Deterministic Read-Only Rehearsal Refresh

**Goal:** Prove a local deterministic chain that uses repo-intelligence context
as explicit visible input and produces governed workflow evidence.

**Target chain:**

```text
repo scan / deterministic fixture
-> explicit handoff
-> review_ai_flow with codex-stub
-> review_findings artifact
-> evidence timeline
```

**Acceptance criteria:**

1. No real adapter is called.
2. No remote side effect occurs.
3. No write-side workflow support is implied.
4. Evidence records handoff digest, adapter identity, artifact path, and final
   workflow state.
5. At least one fail-closed rehearsal is recorded.

## 9. RI-6.5 - MCP Read-Only Design Gate

**Goal:** Decide whether a future repo-intelligence MCP tool is worth building.

This phase is design-only by default. Implementation requires a separate issue,
branch, acceptance criteria, and support-boundary update.

**Minimum design questions:**

1. Which exact read-only operation is exposed?
2. Which policy gates apply?
3. How are path escapes, stale artifacts, namespace mismatches, result limits,
   redaction, and source hashes enforced?
4. How does the tool avoid becoming hidden prompt injection?
5. What evidence is emitted for tool calls?

**Default decision unless proven otherwise:**

```text
no MCP repo-intelligence tool
```

## 10. RI-6.6 - Context Compiler Opt-In Design Gate

**Goal:** Decide whether repo-intelligence context should ever feed
`context_compiler`.

This phase is design-only by default. The safe initial position is explicit
workflow input, not compiler auto-feed.

**Minimum design requirements:**

1. Explicit workspace policy enables the feed.
2. Explicit workflow config requests the feed.
3. Context payload validates source hashes and freshness.
4. Compiled output records source provenance.
5. Disabled config is a no-op.
6. Unknown namespace or stale source fails closed.

**Default decision unless proven otherwise:**

```text
no context_compiler auto-feed
```

## 11. Dependency On GPP

Repo-intelligence roadmap work can improve Beta quality independently, but it
cannot create a general-purpose production claim while `GPP-2` is blocked.

`GPP-6` requires a complete read-only chain with protected real-adapter
evidence. That remains blocked until:

1. `ao-kernel-live-adapter-gate` has the selected GitHub App deployment
   protection rule attested;
2. `AO_CLAUDE_CODE_CLI_AUTH` exists as an environment secret handle without
   reading the secret value;
3. a follow-up prerequisite attestation exits `prerequisites_ready`;
4. `GPP-4` provides a production-certified read-only adapter decision or an
   explicit protected beta permission for rehearsal.

## 12. Risk Register

| Risk | Impact | Control |
|---|---|---|
| Hidden prompt injection | False support claim and hard-to-debug context | Explicit opt-in only; negative tests |
| Stale source snippets | Wrong agent guidance | Hash and freshness validation |
| Namespace confusion | Cross-project retrieval leakage | Recorded namespace and project identity checks |
| Root authority corruption | Agent contract drift | Create-only root export stays separate and confirmed |
| MCP tool overreach | Repo intelligence becomes implicit agent memory | Design gate before implementation |
| GPP-2 bypass | False production platform claim | Keep `support_widening=false` and `production_platform_claim=false` |

## 13. Tracking Checklist

- [x] Open tracking issue #499.
- [x] Create dedicated `codex/ri-roadmap-prioritization` branch and worktree.
- [x] Add this written roadmap.
- [x] Validate documentation formatting.
- [x] Run `python3 scripts/gpp_next.py` and confirm `GPP-2` remains blocked.
- [x] Record closeout decision for `RI-6.0`.
- [ ] Open the next implementation/evidence issue only after this roadmap is
      reviewed or merged.

## 14. RI-6.0 Closeout Criteria

This roadmap slice may close when:

1. the roadmap is committed on a dedicated branch;
2. issue #499 links the branch or PR;
3. validation passes;
4. no runtime code is changed;
5. no support boundary is widened;
6. `GPP-2` remains blocked in `scripts/gpp_next.py`.

Expected closeout decision:

```text
repo_intelligence_priority_roadmap_ready_no_support_widening
```

Recorded closeout decision for this slice:

```text
repo_intelligence_priority_roadmap_ready_no_support_widening
```
