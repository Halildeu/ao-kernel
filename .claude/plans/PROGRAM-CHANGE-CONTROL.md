# Program Change Control Policy

> **Status:** active normative policy (GOV-1)
> **Scope:** General-Purpose Production Promotion program + all SSOT artifacts
> **Authority:** `origin/main`
> **Schema:** `.claude/plans/gpp_status.v1.json`
> **Last reviewed:** 2026-05-25

## Purpose

This document formalizes the change-control rules that previously lived as
HARD RULES in chat memory and user-level CLAUDE.md instructions. It exists so
that any agent or operator starting cold can read the contract for how the
program evolves and what is forbidden.

## Rules

### CC-1 — SSOT mutation only via PR

- **Rule:** `.claude/plans/gpp_status.v1.json`, `GENERAL-PURPOSE-PRODUCTION-PROMOTION-STATUS.md`, and any other governance SSOT may only change through a merged PR; direct edits on `main` are forbidden.
- **Why:** Direct edits skip cross-AI review, CI, and audit trail.
- **Evidence:** Every SSOT change has an associated PR + squash merge + archive tag.

### CC-2 — Cross-AI peer review

- **Rule:** The implementer AI provider MUST differ from the reviewer AI provider (e.g. Anthropic implementer ↔ OpenAI reviewer). Same-session, same-thread, or same-provider double-review is invalid.
- **Why:** Bias isolation; one-provider review reproduces the same blind spots.
- **Evidence:** `local-ai-review-evidence.v1.json` records `implementer.provider` and `reviewer.provider` and the gate fails closed when they match.

### CC-3 — Non-author code-owner approval

- **Rule:** Merge requires at least one non-author code-owner approval (e.g. `gladyatore-lab`); self-approval is invalid.
- **Why:** Mechanical separation between implementer and merger.
- **Evidence:** GitHub branch ruleset `required_pull_request_reviews` + `dismiss_stale_reviews`; per-PR `gh pr view --json reviewDecision`.

### CC-4 — No `--admin` merge

- **Rule:** `gh pr merge --admin` is forbidden. CI red ⇒ fix, not bypass.
- **Why:** Admin bypass invalidates the required-check gate; sets a precedent that erodes governance.
- **Evidence:** Each merge log shows normal squash; archive tag carries the un-bypassed commit history.
- **Exception:** Only a critical production outage with explicit operator declaration + same-day follow-up PR. Pre-production: no exception.

### CC-5 — AI output is evidence, not release authority

- **Rule:** Claude / Codex / any AI output is consulted as advisory evidence; release authority lives in `ao-release-gate` (required status check) + branch ruleset + non-author approval.
- **Why:** Models hallucinate, drift, and are not accountable; humans + verified gates are.
- **Evidence:** `forbidden_actions` includes `treat Codex or Claude output as release authority`; reviewer evidence schema constrains `verdict ∈ {AGREE, REVISE, BLOCK}` as input, not a merge token.

### CC-6 — Guard flag flips require explicit GPP-9 decision

- **Rule:** `support_widening_allowed`, `production_platform_claim_allowed`, and `live_adapter_execution_allowed` may only flip to `true` as part of an explicit GPP-9 promotion decision PR that updates docs, support boundary, known bugs, runbook, examples, and release notes in the same change.
- **Why:** The three flags are the program's contract with downstream users; flipping any one of them without the full promotion package is a fake-work pattern.
- **Evidence:** `forbidden_actions` includes the corresponding lines; pytest drift guards pin all three to `false`.

### CC-7 — ADR / decision-record supersession protocol

- **Rule:** A decision recorded in `.claude/plans/GP-*.md` or `.claude/plans/GPP-*.md` is **never edited in place** to reverse its meaning. Reversal requires a new decision record that names the superseded record and the reason; the original stays as audit trace.
- **Why:** Decision history is part of compliance and program continuity.
- **Evidence:** Closeout records explicitly use a `## Supersession / Reconciliation` section; old records keep their decision string verbatim.

