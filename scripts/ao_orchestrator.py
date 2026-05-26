#!/usr/bin/env python3
"""Thin wrapper for the canonical ``ao-kernel orchestration`` subcommand.

Operators may invoke either:

    ao-kernel orchestration plan --goal "..."
    python scripts/ao_orchestrator.py plan --goal "..."

Both paths share the same handler in ``ao_kernel.orchestration.cli_handlers``.
This script is the path-portable invocation for environments where the
``ao-kernel`` console script is not on PATH (CI, fresh venv, etc.).
"""

from __future__ import annotations

import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from ao_kernel.cli import main as cli_main  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    """Forward to the canonical ``ao-kernel orchestration ...`` CLI."""

    args = list(argv) if argv is not None else sys.argv[1:]
    return cli_main(["orchestration", *args])


if __name__ == "__main__":
    raise SystemExit(main())
