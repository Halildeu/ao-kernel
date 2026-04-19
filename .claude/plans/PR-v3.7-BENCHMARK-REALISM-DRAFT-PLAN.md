# v3.7 — Benchmark Realism (DRAFT v1)

**Status:** DRAFT v1 — master plan pending per-PR CNS
**Prior consensus:** Codex 2-round consult (2026-04-19) → v3.7 theme = Benchmark Realism; Tool-Use automated loop explicitly OUT of scope (built-in Claude/Codex; no parallel feature per user global rule). F1+F2 MUST-ship, F3 NICE-TO-HAVE.

**Depends on:** v3.6.0 LIVE (consumer-side surfaces complete; FAZ-C PR-C2 `parent_env` security-split + PR-C3 `post_adapter_reconcile cost runtime` already landed in v3.3.0 — runtime base exists, only **benchmark activation** is pending).

---

## 1. Problem statement

v3.5 D3 shipped the dev scorecard; its `cost_source` field was designed to distinguish `"mock_shim"` (benchmark-only) from `"real_adapter"` (C3 reconcile path) but only the shim path has shipped. Two concrete gaps:

1. `tests/benchmarks/` runs fast-mode only. `docs/BENCHMARK-SUITE.md §8.3` documents `--benchmark-mode=full` as "ops-only path deferred to FAZ-C PR-C2". Runtime base for secrets-flow + `context_pack_ref` + `parent_env` security-split all landed, but the benchmark harness never activates it.
2. `tests/benchmarks/mock_transport.py::_maybe_consume_budget` is a benchmark-only shim draining `budget.cost_usd` so `assert_cost_consumed` observes drain. Post-C3 the real adapter transport reconcile fires `llm_spend_recorded` events with cost_actual; the scorecard's `cost_source` is hard-coded `"mock_shim"` because no real-adapter fast-path exists in the benchmark.

v3.7 closes both gaps — operator-runnable full-mode + real cost flowing to the scorecard — without changing the default `benchmark-fast` CI behaviour.

---

## 2. Non-goals

- **No automated tool-use loop.** The current manual tool-call pattern in `AoKernelClient.llm_call` is explicit design (see `ao_kernel/client.py:519`). Claude Code / Codex already provide tool-use; a parallel runtime loop would duplicate.
- **No `tool_permissions` / `cycle_detection` runtime enforcement.** Gap between `policy_tool_calling.v1.json` and `tool_gateway.py` (`ToolCallPolicy.from_dict()` only absorbs a subset) is a **v3.9+ governance hardening PR**, not v3.7 scope.
- **No new benchmark scenarios.** `governed_bugfix` + `governed_review` stay the primary set; B7.x+ territory for expansion.
- **No CI-level enforcement of full-mode.** Default PR CI stays fast-only; full-mode runs ops-gated via explicit invocation.
- **No public symbol removals.** `save_store()` etc. remain deprecated-but-present; removals are v4.0 scope.

---

## 3. PR split (per Codex iter-2 2026-04-19)

### PR-F1 — Benchmark full-mode activation (MUST)

**Amaç:** harness-level `--benchmark-mode=fast|full` flag; real-adapter path live under explicit opt-in; CI default untouched.

**Kontrat:**
- Extend `tests/benchmarks/conftest.py` with a `--benchmark-mode` pytest option (default `fast`, accepts `full`).
- `mock_adapter_transport` only patches when fast-mode; full-mode dispatches to real `invoke_cli` / `invoke_http`.
- Full-mode requires `context_pack_ref` on the invocation (`input_envelope` field), env-gated secrets resolved through the existing `_internal/secrets` provider, and a sandbox-safe workspace profile override.
- **Secret ID canonicalization** — bundled `policy_secrets.v1.json` currently allowlists `OPENAI_API_KEY`/`GITHUB_TOKEN`; docs reference `ANTHROPIC_API_KEY`/`GH_TOKEN`. F1 ships as the single ship-blocker item to pick the canonical set (and update bundled defaults + docs in lockstep).
- New ops runbook: `docs/BENCHMARK-FULL-MODE.md` (secrets, workspace override, disposable repo warning, run command).
- README gets one link to the runbook.

**Exit criteria:**
- `pytest tests/benchmarks/ -q` (fast) still green with zero behaviour change.
- `pytest tests/benchmarks/ -q --benchmark-mode=full` exercises at least one scenario through real `invoke_cli` with `context_pack_ref`.
- `.github/workflows/test.yml` unchanged.
- `docs/BENCHMARK-FULL-MODE.md` covers secrets + ops + disposable-repo warning.

**Ship class:** `MUST` for v3.7.

