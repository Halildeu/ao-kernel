#!/usr/bin/env python3
"""Run a library-mode support-widening smoke for one surface class (V5 Epic 3 E-3-2).

Stub-adapter-only; no network, no `.ao/` mutation. Emits a
`support_widening_evidence.v1` artifact (support_widening pinned false) for the
requested surface class. Read-only with respect to the workspace.

    python scripts/run_support_smoke.py --surface python_version \
        [--evidence-out path/to/evidence.json] [--repo owner/name]

The harness runs under the dominant runtime kill-switch
(`ao_kernel._internal.support_widening.harnesses.killswitch`): any network /
subprocess / shell / dynamic-import / secret-env access inside it fails closed.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from ao_kernel._internal.support_widening.evidence import SupportWideningEvidenceError  # noqa: E402
from ao_kernel._internal.support_widening.harnesses.killswitch import SupportWideningError  # noqa: E402
from ao_kernel._internal.support_widening.harnesses.runner import SURFACE_CLASSES, run_surface_smoke  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Support-widening per-surface smoke harness (library-mode, stub adapters)")
    parser.add_argument("--surface", required=True, choices=SURFACE_CLASSES, help="Surface class to smoke")
    parser.add_argument("--evidence-out", default=None, help="Optional path to write the v1 evidence artifact (0o600)")
    parser.add_argument("--repo", default="Halildeu/ao-kernel", help="repo slug for the artifact")
    args = parser.parse_args(argv)

    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    out = Path(args.evidence_out) if args.evidence_out else None
    try:
        payload = run_surface_smoke(args.surface, repo=args.repo, generated_at=generated_at, evidence_out=out)
    except (SupportWideningError, SupportWideningEvidenceError) as exc:
        print(f"SMOKE FAILED ({args.surface}): {exc}", file=sys.stderr)
        return 1

    where = f" → {args.evidence_out}" if out else ""
    print(f"SMOKE OK: surface={args.surface} simulated_only=true live_call_made=false support_widening=false{where}")
    if out is None:
        print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
