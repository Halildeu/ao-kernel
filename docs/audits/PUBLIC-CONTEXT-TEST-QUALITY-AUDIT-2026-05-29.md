# Public Context Pipeline Test-Quality Audit — 2026-05-29

A **coverage-driven** test-quality audit for the `ao_kernel/context/` pipeline
(the governed memory loop). Follows the same methodology as the public-facade
audit (`docs/audits/PUBLIC-FACADE-TEST-QUALITY-AUDIT-2026-05-29.md`), which
explicitly deferred `ao_kernel/context/` to this follow-up.

> **Not a mutation-coverage audit.** Coverage measures execution, not
> assertion strength. A covered branch is not necessarily a well-asserted
> one. See §1.

## 1. Methodology & limitations

- **Instrument**: `coverage.py` branch coverage via `pytest-cov`, JSON report,
  full suite.
- **"Covered" ≠ "well asserted"**: high coverage is necessary, not sufficient.
- **Classification labels** (assigned by source inspection, per Codex
  CNS thread 019e7547 — part-level, not module-level):
  - 🔴 **actionable_offline** — pure-Python / cache / config / selection /
    rerank / fail-closed / corruption / budget logic that is testable
    *without* a live provider or database.
  - 🌐 **external_integration** — live provider HTTP (embeddings) or live
    Postgres+pgvector backend; out of scope for offline unit tests, covered
    only by optional integration evidence.
  - ⚪ **intentionally_uncovered** — defensive fallback (`except: logging
    .warning(...)`) where a test would assert little.
- **Scope**: all 18 `ao_kernel/context/` modules in §2; §3 actionable analysis
  concentrates on the 5 modules below 85%.

## 2. Module coverage (full suite, head a124c3b, branch coverage)

| Module | Cov % | Stmts | Miss | M.Branch | Tier |
|---|---:|---:|---:|---:|---|
| semantic_retrieval.py | 63.3% | 75 | 28 | 12 | 🔴+🌐 priority |
| checkpoint.py | 79.2% | 59 | 9 | 7 | 🔴 fail-closed |
| memory_tiers.py | 80.0% | 54 | 12 | 2 | 🔴 config/time |
| context_compiler.py | 84.2% | 196 | 22 | 21 | 🔴 priority (blast radius) |
| session_lifecycle.py | 84.6% | 37 | 6 | 0 | ⚪ mostly defensive |
| vector_store_pgvector.py | 86.1% | 67 | 11 | 0 | 🌐 optional backend |
| agent_coordination.py | 88.5% | 77 | 7 | 3 | watchlist |
| canonical_store.py | 88.7% | 155 | 17 | 5 | watchlist |
| vector_store.py | 88.9% | 39 | 5 | 0 | watchlist |
| context_injector.py | 89.7% | 74 | 2 | 10 | watchlist |
| memory_pipeline.py | 90.2% | 31 | 3 | 1 | ok |
| vector_store_resolver.py | 90.3% | 85 | 7 | 4 | ok |
| embedding_config.py | 92.4% | 56 | 4 | 1 | 🔴 config (offline) |
| decision_extractor.py | 93.0% | 79 | 3 | 5 | ok |
| profile_router.py | 98.3% | 42 | 0 | 1 | ok |
| __init__.py | 100.0% | 9 | 0 | 0 | ok |
| self_edit_memory.py | 100.0% | 37 | 0 | 0 | ok |
| semantic_indexer.py | 100.0% | 39 | 0 | 0 | ok |

Total: 1211 statements, 18 modules. Aggregate context/ coverage feeds the
repo-wide 86.91% (full suite this run).

## 3. Actionable gaps (5 low-coverage modules)

Per Codex guidance, low coverage on embedding/vector modules is **not**
wholesale "external dependency" — the offline paths are testable and remain
actionable.

### semantic_retrieval.py (63.3% — priority 1: lowest + boundary)

| Lines | What | Tier | Suggested test |
|---|---|---|---|
| 50–73 | `embed_text`: build_embeddings_request + execute_http_request + non-OK status | 🌐 external | optional integration; offline: mock transport for status!=OK error path |
| 99–115 | `embed_decision`: provider/model resolution + cache skip | 🔴 actionable | embedding cache hit/skip without re-embedding (no provider call) |
| 123–125 | `decision["_embedding"]` cache write | 🔴 actionable | assert cache populated/reused |
| 163–168 | `semantic_search` provider/model | 🌐 external | optional |
| 192 | `return []` empty/non-list embedding skip | 🔴 actionable | empty query / non-list embedding → `[]` |

