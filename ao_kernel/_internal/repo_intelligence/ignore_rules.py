"""Default ignore rules for repo-intelligence scans."""

from __future__ import annotations

from dataclasses import dataclass
from fnmatch import fnmatchcase

DEFAULT_IGNORE_PATTERNS: tuple[str, ...] = (
    ".git",
    ".ao",
    "__pycache__",
    ".pytest_cache",
    "dist",
    "build",
    ".venv",
    "*.egg-info",
)


@dataclass(frozen=True)
class IgnoreDecision:
    ignored: bool
    reason: str | None = None


def should_ignore_path(
    repo_relative_path: str,
    *,
    is_dir: bool,
    patterns: tuple[str, ...] = DEFAULT_IGNORE_PATTERNS,
) -> IgnoreDecision:
    """Return whether a repo-relative POSIX path should be ignored.

    Exact-name rules match any path segment, so ``.git/config`` is ignored
    even if only the root ``.git`` directory would normally be visited.
    Glob rules are matched against each segment and the whole path.
    """
    normalized = repo_relative_path.strip("/")
    if not normalized:
        return IgnoreDecision(False)
    parts = tuple(part for part in normalized.split("/") if part)
    for pattern in patterns:
        if _pattern_matches(pattern, normalized, parts):
            suffix = "dir" if is_dir else "file"
            return IgnoreDecision(True, f"default_ignore:{pattern}:{suffix}")
    return IgnoreDecision(False)


def _pattern_matches(pattern: str, path: str, parts: tuple[str, ...]) -> bool:
    if "/" in pattern:
        return fnmatchcase(path, pattern)
    if any(part == pattern for part in parts):
        return True
    return any(fnmatchcase(part, pattern) for part in parts) or fnmatchcase(path, pattern)
