"""Deterministic language detection by path only."""

from __future__ import annotations

from pathlib import PurePosixPath

_EXTENSION_LANGUAGES: dict[str, str] = {
    ".bash": "shell",
    ".c": "c",
    ".cc": "cpp",
    ".cpp": "cpp",
    ".css": "css",
    ".go": "go",
    ".h": "c",
    ".hpp": "cpp",
    ".html": "html",
    ".java": "java",
    ".js": "javascript",
    ".json": "json",
    ".jsx": "javascript",
    ".kt": "kotlin",
    ".kts": "kotlin",
    ".md": "markdown",
    ".mjs": "javascript",
    ".py": "python",
    ".pyi": "python",
    ".rs": "rust",
    ".sh": "shell",
    ".sql": "sql",
    ".toml": "toml",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".yaml": "yaml",
    ".yml": "yaml",
    ".zsh": "shell",
}

_FILENAME_LANGUAGES: dict[str, str] = {
    "dockerfile": "dockerfile",
    "makefile": "makefile",
}


def detect_language(path: str) -> str:
    """Return a deterministic language label for a repo-relative POSIX path.

    The detector intentionally uses only the path/name. It does not inspect
    file contents, so binary files are never read for language detection.
    """
    posix_path = PurePosixPath(path)
    lower_name = posix_path.name.lower()
    by_name = _FILENAME_LANGUAGES.get(lower_name)
    if by_name is not None:
        return by_name
    if lower_name.endswith(".d.ts"):
        return "typescript"
    return _EXTENSION_LANGUAGES.get(posix_path.suffix.lower(), "unknown")


def language_extensions() -> dict[str, str]:
    """Return the extension mapping used by the detector."""
    return dict(sorted(_EXTENSION_LANGUAGES.items()))
