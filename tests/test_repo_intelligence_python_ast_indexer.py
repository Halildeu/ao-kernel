from __future__ import annotations

from pathlib import Path
from typing import Any

from ao_kernel._internal.repo_intelligence.artifacts import (
    validate_python_import_graph,
    validate_python_symbol_index,
)
from ao_kernel._internal.repo_intelligence.python_ast_indexer import build_python_ast_indexes
from ao_kernel._internal.repo_intelligence.scanner import scan_repo


def _make_python_repo(tmp_path: Path) -> Path:
    project = tmp_path / "python-project"
    (project / ".ao").mkdir(parents=True)
    (project / "pkg").mkdir()
    (project / "pkg" / "__init__.py").write_text("from .module import Thing\n", encoding="utf-8")
    (project / "pkg" / "module.py").write_text(
        "\n".join(
            [
                "import os",
                "import json as js",
                "from . import sibling",
                "from .sibling import Helper as Alias",
                "from collections import defaultdict",
                "VALUE = 1",
                "x, y = (1, 2)",
                "class Thing:",
                "    pass",
                "def make():",
                "    return Thing()",
                "async def amake():",
                "    return Thing()",
                "",
            ]
        ),
        encoding="utf-8",
    )
    (project / "pkg" / "sibling.py").write_text("class Helper:\n    pass\n", encoding="utf-8")
    (project / "bad.py").write_text("def broken(:\n", encoding="utf-8")
    (project / "pyproject.toml").write_text("[project]\nname = \"python-project\"\n", encoding="utf-8")
    return project


def _stable_doc(doc: dict[str, Any]) -> dict[str, Any]:
    stable = dict(doc)
    stable["generator"] = dict(doc["generator"])
    stable["generator"]["generated_at"] = "<timestamp>"
    return stable


def test_build_python_ast_indexes_are_schema_valid_and_deterministic(tmp_path: Path) -> None:
    project = _make_python_repo(tmp_path)
    repo_map = scan_repo(project)

    first_graph, first_symbols = build_python_ast_indexes(project, repo_map)
    second_graph, second_symbols = build_python_ast_indexes(project, repo_map)

    validate_python_import_graph(first_graph)
    validate_python_symbol_index(first_symbols)
    assert _stable_doc(first_graph) == _stable_doc(second_graph)
    assert _stable_doc(first_symbols) == _stable_doc(second_symbols)
    assert first_graph["summary"]["python_modules"] == 4
    assert first_symbols["summary"]["python_modules"] == 4


def test_build_python_ast_indexes_resolve_import_edges(tmp_path: Path) -> None:
    project = _make_python_repo(tmp_path)
    repo_map = scan_repo(project)

    import_graph, _symbol_index = build_python_ast_indexes(project, repo_map)
    edges = {
        (
            item["source_module"],
            item["kind"],
            item["target"],
            item["alias"],
            item["resolved"],
        )
        for item in import_graph["edges"]
    }

    assert ("pkg.module", "import", "os", None, True) in edges
    assert ("pkg.module", "import", "json", "js", True) in edges
    assert ("pkg.module", "from_import", "pkg.sibling", None, True) in edges
    assert ("pkg.module", "from_import", "pkg.sibling.Helper", "Alias", True) in edges
    assert ("pkg.module", "from_import", "collections.defaultdict", None, True) in edges


def test_build_python_ast_indexes_collect_top_level_symbols(tmp_path: Path) -> None:
    project = _make_python_repo(tmp_path)
    repo_map = scan_repo(project)

    _import_graph, symbol_index = build_python_ast_indexes(project, repo_map)
    symbols = {
        (
            item["module"],
            item["kind"],
            item["name"],
            item.get("alias_of"),
        )
        for item in symbol_index["symbols"]
    }

    assert ("pkg.module", "class", "Thing", None) in symbols
    assert ("pkg.module", "function", "make", None) in symbols
    assert ("pkg.module", "async_function", "amake", None) in symbols
    assert ("pkg.module", "assignment", "VALUE", None) in symbols
    assert ("pkg.module", "assignment", "x", None) in symbols
    assert ("pkg.module", "assignment", "y", None) in symbols
    assert ("pkg.module", "imported_name", "js", "json") in symbols
    assert ("pkg.module", "imported_name", "Alias", "pkg.sibling.Helper") in symbols


def test_build_python_ast_indexes_record_syntax_errors_without_failing_scan(tmp_path: Path) -> None:
    project = _make_python_repo(tmp_path)
    repo_map = scan_repo(project)

    import_graph, symbol_index = build_python_ast_indexes(project, repo_map)
    graph_diagnostics = {(item["path"], item["code"]) for item in import_graph["diagnostics"]}
    symbol_diagnostics = {(item["path"], item["code"]) for item in symbol_index["diagnostics"]}

    assert ("bad.py", "python_syntax_error") in graph_diagnostics
    assert ("bad.py", "python_syntax_error") in symbol_diagnostics
    assert import_graph["summary"]["diagnostics"] == 1
    assert symbol_index["summary"]["diagnostics"] == 1
