"""Memory profiling harness (V5 Epic 7 E-7-3).

Built on top of Python's stdlib ``tracemalloc`` so the harness has
ZERO extra dependencies and works wherever core ao-kernel works. A
richer profiler (``mprof`` / ``memray`` / ``scalene``) can be wired
later as an optional extra; this slice prioritizes "ships with core"
over rich UI.

Boundaries:

- ``tracemalloc`` only (no mprof / memray / scalene / objgraph extras).
- Library mode only (no ``.ao/`` workspace write).
- Stub workload only (no live LLM provider call). The
  ``live_adapter_execution`` guard flag remains ``const false``.
- Default loop count is small (200) so CI runs finish in <1s.
- Output report is schema-pinned JSON; operators can budget against
  the ``rss_peak_kib`` + ``traced_peak_kib`` + per-snapshot top-N
  allocation rows.

Run:

  python scripts/run_memory_profile.py --iterations 200 --top 10 \
      --json-out -

"""

from __future__ import annotations

import argparse
import gc
import json
import os
import resource
import sys
import time
import tracemalloc
from typing import Any


def _max_rss_kib() -> int:
    """Process peak RSS in KiB (POSIX-portable)."""
    usage = resource.getrusage(resource.RUSAGE_SELF)
    if sys.platform == "darwin":
        return int(usage.ru_maxrss / 1024)
    return int(usage.ru_maxrss)


def _stub_workload(index: int) -> dict[str, Any]:
    """One iteration of the profiling workload.

    Allocates a small dict + list with payload to keep the profiler
    busy without pulling in any live provider client. Returns the
    object so the caller can choose to retain or release.
    """
    return {
        "i": index,
        "payload": ["row-{}".format(j) for j in range(8)],
        "meta": {"created_at": index, "released": False},
    }


def run(
    iterations: int,
    top: int,
    retain_every: int,
) -> dict[str, Any]:
    if iterations < 1:
        raise ValueError("iterations must be >= 1")
    if top < 1:
        raise ValueError("top must be >= 1")
    if retain_every < 0:
        raise ValueError("retain-every must be >= 0")

    tracemalloc.start(25)
    start_wall = time.monotonic()
    start_rss = _max_rss_kib()
    retained: list[dict[str, Any]] = []

    for i in range(iterations):
        obj = _stub_workload(i)
        if retain_every and (i % retain_every == 0):
            retained.append(obj)

    end_wall = time.monotonic()
    end_rss = _max_rss_kib()
    snapshot = tracemalloc.take_snapshot()
    traced_current, traced_peak = tracemalloc.get_traced_memory()

    # Top-N allocation rows (filename + line + size_kib + count)
    stats = snapshot.statistics("lineno")[:top]
    top_rows = [
        {
            "filename": s.traceback[0].filename if s.traceback else "<unknown>",
            "lineno": s.traceback[0].lineno if s.traceback else 0,
            "size_kib": round(s.size / 1024, 3),
            "count": s.count,
        }
        for s in stats
    ]

    tracemalloc.stop()
    # Drop retained refs to model the "release" half of the contract
    retained_count = len(retained)
    retained.clear()
    gc.collect()

    return {
        "schema_version": "memory-profile-report.v1",
        "iterations_requested": iterations,
        "iterations_completed": iterations,
        "retain_every": retain_every,
        "retained_count": retained_count,
        "duration_seconds_actual": round(end_wall - start_wall, 6),
        "rss_kib_start": start_rss,
        "rss_kib_end": end_rss,
        "rss_kib_delta": end_rss - start_rss,
        "traced_kib_current": round(traced_current / 1024, 3),
        "traced_kib_peak": round(traced_peak / 1024, 3),
        "top_allocations": top_rows,
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
            "Memory profiling harness (V5 E-7-3). tracemalloc only; "
            "library mode; live_adapter_execution=false."
        )
    )
    parser.add_argument(
        "--iterations",
        type=int,
        default=200,
        help="Workload iteration count (default 200; safe for CI).",
    )
    parser.add_argument(
        "--top",
        type=int,
        default=10,
        help="Top-N allocation rows to include (default 10).",
    )
    parser.add_argument(
        "--retain-every",
        type=int,
        default=0,
        help=(
            "Retain every Nth workload object to simulate slow leak "
            "(0 = release all; default)."
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
        report = run(args.iterations, args.top, args.retain_every)
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
