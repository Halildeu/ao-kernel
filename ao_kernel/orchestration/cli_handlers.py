"""AO-MA-3 CLI handlers for the ``ao-kernel orchestration`` subcommand.

Wires the orchestrator façade into the canonical CLI entrypoint
(``ao_kernel/cli.py``). The ``scripts/ao_orchestrator.py`` thin wrapper
delegates to the same canonical entrypoint so operators can pick either
invocation pattern.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from ao_kernel.orchestration.orchestrator import (
    OrchestrationError,
    Orchestrator,
    SSOTPaths,
)
from ao_kernel.orchestration.task_graph_builder import TaskSpec


def cmd_orchestration_plan(args: argparse.Namespace) -> int:
    """Handle ``ao-kernel orchestration plan``.

    Reads the operator goal + optional declared specs, builds + emits the
    task graph + assignments + manifest, and prints a short text/json
    summary.
    """

    goal = args.goal
    if not goal:
        print("error: --goal is required", file=sys.stderr)
        return 2

    repo_root = Path(args.repo_root).resolve() if args.repo_root else Path.cwd()
    ssot = SSOTPaths.default(repo_root)
    output_dir = Path(args.output_dir).resolve() if args.output_dir else repo_root / ".ao" / "orchestration"

    declared_specs = _parse_declared_specs(args.declared_spec)
    orchestrator = Orchestrator(
        repo_root=repo_root,
        ssot=ssot,
        output_dir=output_dir,
    )

    try:
        manifest = orchestrator.plan(
            goal=goal,
            declared_specs=declared_specs,
            base_sha=args.base_sha,
            base_ref=args.base_ref,
            repo=args.repo,
        )
    except OrchestrationError as exc:
        print(f"orchestration plan failed: {exc}", file=sys.stderr)
        return 1

    if args.format == "json":
        print(json.dumps(manifest, indent=2, sort_keys=True))
    else:
        print(f"task_graph_id: {manifest['task_graph_id']}")
        print(f"base_dir: {manifest['base_dir']}")
        print(f"generated_at: {manifest['generated_at']}")
        print(f"artifacts ({len(manifest['artifacts'])}):")
        for artifact in manifest["artifacts"]:
            print(f"  - {artifact['path']} ({artifact['sha256'][:14]}…)")
    return 0


def _parse_declared_specs(raw: list[str] | None) -> list[TaskSpec] | None:
    """Parse ``--declared-spec`` CLI repeats into TaskSpec objects.

    Each spec is a ``<task_id>:<comma-separated-paths>[:<description>]`` form.
    Returning ``None`` triggers the conservative single-task default in
    :func:`build_task_graph`.
    """

    if not raw:
        return None
    specs: list[TaskSpec] = []
    for item in raw:
        parts = item.split(":", 2)
        if len(parts) < 2 or not parts[0] or not parts[1]:
            raise SystemExit(f"--declared-spec {item!r} must be <task_id>:<comma-paths>[:<desc>]")
        task_id = parts[0].strip()
        paths = [p.strip() for p in parts[1].split(",") if p.strip()]
        description = parts[2].strip() if len(parts) == 3 and parts[2].strip() else f"Slice {task_id}"
        specs.append(
            TaskSpec(
                task_id=task_id,
                description=description,
                write_paths=paths,
            )
        )
    return specs


def add_orchestration_subparser(sub: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    """Register the ``orchestration`` subparser on the main CLI parser."""

    orchestration_p = sub.add_parser(
        "orchestration",
        help="AO-MA multi-agent orchestrator (read-only artifact emission)",
    )
    orchestration_sub = orchestration_p.add_subparsers(dest="orchestration_command")

    plan_p = orchestration_sub.add_parser(
        "plan",
        help="Build a task graph + assignments from a goal (no agent spawn)",
    )
    plan_p.add_argument(
        "--goal",
        required=True,
        help="Operator goal in free-form text (used as task graph goal field)",
    )
    plan_p.add_argument(
        "--declared-spec",
        action="append",
        default=None,
        help=(
            "Optional declared slice in the form "
            "<task_id>:<comma-paths>[:<description>]; repeat for each slice. "
            "Omit to emit a single conservative task (no path invention)."
        ),
    )
    plan_p.add_argument(
        "--output-dir",
        default=None,
        help="Output directory (default: <repo_root>/.ao/orchestration)",
    )
    plan_p.add_argument(
        "--repo-root",
        default=None,
        help="Repository root path (default: current working directory)",
    )
    plan_p.add_argument(
        "--base-sha",
        default=None,
        help="40-char base SHA (default: git rev-parse origin/main)",
    )
    plan_p.add_argument(
        "--base-ref",
        default="refs/heads/main",
        help="Base ref label (default: refs/heads/main)",
    )
    plan_p.add_argument(
        "--repo",
        default=None,
        help="owner/repo (default: inferred from origin remote URL)",
    )
    plan_p.add_argument(
        "--format",
        choices=["text", "json"],
        default="text",
        help="Stdout summary format (default: text)",
    )
