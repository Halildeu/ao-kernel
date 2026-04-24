from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from ao_kernel._internal.repo_intelligence import artifacts
from ao_kernel._internal.repo_intelligence.artifacts import (
    AGENT_PACK_FILENAME,
    AGENT_PACK_FORMAT_REF,
    PYTHON_IMPORT_GRAPH_FILENAME,
    PYTHON_IMPORT_GRAPH_SCHEMA_NAME,
    PYTHON_SYMBOL_INDEX_FILENAME,
    PYTHON_SYMBOL_INDEX_SCHEMA_NAME,
    REPO_INDEX_MANIFEST_FILENAME,
    REPO_INDEX_MANIFEST_SCHEMA_NAME,
    REPO_MAP_FILENAME,
    REPO_MAP_SCHEMA_NAME,
    validate_python_import_graph,
    validate_python_symbol_index,
    validate_repo_index_manifest,
    validate_repo_map,
    write_repo_scan_artifacts,
)
from ao_kernel._internal.repo_intelligence.context_pack_builder import build_agent_context_pack
from ao_kernel._internal.repo_intelligence.python_ast_indexer import build_python_ast_indexes
from ao_kernel._internal.repo_intelligence.scanner import scan_repo
from ao_kernel.config import load_default


def _repo_with_workspace(tmp_path: Path) -> Path:
    project = tmp_path / "project"
    (project / ".ao" / "context").mkdir(parents=True)
    (project / "pkg").mkdir()
    (project / "pkg" / "__init__.py").write_text("", encoding="utf-8")
    (project / "pkg" / "main.py").write_text("def main():\n    return 0\n", encoding="utf-8")
    (project / "pyproject.toml").write_text("[project]\nname = \"artifact-project\"\n", encoding="utf-8")
    return project


def test_bundled_repo_intelligence_schemas_are_valid() -> None:
    repo_map_schema = load_default("schemas", REPO_MAP_SCHEMA_NAME)
    import_graph_schema = load_default("schemas", PYTHON_IMPORT_GRAPH_SCHEMA_NAME)
    symbol_index_schema = load_default("schemas", PYTHON_SYMBOL_INDEX_SCHEMA_NAME)
    manifest_schema = load_default("schemas", REPO_INDEX_MANIFEST_SCHEMA_NAME)

    Draft202012Validator.check_schema(repo_map_schema)
    Draft202012Validator.check_schema(import_graph_schema)
    Draft202012Validator.check_schema(symbol_index_schema)
    Draft202012Validator.check_schema(manifest_schema)
    assert repo_map_schema["$id"] == "urn:ao:repo-map:v1"
    assert import_graph_schema["$id"] == "urn:ao:python-import-graph:v1"
    assert symbol_index_schema["$id"] == "urn:ao:python-symbol-index:v1"
    assert manifest_schema["$id"] == "urn:ao:repo-index-manifest:v1"


def test_write_repo_scan_artifacts_writes_and_validates_schema_backed_outputs(tmp_path: Path) -> None:
    project = _repo_with_workspace(tmp_path)
    repo_map = scan_repo(project)

    result = write_repo_scan_artifacts(context_dir=project / ".ao" / "context", repo_map=repo_map)
    repo_map_path = project / ".ao" / "context" / REPO_MAP_FILENAME
    manifest_path = project / ".ao" / "context" / REPO_INDEX_MANIFEST_FILENAME
    written_repo_map = json.loads(repo_map_path.read_text(encoding="utf-8"))
    written_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    validate_repo_map(written_repo_map)
    validate_repo_index_manifest(written_manifest)
    assert repo_map_path.is_file()
    assert manifest_path.is_file()
    assert [item["path"] for item in result["artifacts"]] == [
        ".ao/context/repo_map.json",
        ".ao/context/repo_index_manifest.json",
    ]
    assert written_manifest["artifacts"][0]["schema_ref"] == REPO_MAP_SCHEMA_NAME


