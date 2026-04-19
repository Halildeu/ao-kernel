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

## Forward reference for operators (F2+ wiring)

This section records what operators will need when F2 lands a real-adapter smoke. **Do not configure any of this today in response to F1 alone** — nothing in F1 consumes these settings in an actionable path.

### Binaries

| Role | Binary |
|---|---|
| Anthropic Claude | `claude` (Claude Code CLI) |
| GitHub CLI | `gh` |

### Secret environment variables

The bundled `policy_secrets.v1.json` allowlist accepts both the canonical and legacy variants (v3.7 F1 backward-compat widening):

| Role | Canonical (docs-preferred) | Legacy alias (also allowed) |
|---|---|---|
| Anthropic Claude | `ANTHROPIC_API_KEY` | `CLAUDE_API_KEY` |
| GitHub CLI | `GH_TOKEN` | `GITHUB_TOKEN` |
| OpenAI (embeddings / router fallback) | `OPENAI_API_KEY` | — |

> **Actual fail-close gate** is `policy_worktree_profile.v1.json::secrets.allowlist_secret_ids`. The bundled `policy_secrets.v1.json` is the registry / docs canonical surface; the worktree-profile is what the adapter runtime enforces on invocation.

### Workspace profile

- `policy_worktree_profile.enabled = true` with a secrets allowlist that matches your exports.
- `policy_cost_tracking.enabled = true` if you want spend events to reach the reconcile path (F2 ships the matching scorecard label `cost_source="real_adapter"`).

### Disposable target repo

`gh-cli-pr` opens real PRs against the CWD's upstream. When F2 wires a smoke that exercises it, use a disposable sandbox clone, NEVER your main ao-kernel checkout.

---

## Running

Today (F1):

```bash
# Fast mode (default) — unchanged behaviour
pytest tests/benchmarks/ -q
```

```bash
# Full mode — scaffold exists, 0 runnable tests (until F2)
pytest tests/benchmarks/ --benchmark-mode=full -q
```

Fast mode skips `@full_mode` tests; full mode skips everything else in `tests/benchmarks/`.

Post-F2, the same `--benchmark-mode=full` invocation will run the F2-added real-adapter smoke.

---

## Rollback

F1 does not introduce any stateful side-effects on disk. No default CI job is touched. `.github/workflows/test.yml` remains identical to the pre-v3.7 shape.

---

## See also

- [`docs/BENCHMARK-SUITE.md`](BENCHMARK-SUITE.md) — fast-mode contract + scenario catalog
- [`docs/ADAPTERS.md`](ADAPTERS.md) — adapter manifest shape + secrets flow
- [`docs/WORKTREE-PROFILE.md`](WORKTREE-PROFILE.md) — policy surface that will gate real-adapter secrets
- [`tests/benchmarks/conftest.py`](../tests/benchmarks/conftest.py) — `--benchmark-mode` option + `benchmark_mode` fixture + `full_mode` marker
- [`.claude/plans/PR-v3.7-BENCHMARK-REALISM-DRAFT-PLAN.md`](../.claude/plans/PR-v3.7-BENCHMARK-REALISM-DRAFT-PLAN.md) — v3.7 plan; see §3.F2 for the real-adapter follow-up scope
