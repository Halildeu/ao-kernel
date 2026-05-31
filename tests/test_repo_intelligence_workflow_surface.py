from __future__ import annotations

import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError

from ao_kernel.context.context_compiler import compile_context
from ao_kernel.repo_intelligence import (
    build_repo_intelligence_read_only_workflow_surface,
    build_repo_query_context_pack,
    resolve_repo_intelligence_workflow_context,
)


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = (
    ROOT / "ao_kernel" / "defaults" / "schemas" / "repo-intelligence-read-only-workflow-surface.schema.v1.json"
)


def _schema() -> dict:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def _product_onboarding() -> dict:
    return {
        "schema_version": "1",
        "artifact_kind": "repo_intelligence_product_onboarding",
        "enabled": True,
        "support_tier": "beta_read_only_product_onboarding",
        "setup": {
            "github_app": {
                "installation": "required",
                "repository_selection": "selected_repositories",
                "permission_boundary": "read_only_repo_intelligence",
            },
            "repo_local_config": {
                "path": ".ao/config.yml",
                "required": False,
            },
            "end_user_infrastructure": {
                "cloud_run_required": False,
                "vault_required": False,
                "webhook_required": False,
                "github_app_private_key_required": False,
                "release_gate_service_required": False,
                "deployment_protection_service_required": False,
            },
        },
        "workflow": {
            "mode": "read_only",
            "activation": "explicit_opt_in",
            "default_enabled": False,
            "default_auto_feed": False,
        },
        "safety": {
            "hidden_prompt_injection": False,
            "mcp_tool_exposure": False,
            "root_export_required": False,
            "context_compiler_auto_feed": False,
            "implicit_vector_writes": False,
            "implicit_artifact_writes": False,
            "live_adapter_execution": False,
            "support_widening": False,
            "production_platform_claim": False,
        },
    }


def _workflow_context_config(handoff_path: str = "repo-query-handoff.md") -> dict:
    return {
        "schema_version": "1",
        "artifact_kind": "repo_intelligence_explicit_workflow_context",
        "enabled": True,
        "support_tier": "beta_explicit_read_only_workflow_context",
        "product_onboarding": _product_onboarding(),
        "workflow_opt_in": {
            "enabled": True,
            "source": "explicit_handoff_file",
            "handoff_path": handoff_path,
            "require_fresh": True,
            "expected_namespace": "repo_chunk::demo::space::",
            "support_tier": "beta_explicit_handoff",
        },
        "workflow_context": {
            "mode": "visible_operator_handoff",
            "consumer": "workflow_runtime",
            "operator_visible": True,
            "default_enabled": False,
            "automatic_prompt_injection": False,
            "context_compiler_auto_feed": False,
            "write_context_artifacts": False,
            "requires_behavior_tests": True,
        },
        "safety": {
            "hidden_prompt_injection": False,
            "mcp_tool_exposure": False,
            "root_export": False,
            "context_compiler_auto_feed": False,
            "vector_writes": False,
            "artifact_writes": False,
            "live_adapter_execution": False,
            "support_widening": False,
            "production_platform_claim": False,
        },
    }


def test_read_only_workflow_surface_schema_accepts_output_contract(tmp_path: Path) -> None:
    surface = _accepted_surface(tmp_path)

    schema = _schema()
    Draft202012Validator.check_schema(schema)
    errors = list(Draft202012Validator(schema).iter_errors(surface))

    assert errors == []


def test_read_only_workflow_surface_schema_rejects_hidden_body_or_support_claim(tmp_path: Path) -> None:
    validator = Draft202012Validator(_schema())
    surface = _accepted_surface(tmp_path)

    hidden_body = dict(surface)
    hidden_body["surface"] = dict(surface["surface"])
    hidden_body["surface"]["includes_markdown_body"] = True
    with pytest.raises(ValidationError):
        validator.validate(hidden_body)

    production_claim = dict(surface)
    production_claim["safety"] = dict(surface["safety"])
    production_claim["safety"]["production_platform_claim"] = True
    with pytest.raises(ValidationError):
        validator.validate(production_claim)


def test_read_only_workflow_surface_disabled_is_noop(tmp_path: Path) -> None:
    assert build_repo_intelligence_read_only_workflow_surface(None, project_root=tmp_path) == {
        "status": "disabled",
        "enabled": False,
        "decision": "repo_intelligence_read_only_workflow_surface_not_enabled",
    }
    assert build_repo_intelligence_read_only_workflow_surface({"enabled": False}, project_root=tmp_path) == {
        "status": "disabled",
        "enabled": False,
        "decision": "repo_intelligence_read_only_workflow_surface_not_enabled",
    }


