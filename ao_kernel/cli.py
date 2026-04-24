"""ao-kernel CLI entrypoint.

Usage:
    ao-kernel init
    ao-kernel migrate [--dry-run] [--backup]
    ao-kernel doctor
    ao-kernel version
"""

from __future__ import annotations

import argparse
import sys

import ao_kernel


def _cmd_version(args: argparse.Namespace) -> int:
    print(f"ao-kernel {ao_kernel.__version__}")
    return 0


def _cmd_init(args: argparse.Namespace) -> int:
    from ao_kernel.init_cmd import run

    return run(workspace_root_override=args.workspace_root)


def _cmd_migrate(args: argparse.Namespace) -> int:
    from ao_kernel.migrate_cmd import run

    return run(
        workspace_root_override=args.workspace_root,
        dry_run=args.dry_run,
        backup=args.backup,
    )


def _cmd_doctor(args: argparse.Namespace) -> int:
    from ao_kernel.doctor_cmd import run

    return run(workspace_root_override=args.workspace_root)


def _cmd_mcp_serve(args: argparse.Namespace) -> int:
    transport = getattr(args, "transport", "stdio")
    try:
        import asyncio

        if transport == "http":
            from ao_kernel.mcp_server import serve_http

            host = getattr(args, "host", "127.0.0.1")
            port = getattr(args, "port", 8080)
            asyncio.run(serve_http(host=host, port=port))
        else:
            from ao_kernel.mcp_server import serve_stdio

            asyncio.run(serve_stdio())
        return 0
    except ImportError as e:
        if "mcp" in str(e).lower():
            from ao_kernel.i18n import msg

            print(msg("error_mcp_missing"))
            return 1
        raise


def _cmd_repo_scan(args: argparse.Namespace) -> int:
    import json as _json
    from pathlib import Path as _Path

    from ao_kernel.repo_intelligence import scan_repo, write_repo_scan_artifacts

    project_root = _Path(args.project_root or ".").resolve()
    if not project_root.is_dir():
        print(f"project root not found: {project_root}", file=sys.stderr)
        return 1

    workspace_dir = project_root / ".ao"
    if not workspace_dir.is_dir():
        print(
            f".ao workspace not found under {project_root}. Run 'ao-kernel init' first.",
            file=sys.stderr,
        )
        return 1

    context_dir = workspace_dir / "context"
    context_dir.mkdir(parents=True, exist_ok=True)

    repo_map = scan_repo(project_root)
    write_result = write_repo_scan_artifacts(context_dir=context_dir, repo_map=repo_map)
    summary = {
        "status": "ok",
        "command": "repo scan",
        "project_root": ".",
        "project_root_name": project_root.name,
        "summary": repo_map["summary"],
        "artifacts": write_result["artifacts"],
    }
    if args.output == "json":
        print(_json.dumps(summary, indent=2, sort_keys=True))
    else:
        print("repo scan complete")
        print("project_root: .")
        print(f"included_files: {repo_map['summary']['included_files']}")
        print("artifacts:")
        for artifact in write_result["artifacts"]:
            print(f"- {artifact['path']}")
    return 0


def _cmd_cost_reconcile(args: argparse.Namespace) -> int:
    """v3.4.0 CLI: scan ledger for orphan spend entries and stamp
    missing markers. Idempotent + cursor-based."""
    import json as _json
    from pathlib import Path as _Path

    from ao_kernel.cost.policy import load_cost_policy
    from ao_kernel.cost.reconcile_daemon import scan_and_fix

    project_root = _Path(args.project_root or _Path.cwd()).resolve()
    policy = load_cost_policy(project_root)
    if not policy.enabled:
        print(
            "cost tracking policy is disabled; nothing to reconcile",
            file=sys.stderr,
        )
        return 0

    result = scan_and_fix(
        project_root,
        policy,
        dry_run=bool(args.dry_run),
        cursor_reset=bool(args.cursor_reset),
    )

    if args.output == "json":
        payload = {
            "dry_run": bool(args.dry_run),
            "orphans_found": result.orphans_found,
            "orphans_fixed": result.orphans_fixed,
            "orphans_skipped": result.orphans_skipped,
            "cursor_offset_before": result.cursor_offset_before,
            "cursor_offset_after": result.cursor_offset_after,
            "errors": list(result.errors),
        }
        print(_json.dumps(payload, indent=2, sort_keys=True))
    else:
        mode = "dry-run" if args.dry_run else "apply"
        print(
            f"Reconciler {mode}: found={result.orphans_found} "
            f"fixed={result.orphans_fixed} skipped={result.orphans_skipped}"
        )
        print(f"Cursor: offset {result.cursor_offset_before} → {result.cursor_offset_after}")
        if result.errors:
            print("Errors:")
            for err in result.errors:
                print(f"  - {err}")
    return 0 if not result.errors else 1


def _cmd_cost_compact_markers(args: argparse.Namespace) -> int:
    """v3.4.0 #3 CLI: compact `cost_reconciled` markers to archive."""
    import json as _json
    from pathlib import Path as _Path

    from ao_kernel.cost.marker_compaction import (
        compact_all_terminal_runs,
        compact_run_markers,
    )

    if bool(args.run_id) == bool(args.all_terminal):
        print(
            "error: pass exactly one of --run-id or --all-terminal",
            file=sys.stderr,
        )
        return 2

    project_root = _Path(args.project_root or _Path.cwd()).resolve()
    dry_run = bool(args.dry_run)

    if args.run_id:
        res = compact_run_markers(project_root, args.run_id, dry_run=dry_run)
        if args.output == "json":
            payload = {
                "run_id": res.run_id,
                "markers_archived": res.markers_archived,
                "archive_path": (str(res.archive_path.relative_to(project_root)) if res.archive_path else None),
                "already_compact": res.already_compact,
                "dry_run": dry_run,
            }
            print(_json.dumps(payload, indent=2, sort_keys=True))
        else:
            status = "dry-run" if dry_run else "applied"
            if res.already_compact:
                print(f"run {res.run_id}: already compact (no markers)")
            else:
                print(f"run {res.run_id} [{status}]: archived {res.markers_archived} marker(s) → {res.archive_path}")
        return 0

    bulk = compact_all_terminal_runs(project_root, dry_run=dry_run)
    if args.output == "json":
        payload = {
            "runs_scanned": bulk.runs_scanned,
            "runs_compacted": bulk.runs_compacted,
            "markers_archived_total": bulk.markers_archived_total,
            "errors": list(bulk.errors),
            "dry_run": dry_run,
        }
        print(_json.dumps(payload, indent=2, sort_keys=True))
    else:
        mode = "dry-run" if dry_run else "applied"
        print(
            f"Compaction [{mode}]: scanned={bulk.runs_scanned} "
            f"compacted={bulk.runs_compacted} "
            f"markers_total={bulk.markers_archived_total}"
        )
        if bulk.errors:
            print("Errors:")
            for err in bulk.errors:
                print(f"  - {err}")
    return 0 if not bulk.errors else 1