### CC-8 — SSOT schema bump rule

- **Rule:** `gpp_status.v1.json` `schema_version` stays `"1"` as long as additions are non-breaking (new optional fields). A breaking change (renamed/removed required field, type change) requires a new file `gpp_status.v2.json` + reader compatibility plan; consumers must accept both during transition.
- **Why:** Avoid silent schema drift; preserve replay-ability of historical artifacts.
- **Evidence:** Drift-guard test pins `schema_version == "1"` and the required-keys list.

### CC-9 — Branch ruleset mutation is operator-only

- **Rule:** GitHub branch rulesets (ID `16803733` "Protect main" and any future ruleset) are changed only by the repo owner / admin through the GitHub UI. Agents are forbidden from calling `gh api` against `repos/<repo>/rulesets/*` or `repos/<repo>/branches/main/protection`.
- **Why:** Ruleset is the merge authority; agent mutation creates a privilege-escalation path.
- **Evidence:** Every ruleset change carries an operator audit comment (cf. PR #605 issuecomment-4529677096) + post-change API replay in the verification outcomes record.

### CC-10 — Archive tag preservation

- **Rule:** Every merged PR is preserved via `ai-post-merge-cleanup.sh` which pushes an annotated archive tag (`archive/YYYY/MM/<branch>-pr<N>`) to the remote before deleting the branch.
- **Why:** Cross-machine durability for 1+ year recovery; branch cleanup does not lose history.
- **Evidence:** `~/.claude/logs/git-cleanup.log` audit log + `git tag --list 'archive/*'` listing on remote.

### CC-11 — Rollback by archive tag

- **Rule:** Rollback / recovery of a merged PR uses the archive tag, not a destructive history rewrite. `git push --force` against `main` or any protected branch is forbidden.
- **Why:** Protect linear history; allow cross-machine recovery; respect ruleset `block_force_pushes`.
- **Evidence:** Rollback runbook (`docs/ROLLBACK-RUNBOOK.md`) lists recovery commands; force-push is explicitly absent.

### CC-12 — No secret material in artifacts or chat

- **Rule:** Webhook secrets, API keys, GitHub App private keys, vault tokens, PAT, or any credential value may not appear in chat, logs, evidence files, or commit messages.
- **Why:** Pre-production credentials still leak via repo audit, archive tags, and chat history.
- **Evidence:** `forbidden_actions` includes `include credential material in Claude MCP prompts or tool payloads`; reviewer evidence has a `secret_scan` check.

### CC-13 — Per-slice issue + worktree + branch + PR

- **Rule:** Each program slice opens one tracker issue, one dedicated worktree, one short-lived branch, one PR, and produces one exit decision. Multi-slice PRs and shared worktrees are forbidden.
- **Why:** Audit clarity; isolated rollback; parallel multi-agent safety.
- **Evidence:** Branch discipline rules in CLAUDE.md global instructions + `ops.sh preflight` enforcement.

## Change Control for This Policy

This document itself is governed by the same rules. Changes go through a PR
with cross-AI review, non-author approval, CI green, and squash merge.

Supersession of a CC-N rule requires:

1. A new decision record in `.claude/plans/` that names the superseded rule;
2. A PR that updates this file in place with a clear `## Superseded` block above
   the original rule;
3. A drift-guard test that pins the new behavior.

## Cross-References

- `.claude/plans/GENERAL-PURPOSE-PRODUCTION-PROMOTION-STATUS.md` — program SSOT
- `.claude/plans/gpp_status.v1.json` — machine-readable status
- `.claude/plans/GPP-2D-7-AO-GATE-9-GPP-CLOSEOUT.md` — GPP-2 closeout decision
- `docs/ROLLBACK-RUNBOOK.md` — failure-mode recovery
- `.claude/plans/_TEMPLATES/RETROSPECTIVE-TEMPLATE.md` — per-slice retrospective
- `~/.claude/CLAUDE.md` — user-level HARD RULES (chat-side enforcement)
- `AGENTS.md` — agent startup contract
