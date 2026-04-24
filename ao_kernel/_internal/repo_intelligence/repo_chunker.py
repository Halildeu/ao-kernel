"""Deterministic repo chunk manifest generation for repo intelligence."""

from __future__ import annotations

import ast
import fnmatch
import hashlib
import json
from pathlib import Path, PurePosixPath
from typing import Any, Mapping

import ao_kernel
from ao_kernel._internal.shared.utils import now_iso8601

JsonDict = dict[str, Any]

CHUNKER_NAME = "ao-kernel-repo-chunker"
CHUNKER_VERSION = "repo-chunker.v1"
CHUNKER_STRATEGY = "python_symbol_then_line_window"
MAX_CHUNK_BYTES = 12_000
TARGET_CHUNK_BYTES = 8_000
OVERLAP_LINES = 8
MAX_FILE_BYTES = 500_000
MAX_CHUNKS_PER_FILE = 200
CHUNK_ID_PREFIX = "repo-chunk-v1:"

_ALLOWED_LANGUAGES = frozenset({"python", "markdown", "toml", "yaml", "json"})
_TEXT_FILE_SUFFIXES = frozenset({".txt", ".rst"})
_TEXT_FILE_NAMES = frozenset({"license", "notice", "changelog", "contributing"})
_SECRET_PATTERNS = (
    ".env",
    ".env.*",
    "*.pem",
    "*.key",
    "*.crt",
    "*.p12",
    "*.pfx",
    "id_rsa",
    "id_dsa",
    "id_ed25519",
    "secrets.*",
    "credentials.*",
    "*.sqlite",
    "*.db",
    "*.png",
    "*.jpg",
    "*.jpeg",
    "*.gif",
    "*.pdf",
    "*.zip",
    "*.tar",
    "*.gz",
)


