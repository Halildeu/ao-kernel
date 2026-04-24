"""Read-only deterministic repository scanner."""

from __future__ import annotations

import hashlib
import tomllib
from collections import Counter
from pathlib import Path
from typing import Any

import ao_kernel
from ao_kernel._internal.repo_intelligence.ignore_rules import should_ignore_path
from ao_kernel._internal.repo_intelligence.language_detector import detect_language
from ao_kernel._internal.shared.utils import now_iso8601

JsonDict = dict[str, Any]


def scan_repo(project_root: str | Path) -> JsonDict:
    """Scan a repository tree and return a schema-backed repo map document."""
    root = Path(project_root).resolve()
    if not root.is_dir():
        raise FileNotFoundError(f"project_root does not exist or is not a directory: {root}")

    included_files: list[JsonDict] = []
    ignored_paths: list[JsonDict] = []
    diagnostics: list[JsonDict] = []
    directories: set[str] = set()

    stack = [root]
    while stack:
        current = stack.pop()
        try:
            entries = sorted(current.iterdir(), key=lambda entry: _repo_relative_posix(entry, root))
        except OSError as exc:
            diagnostics.append(_diagnostic(_repo_relative_posix(current, root), "directory_unreadable", str(exc)))
            continue

        for entry in entries:
            rel_path = _repo_relative_posix(entry, root)
            if entry.is_symlink():
                diagnostics.append(_diagnostic(rel_path, "symlink_skipped", "symbolic links are not followed"))
                ignored_paths.append({"path": rel_path, "kind": "symlink", "reason": "symlink_not_followed"})
                continue

            try:
                is_dir = entry.is_dir()
            except OSError as exc:
                diagnostics.append(_diagnostic(rel_path, "path_unreadable", str(exc)))
                continue

            ignore_decision = should_ignore_path(rel_path, is_dir=is_dir)
            if ignore_decision.ignored:
                ignored_paths.append(
                    {
                        "path": rel_path,
                        "kind": "directory" if is_dir else "file",
                        "reason": ignore_decision.reason,
                    }
                )
                continue

            if is_dir:
                directories.add(rel_path)
                stack.append(entry)
                continue

            try:
                if entry.is_file():
                    stat = entry.stat()
                    included_files.append(
                        {
                            "path": rel_path,
                            "kind": "file",
                            "size_bytes": stat.st_size,
                            "language": detect_language(rel_path),
                        }
                    )
                else:
                    diagnostics.append(_diagnostic(rel_path, "special_file_skipped", "not a regular file"))
            except OSError as exc:
                diagnostics.append(_diagnostic(rel_path, "file_unreadable", str(exc)))

    included_files.sort(key=lambda item: str(item["path"]))
    ignored_paths.sort(key=lambda item: str(item["path"]))
    diagnostics.sort(key=lambda item: str(item["path"]))
    parsed_pyproject = _load_pyproject(root, included_files, diagnostics)
    diagnostics.sort(key=lambda item: str(item["path"]))
    language_counts = Counter(str(item["language"]) for item in included_files)
    python_candidates = _python_candidates(included_files)
    entrypoints = _python_entrypoint_candidates(included_files, parsed_pyproject)

    return {
        "schema_version": "1",
        "artifact_kind": "repo_map",
        "generator": {
            "name": "ao-kernel",
            "version": ao_kernel.__version__,
            "generated_at": now_iso8601(),
        },
        "project": _project_metadata(root, parsed_pyproject),
        "summary": {
            "included_files": len(included_files),
            "included_directories": len(directories),
            "ignored_paths": len(ignored_paths),
            "diagnostics": len(diagnostics),
            "languages": dict(sorted(language_counts.items())),
            "python_packages": sum(1 for item in python_candidates if item["kind"] == "package"),
            "python_modules": sum(1 for item in python_candidates if item["kind"] == "module"),
            "python_entrypoints": len(entrypoints),
        },
        "files": included_files,
        "ignored": {
            "patterns": [
                ".git",
                ".ao",
                "__pycache__",
                ".pytest_cache",
                "dist",
                "build",
                ".venv",
                "*.egg-info",
            ],
            "paths": ignored_paths,
        },
        "languages": dict(sorted(language_counts.items())),
        "python": {
            "candidates": python_candidates,
            "entrypoints": entrypoints,
        },
        "diagnostics": diagnostics,
    }


