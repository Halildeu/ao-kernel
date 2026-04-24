"""Deterministic Markdown context-pack rendering for repo intelligence."""

from __future__ import annotations

from typing import Any, Mapping

JsonDict = dict[str, Any]

MAX_FILES = 200
MAX_ENTRYPOINTS = 80
MAX_MODULES = 120
MAX_IMPORT_EDGES = 200
MAX_SYMBOLS = 200
MAX_CHUNKS = 160
MAX_DIAGNOSTICS = 120


def build_agent_context_pack(
    *,
    repo_map: Mapping[str, Any],
    import_graph: Mapping[str, Any],
    symbol_index: Mapping[str, Any],
    repo_chunks: Mapping[str, Any] | None = None,
) -> str:
    """Render a deterministic Markdown context pack from local artifacts."""
    lines: list[str] = [
        "# Agent Context Pack",
        "",
        "## Generation Boundary",
        "",
        "- Source: local ao-kernel repo-intelligence artifacts.",
        "- Scope: deterministic repository map, Python import graph, top-level symbol index, and chunk manifest.",
        "- Excluded: LLM summary, embedding calls, vector writes, MCP tools, root exports, and target-specific exports.",
        "",
    ]
    _append_project(lines, repo_map)
    _append_summary(lines, repo_map, import_graph, symbol_index, repo_chunks)
    _append_languages(lines, repo_map)
    _append_entrypoints(lines, repo_map)
    _append_modules(lines, import_graph)
    _append_import_edges(lines, import_graph)
    _append_symbols(lines, symbol_index)
    if repo_chunks is not None:
        _append_chunks(lines, repo_chunks)
    _append_diagnostics(lines, repo_map, import_graph, repo_chunks)
    _append_files(lines, repo_map)
    _append_limits(lines)
    return "\n".join(lines).rstrip() + "\n"


def _append_project(lines: list[str], repo_map: Mapping[str, Any]) -> None:
    project = _mapping(repo_map.get("project"))
    rows = [
        ("Name", _string(project.get("name"))),
        ("Root", _string(project.get("root"))),
        ("Root name", _string(project.get("root_name"))),
    ]
    lines.extend(["## Project", "", "| Field | Value |", "|---|---|"])
    lines.extend(f"| {_md(field)} | {_md(value)} |" for field, value in rows)
    lines.append("")


def _append_summary(
    lines: list[str],
    repo_map: Mapping[str, Any],
    import_graph: Mapping[str, Any],
    symbol_index: Mapping[str, Any],
    repo_chunks: Mapping[str, Any] | None,
) -> None:
    repo_summary = _mapping(repo_map.get("summary"))
    graph_summary = _mapping(import_graph.get("summary"))
    symbol_summary = _mapping(symbol_index.get("summary"))
    chunk_summary = _mapping(repo_chunks.get("summary")) if repo_chunks is not None else {}
    rows = [
        ("Included files", _int(repo_summary.get("included_files"))),
        ("Included directories", _int(repo_summary.get("included_directories"))),
        ("Ignored paths", _int(repo_summary.get("ignored_paths"))),
        ("Repo diagnostics", _int(repo_summary.get("diagnostics"))),
        ("Python packages", _int(repo_summary.get("python_packages"))),
        ("Python modules", _int(repo_summary.get("python_modules"))),
        ("Python entrypoints", _int(repo_summary.get("python_entrypoints"))),
        ("Import edges", _int(graph_summary.get("import_edges"))),
        ("Symbols", _int(symbol_summary.get("symbols"))),
        ("Chunks", _int(chunk_summary.get("chunks"))),
        ("Chunked source files", _int(chunk_summary.get("source_files"))),
        ("AST diagnostics", _int(graph_summary.get("diagnostics"))),
        ("Chunk diagnostics", _int(chunk_summary.get("diagnostics"))),
    ]
    lines.extend(["## Repository Summary", "", "| Metric | Count |", "|---|---:|"])
    lines.extend(f"| {_md(metric)} | {count} |" for metric, count in rows)
    lines.append("")


def _append_languages(lines: list[str], repo_map: Mapping[str, Any]) -> None:
    languages = _mapping(repo_map.get("languages"))
    rows = sorted((str(name), _int(count)) for name, count in languages.items())
    lines.extend(["## Languages", ""])
    if not rows:
        lines.extend(["No language records.", ""])
        return
    lines.extend(["| Language | Files |", "|---|---:|"])
    lines.extend(f"| {_md(name)} | {count} |" for name, count in rows)
    lines.append("")


def _append_entrypoints(lines: list[str], repo_map: Mapping[str, Any]) -> None:
    python_section = _mapping(repo_map.get("python"))
    entrypoints = _sorted_records(_list(python_section.get("entrypoints")), ("kind", "name", "path"))
    lines.extend(["## Python Entrypoints", ""])
    _append_limited_table(
        lines,
        records=entrypoints,
        columns=[
            ("Kind", "kind"),
            ("Name", "name"),
            ("Path", "path"),
            ("Target", "target"),
            ("Reason", "reason"),
        ],
        limit=MAX_ENTRYPOINTS,
    )


def _append_modules(lines: list[str], import_graph: Mapping[str, Any]) -> None:
    modules = _sorted_records(_list(import_graph.get("modules")), ("module", "path"))
    lines.extend(["## Python Modules", ""])
    _append_limited_table(
        lines,
        records=modules,
        columns=[
            ("Module", "module"),
            ("Path", "path"),
            ("Kind", "kind"),
            ("Symbols", "symbols"),
        ],
        limit=MAX_MODULES,
    )