def build_repo_chunks(
    project_root: str | Path,
    *,
    repo_map: Mapping[str, Any],
    import_graph: Mapping[str, Any],
    symbol_index: Mapping[str, Any],
) -> JsonDict:
    """Build a deterministic chunk-boundary manifest from local repo artifacts.

    This function does not embed text, does not contact a vector backend, and
    does not write files. It records stable boundaries and content hashes only.
    """
    root = Path(project_root).resolve()
    modules_by_path = _modules_by_path(import_graph)
    chunks: list[JsonDict] = []
    diagnostics: list[JsonDict] = []
    chunked_source_paths: set[str] = set()
    skipped_paths: set[str] = set()

    for file_record in _file_records(repo_map):
        rel_path = str(file_record["path"])
        language = str(file_record["language"])
        size_bytes = int(file_record["size_bytes"])

        skip_code = _skip_code(rel_path=rel_path, language=language, size_bytes=size_bytes)
        if skip_code is not None:
            diagnostics.append(_diagnostic(rel_path, skip_code, _skip_message(skip_code, language)))
            skipped_paths.add(rel_path)
            continue

        source_path = _resolve_under_root(root, rel_path)
        if source_path is None:
            diagnostics.append(
                _diagnostic(rel_path, "chunk_path_escape_skipped", "repo_map path resolves outside project root")
            )
            skipped_paths.add(rel_path)
            continue
        try:
            if source_path.is_symlink():
                diagnostics.append(_diagnostic(rel_path, "chunk_symlink_skipped", "symbolic links are not chunked"))
                skipped_paths.add(rel_path)
                continue
            content_bytes = source_path.read_bytes()
        except OSError as exc:
            diagnostics.append(_diagnostic(rel_path, "chunk_file_unreadable", str(exc)))
            skipped_paths.add(rel_path)
            continue

        try:
            text = content_bytes.decode("utf-8")
        except UnicodeDecodeError as exc:
            diagnostics.append(_diagnostic(rel_path, "chunk_file_not_utf8", str(exc)))
            skipped_paths.add(rel_path)
            continue

        line_bytes = content_bytes.splitlines(keepends=True)
        if not line_bytes and content_bytes == b"":
            diagnostics.append(_diagnostic(rel_path, "chunk_empty_file_skipped", "empty file has no chunkable text"))
            skipped_paths.add(rel_path)
            continue
        if not line_bytes:
            line_bytes = [content_bytes]

        module = modules_by_path.get(rel_path)
        file_chunks = _chunks_for_file(
            rel_path=rel_path,
            language=language,
            module=module,
            text=text,
            line_bytes=line_bytes,
            diagnostics=diagnostics,
        )
        if file_chunks:
            chunks.extend(file_chunks[:MAX_CHUNKS_PER_FILE])
            chunked_source_paths.add(rel_path)
            if len(file_chunks) > MAX_CHUNKS_PER_FILE:
                diagnostics.append(
                    _diagnostic(
                        rel_path,
                        "chunk_file_limit_exceeded",
                        f"chunk limit exceeded; kept first {MAX_CHUNKS_PER_FILE} chunks",
                    )
                )
        else:
            skipped_paths.add(rel_path)

    chunks.sort(key=_chunk_sort_key)
    diagnostics.sort(key=_diagnostic_sort_key)

    return {
        "schema_version": "1",
        "artifact_kind": "repo_chunks",
        "generator": {
            "name": "ao-kernel",
            "version": ao_kernel.__version__,
            "generated_at": now_iso8601(),
        },
        "project": dict(repo_map["project"]) if isinstance(repo_map.get("project"), Mapping) else {},
        "chunker": {
            "name": CHUNKER_NAME,
            "version": CHUNKER_VERSION,
            "strategy": CHUNKER_STRATEGY,
            "max_chunk_bytes": MAX_CHUNK_BYTES,
            "target_chunk_bytes": TARGET_CHUNK_BYTES,
            "overlap_lines": OVERLAP_LINES,
            "max_file_bytes": MAX_FILE_BYTES,
            "max_chunks_per_file": MAX_CHUNKS_PER_FILE,
        },
        "source_artifacts": {
            "repo_map_sha256": _stable_document_sha256(repo_map),
            "import_graph_sha256": _stable_document_sha256(import_graph),
            "symbol_index_sha256": _stable_document_sha256(symbol_index),
        },
        "summary": {
            "chunks": len(chunks),
            "source_files": len(chunked_source_paths),
            "skipped_files": len(skipped_paths),
            "diagnostics": len(diagnostics),
        },
        "chunks": chunks,
        "diagnostics": diagnostics,
    }


