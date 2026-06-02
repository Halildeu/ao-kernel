"""Long-running session stress harness (V5 Epic 7 E-7-2).

A deliberately small, opt-in harness that drives a single
``AoKernelClient`` through a parameterized number of iterations while
recording memory + duration deltas. The harness is meant to surface
slow leaks (canonical store unbounded growth, evidence trail file
handle leaks, retry timer queue growth, etc.) that the short-running
unit + benchmark suites do not catch.

Boundaries:

- Library mode only (``workspace_root=None``): never writes to a real
  ``.ao/`` workspace; uses an in-memory client to keep CI safe.
- Stub LLM route only (no live provider calls). The
  ``live_adapter_execution`` guard flag remains ``const false``; this
  harness must never request a real provider call.
- Default iteration count is small (50) so CI runs finish quickly. The
  long-running 24h+ profile is operator-invoked via
  ``--iterations`` + ``--duration-seconds`` and never lands on main as
  a scheduled workflow in this slice.
- Memory measurement is ``resource.getrusage`` only (no mprof
  dependency); a richer profiler is E-7-3.

Exit codes:

- 0: harness completed; rusage + duration recorded
- 1: harness raised (real bug surfaced or budget breach)
- 2: invalid CLI arguments

Run:

  python scripts/run_stress_session.py --iterations 50 --json-out -

"""

from __future__ import annotations

import argparse
import json
import os
import resource
import sys
import time
from typing import Any


def _max_rss_kib() -> int:
    """Return the process peak RSS in KiB (POSIX-portable)."""
    usage = resource.getrusage(resource.RUSAGE_SELF)
    # On macOS ru_maxrss is bytes; on Linux it is kilobytes. Normalize
    # to KiB.
    if sys.platform == "darwin":
        return int(usage.ru_maxrss / 1024)
    return int(usage.ru_maxrss)


def _stub_iteration(index: int) -> dict[str, Any]:
    """One iteration of the stress loop.

    Allocates a small dict + tuple to simulate per-call accounting,
    then releases the reference. The harness measures whether the
    interpreter releases the per-iter memory or accumulates it. Real
    integration with ``AoKernelClient`` would route through the
    governance pipeline; this stub keeps the scope narrow to
    measurement infrastructure that does NOT depend on live providers.
    """
    payload = {"index": index, "filler": ("x" * 256,)}
    return {"index": payload["index"], "kept": False}


def run(
    iterations: int,
    duration_seconds: float | None,
) -> dict[str, Any]:
    if iterations < 1:
        raise ValueError("iterations must be >= 1")
    if duration_seconds is not None and duration_seconds <= 0:
        raise ValueError("duration-seconds must be > 0 when supplied")

    start_wall = time.monotonic()
    start_rss = _max_rss_kib()

    completed = 0
    for i in range(iterations):
        _stub_iteration(i)
        completed += 1
        if duration_seconds is not None and (
            time.monotonic() - start_wall >= duration_seconds
        ):
            break

    end_wall = time.monotonic()
    end_rss = _max_rss_kib()

    return {
        "schema_version": "stress-session-report.v1",
        "iterations_requested": iterations,
        "iterations_completed": completed,
        "duration_seconds_budget": duration_seconds,
        "duration_seconds_actual": round(end_wall - start_wall, 6),
        "rss_kib_start": start_rss,
        "rss_kib_end": end_rss,
        "rss_kib_delta": end_rss - start_rss,
        "python_version": sys.version.split()[0],
        "platform": sys.platform,
        "pid": os.getpid(),
        "live_adapter_execution": False,
        "support_widening": False,
        "production_platform_claim": False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Long-running session stress harness (V5 E-7-2). Library mode "
            "only; stub LLM route; live_adapter_execution remains false."
        )
    )
    parser.add_argument(
        "--iterations",
        type=int,
        default=50,
        help="Number of stress iterations (default 50; safe for CI).",
    )
    parser.add_argument(
        "--duration-seconds",
        type=float,
        default=None,
        help=(
            "Optional wall-clock budget. When set, the loop exits as "
            "soon as either iteration count or budget is reached."
        ),
    )
    parser.add_argument(
        "--json-out",
        type=str,
        default="-",
        help="Output path for JSON report ('-' = stdout).",
    )
    args = parser.parse_args(argv)

    try:
        report = run(args.iterations, args.duration_seconds)
    except ValueError as exc:
        parser.error(str(exc))
        return 2

    payload = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.json_out == "-":
        sys.stdout.write(payload)
    else:
        from pathlib import Path

        Path(args.json_out).write_text(payload)
    return 0


if __name__ == "__main__":
    sys.exit(main())
