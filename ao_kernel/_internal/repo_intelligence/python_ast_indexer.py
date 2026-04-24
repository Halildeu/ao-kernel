"""Python AST indexing for read-only repo-intelligence artifacts."""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Any, Mapping

import ao_kernel
from ao_kernel._internal.shared.utils import now_iso8601

JsonDict = dict[str, Any]


def build_python_ast_indexes(project_root: str | Path, repo_map: Mapping[str, Any]) -> tuple[JsonDict, JsonDict]:
    """Build deterministic Python import graph and symbol index documents."""
    root = Path(project_root).resolve()
    module_records = _module_records(repo_map)
    import_edges: list[JsonDict] = []
    symbols: list[JsonDict] = []
    diagnostics: list[JsonDict] = []
    module_symbol_counts: dict[str, int] = {str(record["module"]): 0 for record in module_records}

    for record in module_records:
        module = str(record["module"])
        rel_path = str(record["path"])
        source_path = root / rel_path
        try:
            source = source_path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            diagnostics.append(_diagnostic(rel_path, "python_source_unreadable", str(exc)))
            continue

        try:
            tree = ast.parse(source, filename=rel_path)
        except SyntaxError as exc:
            diagnostics.append(
                _diagnostic(
                    rel_path,
                    "python_syntax_error",
                    exc.msg,
                    lineno=exc.lineno,
                    offset=exc.offset,
                )
            )
            continue

        import_edges.extend(_import_edges_for_module(module=module, path=rel_path, tree=tree))
        module_symbols = _symbols_for_module(module=module, path=rel_path, tree=tree)
        module_symbol_counts[module] = len(module_symbols)
        symbols.extend(module_symbols)

    import_edges.sort(key=_edge_sort_key)
    symbols.sort(key=_symbol_sort_key)
    diagnostics.sort(key=_diagnostic_sort_key)
    modules = [
        {
            "kind": str(record["kind"]),
            "module": str(record["module"]),
            "path": str(record["path"]),
            "symbols": module_symbol_counts[str(record["module"])],
        }
        for record in module_records
    ]

    project = dict(repo_map["project"]) if isinstance(repo_map.get("project"), Mapping) else {}
    import_graph = {
        "schema_version": "1",
        "artifact_kind": "python_import_graph",
        "generator": _generator(),
        "project": project,
        "summary": {
            "python_modules": len(modules),
            "import_edges": len(import_edges),
            "diagnostics": len(diagnostics),
        },
        "modules": modules,
        "edges": import_edges,
        "diagnostics": diagnostics,
    }
    symbol_index = {
        "schema_version": "1",
        "artifact_kind": "python_symbol_index",
        "generator": _generator(),
        "project": project,
        "summary": {
            "python_modules": len(modules),
            "symbols": len(symbols),
            "diagnostics": len(diagnostics),
        },
        "modules": modules,
        "symbols": symbols,
        "diagnostics": diagnostics,
    }
    return import_graph, symbol_index


def _generator() -> JsonDict:
    return {
        "name": "ao-kernel",
        "version": ao_kernel.__version__,
        "generated_at": now_iso8601(),
    }


def _module_records(repo_map: Mapping[str, Any]) -> list[JsonDict]:
    python_section = repo_map.get("python")
    if not isinstance(python_section, Mapping):
        return []
    candidates = python_section.get("candidates")
    if not isinstance(candidates, list):
        return []

    records: list[JsonDict] = []
    for candidate in candidates:
        if not isinstance(candidate, Mapping):
            continue
        kind = candidate.get("kind")
        module = candidate.get("module")
        path = candidate.get("path")
        if kind not in {"module", "package"}:
            continue
        if not isinstance(module, str) or not isinstance(path, str):
            continue
        if not path.endswith(".py"):
            continue
        records.append({"kind": kind, "module": module, "path": path})
    records.sort(key=lambda item: (str(item["module"]), str(item["path"])))
    return records


def _import_edges_for_module(*, module: str, path: str, tree: ast.Module) -> list[JsonDict]:
    edges: list[JsonDict] = []
    for node in tree.body:
        if isinstance(node, ast.Import):
            for alias in node.names:
                target = alias.name
                edges.append(
                    {
                        "kind": "import",
                        "source_module": module,
                        "source_path": path,
                        "target": target,
                        "target_module": target,
                        "imported_name": None,
                        "alias": alias.asname,
                        "level": 0,
                        "resolved": True,
                        "lineno": _lineno(node),
                    }
                )
        elif isinstance(node, ast.ImportFrom):
            target_module, resolved = _resolve_from_import_base(
                source_module=module,
                source_path=path,
                level=node.level,
                imported_module=node.module,
            )
            for alias in node.names:
                target = _target_name(target_module=target_module, imported_name=alias.name)
                edges.append(
                    {
                        "kind": "from_import",
                        "source_module": module,
                        "source_path": path,
                        "target": target,
                        "target_module": target_module,
                        "imported_name": alias.name,
                        "alias": alias.asname,
                        "level": node.level,
                        "resolved": resolved,
                        "lineno": _lineno(node),
                    }
                )
    return edges


