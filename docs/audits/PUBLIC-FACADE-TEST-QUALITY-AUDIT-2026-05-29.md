# Public Facade Test-Quality Audit — 2026-05-29

A **coverage-driven** public-facade test-quality audit for the seven
top-level `ao_kernel/` facade modules. This audit identifies branch- and
line-coverage gaps, classifies each gap by source inspection, and proposes
clustered follow-up test PRs.

> **This is not a mutation-coverage audit.** Coverage measures whether a line
> or branch executed during the test run; it does **not** prove that the
> behavior was asserted. See §1 Methodology & Limitations.

## 0. Tool selection (attempted mutation audit)

The original plan was a mutation-coverage audit using `mutmut`. That tool
could not produce a result in this local environment:

- **Tool**: `mutmut`, version **3.5.0**
- **Command attempted**: `python -m mutmut run --max-children N` with
  `[tool.mutmut]` `paths_to_mutate` / `tests_dir` overridden to the targeted
  module and `tests/`
- **Observed failures (local macOS environment, Darwin 25.5.0 arm64,
  Python 3.13.6)**:
  1. With the repo's string-form config (`paths_to_mutate = "ao_kernel/"`,
     `tests_dir = "tests/"`), the path string was iterated character by
     character, so the pytest invocation received
     `['t', 'e', 's', 't', 's', '/']` and raised
     `BadTestExecutionCommandsException`.
  2. After switching to list-form config, `mutmut`'s `mutants/` working
     directory received only `paths_to_mutate` + `tests_dir`; the repo's
     `scripts/` package (imported by several tests) was absent, raising
     `ModuleNotFoundError: No module named 'scripts'`.
  3. After manually copying `scripts/` into `mutants/`, the stats-collection
     pytest invocation still raised `BadTestExecutionCommandsException`,
     while the same suite runs cleanly (`4629 passed, 76 skipped`) in the
     primary worktree.

These failures were observed **only** in this local macOS environment; no
minimal upstream reproduction was prepared, so no upstream defect claim is
made here. Per the No-Fake-Work rule, no synthetic mutation result was
fabricated. Per the long-term-fix rule, the tool was swapped rather than
patched ad hoc: the audit's value proposition (find weak test surface on the
public facade) is preserved while the measurement instrument changes from
mutation coverage to branch coverage.

A follow-up (`HYG-MUTATION-AUDIT-V2`) may evaluate a `mutmut` downgrade,
config compatibility, or an alternative mutation tool such as `cosmic-ray`.

## 1. Methodology & limitations

- **Instrument**: `coverage.py` branch coverage via `pytest-cov`, JSON report.
- **What a gap means**: a line or branch arc that no test executed.
- **What coverage does NOT prove**: that an executed line was *asserted*. A
  test can drive a branch and assert nothing; coverage still marks it covered.
  Therefore **"covered" ≠ "well asserted"**, and a high coverage percentage is
  a *necessary, not sufficient* condition for behavioral test quality. This
  audit deliberately makes no "covered == verified" claim.
- **Classification labels** (assigned by source inspection):
  - 🔴 **critical** — narrowly defined: a public-API behavior, a
    fail-closed / security / policy branch, a secret boundary, a guardrail,
    explicit error handling, or a backwards-compatible SDK surface.
  - 🟡 **untested_path** — an actionable but non-critical path: an edge case,
    feature branch, or facade delegation that should have a focused test.
  - ⚪ **intentionally_uncovered_or_unreachable** — defensive fallback
    (`except: pass`), import-guard branch, or otherwise low-value code where a
    test would assert little. (Label chosen over "equivalent" to avoid
    importing mutation-testing semantics.)
- **Scope**: the seven top-level facade modules. `ao_kernel/_internal/`
  remains out of scope under the D13 staged-coverage decision.
  `ao_kernel/context/` is deferred to a follow-up audit.

## 2. Module-by-module coverage

Source SHA `ea4edf43`. Values from the coverage JSON described in §5 (the JSON
artifact itself is not committed).

| Module | Stmts | Miss | Branch | Partial | Cov % | Actionable gaps |
|---|---:|---:|---:|---:|---:|---:|
| `ao_kernel/governance.py` | 119 | 3 | 60 | 9 | 93.3% | 4 |
| `ao_kernel/llm.py` | 138 | 15 | 40 | 4 | 87.1% | 3 |
| `ao_kernel/client.py` | 373 | 47 | 88 | 8 | 87.6% | 3 |
| `ao_kernel/config.py` | 64 | 3 | 30 | 3 | 93.6% | 3 |
| `ao_kernel/policy.py` | 14 | 5 | 0 | 0 | 64.3% | 2 |
| `ao_kernel/workspace.py` | 28 | 0 | 4 | 0 | 100.0% | 0 |
| `ao_kernel/tool_gateway.py` | 165 | 7 | 62 | 6 | 94.3% | 4 |

`workspace.py` is fully covered (line + branch); no gaps.

`policy.py` shows the lowest percentage (64.3%), but its gaps are thin facade
delegations (see §3), not behavioral risk — a reminder that a raw percentage
is a poor risk signal on its own.

## 3. Critical gaps (🔴)

These are the fail-closed / input-validation / security branches that no test
currently drives. Each is a candidate for a focused negative test.

