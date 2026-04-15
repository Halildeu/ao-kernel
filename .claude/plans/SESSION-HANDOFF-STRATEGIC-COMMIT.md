# Session Handoff — Strategic Plan v2.1.1 Committed (2026-04-15)

## TL;DR

**v3.0.0 LIVE. Tranche C closed. Strategic pivot complete. Plan v2.1.1 committed with `strategic_commit_ready=true`. Next session opens PR-A0 (docs + adapter contract spec) as the first deliverable of FAZ-A.**

---

## What Happened This Session

1. **Tranche C shipped** (v3.0.0 live, 17 PRs merged, 1004 tests, 85% coverage, PyPI published)
2. **Strategic pivot analysis** — Claude proposed a pivot to "governed coding agent orchestration runtime"
3. **Six adversarial Codex consultations** resolved the pivot:
   - CNS-20260414-013 (niche + priority) — PARTIAL
   - CNS-20260414-014 (build vs integrate) — PARTIAL
   - CNS-20260414-015 (timeline) — DISAGREE
   - CNS-20260414-016 (plan v2 consolidation) — PARTIAL
   - CNS-20260414-017 (plan v2.1 narrow verification) — PARTIAL
   - CNS-20260414-018 (plan v2.1.1 micro verification) — **AGREE + `strategic_commit_ready=true`**
4. **Plan v2.1.1 written** and committed: `.claude/plans/TRANCHE-STRATEGY-V2.md`
5. **Total adversarial stats:** 20 blocking + 20 warning absorbed across 6 CNS, ~70 questions, ~6 hours of Codex time

## Final Strategic Position (locked)

### Niche

> **"Self-hosted, tool-agnostic governance and evidence control-plane for AI coding agents"**

Competitors reframed as adapter targets: GitHub Copilot cloud agent, Cursor background agents, Claude Code enterprise, OpenAI Codex app, Workato enterprise MCP.

### Roadmap — 5 Phases, 29 Weeks Target (+2-4 weeks contingency), 87 PR Target

