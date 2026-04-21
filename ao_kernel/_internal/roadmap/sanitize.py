from __future__ import annotations

import re
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path


# v0.3 WWV: keep this list small and explicit.
# This can later be driven by a tenant decision bundle / policy.
DEFAULT_FORBIDDEN_TOKENS: list[str] = [
    # Example tenant/customer marker (used by smoke test).
    "Beykent",
]


@dataclass(frozen=True)
class SanitizeFinding:
    path: str
    rule: str


def _read_text_best_effort(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return ""


def scan_directory(
    *,
    root: Path,
    forbidden_tokens: list[str] | None = None,
) -> tuple[bool, list[SanitizeFinding]]:
    root = root.resolve()
    tokens = [t for t in (forbidden_tokens or DEFAULT_FORBIDDEN_TOKENS) if isinstance(t, str) and t.strip()]

    # Keep rules deterministic and simple.
    email_re = re.compile(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", re.IGNORECASE)
    private_key_markers = [
        "-----BEGIN PRIVATE KEY-----",
        "-----BEGIN OPENSSH PRIVATE KEY-----",
        "-----BEGIN RSA PRIVATE KEY-----",
    ]
    token_prefixes = [
        "sk-",
        "ghp_",
        "github_pat_",
    ]

    findings: list[SanitizeFinding] = []
    if not root.exists():
        return (True, findings)

    for p in sorted(root.rglob("*"), key=lambda x: x.as_posix()):
        if not p.is_file():
            continue
        rel = p.relative_to(root).as_posix()
        text = _read_text_best_effort(p)

        # Token strings (explicit).
        for tok in tokens:
            if tok and tok in text:
                findings.append(SanitizeFinding(path=rel, rule="FORBIDDEN_TOKEN"))
                break

        # Email addresses.
        if email_re.search(text or ""):
            findings.append(SanitizeFinding(path=rel, rule="EMAIL_DETECTED"))

        # Private key markers.
        for marker in private_key_markers:
            if marker in text:
                findings.append(SanitizeFinding(path=rel, rule="PRIVATE_KEY_MARKER"))
                break

        # Token prefixes (best-effort; do not print the value).
        for pref in token_prefixes:
            if pref in text:
                findings.append(SanitizeFinding(path=rel, rule="TOKEN_PREFIX_DETECTED"))
                break

    ok = not findings
    return (ok, findings)


def findings_fingerprint(findings: list[SanitizeFinding]) -> str:
    raw = "\n".join([f"{f.path}:{f.rule}" for f in findings]).encode("utf-8")
    return sha256(raw).hexdigest()[:16]
