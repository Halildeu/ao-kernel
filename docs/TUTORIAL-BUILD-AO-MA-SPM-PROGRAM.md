# Tutorial: Build Your Own AO-MA-SPM Program with AI (V5 Epic 8 E-8-5)

> **Documentation only.** **Tutorial scaffold.** This tutorial walks
> through bootstrapping a governed multi-AI autonomous program (AO-MA-SPM
> pattern) on top of ao-kernel. It does NOT flip any of the three V5
> guard flags (`support_widening`, `production_platform_claim`,
> `live_adapter_execution`), which remain `const false`. No
> production-ready posture is established by this tutorial; the final
> posture is recorded ONLY by the operator-bound supersession PR at the
> end of the V5 roadmap.

## 1. What You Will Build

A minimal AO-MA-SPM (Sustained Program of Multi-AI) loop where:

- Two AI providers (e.g. Anthropic Claude + OpenAI Codex) write code
  cooperatively
- ao-kernel governs the cross-AI peer review handoff (ADR-0004 HARD RULE)
- Decisions land as ADRs validated against the bundled schema
- A single human operator approves the plan-consensus bundle once per
  cycle (HARD RULE Plan Consensus Autonomy)
- Evidence is recorded in the JSONL append-only trail

You will NOT build:

- Live LLM provider calls (the `[llm]` extra remains optional; this
  tutorial uses canned worker stubs)
- A production deployment (see E-8-1 deployment guide separately)
- Multi-tenant isolation (E-4-3 follow-up)

## 2. Prerequisites

| Requirement | Version |
|---|---|
| Python | 3.11+ |
| ao-kernel | `pip install 'ao-kernel[mcp]'` |
| Git | any recent |
| Two AI provider account placeholders | optional for the canned path |

You do NOT need real API keys to complete this tutorial. The
governance plane works against stub workers; live provider calls are
gated behind the `live_adapter_execution=true` flag flip, which is an
operator-bound supersession PR (E-2-1 future slice).

## 3. Step 1 — Initialize the Workspace

```bash
mkdir my-ao-ma-program && cd my-ao-ma-program
python -m venv .venv
source .venv/bin/activate
pip install 'ao-kernel[mcp]'

ao-kernel init        # creates .ao/ workspace
ao-kernel doctor      # 8 health checks must all pass
```

The `.ao/` directory now contains the canonical decision store, the
JSONL evidence stream, policy bundle, and checkpoint slots.

## 4. Step 2 — Define Your First Slice

A slice is the smallest unit of work an AO-MA-SPM program can plan,
implement, review, and merge.

Create `.claude/plans/SLICE-001-hello-world.md`:

```markdown
# SLICE-001 — Hello AO-MA

## Goal
Print "hello ao-ma" via the ao-kernel governed runtime.

## Acceptance
- ao-kernel native-import a worker result envelope
  produced by a canned stub
- evidence trail records the import event
- 2 reviewer evidence files in ao-ma-10-high-risk-reviews/
  (skipped here because this slice has no .github/ mutation)
```

## 5. Step 3 — Plan-Time Cross-AI Consensus

Per HARD RULE Cross-AI Peer Review + Plan Consensus Autonomy, two
distinct AI providers must AGREE on the plan before implementation.

Open two terminals:

**Terminal A** — Anthropic Claude session:

```bash
# Inside your AI tool of choice (e.g. Claude Code CLI):
"Read SLICE-001-hello-world.md and produce a plan-time verdict."
```

**Terminal B** — OpenAI Codex MCP:

```bash
codex exec --sandbox read-only \
  "Read SLICE-001-hello-world.md and produce a plan-time verdict."
```

Once both reviewers reach AGREE, record the consensus by appending the
verdict block per the AO-MA-SPM helper's invocation report schema (see
`ao_kernel/defaults/schemas/`). The bundled validator rejects any
combination where implementer.provider == reviewer.provider (ADR-0004).

## 6. Step 4 — Implement Against the Stub Worker

ao-kernel ships an import-only worker contract (ADR-0003): the kernel
never spawns the LLM; it imports the result envelope produced by your
worker (CLI subprocess, Claude Code session, Mavis run, etc.).

```python
from ao_kernel import AoKernelClient

with AoKernelClient(workspace_root=".") as client:
    result = client.llm_call(
        messages=[{"role": "user", "content": "print hello ao-ma"}],
        intent="FAST_TEXT",
    )
    print(result.text)
```

If you do not have `[llm]` extra installed, the call falls back to a
no-op path that still exercises the governance pipeline.

## 7. Step 5 — Verify Evidence

```bash
ao-kernel evidence timeline    # JSONL append-only trail
ao-kernel evidence replay      # replay a session
```

Every governance decision (policy check, capability gate, decision
extraction, telemetry) is recorded. Your AO-MA-SPM program audit trail
is now reproducible.

## 8. Step 6 — Open a Pull Request

The release-gate workflow (`ao-release-gate`) inspects:

1. The local-ai-review-evidence.v1.json file (single-AI baseline)
2. For high-risk paths, the supersession evidence pair in
   `ao-ma-10-high-risk-reviews/` (openai + anthropic — both AGREE)
3. The branch protection ruleset (no admin merge, no force-push)

Auto-merge with `--auto` triggers as soon as both technical and review
gates report `success`.

## 9. Step 7 — Wire Up Operator Approval Gate

Once your program is multi-slice, configure a GitHub Environment
(`ao-ma-plan-approval`) so the single human operator approves the
plan-consensus bundle for each cycle. This is the canonical
Plan Consensus Autonomy gate (HARD RULE 2026-04-17).

```yaml
# .github/workflows/ao-ma-plan-consensus.yml — high-risk; requires
# CODEOWNER review before any change. See E-1-1 wiring for reference.
```

This step is OPTIONAL for the tutorial and required only when you
expand to multi-slice production cycles.

## 10. What to Read Next

- [`PRODUCTION-DEPLOYMENT-GUIDE.md`](PRODUCTION-DEPLOYMENT-GUIDE.md) — E-8-1
- [`OPERATOR-RUNBOOK.md`](OPERATOR-RUNBOOK.md) — E-8-3
- [`MIGRATION-GUIDE-V4-TO-V5.md`](MIGRATION-GUIDE-V4-TO-V5.md) — E-8-6 (if present)
- `.claude/plans/adr/` — ADR-0001..0005 cross-AI revalidated
- `ao_kernel/defaults/schemas/ao-ma-adr.schema.v1.json` — ADR contract

## 11. Operator Boundaries

This tutorial is descriptive; it does NOT:

- Make any production-ready claim about the resulting program
- Flip any of the three V5 guard flags
- Authorize live provider calls (`live_adapter_execution=true` requires
  operator-bound supersession PR, E-2-1)
- Replace any operator-owned program governance (incident response,
  vendor escalation, customer notification, postmortem cadence)

## 12. Cross-AI Peer Review Trail

Per HARD RULE Cross-AI Peer Review (2026-05-05 + 2026-05-14):

- Implementer Anthropic Claude → Reviewer OpenAI Codex (post-impl).
- Plan-time consensus required for any change to tutorial language that
  could read as a production claim.
- Plan doc at
  [`../.claude/plans/EPIC-8-5-TUTORIAL.md`](../.claude/plans/EPIC-8-5-TUTORIAL.md).
