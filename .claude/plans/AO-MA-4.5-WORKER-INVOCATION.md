# AO-MA-4.5 — Worker Invocation (deterministic local worker fixture + result emit)

**Status:** implemented (code + schema + tests). Closes the AO-MA dogfooding gap where AO-MA-4 prepared worktrees but no worker ever wrote `worker_result.v1`.
**Date:** 2026-05-29
**Parent:** AO-MA-1 §8 phased plan slice AO-MA-4.5
**Cross-AI consultation:** Codex thread `019e74ef-06a2-7ac3-8cf7-d59d2ac9e27a` (iter-1 REVISE → iter-2 AGREE, `ready_for_impl=true`)
**Support impact:** none
**Production platform claim:** false
**Live adapter execution:** false

## 1. Why

Before AO-MA-4.5, the AO-MA orchestration layer never spawned a worker. AO-MA-3
emitted a task graph, AO-MA-4 prepared worktrees and recorded an
`expected_worker_result_path` per worker, but the file at that path was never
written by any runtime code — the real implementer work happened OUTSIDE
ao-kernel (Claude Code / Codex under human direction). The pipeline could
review/verify/integrate `worker_result.v1` artifacts but could not *produce*
one. AO-MA-4.5 is the producer slice: it makes the orchestration layer drive a
real worker and emit `worker_result.v1`, so the full chain
`plan → spawn → invoke → review → verify → integrate` runs end-to-end on the
repo's own machinery (dogfooding).

## 2. Scope (v1) — deterministic local worker only

AO-MA-4.5 v1 invokes a **pinned deterministic local worker fixture**, not a
live LLM. This keeps `live_adapter_execution=false` (the GPP guard) honest:
real LLM worker execution (e.g. `claude-code-cli`) requires a separate
operator-bound GPP supersession with `live_adapter_execution=true` and is out
of scope. The AO-MA-1 §8 row historically said "LLM-driven"; that remains the
long-term intent, but the v1 acceptance carries **no live-LLM claim**.

Files:

1. `ao_kernel/fixtures/ao_ma_worker_stub.py` — deterministic worker fixture,
   promoted from the AO-MA-8 in-file surrogate (`_emit_mock_worker_result`) to
   a runtime module. Modifies one file from `declared_write_set` in the
   prepared worktree, commits it, derives `head_sha` + `actual_changed_files`
   from real git state, writes a schema-valid `worker_result.v1.json`
   (`worker.provider="local"`).
2. `ao_kernel/orchestration/worker_invoker.py` — `WorkerInvoker.invoke()`:
   reads the AO-MA-4 `runner_report.v1.json`, invokes the pinned fixture for
   each eligible worker (subprocess), validates the emitted `worker_result`,
   bridges it into the base_dir consumption point, and emits a schema-valid
   invocation report.
3. `ao_kernel/defaults/schemas/ao-ma-worker-invocation-report.schema.v1.json` —
   governance-grade invocation report schema (`additionalProperties:false`,
   guard flags `const false`, `fixture_id` `const "ao-ma-worker-stub"`).
4. `ao_kernel/orchestration/cli_handlers.py` + `ao_kernel/cli.py` —
   `ao-kernel orchestration invoke --manifest <path>` (no `--adapter` flag).
5. `tests/test_ao_ma_4_5_worker_invocation.py` — 26 tests (smoke + full chain +
   negative + trust-boundary + worktree-gate + fixture/binding unit tests).

## 3. Design decisions (Codex AGREE)

- **Glue = orchestration-native (option B).** The invoker does NOT reuse
  `executor.run_step`. That path owns its own worktree lifecycle (it would
  bypass the AO-MA-4 worktree truth) and has no native AO-MA
  `live_adapter_execution` gate. The invoker is a thin layer over the
  runner_report truth.
- **Producer = fixture writes worker_result, invoker does not synthesize it.**
  `head_sha`, `actual_changed_files`, worker identity, and the no-secret
  attestation come from the fixture's real git state — not mapped from an
  adapter's stdout (which would be inventing provenance).
- **No arbitrary adapter selection.** `invoke(fixture_id=...)` only accepts the
  pinned `ao-ma-worker-stub`; a live adapter or `live_adapter_execution=true`
  manifest is rejected fail-closed. The CLI exposes no adapter flag.
