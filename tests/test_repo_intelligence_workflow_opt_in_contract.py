from __future__ import annotations

import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError

from ao_kernel.context.context_compiler import compile_context
from ao_kernel.repo_intelligence import (
    build_repo_query_context_pack,
    validate_repo_intelligence_workflow_opt_in,
)


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = (
    ROOT
    / "ao_kernel"
    / "defaults"
    / "schemas"
    / "repo-intelligence-workflow-context-opt-in.schema.v1.json"
)
WORKFLOW_DIR = ROOT / "ao_kernel" / "defaults" / "workflows"


def _schema() -> dict:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def _valid_contract() -> dict:
    return {
        "schema_version": "1",
        "artifact_kind": "repo_intelligence_workflow_context_opt_in",
        "enabled": True,
        "support_tier": "beta_read_only_context",
        "handoff_mode": "operator_markdown_stdout",
        "input": {
            "source": "repo_query",
            "operator_visible": True,
            "automatic_prompt_injection": False,
            "context_compiler_feed": {
                "enabled": True,
                "requires_explicit_workflow_config": True,
                "requires_behavior_tests": True,
            },
        },
        "source_evidence": {
            "repo_chunks_sha256": "a" * 64,
            "repo_vector_index_manifest_sha256": "b" * 64,
            "vector_namespace_key_prefix": "repo_chunk::project::space::",
            "content_status": "current_only",
        },
        "safety": {
            "write_root_authority_files": False,
            "write_context_artifacts": False,
            "mcp_tool_exposure": False,
            "vector_writes": False,
            "hidden_prompt_injection": False,
        },
    }


def test_repo_intelligence_workflow_opt_in_schema_accepts_explicit_contract() -> None:
    schema = _schema()
    Draft202012Validator.check_schema(schema)
    errors = list(Draft202012Validator(schema).iter_errors(_valid_contract()))
    assert errors == []


def test_repo_intelligence_workflow_opt_in_schema_rejects_implicit_or_unsafe_shapes() -> None:
    validator = Draft202012Validator(_schema())

    missing_evidence = _valid_contract()
    del missing_evidence["source_evidence"]["repo_chunks_sha256"]
    with pytest.raises(ValidationError):
        validator.validate(missing_evidence)

    hidden_injection = _valid_contract()
    hidden_injection["input"]["automatic_prompt_injection"] = True
    with pytest.raises(ValidationError):
        validator.validate(hidden_injection)

    production_claim = _valid_contract()
    production_claim["support_tier"] = "production"
    with pytest.raises(ValidationError):
        validator.validate(production_claim)


def test_default_workflows_do_not_declare_repo_intelligence_auto_feed() -> None:
    for workflow_path in WORKFLOW_DIR.glob("*.v1.json"):
        payload = json.loads(workflow_path.read_text(encoding="utf-8"))
        for step in payload["steps"]:
            assert "repo_intelligence_context" not in step
            assert "repo_query_context" not in step


def test_context_compiler_does_not_auto_ingest_repo_query_context() -> None:
    result = compile_context(
        {
            "session_id": "test",
            "ephemeral_decisions": [],
            "repo_query_context": "# Repo Query Context Pack\n\nsensitive implicit context\n",
        },
        profile="TASK_EXECUTION",
    )

    assert result.preamble == ""
    assert "Repo Query Context Pack" not in result.preamble
    assert result.items_included == 0


def test_explicit_workflow_opt_in_accepts_current_operator_handoff(tmp_path: Path) -> None:
    handoff = build_repo_query_context_pack(query_result=_query_result())
    handoff_path = tmp_path / "repo-query-handoff.md"
    handoff_path.write_text(handoff, encoding="utf-8")

    result = validate_repo_intelligence_workflow_opt_in(
        {
            "enabled": True,
            "source": "explicit_handoff_file",
            "handoff_path": "repo-query-handoff.md",
            "require_fresh": True,
            "expected_namespace": "repo_chunk::demo::space::",
            "support_tier": "beta_explicit_handoff",
        },
        project_root=tmp_path,
    )

    assert result["status"] == "accepted"
    assert result["decision"] == "accepted_repo_intelligence_workflow_opt_in"
    assert result["handoff"]["mode"] == "explicit_operator_markdown"
    assert result["handoff"]["support_tier"] == "beta_explicit_handoff"
    assert len(result["handoff"]["markdown_sha256"]) == 64
    assert result["source_metadata"]["freshness_state"] == "current_only"
    assert result["source_metadata"]["stale_candidates"] == 0
    assert result["source_metadata"]["vector_namespace_key_prefix"] == "repo_chunk::demo::space::"
    assert result["source_metadata"]["source_paths"] == ["pkg/main.py"]
    assert result["safety"] == {
        "hidden_injection": False,
        "root_export": False,
        "mcp_exposure": False,
        "context_compiler_auto_feed": False,
        "vector_writes": False,
        "artifact_writes": False,
    }
    assert result["support_widening"] is False
    assert result["production_platform_claim"] is False


def test_explicit_workflow_opt_in_disabled_is_noop(tmp_path: Path) -> None:
    assert validate_repo_intelligence_workflow_opt_in(None, project_root=tmp_path) == {
        "status": "disabled",
        "enabled": False,
        "decision": "repo_intelligence_context_not_enabled",
    }
    assert validate_repo_intelligence_workflow_opt_in({"enabled": False}, project_root=tmp_path) == {
        "status": "disabled",
        "enabled": False,
        "decision": "repo_intelligence_context_not_enabled",
    }


