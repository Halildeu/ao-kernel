# Benchmark Full Mode — Operator Runbook (v3.7 F1)

**Status:** v3.7 F1 opt-in. The default PR CI path is unchanged (`--benchmark-mode=fast` remains the deterministic mock-transport surface; see [`BENCHMARK-SUITE.md`](BENCHMARK-SUITE.md)).

Full mode bypasses the mock transport and dispatches to the real adapter subprocess path. It is **ops-only** — do NOT wire into the default CI matrix. Use this runbook when you need to validate a real end-to-end adapter invocation (e.g., before cutting a release, or when diagnosing an adapter manifest drift).

---

## 1. Prerequisites

### 1.1 Binaries on `$PATH`

Every adapter the benchmark scenarios exercise must be invokable from the shell:

- `claude` — Claude Code CLI (for the `claude-code-cli` adapter)
- `gh` — GitHub CLI (for the `gh-cli-pr` adapter)
- `git` — baseline repo ops
- `pytest` — already required for running the suite

### 1.2 Secrets

Full mode resolves secrets through the existing `_internal/secrets` env provider. The **bundled** `policy_secrets.v1.json` allowlist accepts both the canonical and legacy variants (v3.7 F1 backward-compat):

| Role | Canonical (runbook-preferred) | Legacy alias (also allowed) |
|---|---|---|
| Anthropic Claude | `ANTHROPIC_API_KEY` | `CLAUDE_API_KEY` |
| GitHub CLI | `GH_TOKEN` | `GITHUB_TOKEN` |
| OpenAI (embeddings / router fallback) | `OPENAI_API_KEY` | — |

Export whichever variant you have in your environment before invoking the suite:

```bash
export ANTHROPIC_API_KEY=sk-ant-...
export GH_TOKEN=ghp_...
export OPENAI_API_KEY=sk-...     # optional — only needed if your workspace touches embedding / OpenAI routing
```

> **Actual fail-close gate** is the workspace-level `policy_worktree_profile.v1.json::secrets.allowlist_secret_ids`. Make sure that allowlist includes whatever env names you actually export; the bundled `policy_secrets.v1.json` is the registry/docs canonical — the worktree-profile is what the adapter runtime enforces on invocation.

### 1.3 Workspace profile

Full-mode benchmarks open subprocess shells against real adapters. At minimum:

- `policy_worktree_profile.enabled = true` with a secrets allowlist that matches your exports.
- `policy_cost_tracking.enabled = true` if you want spend events to reach the real reconcile path. (Bundled default is dormant; v3.7 F2 closes the scorecard wiring so a full-mode run with tracking enabled produces `cost_source="real_adapter"` in the scorecard.)

### 1.4 Disposable target repo

`gh-cli-pr` opens a **real PR** against whichever repo the CWD resolves to. Do NOT run full mode inside the ao-kernel main repo checkout. Instead:

1. Clone ao-kernel into a scratch location.
2. Create or reuse a disposable sandbox repo on GitHub that you can freely delete branches + PRs on.
3. Make that sandbox repo the CWD when invoking pytest.

---

## 2. Running

```bash
# From your disposable sandbox clone
pytest tests/benchmarks/ --benchmark-mode=full -q
```

Only tests carrying `@pytest.mark.full_mode` run in this mode. The fast-mode suite is skipped automatically when `full` is passed (and vice-versa).

Default heartbeat — run a single scenario first:

```bash
pytest tests/benchmarks/test_full_mode_smoke.py::TestFullModeGovernedReview \
  --benchmark-mode=full -q
```

---

## 3. Rollback

Full mode only affects the `tests/benchmarks/` suite. If a full-mode run leaves artefacts on your sandbox repo:

- PRs: close via `gh pr close <number>`.
- Branches: delete via `git push origin --delete <branch>`.
- Local `.ao/` state: `git clean -xdf .ao/` (if this is a scratch clone; NEVER run in your main working tree).

No default CI job is touched by this runbook. `.github/workflows/test.yml` remains identical to the pre-v3.7 shape.

---

## 4. See also

- [`docs/BENCHMARK-SUITE.md`](BENCHMARK-SUITE.md) — fast-mode contract + scenario catalog
- [`docs/ADAPTERS.md`](ADAPTERS.md) — adapter manifest shape + secrets flow
- [`docs/WORKTREE-PROFILE.md`](WORKTREE-PROFILE.md) — policy surface for allowlisted secrets / sandbox settings
- [`tests/benchmarks/conftest.py`](../tests/benchmarks/conftest.py) — `--benchmark-mode` option + `benchmark_mode` fixture + `full_mode` marker
