"""Secret-aware exclusion helpers for repo-intelligence scans."""

from __future__ import annotations

import re
from dataclasses import dataclass
from fnmatch import fnmatchcase
from pathlib import PurePosixPath

SECRET_SCAN_MAX_BYTES = 5_000_000

SECRET_LIKE_PATH_PATTERNS: tuple[str, ...] = (
    ".env",
    ".env.*",
    "*.pem",
    "*.key",
    "*.p12",
    "*.pfx",
    "id_rsa",
    "id_dsa",
    "id_ed25519",
    "secrets.*",
    "credentials.*",
)


@dataclass(frozen=True)
class SecretPattern:
    pattern_id: str
    expression: re.Pattern[bytes]


CONTENT_PATTERNS: tuple[SecretPattern, ...] = (
    SecretPattern("private_key_block", re.compile(rb"-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----")),
    SecretPattern("pgp_private_key_block", re.compile(rb"-----BEGIN PGP PRIVATE KEY BLOCK-----")),
    SecretPattern("openai_api_key_like", re.compile(rb"sk-[A-Za-z0-9_-]{20,}")),
    SecretPattern("github_classic_pat_like", re.compile(rb"ghp_[A-Za-z0-9_]{20,}")),
    SecretPattern("github_fine_grained_pat_like", re.compile(rb"github_pat_[A-Za-z0-9_]{20,}")),
    SecretPattern("aws_access_key_id_like", re.compile(rb"AKIA[0-9A-Z]{16}")),
)


@dataclass(frozen=True)
class SecretScanDecision:
    redacted: bool
    reason: str | None = None
    pattern_ids: tuple[str, ...] = ()
    scan_status: str = "not_applicable"


def decide_secret_redaction(
    repo_relative_path: str,
    *,
    content: bytes | None,
    size_bytes: int,
) -> SecretScanDecision:
    """Return whether a file must be excluded from RI context artifacts.

    The decision is metadata-only. It returns pattern identifiers, never
    matched values, line content, or snippets.
    """
    path_match = _match_secret_like_path(repo_relative_path)
    if path_match is not None:
        return SecretScanDecision(
            redacted=True,
            reason=f"secret_redaction:path:{path_match}:file",
            pattern_ids=(f"path:{path_match}",),
            scan_status="path_match",
        )
    if content is None:
        return SecretScanDecision(
            redacted=False,
            scan_status="content_not_read",
        )
    if size_bytes > SECRET_SCAN_MAX_BYTES:
        return SecretScanDecision(
            redacted=False,
            scan_status="content_too_large",
        )
    pattern_ids = tuple(pattern.pattern_id for pattern in CONTENT_PATTERNS if pattern.expression.search(content))
    if pattern_ids:
        return SecretScanDecision(
            redacted=True,
            reason="secret_redaction:content:file",
            pattern_ids=pattern_ids,
            scan_status="content_match",
        )
    return SecretScanDecision(redacted=False, scan_status="clean")


def active_secret_pattern_ids() -> tuple[str, ...]:
    path_ids = tuple(f"path:{pattern}" for pattern in SECRET_LIKE_PATH_PATTERNS)
    content_ids = tuple(pattern.pattern_id for pattern in CONTENT_PATTERNS)
    return (*path_ids, *content_ids)


def _match_secret_like_path(repo_relative_path: str) -> str | None:
    normalized = repo_relative_path.strip("/")
    if not normalized:
        return None
    path = PurePosixPath(normalized)
    parts = tuple(part for part in path.parts if part)
    name = path.name
    for pattern in SECRET_LIKE_PATH_PATTERNS:
        if "/" in pattern:
            if fnmatchcase(normalized, pattern):
                return pattern
            continue
        if any(part == pattern for part in parts) or fnmatchcase(name, pattern):
            return pattern
    return None


__all__ = [
    "SECRET_SCAN_MAX_BYTES",
    "SecretScanDecision",
    "active_secret_pattern_ids",
    "decide_secret_redaction",
]
