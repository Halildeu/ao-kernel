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


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ao-kernel",
        description="Governed AI orchestration runtime",
    )
    parser.add_argument(
        "--workspace-root",
        default=None,
        help="Override workspace root directory",
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
    vm_p.add_argument("--generate-if-missing", action="store_true",
                       help="Generate manifest first if absent")

    mcp_p = sub.add_parser("mcp", help="MCP server commands")
    mcp_sub = mcp_p.add_subparsers(dest="mcp_command")
    serve_p = mcp_sub.add_parser("serve", help="Start MCP server")
    serve_p.add_argument("--transport", choices=["stdio", "http"], default="stdio", help="Transport (default: stdio)")
    serve_p.add_argument("--host", default="127.0.0.1", help="HTTP bind host (default: 127.0.0.1)")
    serve_p.add_argument("--port", type=int, default=8080, help="HTTP port (default: 8080)")

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

    # Metrics subcommand (PR-B5)
    if cmd == "metrics":
        from ao_kernel._internal.metrics.cli_handlers import cmd_metrics_export

        metrics_cmd = getattr(args, "metrics_command", None)
        metrics_dispatch = {
            "export": cmd_metrics_export,
        }
        handler = metrics_dispatch.get(metrics_cmd) if metrics_cmd else None
        if handler is None:
            print("Usage: ao-kernel metrics {export}")
            return 1
        return handler(args)

    handler = dispatch.get(cmd)
    if handler is None:
        parser.print_help()
        return 1

    return handler(args)