def test_read_only_workflow_surface_carries_metadata_without_markdown_body(tmp_path: Path) -> None:
    surface = _accepted_surface(tmp_path)

    assert surface["status"] == "accepted"
    assert surface["decision"] == "accepted_repo_intelligence_read_only_workflow_surface"
    assert surface["support_tier"] == "beta_read_only_workflow_surface"
    assert surface["source"]["workflow_context_decision"] == "accepted_repo_intelligence_workflow_context"
    assert surface["source"]["handoff_support_tier"] == "beta_explicit_handoff"
    assert surface["source"]["vector_namespace_key_prefix"] == "repo_chunk::demo::space::"
    assert surface["source"]["repo_chunks_sha256"] == "c" * 64
    assert surface["source"]["repo_vector_index_manifest_sha256"] == "d" * 64
    assert surface["source"]["freshness_state"] == "current_only"
    assert surface["source"]["stale_candidates"] == 0
    assert surface["source"]["retrieved_chunks"] == 1
    assert surface["retrieved_sources"] == [
        {
            "source_path": "pkg/main.py",
            "start_line": 3,
            "end_line": 4,
            "content_sha256": "e" * 64,
        }
    ]
    assert surface["surface"] == {
        "mode": "operator_visible_read_only_context_pointer",
        "consumer": "workflow_runtime",
        "operator_visible": True,
        "requires_visible_agent_input": True,
        "includes_markdown_body": False,
        "automatic_prompt_injection": False,
        "context_compiler_auto_feed": False,
        "write_context_artifacts": False,
    }
    rendered = json.dumps(surface, sort_keys=True)
    assert "def run():" not in rendered
    assert "Repo Query Context Pack" not in rendered
    assert surface["support_widening"] is False
    assert surface["production_platform_claim"] is False
    assert surface["live_adapter_execution_allowed"] is False


def test_read_only_workflow_surface_blocks_unaccepted_context(tmp_path: Path) -> None:
    result = build_repo_intelligence_read_only_workflow_surface(
        {
            "status": "blocked",
            "enabled": True,
            "decision": "blocked_repo_intelligence_workflow_context",
            "findings": ["freshness_not_current_only"],
        },
        project_root=tmp_path,
    )

    assert result["status"] == "blocked"
    assert result["decision"] == "blocked_repo_intelligence_read_only_workflow_surface"
    assert "workflow_context_not_accepted" in result["findings"]
    assert result["support_widening"] is False
    assert result["production_platform_claim"] is False
    assert result["live_adapter_execution_allowed"] is False


def test_read_only_workflow_surface_blocks_handoff_hash_mismatch(tmp_path: Path) -> None:
    resolved = _accepted_context(tmp_path)
    handoff_path = Path(resolved["context"]["handoff_path"])
    handoff_path.write_text("# modified\n", encoding="utf-8")

    result = build_repo_intelligence_read_only_workflow_surface(resolved, project_root=tmp_path)

    assert result["status"] == "blocked"
    assert "handoff_sha256_mismatch" in result["findings"]
    assert "retrieved_sources_missing" in result["findings"]


def test_read_only_workflow_surface_blocks_missing_metadata_or_unknown_namespace(tmp_path: Path) -> None:
    resolved = _accepted_context(tmp_path)
    resolved["source_metadata"]["vector_namespace_key_prefix"] = "repo_chunks"
    resolved["source_metadata"].pop("repo_chunks_sha256")
    resolved["source_metadata"]["stale_candidates"] = 1

    result = build_repo_intelligence_read_only_workflow_surface(resolved, project_root=tmp_path)

    assert result["status"] == "blocked"
    assert "namespace_invalid" in result["findings"]
    assert "repo_chunks_sha256_invalid" in result["findings"]
    assert "stale_candidates_not_zero" in result["findings"]


def test_read_only_workflow_surface_does_not_auto_ingest_into_context_compiler(tmp_path: Path) -> None:
    handoff = build_repo_query_context_pack(query_result=_query_result())
    surface = _accepted_surface(tmp_path)

    result = compile_context(
        {
            "session_id": "test",
            "ephemeral_decisions": [],
            "repo_intelligence_workflow_surface": surface,
            "repo_query_context": handoff,
        },
        profile="TASK_EXECUTION",
    )

    assert result.preamble == ""
    assert "Repo Query Context Pack" not in result.preamble
    assert result.items_included == 0


def _accepted_surface(tmp_path: Path) -> dict:
    return build_repo_intelligence_read_only_workflow_surface(_accepted_context(tmp_path), project_root=tmp_path)


def _accepted_context(tmp_path: Path) -> dict:
    handoff_path = tmp_path / "repo-query-handoff.md"
    handoff_path.write_text(build_repo_query_context_pack(query_result=_query_result()), encoding="utf-8")
    result = resolve_repo_intelligence_workflow_context(_workflow_context_config(), project_root=tmp_path)
    assert result["status"] == "accepted"
    return result


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
