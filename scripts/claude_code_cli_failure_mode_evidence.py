#!/usr/bin/env python3
"""GPP-4a: claude-code-cli Failure-Mode Matrix evidence emitter/validator.

This script supports two modes:

  emit-simulated   Emit a schema-valid simulated matrix artifact with
                   all seven canonical failure modes. evidence_class is
                   fixed to "simulated"; live_adapter_execution is
                   fixed to false; protected_run.observed is fixed to
                   false.

  validate         Validate an existing matrix artifact against the
                   bundled schema (including the root oneOf bind on
                   evidence_class / live_adapter_execution /
                   protected_run, and the seven `contains` invariants
                   that require every canonical failure mode).

The script never emits live evidence — that path is reserved for an
operator-bound supersession slice (CC-9 enforcement). The artifact
does not by itself promote claude-code-cli to production-certified
read-only; promotion authority is recorded separately in the GPP-4b
decision slice.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker

_SCHEMA_PATH = (
    Path(__file__).resolve().parent.parent
    / "ao_kernel"
    / "defaults"
    / "schemas"
    / "claude-code-cli-failure-mode.schema.v1.json"
)

_SCHEMA_VERSION = "claude-code-cli-failure-mode.v1"

_CANONICAL_MODES = (
    "auth_missing",
    "binary_missing",
    "timeout",
    "prompt_denied",
    "malformed_output",
    "policy_denied",
    "redaction",
)

# Default simulated matrix; covers every canonical mode with stable
# finding codes that mirror the existing repo helper / workflow
# vocabulary (claude_not_logged_in, claude_binary_missing, etc.).
_DEFAULT_COVERAGE: tuple[dict[str, Any], ...] = (
    {
        "failure_mode": "auth_missing",
        "surface": "helper_preflight",
        "stable_finding_codes": ["claude_not_logged_in"],
        "expected_overall_status": "blocked",
        "outcome": "fail_closed",
        "evidence_refs": [
            "tests/test_claude_code_cli_helper.py",
            "scripts/claude_code_cli_helper.py",
        ],
    },
    {
        "failure_mode": "binary_missing",
        "surface": "helper_preflight",
        "stable_finding_codes": ["claude_binary_missing"],
        "expected_overall_status": "blocked",
        "outcome": "fail_closed",
        "evidence_refs": [
            "tests/test_claude_code_cli_helper.py",
            "scripts/claude_code_cli_helper.py",
        ],
    },
    {
        "failure_mode": "timeout",
        "surface": "adapter_runtime",
        "stable_finding_codes": ["adapter_timeout"],
        "expected_overall_status": "fail_closed",
        "outcome": "fail_closed",
        "evidence_refs": [
            "tests/test_claude_code_cli_smoke.py",
            "ao_kernel/_internal/prj_kernel_api/llm.py",
        ],
    },
    {
        "failure_mode": "prompt_denied",
        "surface": "policy_layer",
        "stable_finding_codes": ["prompt_access_denied"],
        "expected_overall_status": "rejected",
        "outcome": "rejected",
        "evidence_refs": [
            "tests/test_claude_code_cli_helper.py",
            "ao_kernel/governance.py",
        ],
    },
    {
        "failure_mode": "malformed_output",
        "surface": "evidence_emitter",
        "stable_finding_codes": ["output_parse_failed"],
        "expected_overall_status": "fail_closed",
        "outcome": "fail_closed",
        "evidence_refs": [
            "tests/test_claude_code_cli_smoke.py",
            "ao_kernel/executor/evidence_emitter.py",
        ],
    },
    {
        "failure_mode": "policy_denied",
        "surface": "policy_layer",
        "stable_finding_codes": ["policy_denied"],
        "expected_overall_status": "rejected",
        "outcome": "rejected",
        "evidence_refs": [
            "tests/test_claude_code_cli_smoke.py",
            "ao_kernel/governance.py",
        ],
    },
    {
        "failure_mode": "redaction",
        "surface": "redaction_layer",
        "stable_finding_codes": ["adapter_log_missing_or_unredacted"],
        "expected_overall_status": "fail_closed",
        "outcome": "fail_closed",
        "evidence_refs": [
            "tests/test_claude_code_cli_smoke.py",
            "ao_kernel/secrets/redaction.py",
        ],
    },
)


class FailureMatrixError(RuntimeError):
    """Raised when the emitter or validator detects a contract violation."""


def _load_schema() -> dict[str, Any]:
    payload = json.loads(_SCHEMA_PATH.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(payload)
    return payload


def _validator() -> Draft202012Validator:
    return Draft202012Validator(_load_schema(), format_checker=FormatChecker())


def validate_artifact(artifact: dict[str, Any]) -> None:
    """Validate ``artifact`` against the bundled schema."""

    errors = sorted(_validator().iter_errors(artifact), key=lambda e: list(e.path))
    if errors:
        first = errors[0]
        path = "/".join(str(p) for p in first.path) or "<root>"
        raise FailureMatrixError(
            f"failure-mode matrix artifact failed schema validation at {path}: {first.message}"
        )


def emit_simulated(
    *,
    program_id: str = "GPP-4a",
    coverage: tuple[dict[str, Any], ...] | None = None,
    observed_at: str | None = None,
) -> dict[str, Any]:
    """Build a simulated-path failure-mode matrix artifact."""

    if observed_at is None:
        observed_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    if coverage is None:
        coverage = _DEFAULT_COVERAGE

    artifact = {
        "schema_version": _SCHEMA_VERSION,
        "artifact_kind": "claude_code_cli_failure_mode_matrix",
        "program_id": program_id,
        "adapter_id": "claude-code-cli",
        "evidence_class": "simulated",
        "overall_status": "coverage_ready_live_evidence_pending",
        "live_adapter_execution": False,
        "support_widening": False,
        "production_platform_claim": False,
        "protected_run": {
            "observed": False,
            "run_url": None,
            "check_run_id": None,
            "source_pin_verified": None,
        },
        "coverage": [dict(item) for item in coverage],
        "observed_at": observed_at,
    }

    validate_artifact(artifact)
    return artifact


def _cli_emit_simulated(args: argparse.Namespace) -> dict[str, Any]:
    return emit_simulated(
        program_id=args.program_id,
        observed_at=args.observed_at,
    )


def _cli_validate(args: argparse.Namespace) -> int:
    payload = json.loads(Path(args.artifact_path).read_text(encoding="utf-8"))
    try:
        validate_artifact(payload)
    except FailureMatrixError as exc:
        print(f"FAIL {exc}", file=sys.stderr)
        return 2
    print("OK")
    return 0


def _write_output(artifact: dict[str, Any], output: Path | None) -> None:
    rendered = json.dumps(artifact, indent=2, sort_keys=True) + "\n"
    if output is None:
        sys.stdout.write(rendered)
    else:
        output.write_text(rendered, encoding="utf-8")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="mode", required=True)

    emit = sub.add_parser(
        "emit-simulated",
        help="Emit a schema-valid simulated failure-mode matrix artifact",
    )
    emit.add_argument("--program-id", default="GPP-4a")
    emit.add_argument("--observed-at", default=None)
    emit.add_argument("--output", type=Path, default=None)

    validate = sub.add_parser(
        "validate", help="Validate an existing matrix artifact against the schema"
    )
    validate.add_argument("--artifact-path", required=True)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.mode == "emit-simulated":
            artifact = _cli_emit_simulated(args)
            _write_output(artifact, args.output)
            return 0
        if args.mode == "validate":
            return _cli_validate(args)
    except FailureMatrixError as exc:
        print(f"FAIL {exc}", file=sys.stderr)
        return 2
    parser.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
