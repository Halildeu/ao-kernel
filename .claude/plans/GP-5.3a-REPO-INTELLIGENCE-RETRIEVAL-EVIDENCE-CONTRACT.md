# GP-5.3a - Repo Intelligence Retrieval Evidence Contract

**Status:** Closeout candidate
**Date:** 2026-04-24
**Authority:** `origin/main` at `3656939`
**Parent tracker:** [#424](https://github.com/Halildeu/ao-kernel/issues/424)
**Slice issue:** [#431](https://github.com/Halildeu/ao-kernel/issues/431)
**Branch:** `codex/gp5-3a-retrieval-evidence`
**Worktree:** `/Users/halilkocoglu/Documents/ao-kernel-gp5-3a`
**Decision:** `keep_beta_read_only_retrieval_contract`

## Purpose

Define the minimum evidence contract that `repo query` must satisfy before its
output can be considered as explicit input for governed workflow context in a
later GP-5 slice.

This slice does not promote repo intelligence to production workflow support.
It tightens the read-only retrieval boundary and records what is already
behavior-tested.

## Scope

1. Pin query-result evidence fields that downstream workflow handoff can trust.
2. Strengthen behavior tests for namespace filtering, source-hash freshness,
   snippet boundaries, and path-escape exclusion.
3. Record the limits of the current relevance signal.
4. Keep `RI-5` root export and `context_compiler` auto-feed out of scope.

## Non-Goals

1. No `context_compiler` auto-injection.
2. No MCP tool wiring for repo query.
3. No root export and no dependency on `.ao/context/repo_export_plan.json`.
4. No root authority file writes.
5. No vector backend writes.
6. No support boundary widening.

## Retrieval Evidence Contract

A valid `repo query` JSON result must carry these evidence groups:

| Group | Required evidence | Purpose |
|---|---|---|
| Generator | `generator.name`, `generator.version`, `generated_at` | identify producing runtime |
| Query parameters | query text, `top_k`, `candidate_limit`, `min_similarity`, token/snippet limits, filters | make retrieval reproducible and bounded |
| Embedding space | provider, model, dimension, chunker version, embedding space id | prevent cross-model/vector-space mixing |
| Namespace | `repo_chunk::<project_identity>::<embedding_space_id>::...` plus metadata checks | keep canonical/session memory out of repo retrieval |
| Source artifacts | repo chunks digest and vector index manifest digest | bind result to local index artifacts |
| Result source | source path, line range, language, kind, chunk id, content hash | make every snippet attributable |
| Relevance signal | vector similarity and applied filters | expose ranking evidence without claiming human relevance |
| Freshness signal | `content_status="current"` only in returned results; stale candidates appear in diagnostics | prevent deleted/refactored code from becoming prompt context |
| Bounds | token estimate, snippet truncation flag, max snippet chars | keep handoff size explicit |
| Diagnostics | filtered/stale/token-budget reasons | show why candidates were excluded |

## Behavior Pinned By This Slice

The focused tests now assert:

1. result source artifact hashes are present and tied to the index manifest;
2. all returned results meet the recorded `min_similarity`;
3. all returned results are `content_status="current"`;
4. untruncated snippets hash back to `content_sha256`;
5. non-repo namespace candidates are filtered;
6. same-key-prefix candidates with wrong repo metadata are filtered;
7. path-escape source candidates are excluded and diagnosed;
8. stale source chunks are excluded and diagnosed;
9. CLI `repo query` remains read-only for `.ao/context` and root authority
   files.

## Relevance Boundary

Current relevance evidence is intentionally limited to:

1. vector-store similarity score;
2. configured `min_similarity`;
3. path/language/symbol filters;
4. deterministic result ordering.

This is enough for a read-only evidence contract. It is not yet enough for a
production claim that the answer is semantically correct for arbitrary coding
tasks. Human-labeled or fixture-level retrieval quality thresholds remain a
future GP-5.4 / GP-5.7 concern.

## RI-5 / GP-5.3 Interface

`GP-5.3a` does not consume RI-5 export artifacts.

| Artifact | GP-5.3a status |
|---|---|
| `.ao/context/repo_export_plan.json` | `not_used` |
| `CLAUDE.md` / `AGENTS.md` root exports | `not_used` |
| stdout Markdown from `repo query --output markdown` | input candidate for `GP-5.3b`, not consumed here |
| JSON query result | evidence contract defined here |

`RI-5a` may continue independently as root/export preview work. It must not be
treated as a prerequisite for read-only retrieval evidence.

## Support Boundary Impact

No support widening.

`repo query` remains `Beta / experimental read-only retrieval`. The slice makes
the evidence contract clearer and better tested, but it does not make
repo-intelligence workflow integration production-supported.

## Next Slice

`GP-5.3b` should define the explicit agent context handoff contract:

1. stdout-only Markdown as manual/operator-visible input;
2. no hidden prompt injection;
3. no context compiler auto-feed;
4. no root export writes;
5. no support widening.

## Validation

Required validation for this slice:

1. `pytest -q tests/test_repo_intelligence_vector_retriever.py tests/test_cli_repo_query.py`
2. `python3 -m ao_kernel doctor`
3. `git diff --check`
4. PR CI
