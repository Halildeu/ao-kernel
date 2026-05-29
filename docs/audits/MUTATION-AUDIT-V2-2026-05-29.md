# Mutation Audit V2 — 2026-05-29

A bounded, audit-only **mutation-testing tool evaluation** plus a real
mutation result for one module. Follow-up to the public-facade audit
(`docs/audits/PUBLIC-FACADE-TEST-QUALITY-AUDIT-2026-05-29.md` §0), where
`mutmut` 3.5.0 could not run on this local macOS environment and the audit
pivoted to coverage. This V2 evaluates `mutmut` 2.4.5.

> **No fabricated scores.** Where the tool produced a trustworthy result it is
> reported; where it produced an anomalous result it is documented as a tool
> limitation, not synthesized into a mutation score.

## 0. Tool setup

- **Tool**: `mutmut` 2.4.5 (3.5.0's three macOS failures documented in the
  public-facade audit §0).
- **Isolation**: a disposable venv at `/tmp/ao-kernel-mutation-venv`
  (`python3 -m venv` + `pip install -e . pytest jsonschema tenacity tiktoken
  mutmut==2.4.5`). The repo's global `mutmut` 3.5.0 was left untouched; the
  `[dev]` extra was deliberately NOT installed (its unpinned `mutmut` would
  pull 3.5.0 again). venv removed after the run.
- **Targets** (Codex CNS thread 019e753e, targeted GAPS cluster): the 3 GAPS
  modules — `ao_kernel/config.py`, `ao_kernel/tool_gateway.py`,
  `ao_kernel/llm.py`.
- **Config**: CLI overrides only (`--paths-to-mutate`, `--tests-dir`,
  `--runner`). `pyproject.toml [tool.mutmut]` was NOT modified.
- **`mutmut results` CLI is broken on Python 3.13**: pony ORM 0.7.19 bytecode
  decompilation raises. Results were read **directly from the SQLite
  `.mutmut-cache`** (`Mutant.status` grouped counts) — real run data, no
  synthesis.

## 1. Results

| Module | Total | Killed | Survived | Suspicious | Mutation score | Trust |
|---|---:|---:|---:|---:|---:|---|
| config.py | 60 | 47 | 13 | 0 | **78.3%** | ✅ trustworthy |
| tool_gateway.py | 220 | 0 | 65 | 155 | N/A (tool anomaly) | ❌ not reported |
| llm.py | 167 | 0 | 140 | 27 | N/A (tool anomaly) | ❌ not reported |

Raw `killed/survived/suspicious` counts are shown for transparency; the
**score column is deliberately N/A** for the two anomaly rows so the `0
killed` figure is never read as a published "0% mutation score" (see §3).

**Only config.py is a trustworthy mutation result.** tool_gateway.py and
llm.py reported 0 killed with high survived/suspicious counts — not a real
"0% mutation score" but a mutmut-2.4.5 malfunction on this codebase (see §3).

## 2. config.py — trustworthy result (78.3%)

47/60 killed. The 13 survived mutants cluster almost entirely on
**error-message string mutations** inside `raise XError(f"...")` statements
(lines 45, 106, 111, 114, 117, 135, 141, 144, 163) plus a few
`workspace_root`/`resolve` control-flow lines (49, 86, 88, 89).

**Actionable finding (assertion strength gap):** the GAPS tests added in
PR #751 assert error conditions with `pytest.raises(XError, match="substring")`.
mutmut mutates the message string (e.g. wraps it `XX...XX`), but the asserted
substring still matches, so the mutant survives. Coverage marked these lines
covered; mutation testing reveals the assertions do not pin the exact message.

This is the kind of gap mutation testing exists to find, and it is real and
low-severity (message text, not behavior).

## 3. tool_gateway.py + llm.py — mutmut 2.4.5 anomaly (not a score)

Both reported **0 killed** despite having substantial test suites
(`test_tool_gateway.py` ~60 tests, `test_llm_facade.py` test classes). A true
0% is implausible; this is a tool/runner interaction failure. Root cause is a
**hypothesis** (no minimal mutmut repro/trace was produced), supported by an
observed contrast with config.py:

- **llm.py (0 killed / 140 survived / 27 suspicious)**: *likely* import-timing.
  `test_llm_facade.py` imports the module **inside each test function**
  (`from ao_kernel.llm import build_request`), whereas `test_config.py`
  (which worked) imports at module top. The contrast *suggests* mutmut 2.4.5's
  mutant injection may not reach a module imported lazily after the test
  process has started, leaving mutated `llm` code unexercised → survived. Not
  proven without a trace.
- **tool_gateway.py (0 killed / 65 survived / 155 suspicious)**: imports at
  module top, yet 155 mutants are **suspicious** (test suite took long but not
  10× baseline). The large module + the gateway's per-call dispatch *plausibly*
  make the selected-test runner slow enough per mutant that mutmut cannot
  distinguish killed from slow. Also a hypothesis.

Per the No-Fake-Work rule and Codex plan-time guidance, these are reported as
a **tool limitation**, not a 0% mutation score.

## 4. Run metadata

| Field | Value |
|---|---|
| Mutation run base SHA | `a124c3b` (the tree the mutmut run was executed against) |
| PR head SHA | `edf9745` (+ subsequent main-merge commit) |
| Current main base SHA | `318d04d` (main advanced via PR #753 during this PR's lifetime) |
| Date | 2026-05-29 |
| OS | Darwin 25.5.0 arm64 (local macOS) |
| Python | 3.13.6 (venv) |
| mutmut | 2.4.5 (isolated venv) |
| Runner | `pytest tests/test_config.py tests/test_tool_gateway.py tests/test_llm_facade.py -x -q --tb=no` |
| Results source | `.mutmut-cache` SQLite `Mutant.status` counts (`mutmut results` CLI broken on py3.13/pony) |
| venv | removed after run; `.mutmut-cache` not committed |

## 5. Follow-up candidates

- **HYG-MUTATION-CONFIG-HARDEN** — add exact-message assertions for the 13
  config.py survived mutants (or accept message-text mutation as
  out-of-policy and document it). Low severity.
- **HYG-MUTATION-AUDIT-V3** — make mutation testing reliable for
  `tool_gateway`/`llm`: either (a) refactor the lazy in-function imports in
  `test_llm_facade.py` to module-top so mutant injection reaches the module,
  (b) raise mutmut's baseline-time multiplier / per-module runner so
  `tool_gateway` mutants are not all "suspicious", or (c) evaluate
  `cosmic-ray` (session-based, AST-rewrite injection) which does not depend on
  import timing.
- **Decision**: mutation testing is **not** adopted as a repo gate. It remains
  an opt-in, manually-run diagnostic. config.py demonstrates value; the
  tool_gateway/llm anomaly shows the tooling is not yet reliable enough to
  gate on.

## 6. Scope boundary (this audit PR)

Doc-only. No `ao_kernel/*` runtime change, no `tests/*` change, no
`pyproject.toml` mutmut-config change, no workflow, no guard flag, no
`gpp_status.v1.json`. The isolated venv and `.mutmut-cache` are excluded from
the committed diff.
