# Benchmark Full Mode — Scaffold + Operator Forward Reference (v3.7 F1)

**Status:** v3.7 F1 — **scaffold only**. The first real full-mode smoke lands in v3.7 F2. Default PR CI is unchanged (`--benchmark-mode=fast` remains the deterministic mock-transport surface; see [`BENCHMARK-SUITE.md`](BENCHMARK-SUITE.md)).

## What F1 actually ships

F1 wires the opt-in surface but does NOT include a runnable real-adapter smoke test:

1. `pytest_addoption --benchmark-mode=fast|full` is registered in `tests/benchmarks/conftest.py`.
2. A new `@pytest.mark.full_mode` marker gates real-adapter tests at collection time.
3. `benchmark_mode` fixture resolves the mode string for fixture wiring.
4. `mock_adapter_transport` docstring pins the convention (fast = patch, full = bypass).
5. Bundled `policy_secrets.v1.json` allowlist canonicalized + backward-compat (5-entry set).
6. `context_pack_ref` real-artefact contract pinned via a fast-mode test (so F2 can rely on it).

F1 does NOT ship a callable `@full_mode` test. Under `--benchmark-mode=full` the collection hook skips every non-`@full_mode` benchmark test and the remainder of the suite collects 0 runnable tests. That is intentional — the first real smoke lands in F2.

## Why the smoke isn't in F1

The bundled bench workflows (`review_ai_flow`, `governed_bugfix_bench`) reference the `codex-stub` local Python helper as their adapter. A genuine real-adapter smoke (one that exercises `claude-code-cli` or `gh-cli-pr` with env-gated secrets) requires three changes that are **F2 scope**:

1. A bench workflow variant pointing at real adapter manifests.
2. `claude-code-cli.manifest.v1.json` to advertise the `review_findings` capability (today absent).
3. Workspace override enabling `policy_worktree_profile` (bundled default is dormant, `enabled=false`, secret allowlist empty).

Without those three, a full-mode "smoke" would either skip silently on prerequisites or fail in misleading places (policy check, capability gap, etc.). Codex post-impl review flagged this as a BLOCK against F1; the response is to narrow F1 to scaffold and route the smoke to F2.

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