- **Worker identity = `local`.** `worker_result.worker.provider="local"` is the
  honest identity (a deterministic local fixture, not a live provider). The
  assignment's planned `agent.provider` (AO-MA-3 metadata, default `anthropic`)
  may differ — no AO-MA layer enforces equality (verified against
  `integrator.py`, `reviewer.py`, `verifier.py`, `worker_runner.py`). A
  regression test pins this so a future (incorrect) equality check cannot
  silently break the chain.
- **Eligible runner statuses = `prepared`, `skipped_existing_idempotent`.**
  Every other status (e.g. `skipped_dry_run`, `failed_*`) is recorded as
  `skipped_not_eligible`; the invoker writes no worker_result for it.

## 4. Producer SSOT vs pipeline consumption — the bridge

AO-MA-4 records `expected_worker_result_path = <worktree_root>/worker_result.v1.json`
(the producer SSOT — the worker writes its result next to where it worked).
But AO-MA-5/6/7 fail-closed on evidence paths **outside the manifest base_dir**
(`<base_dir>/<task_graph_id>/…`) to preserve audit provenance
(`integrator.py::_relativize`, `reviewer.py::_relativize`). A worktree —
especially a realistic one parented outside the repo (`../ao-kernel-feat-X`) —
is never under base_dir.

Plan-time Codex AGREE did not surface this; it was found during
implementation. The resolution keeps the AO-MA-4 SSOT intact and adds a
**bridge**: after the fixture writes `worker_result.v1.json` at the worktree
root, the invoker copies it to the canonical consumption point
`<base_dir>/<task_graph_id>/workers/<task_id>/worker_result.v1.json` and records
both paths in the invocation report (`worker_result_path` = worktree SSOT,
`integrated_worker_result_path` = base_dir copy). The downstream chain consumes
the bridged copy. This makes the chain work regardless of worktree location.

This bridge is recorded for the post-impl cross-AI review: it is a small,
SSOT-preserving addition to the AGREE'd plan (the worktree root remains the
producer truth; the copy is the integration handoff), not a deviation from it.

## 5. Known limitation

- v1 worker is a deterministic local fixture; it does not perform real
  implementation logic. `worker_result.tests_run` is empty and `known_gaps`
  states the fixture nature explicitly.
- The `worker_result.v1.json` written at the worktree root stays untracked.
  Cleaning the worktree after AO-MA-4.5 is a separate operator step; AO-MA-4.5
  makes no end-to-end lifecycle-clean claim.
- Real LLM worker execution is deferred to a future slice gated by an
  operator-bound GPP supersession (`live_adapter_execution=true`).

## 6. Hard stops

- No support widening; `support_widening=false`.
- No production platform claim; `production_platform_claim=false`.
- No live adapter execution; `live_adapter_execution=false`.
- No GitHub write (no `git push`, no `gh pr create`).
- No branch-protection / ruleset / workflow / CODEOWNERS mutation.
- No `gpp_status.v1.json` mutation.
- No executor coupling (orchestration-native invoker).

## 7. Acceptance

1. `ao-ma-worker-invocation-report.schema.v1.json` validates as Draft 2020-12.
2. Layer 1 (smoke): `spawn → invoke` writes a schema-valid `worker_result.v1.json`
   at the runner's expected path; guard flags closed; `actual_changed_files ⊆
   declared_write_set`; `head_sha` is a real commit; invocation report
   schema-valid + persisted.
3. Layer 2 (full chain): `plan → spawn → invoke → review → verify → integrate`
   reaches `IntegrationDecision.overall_status == "all_accepted"` with a
   cross-provider chain (worker=local, reviewer=openai, verifier=tool), using
   the runtime `WorkerInvoker.invoke()` (not the AO-MA-8 surrogate).
4. Negatives: arbitrary adapter rejected; open `live_adapter_execution`
   rejected; non-eligible runner status skipped.
5. Trust boundary fail-closed: manifest envelope + runner_report manifest_sha256
   + assignment_sha256 + assignment schema + cross-ref + worktree-root expected
   path are all checked before the fixture runs; the emitted worker_result is
   bound to this graph/task/base/branch before the bridge copy. Fixture rejects
   absolute / traversal declared paths.
6. 26 tests pass; ruff + mypy clean.
7. Cross-provider post-impl review records AGREE.
