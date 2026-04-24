from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ao_kernel._internal.repo_intelligence.python_ast_indexer import build_python_ast_indexes
from ao_kernel._internal.repo_intelligence.repo_chunker import build_repo_chunks
from ao_kernel._internal.repo_intelligence.scanner import scan_repo
from ao_kernel._internal.repo_intelligence.artifacts import validate_repo_chunks


def _make_chunk_project(tmp_path: Path) -> Path:
    project = tmp_path / "chunk-project"
    (project / ".ao").mkdir(parents=True)
    (project / "pkg").mkdir()
    (project / "pkg" / "__init__.py").write_text("from .main import run\n", encoding="utf-8")
    (project / "pkg" / "main.py").write_text(
        "\n".join(
            [
                "import os",
                "",
                "VALUE = 1",
                "",
                "class App:",
                "    def run(self):",
                "        return os.getcwd()",
                "",
                "def run():",
                "    return App().run()",
                "",
            ]
        ),
        encoding="utf-8",
    )
    (project / "README.md").write_text("# Chunk Project\n\nSome docs.\n", encoding="utf-8")
    (project / "config.json").write_text('{"enabled": true}\n', encoding="utf-8")
    (project / ".env").write_text("TOKEN=secret\n", encoding="utf-8")
    (project / "image.png").write_bytes(b"\x89PNG\r\n")
    (project / "pyproject.toml").write_text("[project]\nname = \"chunk-project\"\n", encoding="utf-8")
    return project


def _build_chunks(project: Path) -> dict[str, Any]:
    repo_map = scan_repo(project)
    import_graph, symbol_index = build_python_ast_indexes(project, repo_map)
    chunks = build_repo_chunks(
        project,
        repo_map=repo_map,
        import_graph=import_graph,
        symbol_index=symbol_index,
    )
    validate_repo_chunks(chunks)
    return chunks


def test_build_repo_chunks_writes_schema_valid_symbol_and_file_slice_boundaries(tmp_path: Path) -> None:
    project = _make_chunk_project(tmp_path)

    chunks = _build_chunks(project)

    assert chunks["artifact_kind"] == "repo_chunks"
    assert chunks["chunker"]["version"] == "repo-chunker.v1"
    chunk_records = chunks["chunks"]
    assert chunks["summary"]["chunks"] == len(chunk_records)
    assert any(item["kind"] == "symbol" and item["symbol"] == "App" for item in chunk_records)
    assert any(item["kind"] == "symbol" and item["symbol"] == "run" for item in chunk_records)
    assert any(item["kind"] == "file_slice" and item["source_path"] == "README.md" for item in chunk_records)
    assert all(str(item["source_path"]).startswith("/") is False for item in chunk_records)
    assert str(project) not in json.dumps(chunk_records, sort_keys=True)


def test_build_repo_chunks_is_deterministic_except_generator_timestamp(tmp_path: Path) -> None:
    project = _make_chunk_project(tmp_path)

    first = _build_chunks(project)
    second = _build_chunks(project)

    assert first["chunks"] == second["chunks"]
    assert first["diagnostics"] == second["diagnostics"]
    assert first["source_artifacts"] == second["source_artifacts"]


def test_build_repo_chunks_records_skip_diagnostics_without_embedding_secret_like_files(tmp_path: Path) -> None:
    project = _make_chunk_project(tmp_path)

    chunks = _build_chunks(project)

    diagnostics = {(item["path"], item["code"]) for item in chunks["diagnostics"]}
    assert (".env", "chunk_secret_like_skipped") in diagnostics
    assert ("image.png", "chunk_secret_like_skipped") in diagnostics
    assert all(item["source_path"] != ".env" for item in chunks["chunks"])
    assert all(item["source_path"] != "image.png" for item in chunks["chunks"])


def test_build_repo_chunks_rejects_repo_map_path_escape(tmp_path: Path) -> None:
    project = _make_chunk_project(tmp_path)
    outside = tmp_path / "outside.md"
    outside.write_text("# outside\n", encoding="utf-8")
    repo_map = scan_repo(project)
    repo_map["files"].append(
        {
            "path": "../outside.md",
            "kind": "file",
            "size_bytes": outside.stat().st_size,
            "language": "markdown",
        }
    )
    import_graph, symbol_index = build_python_ast_indexes(project, repo_map)

    chunks = build_repo_chunks(
        project,
        repo_map=repo_map,
        import_graph=import_graph,
        symbol_index=symbol_index,
    )

    diagnostics = {(item["path"], item["code"]) for item in chunks["diagnostics"]}
    assert ("../outside.md", "chunk_path_escape_skipped") in diagnostics
    assert all(item["source_path"] != "../outside.md" for item in chunks["chunks"])
