# RI-4 - Repo Intelligence Chunking and Vector Indexing Design Gate

**Status:** Design gate
**Date:** 2026-04-24
**Branch:** `codex/repo-intelligence-vector-design`
**Worktree:** `/Users/halilkocoglu/Documents/ao-kernel-repo-intelligence-vector-design`
**Base:** `origin/main` at `6488ba8`
**Rule:** Never work directly on `main`.

## Operational Rules

These rules remain mandatory:

1. Work must happen in a dedicated worktree. Direct work on `main` is
   forbidden.
2. Completed work is integrated through PR review/CI and merge.
3. After a PR is merged, the authoritative source becomes `origin/main`.
4. Active feature worktrees do not update automatically after another PR
   merges.
5. Uncommitted changes must never be lost during refresh, rebase, branch
   switch, pull, or worktree cleanup.
6. Do not use destructive cleanup commands unless the user explicitly requests
   that exact operation.

## Purpose

RI-1, RI-2, and RI-3 made repo intelligence useful without mutating anything
outside `.ao/context/`:

1. RI-1 added deterministic repo scan artifacts.
2. RI-2 added Python AST import graph and symbol index artifacts.
3. RI-3 added a deterministic Markdown agent context pack artifact.

RI-4 is the first tranche that can touch semantic memory. That makes it
higher risk than prior repo-intelligence slices. The design decision is to
split RI-4 into safe, reviewable sub-slices instead of adding vector writes in
one PR.

## Decision

RI-4 must be implemented in this order:

1. `RI-4a` - deterministic chunk manifest only.
2. `RI-4b` - vector indexing dry-run and write-plan artifact only.
3. `RI-4c` - explicit opt-in vector write path.
4. `RI-4d` - retrieval integration, if evidence shows the index is clean and
   useful.

The next implementation PR after this design gate should be `RI-4a` only.

## Non-Negotiable Boundaries

1. `repo scan` must not write vectors.
2. `repo scan` must not call embedding providers.
3. `repo scan` must not require network access.
4. Vector writes must require an explicit command and explicit confirmation.
5. Root authority files must not be written.
6. Existing session/canonical memory namespaces must not be polluted by repo
   chunks.
7. Every vector record must carry provider, model, dimension, chunker version,
   project identity, and chunk identity metadata.
8. Rebuilds must have a deterministic cleanup strategy for stale chunk keys.
9. The support tier must remain Beta / experimental until a later promotion
   decision widens it.

## Proposed Artifact Model

### RI-4a artifact

RI-4a should add one local, schema-backed artifact:

```text
.ao/context/repo_chunks.json
```

It should also extend:

```text
.ao/context/repo_index_manifest.json
```

The chunk manifest should not duplicate full source text. It should record
stable chunk boundaries and content hashes so later stages can read source
files explicitly when needed.

Minimum chunk record fields:

```json
{
  "chunk_id": "repo-chunk-v1:<sha256>",
  "source_path": "ao_kernel/example.py",
  "language": "python",
  "kind": "symbol|module|file_slice",
  "module": "ao_kernel.example",
  "symbol": "ExampleClass",
  "start_line": 1,
  "end_line": 40,
  "byte_start": 0,
  "byte_end": 1234,
  "content_sha256": "<sha256>",
  "token_estimate": 280
}
```

Minimum manifest metadata:

```json
{
  "schema_version": "1",
  "artifact_kind": "repo_chunks",
  "chunker": {
    "name": "ao-kernel-repo-chunker",
    "version": "repo-chunker.v1",
    "strategy": "python_symbol_then_line_window",
    "max_chunk_bytes": 12000,
    "overlap_lines": 8
  },
  "source_artifacts": {
    "repo_map_sha256": "...",
    "import_graph_sha256": "...",
    "symbol_index_sha256": "..."
  },
  "summary": {
    "chunks": 0,
    "source_files": 0,
    "skipped_files": 0,
    "diagnostics": 0
  },
  "chunks": [],
  "diagnostics": []
}
```

### RI-4b artifact

RI-4b should add a dry-run vector write-plan artifact:

```text
.ao/context/repo_vector_write_plan.json
```

This artifact should be generated without embedding calls and without vector
store writes. It should show exactly which chunk keys would be embedded, which
prior keys would be deleted, and which embedding space would be used.

### RI-4c artifact

RI-4c may add a vector index result manifest:

```text
.ao/context/repo_vector_index_manifest.json
```

This manifest is local evidence for an explicit vector indexing run. It is not
the vector store itself.

Minimum fields:

```json
{
  "schema_version": "1",
  "artifact_kind": "repo_vector_index_manifest",
  "command": "repo index",
  "dry_run": false,
  "vector_backend": "pgvector|inmemory",
  "embedding_provider": "openai",
  "embedding_model": "text-embedding-3-small",
  "embedding_dimension": 1536,
  "embedding_space_id": "<sha256>",
  "project_root_identity_sha256": "...",
  "chunk_manifest_sha256": "...",
  "indexed_keys": [],
  "deleted_keys": [],
  "skipped_chunks": [],
  "diagnostics": []
}
```

