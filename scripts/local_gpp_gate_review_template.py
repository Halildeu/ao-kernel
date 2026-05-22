#!/usr/bin/env python3
"""Emit a blank no-secret reviewer-evidence template for the local GPP gate.

The reviewer AI fills the placeholder values and feeds the completed file
to ``scripts/local_gpp_gate.py``. This makes reviewer output a repeatable
structured artifact instead of ad-hoc chat text.

The emitted skeleton is intentionally schema-valid against
``local-ai-review-evidence.schema.v1.json``: string placeholders use the
literal ``FILL_ME`` so the file parses and validates immediately, and the
reviewer replaces them. The reviewer must also replace the placeholder
``changed_files`` entry and add real ``tests`` and ``secret_scan`` check
entries; an unedited template fails the local gate by design, because its
verdict placeholder is the explicit no-op value ``REVISE``.

No secret material may appear in any field, including agent identifiers
and findings strings.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

REVIEW_EVIDENCE_SCHEMA_VERSION = "local-ai-review-evidence.v1"


def build_template() -> dict[str, Any]:
    """Return a schema-valid no-secret reviewer-evidence skeleton."""

    return {
        "schema_version": REVIEW_EVIDENCE_SCHEMA_VERSION,
        "repo": "FILL_ME",
        "work_package": "FILL_ME",
        "implementer": {
            "agent": "FILL_ME",
            "provider": "openai",
        },
        "reviewer": {
            "agent": "FILL_ME",
            "provider": "anthropic",
            "verdict": "REVISE",
        },
        "scope_reviewed": {
            "base_ref": "origin/main",
            "head_ref": "FILL_ME",
            "changed_files": ["FILL_ME"],
        },
        "checks_considered": [
            {"name": "tests", "status": "fail"},
            {"name": "secret_scan", "status": "fail"},
        ],
        "findings": [],
        "secrets_recorded": False,
        "live_adapter_execution": False,
        "support_widening": False,
        "production_platform_claim": False,
    }


def build_parser() -> argparse.ArgumentParser:
    """Build the CLI parser."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Optional path to write the template (defaults to stdout).",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """CLI entrypoint. Returns 0 on success, 2 on a write error."""

    parser = build_parser()
    args = parser.parse_args(argv)

    rendered = json.dumps(build_template(), indent=2, sort_keys=True) + "\n"
    if args.output is not None:
        try:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(rendered, encoding="utf-8")
        except OSError as exc:
            print(f"local_gpp_gate_review_template: {exc}", file=sys.stderr)
            return 2
        print(f"local_gpp_gate_review_template: wrote template to {args.output}")
        return 0

    print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