def _symbols_for_module(*, module: str, path: str, tree: ast.Module) -> list[JsonDict]:
    symbols: list[JsonDict] = []
    for node in tree.body:
        if isinstance(node, ast.ClassDef):
            symbols.append(_symbol(module=module, path=path, name=node.name, kind="class", lineno=_lineno(node)))
        elif isinstance(node, ast.FunctionDef):
            symbols.append(_symbol(module=module, path=path, name=node.name, kind="function", lineno=_lineno(node)))
        elif isinstance(node, ast.AsyncFunctionDef):
            symbols.append(
                _symbol(module=module, path=path, name=node.name, kind="async_function", lineno=_lineno(node))
            )
        elif isinstance(node, ast.Assign):
            for name in _target_names(node.targets):
                symbols.append(_symbol(module=module, path=path, name=name, kind="assignment", lineno=_lineno(node)))
        elif isinstance(node, ast.AnnAssign | ast.AugAssign):
            for name in _target_names([node.target]):
                symbols.append(_symbol(module=module, path=path, name=name, kind="assignment", lineno=_lineno(node)))
        elif _is_type_alias_node(node):
            type_alias_name = _type_alias_name(node)
            if type_alias_name is not None:
                symbols.append(
                    _symbol(module=module, path=path, name=type_alias_name, kind="assignment", lineno=_lineno(node))
                )
        elif isinstance(node, ast.Import):
            for alias in node.names:
                bound_name = alias.asname or alias.name.split(".", 1)[0]
                symbols.append(
                    _symbol(
                        module=module,
                        path=path,
                        name=bound_name,
                        kind="imported_name",
                        lineno=_lineno(node),
                        alias_of=alias.name,
                    )
                )
        elif isinstance(node, ast.ImportFrom):
            target_module, _resolved = _resolve_from_import_base(
                source_module=module,
                source_path=path,
                level=node.level,
                imported_module=node.module,
            )
            for alias in node.names:
                if alias.name == "*":
                    continue
                bound_name = alias.asname or alias.name
                symbols.append(
                    _symbol(
                        module=module,
                        path=path,
                        name=bound_name,
                        kind="imported_name",
                        lineno=_lineno(node),
                        alias_of=_target_name(target_module=target_module, imported_name=alias.name),
                    )
                )
    return symbols


def _resolve_from_import_base(
    *,
    source_module: str,
    source_path: str,
    level: int,
    imported_module: str | None,
) -> tuple[str, bool]:
    if level == 0:
        return imported_module or "", True

    package = source_module if source_path.endswith("/__init__.py") else _parent_module(source_module)
    package_parts = package.split(".") if package else []
    ascend = level - 1
    if ascend > len(package_parts):
        return _raw_relative_module(level=level, imported_module=imported_module), False
    base_parts = package_parts[: len(package_parts) - ascend]
    if imported_module:
        base_parts.extend(imported_module.split("."))
    if not base_parts:
        return _raw_relative_module(level=level, imported_module=imported_module), False
    return ".".join(base_parts), True


def _parent_module(module: str) -> str:
    if "." not in module:
        return ""
    return module.rsplit(".", 1)[0]


def _raw_relative_module(*, level: int, imported_module: str | None) -> str:
    return f"{'.' * level}{imported_module or ''}"


def _target_name(*, target_module: str, imported_name: str | None) -> str:
    if imported_name is None:
        return target_module
    if not target_module:
        return imported_name
    return f"{target_module}.{imported_name}"


def _target_names(nodes: list[ast.expr]) -> list[str]:
    names: list[str] = []
    for node in nodes:
        names.extend(_target_names_from_node(node))
    return sorted(set(names))


def _target_names_from_node(node: ast.expr) -> list[str]:
    if isinstance(node, ast.Name):
        return [node.id]
    if isinstance(node, ast.Tuple | ast.List):
        names: list[str] = []
        for element in node.elts:
            names.extend(_target_names_from_node(element))
        return names
    return []


def _is_type_alias_node(node: ast.AST) -> bool:
    type_alias_cls = getattr(ast, "TypeAlias", None)
    return type_alias_cls is not None and isinstance(node, type_alias_cls)


def _type_alias_name(node: ast.AST) -> str | None:
    name_node = getattr(node, "name", None)
    if isinstance(name_node, ast.Name):
        return name_node.id
    return None


def _symbol(
    *,
    module: str,
    path: str,
    name: str,
    kind: str,
    lineno: int,
    alias_of: str | None = None,
) -> JsonDict:
    record: JsonDict = {
        "kind": kind,
        "module": module,
        "path": path,
        "name": name,
        "qualified_name": f"{module}.{name}",
        "lineno": lineno,
    }
    if alias_of is not None:
        record["alias_of"] = alias_of
    return record


def _diagnostic(
    path: str,
    code: str,
    message: str,
    *,
    lineno: int | None = None,
    offset: int | None = None,
) -> JsonDict:
    record: JsonDict = {"path": path, "code": code, "message": message}
    if lineno is not None:
        record["lineno"] = lineno
    if offset is not None:
        record["offset"] = offset
    return record


def _lineno(node: ast.AST) -> int:
    return int(getattr(node, "lineno", 0) or 0)


def _edge_sort_key(edge: Mapping[str, Any]) -> tuple[str, str, str, str, int]:
    return (
        str(edge["source_module"]),
        str(edge["target"]),
        str(edge.get("alias") or ""),
        str(edge.get("imported_name") or ""),
        int(edge["lineno"]),
    )


def _symbol_sort_key(symbol: Mapping[str, Any]) -> tuple[str, str, str, int]:
    return (
        str(symbol["module"]),
        str(symbol["name"]),
        str(symbol["kind"]),
        int(symbol["lineno"]),
    )


def _diagnostic_sort_key(diagnostic: Mapping[str, Any]) -> tuple[str, str, int, int]:
    return (
        str(diagnostic["path"]),
        str(diagnostic["code"]),
        int(diagnostic.get("lineno") or 0),
        int(diagnostic.get("offset") or 0),
    )
