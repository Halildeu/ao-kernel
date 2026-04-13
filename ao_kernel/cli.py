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

    mcp_p = sub.add_parser("mcp", help="MCP server commands")
    mcp_sub = mcp_p.add_subparsers(dest="mcp_command")
    serve_p = mcp_sub.add_parser("serve", help="Start MCP server")
    serve_p.add_argument("--transport", choices=["stdio", "http"], default="stdio", help="Transport (default: stdio)")
    serve_p.add_argument("--host", default="127.0.0.1", help="HTTP bind host (default: 127.0.0.1)")
    serve_p.add_argument("--port", type=int, default=8080, help="HTTP port (default: 8080)")

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

    # MCP subcommand
    if cmd == "mcp":
        mcp_cmd = getattr(args, "mcp_command", None)
        if mcp_cmd == "serve":
            return _cmd_mcp_serve(args)
        from ao_kernel.i18n import msg
        print(msg("usage_mcp_serve"))
        return 1

    handler = dispatch.get(cmd)
    if handler is None:
        parser.print_help()
        return 1

    return handler(args)
