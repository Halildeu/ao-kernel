from __future__ import annotations

import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError

from ao_kernel.context.context_compiler import compile_context


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
