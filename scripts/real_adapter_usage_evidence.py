#!/usr/bin/env python3
"""GPP-3a: Real-Adapter Usage/Cost Evidence emitter and validator.

This script supports three modes for producing or checking
real-adapter-usage-cost-evidence.v1 artifacts:

  emit-simulated    Emit a schema-valid simulated evidence artifact
                    from a small command-line spec. evidence_class
                    is fixed to "simulated"; live_adapter_execution
                    is fixed to false.

  from-ledger-event Convert one spend-ledger.v1 event into an
                    equivalent evidence artifact. live_adapter_execution
                    follows the source event's surface (false in this
                    slice because GPP-3a does NOT execute live).

  validate          Validate an existing evidence artifact against the
                    bundled schema (including the root oneOf cross-field
                    constraint and the evidence_class /
                    live_adapter_execution allOf if/then bind).

The script never emits live evidence — that path is reserved for
GPP-3c Option X (operator-bound, not autonomous). The artifact does
not by itself close GP-5.9 BC-10; GPP-3b records the closure path
decision and GPP-3c executes it.

This file lives in scripts/ so that operators and CI can run it via
``python3 scripts/real_adapter_usage_evidence.py ...`` without
installing the package.
"""

from __future__ import annotations

import argparse
import json
import sys
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker

_SCHEMA_PATH = (
    Path(__file__).resolve().parent.parent
    / "ao_kernel"
    / "defaults"
    / "schemas"
    / "real-adapter-usage-cost-evidence.schema.v1.json"
)

_SCHEMA_VERSION = "real-adapter-usage-cost-evidence.v1"

_UNAVAILABLE_REASONS = ("usage_missing", "token_unavailable", "cost_unavailable")


class EvidenceError(RuntimeError):
    """Raised when the emitter or validator detects a contract violation."""