def test_write_repo_scan_artifacts_writes_ast_artifacts_and_manifest_records(tmp_path: Path) -> None:
    project = _repo_with_workspace(tmp_path)
    repo_map = scan_repo(project)
    import_graph, symbol_index = build_python_ast_indexes(project, repo_map)

    result = write_repo_scan_artifacts(
        context_dir=project / ".ao" / "context",
        repo_map=repo_map,
        import_graph=import_graph,
        symbol_index=symbol_index,
    )
    context_dir = project / ".ao" / "context"
    written_import_graph = json.loads((context_dir / PYTHON_IMPORT_GRAPH_FILENAME).read_text(encoding="utf-8"))
    written_symbol_index = json.loads((context_dir / PYTHON_SYMBOL_INDEX_FILENAME).read_text(encoding="utf-8"))
    written_manifest = json.loads((context_dir / REPO_INDEX_MANIFEST_FILENAME).read_text(encoding="utf-8"))

    validate_python_import_graph(written_import_graph)
    validate_python_symbol_index(written_symbol_index)
    validate_repo_index_manifest(written_manifest)
    assert [item["path"] for item in result["artifacts"]] == [
        ".ao/context/repo_map.json",
        ".ao/context/import_graph.json",
        ".ao/context/symbol_index.json",
        ".ao/context/repo_index_manifest.json",
    ]
    assert [item["schema_ref"] for item in written_manifest["artifacts"]] == [
        REPO_MAP_SCHEMA_NAME,
        PYTHON_IMPORT_GRAPH_SCHEMA_NAME,
        PYTHON_SYMBOL_INDEX_SCHEMA_NAME,
    ]


def test_write_repo_scan_artifacts_writes_agent_pack_and_manifest_record(tmp_path: Path) -> None:
    project = _repo_with_workspace(tmp_path)
    repo_map = scan_repo(project)
    import_graph, symbol_index = build_python_ast_indexes(project, repo_map)
    agent_pack = build_agent_context_pack(repo_map=repo_map, import_graph=import_graph, symbol_index=symbol_index)

    result = write_repo_scan_artifacts(
        context_dir=project / ".ao" / "context",
        repo_map=repo_map,
        import_graph=import_graph,
        symbol_index=symbol_index,
        agent_pack=agent_pack,
    )
    context_dir = project / ".ao" / "context"
    written_agent_pack = (context_dir / AGENT_PACK_FILENAME).read_text(encoding="utf-8")
    written_manifest = json.loads((context_dir / REPO_INDEX_MANIFEST_FILENAME).read_text(encoding="utf-8"))

    validate_repo_index_manifest(written_manifest)
    assert "# Agent Context Pack" in written_agent_pack
    assert [item["path"] for item in result["artifacts"]] == [
        ".ao/context/repo_map.json",
        ".ao/context/import_graph.json",
        ".ao/context/symbol_index.json",
        ".ao/context/agent_pack.md",
        ".ao/context/repo_index_manifest.json",
    ]
    agent_pack_record = written_manifest["artifacts"][3]
    assert agent_pack_record["path"] == ".ao/context/agent_pack.md"
    assert agent_pack_record["format_ref"] == AGENT_PACK_FORMAT_REF
    assert agent_pack_record["media_type"] == "text/markdown"
    assert "schema_ref" not in agent_pack_record


def test_artifact_writer_delegates_to_shared_atomic_writer(tmp_path: Path, monkeypatch: Any) -> None:
    project = _repo_with_workspace(tmp_path)
    repo_map = scan_repo(project)
    calls: list[str] = []
    real_writer = artifacts.write_json_atomic

    def tracking_writer(path: Path, data: Any, *, indent: int = 2) -> None:
        calls.append(path.name)
        real_writer(path, data, indent=indent)

    monkeypatch.setattr(artifacts, "write_json_atomic", tracking_writer)

    write_repo_scan_artifacts(context_dir=project / ".ao" / "context", repo_map=repo_map)

    assert calls == [REPO_MAP_FILENAME, REPO_INDEX_MANIFEST_FILENAME]


def test_artifact_writer_delegates_agent_pack_to_shared_text_writer(tmp_path: Path, monkeypatch: Any) -> None:
    project = _repo_with_workspace(tmp_path)
    repo_map = scan_repo(project)
    calls: list[str] = []
    real_writer = artifacts.write_text_atomic

    def tracking_writer(path: Path, content: str) -> None:
        calls.append(path.name)
        real_writer(path, content)

    monkeypatch.setattr(artifacts, "write_text_atomic", tracking_writer)

    write_repo_scan_artifacts(
        context_dir=project / ".ao" / "context",
        repo_map=repo_map,
        agent_pack="# Agent Context Pack\n",
    )

    assert calls == [AGENT_PACK_FILENAME]
