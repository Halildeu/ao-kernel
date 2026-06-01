#!/usr/bin/env python3
"""AO-MA-11E-2a CLI — V5 GitHub mirror drift check (read-only).

Compares actual GitHub mirror state (Milestone + Issues + Project) against
.claude/plans/v5_issue_projection.v1.json expected state. Read-only; no writes.

Usage:
    python3 scripts/ao_ma11e2_v5_mirror_drift.py \\
      --projection-manifest .claude/plans/v5_issue_projection.v1.json \\
      --github-token-env GH_TOKEN \\
      --allow-network \\
      --output drift_report.json

Exit codes:
    0  — synced (no drift)
    1  — mirror_drift_detected (fail-closed)
    2  — usage_error / network_not_allowed
    3  — api_error

HARD RULE pin:
    - Token value NEVER appears in --output JSON, stdout, or logs.
    - gh CLI subprocess wrapper is the ONLY network adapter; core module pure stdlib.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

# Project root is two levels up from scripts/.
_REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO_ROOT))

from ao_kernel._internal.ao_ma.github_mirror_drift import (  # noqa: E402
    check_github_mirror_drift,
)


def _gh_api_caller(method: str, path: str):
    """Adapter: gh CLI subprocess wrapper.

    Resolves a small set of paths used by check_github_mirror_drift():
      - GET /repos/{owner}/{repo}/milestones/{n}
      - GET /repos/{owner}/{repo}/issues?milestone={n}&state=all&per_page=100
      - POST graphql:project_items:<node_id>  (custom convention; we map to GraphQL)
    """
    if path.startswith("graphql:project_items:"):
        node_id = path.split(":", 2)[2]
        query = (
            'query($id:ID!){ node(id:$id){ ... on ProjectV2 { '
            "items(first:100){ totalCount nodes{ id content{ ... on Issue { number url } } } } "
            "} } }"
        )
        proc = subprocess.run(
            [
                "gh",
                "api",
                "graphql",
                "-f",
                f"query={query}",
                "-F",
                f"id={node_id}",
            ],
            capture_output=True,
            text=True,
            check=False,
            timeout=30,
        )
        if proc.returncode != 0:
            raise RuntimeError(f"gh GraphQL failed: {proc.stderr.strip()}")
        data = json.loads(proc.stdout)
        items_node = (
            data.get("data", {}).get("node", {}).get("items", {})
        )
        return {"items": items_node.get("nodes", [])}

    # REST path
    if method != "GET":
        raise ValueError(f"Unsupported method for REST path: {method}")
    proc = subprocess.run(
        ["gh", "api", path],
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )
    if proc.returncode != 0:
        # gh exits non-zero for 404; treat as None for missing resources
        stderr = proc.stderr.strip()
        if "HTTP 404" in stderr or "Not Found" in stderr:
            return None
        raise RuntimeError(f"gh REST failed: {stderr}")
    if not proc.stdout.strip():
        return None
    return json.loads(proc.stdout)


def _build_argparser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "AO-MA-11E-2a: read-only GitHub mirror drift check vs projection manifest."
        )
    )
    parser.add_argument(
        "--projection-manifest",
        type=Path,
        default=_REPO_ROOT / ".claude" / "plans" / "v5_issue_projection.v1.json",
        help="Path to v5_issue_projection.v1.json (default: V5 manifest).",
    )
    parser.add_argument(
        "--github-token-env",
        default="GH_TOKEN",
        help="Env-var name to resolve GitHub token (NOT the value). Default: GH_TOKEN.",
    )
    parser.add_argument(
        "--allow-network",
        action="store_true",
        help="Required: actually call gh API. Without this flag, exit_decision=network_not_allowed.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="If set, write JSON report to this path; otherwise print to stdout.",
    )
    parser.add_argument(
        "--repo-owner",
        default="Halildeu",
    )
    parser.add_argument(
        "--repo-name",
        default="ao-kernel",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_argparser()
    args = parser.parse_args(argv)

    if not args.projection_manifest.is_file():
        print(
            f"::error::projection manifest not found: {args.projection_manifest}",
            file=sys.stderr,
        )
        return 2

    token_env = args.github_token_env
    token_present = bool(os.environ.get(token_env, "").strip())

    report = check_github_mirror_drift(
        projection_manifest_path=args.projection_manifest,
        gh_api_caller=_gh_api_caller,
        repo_owner=args.repo_owner,
        repo_name=args.repo_name,
        network_allowed=args.allow_network,
        token_env=token_env,
        token_present=token_present,
    )
    report_dict = report.to_dict()
    output_json = json.dumps(report_dict, indent=2)

    # Secret redaction safety: token value is never inserted into the report by the
    # core module, but as a defensive belt-and-suspenders check, refuse to emit
    # output that contains the literal token value.
    if token_present:
        token_value = os.environ.get(token_env, "")
        if token_value and token_value in output_json:
            print(
                "::error::SECURITY: token value leaked into report; aborting output",
                file=sys.stderr,
            )
            return 2

    if args.output is not None:
        args.output.write_text(output_json + "\n", encoding="utf-8")
    else:
        print(output_json)

    return report.to_exit_code()


if __name__ == "__main__":
    sys.exit(main())
