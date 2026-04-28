from __future__ import annotations

import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError

from ao_kernel.context.context_compiler import compile_context
from ao_kernel.repo_intelligence import (
    build_repo_query_context_pack,
    resolve_repo_intelligence_workflow_context,
)


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = (
    ROOT / "ao_kernel" / "defaults" / "schemas" / "repo-intelligence-explicit-workflow-context.schema.v1.json"
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


def test_explicit_workflow_context_schema_accepts_visible_read_only_contract() -> None:
    schema = _schema()
    Draft202012Validator.check_schema(schema)
    errors = list(Draft202012Validator(schema).iter_errors(_workflow_context_config()))
    assert errors == []


def test_explicit_workflow_context_schema_rejects_auto_feed_or_end_user_hosting() -> None:
    validator = Draft202012Validator(_schema())

    auto_feed = _workflow_context_config()
    auto_feed["workflow_context"]["context_compiler_auto_feed"] = True
    with pytest.raises(ValidationError):
        validator.validate(auto_feed)

    end_user_cloud_run = _workflow_context_config()
    end_user_cloud_run["product_onboarding"]["setup"]["end_user_infrastructure"]["cloud_run_required"] = True
    with pytest.raises(ValidationError):
        validator.validate(end_user_cloud_run)

    production_claim = _workflow_context_config()
    production_claim["safety"]["production_platform_claim"] = True
    with pytest.raises(ValidationError):
        validator.validate(production_claim)


def test_explicit_workflow_context_disabled_is_noop(tmp_path: Path) -> None:
    assert resolve_repo_intelligence_workflow_context(None, project_root=tmp_path) == {
        "status": "disabled",
        "enabled": False,
        "decision": "repo_intelligence_workflow_context_not_enabled",
    }
    assert resolve_repo_intelligence_workflow_context({"enabled": False}, project_root=tmp_path) == {
        "status": "disabled",
        "enabled": False,
        "decision": "repo_intelligence_workflow_context_not_enabled",
    }


def test_explicit_workflow_context_accepts_visible_handoff_pointer(tmp_path: Path) -> None:
    handoff_path = tmp_path / "repo-query-handoff.md"
    handoff_path.write_text(build_repo_query_context_pack(query_result=_query_result()), encoding="utf-8")

    result = resolve_repo_intelligence_workflow_context(
        _workflow_context_config(),
        project_root=tmp_path,
    )

    assert result["status"] == "accepted"
    assert result["decision"] == "accepted_repo_intelligence_workflow_context"
    assert result["context"]["mode"] == "visible_operator_handoff"
    assert result["context"]["consumer"] == "workflow_runtime"
    assert result["context"]["handoff_path"] == str(handoff_path)
    assert len(result["context"]["markdown_sha256"]) == 64
    assert result["context"]["operator_visible"] is True
    assert result["context"]["automatic_prompt_injection"] is False
    assert result["context"]["context_compiler_auto_feed"] is False
    assert result["context"]["write_context_artifacts"] is False
    assert result["source_metadata"]["vector_namespace_key_prefix"] == "repo_chunk::demo::space::"
    assert result["source_metadata"]["source_paths"] == ["pkg/main.py"]
    assert result["product_onboarding"]["required_end_user_steps"] == ["install_github_app", "select_repositories"]
    assert result["workflow_opt_in"]["decision"] == "accepted_repo_intelligence_workflow_opt_in"
    assert result["safety"] == {
        "hidden_prompt_injection": False,
        "mcp_tool_exposure": False,
        "root_export": False,
        "context_compiler_auto_feed": False,
        "vector_writes": False,
        "artifact_writes": False,
        "live_adapter_execution": False,
        "support_widening": False,
        "production_platform_claim": False,
    }
    assert result["support_widening"] is False
    assert result["production_platform_claim"] is False
    assert result["live_adapter_execution_allowed"] is False


def test_explicit_workflow_context_blocks_stale_or_unsafe_handoff(tmp_path: Path) -> None:
    query_result = _query_result()
    query_result["summary"]["stale_candidates"] = 1
    handoff_path = tmp_path / "stale.md"
    handoff_path.write_text(build_repo_query_context_pack(query_result=query_result), encoding="utf-8")

    result = resolve_repo_intelligence_workflow_context(
        _workflow_context_config("stale.md"),
        project_root=tmp_path,
    )

    assert result["status"] == "blocked"
    assert result["decision"] == "blocked_repo_intelligence_workflow_context"
    assert "workflow_opt_in_freshness_not_current_only" in result["findings"]
    assert "workflow_opt_in_stale_candidates_not_zero" in result["findings"]
    assert result["workflow_opt_in"]["decision"] == "blocked_repo_intelligence_workflow_opt_in"
    assert result["support_widening"] is False
    assert result["production_platform_claim"] is False
    assert result["live_adapter_execution_allowed"] is False


def test_explicit_workflow_context_blocks_unsafe_onboarding_or_auto_feed(tmp_path: Path) -> None:
    handoff_path = tmp_path / "repo-query-handoff.md"
    handoff_path.write_text(build_repo_query_context_pack(query_result=_query_result()), encoding="utf-8")
    config = _workflow_context_config()
    config["product_onboarding"]["setup"]["end_user_infrastructure"]["webhook_required"] = True
    config["workflow_context"]["default_enabled"] = True
    config["workflow_context"]["automatic_prompt_injection"] = True
    config["safety"]["mcp_tool_exposure"] = True

    result = resolve_repo_intelligence_workflow_context(config, project_root=tmp_path)

    assert result["status"] == "blocked"
    assert "product_onboarding_end_user_webhook_required_not_false" in result["findings"]
    assert "workflow_context_default_enabled_not_false" in result["findings"]
    assert "workflow_context_automatic_prompt_injection_not_false" in result["findings"]
    assert "safety_mcp_tool_exposure_not_false" in result["findings"]


def test_explicit_workflow_context_does_not_auto_ingest_into_context_compiler(tmp_path: Path) -> None:
    handoff_path = tmp_path / "repo-query-handoff.md"
    handoff = build_repo_query_context_pack(query_result=_query_result())
    handoff_path.write_text(handoff, encoding="utf-8")
    resolved = resolve_repo_intelligence_workflow_context(_workflow_context_config(), project_root=tmp_path)

    result = compile_context(
        {
            "session_id": "test",
            "ephemeral_decisions": [],
            "repo_intelligence_workflow_context": resolved,
            "repo_query_context": handoff,
        },
        profile="TASK_EXECUTION",
    )

    assert result.preamble == ""
    assert "Repo Query Context Pack" not in result.preamble
    assert result.items_included == 0


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
