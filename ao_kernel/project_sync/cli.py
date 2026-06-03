"""CLI handlers for ``ao-kernel project ...`` subcommands.

The CLI is intentionally thin — it parses args, builds clients, calls
into the pure modules, and prints a deterministic JSON report. Heavy
logic lives in the rest of ``ao_kernel.project_sync``.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Any

from ao_kernel.project_sync.derivers import FieldDeriver, derive_all_fields
from ao_kernel.project_sync.drift_healer import DriftHealer, DriftReport
from ao_kernel.project_sync.errors import ManifestDriftError, ProjectSyncError
from ao_kernel.project_sync.issues import IssueClient, IssueRecord
from ao_kernel.project_sync.label_migrator import LabelMigrator, MigrationReport
from ao_kernel.project_sync.manifest import ProjectionManifest
from ao_kernel.project_sync.project_v2 import ProjectV2Client
from ao_kernel.project_sync.slice_adder import (
    AddSliceRequest,
    SliceAdder,
)

_DEFAULT_MANIFEST = ".claude/plans/v5_issue_projection.v1.json"


def add_project_subparser(sub: "argparse._SubParsersAction[Any]") -> None:
    """Register the ``project`` subparser group on the main CLI."""
    project_p = sub.add_parser("project", help="GitHub Projects v2 mirror sync")
    project_sub = project_p.add_subparsers(dest="project_command")

    sync_p = project_sub.add_parser("sync", help="Full bidirectional sync (manifest -> board)")
    _add_common_args(sync_p)
    sync_p.add_argument("--label", default="mirror:authority", help="Label scoping which issues to sync")
    sync_p.set_defaults(func=_cmd_sync)

    drift_p = project_sub.add_parser("drift", help="Check drift between manifest and board")
    _add_common_args(drift_p)
    drift_p.add_argument("--label", default="mirror:authority", help="Label scoping which issues to scan")
    drift_p.add_argument("--strict", action="store_true", help="Exit 1 if drift detected")
    drift_p.set_defaults(func=_cmd_drift)

    add_slice_p = project_sub.add_parser("add-slice", help="Atomic new-slice add (issue + board + fields)")
    _add_common_args(add_slice_p)
    add_slice_p.add_argument("--epic", required=True, help="Epic id (e.g. 1, 2, P0)")
    add_slice_p.add_argument("--slice-id", required=True, help="Slice id (e.g. E-1-3)")
    add_slice_p.add_argument("--title", required=True, help="Issue title")
    add_slice_p.add_argument("--risk", required=True, choices=["low", "normal", "high", "critical"])
    add_slice_p.add_argument("--plan-ref", required=True, help="Plan doc path or PR url")
    add_slice_p.add_argument("--consensus", required=True, choices=["2-way", "3-way", "pending", "AGREE-merged"])
    add_slice_p.add_argument(
        "--guard",
        default="none",
        choices=["live_adapter", "support_widening", "production_platform_claim", "none"],
    )
    add_slice_p.add_argument("--depends-on", default="", help="Comma-separated issue numbers")
    add_slice_p.add_argument("--estimate-days", type=float, default=None)
    add_slice_p.add_argument("--dry-run", action="store_true", help="Plan only; no GitHub mutations")
    add_slice_p.set_defaults(func=_cmd_add_slice)

    field_set_p = project_sub.add_parser("field-set", help="Set a single project field on an item")
    _add_common_args(field_set_p)
    field_set_p.add_argument("--item", required=True, type=int, help="Issue number")
    field_set_p.add_argument("--field", required=True, help="Project field name (e.g. Risk)")
    field_set_p.add_argument("--value", required=True, help="Field value to set")
    field_set_p.set_defaults(func=_cmd_field_set)

    label_p = project_sub.add_parser("label-cleanup", help="Migrate convention labels to project fields")
    _add_common_args(label_p)
    label_p.add_argument("--label", default="mirror:authority", help="Scope label for issues to clean up")
    label_p.add_argument("--dry-run", action="store_true", help="Report only; no label drop")
    label_p.set_defaults(func=_cmd_label_cleanup)

    from_pr_p = project_sub.add_parser("from-pr", help="Derive a slice from a PR + add to board")
    _add_common_args(from_pr_p)
    from_pr_p.add_argument("pr_number", type=int, help="PR number")
    from_pr_p.add_argument("--dry-run", action="store_true", help="Plan only; no GitHub mutations")
    from_pr_p.set_defaults(func=_cmd_from_pr)


def _add_common_args(p: argparse.ArgumentParser) -> None:
    p.add_argument(
        "--manifest",
        default=_DEFAULT_MANIFEST,
        help=f"Projection manifest path (default: {_DEFAULT_MANIFEST})",
    )
    p.add_argument("--repo", default=None, help="GitHub repo (owner/name); default uses gh context")
    p.add_argument("--gh-binary", default=None, help="Override gh binary path")
    p.add_argument(
        "--output",
        choices=["text", "json"],
        default="text",
        help="Output format (default: text)",
    )


def dispatch(args: argparse.Namespace) -> int:
    """Top-level dispatcher; the public CLI wires this in ``cli.py``."""
    func = getattr(args, "func", None)
    if func is None:
        print("project: missing subcommand (try 'sync', 'drift', 'add-slice')", file=sys.stderr)
        return 2
    try:
        return int(func(args))
    except ManifestDriftError as exc:
        print(f"project: drift detected: {exc}", file=sys.stderr)
        return 1
    except ProjectSyncError as exc:
        print(f"project: {exc}", file=sys.stderr)
        return 1


def _build_clients(args: argparse.Namespace) -> tuple[IssueClient, ProjectV2Client, ProjectionManifest]:
    manifest_path = Path(args.manifest).expanduser().resolve()
    manifest = ProjectionManifest.load(manifest_path)
    issues = IssueClient(gh_binary=getattr(args, "gh_binary", None), repo=getattr(args, "repo", None))
    project = ProjectV2Client(gh_binary=getattr(args, "gh_binary", None))
    return issues, project, manifest


def _emit(args: argparse.Namespace, payload: dict[str, Any]) -> None:
    if args.output == "json":
        print(json.dumps(payload, indent=2, sort_keys=True))
        return
    summary = payload.get("summary", {})
    print(f"project {payload.get('command', '?')} complete")
    for key, value in summary.items():
        print(f"  {key}: {value}")


def _cmd_sync(args: argparse.Namespace) -> int:
    issues_client, project_client, manifest = _build_clients(args)
    fetched = issues_client.list_issues_with_label(args.label, limit=200)
    healer = DriftHealer(
        issue_client=issues_client,
        project_client=project_client,
        manifest=manifest,
    )
    report = healer.heal(fetched)
    _emit(
        args,
        _sync_payload(
            report,
            scanned=len(fetched),
            manifest_digest=manifest.digest(),
        ),
    )
    return 0


def _cmd_drift(args: argparse.Namespace) -> int:
    issues_client, project_client, manifest = _build_clients(args)
    fetched = issues_client.list_issues_with_label(args.label, limit=200)
    healer = DriftHealer(
        issue_client=issues_client,
        project_client=project_client,
        manifest=manifest,
    )
    report = healer.check(fetched, strict=args.strict)
    _emit(args, _drift_payload("drift", report, scanned=len(fetched)))
    return 1 if (args.strict and report.has_drift) else 0


def _const_pinned_envelope() -> dict[str, Any]:
    """Schema-required envelope (guard flags, register authority, write flag).

    Every report this module emits ships the same const-pinned envelope
    so the matching schema can validate without per-command branching.
    """
    return {
        "guard_flags": {
            "live_adapter_execution": False,
            "support_widening": False,
            "production_platform_claim": False,
        },
        "register_authority": "evidence_record_only",
        "github_write_authorized": True,
    }


def _cmd_add_slice(args: argparse.Namespace) -> int:
    issues_client, project_client, manifest = _build_clients(args)
    depends = [int(n) for n in args.depends_on.split(",") if n.strip()] if args.depends_on else []
    request = AddSliceRequest(
        epic=args.epic,
        slice_id=args.slice_id,
        title=args.title,
        risk=args.risk,
        plan_ref=args.plan_ref,
        consensus=args.consensus,
        guard=args.guard,
        depends_on=depends,
        estimate_days=args.estimate_days,
    )
    adder = SliceAdder(
        issue_client=issues_client,
        project_client=project_client,
        manifest=manifest,
    )
    result = adder.add(request, dry_run=args.dry_run)
    payload: dict[str, Any] = {
        "command": "add-slice",
        "dry_run": bool(args.dry_run),
        "summary": {
            "issue_number": result.issue.number,
            "item_id": result.item_id,
            "fields_set": ",".join(result.fields_set),
            "manifest_digest": result.manifest_digest,
        },
    }
    _emit(args, payload)
    return 0


def _cmd_field_set(args: argparse.Namespace) -> int:
    issues_client, project_client, manifest = _build_clients(args)
    project_node_id = manifest.project_node_id()
    if project_node_id is None:
        print("project field-set: manifest has no runtime project board", file=sys.stderr)
        return 1
    issue = issues_client.get_issue(args.item)
    fields_map = project_client.fetch_fields(project_node_id)
    field_obj = fields_map.get(args.field)
    if field_obj is None:
        print(f"project field-set: unknown field {args.field!r}", file=sys.stderr)
        return 1
    item_id = project_client.find_item_for_issue(project_node_id, issue.node_id)
    if item_id is None:
        item_id = project_client.add_issue_to_project(project_node_id, issue.node_id)
    project_client.set_field_value(
        project_node_id=project_node_id,
        item_id=item_id,
        field=field_obj,
        value=args.value,
    )
    _emit(
        args,
        {
            "command": "field-set",
            "summary": {
                "issue_number": issue.number,
                "field": args.field,
                "value": args.value,
            },
        },
    )
    return 0


def _cmd_label_cleanup(args: argparse.Namespace) -> int:
    issues_client, project_client, manifest = _build_clients(args)
    fetched = issues_client.list_issues_with_label(args.label, limit=200)
    migrator = LabelMigrator(
        issue_client=issues_client,
        project_client=project_client,
        manifest=manifest,
    )
    report = migrator.migrate(fetched, dry_run=args.dry_run)
    _emit(args, _migration_payload(report, dry_run=args.dry_run, scanned=len(fetched)))
    return 0


def _cmd_from_pr(args: argparse.Namespace) -> int:
    issues_client, project_client, manifest = _build_clients(args)
    # ``gh pr view`` is a thin lookup we route through IssueClient._run.
    raw = issues_client._run(["pr", "view", str(args.pr_number), "--json", "number,title,body,labels"])
    payload = json.loads(raw)
    fake_issue = IssueRecord(
        number=int(payload.get("number", 0)),
        node_id="",
        title=str(payload.get("title", "")),
        body=str(payload.get("body", "")),
        labels=[lbl.get("name", "") for lbl in payload.get("labels", []) if isinstance(lbl, dict)],
    )
    derived = derive_all_fields(
        fake_issue,
        deriver=FieldDeriver(),
        require_epic=False,
        require_risk=False,
    )
    _emit(
        args,
        {
            "command": "from-pr",
            "dry_run": bool(args.dry_run),
            "summary": {
                "pr_number": args.pr_number,
                "derived_epic": derived.epic or "",
                "derived_risk": derived.risk or "",
                "derived_guard": derived.guard,
                "derived_estimate": derived.estimate if derived.estimate is not None else "",
                "warnings": ",".join(derived.warnings),
            },
        },
    )
    return 0


def _drift_payload(command: str, report: DriftReport, *, scanned: int) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "schema_version": "project-sync-drift-report.v1",
        "command": command,
        "summary": {
            "issues_scanned": scanned,
            "findings": len(report.findings),
            "healed": len(report.healed),
            "warnings": len(report.warnings),
        },
        "findings": [asdict(f) for f in report.findings],
        "healed": [asdict(f) for f in report.healed],
        "warnings": report.warnings,
    }
    payload.update(_const_pinned_envelope())
    return payload


def _sync_payload(report: DriftReport, *, scanned: int, manifest_digest: str) -> dict[str, Any]:
    """Schema-bound payload for ``ao-kernel project sync`` (sync-report.v1).

    ``items_added`` / ``items_existing`` come straight off the
    :class:`DriftReport` so a single new issue with N missing-field
    findings counts as one item add (not N). Codex iter-2 absorb:
    workflow consumers expect issue-level granularity.
    """
    payload: dict[str, Any] = {
        "schema_version": "project-sync-sync-report.v1",
        "command": "sync",
        "summary": {
            "issues_scanned": scanned,
            "fields_set": len(report.healed),
            "items_added": report.items_added,
            "items_existing": report.items_existing,
        },
        "manifest_digest": manifest_digest,
    }
    payload.update(_const_pinned_envelope())
    return payload


def _migration_payload(report: MigrationReport, *, dry_run: bool, scanned: int) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "schema_version": "project-sync-label-migration-report.v1",
        "command": "label-cleanup",
        "dry_run": dry_run,
        "summary": {
            "issues_scanned": scanned,
            "entries": len(report.entries),
            "dropped": report.dropped_count,
            "skipped": len(report.skipped),
        },
        "entries": [asdict(e) for e in report.entries],
        "skipped": report.skipped,
        "warnings": report.warnings,
    }
    payload.update(_const_pinned_envelope())
    return payload
