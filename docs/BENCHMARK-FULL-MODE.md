# Benchmark Full Mode — Operator Runbook (v3.7 F2)

**Status:** v3.7 F2 — **first runnable full-mode smoke** landed (codex-stub subprocess path; external adapter wiring stays scope-out). Default PR CI is unchanged (`--benchmark-mode=fast` remains the deterministic mock-transport surface; see [`BENCHMARK-SUITE.md`](BENCHMARK-SUITE.md)).

## What F2 ships

F2 extends the F1 scaffold with an actual runnable `@pytest.mark.full_mode` smoke:

1. `_maybe_consume_budget` benchmark-only shim **removed** — adapter-path `post_adapter_reconcile` middleware (v3.3.0 PR-C3) is the sole cost drainer.
2. Mode-gated cost-tracking override in `tests/benchmarks/conftest.py::workspace_root`: full mode flips `policy_cost_tracking.enabled=true`; fast mode keeps bundled dormant default.
3. First runnable `@full_mode` smoke: `TestFullModeAdapterPathReconcile` in `tests/benchmarks/test_full_mode_smoke.py` dispatches `governed_review` via real `invoke_cli` against `codex-stub`.
4. Scorecard collector switches to **event-backed** cost-source detection: `llm_spend_recorded(source="adapter_path")` → `cost_source="real_adapter"`. No event + no drain → `None`. Legacy positive drain (historical artefacts from the removed shim) → `"mock_shim"`.
5. Render footer wording: `real_adapter` → "adapter-path reconcile (event-backed; non-shim)". Codex iter-2 correction: NOT "real adapter spend" — codex-stub emits canned events, not vendor billing.
6. Mode-gated scorecard session-finish: fast mode expects `{governed_review, governed_bugfix}`; full mode expects `{governed_review}` only (no `gh-cli-pr` wiring in F2 scope).

## What F2 deliberately does NOT ship (scope-out)

- **External `claude-code-cli` / `gh-cli-pr` wiring.** The codex-stub adapter proves the adapter-path reconcile fires correctly; extending this to real vendor adapters requires a bench workflow variant, capability-matrix adjustments on `claude-code-cli.manifest.v1.json`, and `policy_worktree_profile.enabled=true` — all **F2.1+ scope**.
- **`governed_bugfix` full-mode smoke.** `gh-cli-pr` fragility keeps it out of F2. Fast-mode bugfix coverage unchanged.
- **CI full-mode gate.** `.github/workflows/test.yml` diff=0 remains; operators run full mode explicitly.

## Prerequisites (F2 shipped state)

### Local Python must import `ao_kernel`

The bundled bench workflows invoke `codex-stub` via a plain `python3 -m ao_kernel.fixtures.codex_stub` command. The `python3` on `$PATH` must be able to import `ao_kernel`. In an editable install (`pip install -e ".[dev,llm,mcp,metrics]"`) this is automatic; in a system python with ao-kernel missing, the F2 smoke skips gracefully via the workflow-failed event check.

### Secret environment variables (F2.1+ forward reference)

When F2.1+ wires external `claude-code-cli` / `gh-cli-pr` adapters, operators will export:

| Role | Canonical (docs-preferred) | Legacy alias (also allowed in bundled allowlist) |
|---|---|---|
| Anthropic Claude | `ANTHROPIC_API_KEY` | `CLAUDE_API_KEY` |
| GitHub CLI | `GH_TOKEN` | `GITHUB_TOKEN` |
| OpenAI (embeddings / router fallback) | `OPENAI_API_KEY` | — |

> **Actual fail-close gate** is `policy_worktree_profile.v1.json::secrets.allowlist_secret_ids`. The bundled `policy_secrets.v1.json` is the registry / docs canonical surface; the worktree-profile is what the adapter runtime enforces on invocation. Neither is required for the F2 codex-stub smoke.

### Workspace profile (F2)

- `policy_cost_tracking.v1.json::enabled=true` — F2 workspace_root fixture flips this automatically in full mode so `post_adapter_reconcile` emits `llm_spend_recorded` events. Fast mode keeps the bundled dormant default.
- `policy_worktree_profile.enabled=true` is NOT required for the F2 codex-stub smoke; it becomes relevant when external adapters are wired (F2.1+).

### Disposable target repo (F2.1+ only)

`gh-cli-pr` opens real PRs against the CWD's upstream. When F2.1+ wires a smoke that exercises it, use a disposable sandbox clone, NEVER your main ao-kernel checkout. The F2 codex-stub smoke does NOT open remote PRs and is safe to run in any checkout.

---

## Running

Fast mode (default, unchanged):

```bash
pytest tests/benchmarks/ -q
```

Full mode (F2 smoke):

```bash
pytest tests/benchmarks/ --benchmark-mode=full -q
```

In full mode the collection hook skips every non-`@full_mode` benchmark test; only `TestFullModeAdapterPathReconcile` runs. If `python3` cannot import `ao_kernel`, the test skips gracefully (`subprocess prereq miss`).

---

## Rollback

F2 does not introduce any stateful side-effects on disk. No default CI job is touched. `.github/workflows/test.yml` remains identical to the pre-v3.7 shape.

---

## See also

- [`docs/BENCHMARK-SUITE.md`](BENCHMARK-SUITE.md) — fast-mode contract + scenario catalog
- [`docs/ADAPTERS.md`](ADAPTERS.md) — adapter manifest shape + secrets flow
- [`docs/WORKTREE-PROFILE.md`](WORKTREE-PROFILE.md) — policy surface that will gate real-adapter secrets
- [`tests/benchmarks/conftest.py`](../tests/benchmarks/conftest.py) — `--benchmark-mode` option + `benchmark_mode` fixture + `full_mode` marker
- [`.claude/plans/PR-v3.7-BENCHMARK-REALISM-DRAFT-PLAN.md`](../.claude/plans/PR-v3.7-BENCHMARK-REALISM-DRAFT-PLAN.md) — v3.7 plan; see §3.F2 for the real-adapter follow-up scope
