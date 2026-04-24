from __future__ import annotations

from pathlib import Path
from typing import Any

from ao_kernel._internal.repo_intelligence.context_pack_builder import build_agent_context_pack
from ao_kernel._internal.repo_intelligence.python_ast_indexer import build_python_ast_indexes
from ao_kernel._internal.repo_intelligence.scanner import scan_repo


def _make_context_pack_repo(tmp_path: Path) -> Path:
    project = tmp_path / "context-pack-project"
    (project / ".ao").mkdir(parents=True)
    (project / "pkg").mkdir()
    (project / "pkg" / "__init__.py").write_text("from .main import run\n", encoding="utf-8")
    (project / "pkg" / "main.py").write_text(
        "\n".join(
            [
                "import os",
                "from .worker import Worker",
                "VALUE = 1",
                "class App:",
                "    pass",
                "def run():",
                "    return Worker()",
                "",
            ]
        ),
        encoding="utf-8",
    )
    (project / "pkg" / "worker.py").write_text("class Worker:\n    pass\n", encoding="utf-8")
    (project / "README.md").write_text("# Context Pack\n", encoding="utf-8")
    (project / "pyproject.toml").write_text(
        "[project]\nname = \"context-pack-project\"\n[project.scripts]\ncontext-pack = \"pkg.main:run\"\n",
        encoding="utf-8",
    )
    return project


def _stable_artifacts(project: Path) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    repo_map = scan_repo(project)
    import_graph, symbol_index = build_python_ast_indexes(project, repo_map)
    return repo_map, import_graph, symbol_index


def test_build_agent_context_pack_is_deterministic_and_omits_timestamps(tmp_path: Path) -> None:
    project = _make_context_pack_repo(tmp_path)
    repo_map, import_graph, symbol_index = _stable_artifacts(project)

    first = build_agent_context_pack(repo_map=repo_map, import_graph=import_graph, symbol_index=symbol_index)
    repo_map["generator"]["generated_at"] = "2099-01-01T00:00:00Z"
    import_graph["generator"]["generated_at"] = "2099-01-01T00:00:01Z"
    symbol_index["generator"]["generated_at"] = "2099-01-01T00:00:02Z"
    second = build_agent_context_pack(repo_map=repo_map, import_graph=import_graph, symbol_index=symbol_index)

    assert first == second
    assert "generated_at" not in first
    assert first.endswith("\n")


def test_build_agent_context_pack_renders_core_sections(tmp_path: Path) -> None:
    project = _make_context_pack_repo(tmp_path)
    repo_map, import_graph, symbol_index = _stable_artifacts(project)

    pack = build_agent_context_pack(repo_map=repo_map, import_graph=import_graph, symbol_index=symbol_index)

    assert "# Agent Context Pack" in pack
    assert "## Generation Boundary" in pack
    assert "| Name | context-pack-project |" in pack
    assert "| Python |" not in pack
    assert "| python | 3 |" in pack
    assert "| console_script | context-pack | pyproject.toml | pkg.main:run | project.scripts |" in pack
    assert "| pkg.main | pkg/main.py | module |" in pack
    assert "| pkg.main | pkg.worker.Worker | from_import |" in pack
    assert "| pkg.main.App | class | pkg/main.py |" in pack
    assert "| README.md | markdown |" in pack
    assert "No LLM summary" not in pack
    assert "LLM summary" in pack
