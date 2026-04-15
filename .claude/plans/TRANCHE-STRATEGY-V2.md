# Tranche Strategy v2.1.1 — Post-CNS-017 Micro-Revision (2026-04-15)

## Status

- **Baseline:** v3.0.0 LIVE (Tranche C shipped 2026-04-14)
- **Five Codex strategic consultations concluded:**
  - CNS-20260414-013 (niche + priority) — PARTIAL
  - CNS-20260414-014 (build vs integrate) — PARTIAL
  - CNS-20260414-015 (timeline) — DISAGREE
  - CNS-20260414-016 (plan v2 consolidation) — PARTIAL + "dar düzeltme yeter"
  - **CNS-20260414-017** (plan v2.1 narrow verification) — PARTIAL, operational surfaces correct, three mechanical text residuals remain
- **Divergence outcomes (finalized §5):**
  - D1 timeline: **Claude wins** + contingency buffer
  - D2 #8/#9: **Codex wins (partial)** — #8 adopt+wrap, #9 **build** (split)
  - D3 FAZ-C bundle: **Claude wins** — v4.0 = breaking + code intelligence, C0/C1 tracks
  - D4 sandbox: **Codex wins (partial)** — expanded minimum (env/command/cwd allowlist + secret deny-by-default)
- **Next step** — CNS-20260414-018 iter-4 (very narrow, single-pass expected `strategic_commit_ready=true`)

## Revision History

| Version | Date | Scope |
|---|---|---|
| v2.0 | 2026-04-14 | Initial consolidation after CNS-013/014/015 |
| v2.1 | 2026-04-15 | Narrow corrections from CNS-016: D2 split, D4 sandbox expansion, week arithmetic, build-new count, success criteria gates, FAZ-C two-track, competitor matrix gate, head SHA audit |
| **v2.1.1** | 2026-04-15 | **Three mechanical text fixes from CNS-017 NB1/NB2/NB3**: §5 rewritten as "Resolved CNS-016 Divergence Outcomes" (removes stale pre-CNS-016 arguments); §6 week 16 → week 19; §4 integrate 7 → 8 (NEW:metrics-export added), total accounting 39 → 40 |

---

## 1. Niche Position (revised per CNS-013)

**Before (v1):**
> "Governed coding agent orchestration runtime — rakipsiz"

**After (v2):**
> **"Self-hosted, tool-agnostic governance and evidence control-plane for AI coding agents."**

### Rationale

GitHub's 2026-04-14 Copilot cloud agent changelog (third-party Claude/Codex agents with policy enablement, PR/session tracking, MCP, custom agents), Cursor background agents (branch/PR/handoff + Admin API spend), Claude Code enterprise managed settings, Workato enterprise MCP gateway — all converge on the "coding agent orchestration" space. **The niche is not empty.**

**Our defensible differentiator:** self-hosted, vendor-neutral, fail-closed policy + JSONL/SHA256 evidence + canonical memory + CAS write path. Competitors either own the stack vertically (GitHub, Cursor) or sit in one capability slice (LangGraph workflows, Zep memory). ao-kernel stays out of the runtime battle and sits above as the **governance + evidence plane** the others cannot provide honestly.

### Competitor reframe

- **GitHub Copilot cloud agent / Cursor background agents / Codex app / Claude Code** → **adapter targets**, not competitors
- **LangGraph / Temporal / Prefect** → **optional backend adapters** under `[langgraph-compat]`
- **Zep / Letta / Mem0 / Cognee / Graphiti** → **optional memory backends** under `[knowledge-graph]`
- **Workato enterprise MCP** → closest strategic overlap — differentiate via self-host + OSS + code-specific

---

## 2. Five-Phase Roadmap (hybrid: Codex's six-phase compressed)

