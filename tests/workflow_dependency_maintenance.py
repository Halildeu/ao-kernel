"""Fail-closed classifier for dependency-only GitHub Actions diffs."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

_ALLOWED_ACTION_VERSION_LINE = re.compile(
    r"^[+-]\s*(?:-\s+)?uses:\s+(?:"
    r"actions/checkout@v[67]|"
    r"github/codeql-action/(?:init|analyze|upload-sarif)@v[34]|"
    r"google-github-actions/deploy-cloudrun@v[23]"
    r")$"
)


def changed_lines_are_dependency_only(diff_text: str) -> bool:
    changed_lines = [
        line
        for line in diff_text.splitlines()
        if line.startswith(("+", "-")) and not line.startswith(("+++", "---"))
    ]
    return bool(changed_lines) and all(_ALLOWED_ACTION_VERSION_LINE.fullmatch(line) for line in changed_lines)


def workflow_diff_is_dependency_only(
    repo_root: Path,
    paths: list[str],
    *,
    base_ref: str = "origin/main",
    head_ref: str = "HEAD",
) -> bool:
    if not paths:
        return False
    proc = subprocess.run(
        ["git", "diff", "--unified=0", f"{base_ref}...{head_ref}", "--", *paths],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )
    return proc.returncode == 0 and changed_lines_are_dependency_only(proc.stdout)