### context_compiler.py (84.2% — priority 1: 196 stmt, largest blast radius)

| Lines | What | Tier | Suggested test |
|---|---|---|---|
| 155 | `item.included = False` budget exclusion | 🔴 actionable | budget overflow → item excluded from compiled context |
| 258 | `except Exception` telemetry fallback | ⚪ defensive | low value |
| 338, 346 | relevance score constants (0.3 / 0.8) | 🔴 actionable | rerank scoring branches |
| 397 | `content` list branch | 🔴 actionable | message content as list normalization |
| 425–439 | semantic rerank `sim_map` build + sort | 🔴 actionable | rerank ordering with similarity map |

### checkpoint.py (79.2% — fail-closed integrity)

| Lines | What | Tier | Suggested test |
|---|---|---|---|
| 90, 102 | `raise CheckpointError(...)` | 🔴 actionable | corrupt/invalid checkpoint → CheckpointError |
| 106 | `except (ValueError, TypeError)` | 🔴 actionable | malformed cursor parse |
| 112 | `has_provider_cursor` resume metadata | 🔴 actionable | resume metadata flag set |
| 147 | `except (json.JSONDecodeError, OSError)` | 🔴 actionable | corrupt checkpoint file fail-closed |

### memory_tiers.py (80.0% — config / time edges)

| Lines | What | Tier | Suggested test |
|---|---|---|---|
| 40–43 | `float(confidence)` coercion try | 🔴 actionable | non-numeric confidence coercion |
| 94–112 | `load_default` + `datetime.now` + `except` | 🔴 actionable | tier config load + age computation edge |

### session_lifecycle.py (84.6% — mostly defensive)

| Lines | What | Tier | Suggested test |
|---|---|---|---|
| 89–91 | `except Exception: logging.warning("distillation failed")` | ⚪ defensive | low value |
| 104–106 | `except Exception: logging.warning("promotion failed")` | ⚪ defensive | low value |

session_lifecycle's misses are defensive logging fallbacks; its 84.6% is not
a behavioral risk. Listed for completeness, not prioritized.

## 4. Watchlist (85–90%, not prioritized)

vector_store_pgvector.py (🌐 optional Postgres+pgvector backend — import guard
/ dimension / namespace / mocked-connection paths testable; live DB E2E is a
separate optional dependency lane), agent_coordination.py, canonical_store.py,
vector_store.py, context_injector.py. These have adequate coverage; no
critical fail-closed surface is currently uncovered.

## 5. Run metadata (reproducibility)

| Field | Value |
|---|---|
| Repo head SHA | `a124c3b` |
| Date | 2026-05-29 |
| OS | Darwin 25.5.0 arm64 |
| Python | 3.13.6 |
| coverage | 7.13.4 (branch) |
| pytest-cov | 7.0.0 |
| Command | `pytest tests/ --cov=ao_kernel.context --cov-branch --cov-report=json` |
| Full suite | 4642 passed, 76 skipped, 141s |
| Coverage JSON | generated locally; **not committed** (table above is the durable artifact) |

## 6. Follow-up PR candidates (clustered)

- **HYG-PUBLIC-CONTEXT-GAPS-01** — semantic_retrieval offline (cache skip,
  empty/non-list embedding) + context_compiler rerank/budget/selection
  branches (priority 1).
- **HYG-PUBLIC-CONTEXT-GAPS-02** — checkpoint + session_lifecycle fail-closed:
  CheckpointError raises, corrupt-file `OSError`/`JSONDecodeError`, resume
  metadata. (session_lifecycle defensive logging excluded.)
- **HYG-PUBLIC-CONTEXT-GAPS-03** — memory_tiers confidence coercion + tier
  config/age edges + embedding_config env/policy precedence + secret repr
  boundary.
- **(optional) HYG-PUBLIC-CONTEXT-PGVECTOR-INTEGRATION** — pgvector mocked-unit
  coverage + optional live-DB integration evidence (separate optional
  dependency lane; not an offline unit-test cluster).

## 7. Scope boundary (this audit PR)

Doc-only. No `ao_kernel/context/*`, no `tests/*`, no `pyproject.toml`, no
`.github/workflows/*`, no `gpp_status.v1.json`, no guard flag or
support/production claim change. Coverage JSON generated locally and excluded
from the committed diff.