| Phase | Weeks | PRs | Release | Cumulative week | Core promise |
|---|---|---|---|---|---|
| **FAZ-A** | 8 | 26 | **v3.1.0** | 8 | Governed coding workflow demo (end-to-end: issue → workflow → agent → diff → test → approval → PR → evidence) |
| **FAZ-B** | 4 | 12 | v3.2.0 | 12 | Ops hardening (multi-agent lease/fencing, review AI, cost catalog, policy simulation, metrics export) |
| **FAZ-C** | 7 | 22 | **v4.0.0 breaking** | **19** | Breaking cleanup + code intelligence (two internal tracks: C0 migration, C1 optional code-index/LSP/editing) |
| **FAZ-D** | 5 | 14 | v4.1.0 | 24 | Graph + temporal (#9 native branching, LangGraph adapter for #8, temporal reasoning, evidence-bound KG, cron) |
| **FAZ-E** | 5 | 13 | v4.2.0 | 29 | Enterprise preview (dashboard, SSO, residency, analytics, multi-tenant) |
| **Total** | **29 weeks target** | **87 PR target** | 5 releases | 29 | **+2–4 weeks contingency buffer** (CNS-016 W1: treat estimate as optimistic lower bound, not commitment) |

- **Demo-ready phase:** FAZ-A (week 8)
- **Breaking phase:** FAZ-C (week 19, not week 16 — corrected per CNS-016 B3)
- **FAZ-C release train (CNS-016 W2):** two internal milestones within v4.0.0:
  - **C0** — breaking contract freeze + migration guide + migration tests (must pass before any C1 work merges)
  - **C1** — optional `[code-index]`, `[lsp]`, agentic editing, merge conflict assistant (any failure must not block C0's migration correctness)
- **Migration window:** v3.x compatibility ≥ one minor cycle before v4.0

---

## 3. Feature Inventory — 40 items (30 original + 10 new from CNS-013)

### P0 — FAZ-A (14 items, governed demo MVP)

Claude ranking + CNS-013 re-ordering merged:

| # | Feature | Category | Notes |
|---|---|---|---|
| 22 | Tutorial / onboarding docs | write-lite | Adoption gate — CNS-013 W3 |
| 3 | Intent router + workflow registry | build | Rule-first + `[llm]` fallback |
| 2 | Durable workflow state machine | build | CAS-backed, canonical workflow_state |
| 10 | Human-in-the-loop resumable interrupt | build | P1→P0 per CNS-013 |
| 17 | Approval workflows | build | P1→P0 per CNS-013, shares interrupt primitive with #10 |
| 6 | Diff preview + apply + rollback | build | Governed patch transaction |
| 16 | Patch apply/revert primitive | build | Orchestrated on #6 |
| 5 | Git integration primitives | build | **POSIX git CLI wrapper**, not Python SDK |
| 19 | PR creation / review automation | adopt+wrap | `gh` / `glab` CLI + REST, PyGithub LGPL skipped |
| 7 (thin) | Cost ledger + hard budget cap (fail-closed) | build | Model routing deferred to FAZ-B |
| NEW | Agent adapter contract | build | Claude Code, Codex, Cursor, GitHub cloud agent bridge spec |
| NEW | CI/CD required-check gate | build | GitHub Actions / GitLab CI status, command allowlist |
| NEW | **Worktree execution profile** (demo-tier; CNS-016 D4 expansion) | build | Per-agent worktree + sanitized env allowlist + **secret deny-by-default** (not just redaction) + command allowlist + cwd confinement + evidence redaction. Network/egress OS sandbox (cgroups/firejail/nsjail) deferred to FAZ-B ops hardening. |
| NEW | Evidence query / replay CLI | build | JSONL + SHA256 → timeline, provenance, replay |

**FAZ-A release gate:** one end-to-end demo flow works locally; adapter examples + docs ship together.

### P1 — FAZ-B (9 items, ops hardening)

| # | Feature | Category |
|---|---|---|
| 4 | Multi-agent handoff + capability matrix (lease + fencing token) | build |
| 18 | Code review AI workflow step | write-lite |
| 20 | Commit AI (auto-message) | write-lite |
| 7 (full) | Cost tracking full + price catalog | build |
| 21 | Model routing by cost | build |
| NEW | Policy simulation harness | build |
| NEW | Price catalog + spend ledger | build |
| NEW | Metrics export (Prometheus / OTEL) | integrate (`[metrics]`) |
| NEW | Agent benchmark / regression suite | build |

### P1 — FAZ-C (7 items, breaking + code intelligence)

| # | Feature | Category |
|---|---|---|
| — | **Breaking:** CAS `allow_overwrite` default flip | build |
| — | **Breaking:** `save_store` removal | build |
| — | **Breaking:** Workflow state schema stabilization | build |
| — | **Breaking:** HITL interrupt API stabilization | build |
| — | **Breaking:** Diff/apply contract stabilization | build |
| — | **Breaking:** MCP tool envelope cleanup | build |
| 1 | Repository code indexing (tree-sitter) | integrate (`[code-index]`) |
| 14 | LSP integration | integrate (`[lsp]`) |
| 15 | Cross-file reference tracking | integrate (`[code-index]`) |
| 11 | LLM-driven multi-file coherent edits | adopt+wrap (Aider patterns) |
| 12 | Agentic file editing (plan→apply→verify) | adopt+wrap |
| 28 | Merge conflict resolution workflow | write-lite |
| 23 | On-prem / air-gapped hardening | write-lite |
| 26 | Compliance report generator | write-lite |

### P1 — FAZ-D (5 items, graph + temporal)

| # | Feature | Category | Note |
|---|---|---|---|
| 8 | Agent graph execution | **adopt+wrap** (LangGraph import adapter + thin custom-lite fallback) | CNS-016 D2: #8 stays adopt+wrap |
| 9 | Conditional branching | **build** | CNS-016 D2 (Codex wins): native deterministic predicates + branch evidence + replay determinism + fail-closed semantics are core governance contracts, not delegable to external runtime |
| 13 | Temporal reasoning over evidence/workflows | build | Native facts with valid_at/invalid_at/observed_at |
| 27 | Knowledge graph (evidence-bound) | integrate (`[knowledge-graph]` Graphiti) | |
| NEW | Cron / scheduled workflows | build | |

### P2 — FAZ-E (5 items, enterprise preview)

| # | Feature | Category |
|---|---|---|
| 24 | Web dashboard | integrate (`[dashboard]` Starlette + HTMX) |
| 25 | SSO / OIDC (`[sso]` Authlib) + `[saml]` separate | integrate |
| 29 | Data residency policies | build |
| 30 | Team analytics | integrate (`[metrics]` export + dashboard view) |
| NEW | Multi-tenant isolation + backup/DR + retention/legal hold | build |

---

## 4. Build vs Integrate Matrix (revised per CNS-014 + CNS-016 + CNS-017)

| Category | Count | Feature IDs |
|---|---|---|
| **Build** (niche core) | 13 + 9 NEW = **22** | Original: #2, #3, #4, #5, #6, #7, #9 (CNS-016 D2 moved from adopt), #10, #13, #16, #17, #21, #29. NEW: adapter-contract, CI/CD-gate, worktree-execution-profile, evidence-CLI, policy-sim, price-catalog, agent-benchmark, multi-tenant, cron-workflows |
| **Integrate** (OSS extras) | 7 + 1 NEW = **8** | #1 (tree-sitter), #14 (pygls), #15 (SCIP), #24 (Starlette/HTMX), #25 (Authlib), #27 (Graphiti), #30 (prometheus-client) + NEW:metrics-export (prometheus-client / OTEL mapping under `[metrics]`) |
| **Adopt + Wrap** (ecosystem) | 4 | #8 (LangGraph import adapter only), #11 / #12 (Aider patterns), #19 (gh/glab CLI + REST) |
| **Write-Lite** (docs/thin) | 6 | #18 review AI, #20 commit AI, #22 docs, #23 hardening, #26 compliance report, #28 merge conflict |
| **Total accounting** | **22 + 8 + 4 + 6 = 40** | 30 original + 10 NEW = 40 items, fully accounted (CNS-017 NB3 fix) |

### Extras posture

- **Core dep unchanged:** `jsonschema>=4.23.0`
- **Existing extras kept:** `[llm]`, `[mcp]`, `[mcp-http]`, `[otel]`, `[pgvector]`, `[dev]`
- **New extras:** `[code-index]`, `[lsp]`, `[dashboard]`, `[metrics]`, `[sso]`, `[saml]` (separate, security review), `[knowledge-graph]`, `[langgraph-compat]`, `[vcs-github]` (REST + CLI), `[vcs-gitlab]` (REST + CLI)
- **Meta-extras:** `[coding]` = `[llm]+[code-index]+[lsp]+[metrics]`; `[enterprise]` = `[otel]+[metrics]+[dashboard]+[sso]+[pgvector]`; `[all]` = CI / maintainer smoke only
- **Rejected:** `[git]` (use system git CLI), `[routing]` (core router data), direct PyGithub/python-gitlab default (LGPL)

---

## 5. Resolved CNS-016 Divergence Outcomes

**Four pre-CNS-016 divergences have been adjudicated. This section records the final outcome (not the historical argument). §3, §4, §10 are the authoritative operational surfaces.**

### Outcome 1 — Timeline estimate: **Claude wins (D1)**

**Final:** 87 PR / 29 weeks target + **2-4 weeks contingency buffer** (§2 footer).
- Codex accepted: "defensible but treat as optimistic lower bound, not commitment"
- Basis: Tranche C pattern maturity + ao-kernel ~40% scaffolding + primitive merging (#10+#17, #6+#16)
- Watch: if FAZ-A golden-path demo/adapter/evidence CLI doesn't ship by week 2-3, revise buffer to +4-6 weeks (CNS-017 Q7)

### Outcome 2 — #8 vs #9: **Codex wins (partial) — split**

**Final:** #8 adopt+wrap, **#9 build** (see §3 FAZ-D table, §4 matrix).
- **#8 agent graph execution** → `[langgraph-compat]` adopt+wrap (LangGraph import adapter + thin custom-lite fallback). ao-kernel avoids graph-runtime competition.
- **#9 conditional branching** → **build** (native deterministic predicates + branch decision evidence + replay determinism + fail-closed semantics). Policy-visible branch behaviour cannot be delegated to an external runtime.
- Release gate (§10 FAZ-D): "branch predicate evidence + replay determinism" test.

### Outcome 3 — FAZ-C bundle: **Claude wins (D3)**

**Final:** v4.0.0 = breaking cleanup **and** code intelligence bundle, with **two internal tracks**:
- **C0 (release blocker):** breaking contract freeze + migration guide + migration tests verified
- **C1 (optional payload):** `[code-index]`, `[lsp]`, agentic editing, merge conflict assistant; **any C1 failure must NOT block C0 migration correctness**
- Rationale Codex accepted: major release carries migration expectation naturally; bundling avoids a value-less standalone "just removes deprecated APIs" release.

### Outcome 4 — Sandbox profile: **Codex wins (partial) — expanded minimum**

**Final:** FAZ-A P0 **"worktree execution profile"** with the full CNS-016-prescribed minimum:
- Per-agent worktree ✓
- Sanitized env allowlist ✓
- **Secret deny-by-default** (not just redaction) ✓
- Command allowlist ✓
- CWD confinement ✓
- Evidence redaction ✓
- **Deferred to FAZ-B:** OS-level network/egress sandboxing (cgroups / firejail / nsjail) — multi-OS surface
- Release gate (§10 FAZ-A): env/command/cwd violation tests + secret deny-by-default test

---

## 6. Accepted from Codex (no divergence)

1. Niche cumlesi revize: **"Self-hosted governance control-plane for coding agents"**
2. Code indexing P0 → P1 optional extra (`[code-index]`)
3. Docs (#22) P0 adoption gate
4. HITL (#10) + Approval (#17) P0
5. LangGraph parity dropped; import/export adapter only
6. v4.0 breaking early (FAZ-C end, **week 19**) — not delayed to graph phase
7. POSIX git CLI wrapper for #5 (not pygit2 GPLv2 or GitPython maintenance mode)
8. WRITE-LITE count grew to 6 (#18, #20, #22, #23, #26, #28)
9. `[coding]` + `[enterprise]` meta-extras
10. Competitor matrix as live doc (not marketing hype "rakipsiz")

---

## 7. Demo Flow (FAZ-A acceptance)

Single end-to-end dogfood flow must pass before v3.1.0 ship:

```
1. issue / spec (markdown file or GitHub issue URL)
2. ao-kernel intent router → selects BUG_FIX_FLOW
3. workflow state machine starts (run_id, checkpoint persisted)
4. context compiler compiles: canonical decisions + session transcript + workspace facts
5. adapter calls external agent (Claude Code CLI example)
6. agent returns proposed change
7. diff preview generated
8. CI gate runs (tests + lint)
9. human approval (gate)
10. git commit + PR creation via gh CLI
11. evidence CLI can replay the entire flow: `ao-kernel evidence timeline --run <id>`
```

If any step cannot be demoed locally, FAZ-A is not done.

---

## 8. Breaking Cleanup Checklist (FAZ-C)

- [ ] `canonical_store.save_store` removed (deprecated in v3.0.0)
- [ ] `promote_decision` `allow_overwrite=False` default flip
- [ ] `save_store_cas` becomes the only public write path
- [ ] Workflow state schema v1 → locked as contract (no additive changes without migration)
- [ ] HITL interrupt API `resume(token, payload)` signature locked
- [ ] Diff/apply contract (envelope, diff-id, revert chain) locked
- [ ] MCP tool envelope: deprecated fields removed, `api_version` enum tightened
- [ ] `policy_mcp_tool_calling.v1.json` subfields `implicit_canonical_promote` required when enabled (currently optional)

Migration guide: CHANGELOG.md `[4.0.0]` section, per-item before/after examples.

---

## 9. Risk Register

| Risk | Level | Mitigation |
|---|---|---|
| **Scope creep** (40 items) | Orta | P2'nin yarısını v5+'ya ertele (CNS-013 önerisi: #27, #28, #30 v5+) |
| **LangGraph API churn** | Orta | Adapter sınırlı yüzey (import/export only), kendi custom-lite fallback |
| **Market speed** (GitHub / Cursor hareketi) | Orta | Self-hosted + policy niche zaman içinde değerlenir; 7 ay kabul edilebilir |
| **Adoption** (docs + adapter örnekleri) | Yüksek | Docs FAZ-A P0 (CNS-013 W3) |
| **Ecosystem drift** (Zep deprecated → Graphiti) | Düşük | `[knowledge-graph]` extras explicit, backend swap mümkün |
| **Binary wheel / license** (tree-sitter, pgvector) | Düşük | Optional extras, POSIX-only contract, constraints lock + pip-audit CI |
| **Breaking migration burden** | Düşük | Early (FAZ-C) + per-item migration guide |
| **Codex divergence wrong** (4 points) | Orta | CNS-016 iter-2 adversarial verify |

---

## 10. Success Criteria

### FAZ-A (v3.1.0)
- [ ] End-to-end demo flow passes locally
- [ ] 3 adapter examples work: Claude Code, Codex (stub/CLI), gh CLI PR path (CNS-016 Q10)
- [ ] Docs published: tutorial + 3 adapter walkthroughs
- [ ] `ao-kernel evidence timeline` CLI works
- [ ] Worktree execution profile test: env allowlist violation denied, command allowlist violation denied, cwd escape denied, secret deny-by-default enforced (CNS-016 Q11)
- [ ] CI gate deny/allow fixture test: policy-allowed status passes, policy-denied status blocks merge (CNS-016 Q11)
- [ ] **Competitor / adapter matrix live doc published** (README or docs/COMPETITOR-MATRIX.md) — prevents "rakipsiz" regression (CNS-016 W3)
- [ ] 1000+ tests green; coverage ≥ 85%

### FAZ-B (v3.2.0)
- [ ] Governed review + governed bugfix benchmarks pass
- [ ] Cost cap fail-closed test: budget exceeded → deny + audit
- [ ] Policy simulation reports deny/allow diff for fixture changes
- [ ] Metrics export visible in Prometheus + Grafana dashboard
- [ ] **Lease/fencing race test** (CNS-016 Q11): two concurrent agents, one owns claim, second receives `CLAIM_CONFLICT` with fencing_token, expired claim takeover works
- [ ] Pre-FAZ-B design note for #4 lease/fencing (mini-CNS or inline spec): `claim_id, owner_agent_id, fencing_token, expires_at, heartbeat, takeover, CAS expected_revision, evidence event` (CNS-016 additional recommendation)

### FAZ-C (v4.0.0) — two-track release (CNS-016 W2)
**C0 track (blocks release):**
- [ ] All breaking items checklisted (§8) green
- [ ] v3.x migration guide published
- [ ] **Migration guide examples verified by tests** (CNS-016 Q11): each migration example has a passing before/after test

**C1 track (optional payload, does NOT block C0):**
- [ ] Code index `ao-kernel[code-index]` works offline
- [ ] LSP `ao-kernel[lsp]` integration ships one adapter example
- [ ] Agentic editing flow demonstrable on a sample repo
- [ ] Merge conflict assistant workflow step exercised

### FAZ-D (v4.1.0)
- [ ] LangGraph import/export roundtrip lossless (for #8)
- [ ] **Native #9 branch replay test** (CNS-016 Q11): deterministic predicate evidence + replay/dry-run produces identical branch decisions across runs
- [ ] Temporal queries over evidence ≥ 10 example queries
- [ ] Cron workflow runs nightly dependency review

### FAZ-E (v4.2.0)
- [ ] Dashboard deployed in Docker compose example
- [ ] SSO + multi-tenant demo passes enterprise evaluation checklist
- [ ] Data residency policy enforced per-workspace

---

## 11. Next Steps (post v2.1)

1. **User review of plan v2.1** — accept / revise
2. **CNS-20260414-017 iter-3** — narrow verification of CNS-016's three blocking corrections and four warnings (expected single-pass `strategic_commit_ready=true`)
3. **Pre-FAZ-A:** mini-CNS or design note for #4 multi-agent lease/fencing (CNS-016 additional recommendation; before FAZ-B starts)
4. **Begin FAZ-A PR-A0** — docs + adapter contract spec (not code first per CNS-016 additional recommendation)
5. **P0 tracker** — manage as 6 workstreams (adoption docs, workflow core, governed change, VCS/PR, safety/cost, evidence replay), not 14 individual IDs (CNS-016 Q6)

## 12. Audit Trail (CNS-016 housekeeping)

| Field | Value |
|---|---|
| request_head_sha (CNS-013/014/015/016) | `7b44822` |
| observed_head_sha at CNS-016 response | `315b205` |
| v2.1 target branch | `main` (post-v3.0.0) |
| Strategic commit target SHA | to be pinned at FAZ-A PR-A0 branch |

**Note (CNS-016 W4):** Response `head_sha` ≠ request `head_sha`. `315b205` was the local worktree state at Codex's inspection. No material drift in scoped files; both SHAs recorded here for traceability.

---

**Status:** DRAFT v2.1, awaiting user approval before CNS-017 iter-3 submission.
