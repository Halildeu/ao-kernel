#!/usr/bin/env python3
"""CLI wrapper for the V5 E-2-4 no-network live-adapter dry-run harness."""

from __future__ import annotations

import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from ao_kernel._internal.live_adapter_dryrun import main  # noqa: E402


if __name__ == "__main__":
    raise SystemExit(main())
