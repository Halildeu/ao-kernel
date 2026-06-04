# E-3-2 — Per-surface smoke harness scaffolding (decision record)

> V5 Epic 3, slice #854. Infrastructure-only. Library-mode, stub-adapter-only
> smoke harness that emits a `support_widening_evidence.v1` artifact (E-3-1) per
> surface class — **no network, no `.ao/` mutation, no guard-flag flip**.

## Deliverables

- `scripts/run_support_smoke.py --surface <class> [--evidence-out <path>] [--repo …]`
- `ao_kernel/_internal/support_widening/harnesses/killswitch.py` — dominant runtime kill-switch
- `ao_kernel/_internal/support_widening/harnesses/runner.py` — `run_surface_smoke()` + per-surface stub registry
- `tests/test_run_support_smoke.py` (15 cases: parametrized per-surface + kill-switch negatives)

## Three-layer stub-purity discipline

1. **Static (advisory):** forbidden-import set documented; dynamic import bypasses
   a pure AST scan, so it is NOT the enforcement.
2. **Runtime kill-switch (dominant):** `live_call_killswitch()` patches every
   forbidden path to fail closed and restores all originals on exit —
   `socket.socket`, `http.client.HTTPConnection`, `urllib.urlopen`/`OpenerDirector`,
   `requests`/`httpx` send (patched only when importable), `subprocess.*`,
   `os.system`/`os.popen`, forbidden imports via `import` / `__import__` /
   `importlib` / `exec("import …")`, and **env reads** under an **allowlist-only**
   model: `os.environ` / `os.environb` are swapped for sanitized views where every
   read path — direct (`os.environ["X"]` / `get` / `in`), `os.getenv` / `os.getenvb`,
   and bulk (`copy`/`keys`/`items`/`values`/`iter`/`dict()`) — raises for any key
   NOT in the small allowlist (`WORKSPACE_ROOT`, `CI`, `PYTHONPATH`, `PATH`, `HOME`,
   `TMPDIR`). Allowlist-only (not a "secret-looking" regex) closes the gap for
   credential-class keys like `AWS_ACCESS_KEY_ID` / `OPENAI_ORGANIZATION` that a
   regex misses (Codex E-3-2 iter-2 absorb).
3. **Runtime declaration:** `assert_no_live_capability(stub)` rejects any stub
   advertising `live_capability=True`.

The emitted artifact pins `simulated_only: true` + `live_call_made: false` +
`support_widening: false` (schema const + E-3-1 `parse_v1` runtime re-assert), so a
forged "live call" payload is schema-invalid.

## Design deviation from the plan's literal structure (documented)

The plan listed "one module per surface class" + "one test file per surface
class". The five surfaces are near-identical stub shells, so a **registry**
(`_SURFACE_STUBS` in `runner.py`) + **parametrized tests** (one case per surface)
is the DRY/maintainable form (CLAUDE.md long-term-durable-solution rule). Per-surface
behaviour is still fully covered: `test_surface_smoke_emits_valid_pinned_artifact`
runs once per surface class and validates the emitted artifact against the E-3-1
schema, and `test_all_five_surface_classes_present` pins the registry set.

## Lessons applied from earlier slices

- Evidence artifact written `0o600` (CodeQL `py/overly-permissive-file`, caught on E-2-2).
- Calendar-coupling RFC3339 `generated_at` from the E-3-1 schema is reused as-is.

## Out of scope

- Running the harness in CI (E-3-3, high-risk workflow → operator review).
- Live evidence / v2 supersession (Epic 9).

## Cross-AI review

Implementer claude (anthropic) → reviewer codex (openai). See PR evidence.