**Risks:**
- Test: high (nondeterminism, secret drift, real PR creation risk).
- Release: high (secret leakage if docs/defaults drift).
- Mitigation: canonicalization is a ship-blocker; no new CI path; runbook explicitly warns against main repo.

---

### PR-F2 — Real cost reconcile + scorecard `real_adapter` (MUST)

**Amaç:** Shim-dependent budget drain removal; scorecard's `cost_source` field picks `"real_adapter"` when full-mode runs produce real `llm_spend_recorded` events.

**Kontrat:**
- Remove `tests/benchmarks/mock_transport.py::_maybe_consume_budget` (benchmark-only shim).
- Under `--benchmark-mode=full`, the real `post_adapter_reconcile` middleware (PR-C3, already shipped v3.3.0) is the sole budget-drainer.
- Benchmark workspace override enables `policy_cost_tracking.v1.json::enabled=true` (bundled default is dormant) so the full-mode path observes real reconcile.
- `ao_kernel/_internal/scorecard/collector.py` — `cost_source` picks `"real_adapter"` when any `llm_spend_recorded` event fires; otherwise `"mock_shim"` (fast-mode preserved).
- `ao_kernel/_internal/scorecard/render.py` — footer text adapts: `mock_shim` → "benchmark-only; not real billing"; `real_adapter` → "real adapter spend".

**Exit criteria:**
- Fast-mode scorecard keeps `cost_source="mock_shim"` (unchanged).
- Full-mode scorecard emits `cost_source="real_adapter"`.
- No more run-state direct cost drain from benchmark harness code.
- `llm_spend_recorded.source="adapter_path"` observed in full-mode events.

**Ship class:** `MUST` for v3.7.

**Risks:**
- Test: medium (cost policy fail-closed could break benchmark coverage if misconfigured).
- Release: medium.
- Depends on: PR-F1 (full-mode path must exist first).

---

### PR-F3 — v3.6 observability cleanup (NICE-TO-HAVE)

**Amaç:** Small follow-up absorbing Codex's non-blocking E2 review note — consultation lines now count toward `max_tokens` but `items_included/items_excluded/selection_log` still count only classical lane items (telemetry drift).

**Kontrat:**
- `ao_kernel/context/context_compiler.py` — consultation lines accumulate into `items_included`, `items_excluded`, and emit `selection_log` entries (lane=`consultation`).
- Test updates: `tests/test_context_consultation_lane.py` pins the consultation accounting.
- `docs/CONSULTATION-QUERY.md` note on telemetry semantics.

**Exit criteria:**
- `items_included + items_excluded` matches the pre-truncation candidate set across all 4 lanes.
- `selection_log` entries exist for dropped consultations (lane=`consultation`, reason=`budget exceeded`).

**Ship class:** `NICE-TO-HAVE` for v3.7. Defer to v3.8 PR-H1 or dedicated v3.6.1 patch if capacity tight.

**Risks:**
- Build: low.
- Test: low-medium.
- Release: low (additive only, no contract break).

---

## 4. Sequencing

```
F1 (full-mode activation) → F2 (cost reconcile wiring)
                              ↓
                           F3 (observability cleanup — sidecar, merge-order-agnostic)
                              ↓
                           release(v3.7.0)
```

Per two-gate rule: plan-time CNS per PR, impl, post-impl review, admin-squash merge.

**Paralelism option:** F3 impl can happen in parallel with F1 plan-time iter (independent files, no contract overlap). F2 depends on F1 merged.

---

## 5. v3.8 forward reference (Rolling Hardening)

Per Codex iter-2 split — recorded here for continuity, not v3.7 scope:

| PR | Scope | Ship |
|---|---|---|
| PR-H1 | `_internal` coverage tranche (omit list daraltma) | MUST |
| PR-H2 | FS lock parity audit (every-write-path check) | MUST |
| PR-H3 | `save_store()` deprecation cleanup (2 test call-sites) | DEFERABLE |
| PR-H4 | `quality_waiver` dead-or-enforce decision | MUST |

Codex recommended sequence: `H2 → H1 → H4 → H3`.

**Open for v3.8 plan-time:** whether to REMOVE `quality_waiver` (Codex default recommendation) or revive with required rationale + reporting contract.

---

## 6. Explicit non-contracts

- v3.7 does NOT activate tool-use loops, nor runtime enforcement of dormant `policy_tool_calling` fields.
- v3.7 does NOT introduce a v3.6.1 patch — F3 absorb suffices for the lone residual observability drift.
- v3.7 does NOT extend scorecard trend / sparkline (still v3.6+ deferred).
- `save_store()` stays deprecated-but-present until v4.0; v3.8 H3 only cleans call-sites.
