"""CLI handlers for ``ao-kernel evidence`` subcommands (PR-A5).

Called from ``ao_kernel.cli`` argparse dispatcher. Returns int exit code.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any


def cmd_timeline(args: Any) -> int:
    """Handle ``ao-kernel evidence timeline``."""
    from ao_kernel._internal.evidence.timeline import timeline

    workspace = _resolve_workspace(args)
    try:
        output = timeline(
            workspace, args.run_id,
            format=getattr(args, "format", "table"),
            filter_kinds=(
                args.filter_kind.split(",") if getattr(args, "filter_kind", None) else None
            ),
            filter_actor=getattr(args, "filter_actor", None),
            limit=getattr(args, "limit", None),
        )
    except FileNotFoundError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    print(output)
    return 0


def cmd_replay(args: Any) -> int:
    """Handle ``ao-kernel evidence replay``."""
    from ao_kernel._internal.evidence.replay import format_replay_report, replay

    workspace = _resolve_workspace(args)
    try:
        report = replay(
            workspace, args.run_id,
            mode=getattr(args, "mode", "inspect"),
        )
    except FileNotFoundError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    print(format_replay_report(report))
    return 1 if report.warnings else 0


def cmd_generate_manifest(args: Any) -> int:
    """Handle ``ao-kernel evidence generate-manifest``."""
    from ao_kernel._internal.evidence.manifest import generate_manifest

    workspace = _resolve_workspace(args)
    try:
        result = generate_manifest(workspace, args.run_id)
    except FileNotFoundError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    print(f"manifest generated: {result.manifest_path}")
    print(f"  files: {len(result.files)}")
    print(f"  generated_at: {result.generated_at}")
    return 0


def cmd_verify_manifest(args: Any) -> int:
    """Handle ``ao-kernel evidence verify-manifest``.

    Exit codes: 0=OK, 1=mismatch/missing, 2=outdated, 3=manifest missing.
    """
    from ao_kernel._internal.evidence.manifest import verify_manifest

    workspace = _resolve_workspace(args)
    try:
        result = verify_manifest(
            workspace, args.run_id,
            generate_if_missing=getattr(args, "generate_if_missing", False),
        )
    except FileNotFoundError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 3

    # I4-B1 fix: missing manifest.json itself → exit 3 (before generic missing)
    if result.missing == ("manifest.json",):
        print(f"MISSING: manifest.json for run {result.run_id} (use --generate-if-missing)")
        return 3

    if result.all_match and not result.manifest_outdated:
        print(f"OK: all files match for run {result.run_id}")
        return 0

    if result.mismatches or result.missing:
        for m in result.mismatches:
            print(f"MISMATCH: {m}")
        for m in result.missing:
            print(f"MISSING: {m}")
        return 1

    if result.manifest_outdated:
        for e in result.extra_in_scope:
            print(f"OUTDATED (new file not in manifest): {e}")
        return 2

    return 0


def _resolve_workspace(args: Any) -> Path:
    ws = getattr(args, "workspace_root", None)
    if ws:
        return Path(ws)
    from ao_kernel.config import workspace_root
    resolved = workspace_root()
    if resolved is None:
        print("error: no .ao/ workspace found", file=sys.stderr)
        sys.exit(1)
    return resolved
