#!/usr/bin/env python3
"""Emit advisory CI artifacts for the live-adapter dry-run harness.

This wrapper is V5 Epic 2 E-2-6 Path A: pull_request-safe, artifact-only,
and deliberately secret-free. It fails closed when protected credential
environment variables are present, then delegates to the E-2-4 dry-run harness
which already blocks network/subprocess/native escape paths.
"""

from __future__ import annotations

import argparse
import contextlib
import datetime as dt
import json
import os
import sys
import uuid
from pathlib import Path
from typing import Any, Mapping

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from ao_kernel._internal.live_adapter_dryrun import (  # noqa: E402
    DryRunKillSwitchError,
    DryRunSchemaError,
    run_live_adapter_dryrun,
)

FORBIDDEN_SECRET_ENV_NAMES: tuple[str, ...] = (
    "OPENAI_API_KEY",
    "ANTHROPIC_API_KEY",
    "AO_CLAUDE_CODE_CLI_AUTH",
    "TEAMS_WEBHOOK_URL",
    "AO_GITHUB_APP_PRIVATE_KEY",
    "AO_RELEASE_GATE_WEBHOOK_SECRET",
)


class WorkflowEvidenceError(RuntimeError):
    """Raised when the advisory evidence workflow would cross a boundary."""


def _iso_now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    rendered = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    tmp_path = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        fd = os.open(tmp_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write(rendered)
                handle.flush()
                os.fsync(handle.fileno())
        except BaseException:
            with contextlib.suppress(OSError):
                os.close(fd)
            raise
        os.replace(tmp_path, path)
        with contextlib.suppress(OSError):
            directory_fd = os.open(path.parent, os.O_RDONLY)
            try:
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)
    finally:
        with contextlib.suppress(FileNotFoundError):
            tmp_path.unlink()
    with contextlib.suppress(OSError):
        os.chmod(path, 0o600)


def _assert_no_forbidden_secret_env() -> None:
    present = sorted(name for name in FORBIDDEN_SECRET_ENV_NAMES if os.environ.get(name))
    if present:
        raise WorkflowEvidenceError("forbidden secret environment variables are present for advisory CI")


def _stdout_summary_payload() -> dict[str, object]:
    return {
        "mode": "advisory_ci_path_a",
        "status": "ok",
        "artifacts_written": True,
        "live_adapter_execution": False,
        "support_widening": False,
        "production_platform_claim": False,
    }


def emit_advisory_workflow_evidence(
    *,
    output_dir: Path,
    provider_id: str = "openai",
    model: str = "gpt-4o-mini",
    intent: str = "FAST_TEXT",
) -> dict[str, Any]:
    """Run one dry-run call and write the advisory workflow summary."""

    _assert_no_forbidden_secret_env()
    root = Path(output_dir)
    evidence_dir = root / "evidence"
    envelope_path = evidence_dir / "live-adapter-dryrun.envelope.v1.json"
    result = run_live_adapter_dryrun(
        provider_id=provider_id,
        model=model,
        intent=intent,
        output=envelope_path,
        workspace_root=root,
        prompt="advisory-ci-dry-run",
        session_id="e-2-6-advisory-ci",
    )
    audit_path = evidence_dir / "per_call_audit.jsonl"
    summary_path = root / "live-adapter-evidence-workflow-summary.v1.json"
    summary: dict[str, Any] = {
        "schema_version": "live-adapter-evidence-workflow-summary.v1",
        "artifact_kind": "live_adapter_evidence_workflow_summary",
        "mode": "advisory_ci_path_a",
        "created_at": _iso_now(),
        "trigger_surface": "pull_request_or_workflow_dispatch",
        "permission_surface": "contents_read_only",
        "notification_surface": "artifact_only_no_pr_comment_no_teams_webhook",
        "secret_env_policy": {
            "forbidden_env_names": list(FORBIDDEN_SECRET_ENV_NAMES),
            "forbidden_env_present": [],
        },
        "provider_id": provider_id,
        "model": model,
        "intent": intent,
        "envelope_digest": result.envelope["envelope_digest"],
        "cost_breach_state": result.cost_breach_state,
        "audit_receipt": result.audit_receipt,
        "artifacts": {
            "envelope": str(envelope_path),
            "per_call_audit": str(audit_path),
            "summary": str(summary_path),
        },
        "live_adapter_execution": False,
        "support_widening": False,
        "production_platform_claim": False,
    }
    _write_json(summary_path, summary)
    return summary


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Emit secret-free live-adapter advisory CI dry-run artifacts.")
    parser.add_argument("--output-dir", type=Path, default=Path("live-adapter-evidence"))
    parser.add_argument("--provider", dest="provider_id", default="openai")
    parser.add_argument("--model", default="gpt-4o-mini")
    parser.add_argument("--intent", default="FAST_TEXT")
    parser.add_argument("--output-format", choices=("json", "text"), default="json")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        emit_advisory_workflow_evidence(
            output_dir=args.output_dir,
            provider_id=args.provider_id,
            model=args.model,
            intent=args.intent,
        )
    except (DryRunKillSwitchError, DryRunSchemaError, WorkflowEvidenceError, OSError, ValueError) as exc:
        print(f"live-adapter advisory evidence failed: {exc}", file=sys.stderr)
        return 1
    if args.output_format == "json":
        print(json.dumps(_stdout_summary_payload(), indent=2, sort_keys=True))
    else:
        print("live-adapter advisory evidence: ok")
        print("artifacts_written: true")
        print("live_adapter_execution: false")
        print("support_widening: false")
        print("production_platform_claim: false")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