def _file_records(repo_map: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    files = repo_map.get("files")
    if not isinstance(files, list):
        return []
    records = [item for item in files if isinstance(item, Mapping)]
    return sorted(records, key=lambda item: str(item.get("path") or ""))


def _modules_by_path(import_graph: Mapping[str, Any]) -> dict[str, str]:
    modules = import_graph.get("modules")
    if not isinstance(modules, list):
        return {}
    result: dict[str, str] = {}
    for item in modules:
        if not isinstance(item, Mapping):
            continue
        path = item.get("path")
        module = item.get("module")
        if isinstance(path, str) and isinstance(module, str):
            result[path] = module
    return result


def _skip_code(*, rel_path: str, language: str, size_bytes: int) -> str | None:
    if _is_secret_like(rel_path):
        return "chunk_secret_like_skipped"
    if size_bytes > MAX_FILE_BYTES:
        return "chunk_file_too_large"
    if not _is_chunkable_language(rel_path, language):
        return "chunk_language_skipped"
    return None


def _is_chunkable_language(rel_path: str, language: str) -> bool:
    if language in _ALLOWED_LANGUAGES:
        return True
    posix = PurePosixPath(rel_path)
    if posix.suffix.lower() in _TEXT_FILE_SUFFIXES:
        return True
    return posix.name.lower() in _TEXT_FILE_NAMES


def _is_secret_like(rel_path: str) -> bool:
    name = PurePosixPath(rel_path).name.lower()
    return any(fnmatch.fnmatchcase(name, pattern) for pattern in _SECRET_PATTERNS)


def _resolve_under_root(root: Path, rel_path: str) -> Path | None:
    candidate = (root / rel_path).resolve()
    try:
        candidate.relative_to(root)
    except ValueError:
        return None
    return candidate


def _skip_message(code: str, language: str) -> str:
    if code == "chunk_secret_like_skipped":
        return "secret-like path is excluded from chunking"
    if code == "chunk_file_too_large":
        return f"file exceeds max_file_bytes={MAX_FILE_BYTES}"
    if code == "chunk_language_skipped":
        return f"language is not enabled for chunking: {language}"
    return code


def _chunks_for_file(
    *,
    rel_path: str,
    language: str,
    module: str | None,
    text: str,
    line_bytes: list[bytes],
    diagnostics: list[JsonDict],
) -> list[JsonDict]:
    if language == "python" and rel_path.endswith(".py"):
        return _python_chunks(
            rel_path=rel_path,
            module=module,
            text=text,
            line_bytes=line_bytes,
            diagnostics=diagnostics,
        )
    return _range_chunks(
        rel_path=rel_path,
        language=language,
        kind="file_slice",
        module=None,
        symbol=None,
        line_bytes=line_bytes,
        start_line=1,
        end_line=len(line_bytes),
    )


def _python_chunks(
    *,
    rel_path: str,
    module: str | None,
    text: str,
    line_bytes: list[bytes],
    diagnostics: list[JsonDict],
) -> list[JsonDict]:
    try:
        tree = ast.parse(text, filename=rel_path)
    except SyntaxError as exc:
        diagnostics.append(
            _diagnostic(
                rel_path,
                "chunk_python_syntax_error",
                exc.msg,
                lineno=exc.lineno,
                offset=exc.offset,
            )
        )
        return _range_chunks(
            rel_path=rel_path,
            language="python",
            kind="module",
            module=module,
            symbol=None,
            line_bytes=line_bytes,
            start_line=1,
            end_line=len(line_bytes),
        )

    symbol_ranges = _python_symbol_ranges(tree, len(line_bytes))
    chunks: list[JsonDict] = []
    covered_ranges: list[tuple[int, int]] = []
    for start_line, end_line, symbol in symbol_ranges:
        chunks.extend(
            _range_chunks(
                rel_path=rel_path,
                language="python",
                kind="symbol",
                module=module,
                symbol=symbol,
                line_bytes=line_bytes,
                start_line=start_line,
                end_line=end_line,
            )
        )
        covered_ranges.append((start_line, end_line))

    for start_line, end_line in _uncovered_ranges(covered_ranges, len(line_bytes)):
        if _range_is_blank(line_bytes, start_line, end_line):
            continue
        chunks.extend(
            _range_chunks(
                rel_path=rel_path,
                language="python",
                kind="module",
                module=module,
                symbol=None,
                line_bytes=line_bytes,
                start_line=start_line,
                end_line=end_line,
            )
        )
    return chunks


def _python_symbol_ranges(tree: ast.Module, max_line: int) -> list[tuple[int, int, str]]:
    ranges: list[tuple[int, int, str]] = []
    for node in tree.body:
        if not isinstance(node, ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef):
            continue
        start_line = _bounded_line(int(getattr(node, "lineno", 1) or 1), max_line)
        end_line = _bounded_line(int(getattr(node, "end_lineno", start_line) or start_line), max_line)
        if end_line < start_line:
            end_line = start_line
        ranges.append((start_line, end_line, node.name))
    ranges.sort(key=lambda item: (item[0], item[1], item[2]))
    return ranges


def _uncovered_ranges(covered: list[tuple[int, int]], max_line: int) -> list[tuple[int, int]]:
    ranges: list[tuple[int, int]] = []
    cursor = 1
    for start_line, end_line in sorted(covered):
        if cursor < start_line:
            ranges.append((cursor, start_line - 1))
        cursor = max(cursor, end_line + 1)
    if cursor <= max_line:
        ranges.append((cursor, max_line))
    return ranges


def _range_chunks(
    *,
    rel_path: str,
    language: str,
    kind: str,
    module: str | None,
    symbol: str | None,
    line_bytes: list[bytes],
    start_line: int,
    end_line: int,
) -> list[JsonDict]:
    chunks: list[JsonDict] = []
    for chunk_start, chunk_end in _split_line_range(line_bytes, start_line, end_line):
        byte_start, byte_end, content_bytes = _content_span(line_bytes, chunk_start, chunk_end)
        content_sha256 = hashlib.sha256(content_bytes).hexdigest()
        record: JsonDict = {
            "chunk_id": _chunk_id(
                rel_path=rel_path,
                kind=kind,
                module=module,
                symbol=symbol,
                start_line=chunk_start,
                end_line=chunk_end,
                content_sha256=content_sha256,
            ),
            "source_path": rel_path,
            "language": language,
            "kind": kind,
            "start_line": chunk_start,
            "end_line": chunk_end,
            "byte_start": byte_start,
            "byte_end": byte_end,
            "content_sha256": content_sha256,
            "token_estimate": _token_estimate(content_bytes),
        }
        if module:
            record["module"] = module
        if symbol:
            record["symbol"] = symbol
        chunks.append(record)
    return chunks


def _split_line_range(line_bytes: list[bytes], start_line: int, end_line: int) -> list[tuple[int, int]]:
    ranges: list[tuple[int, int]] = []
    cursor = start_line
    while cursor <= end_line:
        chunk_end = cursor
        size = 0
        while chunk_end <= end_line:
            line_size = len(line_bytes[chunk_end - 1])
            if size > 0 and size + line_size > MAX_CHUNK_BYTES:
                break
            size += line_size
            chunk_end += 1
        current_end = max(cursor, chunk_end - 1)
        ranges.append((cursor, current_end))
        if current_end >= end_line:
            break
        cursor = max(current_end - OVERLAP_LINES + 1, cursor + 1)
    return ranges


def _content_span(line_bytes: list[bytes], start_line: int, end_line: int) -> tuple[int, int, bytes]:
    byte_start = sum(len(item) for item in line_bytes[: start_line - 1])
    content_bytes = b"".join(line_bytes[start_line - 1 : end_line])
    byte_end = byte_start + len(content_bytes)
    return byte_start, byte_end, content_bytes


def _chunk_id(
    *,
    rel_path: str,
    kind: str,
    module: str | None,
    symbol: str | None,
    start_line: int,
    end_line: int,
    content_sha256: str,
) -> str:
    payload = "\n".join(
        [
            CHUNKER_VERSION,
            rel_path,
            kind,
            module or "",
            symbol or "",
            str(start_line),
            str(end_line),
            content_sha256,
        ]
    )
    return f"{CHUNK_ID_PREFIX}{hashlib.sha256(payload.encode('utf-8')).hexdigest()}"


def _range_is_blank(line_bytes: list[bytes], start_line: int, end_line: int) -> bool:
    content = b"".join(line_bytes[start_line - 1 : end_line])
    return not content.strip()


def _token_estimate(content_bytes: bytes) -> int:
    if not content_bytes:
        return 0
    return (len(content_bytes) + 3) // 4


def _bounded_line(value: int, max_line: int) -> int:
    return min(max(value, 1), max_line)


def _stable_document_sha256(document: Mapping[str, Any]) -> str:
    normalized = _without_generated_at(document)
    content = json.dumps(normalized, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def _without_generated_at(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {
            str(key): _without_generated_at(item)
            for key, item in value.items()
            if str(key) != "generated_at"
        }
    if isinstance(value, list):
        return [_without_generated_at(item) for item in value]
    return value


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


def _chunk_sort_key(chunk: Mapping[str, Any]) -> tuple[str, int, int, str]:
    return (
        str(chunk["source_path"]),
        int(chunk["start_line"]),
        int(chunk["end_line"]),
        str(chunk["chunk_id"]),
    )


def _diagnostic_sort_key(diagnostic: Mapping[str, Any]) -> tuple[str, str, int, int]:
    return (
        str(diagnostic["path"]),
        str(diagnostic["code"]),
        int(diagnostic.get("lineno") or 0),
        int(diagnostic.get("offset") or 0),
    )


__all__ = ["build_repo_chunks"]
