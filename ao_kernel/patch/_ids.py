"""Patch / reverse-diff identifier validation (PR-A4a B3 absorb).

``patch_id`` and ``reverse_diff_id`` are caller-controlled strings that
get joined into filesystem paths under ``{run_dir}/patches/`` and
``{run_dir}/artifacts/``. Without validation, a caller could pass
``../escape`` and cause writes outside the run directory, or overwrite
unrelated files. A narrow regex restricts ids to a URL-safe, dot-free
charset that cannot encode a path separator or a parent-traversal.
"""

from __future__ import annotations

import re


# URL-safe token charset (no dots, no slashes, no path separators).
# Matches the output of ``secrets.token_urlsafe(32)`` (43 chars) plus
# any human-friendly id the caller might assign. Length is capped at
# 128 so a malicious caller cannot exhaust inode or filename limits.
_VALID_ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,128}$")


def validate_patch_id(patch_id: str) -> None:
    """Raise ``ValueError`` if ``patch_id`` cannot be safely joined
    into a filesystem path. Uses a strict allowlist (alphanumerics +
    ``-`` + ``_``) to prevent directory traversal, path separator
    injection, and relative-parent references.
    """
    if not isinstance(patch_id, str):
        raise ValueError(
            f"patch_id must be a string, got {type(patch_id).__name__}"
        )
    if not _VALID_ID_RE.match(patch_id):
        raise ValueError(
            f"invalid patch_id {patch_id!r}: must match "
            f"{_VALID_ID_RE.pattern} (alphanumerics, underscore, dash; "
            f"1-128 chars; no path separators or parent traversal)"
        )


__all__ = ["validate_patch_id"]