| Module | Line(s) / arc | Behavior | Suggested test target |
|---|---|---|---|
| `config.py` | 115 | `workspace.json` is valid JSON but not an object → `WorkspaceCorruptedError` | Load a workspace whose `workspace.json` top-level is a list / scalar; assert `WorkspaceCorruptedError`. |
| `config.py` | 145 | Bundled default is valid JSON but not an object → `DefaultsNotFoundError` | Force a non-object bundled default (monkeypatch loader text); assert `DefaultsNotFoundError`. |
| `config.py` | 164 | Workspace override file is not an object → `DefaultsNotFoundError` | Write a non-object override JSON; assert `DefaultsNotFoundError`. |
| `llm.py` | 104–115 (arc 101→117) | Provider-guardrails policy path: when a workspace guardrails policy exists and **denies** the provider/model, `build_request` raises `ValueError`. The entire guardrails branch is uncovered. | With a workspace guardrails policy that denies a provider/model, assert `build_request` raises `ValueError` carrying `reason_codes`; and a positive case where it is allowed. |
| `tool_gateway.py` | 119 | `blocked_tools` not a list → `ValueError` | Construct a `ToolGateway` policy with `blocked_tools` as a string; assert `ValueError`. |
| `tool_gateway.py` | 122 | `blocked_tools` entries not `str` → `ValueError` | `blocked_tools` containing a non-string; assert `ValueError`. |
| `tool_gateway.py` | 143 | `cycle_detection` not an object → `ValueError` | `cycle_detection` as a scalar; assert `ValueError`. |
| `tool_gateway.py` | 151 | `cycle_detection.enabled` not bool (strict, no coercion) → `ValueError` | `cycle_detection.enabled` as `1`/`"true"`; assert `ValueError`. |
| `governance.py` | arcs 190→201, 209→214, 215→220, 221→230 | Provider-guardrails and generic-rules edge branches (`PROVIDER_DISABLED`, `MODEL_NOT_ALLOWED`, `BLOCKED_VALUE`, `LIMIT_EXCEEDED`) — partial branch coverage. | Targeted policy fixtures that trigger each violation code individually. |

## 4. Non-critical actionable gaps (🟡)

| Module | Line(s) | Behavior | Note |
|---|---|---|---|
| `policy.py` | 32–33 | `load()` facade → `config.load_with_override` | Thin delegation; a focused test pins the contract. |
| `policy.py` | 38–40 | `list_policies()` → bundled policy enumeration | A test asserting non-empty list + `.json` filter pins the contract. |
| `llm.py` | 266, 268 | `count_tokens()` facade → internal token counter | Delegation; pin with a known-message token count. |
| `client.py` | 396–405 | Session-resume path: load prior context, set active | Edge path behind `resume and ws`; an integration test would cover it. |
| `client.py` | 593–617 | Streaming build-request-with-context branch | Streaming + active-session edge; covered partially. |
| `governance.py` | 106, 110 | Tool-calling / provider-guardrails dispatch detection | Partial branch on policy-type auto-detection. |

## 4b. Intentionally uncovered / unreachable (⚪)

Not proposed for new tests; recorded for completeness:

- `llm.py` 325–335 — `except Exception: pass` fallbacks around canonical /
  workspace-facts loading (defensive; failure is silently tolerated by design).
- `client.py` various `except Exception: pass` fallbacks around optional
  context loading.
- Import-guard branches (`except (FileNotFoundError, ImportError): pass`).

## 5. Run metadata (reproducibility)

| Field | Value |
|---|---|
| Repo head SHA | `ea4edf43` |
| Date | 2026-05-29 |
| OS | Darwin 25.5.0 arm64 (local macOS) |
| Python | 3.13.6 |
| pytest | 9.0.2 |
| pytest-cov | 7.0.0 |
| coverage | 7.13.4 |
| Branch coverage | enabled (`--cov-branch`) |
| Coverage config source | `pyproject.toml` (`[tool.coverage]`) |
| Full-suite health run | `pytest tests/ --cov=ao_kernel --cov-branch` → 4629 passed, 76 skipped, 149.74s |
| Audit-aligned command | `python3 -m pytest tests/ --ignore=tests/benchmarks --cov=ao_kernel --cov-branch --cov-report=json:<path> --cov-report=term-missing` |
| Coverage JSON | generated locally for extraction; **not committed** (table above is the durable artifact) |

## 6. Follow-up PR candidates (clustered)

Per the long-term-fix discipline, follow-up tests are clustered by risk area,
not one-PR-per-gap:

- **`HYG-PUBLIC-FACADE-GAPS-01`** — `config.py` corrupt-input fail-closed
  branches (115, 145, 164) + `governance.py` policy-violation edge codes
  (`PROVIDER_DISABLED`, `MODEL_NOT_ALLOWED`, `BLOCKED_VALUE`, `LIMIT_EXCEEDED`).
- **`HYG-PUBLIC-FACADE-GAPS-02`** — `tool_gateway.py` policy input-validation
  `ValueError` branches (119, 122, 143, 151) — strict type validation,
  no silent coercion.
- **`HYG-PUBLIC-FACADE-GAPS-03`** — `llm.py` provider-guardrails deny/allow
  path (104–115) + `count_tokens` / `policy.py` facade delegation pins.
- **`HYG-MUTATION-AUDIT-V2`** — evaluate `mutmut` downgrade / config
  compatibility / `cosmic-ray` as a true mutation-coverage instrument.
- **`HYG-PUBLIC-CONTEXT-TEST-QUALITY-AUDIT`** — second coverage/test-quality
  audit for `ao_kernel/context/` public exports.

## 7. Scope boundary (this audit PR)

This PR is **doc-only**. It does not add tests, and it does not modify:

- `pyproject.toml` (including `[tool.mutmut]` config)
- any `.github/workflows/*`
- `.claude/plans/gpp_status.v1.json`
- any guard flag JSON or production / support / promotion decision artifact
- any `ao_kernel/` runtime module
- any `tests/*` file

The coverage JSON and any `mutmut` working directories produced during the
audit are intentionally left out of the committed diff.