def _load_schema() -> dict[str, Any]:
    """Load and lightly self-validate the bundled schema."""

    payload = json.loads(_SCHEMA_PATH.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(payload)
    return payload


def _validator() -> Draft202012Validator:
    return Draft202012Validator(_load_schema(), format_checker=FormatChecker())


def validate_evidence(artifact: dict[str, Any]) -> None:
    """Validate ``artifact`` against the bundled v1 schema.

    Raises :class:`EvidenceError` on the first schema violation.
    """

    errors = sorted(_validator().iter_errors(artifact), key=lambda e: list(e.path))
    if errors:
        first = errors[0]
        path = "/".join(str(p) for p in first.path) or "<root>"
        raise EvidenceError(
            f"evidence artifact failed schema validation at {path}: {first.message}"
        )


def emit_simulated(
    *,
    adapter_id: str,
    model_id: str,
    run_id: str,
    step_id: str,
    elapsed_seconds: float,
    prompt_tokens: int | None,
    completion_tokens: int | None,
    total_cost_usd: Decimal | None,
    pricing_source_type: str,
    pricing_source_ref: str,
    unavailable_reason: str | None,
    observed_at: str | None = None,
) -> dict[str, Any]:
    """Build a simulated-path evidence artifact.

    ``evidence_class`` is fixed to ``simulated`` and
    ``live_adapter_execution`` to ``false``. The caller must pass either
    a non-null ``unavailable_reason`` (with all three usage/cost
    arguments set to ``None``) or a null reason with all three usage/cost
    arguments set.
    """

    if observed_at is None:
        observed_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    if unavailable_reason is not None:
        if unavailable_reason not in _UNAVAILABLE_REASONS:
            raise EvidenceError(
                f"unavailable_reason must be one of {_UNAVAILABLE_REASONS!r} or None"
            )
        if any(
            v is not None for v in (prompt_tokens, completion_tokens, total_cost_usd)
        ):
            raise EvidenceError(
                "unavailable_reason is non-null but one of prompt_tokens / "
                "completion_tokens / total_cost_usd is also non-null; the "
                "schema requires all three to be null in the unavailable branch"
            )
    else:
        if (
            prompt_tokens is None
            or completion_tokens is None
            or total_cost_usd is None
        ):
            raise EvidenceError(
                "unavailable_reason is null but one of prompt_tokens / "
                "completion_tokens / total_cost_usd is null; the schema "
                "requires all three to be non-null in the complete branch"
            )

    cost_str: str | None
    if total_cost_usd is None:
        cost_str = None
    else:
        # Render via Decimal with up to 8 decimal places, matching schema pattern.
        normalized = Decimal(total_cost_usd).quantize(Decimal("0.00000001")).normalize()
        if "." in str(normalized):
            cost_str = format(normalized, "f")
        else:
            cost_str = f"{normalized:.2f}"

    artifact: dict[str, Any] = {
        "schema_version": _SCHEMA_VERSION,
        "evidence_class": "simulated",
        "adapter_id": adapter_id,
        "model_id": model_id,
        "run_id": run_id,
        "step_id": step_id,
        "elapsed_seconds": elapsed_seconds,
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_cost_usd": cost_str,
        "currency": "USD",
        "pricing_source": {
            "source_type": pricing_source_type,
            "source_ref": pricing_source_ref,
            "source_digest": None,
            "retrieved_at": None,
        },
        "unavailable_reason": unavailable_reason,
        "observed_at": observed_at,
        "live_adapter_execution": False,
        "support_widening": False,
        "production_platform_claim": False,
        "linked_spend_ledger_events": None,
    }

    validate_evidence(artifact)
    return artifact


def from_ledger_event(
    event: dict[str, Any],
    *,
    adapter_id: str,
    pricing_source_type: str = "bundled_catalog",
    pricing_source_ref: str = "ao_kernel.cost.catalog",
    observed_at: str | None = None,
) -> dict[str, Any]:
    """Convert a spend-ledger.v1 event into an evidence artifact.

    ``evidence_class`` is fixed to ``simulated`` in GPP-3a (the live
    path is reserved for GPP-3c Option X). The ``usage_missing`` flag on
    the source event maps to ``unavailable_reason="usage_missing"`` and
    drops the tokens/cost into the unavailable branch.
    """

    if observed_at is None:
        observed_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    usage_missing = bool(event.get("usage_missing"))
    if usage_missing:
        prompt_tokens: int | None = None
        completion_tokens: int | None = None
        total_cost: Decimal | None = None
        unavailable_reason: str | None = "usage_missing"
    else:
        prompt_tokens = int(event["tokens_input"])
        completion_tokens = int(event["tokens_output"])
        total_cost = Decimal(str(event["cost_usd"]))
        unavailable_reason = None

    artifact = emit_simulated(
        adapter_id=adapter_id,
        model_id=event["model"],
        run_id=event["run_id"],
        step_id=event["step_id"],
        elapsed_seconds=0.0,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_cost_usd=total_cost,
        pricing_source_type=pricing_source_type,
        pricing_source_ref=pricing_source_ref,
        unavailable_reason=unavailable_reason,
        observed_at=observed_at,
    )

    digest = event.get("billing_digest")
    if isinstance(digest, str):
        artifact["linked_spend_ledger_events"] = [
            {
                "run_id": event["run_id"],
                "step_id": event["step_id"],
                "attempt": event.get("attempt"),
                "billing_digest": digest,
            }
        ]
        validate_evidence(artifact)

    return artifact


def _cli_emit_simulated(args: argparse.Namespace) -> dict[str, Any]:
    return emit_simulated(
        adapter_id=args.adapter_id,
        model_id=args.model_id,
        run_id=args.run_id or str(uuid.uuid4()),
        step_id=args.step_id,
        elapsed_seconds=args.elapsed_seconds,
        prompt_tokens=args.prompt_tokens,
        completion_tokens=args.completion_tokens,
        total_cost_usd=(
            None if args.total_cost_usd is None else Decimal(args.total_cost_usd)
        ),
        pricing_source_type=args.pricing_source_type,
        pricing_source_ref=args.pricing_source_ref,
        unavailable_reason=args.unavailable_reason,
        observed_at=args.observed_at,
    )


def _cli_from_ledger_event(args: argparse.Namespace) -> dict[str, Any]:
    event = json.loads(Path(args.event_path).read_text(encoding="utf-8"))
    return from_ledger_event(
        event,
        adapter_id=args.adapter_id,
        pricing_source_type=args.pricing_source_type,
        pricing_source_ref=args.pricing_source_ref,
        observed_at=args.observed_at,
    )


def _cli_validate(args: argparse.Namespace) -> int:
    payload = json.loads(Path(args.artifact_path).read_text(encoding="utf-8"))
    try:
        validate_evidence(payload)
    except EvidenceError as exc:
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

    emit = sub.add_parser("emit-simulated", help="Emit a simulated evidence artifact")
    emit.add_argument("--adapter-id", required=True)
    emit.add_argument("--model-id", required=True)
    emit.add_argument("--run-id", default=None, help="UUID; auto-generated when omitted")
    emit.add_argument("--step-id", required=True)
    emit.add_argument("--elapsed-seconds", type=float, required=True)
    emit.add_argument("--prompt-tokens", type=int, default=None)
    emit.add_argument("--completion-tokens", type=int, default=None)
    emit.add_argument("--total-cost-usd", default=None)
    emit.add_argument(
        "--pricing-source-type",
        default="simulated_fixture",
        choices=[
            "bundled_catalog",
            "workspace_catalog",
            "operator_supplied",
            "simulated_fixture",
        ],
    )
    emit.add_argument("--pricing-source-ref", default="fixture/anthropic-2026-05")
    emit.add_argument(
        "--unavailable-reason",
        default=None,
        choices=[None, "usage_missing", "token_unavailable", "cost_unavailable"],
    )
    emit.add_argument("--observed-at", default=None)
    emit.add_argument("--output", type=Path, default=None)

    convert = sub.add_parser(
        "from-ledger-event", help="Convert a spend ledger event to evidence"
    )
    convert.add_argument("--event-path", required=True)
    convert.add_argument("--adapter-id", required=True)
    convert.add_argument(
        "--pricing-source-type",
        default="bundled_catalog",
        choices=[
            "bundled_catalog",
            "workspace_catalog",
            "operator_supplied",
            "simulated_fixture",
        ],
    )
    convert.add_argument("--pricing-source-ref", default="ao_kernel.cost.catalog")
    convert.add_argument("--observed-at", default=None)
    convert.add_argument("--output", type=Path, default=None)

    validate = sub.add_parser("validate", help="Validate an existing evidence artifact")
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
        if args.mode == "from-ledger-event":
            artifact = _cli_from_ledger_event(args)
            _write_output(artifact, args.output)
            return 0
        if args.mode == "validate":
            return _cli_validate(args)
    except EvidenceError as exc:
        print(f"FAIL {exc}", file=sys.stderr)
        return 2

    parser.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
