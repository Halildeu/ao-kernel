"""Public repo-intelligence facade for local repo artifacts."""

from __future__ import annotations

from ao_kernel._internal.repo_intelligence.artifacts import (
    validate_repo_export_plan,
    write_repo_export_plan_artifact,
    write_repo_scan_artifacts,
    write_repo_vector_index_manifest_artifact,
    write_repo_vector_write_plan_artifact,
)
from ao_kernel._internal.repo_intelligence.context_pack_builder import (
    build_agent_context_pack,
    build_repo_query_context_pack,
)
from ao_kernel._internal.repo_intelligence.python_ast_indexer import build_python_ast_indexes
from ao_kernel._internal.repo_intelligence.repo_chunker import build_repo_chunks
from ao_kernel._internal.repo_intelligence.repo_vector_indexer import (
    CONFIRM_VECTOR_INDEX,
    write_repo_vectors,
)
from ao_kernel._internal.repo_intelligence.repo_vector_plan import build_repo_vector_write_plan
from ao_kernel._internal.repo_intelligence.repo_vector_retriever import query_repo_vectors
from ao_kernel._internal.repo_intelligence.scanner import scan_repo
from ao_kernel._internal.repo_intelligence.export_plan import (
    build_repo_export_plan,
    supported_repo_export_targets,
)

__all__ = [
    "build_agent_context_pack",
    "build_repo_query_context_pack",
    "build_repo_export_plan",
    "build_python_ast_indexes",
    "build_repo_chunks",
    "build_repo_vector_write_plan",
    "CONFIRM_VECTOR_INDEX",
    "query_repo_vectors",
    "scan_repo",
    "supported_repo_export_targets",
    "validate_repo_export_plan",
    "write_repo_export_plan_artifact",
    "write_repo_scan_artifacts",
    "write_repo_vector_index_manifest_artifact",
    "write_repo_vectors",
    "write_repo_vector_write_plan_artifact",
]