## Chunking Rules

RI-4a chunking must be deterministic:

1. Use repo-relative POSIX paths only.
2. Do not follow symlinks.
3. Consume RI-1/RI-2 artifacts where possible.
4. Use Python symbols as the first chunk boundary source.
5. Fall back to deterministic line windows for files without usable symbols.
6. Split large symbols by line windows rather than producing unbounded chunks.
7. Sort chunks by `source_path`, `start_line`, `end_line`, and `chunk_id`.
8. Do not include generation timestamps in chunk identity.
9. Use a stable `content_sha256` over the exact bytes covered by the chunk.
10. Keep chunk IDs independent from absolute filesystem paths.

Recommended first limits:

| Setting | Value |
|---|---:|
| `max_chunk_bytes` | 12000 |
| `target_chunk_bytes` | 8000 |
| `overlap_lines` | 8 |
| `max_file_bytes` | 500000 |
| `max_chunks_per_file` | 200 |

## Secret and Noise Exclusion

Vector indexing must be stricter than repo scanning. A file appearing in
`repo_map.json` does not automatically mean it is safe to embed.

RI-4a should start with a conservative chunking allowlist:

1. Python source files.
2. Markdown documentation.
3. TOML/YAML/JSON config files that are not secret-like.
4. Plain text project docs.

RI-4a should exclude these from chunking by default:

```text
.env
.env.*
*.pem
*.key
*.crt
*.p12
*.pfx
id_rsa
id_dsa
id_ed25519
secrets.*
credentials.*
*.sqlite
*.db
*.png
*.jpg
*.jpeg
*.gif
*.pdf
*.zip
*.tar
*.gz
```

If a file is excluded by the chunker but present in `repo_map.json`, record a
diagnostic in `repo_chunks.json`. Do not silently embed it later.

## Vector Key and Namespace Rules

Vector keys must never collide with session/canonical memory decisions.

Recommended key shape:

```text
repo_chunk::<project_root_identity_sha256>::<embedding_space_id>::<chunk_id>
```

Where:

```text
embedding_space_id = sha256(provider || model || dimension || chunker_version)
```

Required vector metadata:

```json
{
  "source": "repo_intelligence",
  "artifact_kind": "repo_chunk",
  "project_name": "ao-kernel",
  "project_root_identity_sha256": "...",
  "source_path": "ao_kernel/example.py",
  "chunk_id": "repo-chunk-v1:<sha256>",
  "content_sha256": "...",
  "chunker_version": "repo-chunker.v1",
  "embedding_provider": "openai",
  "embedding_model": "text-embedding-3-small",
  "embedding_dimension": 1536
}
```

## CLI Design

`repo scan` remains the local artifact generator and must not perform vector
writes.

RI-4a may extend scan output with chunk artifacts:

```bash
python3 -m ao_kernel repo scan --project-root . --output json
```

Expected RI-4a artifact set:

```text
.ao/context/repo_map.json
.ao/context/import_graph.json
.ao/context/symbol_index.json
.ao/context/agent_pack.md
.ao/context/repo_chunks.json
.ao/context/repo_index_manifest.json
```

RI-4b/RI-4c should use a separate command surface:

```bash
python3 -m ao_kernel repo index --project-root . --workspace-root .ao --dry-run --output json
python3 -m ao_kernel repo index --project-root . --workspace-root .ao --write-vectors --confirm-vector-index I_UNDERSTAND_REPO_VECTOR_WRITES --output json
```

`repo index` must fail closed if:

1. `repo_chunks.json` is missing or schema-invalid.
2. embedding provider configuration is missing.
3. vector backend resolution fails.
4. embedding dimension/model does not match the backend namespace.
5. explicit confirmation is missing for real vector writes.

## Rebuild and Cleanup Rules

RI-4c must avoid stale vector memory:

1. Read the prior `.ao/context/repo_vector_index_manifest.json` if present.
2. Compare prior indexed keys with current chunk keys for the same project and
   embedding space.
3. Delete stale keys before storing replacement vectors.
4. Record `deleted_keys` in the new manifest.
5. If cleanup fails, fail the vector write command unless `--dry-run` is used.
6. Do not delete keys outside the recorded project identity and embedding
   space.

## Implementation Slices

### RI-4a - Chunk manifest only

Planned files:

```text
ao_kernel/_internal/repo_intelligence/repo_chunker.py
ao_kernel/defaults/schemas/repo-chunks.schema.v1.json
ao_kernel/_internal/repo_intelligence/artifacts.py
ao_kernel/_internal/repo_intelligence/context_pack_builder.py
ao_kernel/cli.py
ao_kernel/repo_intelligence/__init__.py
tests/test_repo_intelligence_chunker.py
tests/test_repo_intelligence_artifacts.py
tests/test_cli_repo_scan.py
docs/PUBLIC-BETA.md
docs/SUPPORT-BOUNDARY.md
```

