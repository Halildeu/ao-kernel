#!/usr/bin/env python3
"""Build an ao-release-gate dry-run payload from API-derived PR data.

This builder runs INSIDE the ao-release-gate GitHub Actions workflow on
the protected base ref (GPP-2D design §3.2). It composes the release-gate
payload only from the GitHub API and the base-ref ``gpp_status.v1.json``,
NEVER from a PR-committed JSON file (GPP-2D design §3.3): PR-author-
supplied ``allowed_path_prefixes`` / ``required_checks`` /
``branch_up_to_date`` / ``admin_bypass_requested`` fields would let a PR
self-approve.

The builder takes the trusted operator-supplied / API-derived fields as
CLI args plus two JSON blobs the workflow has already fetched via ``gh``:

- ``--pr-files-json`` — output of ``gh pr view <N> --json files``.
- ``--check-runs-json`` — output of ``gh api repos/.../commits/<SHA>/check-runs``,
  filtered to exclude the ao-release-gate / ao-release-gate-shadow names
  (otherwise the gate would see its own shadow job as a pending required
  check).
- ``--pr-reviews-json`` — output of ``gh pr view <N> --json reviews,author``.
  The builder carries only reviewer login, state, and reviewed commit SHA so
  the decision core can preserve human review for high-risk paths without
  treating reviewer text as release authority.

The output is a single payload JSON consumable by
``scripts/ao_release_gate_decision.py``. The builder is side-effect free
beyond writing the output file and emits no secret material.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

# A repo-owned, base-ref-trusted path allowlist for the diff_scope check.
# Hard-coded here rather than read from gpp_status.current_wp.allowed_scope
# because that field carries narrative scope statements, not file-path
# prefixes. Refining this is a GPP-2D-3 follow-up.
DEFAULT_ALLOWED_PATH_PREFIXES = (
    "ao_kernel/",
    "scripts/",
    "tests/",
    ".claude/plans/",
    ".github/workflows/",
    ".github/CODEOWNERS",
    "deploy/",
    "docs/",
    "AGENTS.md",
    "CLAUDE.md",
    "README.md",
    # GPP-2D-3c bootstrap prerequisite: the ao-release-gate enforce
    # job reads `local-ai-review-evidence.v1.json` from the PR head
    # at the repo root and generates the head-bound
    # `local-gpp-gate-evidence.v1.json` at CI runtime. The decision
    # core's `diff_scope` check then requires every committed path
    # to be in this allowlist. Both files live at the repo root, are
    # cross-AI-review / local-gate only (never runtime adapter state),
    # and never widen support or claim production readiness.
    "local-ai-review-evidence.v1.json",
    "local-gpp-gate-evidence.v1.json",
)


def _bool_arg(value: str) -> bool:
    """Parse a ``true`` / ``false`` string argument as a boolean."""

    normalized = value.strip().lower()
    if normalized in {"true", "1", "yes"}:
        return True
    if normalized in {"false", "0", "no", ""}:
        return False
    raise argparse.ArgumentTypeError(f"expected 'true' or 'false', got {value!r}")


def _changed_paths(pr_files_json_path: Path) -> list[str]:
    """Extract changed file paths from the ``gh pr view --json files`` output."""

    data = json.loads(pr_files_json_path.read_text(encoding="utf-8"))
    files = data.get("files", []) if isinstance(data, dict) else []
    paths: list[str] = []
    for entry in files:
        if isinstance(entry, dict):
            path = entry.get("path")
            if isinstance(path, str) and path.strip():
                paths.append(path.strip())
    return sorted(paths)


def _review_context(pr_reviews_json_path: Path | None) -> tuple[str | None, list[dict[str, Any]]]:
    """Extract PR author and normalized reviews from ``gh pr view`` output."""

    def normalized_string(value: object) -> str | None:
        if isinstance(value, str) and value.strip():
            return value.strip()
        return None

    if pr_reviews_json_path is None:
        return None, []
    data = json.loads(pr_reviews_json_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        return None, []
    raw_author = data.get("author")
    author = normalized_string(raw_author.get("login")) if isinstance(raw_author, dict) else None
    reviews: list[dict[str, Any]] = []
    for item in data.get("reviews", []):
        if not isinstance(item, dict):
            continue
        raw_reviewer = item.get("author")
        reviewer = normalized_string(raw_reviewer.get("login")) if isinstance(raw_reviewer, dict) else None
        raw_commit = item.get("commit")
        commit_oid = normalized_string(raw_commit.get("oid")) if isinstance(raw_commit, dict) else None
        reviews.append(
            {
                "author": reviewer,
                "state": normalized_string(item.get("state")),
                "commit_oid": commit_oid,
            }
        )
    return author if isinstance(author, str) else None, reviews


def _check_run_sort_key(entry: dict[str, Any]) -> tuple[str, str, int]:
    """Sort key for picking the latest check-run by name.

    ``gh api .../check-runs`` returns every check-run on the commit,
    including the ones cancelled by ``concurrency.cancel-in-progress``
    from a previous workflow attempt. Picking the most recent
    ``completed_at`` (or ``started_at`` if not yet completed) keeps the
    gate honest: a stale cancelled run does not permanently mark a check
    as not-green if the new run is green.

    Falls back to the GitHub check-run id (numeric, monotonically
    increasing) when timestamps are missing or equal.
    """

    raw_completed = entry.get("completed_at")
    completed: str = raw_completed if isinstance(raw_completed, str) else ""
    raw_started = entry.get("started_at")
    started: str = raw_started if isinstance(raw_started, str) else ""
    raw_id = entry.get("id")
    cid: int = raw_id if isinstance(raw_id, int) else 0
    return (completed, started, cid)


def _normalized_checks(
    check_runs_json_path: Path,
    required_checks_allowlist: list[str] | None = None,
) -> list[dict[str, Any]]:
    """Extract normalized {name, status, conclusion} check-run entries.

    The shadow / enforce jobs of the ao-release-gate itself are always
    excluded so the gate does not see its own pending status as a
    required-check failure.

    When ``required_checks_allowlist`` is supplied, ONLY check-runs whose
    name is on the allowlist are returned. Advisory / non-blocking jobs
    (``extras-install`` with ``continue-on-error: true``,
    ``benchmark-fast``, ``scorecard``) must NOT count toward the required
    set: their failure or in-progress state must not block the gate. The
    allowlist is the trusted workflow-side declaration of which CI jobs
    are required.

    When ``required_checks_allowlist`` is ``None`` or empty, every
    check-run other than the self-name exclusion is returned (legacy
    permissive behavior).

    Entries are de-duplicated by name keeping the most recent run
    (see ``_check_run_sort_key``) so a cancelled previous run does not
    block a green current run.
    """

    data = json.loads(check_runs_json_path.read_text(encoding="utf-8"))
    runs = data.get("check_runs", []) if isinstance(data, dict) else []
    excluded = {"ao-release-gate", "ao-release-gate-shadow"}
    allow = list(required_checks_allowlist) if required_checks_allowlist else None
    allow_set = set(allow) if allow is not None else None
    by_name: dict[str, dict[str, Any]] = {}
    for entry in runs:
        if not isinstance(entry, dict):
            continue
        name = entry.get("name")
        if not isinstance(name, str) or name in excluded:
            continue
        if allow_set is not None and name not in allow_set:
            continue
        existing = by_name.get(name)
        if existing is None or _check_run_sort_key(entry) > _check_run_sort_key(existing):
            by_name[name] = entry
    out: list[dict[str, Any]] = []
    for name, entry in by_name.items():
        out.append(
            {
                "name": name,
                "status": entry.get("status"),
                "conclusion": entry.get("conclusion"),
            }
        )
    # Fail-closed for allowlisted names that the GitHub API never returned.
    # Without this, the decision core's _required_checks_are_green would
    # silently approve a payload where, say, `typecheck` was on the
    # allowlist but never started on the commit. The synthetic
    # `status: "missing"` entry fails the not-green check.
    if allow is not None:
        present = {entry["name"] for entry in out}
        for required_name in allow:
            if required_name not in present:
                out.append(
                    {
                        "name": required_name,
                        "status": "missing",
                        "conclusion": None,
                    }
                )
    return out


def _reviewed_slice(gpp_status_path: Path) -> str:
    """Return the base-ref-trusted reviewed slice (current_wp.id)."""

    status = json.loads(gpp_status_path.read_text(encoding="utf-8"))
    current_wp = status.get("current_wp") if isinstance(status, dict) else None
    if isinstance(current_wp, dict):
        wp_id = current_wp.get("id")
        if isinstance(wp_id, str) and wp_id.strip():
            return wp_id.strip()
    raise SystemExit("gpp_status.v1.json missing current_wp.id")


def _work_package_issue_url(gpp_status_path: Path) -> str:
    """Return the base-ref-trusted work-package issue URL.

    The decision core's gpp_issue_consistency check requires the payload's
    issue_url to equal the GPP current work-package issue URL exactly. The
    workflow CANNOT source this from ``pull_request.issue_url`` — that field
    is the PR's own API URL, not the GPP work-package issue URL — so the
    builder derives it from the base-ref ``gpp_status.current_wp.issue``.
    """

    status = json.loads(gpp_status_path.read_text(encoding="utf-8"))
    current_wp = status.get("current_wp") if isinstance(status, dict) else None
    if isinstance(current_wp, dict):
        issue = current_wp.get("issue")
        if isinstance(issue, str) and issue.strip():
            return issue.strip()
    raise SystemExit("gpp_status.v1.json missing current_wp.issue")


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    """Build the release-gate payload dictionary from trusted inputs."""

    pr_author, human_reviews = _review_context(args.pr_reviews_json)
    return {
        "repository": {"full_name": args.repository},
        "pull_request": {
            "number": args.pr_number,
            "author": {"login": pr_author} if pr_author is not None else {},
            "base": {"ref": args.base_ref},
            "head": {
                "ref": args.head_ref,
                "sha": args.head_sha,
                "repo": {"fork": args.from_fork},
            },
        },
        # issue_url comes from the base-ref-trusted gpp_status, NOT from the
        # pull_request.issue_url webhook field (which is the PR's own API
        # URL, not the GPP work-package issue URL).
        "issue_url": _work_package_issue_url(args.gpp_status),
        "branch_up_to_date": args.branch_up_to_date,
        "event_name": "pull_request",
        "reviewed_slice": _reviewed_slice(args.gpp_status),
        "changed_paths": _changed_paths(args.pr_files_json),
        "allowed_path_prefixes": list(DEFAULT_ALLOWED_PATH_PREFIXES),
        "pr_author": pr_author,
        "human_reviews": human_reviews,
        "path_sensitive_human_review_enabled": args.pr_reviews_json is not None,
        "required_checks": _normalized_checks(
            args.check_runs_json,
            required_checks_allowlist=list(args.required_check) if args.required_check else None,
        ),
        "forbidden_secret_context_detected": False,
        "admin_bypass_requested": False,
        "pat_backed_bot_actor": False,
        "codex_or_claude_release_authority": False,
        "live_adapter_execution_requested": False,
    }


def build_parser() -> argparse.ArgumentParser:
    """Build the CLI parser."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository", required=True, help="Full GitHub repository name (owner/repo).")
    parser.add_argument("--pr-number", type=int, required=True)
    parser.add_argument("--base-ref", required=True)
    parser.add_argument("--head-ref", required=True)
    parser.add_argument("--head-sha", required=True)
    parser.add_argument("--from-fork", type=_bool_arg, required=True)
    parser.add_argument("--branch-up-to-date", type=_bool_arg, required=True)
    parser.add_argument(
        "--gpp-status",
        type=Path,
        required=True,
        help=(
            "Path to the base-ref gpp_status.v1.json. Trusted source of both "
            "reviewed_slice (current_wp.id) and issue_url (current_wp.issue)."
        ),
    )
    parser.add_argument("--pr-files-json", type=Path, required=True)
    parser.add_argument("--check-runs-json", type=Path, required=True)
    parser.add_argument(
        "--pr-reviews-json",
        type=Path,
        default=None,
        help=(
            "Optional output of `gh pr view <N> --json reviews,author`. "
            "When supplied, the payload carries only normalized review metadata "
            "for the path-sensitive high-risk human gate."
        ),
    )
    parser.add_argument(
        "--required-check",
        action="append",
        default=[],
        help=(
            "Name of a required CI check; may be repeated. When supplied, the builder filters "
            "the GitHub API check-runs payload down to this allowlist so advisory / non-blocking "
            "jobs (extras-install, benchmark-fast, scorecard, ...) cannot block the gate. When "
            "omitted the builder falls back to the legacy permissive behavior (every check-run "
            "other than ao-release-gate / ao-release-gate-shadow). The GPP-2D-3 enforce job in "
            "test.yml passes one --required-check per dependency in its `needs:` graph."
        ),
    )
    parser.add_argument("--output", type=Path, required=True, help="Where to write the payload JSON.")
    return parser


def main(argv: list[str] | None = None) -> int:
    """CLI entrypoint."""

    parser = build_parser()
    args = parser.parse_args(argv)
    payload = build_payload(args)
    args.output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
