#!/usr/bin/env python3
"""Print the current GPP work package for Codex/Claude operator sessions."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any


DEFAULT_STATUS_PATH = Path(".claude/plans/gpp_status.v1.json")


class GppStatusError(RuntimeError):
    """Raised when the GPP status file is missing or malformed."""


def repo_root_from_script() -> Path:
    """Return the repository root based on this script path."""

    return Path(__file__).resolve().parents[1]


def load_status(path: Path) -> dict[str, Any]:
    """Load and minimally validate the GPP status payload."""

    if not path.exists():
        raise GppStatusError(f"GPP status file not found: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise GppStatusError("GPP status payload must be a JSON object")

    required = (
        "schema_version",
        "program_id",
        "authority_ref",
        "current_wp",
        "blocked_wps",
        "support_widening_allowed",
        "production_platform_claim_allowed",
        "live_adapter_execution_allowed",
        "required_startup_checks",
        "required_workflow",
        "forbidden_actions",
        "next_allowed_actions",
    )
    missing = [key for key in required if key not in payload]
    if missing:
        raise GppStatusError(f"GPP status missing required keys: {', '.join(missing)}")

    current_wp = payload["current_wp"]
    if not isinstance(current_wp, dict) or not current_wp.get("id") or not current_wp.get("title"):
        raise GppStatusError("GPP status current_wp must include id and title")

    for guard in ("support_widening_allowed", "production_platform_claim_allowed", "live_adapter_execution_allowed"):
        if payload[guard] is not False:
            raise GppStatusError(f"{guard} must be false until an explicit promotion decision")

    if not isinstance(payload["blocked_wps"], list):
        raise GppStatusError("blocked_wps must be a list")

    return payload


def run_git_summary(repo_root: Path) -> dict[str, str]:
    """Return non-fatal git status signals for operator startup."""

    commands = {
        "status": ["git", "status", "--short", "--branch"],
        "divergence": ["git", "rev-list", "--left-right", "--count", "HEAD...origin/main"],
        "origin_head": ["git", "rev-parse", "--short", "origin/main"],
    }
    summary: dict[str, str] = {}
    for key, command in commands.items():
        completed = subprocess.run(
            command,
            cwd=repo_root,
            check=False,
            capture_output=True,
            text=True,
        )
        if completed.returncode == 0:
            summary[key] = completed.stdout.strip()
        else:
            summary[key] = f"unavailable: {completed.stderr.strip() or completed.returncode}"
    return summary


def render_text(payload: dict[str, Any], *, git_summary: dict[str, str] | None = None) -> str:
    """Render a concise operator-facing status report."""

    current_wp = payload["current_wp"]
    blocked_wps = payload["blocked_wps"]
    current_label = "Active WP" if current_wp.get("status") == "active" else "Current WP"
    status_label = "Active status" if current_wp.get("status") == "active" else "Current status"
    lines = [
        f"Program: {payload.get('program_title', payload['program_id'])}",
        f"Authority ref: {payload['authority_ref']}",
        f"Authority head at last update: {payload.get('authority_head_at_last_update', 'unknown')}",
        f"{current_label}: {current_wp['id']} - {current_wp['title']}",
        f"{status_label}: {current_wp.get('status', 'unknown')}",
        f"Exit decision: {current_wp.get('exit_decision', 'unset')}",
        f"Support widening allowed: {str(payload['support_widening_allowed']).lower()}",
        f"Production platform claim allowed: {str(payload['production_platform_claim_allowed']).lower()}",
        f"Live adapter execution allowed: {str(payload['live_adapter_execution_allowed']).lower()}",
        "",
        "Blocked work packages:",
    ]

    if blocked_wps:
        for item in blocked_wps:
            lines.append(f"- {item['id']}: {item['reason']}")
    else:
        lines.append("- none")

    lines.extend(["", "Required startup checks:"])
    for item in payload["required_startup_checks"]:
        lines.append(f"- {item['id']}: {item['command']}")

    lines.extend(["", "Next allowed actions:"])
    for action in payload["next_allowed_actions"]:
        lines.append(f"- {action}")

    lines.extend(["", "Forbidden actions:"])
    for action in payload["forbidden_actions"]:
        lines.append(f"- {action}")

    if git_summary is not None:
        lines.extend(["", "Current git signals:"])
        lines.append(git_summary.get("status", "status unavailable"))
        lines.append(f"divergence: {git_summary.get('divergence', 'unavailable')}")
        lines.append(f"origin/main head: {git_summary.get('origin_head', 'unavailable')}")

    return "\n".join(lines) + "\n"


def build_parser() -> argparse.ArgumentParser:
    """Build CLI parser."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--status-path", type=Path, default=None, help="Path to gpp_status.v1.json")
    parser.add_argument("--repo-root", type=Path, default=None, help="Repository root for git summary")
    parser.add_argument("--output", choices=("text", "json"), default="text", help="Output format")
    parser.add_argument("--skip-git", action="store_true", help="Do not collect git summary")
    return parser


def main(argv: list[str] | None = None) -> int:
    """CLI entrypoint."""

    parser = build_parser()
    args = parser.parse_args(argv)
    repo_root = args.repo_root.resolve() if args.repo_root else repo_root_from_script()
    status_path = args.status_path.resolve() if args.status_path else repo_root / DEFAULT_STATUS_PATH

    try:
        payload = load_status(status_path)
    except (GppStatusError, json.JSONDecodeError) as exc:
        print(f"gpp_next: {exc}", file=sys.stderr)
        return 2

    if args.output == "json":
        print(json.dumps(payload, indent=2, sort_keys=True))
        return 0

    git_summary = None if args.skip_git else run_git_summary(repo_root)
    print(render_text(payload, git_summary=git_summary), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
