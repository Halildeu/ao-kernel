# Prompt Experiments — Operator Runbook

**Scope.** Operator-facing walkthrough for authoring + comparing prompt variants against `review_findings`-producing workflow runs. Paired with:

- `ao_kernel/defaults/schemas/prompt-variant.schema.v1.json` (v3.12 E1) — JSON Schema for variant entries.
- `ao_kernel.prompts` (v3.12 E1) — `PromptVariant` dataclass + `load_prompt_variants(workspace_root)` loader.
- `ao_kernel.experiments` (v3.12 E2) — `compare_variants(run_ids, workspace_root=...)` read-only comparison helper.
- `docs/BENCHMARK-REAL-ADAPTER-RUNBOOK.md` — prerequisite for any real-adapter run.

**Status (v3.12).** This is a **contract-only** shipment. ao-kernel does **NOT** orchestrate A/B dispatch at runtime — operators start each variant run manually and pair them post-run via `compare_variants`. Runtime A/B automation is deferred until at least one operator-validated real-adapter smoke cycle exists (Codex v3.9+ plan-time precondition; tracked toward v3.13+).

This runbook is an operator/evaluation surface, not a shipped experiment scheduler. A successful comparison here does not widen the default supported demo lane on its own.

---

## 1. Why a contract-only experiment surface

Prompt experimentation is powerful but easy to misuse: it's tempting to ship an A/B runner that orchestrates variants, samples runs, and hands back a "winner" score. Without trustworthy metrics — meaning an operator has actually run the real adapter end-to-end and validated the `review_findings` artefact shape against their own prompt — an automated A/B runner would produce confident-looking numbers off of stub data.

v3.12 takes the opposite cut: ship the **declarative contract** (variant registry, schema, loader, `intent.metadata.variant_id` stamp, read-only comparison helper), let operators drive the runs, and defer the orchestration layer until real-adapter smokes exist.

The upside: `compare_variants` output is grounded in real `review_findings` payloads the operator trusts. When the prereq clears, a future PR can wire the orchestrator on top of this contract without breaking operators who already use the helper.

---

## 2. Authoring variants

Place a workspace override at `.ao/registry/prompt_variant_registry.v1.json` (bundled default ships empty). Each entry must satisfy `prompt-variant.schema.v1.json`:

```json
{
  "version": "v1",
  "variants": [
    {
      "variant_id": "review.concise.v1",
      "version": "1.0.0",
      "prompt_template": "Summarize findings in at most 3 bullets. Use severity tags error|warning|info|note.",
      "expected_capability": "review_findings",
      "metadata": {
        "experiment_id": "exp-2026-04-19-concise-vs-detailed",
        "branch": "feat/review-tuning",
        "created_by": "halil"
      }
    },
    {
      "variant_id": "review.detailed.v2",
      "version": "2.0.0",
      "prompt_template": "For each finding, include (a) file:line, (b) severity, (c) one-sentence rationale, (d) optional suggestion.",
      "expected_capability": "review_findings",
      "metadata": {
        "experiment_id": "exp-2026-04-19-concise-vs-detailed",
        "branch": "feat/review-tuning",
        "created_by": "halil"
      }
    }
  ]
}
```

Schema invariants enforced by the loader:

- `variant_id` — non-empty, pattern `^[A-Za-z0-9][A-Za-z0-9_.-]*$`, unique within the registry.
- `version` — non-empty string (operator-controlled; not parsed).
- `prompt_template` — non-empty string (the literal body handed to the adapter).
- `expected_capability` (optional) — one of `review_findings`, `commit_message`, `write_diff`. Closed enum — extra values rejected.
- `metadata` (optional) — freeform object; ao-kernel reads `experiment_id` by convention but does not validate anything else.

Any schema violation raises `PromptVariantError` at load time with a schema-path excerpt:

```
PromptVariantError: prompt-variant schema violation at $.variant_id: '-bad' does not match '^[A-Za-z0-9][A-Za-z0-9_.-]*$'
```

Loading:

```python
from pathlib import Path
from ao_kernel.prompts import load_prompt_variants

variants = load_prompt_variants(workspace_root=Path("."))
concise = next(v for v in variants if v.variant_id == "review.concise.v1")
print(concise.prompt_template)
```

---

## 3. Stamping the `variant_id` on a run

When the operator starts a workflow run (typically via `ao_kernel.workflow.create_run` or the upstream driver), they write the chosen variant id into `intent.metadata.variant_id`. That stamp is the contract anchor for everything downstream:

```python
import uuid
from ao_kernel.workflow import create_run

run_id = str(uuid.uuid4())
create_run(
    workspace_root,
    run_id=run_id,
    workflow_id="governed_review_claude_code_cli",
    workflow_version="1.0.0",
    intent={
        "kind": "inline_prompt",
        "payload": "review the diff in HEAD",
        "metadata": {
            "variant_id": "review.concise.v1",        # required for compare_variants
            "experiment_id": "exp-2026-04-19-concise-vs-detailed",
        },
    },
    budget={
        "time_seconds": {"limit": 600.0, "spent": 0.0, "remaining": 600.0},
        "fail_closed_on_exhaust": True,
    },
    policy_refs=["ao_kernel/defaults/policies/policy_worktree_profile.v1.json"],
    evidence_refs=[f".ao/evidence/workflows/{run_id}/events.jsonl"],
    adapter_refs=["claude-code-cli"],
)
```