def _cmd_consultation_promote(args: argparse.Namespace) -> int:
    """v3.5 D2b CLI: promote resolved AGREE/PARTIAL consultations
    from the evidence archive into canonical_decisions.v1.json.
    Opt-in via policy.promotion.enabled=true; --force bypasses
    the flag only (integrity + eligibility still enforced)."""
    import json as _json
    from pathlib import Path as _Path

    from ao_kernel.config import load_with_override
    from ao_kernel.consultation.promotion import (
        promote_resolved_consultations,
    )

    project_root = _Path(args.project_root or _Path.cwd()).resolve()
    policy = load_with_override(
        "policies",
        "policy_agent_consultation.v1.json",
        workspace=project_root / ".ao",
    )

    summary = promote_resolved_consultations(
        project_root,
        policy,
        dry_run=bool(args.dry_run),
        force=bool(args.force),
    )

    if args.output == "json":
        payload = {
            "dry_run": summary.dry_run,
            "scanned": summary.scanned,
            "eligible": summary.eligible,
            "promoted": summary.promoted,
            "updated": summary.updated,
            "skipped_same_digest": summary.skipped_same_digest,
            "skipped_integrity": summary.skipped_integrity,
            "skipped_ineligible": summary.skipped_ineligible,
            "skipped_disabled": summary.skipped_disabled,
            "skipped_missing_record": summary.skipped_missing_record,
            "errors": list(summary.errors),
        }
        print(_json.dumps(payload, indent=2, sort_keys=True))
    else:
        mode = "dry-run" if summary.dry_run else "applied"
        print(
            f"Consultation promote [{mode}]: "
            f"scanned={summary.scanned} "
            f"eligible={summary.eligible} "
            f"promoted={summary.promoted} "
            f"updated={summary.updated}"
        )
        print(
            f"  skipped: same_digest={summary.skipped_same_digest} "
            f"integrity={summary.skipped_integrity} "
            f"ineligible={summary.skipped_ineligible} "
            f"disabled={summary.skipped_disabled} "
            f"missing_record={summary.skipped_missing_record}"
        )
        if summary.errors:
            print("Errors:")
            for err in summary.errors:
                print(f"  - {err}")
    return 0 if (not summary.errors and summary.skipped_disabled == 0) else (0 if summary.skipped_disabled else 1)


def _cmd_consultation_archive(args: argparse.Namespace) -> int:
    """v3.5 D2a CLI: scan CNS corpus, snapshot into
    `.ao/evidence/consultations/<CNS-ID>/`, emit events, build
    resolution record, refresh integrity manifest + archive-meta.
    Idempotent. `--verify` validates existing manifests without
    mutation."""
    import json as _json
    from pathlib import Path as _Path

    from ao_kernel.config import load_with_override
    from ao_kernel.consultation.archive import archive_all
    from ao_kernel.consultation.integrity import (
        verify_consultation_manifest,
    )

    project_root = _Path(args.project_root or _Path.cwd()).resolve()
    policy = load_with_override(
        "policies",
        "policy_agent_consultation.v1.json",
        workspace=project_root / ".ao",
    )

    # --verify path: no mutation, integrity-only
    if getattr(args, "verify", False):
        evidence_root = project_root / ".ao" / "evidence" / "consultations"
        verify_results: list[tuple[str, bool, list[str]]] = []
        overall_ok = True
        if evidence_root.is_dir():
            for cns_dir in sorted(evidence_root.iterdir()):
                if not cns_dir.is_dir():
                    continue
                if cns_dir.name.startswith("."):
                    continue
                ok, errors = verify_consultation_manifest(cns_dir)
                if not ok:
                    overall_ok = False
                verify_results.append((cns_dir.name, ok, errors))
        if args.output == "json":
            payload = {
                "ok": overall_ok,
                "scanned": len(verify_results),
                "results": [{"cns_id": name, "ok": ok, "errors": list(errs)} for name, ok, errs in verify_results],
            }
            print(_json.dumps(payload, indent=2, sort_keys=True))
        else:
            print(f"Consultation verify: scanned={len(verify_results)} ok={overall_ok}")
            for name, ok, errs in verify_results:
                if not ok:
                    print(f"  - {name}:")
                    for err in errs:
                        print(f"      • {err}")
        return 0 if overall_ok else 1

    summary = archive_all(
        policy,
        workspace_root=project_root,
        dry_run=bool(args.dry_run),
        renormalize=bool(args.renormalize),
    )

    if args.output == "json":
        payload = {
            "dry_run": summary.dry_run,
            "scanned_cns": summary.scanned_cns,
            "archived": summary.archived,
            "errors_total": summary.errors_total,
            "results": [
                {
                    "cns_id": r.cns_id,
                    "evidence_dir": str(r.evidence_dir),
                    "events_appended": r.events_appended,
                    "record_written": r.record_written,
                    "manifest_written": r.manifest_written,
                    "errors": list(r.errors),
                }
                for r in summary.results
            ],
        }
        print(_json.dumps(payload, indent=2, sort_keys=True))
    else:
        mode = "dry-run" if summary.dry_run else "applied"
        print(
            f"Consultation archive [{mode}]: "
            f"scanned={summary.scanned_cns} "
            f"archived={summary.archived} "
            f"errors={summary.errors_total}"
        )
    return 0 if summary.errors_total == 0 else 1