def test_explicit_workflow_opt_in_blocks_stale_or_namespace_mismatch(tmp_path: Path) -> None:
    query_result = _query_result()
    query_result["summary"]["stale_candidates"] = 1
    handoff_path = tmp_path / "stale.md"
    handoff_path.write_text(build_repo_query_context_pack(query_result=query_result), encoding="utf-8")

    result = validate_repo_intelligence_workflow_opt_in(
        {
            "enabled": True,
            "source": "explicit_handoff_file",
            "handoff_path": str(handoff_path),
            "require_fresh": True,
            "expected_namespace": "repo_chunk::other::space::",
            "support_tier": "beta_explicit_handoff",
        },
        project_root=tmp_path,
    )

    assert result["status"] == "blocked"
    assert result["decision"] == "blocked_repo_intelligence_workflow_opt_in"
    assert "freshness_not_current_only" in result["findings"]
    assert "source_artifact_freshness_not_current_only" in result["findings"]
    assert "stale_candidates_not_zero" in result["findings"]
    assert "namespace_mismatch" in result["findings"]
    assert result["support_widening"] is False
    assert result["production_platform_claim"] is False


def test_explicit_workflow_opt_in_blocks_hash_mismatch_and_path_escape(tmp_path: Path) -> None:
    handoff_path = tmp_path / "handoff.md"
    handoff_path.write_text(build_repo_query_context_pack(query_result=_query_result()), encoding="utf-8")

    result = validate_repo_intelligence_workflow_opt_in(
        {
            "enabled": True,
            "source": "explicit_handoff_file",
            "handoff_path": "../handoff.md",
            "require_fresh": True,
            "expected_namespace": "repo_chunk::demo::space::",
            "support_tier": "beta_explicit_handoff",
            "expected_markdown_sha256": "0" * 64,
        },
        project_root=tmp_path,
    )

    assert result["status"] == "blocked"
    assert "handoff_path_escape" in result["findings"]

    result = validate_repo_intelligence_workflow_opt_in(
        {
            "enabled": True,
            "source": "explicit_handoff_file",
            "handoff_path": str(handoff_path),
            "require_fresh": True,
            "expected_namespace": "repo_chunk::demo::space::",
            "support_tier": "beta_explicit_handoff",
            "expected_markdown_sha256": "0" * 64,
        },
        project_root=tmp_path,
    )

    assert result["status"] == "blocked"
    assert "handoff_sha256_mismatch" in result["findings"]


def test_explicit_workflow_opt_in_blocks_hidden_injection_or_chunk_path_escape(tmp_path: Path) -> None:
    handoff = build_repo_query_context_pack(query_result=_query_result())
    handoff = handoff.replace(
        "| Hidden injection | disabled; operator must provide this Markdown as visible input |",
        "| Hidden injection | enabled |",
    ).replace("### 1. `pkg/main.py:3-4`", "### 1. `../secret.py:3-4`")
    handoff_path = tmp_path / "unsafe.md"
    handoff_path.write_text(handoff, encoding="utf-8")

    result = validate_repo_intelligence_workflow_opt_in(
        {
            "enabled": True,
            "source": "explicit_handoff_file",
            "handoff_path": str(handoff_path),
            "require_fresh": True,
            "expected_namespace": "repo_chunk::demo::space::",
            "support_tier": "beta_explicit_handoff",
        },
        project_root=tmp_path,
    )

    assert result["status"] == "blocked"
    assert "hidden_injection_not_disabled" in result["findings"]
    assert "source_path_escape" in result["findings"]


def _query_result() -> dict:
    return {
        "schema_version": "1",
        "artifact_kind": "repo_vector_query_result",
        "generator": {
            "name": "ao-kernel",
            "version": "4.0.0",
            "generated_at": "2026-04-27T00:00:00Z",
        },
        "project": {
            "root": ".",
            "root_name": "demo",
            "name": "demo",
            "root_identity_sha256": "a" * 64,
        },
        "retriever": {
            "name": "ao-kernel-repo-vector-retriever",
            "version": "repo-vector-retriever.v1",
            "mode": "query_vectors",
        },
        "query": {
            "text": "where is run defined",
            "top_k": 5,
            "candidate_limit": 50,
            "min_similarity": 0.3,
            "max_tokens": 2000,
            "max_snippet_chars": 1200,
            "filters": {
                "source_path_prefix": "pkg/",
                "language": "python",
                "symbol": "run",
            },
        },
        "embedding_space": {
            "provider": "openai",
            "model": "text-embedding-3-small",
            "dimension": 1536,
            "embedding_space_id": "b" * 64,
        },
        "vector_namespace": {
            "key_prefix": "repo_chunk::demo::space::",
            "project_root_identity_sha256": "a" * 64,
        },
        "source_artifacts": {
            "repo_chunks_sha256": "c" * 64,
            "repo_vector_index_manifest_sha256": "d" * 64,
        },
        "summary": {
            "matches": 1,
            "candidate_matches": 1,
            "filtered_candidates": 1,
            "stale_candidates": 0,
            "embedding_calls": 1,
            "estimated_tokens": 12,
            "truncated_results": 0,
        },
        "results": [
            {
                "key": "repo_chunk::demo::space::repo-chunk-v1:1",
                "similarity": 0.9876,
                "source_path": "pkg/main.py",
                "start_line": 3,
                "end_line": 4,
                "language": "python",
                "kind": "symbol",
                "module": "pkg.main",
                "symbol": "run",
                "chunk_id": "repo-chunk-v1:1",
                "content_sha256": "e" * 64,
                "token_estimate": 12,
                "snippet": "def run():\n    return VALUE\n",
                "snippet_truncated": False,
                "content_status": "current",
            }
        ],
        "diagnostics": [],
    }
