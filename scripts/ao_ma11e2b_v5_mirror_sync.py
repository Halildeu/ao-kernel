#!/usr/bin/env python3
"""AO-MA-11E-2b CLI — V5 GitHub mirror write sync (dry-run + apply).

Dry-run (default; safe, no GitHub write):
    python3 scripts/ao_ma11e2b_v5_mirror_sync.py \\
      --projection-manifest .claude/plans/v5_issue_projection.v1.json \\
      --github-token-env GH_TOKEN \\
      --allow-network \\
      --output sync_report.json

Apply (operator-only; requires 4-input typed confirmation chain):
    python3 scripts/ao_ma11e2b_v5_mirror_sync.py \\
      --apply \\
      --allow-network \\
      --confirmation AO-MA-11E-2B-APPLY \\
      --accepted-dry-run-report ./sync_report.json \\
      --accepted-dry-run-report-digest sha256:<64-hex> \\
      --output apply_report.json

Plus optional env-var second confirmation (AO-MA-10O pattern):
    AO_MA_11E_2B_APPLY_ACK=1 python3 scripts/ao_ma11e2b_v5_mirror_sync.py --apply ...

Exit codes:
    0 — dry_run_complete or applied
    1 — applied_with_post_drift (apply succeeded but post-drift remains)
    2 — apply_aborted / usage_error / network_not_allowed / confirmation_missing
    3 — api_error
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO_ROOT))

from ao_kernel._internal.ao_ma.github_mirror_sync import (  # noqa: E402
    sync_v5_mirror,
)


def _resolve_issue_node_id_from_url(url: str) -> str:
    """Extract issue number from URL and resolve its GitHub node_id."""
    # url e.g. https://github.com/Halildeu/ao-kernel/issues/774
    parts = url.rstrip("/").split("/")
    if len(parts) < 7 or parts[-2] != "issues":
        raise RuntimeError(f"unparseable issue URL: {url}")
    owner = parts[-4]
    repo = parts[-3]
    num = parts[-1]
    proc = subprocess.run(
        ["gh", "api", f"/repos/{owner}/{repo}/issues/{num}", "--jq", ".node_id"],
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"failed to resolve node_id for {url}: {proc.stderr.strip()}")
    return proc.stdout.strip()


def _gh_graphql(query: str, variables: dict) -> dict:
    """Run a GraphQL query via gh CLI; raise RuntimeError on non-zero."""
    args = ["gh", "api", "graphql", "-f", f"query={query}"]
    for k, v in variables.items():
        args += ["-F", f"{k}={v}"]
    proc = subprocess.run(
        args, capture_output=True, text=True, check=False, timeout=30
    )
    if proc.returncode != 0:
        raise RuntimeError(f"gh GraphQL failed: {proc.stderr.strip()}")
    return json.loads(proc.stdout)


def _gh_api_caller(method: str, path: str, body: dict | None = None):
    """gh CLI subprocess wrapper supporting GET/POST/PATCH/DELETE + GraphQL.

    GraphQL conventions (path prefix):
    - graphql:project_items:<node_id> — list project items
    - graphql:add_project_item:<node_id>:<issue_url> — add issue to project
    - graphql:remove_project_item:<node_id>:<issue_url> — remove item from project
    """
    if path.startswith("graphql:project_items:"):
        node_id = path.split(":", 2)[2]
        query = (
            'query($id:ID!){ node(id:$id){ ... on ProjectV2 { '
            "items(first:100){ totalCount nodes{ id content{ ... on Issue { number url } } } } "
            "} } }"
        )
        data = _gh_graphql(query, {"id": node_id})
        items_node = data.get("data", {}).get("node", {}).get("items", {})
        return {"items": items_node.get("nodes", [])}
    if path.startswith("graphql:add_project_item:"):
        _, _, node_id, url = path.split(":", 3)
        # First, resolve the issue's node_id from URL
        issue_node = _resolve_issue_node_id_from_url(url)
        query = (
            "mutation($p:ID!,$c:ID!){"
            "addProjectV2ItemById(input:{projectId:$p,contentId:$c}){item{id}}"
            "}"
        )
        return _gh_graphql(query, {"p": node_id, "c": issue_node})
    if path.startswith("graphql:remove_project_item:"):
        _, _, node_id, url = path.split(":", 3)
        # Project v2 deletion requires the item's node_id (not content id),
        # which is found by scanning items.
        items_resp = _gh_api_caller(
            "POST", f"graphql:project_items:{node_id}", None
        )
        target_item_id = None
        for item in items_resp.get("items", []):
            content = item.get("content") or {}
            if content.get("url") == url:
                target_item_id = item.get("id")
                break
        if target_item_id is None:
            return None  # idempotent: already absent
        query = (
            "mutation($p:ID!,$i:ID!){"
            "deleteProjectV2Item(input:{projectId:$p,itemId:$i}){deletedItemId}"
            "}"
        )
        return _gh_graphql(query, {"p": node_id, "i": target_item_id})

    args = ["gh", "api", "-X", method, path]
    if body is not None:
        # gh api accepts JSON via stdin with --input -
        args += ["--input", "-"]
        proc = subprocess.run(
            args,
            input=json.dumps(body),
            capture_output=True,
            text=True,
            check=False,
            timeout=30,
        )
    else:
        proc = subprocess.run(
            args,
            capture_output=True,
            text=True,
            check=False,
            timeout=30,
        )
    if proc.returncode != 0:
        stderr = proc.stderr.strip()
        if "HTTP 404" in stderr or "Not Found" in stderr:
            return None
        raise RuntimeError(f"gh REST failed: {stderr}")
    if not proc.stdout.strip():
        return None
    return json.loads(proc.stdout)


def _build_argparser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="AO-MA-11E-2b: V5 GitHub mirror write sync (dry-run + apply)."
    )
    parser.add_argument(
        "--projection-manifest",
        type=Path,
        default=_REPO_ROOT / ".claude" / "plans" / "v5_issue_projection.v1.json",
    )
    parser.add_argument("--github-token-env", default="GH_TOKEN")
    parser.add_argument("--allow-network", action="store_true")
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Live GitHub write (requires --confirmation + --accepted-dry-run-report-digest)",
    )
    parser.add_argument(
        "--confirmation",
        default=None,
        help="Operator-typed confirmation; must equal 'AO-MA-11E-2B-APPLY' for apply",
    )
    parser.add_argument(
        "--accepted-dry-run-report",
        type=Path,
        default=None,
        help="Path to dry-run report that the operator accepted (used to compute digest)",
    )
    parser.add_argument(
        "--accepted-dry-run-report-digest",
        default=None,
        help="SHA256 of accepted dry-run report (sha256:<64 hex>)",
    )
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument("--repo-owner", default="Halildeu")
    parser.add_argument("--repo-name", default="ao-kernel")
    parser.add_argument("--environment-name", default="ao-ma-mirror-sync")
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

    # Second confirmation env-var (AO-MA-10O pattern)
    apply_ack_env = os.environ.get("AO_MA_11E_2B_APPLY_ACK", "")
    if args.apply and apply_ack_env != "1":
        print(
            "::error::apply requires AO_MA_11E_2B_APPLY_ACK=1 env-var (second confirmation)",
            file=sys.stderr,
        )
        return 2

    # Verify accepted-dry-run-report digest matches file content (if provided)
    if args.apply and args.accepted_dry_run_report is not None:
        computed = (
            "sha256:"
            + hashlib.sha256(args.accepted_dry_run_report.read_bytes()).hexdigest()
        )
        if args.accepted_dry_run_report_digest != computed:
            print(
                f"::error::accepted_dry_run_report_digest mismatch: "
                f"expected {computed}, got {args.accepted_dry_run_report_digest}",
                file=sys.stderr,
            )
            return 2

    # Load pre-drift snapshot from accepted dry-run report (apply mode)
    pre_drift_snapshot = None
    if args.apply and args.accepted_dry_run_report is not None:
        try:
            pre_drift_snapshot = json.loads(
                args.accepted_dry_run_report.read_text(encoding="utf-8")
            )
        except Exception as exc:
            print(f"::error::failed to load accepted dry-run report: {exc}", file=sys.stderr)
            return 2

    report = sync_v5_mirror(
        projection_manifest_path=args.projection_manifest,
        gh_api_caller=_gh_api_caller,
        repo_owner=args.repo_owner,
        repo_name=args.repo_name,
        network_allowed=args.allow_network,
        apply_mode=args.apply,
        confirmation=args.confirmation,
        accepted_dry_run_report_digest=args.accepted_dry_run_report_digest,
        pre_drift_snapshot=pre_drift_snapshot,
        environment_name=args.environment_name,
        token_env=token_env,
        token_present=token_present,
    )
    output_json = json.dumps(report.to_dict(), indent=2)

    # Token leakage defense
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