def _cmd_consultation_migrate(args: argparse.Namespace) -> int:
    """v3.5 D1 CLI: copy-forward legacy consultation artefacts to the
    canonical `.ao/consultations/` layout."""
    import json as _json
    from pathlib import Path as _Path

    from ao_kernel.config import load_with_override
    from ao_kernel.consultation.migrate import migrate_consultations

    project_root = _Path(args.project_root or _Path.cwd()).resolve()
    # PR-D1 fix: workspace override hit first (policy SSOT). Workspace
    # resources live under `<project_root>/.ao/`; load_with_override
    # resolves to bundled default when no override exists.
    policy = load_with_override(
        "policies",
        "policy_agent_consultation.v1.json",
        workspace=project_root / ".ao",
    )

    result = migrate_consultations(
        policy,
        workspace_root=project_root,
        dry_run=bool(args.dry_run),
        force=bool(args.force),
        include_invalid=bool(args.include_invalid),
    )

    if args.output == "json":
        payload = {
            "dry_run": result.dry_run,
            "copied": result.copied_count,
            "skipped_existing": result.skipped_existing,
            "skipped_invalid": result.skipped_invalid,
            "backup_manifest": (str(result.backup_manifest) if result.backup_manifest else None),
            "entries": [
                {
                    "artefact": e.artefact,
                    "source": str(e.source),
                    "target": str(e.target),
                    "status": e.status,
                    "classification": e.classification.value,
                }
                for e in result.entries
            ],
        }
        print(_json.dumps(payload, indent=2, sort_keys=True))
    else:
        mode = "dry-run" if result.dry_run else "applied"
        print(
            f"Consultation migration [{mode}]: "
            f"copied={result.copied_count} "
            f"skipped_existing={result.skipped_existing} "
            f"skipped_invalid={result.skipped_invalid}"
        )
        if result.backup_manifest:
            print(f"Backup manifest: {result.backup_manifest}")
    return 0


def _resolve_scorecard_policy(
    project_root: object = None,
) -> "dict[str, object]":
    """Load policy_scorecard.v1.json with optional workspace override."""
    from pathlib import Path as _Path

    from ao_kernel.config import load_with_override

    workspace: _Path | None = None
    if project_root is not None:
        workspace = _Path(str(project_root)).expanduser().resolve() / ".ao"
    return load_with_override(
        "policies",
        "policy_scorecard.v1.json",
        workspace=workspace,
    )


def _cmd_scorecard_emit(args: argparse.Namespace) -> int:
    """Run benchmarks + write scorecard. Policy-agnostic (plan §3.8)."""
    import os
    import subprocess
    from pathlib import Path as _Path

    from ao_kernel._internal.scorecard.collector import (
        DEFAULT_OUTPUT_FILENAME,
        resolve_output_path,
    )

    output = _Path(args.output_path).expanduser().resolve() if args.output_path else resolve_output_path()
    env = os.environ.copy()
    env["AO_SCORECARD_OUTPUT"] = str(output)
    cmd = ["pytest", "tests/benchmarks/", "-q"]
    if args.pytest_args:
        cmd.extend(args.pytest_args)
    try:
        completed = subprocess.run(cmd, env=env, check=False)
    except FileNotFoundError:
        print(
            "pytest binary not found; install the [dev] extra or run in a virtualenv.",
            file=sys.stderr,
        )
        return 2
    # Emit is advisory: even on pytest failure the scorecard is written by
    # the pytest_sessionfinish hook (failure diagnostic carried in content).
    if not output.is_file():
        print(
            f"scorecard output not produced at {output} (check benchmark session logs).",
            file=sys.stderr,
        )
        return completed.returncode or 3
    print(f"scorecard emitted: {output}")
    if completed.returncode != 0:
        print(
            f"pytest exit={completed.returncode}; see benchmark logs above.",
            file=sys.stderr,
        )
    if not args.output_path and output != resolve_output_path():
        print(
            f"(default filename would have been {DEFAULT_OUTPUT_FILENAME})",
            file=sys.stderr,
        )
    return completed.returncode


def _cmd_scorecard_compare(args: argparse.Namespace) -> int:
    """Diff baseline vs head + render + exit per fail_action."""
    import json as _json
    from pathlib import Path as _Path

    from ao_kernel._internal.scorecard.compare import (
        compare_scorecards,
        exit_code_for,
    )
    from ao_kernel._internal.scorecard.render import render_diff

    head_path = _Path(args.head).expanduser().resolve()
    if not head_path.is_file():
        print(f"head scorecard not found: {head_path}", file=sys.stderr)
        return 2
    head = _json.loads(head_path.read_text(encoding="utf-8"))

    baseline = None
    baseline_sha = "_(not found)_"
    if args.baseline:
        baseline_path = _Path(args.baseline).expanduser().resolve()
        if baseline_path.is_file():
            baseline = _json.loads(baseline_path.read_text(encoding="utf-8"))
            baseline_sha = baseline.get("git_sha", "unknown") if isinstance(baseline, dict) else "unknown"
        else:
            print(
                f"baseline scorecard not found at {baseline_path}; rendering diff against empty baseline.",
                file=sys.stderr,
            )

    policy = _resolve_scorecard_policy(getattr(args, "project_root", None))
    # Codex post-impl review SUGGEST absorb: `enabled=false` gates the
    # compare/comment opinion layer. Emit an advisory banner + exit 0
    # without rendering the full diff so downstream stages know the
    # output is intentionally empty.
    if not bool(policy.get("enabled", True)):
        print("<!-- ao-scorecard -->")
        print(
            "### 📊 Benchmark Scorecard\n\n_Scorecard compare disabled via `policy_scorecard.enabled=false`._",
        )
        print(
            "INFO: policy_scorecard.enabled=false; compare skipped.",
            file=sys.stderr,
        )
        return 0
    diff = compare_scorecards(baseline, head, policy=policy)
    rendered = render_diff(diff, head_scorecard=head)
    print(rendered)
    if diff.has_regression and policy.get("fail_action") == "warn":
        print(
            f"WARN: regression detected (baseline={baseline_sha}) — bundled policy is warn-only; exit 0.",
            file=sys.stderr,
        )
    return exit_code_for(diff)


