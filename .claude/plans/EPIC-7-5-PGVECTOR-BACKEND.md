# V5 Epic 7 E-7-5: pgvector Semantic Backend

> **Risk class:** low-risk (additive; opt-in extra; lazy import)
> **Implementer:** Anthropic Claude / **Reviewer:** OpenAI Codex (post-impl)

## 1. Scope

Pluggable semantic-retrieval backend protocol with two implementations:
default in-memory (no extras) and opt-in pgvector (requires
`[pgvector]` extra). Backend selection is operator-owned; no automatic
detection. Default = in-memory; the existing pure-Python cosine path
in `semantic_retrieval.py` remains the SSOT for similarity math.

**In scope:**
- `ao_kernel/context/semantic_backends/__init__.py` (public API)
- `ao_kernel/context/semantic_backends/base.py` (`SemanticBackend` Protocol + `SemanticSearchResult` + `SemanticBackendError`)
- `ao_kernel/context/semantic_backends/in_memory.py` (default; wraps existing cosine)
- `ao_kernel/context/semantic_backends/pgvector.py` (opt-in; lazy `psycopg2` + `pgvector` import)
- 20 invariant tests (+2 skipped: missing-extras branch + live DB roundtrip)

**Out of scope (ZERO TOUCH):**
- `.github/workflows/*`
- `ao_kernel/context/semantic_retrieval.py` (pure-Python cosine SSOT unchanged)
- Automatic backend detection / fallback at runtime (operator-owned)
- Schema migrations from the governance plane (operator owns DDL)
- Live LLM provider calls (embeddings flow through existing `embed_text` path)
- Any guard flag flip (3 const false)

## 2. Backend Protocol

`SemanticBackend(Protocol)`:
- `backend_name: str`
- `is_available() -> bool`
- `upsert(decision_id, embedding, payload) -> None`
- `search(query_embedding, *, limit=10, min_score=0.0) -> list[SemanticSearchResult]`
- `delete(decision_id) -> None`
- `count() -> int`

Both impls bind to the protocol via `assert isinstance(...)` at module
load time so static type-checkers + runtime conformance both pass.

## 3. pgvector Backend (opt-in)

- Lazy imports `psycopg2` + `pgvector` on first DB call (not at construction)
- Raises `SemanticBackendError` with install hint if extras missing
- Requires `AO_KERNEL_PGVECTOR_DSN` env var (NEVER constructor param) — operator-bound
- DDL is operator-owned (no runtime schema migrations)
- Default embedding dim 1536 (OpenAI text-embedding-3-small); overridable

### Schema (operator runs once)

```sql
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS ao_semantic_decisions (
    decision_id TEXT PRIMARY KEY,
    embedding   VECTOR(1536) NOT NULL,
    payload     JSONB NOT NULL,
    updated_at  TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ao_semantic_decisions_embedding_ivfflat
  ON ao_semantic_decisions USING ivfflat (embedding vector_cosine_ops)
  WITH (lists = 100);
```

## 4. Test Sections (22 invariants — 20 pass + 2 skipped)

| Section | Count | Focus |
|---|---|---|
| 1. Protocol shape | 4 | In-memory + pgvector backends conform; SearchResult dataclass + BackendError exception |
| 2. In-memory CRUD | 8 | Empty start + upsert/count + upsert replaces + search sorted + min_score filter + limit + delete + input validation |
| 3. pgvector lazy + extras + env | 5 | No extras at construction + is_available without env false + typed error on missing extras + typed error on missing DSN + embedding_dim validated |
| 4. Live pgvector roundtrip | 1 (skipped) | Operator opt-in via `AO_KERNEL_PGVECTOR_DSN` |
| 5. Module structure + guard flags | 4 | Public API exposed + top-level no psycopg2 import + docstring pins guard flags + ZERO TOUCH workflows |

## 5. References

- `ao_kernel/context/semantic_retrieval.py` (existing pure-Python SSOT)
- `pyproject.toml [pgvector]` extra (pre-existing; backend now binds)
- E-7-2 stress harness (PR #819 merged)
- E-7-3 memory profiling (PR #820 merged)
- V5 roadmap §E-7-5
- HARD RULE Cross-AI Peer Review + No Fake Work + Uzun Vadeli
