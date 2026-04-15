# Competitor / Adapter Matrix

This is a living document. It maps ao-kernel's position against adjacent platforms and lists the integration status of each as an adapter target. The matrix exists because "rakipsiz" (no competitor) is factually wrong and sustainably misleading — the coding-agent-orchestration space is crowded. ao-kernel's differentiator is narrower and more durable than the claim of being alone.

Last updated: 2026-04-15 (PR-A0 — initial). Review cadence: one refresh per phase ship (FAZ-A, FAZ-B, FAZ-C, FAZ-D, FAZ-E).

---

## 1. Purpose

The matrix does three things:

1. **Forces honesty in positioning.** Every entry names a real product and says where it overlaps.
2. **Drives adapter priority.** Platforms in the top section of the matrix are adapter targets (we plug into them); platforms in the lower section are comparison-only (we compete with them at a conceptual level but don't integrate).
3. **Guards against scope drift.** If a new feature duplicates what an existing entry already does well, the feature needs a written differentiator or gets cut.

### ao-kernel's defensible niche

> **"Self-hosted, tool-agnostic governance and evidence control-plane for AI coding agents."**

The durable moat is the combination of: self-hosted · vendor-neutral · fail-closed policy · JSONL/SHA-256 evidence · canonical memory · CAS write path. Competitors own one or two of these (or own none and aim at a different layer of the stack).

---

## 2. Matrix

| Platform | Category | Overlap with ao-kernel | Our Differentiator | Adapter Status |
|---|---|---|---|---|
| **GitHub Copilot cloud agent** | Coding agent runtime (SaaS, managed) | Agent orchestration with policy and session tracking | Self-hosted, vendor-neutral, no cloud lock-in; policy-first fail-closed | Planned (FAZ-A) |
| **Cursor background agents** | IDE + cloud orchestration | Branch, PR, session handoff, admin spend controls | JSONL evidence + CAS canonical memory; open-source governance surface | Planned (FAZ-A) |
| **Claude Code enterprise** | CLI agent + managed settings | Enterprise settings governance | JSON-schema contracts + replay-deterministic policy gates | Planned (FAZ-A demo) |
| **OpenAI Codex app** | Coding agent | Agent orchestration | Open source + policy SSOT; self-hosted memory and evidence | Planned (FAZ-A stub) |
| **Workato enterprise MCP gateway** | Enterprise MCP governance | Tool gateway + policy | Self-host + OSS + code-specific (Workato is enterprise integration-wide) | Comparison only (strategic overlap, not an adapter target) |
| **LangGraph** | Python graph workflow library | Workflow definition + state machine | Governance-first + replay-deterministic predicates (FAZ-D native #9 branching); optional backend via `[langgraph-compat]` | Optional backend (FAZ-D) |
| **Temporal / Prefect** | Durable workflow engines | Durable state + retry | Policy + evidence + memory baked in, not bolted on | Out of scope |
| **Zep / Letta / Mem0 / Graphiti** | Agent memory backends | Canonical memory, temporal queries | CAS write path, fail-closed promotion, evidence-bound; optional integration via `[knowledge-graph]` | Optional backend (FAZ-D) |
| **Aider / Sweep / Devin / windsurf-cascade** | Coding agent (full-stack) | Agent runtime | Control-plane, not runtime: we sit above these and govern them | Comparison only (route via `custom-cli` / `custom-http` if adapter support is requested) |

---

## 3. Adapter Status Taxonomy

Each entry in the matrix carries a status tag from this closed set:

| Status | Meaning | Action |
|---|---|---|
| `planned` | Target for an upcoming phase. | Adapter contract exists or is being written. Demo adapter example ships with the phase release. |
| `prototype` | Working in-repo example; not on a stability contract. | Useful for demos; not recommended for production. |
| `shipped` | Production-ready adapter; contract is stable; version pinned. | Supported across minor releases until a breaking change ships with a major. |
| `blocked` | Integration wanted, but a platform-side gap blocks it. | Documented blocker; watched until unblocked. |
| `comparison-only` | Named in the matrix for positioning clarity; no adapter is planned. | Mention in docs, do not build. |
| `out of scope` | Explicitly rejected as an integration target. | Direct users elsewhere. |

The current state of every entry is in the rightmost column of §2.

---

## 4. Positioning Rules

The following rules prevent the matrix from drifting into marketing:

1. **Every entry must name a real product** with a URL reference in the source tracker (maintained out of this doc to keep it markdown-clean).
2. **Overlap column must be specific.** Not "ai features" or "agents" — name the capability that genuinely overlaps (session tracking, branch creation, memory store).
3. **Differentiator column must be falsifiable.** "Better" is not a differentiator; "self-hosted" and "CAS write path" are.
4. **No claims of being alone.** If ao-kernel genuinely has no competitor in a sub-area, that area is probably too narrow to ship yet.
5. **Adapter status changes are governance events.** Moving from `planned` → `shipped` requires a merged adapter in the repo and a walkthrough in [docs/ADAPTERS.md](ADAPTERS.md).

---

## 5. Update Cadence

| Trigger | Action |
|---|---|
| FAZ-A ship (v3.1.0) | Update adapter status for Claude Code CLI, Codex stub, gh CLI PR path, GitHub Copilot cloud, Cursor bg. |
| FAZ-B ship (v3.2.0) | Update any changes from ops hardening (metrics, policy sim) that shift differentiator claims. |
| FAZ-C ship (v4.0.0) | Review breaking migration implications on published adapters. Review `[code-index]` vs tree-sitter competitors. |
| FAZ-D ship (v4.1.0) | Update LangGraph, Zep/Letta/Mem0/Graphiti integration status (`[langgraph-compat]`, `[knowledge-graph]`). |
| FAZ-E ship (v4.2.0) | Update enterprise-preview entries (dashboard, SSO, multi-tenant) against competing enterprise offerings. |
| Any new bundled adapter merges | Move its status to `shipped` and add walkthrough to ADAPTERS.md. |
| Any competitor launches a feature that collapses an overlap column into equivalence | Revise the differentiator or acknowledge parity. |

---

## 6. Rejected Rows (for the record)

The following were considered and explicitly excluded from the matrix, with reasons. These should not be re-added without a new competitive-analysis write-up:

| Rejected | Reason |
|---|---|
| ChatGPT Code Interpreter | Different primitive (sandbox Python REPL), not a coding agent orchestrator. |
| GitHub Actions | General CI/CD; ao-kernel's CI gate invokes it, not competes with it. |
| Jupyter / VS Code extensions | Editor surface, not orchestration. |
| Replit AI | IDE-bound, not self-hostable, different audience. |
| AutoGPT / BabyAGI | Early-generation autonomous agents; not coding-specific; largely dormant. |

---

## 7. Cross-References

- [docs/ADAPTERS.md](ADAPTERS.md) — adapter contract and walkthroughs for the `planned` / `shipped` entries above.
- [docs/DEMO-SCRIPT.md](DEMO-SCRIPT.md) — the FAZ-A demo flow that exercises Claude Code CLI / codex-stub / gh-cli-pr adapters.
- [docs/WORKTREE-PROFILE.md](WORKTREE-PROFILE.md) — the sandbox each adapter runs inside.
- `.claude/plans/TRANCHE-STRATEGY-V2.md` §1, §4 — the niche statement and build-vs-integrate classification that pin the positioning.