def _cmd_scorecard_render(args: argparse.Namespace) -> int:
    """Render markdown only — no policy evaluation, always exit 0."""
    import json as _json
    from pathlib import Path as _Path

    from ao_kernel._internal.scorecard.compare import compare_scorecards
    from ao_kernel._internal.scorecard.render import render_diff

    head_path = _Path(args.input).expanduser().resolve()
    if not head_path.is_file():
        print(f"input scorecard not found: {head_path}", file=sys.stderr)
        return 2
    head = _json.loads(head_path.read_text(encoding="utf-8"))

    baseline = None
    if args.baseline:
        baseline_path = _Path(args.baseline).expanduser().resolve()
        if baseline_path.is_file():
            baseline = _json.loads(baseline_path.read_text(encoding="utf-8"))

    diff = compare_scorecards(baseline, head)
    print(render_diff(diff, head_scorecard=head))
    return 0


def _cmd_scorecard_post_comment(args: argparse.Namespace) -> int:
    """CI-side sentinel-sticky upsert via gh; advisory-only (exit 0).

    Codex post-impl review SUGGEST absorb: honour
    ``policy_scorecard.enabled`` and ``policy_scorecard.post_pr_comment``.
    When either flag is false, skip the upsert entirely with an
    advisory stderr line. Policy is still resolved so operators can
    override via workspace policy files.
    """
    import os
    from pathlib import Path as _Path

    from ao_kernel._internal.scorecard.post_comment import (
        upsert_sticky_comment,
    )

    policy = _resolve_scorecard_policy(getattr(args, "project_root", None))
    if not bool(policy.get("enabled", True)):
        print(
            "INFO: policy_scorecard.enabled=false; post-comment skipped.",
            file=sys.stderr,
        )
        return 0
    if not bool(policy.get("post_pr_comment", True)):
        print(
            "INFO: policy_scorecard.post_pr_comment=false; upsert skipped.",
            file=sys.stderr,
        )
        return 0

    body_path = _Path(args.body_file).expanduser().resolve()
    if not body_path.is_file():
        print(f"body file not found: {body_path}", file=sys.stderr)
        return 0  # advisory
    body = body_path.read_text(encoding="utf-8")

    repo = args.repo or os.environ.get("GITHUB_REPOSITORY") or ""
    if not repo:
        print(
            "GITHUB_REPOSITORY env var or --repo flag required; skipping post.",
            file=sys.stderr,
        )
        return 0  # advisory

    result = upsert_sticky_comment(
        repo=repo,
        pr=int(args.pr),
        body=body,
        sentinel=args.sentinel,
    )
    print(f"post-comment {result.outcome}: {result.message}")
    return 0  # always advisory


