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
from ao_kernel.orchestration.reviewer import (
    ReviewInputs,
    Reviewer,
    ReviewerError,
)
from ao_kernel.orchestration.task_graph_builder import TaskSpec
from ao_kernel.orchestration.verifier import (
    VerificationInputs,
    Verifier,
    VerifierError,
)
from ao_kernel.orchestration.native_worker_import import (
    NativeWorkerImportError,
    import_native_worker_result,
)
from ao_kernel.orchestration.worker_invoker import WorkerInvocationError, WorkerInvoker
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

    # AO-MA-6: review (artifact intake; NO LLM call; NO PR/GitHub fetch)
    review_p = orchestration_sub.add_parser(
        "review",
        help=(
            "Reviewer artifact intake v1: validate inputs, enforce cross-provider + bounded "
            "REVISE, emit schema-valid review_verdict.v1.json. NO LLM call, NO PR/GitHub fetch — "
            "operator (or external reviewer) supplies the verdict + findings + evidence paths."
        ),
    )
    review_p.add_argument("--manifest", required=True, help="Path to AO-MA-3 manifest.v1.json")
    review_p.add_argument("--task-id", required=True, help="Task ID being reviewed (must match runner_report worker)")
    review_p.add_argument(
        "--worker-result",
        action="append",
        required=True,
        help=(
            "Per-task worker_result.v1.json mapping '<task_id>=<path>'. Reviewer reads the "
            "implementer identity from worker_result.worker.provider (cross-provider HARD RULE)."
        ),
    )
    review_p.add_argument("--reviewer-agent-id", required=True, help="Reviewer agent ID (free string)")
    review_p.add_argument(
        "--reviewer-provider",
        required=True,
        choices=["openai", "anthropic", "minimax", "google", "local", "tool"],
        help="Reviewer LLM provider; must differ from worker_result.worker.provider",
    )
    review_p.add_argument("--reviewer-session-id", required=True, help="Reviewer session ID (audit trail)")
    review_p.add_argument(
        "--verdict",
        required=True,
        choices=["AGREE", "REVISE", "BLOCK"],
        help="Reviewer's verdict; REVISE may be force-blocked when bounded REVISE budget exhausted",
    )
    review_p.add_argument(
        "--findings-json",
        required=True,
        help=(
            "Path to JSON file containing a top-level array of finding objects matching "
            "ao-ma-review-verdict.schema.v1.json::$defs.finding (severity + title + body required; "
            "additionalProperties=false)."
        ),
    )
    review_p.add_argument("--diff-path", default=None, help="Optional: PR/git diff snapshot consulted")
    review_p.add_argument(
        "--acceptance-criteria-path", default=None, help="Optional: task.acceptance_criteria evidence"
    )
    review_p.add_argument("--repo-ssot", default=None, help="Optional: repo SSOT excerpt consulted")
    review_p.add_argument("--ci-results", default=None, help="Optional: CI output consulted")
    review_p.add_argument("--artifact-chain", default=None, help="Optional: related AO-MA artifacts consulted")
    review_p.add_argument(
        "--prior-review-verdict",
        action="append",
        default=None,
        help=(
            "Repeatable: path to prior review_verdict.v1.json file (same task). Used for "
            "bounded REVISE budget count. Verdicts for other graphs/tasks ignored defensively."
        ),
    )
    review_p.add_argument(
        "--repo-root",
        default=None,
        help="Repository root path (default: current working directory)",
    )
    review_p.add_argument(
        "--format",
        choices=["text", "json"],
        default="text",
        help="Stdout summary format (default: text)",
    )

    # AO-MA-7: verify (deterministic checks; NO LLM call)
    verify_p = orchestration_sub.add_parser(
        "verify",
        help=(
            "Verifier lane v1: deterministic GPP guard + metadata secret scan + diff scope + "
            "artifact hash checks. Emits schema-valid verification_report.v1.json. NO LLM call, "
            "NO subprocess, NO PR/GitHub fetch — pure-data verification."
        ),
    )
    verify_p.add_argument("--manifest", required=True, help="Path to AO-MA-3 manifest.v1.json")
    verify_p.add_argument(
        "--task-id",
        required=True,
        help="Task ID being verified (must match worker_result.task_id and task_graph entry)",
    )
    verify_p.add_argument(
        "--worker-result",
        action="append",
        required=True,
        help=(
            "Per-task worker_result.v1.json mapping '<task_id>=<path>'. Verifier reads the "
            "implementer identity from worker_result.worker.provider (cross-provider HARD RULE; "
            "set --verifier-provider tool for no-LLM verifier)."
        ),
    )
    verify_p.add_argument("--verifier-agent-id", required=True, help="Verifier agent ID (free string)")
    verify_p.add_argument(
        "--verifier-provider",
        default="tool",
        choices=["openai", "anthropic", "minimax", "google", "local", "tool"],
        help=(
            "Verifier provider identity (default: tool — no-LLM deterministic verifier). "
            "Must differ from worker_result.worker.provider."
        ),
    )
    verify_p.add_argument("--verifier-session-id", required=True, help="Verifier session ID (audit trail)")
    verify_p.add_argument(
        "--review-verdict",
        default=None,
        help=(
            "Optional: path to review_verdict.v1.json (AO-MA-6 output). Verifier reads "
            "guard_flags + no_secret_attestation + computes its hash into artifact_hashes."
        ),
    )
    verify_p.add_argument(
        "--gpp-status",
        default=None,
        help=(
            "Optional: path to gpp_status.v1.json (defaults to <repo_root>/.claude/plans/"
            "gpp_status.v1.json when present). Verifier reads support_widening_allowed + "
            "production_platform_claim_allowed + live_adapter_execution_allowed allowlist flags."
        ),
    )
    verify_p.add_argument(
        "--repo-root",
        default=None,
        help="Repository root path (default: current working directory)",
    )
    verify_p.add_argument(
        "--format",
        choices=["text", "json"],
        default="text",
        help="Stdout summary format (default: text)",
    )

    # AO-MA-4.5: invoke pinned deterministic local worker fixture per prepared worktree
    invoke_p = orchestration_sub.add_parser(
        "invoke",
        help=(
            "AO-MA-4.5 worker invocation v1: run the pinned deterministic local worker "
            "fixture for each prepared runner_report worktree and emit "
            "worker_invocation_report.v1.json. No arbitrary adapter selection, no live "
            "adapter execution — a live adapter or open live_adapter_execution flag is "
            "rejected fail-closed."
        ),
    )
    invoke_p.add_argument("--manifest", required=True, help="Path to AO-MA-3 manifest.v1.json")
    invoke_p.add_argument(
        "--repo-root",
        default=None,
        help="Repository root path (default: current working directory)",
    )
    invoke_p.add_argument(
        "--format",
        choices=["text", "json"],
        default="text",
        help="Stdout summary format (default: text)",
    )

    # AO-MA-4.6-1: native worker result import (import-only)
    native_p = orchestration_sub.add_parser(
        "native-import",
        help=(
            "AO-MA-4.6-1 native worker result import (import-only): operator/AI "
            "produces worker_result.v1.json externally via a native interface "
            "(claude-cli, codex-cli, mavis-cli, local-file); ao-kernel imports + "
            "schema-validates + provenance-binds it and atomically copies to "
            "<artifact_dir>/workers/<task_id>/worker_result.v1.json. ao-kernel "
            "calls NOTHING — no subprocess, no network, no LLM, no GitHub. Fatal "
            "trust-boundary errors raise NativeWorkerImportError + exit 1; "
            "policy-invalid emits a schema-valid invalid import_report + exit 1; "
            "all-pass emits valid import_report + integrated copy + exit 0."
        ),
    )
    native_p.add_argument(
        "--result",
        required=True,
        help="Path to the operator/AI-produced worker_result.v1.json (absolute permitted)",
    )
    native_p.add_argument(
        "--runner-report",
        required=True,
        help="Path to the AO-MA-4 runner_report.v1.json (its parent is the canonical artifact_dir)",
    )
    native_p.add_argument(
        "--source-interface",
        required=True,
        choices=["claude-cli", "codex-cli", "mavis-cli", "local-file"],
        help="Native interface that produced the worker_result.v1.json",
    )
    native_p.add_argument(
        "--imported-at",
        default=None,
        help=(
            "RFC3339 UTC timestamp (YYYY-MM-DDTHH:MM:SSZ). Default: current UTC. "
            "Module is pure; CLI stamps the timestamp once and passes it through."
        ),
    )
    native_p.add_argument(
        "--artifact-dir",
        default=None,
        help=(
            "Optional artifact directory. Default: runner_report parent. When "
            "supplied, MUST equal runner_report.parent.resolve() (mismatch is fatal)."
        ),
    )
    native_p.add_argument(
        "--allow-source-interface",
        action="append",
        choices=["claude-cli", "codex-cli", "mavis-cli", "local-file"],
        default=None,
        help=(
            "Narrow the source_interface allowlist for this import. Repeatable. "
            "Default: full canonical allowlist (claude-cli, codex-cli, mavis-cli, "
            "local-file). Effective allowlist is recorded in the import report."
        ),
    )
    native_p.add_argument(
        "--out",
        required=True,
        help="Path to write the ao-ma-native-worker-import-report.v1.json artifact",
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
    # (no_workers is no longer reachable here — Codex iter-5 absorb moved
    # empty runner_report.workers to IntegratorError → exit 2 trust-boundary
    # failure, since iter-4 required "at least one worker decision" for emit.)
    if decision.has_pending or decision.has_rejections or decision.has_conflicts:
        return 1
    return 0


def cmd_orchestration_review(args: argparse.Namespace) -> int:
    """Handle ``ao-kernel orchestration review`` (AO-MA-6 v1).

    Exit codes (Codex iter-1/2 absorb):

    - 0 — review_verdict.v1.json emitted (AGREE/REVISE/BLOCK or budget-forced BLOCK)
    - 2 — missing required input / schema validation fail / cross-provider violation / trust-boundary fail
    - 3 — write failure (FS / schema mismatch at emit time)
    """

    manifest_path = Path(args.manifest).resolve()
    if not manifest_path.exists():
        print(f"error: manifest not found: {manifest_path!s}", file=sys.stderr)
        return 2
    repo_root = Path(args.repo_root).resolve() if args.repo_root else Path.cwd()
    worker_result_paths = _parse_per_task_paths(args.worker_result, "worker-result")

    def _opt_path(value: str | None) -> Path | None:
        return Path(value).resolve() if value else None

    findings_path = Path(args.findings_json).resolve()
    if not findings_path.exists():
        print(f"error: --findings-json file not found: {findings_path!s}", file=sys.stderr)
        return 2

    prior_paths = [Path(p).resolve() for p in (args.prior_review_verdict or [])]
    for p in prior_paths:
        if not p.exists():
            print(f"error: --prior-review-verdict file not found: {p!s}", file=sys.stderr)
            return 2

    inputs = ReviewInputs(
        manifest_path=manifest_path,
        task_id=args.task_id,
        worker_result_paths=worker_result_paths,
        reviewer_agent_id=args.reviewer_agent_id,
        reviewer_provider=args.reviewer_provider,
        reviewer_session_id=args.reviewer_session_id,
        verdict=args.verdict,
        findings_path=findings_path,
        diff_path=_opt_path(args.diff_path),
        acceptance_criteria_path=_opt_path(args.acceptance_criteria_path),
        repo_ssot_path=_opt_path(args.repo_ssot),
        ci_results_path=_opt_path(args.ci_results),
        artifact_chain_path=_opt_path(args.artifact_chain),
        prior_review_verdict_paths=prior_paths,
    )

    reviewer = Reviewer(repo_root=repo_root)
    try:
        decision = reviewer.review(inputs)
    except ReviewerError as exc:
        msg = str(exc)
        if "review_verdict write failed" in msg:
            print(f"orchestration review emit failure: {msg}", file=sys.stderr)
            return 3
        print(f"orchestration review failed: {msg}", file=sys.stderr)
        return 2

    if args.format == "json":
        print(
            json.dumps(
                {
                    "requested_verdict": decision.requested_verdict,
                    "emitted_verdict": decision.emitted_verdict,
                    "prior_revise_count": decision.prior_revise_count,
                    "max_revise_rounds": decision.max_revise_rounds,
                    "budget_forced_block": decision.budget_forced_block,
                    "diagnostics": decision.diagnostics,
                    "report": decision.report,
                },
                indent=2,
                sort_keys=True,
            )
        )
    else:
        print(f"requested_verdict: {decision.requested_verdict}")
        print(f"emitted_verdict:   {decision.emitted_verdict}")
        print(f"prior_revise_count: {decision.prior_revise_count}")
        print(f"max_revise_rounds:  {decision.max_revise_rounds}")
        print(f"budget_forced_block: {decision.budget_forced_block}")
        if decision.diagnostics:
            print("diagnostics:")
            for diag in decision.diagnostics:
                print(f"  - {diag}")
        print(f"emitted to: {manifest_path.parent / 'workers' / args.task_id / 'review_verdict.v1.json'}")

    return 0


def cmd_orchestration_verify(args: argparse.Namespace) -> int:
    """Handle ``ao-kernel orchestration verify`` (AO-MA-7 v1).

    Exit codes (Codex iter-1 must_close #6 absorb):

    - 0 — verification_report.v1.json emitted, all checks pass
    - 1 — verification_report.v1.json emitted, failed_checks non-empty
    - 2 — missing required input / schema validation fail / cross-provider violation / trust-boundary fail
    - 3 — write failure (FS / schema mismatch at emit time)
    """

    manifest_path = Path(args.manifest).resolve()
    if not manifest_path.exists():
        print(f"error: manifest not found: {manifest_path!s}", file=sys.stderr)
        return 2
    repo_root = Path(args.repo_root).resolve() if args.repo_root else Path.cwd()
    worker_result_paths = _parse_per_task_paths(args.worker_result, "worker-result")

    review_verdict_path: Path | None = None
    if args.review_verdict:
        review_verdict_path = Path(args.review_verdict).resolve()
        if not review_verdict_path.exists():
            print(f"error: --review-verdict file not found: {review_verdict_path!s}", file=sys.stderr)
            return 2

    gpp_status_path: Path | None = None
    if args.gpp_status:
        gpp_status_path = Path(args.gpp_status).resolve()
        if not gpp_status_path.exists():
            print(f"error: --gpp-status file not found: {gpp_status_path!s}", file=sys.stderr)
            return 2

    inputs = VerificationInputs(
        manifest_path=manifest_path,
        task_id=args.task_id,
        worker_result_paths=worker_result_paths,
        verifier_agent_id=args.verifier_agent_id,
        verifier_provider=args.verifier_provider,
        verifier_session_id=args.verifier_session_id,
        review_verdict_path=review_verdict_path,
        gpp_status_path=gpp_status_path,
    )

    verifier = Verifier(repo_root=repo_root)
    try:
        result = verifier.verify(inputs)
    except VerifierError as exc:
        msg = str(exc)
        if "verification_report write failed" in msg:
            print(f"orchestration verify emit failure: {msg}", file=sys.stderr)
            return 3
        print(f"orchestration verify failed: {msg}", file=sys.stderr)
        return 2

    if args.format == "json":
        print(
            json.dumps(
                {
                    "overall_pass": result.overall_pass,
                    "failed_checks": result.failed_checks,
                    "diagnostics": result.diagnostics,
                    "report": result.report,
                },
                indent=2,
                sort_keys=True,
            )
        )
    else:
        print(f"overall_pass: {result.overall_pass}")
        commands = result.report.get("commands", [])
        for cmd_entry in commands:
            print(f"  - {cmd_entry['command']}: {cmd_entry['outcome']}")
        if result.failed_checks:
            print("failed_checks:")
            for fc in result.failed_checks:
                print(f"  - {fc}")
        if result.diagnostics:
            print("diagnostics:")
            for diag in result.diagnostics:
                print(f"  - {diag}")
        print(f"emitted to: {manifest_path.parent / 'workers' / args.task_id / 'verification_report.v1.json'}")

    return 1 if result.failed_checks else 0


def cmd_orchestration_invoke(args: argparse.Namespace) -> int:
    """Handle ``ao-kernel orchestration invoke`` (AO-MA-4.5 v1).

    Runs the pinned deterministic local worker fixture for each eligible
    runner_report worker entry (``prepared`` / ``skipped_existing_idempotent``)
    and emits ``worker_invocation_report.v1.json``. There is no arbitrary
    adapter selection and no live adapter execution; a live adapter or an open
    ``live_adapter_execution`` flag is rejected fail-closed.

    Exit codes:

    - 0 — invocation report emitted; no worker entry failed
    - 1 — invocation report emitted; at least one worker entry failed
    - 2 — manifest not found / trust-boundary or fail-closed error
    """

    manifest_path = Path(args.manifest).resolve()
    if not manifest_path.exists():
        print(f"error: manifest not found: {manifest_path!s}", file=sys.stderr)
        return 2
    repo_root = Path(args.repo_root).resolve() if args.repo_root else Path.cwd()
    invoker = WorkerInvoker(repo_root=repo_root)
    try:
        report = invoker.invoke(manifest_path=manifest_path)
    except WorkerInvocationError as exc:
        print(f"orchestration invoke failed: {exc}", file=sys.stderr)
        return 2

    if args.format == "json":
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print(f"task_graph_id: {report['task_graph_id']}")
        print(f"fixture_id: {report['fixture_id']}")
        print(f"invoked ({len(report['invoked'])}):")
        for entry in report["invoked"]:
            print(f"  - {entry['task_id']} [{entry['status']}] {entry['reason']}")

    if any(entry["status"] == "failed" for entry in report["invoked"]):
        return 1
    return 0


def _load_schema(name: str) -> dict[str, object]:
    """Load a bundled AO-MA schema by file name (importlib.resources)."""

    from importlib import resources

    schema_path = resources.files("ao_kernel.defaults.schemas").joinpath(name)
    return json.loads(schema_path.read_text(encoding="utf-8"))  # type: ignore[no-any-return]


def cmd_orchestration_native_import(args: argparse.Namespace) -> int:
    """Handle ``ao-kernel orchestration native-import`` (AO-MA-4.6-1).

    Exit codes:
    - 0 — schema-valid import_report emitted with valid=true; integrated copy written
    - 1 — schema-valid import_report emitted with valid=false (policy-invalid)
          OR fatal trust-boundary error before any report was written
    """

    import datetime as _dt

    source_path = Path(args.result).resolve()
    runner_report_path = Path(args.runner_report).resolve()
    artifact_dir = Path(args.artifact_dir).resolve() if args.artifact_dir else None
    if args.imported_at:
        imported_at = args.imported_at
    else:
        imported_at = _dt.datetime.now(tz=_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    out_path = Path(args.out).resolve()
    allowlist = args.allow_source_interface if args.allow_source_interface else None

    worker_result_schema = _load_schema("ao-ma-worker-result.schema.v1.json")
    runner_report_schema = _load_schema("ao-ma-runner-report.schema.v1.json")
    task_graph_schema = _load_schema("ao-ma-task-graph.schema.v1.json")
    assignment_schema = _load_schema("ao-ma-agent-assignment.schema.v1.json")
    import_report_schema = _load_schema("ao-ma-native-worker-import-report.schema.v1.json")

    try:
        report = import_native_worker_result(
            source_result_path=source_path,
            runner_report_path=runner_report_path,
            source_interface=args.source_interface,
            imported_at=imported_at,
            artifact_dir=artifact_dir,
            source_interface_allowlist=allowlist,
            worker_result_schema=worker_result_schema,
            runner_report_schema=runner_report_schema,
            task_graph_schema=task_graph_schema,
            assignment_schema=assignment_schema,
            import_report_schema=import_report_schema,
        )
    except NativeWorkerImportError as exc:
        print(f"orchestration native-import failed: {exc}", file=sys.stderr)
        return 1

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"import_report: {out_path!s} (valid={report['valid']})", file=sys.stderr)
    return 0 if report["valid"] else 1
