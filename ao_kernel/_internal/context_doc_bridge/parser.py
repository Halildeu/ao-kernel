"""Source-document parsing for the context doc-bridge (internal).

Pure helpers: read a ``.md`` source, extract a short value via a bounded
strategy, hash it, and screen for secret-like tokens. No network; the only
I/O is reading the file path the caller already resolved + confined.
"""

from __future__ import annotations

import hashlib
import re
from pathlib import Path

MAX_VALUE_LEN = 300

# Secret-like token screens. A source value matching any of these is NOT
# ingested (Codex acceptance #4: skip + diagnostic, never redact-and-store).
_SECRET_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"sk-[A-Za-z0-9]{12,}"),
    re.compile(r"eyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}"),  # JWT
    re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._\-]{12,}"),
    re.compile(
        r"(?i)\b(?:password|passwd|secret|api[_-]?key|access[_-]?token|"
        r"client[_-]?secret|refresh[_-]?token)\b\s*[:=]\s*\S{6,}"
    ),
    re.compile(r"-----BEGIN (?:[A-Z]+ )?PRIVATE KEY-----"),
    re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),  # AWS access key id
)

_STATUS_KEYWORDS = (
    "Accepted",
    "Kabul",
    "Approved",
    "Rejected",
    "Reddedildi",
    "Superseded",
    "Deprecated",
    "Proposed",
    "Draft",
)


def sha256_text(text: str) -> str:
    return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()


def sha256_file(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def looks_like_secret(text: str) -> bool:
    """True if the text contains a secret-like token (block ingest)."""
    return any(p.search(text) for p in _SECRET_PATTERNS)


def _clip(text: str) -> str:
    return " ".join(text.split())[:MAX_VALUE_LEN]


def first_heading(text: str, fallback: str) -> str:
    for line in text.splitlines():
        if line.startswith("# "):
            return _clip(line[2:])
    return _clip(fallback)


def status_and_date(text: str) -> tuple[str, str]:
    """Extract (status, date) from an ADR-style document head."""
    head = "\n".join(text.splitlines()[:40])
    dm = re.search(r"(20\d\d-\d\d-\d\d)", head)
    date = dm.group(1) if dm else ""
    m = re.search(r"##\s*(?:Status|Durum)\s*\n+\**\s*([A-Za-zçğıöşüÇĞİÖŞÜ]+)", head)
    if m:
        return m.group(1).capitalize(), date
    m = re.search(r"(?:\*\*)?Status(?:\*\*)?\s*[:：]\s*\**([A-Za-zçğıöşü]+)", head, re.I)
    if m:
        return m.group(1).capitalize(), date
    for kw in _STATUS_KEYWORDS:
        if re.search(rf"\b{kw}\b", head, re.I):
            return kw.capitalize(), date
    return "Unknown", date


def section_headings(text: str, limit: int) -> list[str]:
    out: list[str] = []
    for line in text.splitlines():
        if line.startswith("## "):
            out.append(_clip(line[3:]))
            if len(out) >= limit:
                break
    return out
