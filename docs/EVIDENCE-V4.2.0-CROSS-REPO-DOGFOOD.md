# Evidence — v4.2.0 Cross-Repo Dogfood (usage-model demo)

> ## ⚠️ Evidence class: operator-local usage-model demo — NOT project-owned production evidence
>
> Per the GPP contract (CLAUDE.md §21): **local/operator smoke is NOT project-owned
> production evidence.** This document records a reproducible demonstration that
> the **published** `ao-kernel==4.2.0` (from PyPI) can be installed into a *fresh,
> separate repository* and used as a governed control-plane **with no provider API
> key**. It demonstrates the **usage model**, not a production-readiness claim.
>
> The three guard flags remain **const false** (`live_adapter_execution`,
> `support_widening`, `production_platform_claim`). No provider API call is made;
> the AI sources below (`claude-cli`, `codex-cli`) are illustrative
> CLI-subscription provenance labels recorded into the governed decision store —
> not programmatic API invocations.

## 1. What this demonstrates

The documented operating model is: **ao-kernel governs; the AIs (Claude / Codex /
Mavis) do the work through their own CLI subscriptions; ao-kernel never makes
programmatic provider API calls.** This dogfood proves that model works end-to-end
when ao-kernel is installed into another repo straight from PyPI:

1. `pip install ao-kernel==4.2.0` + `ao-kernel init` in a fresh repo.
2. Governed multi-AI turns recorded with CLI-subscription provenance.
3. Fail-closed policy engine denies an unknown action and evaluates a bundled policy.
4. Governed context continuity: decisions recalled across turns.
5. Governed context persisted: the **canonical decision store** is written under
   `.ao/` (this is the canonical-decision persistence surface, *not* the separate
   JSONL evidence trail).

All with **no API key**.

## 2. Reproducible transcript

This is the verbatim output of a clean run on 2026-06-07 (fresh temp repo, fresh
venv, install from PyPI):

```text
$ pip install ao-kernel==4.2.0  &&  ao-kernel init
Workspace created: <fresh-repo>/.ao
ao-kernel 4.2.0 (from PyPI)

$ governed multi-AI flow (no API key):
turn1: recorded 2 governed decisions (source=claude-cli, codex-cli)
turn2: policy gate (unknown) -> deny [fail-closed]
turn2: bundled policy_cost_tracking -> deny
turn3: query_memory('arch.*') -> 2 decisions recalled across turns
        - arch.auth = oauth2-pkce
        - arch.db = postgres

$ governed context / canonical decision store (.ao):
.ao/workspace.json
.ao/canonical_decisions.v1.json
```

Reproduce it yourself:

```bash
cd $(mktemp -d) && git init -q
python3 -m venv .venv && .venv/bin/pip install -q "ao-kernel==4.2.0"
.venv/bin/ao-kernel init
.venv/bin/python - <<'PY'
from ao_kernel import AoKernelClient
with AoKernelClient(workspace_root=".") as c:
    c.record_decision("arch.db", "postgres", source="claude-cli", confidence=0.9)
    c.record_decision("arch.auth", "oauth2-pkce", source="codex-cli", confidence=0.85)
    print("unknown policy ->", c.check_policy("nope", {"action": "x"}).get("decision"))
    print("bundled policy_cost_tracking ->", c.check_policy("policy_cost_tracking", {"action": "llm_call"}).get("decision"))
    print("recalled:", [(h["key"], h["value"]) for h in c.query_memory("arch.*")])
PY
```

## 3. What it proves — and what it does NOT

**Proves (narrow, honest):**

- The published `ao-kernel==4.2.0` installs into a fresh, separate repo from PyPI.
- The governance core works there with **no API key**: fail-closed policy
  (`deny` on unknown + bundled-policy evaluation), governed context
  record/recall across turns, and a persisted **canonical decision store** under
  `.ao/`.
- The CLI-subscription operating model is exercised end-to-end (decision
  provenance recorded; no programmatic provider call).

**Does NOT prove (out of scope):**

- It is **not** project-owned production evidence (§21) and confers **no**
  production-platform claim.
- It does **not** exercise `live_adapter_execution` (no provider API call).
- It does **not** widen the support boundary; the three guard flags stay false.
- It does **not** exercise the self-hosted **JSONL evidence trail**
  (`.ao/evidence/.../*.jsonl`), which is a separate surface; this demo writes only
  the canonical decision store. See `docs/EVIDENCE-TIMELINE.md` for the JSONL trail.
- Multi-tenant / concurrent / at-scale safety is not claimed here.

## 4. References

- Consumer guide: `docs/USING-AO-KERNEL-IN-YOUR-PROJECT.md`
- Supersession decision (governed control-plane reframe):
  `.claude/plans/EPIC-9-PR-XFINAL-SUPERSESSION-CLOSEOUT.md`
- Guard-flag authority: `.claude/plans/gpp_status.v1.json` (all three false)
- Cross-AI review: implementer `anthropic` / reviewer `openai` (Codex thread `019ea0f0`)