def _cmd_executor_dry_run(args: argparse.Namespace) -> int:
    """PR-C6 CLI: preview a step's effects without side-effects."""
    import json as _json
    from pathlib import Path as _Path

    from ao_kernel.adapters import AdapterRegistry
    from ao_kernel.executor import Executor
    from ao_kernel.workflow.registry import WorkflowRegistry
    from ao_kernel.workflow.run_store import load_run

    project_root = _Path(args.project_root or _Path.cwd()).resolve()

    wreg = WorkflowRegistry()
    wreg.load_bundled()
    wreg.load_workspace(project_root)
    areg = AdapterRegistry()
    areg.load_bundled()
    areg.load_workspace(project_root)

    try:
        record, _ = load_run(project_root, args.run_id)
    except Exception as exc:
        print(f"run not found: {exc}", file=sys.stderr)
        return 1

    try:
        definition = wreg.get(
            record["workflow_id"],
            version=record["workflow_version"],
        )
    except Exception as exc:
        print(f"workflow not resolvable: {exc}", file=sys.stderr)
        return 1

    step_def = next(
        (s for s in definition.steps if s.step_name == args.step_name),
        None,
    )
    if step_def is None:
        print(
            f"step_name={args.step_name!r} not in workflow {record['workflow_id']}@{record['workflow_version']}",
            file=sys.stderr,
        )
        return 1

    executor = Executor(
        workspace_root=project_root,
        workflow_registry=wreg,
        adapter_registry=areg,
    )
    # v3.4.0 #4: actor-aware dispatch extended to non-adapter actors.
    # PR-C6.1 routed only `adapter` through the driver (full envelope
    # + parent_env parity); v3.4.0 #4 lets `system` and `ao-kernel`
    # actors flow through the driver as well so sandbox parent_env
    # derivation matches the real run. `--executor-only` flag still
    # forces executor path for debugging / backward-compat.
    executor_only = getattr(args, "executor_only", False)
    use_driver = (not executor_only) and step_def.actor in ("adapter", "system", "ao-kernel")
    if use_driver:
        from ao_kernel.executor.multi_step_driver import MultiStepDriver

        driver = MultiStepDriver(
            workspace_root=project_root,
            registry=wreg,
            adapter_registry=areg,
            executor=executor,
        )
        result = driver.dry_run_step(
            args.run_id,
            args.step_name,
            attempt=args.attempt,
        )
    else:
        result = executor.dry_run_step(
            args.run_id,
            step_def,
            attempt=args.attempt or 1,
        )
    if args.format == "json":
        out = {
            "predicted_events": [{"kind": k, "payload": dict(p)} for k, p in result.predicted_events],
            "policy_violations": list(result.policy_violations),
            "simulated_budget_after": dict(result.simulated_budget_after),
            "simulated_outputs": dict(result.simulated_outputs),
        }
        print(_json.dumps(out, indent=2, sort_keys=True))
    else:
        print(
            f"predicted_events: {len(result.predicted_events)}\n"
            f"policy_violations: {len(result.policy_violations)}\n"
            f"simulated_outputs: {len(result.simulated_outputs)}"
        )
    return 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ao-kernel",
        description="Governed AI orchestration runtime",
    )
    parser.add_argument(
        "--workspace-root",
        default=None,
        help="Override project root or explicit .ao workspace directory",
    )

    sub = parser.add_subparsers(dest="command")

    sub.add_parser("version", help="Print version")

    sub.add_parser("init", help="Create .ao/ workspace")

    migrate_p = sub.add_parser("migrate", help="Run workspace migration")
    migrate_p.add_argument("--dry-run", action="store_true", help="Only report, no changes")
    migrate_p.add_argument("--backup", action="store_true", help="Backup files before mutation")

    sub.add_parser("doctor", help="Workspace health check")

    # Evidence subcommands (PR-A5)
    ev_p = sub.add_parser("evidence", help="Evidence timeline + replay + manifest")
    ev_sub = ev_p.add_subparsers(dest="evidence_command")

    tl_p = ev_sub.add_parser("timeline", help="Show evidence event timeline")
    tl_p.add_argument("--run", dest="run_id", required=True, help="Run ID (UUID)")
    tl_p.add_argument("--format", choices=["table", "json"], default="table")
    tl_p.add_argument("--filter-kind", default=None, help="Comma-separated kind filter")
    tl_p.add_argument("--filter-actor", default=None, help="Actor filter")
    tl_p.add_argument("--limit", type=int, default=None, help="Last N events")

    rp_p = ev_sub.add_parser("replay", help="Replay event stream (inspect/dry-run)")
    rp_p.add_argument("--run", dest="run_id", required=True, help="Run ID (UUID)")
    rp_p.add_argument("--mode", choices=["inspect", "dry-run"], default="inspect")

    gm_p = ev_sub.add_parser("generate-manifest", help="Generate SHA-256 manifest")
    gm_p.add_argument("--run", dest="run_id", required=True, help="Run ID (UUID)")

    vm_p = ev_sub.add_parser("verify-manifest", help="Verify SHA-256 manifest")
    vm_p.add_argument("--run", dest="run_id", required=True, help="Run ID (UUID)")
    vm_p.add_argument("--generate-if-missing", action="store_true", help="Generate manifest first if absent")

    mcp_p = sub.add_parser("mcp", help="MCP server commands")
    mcp_sub = mcp_p.add_subparsers(dest="mcp_command")
    serve_p = mcp_sub.add_parser("serve", help="Start MCP server")
    serve_p.add_argument("--transport", choices=["stdio", "http"], default="stdio", help="Transport (default: stdio)")
    serve_p.add_argument("--host", default="127.0.0.1", help="HTTP bind host (default: 127.0.0.1)")
    serve_p.add_argument("--port", type=int, default=8080, help="HTTP port (default: 8080)")

    repo_p = sub.add_parser("repo", help="Repository intelligence commands")
    repo_sub = repo_p.add_subparsers(dest="repo_command")
    scan_p = repo_sub.add_parser("scan", help="Scan repository and write read-only repo-intelligence artifacts")
    scan_p.add_argument(
        "--project-root",
        default=".",
        help="Repository root to scan (default: current directory)",
    )
    scan_p.add_argument(
        "--output",
        choices=["text", "json"],
        default="text",
        help="Command output format (default: text)",
    )

    # Metrics subcommands (PR-B5)
    metrics_p = sub.add_parser(
        "metrics",
        help="Prometheus textfile export + debug query",
    )
    metrics_sub = metrics_p.add_subparsers(dest="metrics_command")

    export_p = metrics_sub.add_parser(
        "export",
        help="Emit cumulative Prometheus textfile",
    )
    export_p.add_argument(
        "--format",
        choices=["prometheus"],
        default="prometheus",
        help="Output format (only 'prometheus' for textfile mode)",
    )
    export_p.add_argument(
        "--output",
        default=None,
        help="File path for atomic write; omit for stdout",
    )

    # PR-B5 C3b: debug-query — non-Prometheus JSON query surface.
    from ao_kernel._internal.metrics.debug_query import parse_iso8601_strict

    debug_p = metrics_sub.add_parser(
        "debug-query",
        help=("Ad-hoc JSON query over evidence events (never Prometheus textfile; for operator debugging)"),
    )
    debug_p.add_argument(
        "--since",
        type=parse_iso8601_strict,
        default=None,
        help=("Filter events at or after this ISO-8601 timestamp; timezone required (use 'Z' or '+HH:MM')"),
    )
    debug_p.add_argument(
        "--run",
        dest="run",
        default=None,
        help="Limit to a single run_id",
    )
    debug_p.add_argument(
        "--format",
        choices=["json"],
        default="json",
        help="Output format (only 'json' for debug-query)",
    )
    debug_p.add_argument(
        "--output",
        default=None,
        help="File path for atomic write; omit for stdout",
    )

    coordination_p = sub.add_parser(
        "coordination",
        help="Coordination claim visibility",
    )
    coordination_sub = coordination_p.add_subparsers(dest="coordination_command")
    coordination_status_p = coordination_sub.add_parser(
        "status",
        help="Show current claim ownership / grace / takeover snapshot",
    )
    coordination_status_p.add_argument(
        "--format",
        choices=["text", "json"],
        default="text",
        help="Output format (default: text)",
    )
    coordination_status_p.add_argument(
        "--output",
        default=None,
        help="File path for atomic write; omit for stdout",
    )
    coordination_takeover_p = coordination_sub.add_parser(
        "takeover",
        help="Take over a past-grace coordination claim for a new owner",
    )
    coordination_takeover_p.add_argument(
        "--resource-id",
        required=True,
        help="Exact claim resource_id to take over",
    )
    coordination_takeover_p.add_argument(
        "--owner-tag",
        required=True,
        help="New owner tag / agent id that will hold the claim",
    )
    coordination_takeover_p.add_argument(
        "--format",
        choices=["text", "json"],
        default="text",
        help="Output format (default: text)",
    )
    coordination_takeover_p.add_argument(
        "--output",
        default=None,
        help="File path for atomic write; omit for stdout",
    )

    # Policy-sim subcommand (PR-B4)
    policy_sim_p = sub.add_parser(
        "policy-sim",
        help="Dry-run simulation of proposed policy changes",
    )
    policy_sim_sub = policy_sim_p.add_subparsers(dest="policy_sim_command")

    run_p = policy_sim_sub.add_parser(
        "run",
        help="Evaluate scenarios against baseline + proposed policy sets",
    )
    run_p.add_argument(
        "--scenarios",
        default=None,
        help="Scenario file or directory; omit for bundled fixtures",
    )
    # PR-C5: exactly one of --proposed-policies | --proposed-patches
    # is required. The mutex is enforced at the parser level so the
    # handler never sees both together.
    _proposed_group = run_p.add_mutually_exclusive_group(required=True)
    _proposed_group.add_argument(
        "--proposed-policies",
        default=None,
        help="Directory containing proposed policy JSON files",
    )
    _proposed_group.add_argument(
        "--proposed-patches",
        default=None,
        help=("Directory containing RFC 7396 JSON Merge Patch files (<name>.v1.patch.json → patches <name>.v1.json)"),
    )
    run_p.add_argument(
        "--baseline-source",
        choices=["bundled", "workspace_override", "explicit"],
        default="bundled",
        help="Baseline assembly source (default: bundled)",
    )
    run_p.add_argument(
        "--baseline-overrides",
        default=None,
        help="Directory for baseline overrides (used with --baseline-source=explicit)",
    )
    run_p.add_argument(
        "--format",
        choices=["json", "text"],
        default="json",
        help="Report format (default: json)",
    )
    run_p.add_argument(
        "--output",
        default=None,
        help="File path for atomic write; omit for stdout",
    )
    run_p.add_argument(
        "--enable-host-fs-probes",
        action="store_true",
        help="Opt-in host-FS-dependent probes (default off; deferred in v1)",
    )
    run_p.add_argument(
        "--project-root",
        default=None,
        help="Project root for adapter discovery (default: cwd)",
    )

    # PR-C6: executor dry-run subcommand
    executor_p = sub.add_parser(
        "executor",
        help="Executor primitives (dry-run preview, etc.)",
    )
    executor_sub = executor_p.add_subparsers(dest="executor_command")
    dry_run_p = executor_sub.add_parser(
        "dry-run",
        help="Preview a step's predicted effects without side-effects",
    )
    dry_run_p.add_argument(
        "run_id",
        help="Run identifier (UUID) from a seeded workflow run",
    )
    dry_run_p.add_argument(
        "step_name",
        help="Step name (must be part of the pinned workflow definition)",
    )
    dry_run_p.add_argument(
        "--attempt",
        type=int,
        default=None,
        help=(
            "Attempt number for retry-aware dry-run. When omitted, the "
            "driver derives the next legal attempt; when supplied, must "
            "match that value (PR-C6.1)."
        ),
    )
    dry_run_p.add_argument(
        "--executor-only",
        action="store_true",
        help=(
            "PR-C6.1 debug opt-out: force Executor.dry_run_step directly "
            "instead of the actor-aware dispatch. Useful for debugging "
            "driver-layer derivation gaps or for actors that don't have "
            "driver parity yet (non-adapter actors route here by default)."
        ),
    )
    dry_run_p.add_argument(
        "--format",
        choices=["json", "text"],
        default="json",
        help="Report format (default: json)",
    )
    dry_run_p.add_argument(
        "--project-root",
        default=None,
        help="Project root (default: cwd)",
    )

    # v3.4.0 #1: cost subcommand — reconciler daemon
    cost_p = sub.add_parser(
        "cost",
        help="Cost runtime ops (reconciliation daemon, etc.)",
    )
    cost_sub = cost_p.add_subparsers(dest="cost_command")
    reconcile_p = cost_sub.add_parser(
        "reconcile",
        help=(
            "Scan the spend ledger for orphan entries (ledger present "
            "without a matching cost_reconciled marker) and stamp the "
            "missing markers. Idempotent + cursor-based; safe to run "
            "repeatedly (e.g. via cron)."
        ),
    )
    reconcile_p.add_argument(
        "--dry-run",
        action="store_true",
        help=(
            "Report orphans without stamping markers or advancing the "
            "cursor. Useful to preview pending recovery before a real "
            "pass."
        ),
    )
    reconcile_p.add_argument(
        "--cursor-reset",
        action="store_true",
        help=(
            "Ignore any existing reconciler cursor and scan the entire "
            "ledger from offset 0. The cursor is rewritten at the end "
            "of a non-dry-run pass."
        ),
    )
    reconcile_p.add_argument(
        "--output",
        choices=["json", "human"],
        default="human",
        help="Output format (default: human)",
    )
    reconcile_p.add_argument(
        "--project-root",
        default=None,
        help="Project root (default: cwd)",
    )

    # v3.5 D1: consultation migrate subcommand
    consult_p = sub.add_parser(
        "consultation",
        help="Consultation (CNS) artefact management",
    )
    consult_sub = consult_p.add_subparsers(dest="consultation_command")
    migrate_cons_p = consult_sub.add_parser(
        "migrate",
        help=(
            "Copy-forward legacy `.cache/...` consultation artefacts to "
            "the canonical `.ao/consultations/` layout. Idempotent + "
            "reversible (migration manifest written under "
            "`.ao/consultations/.migration_backup/`)."
        ),
    )
    migrate_cons_p.add_argument(
        "--dry-run",
        action="store_true",
        help="Report what WOULD be copied without touching disk.",
    )
    migrate_cons_p.add_argument(
        "--force",
        action="store_true",
        help="Overwrite pre-existing canonical files (non-destructive by default).",
    )
    migrate_cons_p.add_argument(
        "--include-invalid",
        action="store_true",
        help="Copy files flagged INVALID_JSON anyway (default: skipped).",
    )
    migrate_cons_p.add_argument(
        "--output",
        choices=["json", "human"],
        default="human",
    )
    migrate_cons_p.add_argument(
        "--project-root",
        default=None,
        help="Project root (default: cwd)",
    )

    # v3.5 D2a: consultation archive subcommand
    archive_cons_p = consult_sub.add_parser(
        "archive",
        help=(
            "Scan CNS corpus and archive into "
            "`.ao/evidence/consultations/<CNS-ID>/` "
            "(snapshots + events + resolution record + integrity "
            "manifest). Idempotent — repeat runs skip duplicate events."
        ),
    )
    archive_cons_p.add_argument(
        "--dry-run",
        action="store_true",
        help="Report scope without touching disk.",
    )
    archive_cons_p.add_argument(
        "--renormalize",
        action="store_true",
        help=(
            "Force resolution record rebuild even if digest matches. "
            "Use after normalizer_version upgrade to backfill historical "
            "CNS records."
        ),
    )
    archive_cons_p.add_argument(
        "--verify",
        action="store_true",
        help=(
            "Verify integrity manifests for all existing evidence "
            "directories under `.ao/evidence/consultations/`. No "
            "snapshot or record mutations; non-zero exit on any "
            "digest mismatch or missing file."
        ),
    )
    archive_cons_p.add_argument(
        "--output",
        choices=["json", "human"],
        default="human",
    )
    archive_cons_p.add_argument(
        "--project-root",
        default=None,
    )

    # v3.5 D2b: consultation promote subcommand
    promote_cons_p = consult_sub.add_parser(
        "promote",
        help=(
            "Promote resolved AGREE/PARTIAL consultations from the "
            "evidence archive into canonical_decisions.v1.json. "
            "Opt-in via policy flag `promotion.enabled=true`; --force "
            "bypasses the flag only (integrity + eligibility still "
            "enforced)."
        ),
    )
    promote_cons_p.add_argument(
        "--dry-run",
        action="store_true",
        help="Count what WOULD be promoted without touching the store.",
    )
    promote_cons_p.add_argument(
        "--force",
        action="store_true",
        help=("Bypass the policy.promotion.enabled gate for this run (integrity + eligibility still enforced)."),
    )
    promote_cons_p.add_argument(
        "--output",
        choices=["json", "human"],
        default="human",
    )
    promote_cons_p.add_argument(
        "--project-root",
        default=None,
    )

    # v3.4.0 #3: cost compact-markers subcommand
    compact_p = cost_sub.add_parser(
        "compact-markers",
        help=(
            "Archive `cost_reconciled` markers for a run (or all "
            "terminal runs) to .ao/cost/markers-archive/{run_id}.jsonl "
            "and clear the in-record list. Keeps state.v1.json lean "
            "on long-lived workspaces. Idempotent (empty → no-op)."
        ),
    )
    compact_p.add_argument(
        "--run-id",
        default=None,
        help=("Compact a single run by id. Mutually exclusive with --all-terminal."),
    )
    compact_p.add_argument(
        "--all-terminal",
        action="store_true",
        help=("Compact every on-disk run in a terminal state (completed / failed / cancelled)."),
    )
    compact_p.add_argument(
        "--dry-run",
        action="store_true",
        help="Report scope without mutating anything.",
    )
    compact_p.add_argument(
        "--output",
        choices=["json", "human"],
        default="human",
        help="Output format (default: human)",
    )
    compact_p.add_argument(
        "--project-root",
        default=None,
        help="Project root (default: cwd)",
    )

    # v3.5 D3: scorecard subcommand
    scorecard_p = sub.add_parser(
        "scorecard",
        help=("Dev scorecard for PR-B7 benchmarks: emit, compare vs main baseline, render markdown, post-comment."),
    )
    scorecard_sub = scorecard_p.add_subparsers(dest="scorecard_command")

    emit_sc_p = scorecard_sub.add_parser(
        "emit",
        help=("Run tests/benchmarks/ via pytest and write benchmark_scorecard.v1.json. Policy-agnostic."),
    )
    emit_sc_p.add_argument(
        "--output",
        dest="output_path",
        default=None,
        help=("Output path (default: $AO_SCORECARD_OUTPUT or ./benchmark_scorecard.v1.json)."),
    )
    emit_sc_p.add_argument(
        "pytest_args",
        nargs=argparse.REMAINDER,
        help="Extra arguments forwarded to pytest after `--`.",
    )

    compare_sc_p = scorecard_sub.add_parser(
        "compare",
        help=("Diff baseline vs head scorecard, render markdown, exit per policy_scorecard.fail_action."),
    )
    compare_sc_p.add_argument(
        "--baseline",
        default=None,
        help="Path to baseline scorecard JSON.",
    )
    compare_sc_p.add_argument(
        "--head",
        required=True,
        help="Path to head scorecard JSON.",
    )
    compare_sc_p.add_argument(
        "--project-root",
        default=None,
        help="Project root (optional; resolves workspace policy override).",
    )

    render_sc_p = scorecard_sub.add_parser(
        "render",
        help="Render diff markdown to stdout (no policy, always exit 0).",
    )
    render_sc_p.add_argument(
        "--input",
        required=True,
        help="Path to head scorecard JSON.",
    )
    render_sc_p.add_argument(
        "--baseline",
        default=None,
        help="Optional baseline scorecard JSON for delta columns.",
    )

    post_sc_p = scorecard_sub.add_parser(
        "post-comment",
        help=("Upsert a sentinel-tagged sticky comment on a PR. Advisory-only — exit 0 on any failure."),
    )
    post_sc_p.add_argument(
        "--pr",
        required=True,
        type=int,
        help="PR number.",
    )
    post_sc_p.add_argument(
        "--body-file",
        required=True,
        help="Path to rendered markdown.",
    )
    post_sc_p.add_argument(
        "--sentinel",
        required=True,
        help=(
            "HTML sentinel string the body must contain. "
            "Existing comments that include this string are PATCHed "
            "instead of posted fresh."
        ),
    )
    post_sc_p.add_argument(
        "--repo",
        default=None,
        help="`owner/name` slug (default: $GITHUB_REPOSITORY).",
    )
    post_sc_p.add_argument(
        "--project-root",
        default=None,
        help="Project root (optional; resolves workspace policy override).",
    )

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(sys.argv[1:] if argv is None else argv)

    dispatch = {
        "version": _cmd_version,
        "init": _cmd_init,
        "migrate": _cmd_migrate,
        "doctor": _cmd_doctor,
    }

    cmd = args.command
    if cmd is None:
        parser.print_help()
        return 0

    # Evidence subcommand (PR-A5)
    if cmd == "evidence":
        from ao_kernel._internal.evidence.cli_handlers import (
            cmd_generate_manifest,
            cmd_replay,
            cmd_timeline,
            cmd_verify_manifest,
        )

        ev_dispatch = {
            "timeline": cmd_timeline,
            "replay": cmd_replay,
            "generate-manifest": cmd_generate_manifest,
            "verify-manifest": cmd_verify_manifest,
        }
        ev_cmd = getattr(args, "evidence_command", None)
        handler = ev_dispatch.get(ev_cmd) if ev_cmd else None
        if handler is None:
            print("Usage: ao-kernel evidence {timeline|replay|generate-manifest|verify-manifest}")
            return 1
        return handler(args)

    # MCP subcommand
    if cmd == "mcp":
        mcp_cmd = getattr(args, "mcp_command", None)
        if mcp_cmd == "serve":
            return _cmd_mcp_serve(args)
        from ao_kernel.i18n import msg

        print(msg("usage_mcp_serve"))
        return 1

    # Repo-intelligence subcommand (RI-1)
    if cmd == "repo":
        repo_cmd = getattr(args, "repo_command", None)
        if repo_cmd == "scan":
            return _cmd_repo_scan(args)
        print("Usage: ao-kernel repo scan [--project-root PATH] [--output {text,json}]", file=sys.stderr)
        return 1

    # Executor subcommand (PR-C6)
    if cmd == "executor":
        ex_cmd = getattr(args, "executor_command", None)
        if ex_cmd == "dry-run":
            return _cmd_executor_dry_run(args)
        print("Usage: ao-kernel executor {dry-run}", file=sys.stderr)
        return 1

    # Policy-sim subcommand (PR-B4)
    if cmd == "policy-sim":
        from ao_kernel._internal.policy_sim.cli_handlers import (
            cmd_policy_sim_run,
        )

        ps_cmd = getattr(args, "policy_sim_command", None)
        if ps_cmd == "run":
            return cmd_policy_sim_run(args)
        print("Usage: ao-kernel policy-sim run [options]", file=sys.stderr)
        return 1

    # Consultation subcommand (v3.5 D1 migrate + D2a archive + D2b promote)
    if cmd == "consultation":
        cns_cmd = getattr(args, "consultation_command", None)
        if cns_cmd == "migrate":
            return _cmd_consultation_migrate(args)
        if cns_cmd == "archive":
            return _cmd_consultation_archive(args)
        if cns_cmd == "promote":
            return _cmd_consultation_promote(args)
        print(
            "Usage: ao-kernel consultation {migrate|archive|promote}",
            file=sys.stderr,
        )
        return 1

    # Cost subcommand (v3.4.0 #1 reconciler + #3 compact-markers)
    if cmd == "cost":
        cost_cmd = getattr(args, "cost_command", None)
        if cost_cmd == "reconcile":
            return _cmd_cost_reconcile(args)
        if cost_cmd == "compact-markers":
            return _cmd_cost_compact_markers(args)
        print(
            "Usage: ao-kernel cost {reconcile|compact-markers}",
            file=sys.stderr,
        )
        return 1

    # Scorecard subcommand (v3.5 D3)
    if cmd == "scorecard":
        sc_cmd = getattr(args, "scorecard_command", None)
        if sc_cmd == "emit":
            return _cmd_scorecard_emit(args)
        if sc_cmd == "compare":
            return _cmd_scorecard_compare(args)
        if sc_cmd == "render":
            return _cmd_scorecard_render(args)
        if sc_cmd == "post-comment":
            return _cmd_scorecard_post_comment(args)
        print(
            "Usage: ao-kernel scorecard {emit|compare|render|post-comment}",
            file=sys.stderr,
        )
        return 1

    # Metrics subcommand (PR-B5)
    if cmd == "metrics":
        from ao_kernel._internal.metrics.cli_handlers import (
            cmd_metrics_export,
        )
        from ao_kernel._internal.metrics.debug_query import (
            cmd_metrics_debug_query,
        )

        metrics_cmd = getattr(args, "metrics_command", None)
        metrics_dispatch = {
            "export": cmd_metrics_export,
            "debug-query": cmd_metrics_debug_query,
        }
        handler = metrics_dispatch.get(metrics_cmd) if metrics_cmd else None
        if handler is None:
            print("Usage: ao-kernel metrics {export|debug-query}")
            return 1
        return handler(args)

    if cmd == "coordination":
        from ao_kernel._internal.coordination.cli_handlers import (
            cmd_coordination_status,
            cmd_coordination_takeover,
        )

        coordination_cmd = getattr(args, "coordination_command", None)
        if coordination_cmd == "status":
            return cmd_coordination_status(args)
        if coordination_cmd == "takeover":
            return cmd_coordination_takeover(args)
        print("Usage: ao-kernel coordination {status|takeover}", file=sys.stderr)
        return 1

    handler = dispatch.get(cmd)
    if handler is None:
        parser.print_help()
        return 1

    return handler(args)


if __name__ == "__main__":
    raise SystemExit(main())
