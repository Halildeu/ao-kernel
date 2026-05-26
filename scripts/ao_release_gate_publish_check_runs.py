#!/usr/bin/env python3
"""Publish the ao-release-gate dual check-runs via the GitHub Checks API.

RG-CONCLUSION-SEMANTICS C-prime migration. The decision step writes two
no-secret check-run artifacts (``ao-release-gate-technical.check-run.json``
and ``ao-release-gate-review.check-run.json``) into a directory. This
script reads them and POSTs each to ``/repos/{owner}/{repo}/check-runs``
using ``gh api``, inheriting ``GITHUB_TOKEN`` from the calling workflow.

The legacy ``ao-release-gate`` Actions job conclusion remains the existing
required check (C-prime compatibility wrapper: a lone CODEOWNER-review-
pending blocker maps to success). The two new check-runs carry the richer
signal (``action_required`` for review pending, ``stale`` for branch
behind, ``failure`` for real violations). After Phase 2 ruleset cutover
(operator action), they become the source-pinned required check set on
branch protection.

This script is a thin orchestrator on top of ``gh api``; the conclusion
shape is decided upstream by
``ao_kernel.ao_release_gate.build_technical_check_run`` /
``build_review_check_run``. Unit tests cover the shape validation, gh api
invocation pattern, and dry-run path.

Exit codes:
- 0 — every artifact found was either published or recognized as
  intentionally absent (a missing artifact emits a stderr warning but
  does not fail the workflow, so this never breaks CI on a transient
  decision-step failure that already exited non-zero upstream)
- 1 — invalid input (missing required arg, malformed JSON, schema
  violation, gh api failure on a present artifact)
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

_VALID_CONCLUSIONS = {"success", "failure", "neutral", "action_required", "stale"}
_VALID_STATUSES = {"completed"}
_REQUIRED_FIELDS = ("name", "status", "conclusion", "title", "summary")
_CHECK_RUN_FILES = (
    "ao-release-gate-technical.check-run.json",
    "ao-release-gate-review.check-run.json",
)


def _load_check_run(path: Path) -> dict[str, Any]:
    """Load and structurally validate a single check-run artifact."""

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"{path}: not valid JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"{path}: top-level value must be a JSON object")
    missing = [field for field in _REQUIRED_FIELDS if field not in payload]
    if missing:
        raise ValueError(f"{path}: missing required fields: {sorted(missing)}")
    if payload["status"] not in _VALID_STATUSES:
        raise ValueError(f"{path}: status={payload['status']!r} not in {sorted(_VALID_STATUSES)}")
    if payload["conclusion"] not in _VALID_CONCLUSIONS:
        raise ValueError(
            f"{path}: conclusion={payload['conclusion']!r} not in {sorted(_VALID_CONCLUSIONS)}"
        )
    if not isinstance(payload["name"], str) or not payload["name"]:
        raise ValueError(f"{path}: name must be a non-empty string")
    return payload


def build_check_run_body(payload: dict[str, Any], head_sha: str) -> dict[str, Any]:
    """Build the GitHub Checks API POST body for a check-run payload.

    The Checks API requires ``name``, ``head_sha``, and (for completed
    runs) ``status='completed'`` + a valid ``conclusion``. ``output``
    accepts ``title`` (max 255 chars) + ``summary`` (markdown) + ``text``
    (optional markdown details). No secret material is recorded.
    """

    return {
        "name": payload["name"],
        "head_sha": head_sha,
        "status": payload["status"],
        "conclusion": payload["conclusion"],
        "output": {
            "title": payload["title"],
            "summary": payload["summary"],
            "text": payload.get("text", ""),
        },
    }


def _publish_via_gh_api(
    repo: str,
    body: dict[str, Any],
    *,
    runner: Any = subprocess.run,
) -> None:
    """POST a check-run body to GitHub via ``gh api``.

    ``runner`` is injected for testability; defaults to ``subprocess.run``.
    A failed call (non-zero exit) raises ``subprocess.CalledProcessError``;
    the caller decides whether to swallow it.
    """

    runner(
        [
            "gh",
            "api",
            "-X",
            "POST",
            f"repos/{repo}/check-runs",
            "--input",
            "-",
        ],
        input=json.dumps(body).encode("utf-8"),
        check=True,
    )


def publish_dir(
    directory: Path,
    *,
    repo: str,
    head_sha: str,
    dry_run: bool = False,
    runner: Any = subprocess.run,
    log: Any = sys.stderr,
) -> int:
    """Publish every recognized check-run artifact found under ``directory``.

    Returns the count of artifacts published (0 if none were present;
    raises for malformed input or gh api failure on a present artifact).
    A missing-but-expected artifact emits a stderr warning and is
    skipped without raising, so a partial-output upstream step (decision
    crash before emit-multi-check-runs ran) does not double-fail this
    publish step.
    """

    if not directory.exists() or not directory.is_dir():
        print(f"::warning::{directory} not a directory; nothing to publish", file=log)
        return 0
    published = 0
    for filename in _CHECK_RUN_FILES:
        path = directory / filename
        if not path.exists():
            print(f"::warning::{path} missing; skipping", file=log)
            continue
        payload = _load_check_run(path)
        body = build_check_run_body(payload, head_sha)
        if dry_run:
            print(
                f"dry-run: would publish {payload['name']} conclusion={payload['conclusion']}",
                file=log,
            )
        else:
            _publish_via_gh_api(repo, body, runner=runner)
            print(
                f"published {payload['name']} conclusion={payload['conclusion']}",
                file=log,
            )
        published += 1
    return published


def build_parser() -> argparse.ArgumentParser:
    """Build the CLI parser."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dir",
        type=Path,
        required=True,
        help="Directory containing ao-release-gate-{technical,review}.check-run.json artifacts.",
    )
    parser.add_argument(
        "--repo",
        required=True,
        help="GitHub repository in 'owner/name' shape.",
    )
    parser.add_argument(
        "--head-sha",
        required=True,
        help="Pull request head SHA the check-runs are pinned to.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate artifacts and log intent without calling gh api.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """CLI entrypoint."""

    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        publish_dir(
            args.dir,
            repo=args.repo,
            head_sha=args.head_sha,
            dry_run=args.dry_run,
        )
    except (ValueError, FileNotFoundError) as exc:
        print(f"::error::{exc}", file=sys.stderr)
        return 1
    except subprocess.CalledProcessError as exc:
        print(f"::error::gh api failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
