from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from ao_kernel._internal.repo_intelligence.artifacts import validate_repo_vector_write_plan
from ao_kernel._internal.repo_intelligence.python_ast_indexer import build_python_ast_indexes
from ao_kernel._internal.repo_intelligence.repo_chunker import build_repo_chunks
from ao_kernel._internal.repo_intelligence.repo_vector_plan import build_repo_vector_write_plan
from ao_kernel._internal.repo_intelligence.scanner import scan_repo


def _make_vector_plan_project(tmp_path: Path) -> Path:
    project = tmp_path / "vector-plan-project"
    (project / ".ao" / "context").mkdir(parents=True)
    (project / "pkg").mkdir()
    (project / "pkg" / "__init__.py").write_text("from .main import run\n", encoding="utf-8")
    (project / "pkg" / "main.py").write_text(
        "\n".join(
            [
                "VALUE = 1",
                "",
                "def run():",
                "    return VALUE",
                "",
            ]
        ),
        encoding="utf-8",
    )
    (project / "README.md").write_text("# Vector Plan Project\n\nLocal docs.\n", encoding="utf-8")
    (project / "pyproject.toml").write_text("[project]\nname = \"vector-plan-project\"\n", encoding="utf-8")
    return project


def _build_chunks(project: Path) -> dict[str, Any]:
    repo_map = scan_repo(project)
    import_graph, symbol_index = build_python_ast_indexes(project, repo_map)
    return build_repo_chunks(project, repo_map=repo_map, import_graph=import_graph, symbol_index=symbol_index)


def _build_plan(repo_chunks: dict[str, Any], previous_index_manifest: dict[str, Any] | None = None) -> dict[str, Any]:
    return build_repo_vector_write_plan(
        repo_chunks=repo_chunks,
        embedding_provider="openai",
        embedding_model="text-embedding-3-small",
        embedding_dimension=1536,
        previous_index_manifest=previous_index_manifest,
    )


def _stable_plan(plan: dict[str, Any]) -> dict[str, Any]:
    normalized = json.loads(json.dumps(plan, sort_keys=True))
    normalized["generator"]["generated_at"] = "<timestamp>"
    return normalized


def test_build_repo_vector_write_plan_is_schema_valid_and_side_effect_free(tmp_path: Path) -> None:
    project = _make_vector_plan_project(tmp_path)
    repo_chunks = _build_chunks(project)

    plan = _build_plan(repo_chunks)

    validate_repo_vector_write_plan(plan)
    assert plan["artifact_kind"] == "repo_vector_write_plan"
    assert plan["planner"]["mode"] == "dry_run"
    assert plan["summary"]["embedding_calls"] == 0
    assert plan["summary"]["vector_writes"] == 0
    assert plan["summary"]["planned_upserts"] == len(repo_chunks["chunks"])
    assert plan["summary"]["planned_deletes"] == 0
    assert all(str(item["key"]).startswith("repo_chunk::") for item in plan["planned_upserts"])
    assert str(project) not in json.dumps(plan["planned_upserts"], sort_keys=True)


def test_build_repo_vector_write_plan_is_deterministic_except_generator_timestamp(tmp_path: Path) -> None:
    project = _make_vector_plan_project(tmp_path)
    repo_chunks = _build_chunks(project)

    first = _build_plan(repo_chunks)
    second = _build_plan(repo_chunks)

    assert _stable_plan(first) == _stable_plan(second)


def test_build_repo_vector_write_plan_records_stale_key_deletes_deterministically(tmp_path: Path) -> None:
    project = _make_vector_plan_project(tmp_path)
    repo_chunks = _build_chunks(project)
    current = _build_plan(repo_chunks)
    stale_key = (
        "repo_chunk::"
        f"{current['vector_namespace']['project_root_identity_sha256']}::"
        f"{current['embedding_space']['embedding_space_id']}::"
        f"repo-chunk-v1:{'a' * 64}"
    )
    previous = {
        "project": current["project"],
        "embedding_space": current["embedding_space"],
        "indexed_keys": [current["planned_upserts"][0]["key"], stale_key],
    }

    plan = _build_plan(repo_chunks, previous_index_manifest=previous)

    validate_repo_vector_write_plan(plan)
    assert plan["summary"]["previous_indexed_keys"] == 2
    assert plan["summary"]["planned_deletes"] == 1
    assert plan["planned_deletes"] == [{"operation": "delete", "key": stale_key}]


def test_build_repo_vector_write_plan_ignores_previous_manifest_for_other_project(tmp_path: Path) -> None:
    project = _make_vector_plan_project(tmp_path)
    repo_chunks = _build_chunks(project)
    current = _build_plan(repo_chunks)
    previous = {
        "project": {**current["project"], "root_identity_sha256": "b" * 64},
        "embedding_space": current["embedding_space"],
        "indexed_keys": [current["planned_upserts"][0]["key"]],
    }

    plan = _build_plan(repo_chunks, previous_index_manifest=previous)

    validate_repo_vector_write_plan(plan)
    assert plan["planned_deletes"] == []
    assert plan["diagnostics"] == [
        {
            "code": "previous_index_manifest_project_mismatch",
            "message": "prior vector index manifest belongs to a different project identity",
        }
    ]


def test_build_repo_vector_write_plan_requires_previous_manifest_namespace_for_deletes(tmp_path: Path) -> None:
    project = _make_vector_plan_project(tmp_path)
    repo_chunks = _build_chunks(project)
    previous = {
        "indexed_keys": [f"repo_chunk::{'b' * 64}::{'c' * 64}::repo-chunk-v1:{'d' * 64}"],
    }

    plan = _build_plan(repo_chunks, previous_index_manifest=previous)

    validate_repo_vector_write_plan(plan)
    assert plan["summary"]["previous_indexed_keys"] == 0
    assert plan["planned_deletes"] == []
    assert plan["diagnostics"] == [
        {
            "code": "previous_index_manifest_project_identity_missing",
            "message": "prior vector index manifest has no project identity; stale deletes are not planned",
        }
    ]


@pytest.mark.parametrize(
    ("provider", "model", "dimension", "message"),
    [
        ("", "text-embedding-3-small", 1536, "embedding_provider must be non-empty"),
        ("openai", "", 1536, "embedding_model must be non-empty"),
        ("openai", "text-embedding-3-small", 0, "embedding_dimension must be positive"),
    ],
)
def test_build_repo_vector_write_plan_rejects_invalid_embedding_identity(
    tmp_path: Path,
    provider: str,
    model: str,
    dimension: int,
    message: str,
) -> None:
    project = _make_vector_plan_project(tmp_path)
    repo_chunks = _build_chunks(project)

    with pytest.raises(ValueError, match=message):
        build_repo_vector_write_plan(
            repo_chunks=repo_chunks,
            embedding_provider=provider,
            embedding_model=model,
            embedding_dimension=dimension,
        )