def _append_import_edges(lines: list[str], import_graph: Mapping[str, Any]) -> None:
    edges = _sorted_records(_list(import_graph.get("edges")), ("source_module", "target", "alias", "lineno"))
    lines.extend(["## Import Edges", ""])
    _append_limited_table(
        lines,
        records=edges,
        columns=[
            ("Source", "source_module"),
            ("Target", "target"),
            ("Kind", "kind"),
            ("Alias", "alias"),
            ("Line", "lineno"),
        ],
        limit=MAX_IMPORT_EDGES,
    )


def _append_symbols(lines: list[str], symbol_index: Mapping[str, Any]) -> None:
    symbols = _sorted_records(_list(symbol_index.get("symbols")), ("module", "name", "kind", "lineno"))
    lines.extend(["## Top-Level Symbols", ""])
    _append_limited_table(
        lines,
        records=symbols,
        columns=[
            ("Qualified name", "qualified_name"),
            ("Kind", "kind"),
            ("Path", "path"),
            ("Line", "lineno"),
            ("Alias of", "alias_of"),
        ],
        limit=MAX_SYMBOLS,
    )


def _append_chunks(lines: list[str], repo_chunks: Mapping[str, Any]) -> None:
    chunks = _sorted_records(_list(repo_chunks.get("chunks")), ("source_path", "start_line", "end_line", "chunk_id"))
    lines.extend(["## Repo Chunks", ""])
    _append_limited_table(
        lines,
        records=chunks,
        columns=[
            ("Path", "source_path"),
            ("Kind", "kind"),
            ("Module", "module"),
            ("Symbol", "symbol"),
            ("Start", "start_line"),
            ("End", "end_line"),
            ("Tokens", "token_estimate"),
        ],
        limit=MAX_CHUNKS,
    )


def _append_diagnostics(
    lines: list[str],
    repo_map: Mapping[str, Any],
    import_graph: Mapping[str, Any],
    repo_chunks: Mapping[str, Any] | None,
) -> None:
    diagnostic_records: list[Mapping[str, Any]] = [
        {"source": "repo_map", **item}
        for item in _list(repo_map.get("diagnostics"))
        if isinstance(item, Mapping)
    ]
    diagnostic_records.extend(
        {"source": "python_ast", **item}
        for item in _list(import_graph.get("diagnostics"))
        if isinstance(item, Mapping)
    )
    if repo_chunks is not None:
        diagnostic_records.extend(
            {"source": "repo_chunks", **item}
            for item in _list(repo_chunks.get("diagnostics"))
            if isinstance(item, Mapping)
        )
    diagnostics = _sorted_records(diagnostic_records, ("path", "code", "source", "lineno", "offset"))
    lines.extend(["## Diagnostics", ""])
    _append_limited_table(
        lines,
        records=diagnostics,
        columns=[
            ("Source", "source"),
            ("Path", "path"),
            ("Code", "code"),
            ("Line", "lineno"),
            ("Message", "message"),
        ],
        limit=MAX_DIAGNOSTICS,
    )


def _append_files(lines: list[str], repo_map: Mapping[str, Any]) -> None:
    files = _sorted_records(_list(repo_map.get("files")), ("path",))
    lines.extend(["## Source Files", ""])
    _append_limited_table(
        lines,
        records=files,
        columns=[
            ("Path", "path"),
            ("Language", "language"),
            ("Bytes", "size_bytes"),
        ],
        limit=MAX_FILES,
    )


def _append_limits(lines: list[str]) -> None:
    lines.extend(
        [
            "## Pack Limits",
            "",
            "| Section | Limit |",
            "|---|---:|",
            f"| Python Entrypoints | {MAX_ENTRYPOINTS} |",
            f"| Python Modules | {MAX_MODULES} |",
            f"| Import Edges | {MAX_IMPORT_EDGES} |",
            f"| Top-Level Symbols | {MAX_SYMBOLS} |",
            f"| Repo Chunks | {MAX_CHUNKS} |",
            f"| Diagnostics | {MAX_DIAGNOSTICS} |",
            f"| Source Files | {MAX_FILES} |",
            "",
        ]
    )


def _append_limited_table(
    lines: list[str],
    *,
    records: list[Mapping[str, Any]],
    columns: list[tuple[str, str]],
    limit: int,
) -> None:
    if not records:
        lines.extend(["No records.", ""])
        return
    visible = records[:limit]
    header = "| " + " | ".join(_md(name) for name, _field in columns) + " |"
    divider = "| " + " | ".join("---" for _name, _field in columns) + " |"
    lines.extend([header, divider])
    for record in visible:
        values = [_md(_string(record.get(field))) for _name, field in columns]
        lines.append("| " + " | ".join(values) + " |")
    if len(records) > limit:
        lines.append("")
        lines.append(f"Truncated: showing {limit} of {len(records)} records.")
    lines.append("")


def _mapping(value: Any) -> Mapping[str, Any]:
    if isinstance(value, Mapping):
        return value
    return {}


def _list(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    return []


def _sorted_records(records: list[Any], fields: tuple[str, ...]) -> list[Mapping[str, Any]]:
    mapped = [record for record in records if isinstance(record, Mapping)]
    return sorted(mapped, key=lambda item: tuple(_string(item.get(field)) for field in fields))


def _string(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def _int(value: Any) -> int:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    return 0


def _md(value: str) -> str:
    return value.replace("\\", "\\\\").replace("|", "\\|").replace("\n", " ").strip()