Workflow-run schema (`workflow-run.schema.v1.json`) treats `intent.metadata` as a freeform map — no schema change was needed to support the stamp. Just make sure the key is `variant_id` (the helper looks for that exact name).

The actual adapter invocation (which picks up `variants[...].prompt_template`) happens outside ao-kernel today: the operator passes the chosen template through `{context_pack_ref}` per the BENCHMARK-REAL-ADAPTER-RUNBOOK.md §3 prompt contract. `compare_variants` then pairs `variant_id` ↔ `review_findings` artefact after each run finishes.

---

## 4. Running each variant

For each variant you want in the comparison:

1. **Check out a clean disposable sandbox repo** (BENCHMARK-REAL-ADAPTER-RUNBOOK.md §4).
2. **Ensure the workspace override** enables the worktree profile (`enabled=true`, `ANTHROPIC_API_KEY` in `allowlist_secret_ids`, etc.).
3. **Set the variant prompt** — typically by writing it into the `context_pack_ref` file that the workflow's `compile_context` step produces. Any mechanism that gets the template into the adapter's `--prompt-file` is fine; ao-kernel doesn't mandate a particular channel.
4. **Start the run** with `intent.metadata.variant_id = <that variant's id>`.
5. **Wait for completion** and confirm the run reaches `state=completed` with `review_findings` in at least one `step_record.capability_output_refs`.
6. **Record the run_id** somewhere (a plain text file, a one-line note — anything).

Repeat for every variant. No ao-kernel-side coordination; the operator is the loop.

---

## 5. Comparing the results

Once the run set is complete:

```python
from pathlib import Path
from ao_kernel.experiments import compare_variants

workspace = Path(".")
run_ids = [
    "a1b2c3d4-...",  # review.concise.v1 run
    "e5f6a7b8-...",  # review.detailed.v2 run
    # ... add all runs in the experiment
]

comparison = compare_variants(run_ids, workspace_root=workspace)

for variant_id, entries in comparison.by_variant.items():
    print(f"\n=== {variant_id} ({len(entries)} run(s)) ===")
    for entry in entries:
        if entry.review_findings is not None:
            payload = entry.review_findings
            findings = payload.get("findings", [])
            summary = payload.get("summary", "")
            print(f"  [{entry.run_id}] {len(findings)} finding(s) — {summary}")
        else:
            print(f"  [{entry.run_id}] NO PAYLOAD — {entry.load_error}")
```

Contract reminders:

- `compare_variants` **fails closed** if any run is missing `intent.metadata.variant_id`. Unstamped runs don't belong in an experiment; the helper won't silently include them.
- Artefact load failures (missing file, malformed JSON, non-dict payload) are packaged into `VariantComparisonEntry.load_error` rather than raised. The row still ships — the operator sees which runs produced analyzable payloads and which didn't.
- Entries preserve the order of the `run_ids` argument. `by_variant` groups them for quick lookup.

## 6. What this runbook does NOT ship

- **Automated A/B dispatch.** ao-kernel does not iterate through variants, start their runs, aggregate scores, or pick a "winner." Operators run each variant by hand (§4).
- **Scoring / threshold gates.** `VariantComparison` is raw data. The operator writes their own diff logic, stats, or reviewer tooling on top.
- **`differing_findings()` / diff helpers.** Additive surface deferred per Codex plan-time — add if real demand surfaces.
- **Bench harness integration.** `tests/benchmarks/` stays on the deterministic `codex-stub` path. Real-adapter runs are operator-driven only.

---

## 7. Pre-v3.13 checklist before runtime A/B lands

If v3.13 (or later) opens the runtime A/B orchestrator, these need to clear first:

1. **At least one operator-validated real-adapter smoke cycle** — someone actually ran `claude-code-cli` with a real prompt through the `governed_review_claude_code_cli` workflow and confirmed the `review_findings` envelope came back clean.
2. **Reproducible runs** — same prompt + same commit = same findings shape (within model nondeterminism tolerance).
3. **Cost ceiling** — per-run budget guard so the orchestrator doesn't blow through an API budget during a variant sweep.

Until those clear, the contract-only surface in this runbook is the sanctioned path.

---

## 8. Related docs

- `docs/BENCHMARK-REAL-ADAPTER-RUNBOOK.md` — operator setup for real-adapter review runs (workspace override, secret flow, prompt contract). Required reading before stamping variant_id on a real run.
- `docs/BENCHMARK-SUITE.md` — benchmark architecture (codex-stub baseline).
- `docs/ADAPTERS.md` — adapter manifest schema + capability registry.
- `ao_kernel/prompts.py` — loader API reference.
- `ao_kernel/experiments/compare.py` — comparison helper API reference.

---

## 9. v3.12 E-arc ship map

- PR #168 (E1) — prompt-variant schema + registry + `ao_kernel.prompts` loader + `intent.metadata.variant_id` contract.
- PR #169 (E2) — `ao_kernel.experiments.compare_variants` read-only helper.
- **This PR (E3)** — Operator runbook.

All three ship together in v3.12.0. Runtime A/B automation deferred to a later release once the §7 prereqs clear.
