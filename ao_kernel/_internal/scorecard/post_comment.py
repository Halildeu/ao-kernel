"""Sticky-comment upsert via ``gh`` CLI.

Implements the CLI side of the sentinel-based sticky comment flow. Called
from CI via ``ao-kernel scorecard post-comment``. All failures are
advisory-only (caller expects exit 0 even on network error / permission
drop) so benchmark PRs are never red-checked by comment failure.
"""

from __future__ import annotations

import json
import logging
import shutil
import subprocess
from dataclasses import dataclass
from typing import Any, Sequence


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class PostCommentResult:
    outcome: str  # "posted" | "patched" | "skipped" | "failed"
    comment_id: int | None
    message: str


def _gh_available() -> bool:
    return shutil.which("gh") is not None


def _list_comments(repo: str, pr: int) -> list[dict[str, Any]]:
    cmd = [
        "gh",
        "api",
        f"repos/{repo}/issues/{pr}/comments",
        "--paginate",
        "--jq",
        ".[]",
    ]
    try:
        out = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True,
            timeout=30,
        )
    except (subprocess.SubprocessError, FileNotFoundError) as exc:
        logger.warning("gh api list-comments failed: %s", exc)
        return []
    comments: list[dict[str, Any]] = []
    for line in out.stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            comments.append(payload)
    return comments


def _find_sentinel(
    comments: Sequence[dict[str, Any]],
    sentinel: str,
) -> dict[str, Any] | None:
    for comment in comments:
        body = comment.get("body")
        if isinstance(body, str) and sentinel in body:
            return comment
    return None


def _post_new(repo: str, pr: int, body: str) -> PostCommentResult:
    cmd = [
        "gh",
        "api",
        f"repos/{repo}/issues/{pr}/comments",
        "--method",
        "POST",
        "--field",
        f"body={body}",
    ]
    try:
        out = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True,
            timeout=30,
        )
    except (subprocess.SubprocessError, FileNotFoundError) as exc:
        logger.warning("gh api post-comment failed: %s", exc)
        return PostCommentResult("failed", None, str(exc))
    payload: dict[str, Any] = {}
    try:
        loaded = json.loads(out.stdout or "{}")
        if isinstance(loaded, dict):
            payload = loaded
    except json.JSONDecodeError:
        pass
    raw_id = payload.get("id")
    comment_id = int(raw_id) if isinstance(raw_id, int) else None
    return PostCommentResult("posted", comment_id, "created")


def _patch_existing(
    repo: str,
    comment_id: int,
    body: str,
) -> PostCommentResult:
    cmd = [
        "gh",
        "api",
        f"repos/{repo}/issues/comments/{comment_id}",
        "--method",
        "PATCH",
        "--field",
        f"body={body}",
    ]
    try:
        subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True,
            timeout=30,
        )
    except (subprocess.SubprocessError, FileNotFoundError) as exc:
        logger.warning("gh api patch-comment failed: %s", exc)
        return PostCommentResult("failed", comment_id, str(exc))
    return PostCommentResult("patched", comment_id, "updated")


def upsert_sticky_comment(
    *,
    repo: str,
    pr: int,
    body: str,
    sentinel: str,
) -> PostCommentResult:
    """Upsert a PR comment bearing ``sentinel``.

    If a comment containing the sentinel already exists, PATCH it.
    Otherwise POST a new one. All failures are downgraded to
    ``PostCommentResult(outcome="failed")`` — caller exits 0 regardless.
    """
    if not _gh_available():
        return PostCommentResult("skipped", None, "gh CLI not on PATH")
    if sentinel not in body:
        return PostCommentResult("skipped", None, "body missing sentinel")
    comments = _list_comments(repo, pr)
    existing = _find_sentinel(comments, sentinel)
    if existing is not None:
        comment_id_raw = existing.get("id")
        if isinstance(comment_id_raw, int):
            return _patch_existing(repo, comment_id_raw, body)
    return _post_new(repo, pr, body)


__all__ = ["PostCommentResult", "upsert_sticky_comment"]