def _repo_relative_posix(path: Path, root: Path) -> str:
    if path == root:
        return "."
    return path.relative_to(root).as_posix()


def _diagnostic(path: str, code: str, message: str) -> JsonDict:
    return {"path": path, "code": code, "message": message}


def _load_pyproject(root: Path, included_files: list[JsonDict], diagnostics: list[JsonDict]) -> JsonDict:
    if not any(item["path"] == "pyproject.toml" for item in included_files):
        return {}
    pyproject_path = root / "pyproject.toml"
    try:
        parsed = tomllib.loads(pyproject_path.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError, UnicodeDecodeError) as exc:
        diagnostics.append(_diagnostic("pyproject.toml", "pyproject_unreadable", str(exc)))
        return {}
    if not isinstance(parsed, dict):
        return {}
    return parsed


def _project_metadata(root: Path, pyproject: JsonDict) -> JsonDict:
    project_section = pyproject.get("project")
    project_name = root.name
    if isinstance(project_section, dict) and isinstance(project_section.get("name"), str):
        project_name = project_section["name"]
    return {
        "root": ".",
        "root_name": root.name,
        "name": project_name,
        "root_identity_sha256": hashlib.sha256(str(root).encode("utf-8")).hexdigest(),
    }


def _python_candidates(included_files: list[JsonDict]) -> list[JsonDict]:
    candidates: list[JsonDict] = []
    for item in included_files:
        path = str(item["path"])
        if item.get("language") != "python":
            continue
        module = _module_name_from_python_path(path)
        if module is None:
            continue
        if path.endswith("/__init__.py"):
            candidates.append({"kind": "package", "path": path, "module": module})
        elif not path.endswith(".pyi"):
            candidates.append({"kind": "module", "path": path, "module": module})
    candidates.sort(key=lambda item: (str(item["kind"]), str(item["module"]), str(item["path"])))
    return candidates


def _module_name_from_python_path(path: str) -> str | None:
    parts = path.split("/")
    filename = parts[-1]
    if filename == "__init__.py":
        module_parts = parts[:-1]
    elif filename.endswith(".py"):
        module_parts = [*parts[:-1], filename[:-3]]
    elif filename.endswith(".pyi"):
        module_parts = [*parts[:-1], filename[:-4]]
    else:
        return None
    if not module_parts:
        return None
    return ".".join(part.replace("-", "_") for part in module_parts)


def _python_entrypoint_candidates(included_files: list[JsonDict], pyproject: JsonDict) -> list[JsonDict]:
    candidates: list[JsonDict] = []
    for item in included_files:
        path = str(item["path"])
        if item.get("language") != "python" or not path.endswith(".py"):
            continue
        name = path.rsplit("/", 1)[-1]
        reason = _entrypoint_reason(path, name)
        if reason is not None:
            candidates.append(
                {
                    "kind": "python_file",
                    "name": name[:-3],
                    "path": path,
                    "reason": reason,
                }
            )

    project_section = pyproject.get("project")
    scripts = project_section.get("scripts") if isinstance(project_section, dict) else None
    if isinstance(scripts, dict):
        for name, target in sorted(scripts.items()):
            if isinstance(name, str) and isinstance(target, str):
                candidates.append(
                    {
                        "kind": "console_script",
                        "name": name,
                        "path": "pyproject.toml",
                        "target": target,
                        "reason": "project.scripts",
                    }
                )
    candidates.sort(key=lambda item: (str(item["kind"]), str(item["name"]), str(item["path"])))
    return candidates


def _entrypoint_reason(path: str, name: str) -> str | None:
    if name == "__main__.py":
        return "__main__ module"
    if name in {"cli.py", "main.py"}:
        return "conventional entrypoint filename"
    if path.startswith("scripts/"):
        return "scripts directory"
    if path.startswith("examples/"):
        return "examples directory"
    return None
