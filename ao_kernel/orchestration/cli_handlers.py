"""AO-MA-3 CLI handlers for the ``ao-kernel orchestration`` subcommand.

Wires the orchestrator façade into the canonical CLI entrypoint
(``ao_kernel/cli.py``). The ``scripts/ao_orchestrator.py`` thin wrapper
delegates to the same canonical entrypoint so operators can pick either
invocation pattern.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from ao_kernel.orchestration.integrator import (
    Integrator,
    IntegratorError,
    render_assembly_plan_text,
)
from ao_kernel.orchestration.orchestrator import (
    OrchestrationError,
    Orchestrator,
    SSOTPaths,
)
from ao_kernel.orchestration.task_graph_builder import TaskSpec
from ao_kernel.orchestration.worker_runner import WorkerRunner, WorkerRunnerError


def _resolve_worktree_base(cli_arg: str | None) -> Path | None:
    """Resolve worktree base path: CLI flag wins, then ``AO_MA_WORKTREE_BASE`` env, else None.

    Codex iter-4 absorb (doc drift fix): the AO-MA-4 plan doc has
    declared an env fallback since iter-1 but the runtime never honored
    it. Either the env had to be implemented or the plan had to drop
    the claim; implementing keeps the operator runbook honest.
    """

    if cli_arg:
        return Path(cli_arg).resolve()
    env_value = os.environ.get("AO_MA_WORKTREE_BASE")
    if env_value:
        return Path(env_value).resolve()
    return None


def cmd_orchestration_spawn(args: argparse.Namespace) -> int:
    """Handle ``ao-kernel orchestration spawn``."""

    manifest_path = Path(args.manifest).resolve()
    if not manifest_path.exists():
        print(f"error: manifest not found: {manifest_path!s}", file=sys.stderr)
        return 2
    repo_root = Path(args.repo_root).resolve() if args.repo_root else Path.cwd()
    worktree_base = _resolve_worktree_base(args.worktree_base)
    runner = WorkerRunner(repo_root=repo_root, worktree_base=worktree_base, dry_run=args.dry_run)
    try:
        report = runner.spawn(manifest_path=manifest_path)
    except WorkerRunnerError as exc:
        print(f"orchestration spawn failed: {exc}", file=sys.stderr)
        return 1
    if args.format == "json":
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print(f"task_graph_id: {report['task_graph_id']}")
        print(f"base_sync_check: {report['base_sync_check']}")
        print(f"conflict_check: {report['conflict_check']}")
        print(f"workers ({len(report['workers'])}):")
        for w in report["workers"]:
            print(f"  - {w['task_id']} [{w['status']}] {w['reason']}")
    # exit non-zero if any worker failed (Codex iter-4 absorb adds
    # failed_overlap + failed_post_add_verify to the fail surface)
    fail_statuses = {
        "failed_base_mismatch",
        "failed_branch_exists_mismatch",
        "failed_worktree_exists_mismatch",
        "failed_empty_write_set",
        "failed_assignment_sha_mismatch",
        "failed_overlap",
        "failed_post_add_verify",
    }
    if any(w["status"] in fail_statuses for w in report["workers"]):
        return 1
    return 0


def cmd_orchestration_cleanup(args: argparse.Namespace) -> int:
    """Handle ``ao-kernel orchestration cleanup``."""

    manifest_path = Path(args.manifest).resolve()
    if not manifest_path.exists():
        print(f"error: manifest not found: {manifest_path!s}", file=sys.stderr)
        return 2
    repo_root = Path(args.repo_root).resolve() if args.repo_root else Path.cwd()
    worktree_base = _resolve_worktree_base(args.worktree_base)
    runner = WorkerRunner(repo_root=repo_root, worktree_base=worktree_base)
    try:
        result = runner.cleanup(manifest_path=manifest_path, delete_branches=args.delete_branches)
    except WorkerRunnerError as exc:
        print(f"orchestration cleanup failed: {exc}", file=sys.stderr)
        return 1
    if args.format == "json":
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        print(f"removed_worktrees ({len(result['removed_worktrees'])}):")
        for w in result["removed_worktrees"]:
            print(f"  - {w}")
        if result["kept_dirty"]:
            print(f"kept_dirty ({len(result['kept_dirty'])}): {result['kept_dirty']}")
        if result["deleted_branches"]:
            print(f"deleted_branches ({len(result['deleted_branches'])}): {result['deleted_branches']}")
    if result["kept_dirty"]:
        return 1
    return 0


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

    # AO-MA-4: spawn parallel worktrees from a manifest
    spawn_p = orchestration_sub.add_parser(
        "spawn",
        help="Prepare parallel git worktrees from an AO-MA-3 manifest (no agent execution)",
    )
    spawn_p.add_argument(
        "--manifest",
        required=True,
        help="Path to AO-MA-3 manifest.v1.json",
    )
    spawn_p.add_argument(
        "--repo-root",
        default=None,
        help="Repository root path (default: current working directory)",
    )
    spawn_p.add_argument(
        "--worktree-base",
        default=None,
        help=(
            "Override base directory for worktrees. Precedence: this flag > "
            "AO_MA_WORKTREE_BASE env > planned path under repo root."
        ),
    )
    spawn_p.add_argument(
        "--dry-run",
        action="store_true",
        help="Plan worktrees without creating them on disk",
    )
    spawn_p.add_argument(
        "--format",
        choices=["text", "json"],
        default="text",
        help="Stdout summary format (default: text)",
    )

    # AO-MA-4: cleanup prepared worktrees
    cleanup_p = orchestration_sub.add_parser(
        "cleanup",
        help="Remove prepared worktrees (clean only) and optionally branches",
    )
    cleanup_p.add_argument(
        "--manifest",
        required=True,
        help="Path to AO-MA-3 manifest.v1.json",
    )
    cleanup_p.add_argument(
        "--repo-root",
        default=None,
        help="Repository root path (default: current working directory)",
    )
    cleanup_p.add_argument(
        "--worktree-base",
        default=None,
        help=(
            "Override base directory for worktrees. Precedence: this flag > "
            "AO_MA_WORKTREE_BASE env > planned path under repo root."
        ),
    )
    cleanup_p.add_argument(
        "--delete-branches",
        action="store_true",
        help="Delete branches that are clean and already merged into origin/main",
    )
    cleanup_p.add_argument(
        "--format",
        choices=["text", "json"],
        default="text",
        help="Stdout summary format (default: text)",
    )

    # AO-MA-5: integrate worker outputs (read-only policy; NO remote write)
    integrate_p = orchestration_sub.add_parser(
        "integrate",
        help=(
            "Integrator policy v1: accept/reject/not_integratable worker outputs + conflict "
            "report + operator-runnable assembly plan. No git push, no gh pr create — integrator "
            "produces data; operator executes assembly_plan by hand."
        ),
    )
    integrate_p.add_argument("--manifest", required=True, help="Path to AO-MA-3 manifest.v1.json")
    integrate_p.add_argument(
        "--runner-report",
        default=None,
        help="Path to AO-MA-4 runner_report.v1.json (default: <manifest_dir>/runner_report.v1.json)",
    )
    integrate_p.add_argument(
        "--worker-result",
        action="append",
        default=None,
        help=(
            "Per-task worker_result.v1.json mapping in the form '<task_id>=<path>'. Repeat per task. "
            "Default: use runner_report worker entry's expected_worker_result_path."
        ),
    )
    integrate_p.add_argument(
        "--review-verdict",
        action="append",
        default=None,
        help="Per-task review_verdict.v1.json mapping '<task_id>=<path>'. Repeat per task.",
    )
    integrate_p.add_argument(
        "--verification-report",
        action="append",
        default=None,
        help="Per-task verification_report.v1.json mapping '<task_id>=<path>'. Repeat per task.",
    )
    integrate_p.add_argument(
        "--repo-root",
        default=None,
        help="Repository root path (default: current working directory)",
    )
    integrate_p.add_argument(
        "--format",
        choices=["text", "json"],
        default="text",
        help="Stdout summary format (default: text)",
    )


def _parse_per_task_paths(raw: list[str] | None, kind: str) -> dict[str, Path]:
    """Parse repeated '--worker-result <task_id>=<path>' CLI args into a dict.

    Format: '<task_id>=<path>'. Raises SystemExit on malformed input
    (operator error — bad CLI invocation, not a runner failure).
    """

    if not raw:
        return {}
    out: dict[str, Path] = {}
    for entry in raw:
        if "=" not in entry:
            raise SystemExit(f"--{kind} {entry!r} must be '<task_id>=<path>'")
        task_id, _, path = entry.partition("=")
        task_id = task_id.strip()
        path = path.strip()
        if not task_id or not path:
            raise SystemExit(f"--{kind} {entry!r} must be '<task_id>=<path>' with both sides non-empty")
        out[task_id] = Path(path)
    return out


def cmd_orchestration_integrate(args: argparse.Namespace) -> int:
    """Handle ``ao-kernel orchestration integrate`` (AO-MA-5 v1).

    Exit codes (Codex iter-2 absorb):

    - 0 — all accepted, no conflict, no pending
    - 1 — any not_integratable / rejected / conflict (operator action)
    - 2 — manifest envelope invalid / runner_report missing / artifact load fail (operator error)
    - 3 — integration emit failure (FS/schema)
    """

    manifest_path = Path(args.manifest).resolve()
    if not manifest_path.exists():
        print(f"error: manifest not found: {manifest_path!s}", file=sys.stderr)
        return 2
    runner_report_path = Path(args.runner_report).resolve() if args.runner_report else None
    repo_root = Path(args.repo_root).resolve() if args.repo_root else Path.cwd()
    worker_result_paths = _parse_per_task_paths(args.worker_result, "worker-result")
    review_verdict_paths = _parse_per_task_paths(args.review_verdict, "review-verdict")
    verification_report_paths = _parse_per_task_paths(args.verification_report, "verification-report")

    integrator = Integrator(repo_root=repo_root)
    try:
        decision = integrator.integrate(
            manifest_path=manifest_path,
            runner_report_path=runner_report_path,
            worker_result_paths=worker_result_paths,
            review_verdict_paths=review_verdict_paths,
            verification_report_paths=verification_report_paths,
        )
    except IntegratorError as exc:
        msg = str(exc)
        # Distinguish trust-boundary failures (exit 2) from emit failures (exit 3)
        if "integration report write failed" in msg:
            print(f"orchestration integrate emit failure: {msg}", file=sys.stderr)
            return 3
        print(f"orchestration integrate failed: {msg}", file=sys.stderr)
        return 2

    if args.format == "json":
        print(
            json.dumps(
                {
                    "overall_status": decision.overall_status,
                    "report": decision.report,
                    "assembly_plan": decision.assembly_plan,
                    "diagnostics": decision.diagnostics,
                    "has_conflicts": decision.has_conflicts,
                    "has_rejections": decision.has_rejections,
                    "has_pending": decision.has_pending,
                },
                indent=2,
                sort_keys=True,
            )
        )
    else:
        print(f"overall_status: {decision.overall_status}")
        if decision.diagnostics:
            print("diagnostics:")
            for diag in decision.diagnostics:
                print(f"  - {diag}")
        print(render_assembly_plan_text(decision.assembly_plan))

    # Exit code matrix
    if decision.has_pending or decision.has_rejections or decision.has_conflicts:
        return 1
    if decision.overall_status == "no_workers":
        return 1
    return 0