| Phase | Weeks | PR | Release | Focus |
|---|---|---|---|---|
| **FAZ-A** | 8 (cum 8) | 26 | **v3.1.0** | Governed demo MVP (uçtan uca akış: issue → workflow → agent → diff → test → approval → PR → evidence) |
| **FAZ-B** | 4 (cum 12) | 12 | v3.2.0 | Ops hardening (multi-agent lease/fencing, cost catalog, policy simulation, metrics export) |
| **FAZ-C** | 7 (cum 19) | 22 | **v4.0.0 breaking** | Two internal tracks: **C0** breaking cleanup + migration; **C1** optional code-index / LSP / editing |
| **FAZ-D** | 5 (cum 24) | 14 | v4.1.0 | Graph + temporal (#8 adopt, #9 build split; temporal reasoning; KG) |
| **FAZ-E** | 5 (cum 29) | 13 | v4.2.0 | Enterprise preview (dashboard, SSO, residency, analytics, multi-tenant) |

### Feature Inventory — 40 Items (30 original + 10 new from CNS-013)

- **Build (niche core): 22** — 13 original (#2, #3, #4, #5, #6, #7, #9, #10, #13, #16, #17, #21, #29) + 9 NEW (adapter-contract, CI/CD-gate, worktree-execution-profile, evidence-CLI, policy-sim, price-catalog, agent-benchmark, multi-tenant, cron-workflows)
- **Integrate (OSS extras): 8** — #1 tree-sitter, #14 pygls, #15 SCIP, #24 Starlette, #25 Authlib, #27 Graphiti, #30 prometheus-client, NEW:metrics-export
- **Adopt + Wrap (ecosystem): 4** — #8 LangGraph import adapter, #11 / #12 Aider patterns, #19 gh/glab CLI + REST
- **Write-Lite (docs/thin): 6** — #18 review AI, #20 commit AI, #22 docs, #23 hardening, #26 compliance report, #28 merge conflict

### Four Divergence Outcomes (finalized §5 of plan v2.1.1)

| ID | Topic | Winner | Final |
|---|---|---|---|
| D1 | 87 PR / 29 weeks | **Claude** | +2-4 weeks contingency buffer |
| D2 | #8/#9 category | **Codex (partial)** | #8 adopt+wrap; #9 build (split) |
| D3 | FAZ-C bundle | **Claude** | v4.0 = breaking + code intelligence, C0/C1 tracks |
| D4 | Sandbox profile | **Codex (partial)** | Expanded minimum (env + command + cwd allowlist + secret deny-by-default) |

### New Extras Posture (core dep unchanged: `jsonschema>=4.23.0`)

- `[code-index]`, `[lsp]`, `[dashboard]`, `[metrics]`, `[sso]`, `[saml]` (separate, security review), `[knowledge-graph]`, `[langgraph-compat]`, `[vcs-github]`, `[vcs-gitlab]`
- Meta-extras: `[coding]` = `[llm]+[code-index]+[lsp]+[metrics]`; `[enterprise]` = `[otel]+[metrics]+[dashboard]+[sso]+[pgvector]`
- Rejected: `[git]` (use system git CLI); `[routing]` (core data)

---

## Next Session — First Deliverable: PR-A0

**Start here.** PR-A0 is docs + spec only, not code.

### PR-A0 Scope (adoption gate foundation)

1. **Agent adapter contract spec** — `docs/ADAPTERS.md` + `ao_kernel/defaults/schemas/agent-adapter-contract.schema.v1.json`
2. **Workflow run schema** — `ao_kernel/defaults/schemas/workflow-run.schema.v1.json`
3. **Evidence timeline contract** — `docs/EVIDENCE-TIMELINE.md`
4. **Worktree execution profile spec** — `docs/WORKTREE-PROFILE.md` + `ao_kernel/defaults/policies/policy_worktree_profile.v1.json`
5. **Demo acceptance script** — `docs/DEMO-SCRIPT.md` (issue → workflow → agent → diff → test → approval → PR → evidence)
6. **Competitor / adapter matrix live doc** — `docs/COMPETITOR-MATRIX.md`

### Quick-Start (Next Session)

```bash
# 1. Verify state
cd /Users/halilkocoglu/Documents/ao-kernel
git log -1 --format="%h %s"           # 7b44822 or newer (release v3.0.0)
python3 -m pytest --co -q | tail -1   # 1004 tests
gh pr list --state open --limit 3     # strategic plan PR
ls .claude/plans/TRANCHE-STRATEGY-V2.md

# 2. Read the plan
cat .claude/plans/TRANCHE-STRATEGY-V2.md

# 3. Read the handoff (this doc)
cat .claude/plans/SESSION-HANDOFF-STRATEGIC-COMMIT.md

# 4. Open PR-A0
git fetch origin main --quiet
git checkout -b claude/faz-a-pr-a0 origin/main
# implement: docs/spec only, no code
```

### P0 Tracker — 6 Workstreams (not 14 items — CNS-016 Q6)

1. **Adoption docs** — #22 tutorial/onboarding + competitor matrix
2. **Workflow core** — #2 state machine + #3 intent router + workflow registry
3. **Governed change** — #6 + #16 unified diff/patch engine; #10 + #17 unified interrupt/approval primitive
4. **VCS + PR** — #5 git CLI + #19 gh/glab
5. **Safety + cost** — worktree profile + cost ledger thin + CI gate
6. **Evidence replay** — evidence CLI

### FAZ-A Release Gates (v3.1.0 ship criteria)

- [ ] End-to-end demo flow passes locally
- [ ] 3 adapter examples work: Claude Code, Codex (stub/CLI), gh CLI PR path
- [ ] Docs published: tutorial + 3 adapter walkthroughs
- [ ] `ao-kernel evidence timeline` CLI works
- [ ] Worktree profile test: env/command/cwd violations denied, secret deny-by-default enforced
- [ ] CI gate deny/allow fixture test
- [ ] **Competitor / adapter matrix live doc published**
- [ ] 1000+ tests green; coverage ≥ 85%

---

## Key Invariants (do not regress)

### From v3.0.0 (Tranche C)

- `ao_kernel/_internal/shared/lock.py::file_lock` POSIX-only
- `canonical_store._mutate_with_cas` = only canonical write path
- `workspace.project_root()` = directory containing `.ao/`, not `.ao` itself
- `ToolSpec.allowed=True` + handler-level deny envelope
- `_resolve_workspace_for_call` fallback = key-absent only
- `_IMPLICIT_PROMOTE_SKIP = {ao_memory_read, ao_memory_write}`
- MCP evidence = JSONL + fsync (no manifest — workspace artefacts only)
- `_SERVER_SIDE_CONFIDENCE = 0.8` (caller ignored)

### From strategic plan v2.1.1 (FAZ-A onward)

- **Core dep invariant:** only `jsonschema>=4.23.0`; all new packages live in extras under lazy import
- **#9 conditional branching MUST be build** (not delegable; deterministic predicates + branch evidence + replay)
- **Sandbox P0 minimum:** worktree + env allowlist + secret deny-by-default + command allowlist + cwd confinement + evidence redaction (network/egress FAZ-B)
- **#8 agent graph** = LangGraph import adapter only under `[langgraph-compat]`; no runtime dependency
- **FAZ-C release policy:** C0 migration correctness blocks release; C1 optional payload failure does NOT
- **Docs-first:** PR-A0 is docs + spec, not code
- **P0 tracked as 6 workstreams**, not 14 individual feature IDs

---

## Audit Trail

- Plan location: `.claude/plans/TRANCHE-STRATEGY-V2.md` (v2.1.1)
- Consensus docs:
  - `.ao/consultations/CNS-20260414-010.consensus.md` (Tranche C plan)
  - `.ao/consultations/CNS-20260414-011.consensus.md` (C6a impl)
  - `.ao/consultations/CNS-20260414-012.consensus.md` (C6b impl)
  - No consolidated consensus doc for 013–018 yet — request/response files are the source of truth
- Request/response pairs: `.ao/consultations/requests/CNS-20260414-{013..018}.request.v1.json`, `.ao/consultations/responses/CNS-20260414-{013..018}.codex.response.v1.json`
- Release target branch: `main`
- Head SHA at strategic commit: `7b44822` (v3.0.0 merge commit)
- Observed SHA at CNS-018 response: `315b205` (local worktree state, not material drift)

---

## Adversarial Consensus Track Record (Tranche C + Strategic Pivot)

| CNS | Topic | Iterations | Blocking | Warning | Final |
|---|---|---|---|---|---|
| 010 | Tranche C master plan | 3 | 10 | 7 | AGREE |
| 011 | PR-C6a implementation | 3 | 5 | 9 | AGREE |
| 012 | PR-C6b implementation | 2 | 1 | 6 | AGREE |
| 013 | Strategic niche + priority | 1 | 5 | 5 | PARTIAL |
| 014 | Build vs integrate matrix | 1 | 4 | 5 | PARTIAL |
| 015 | Quick Win Timeline | 1 | 5 | 5 | DISAGREE |
| 016 | Plan v2 consolidation | 1 | 3 | 4 | PARTIAL |
| 017 | Plan v2.1 narrow verification | 1 | 3 | 1 | PARTIAL |
| **018** | **Plan v2.1.1 micro verification** | **1** | **0** | **0** | **AGREE ✅** |

**Grand total:** 9 CNS, 14 iterations, 36 blocking absorbed, 42 warning absorbed, Claude's first-shot thesis survived 0/9 times.

---

**Status:** Plan v2.1.1 committed and `strategic_commit_ready=true`. Next session opens PR-A0.
