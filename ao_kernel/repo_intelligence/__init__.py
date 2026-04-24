"""Public repo-intelligence facade.

RI-1 exposes only the narrow read-only scan and artifact writer functions.
"""

from __future__ import annotations

from ao_kernel._internal.repo_intelligence.artifacts import write_repo_scan_artifacts
from ao_kernel._internal.repo_intelligence.scanner import scan_repo

__all__ = [
    "scan_repo",
    "write_repo_scan_artifacts",
]
