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


def _normalized_checks(check_runs_json_path: Path) -> list[dict[str, Any]]:
    """Extract normalized {name, status, conclusion} check-run entries.

    The shadow / enforce jobs of the ao-release-gate itself are excluded so
    the gate does not see its own pending status as a required-check
    failure.
    """

    data = json.loads(check_runs_json_path.read_text(encoding="utf-8"))
    runs = data.get("check_runs", []) if isinstance(data, dict) else []
    excluded = {"ao-release-gate", "ao-release-gate-shadow"}
    out: list[dict[str, Any]] = []
    for entry in runs:
        if not isinstance(entry, dict):
            continue
        name = entry.get("name")
        if not isinstance(name, str) or name in excluded:
            continue
        out.append(
            {
                "name": name,
                "status": entry.get("status"),
                "conclusion": entry.get("conclusion"),
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


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    """Build the release-gate payload dictionary from trusted inputs."""

    return {
        "repository": {"full_name": args.repository},
        "pull_request": {
            "number": args.pr_number,
            "base": {"ref": args.base_ref},
            "head": {
                "ref": args.head_ref,
                "sha": args.head_sha,
                "repo": {"fork": args.from_fork},
            },
        },
        "issue_url": args.issue_url,
        "branch_up_to_date": args.branch_up_to_date,
        "event_name": "pull_request",
        "reviewed_slice": _reviewed_slice(args.gpp_status),
        "changed_paths": _changed_paths(args.pr_files_json),
        "allowed_path_prefixes": list(DEFAULT_ALLOWED_PATH_PREFIXES),
        "required_checks": _normalized_checks(args.check_runs_json),
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
    parser.add_argument("--issue-url", required=True)
    parser.add_argument("--from-fork", type=_bool_arg, required=True)
    parser.add_argument("--branch-up-to-date", type=_bool_arg, required=True)
    parser.add_argument(
        "--gpp-status",
        type=Path,
        required=True,
        help="Path to the base-ref gpp_status.v1.json (trusted source of reviewed_slice).",
    )
    parser.add_argument("--pr-files-json", type=Path, required=True)
    parser.add_argument("--check-runs-json", type=Path, required=True)
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