Acceptance:

- [ ] Dedicated worktree and non-main branch.
- [ ] `repo_chunks.json` is schema-backed.
- [ ] Chunk output is deterministic across repeated runs.
- [ ] Chunk IDs do not include absolute filesystem paths.
- [ ] Chunker records diagnostics for skipped secret-like or oversized files.
- [ ] `repo scan` writes only under `.ao/context/`.
- [ ] No embedding calls.
- [ ] No vector store writes.
- [ ] No network access.
- [ ] No root authority file writes.
- [ ] Focused tests pass.
- [ ] `ruff check ao_kernel/ tests/` passes.
- [ ] `mypy ao_kernel/` passes.
- [ ] `python3 scripts/packaging_smoke.py` passes.

### RI-4b - Vector write-plan dry-run

Planned files:

```text
ao_kernel/_internal/repo_intelligence/repo_vector_plan.py
ao_kernel/defaults/schemas/repo-vector-write-plan.schema.v1.json
ao_kernel/cli.py
tests/test_repo_intelligence_vector_plan.py
tests/test_cli_repo_index.py
docs/PUBLIC-BETA.md
docs/SUPPORT-BOUNDARY.md
```

Acceptance:

- [ ] `repo index --dry-run` reads `repo_chunks.json`.
- [ ] Dry-run emits `.ao/context/repo_vector_write_plan.json`.
- [ ] Dry-run performs no embedding calls.
- [ ] Dry-run performs no vector store writes.
- [ ] Planned keys are deterministic.
- [ ] Stale-key deletion plan is deterministic.
- [ ] Missing or invalid chunk manifest fails closed.

### RI-4c - Explicit vector write

Planned files:

```text
ao_kernel/_internal/repo_intelligence/repo_vector_indexer.py
ao_kernel/defaults/schemas/repo-vector-index-manifest.schema.v1.json
ao_kernel/cli.py
tests/test_repo_intelligence_vector_indexer.py
tests/test_cli_repo_index.py
docs/PUBLIC-BETA.md
docs/SUPPORT-BOUNDARY.md
```

Acceptance:

- [ ] Real vector writes require `--write-vectors`.
- [ ] Real vector writes require
      `--confirm-vector-index I_UNDERSTAND_REPO_VECTOR_WRITES`.
- [ ] Uses existing vector store resolver rather than inventing a separate
      backend selection path.
- [ ] Uses existing embedding configuration resolver.
- [ ] Stores required metadata on every vector record.
- [ ] Deletes stale keys only inside the recorded project and embedding space.
- [ ] Writes `.ao/context/repo_vector_index_manifest.json`.
- [ ] Fails closed on backend/model/dimension mismatch.
- [ ] Behavior tests use mocked embeddings and mocked vector store.
- [ ] No integration test requires a live pgvector service by default.

### RI-4d - Retrieval integration

Do not start this until RI-4c has stable evidence.

Questions to answer before implementation:

1. Should repo chunk retrieval feed `context_compiler` directly?
2. Should repo chunk retrieval be a separate agent-context query command?
3. What ranking blend should combine symbol/path filters and vector search?
4. What is the maximum retrieved token budget?
5. How does the caller distinguish repo chunks from canonical decisions?

## Rejected Approaches

| Approach | Decision | Reason |
|---|---|---|
| Auto-index during `repo scan` | Rejected | `repo scan` must stay local, deterministic, and no-network |
| Store repo vectors in session/canonical key namespace | Rejected | Pollutes existing memory and makes cleanup ambiguous |
| Write vectors without a local manifest | Rejected | No deterministic cleanup path for stale chunks |
| Use full source text inside `repo_chunks.json` | Rejected | Unnecessary duplication and higher accidental disclosure risk |
| Vector index all scanned files | Rejected | Scan inclusion is not the same as embedding safety |
| Root `CLAUDE.md`/`AGENTS.md` export in RI-4 | Rejected | Root export remains a separate explicit-confirm tranche |
| Live pgvector dependency in default CI | Rejected | CI should stay deterministic without external services |

## Risk Register

| Risk | Impact | Mitigation |
|---|---|---|
| Vector memory pollution | Bad retrieval and stale context | Split RI-4a/4b/4c and require explicit writes |
| Secret embedding | Sensitive data leaves local source context | Conservative chunk allowlist and secret-like denylist |
| Model namespace collision | Bad similarity matches | Include provider/model/dimension in key and metadata |
| Stale chunks after refactor | Retrieval returns deleted code | Prior manifest comparison and stale-key deletion |
| Non-deterministic chunks | Unstable IDs and noisy diffs | Stable sorting, fixed limits, content-based hashes |
| Support overclaim | Users expect production indexing | Keep Beta / experimental docs boundary |
| CI flakiness | External service dependency | Mock embeddings/vector store by default |

## Tracking Log

| Date | Status | Notes |
|---|---|---|
| 2026-04-24 | Design gate | Added RI-4 chunking/vector indexing plan before implementation. |
