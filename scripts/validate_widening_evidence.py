#!/usr/bin/env python3
"""Validate support-widening evidence with the E-3-6 recompute validator."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from ao_kernel._internal.support_widening.validator import (  # noqa: E402
    WideningEvidenceValidationContext,
    validation_report,
)


def _read_json(path: Path) -> dict[str, Any]:
    parsed = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(parsed, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return parsed


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="E-3-6 v1-only support-widening recompute-not-trust validator"
    )
    parser.add_argument("--evidence", required=True, help="Path to evidence JSON")
    parser.add_argument(
        "--context",
        default=None,
        help=(
            "Optional context JSON with recomputed_plan_digest, "
            "recomputed_final_diff_digest, github_pr_head_sha, workflow_runs, "
            "workflow_artifacts, artifact_paths, and now"
        ),
    )
    args = parser.parse_args(argv)

    evidence_path = Path(args.evidence)
    context_path = Path(args.context) if args.context else None
    try:
        evidence = _read_json(evidence_path)
        context = (
            WideningEvidenceValidationContext.from_dict(_read_json(context_path))
            if context_path is not None
            else WideningEvidenceValidationContext()
        )
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(json.dumps({"valid": False, "decision": "usage_error", "error": str(exc)}, sort_keys=True))
        return 2

    report = validation_report(evidence, context=context)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["valid"] else 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
