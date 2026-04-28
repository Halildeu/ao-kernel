#!/usr/bin/env python3
"""Emit metadata-only attestation for the internal GPP-2 gate host bundle."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Iterable

DEFAULT_BUNDLE_DIR = Path("deploy/internal-gate-host")
REQUIRED_FILES = ("compose.yaml", ".env.example", "Caddyfile.example", "README.md")

COMPOSE_MARKERS = (
    "live-adapter-gate-policy:",
    "ao-release-gate:",
    "caddy:",
    "ghcr.io/halildeu/ao-kernel-live-adapter-gate-policy-service",
    "ghcr.io/halildeu/ao-kernel-ao-release-gate-service",
    "AO_LIVE_ADAPTER_GATE_WEBHOOK_SECRET_ID",
    "AO_RELEASE_GATE_WEBHOOK_SECRET_ID",
    "AO_GITHUB_APP_PRIVATE_KEY_PEM_ID",
    "SECRETS_PROVIDER",
    "VAULT_ADDR",
    "VAULT_TOKEN",
    "AO_RELEASE_GATE_GPP_STATUS_PATH",
)

CADDY_MARKERS = (
    "/github/deployment-protection",
    "/github/ao-release-gate",
    "live-adapter-gate-policy:8000",
    "ao-release-gate:8000",
)

ENV_MARKERS = (
    "SECRETS_PROVIDER=hashicorp_vault",
    "AO_LIVE_ADAPTER_GATE_WEBHOOK_SECRET_ID=",
    "AO_RELEASE_GATE_WEBHOOK_SECRET_ID=",
    "AO_GITHUB_APP_PRIVATE_KEY_PEM_ID=",
)

FORBIDDEN_MARKERS = (
    "AO_CLAUDE_CODE_CLI_AUTH",
    "AO_LIVE_ADAPTER_GATE_WEBHOOK_SECRET:",
    "AO_RELEASE_GATE_WEBHOOK_SECRET:",
    "AO_GITHUB_APP_PRIVATE_KEY_PEM:",
    "BEGIN PRIVATE KEY",
)


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _missing_markers(text: str, markers: Iterable[str]) -> list[str]:
    return [marker for marker in markers if marker not in text]


def build_attestation(bundle_dir: Path) -> dict[str, object]:
    """Build static, no-secret attestation for the internal host bundle."""

    bundle_dir = bundle_dir.resolve()
    findings: list[dict[str, str]] = []
    file_text: dict[str, str] = {}

    for filename in REQUIRED_FILES:
        path = bundle_dir / filename
        if not path.exists():
            findings.append(
                {
                    "code": "internal_gate_host_required_file_missing",
                    "detail": f"Missing {filename}.",
                }
            )
            continue
        file_text[filename] = _read(path)

    if "compose.yaml" in file_text:
        for marker in _missing_markers(file_text["compose.yaml"], COMPOSE_MARKERS):
            findings.append(
                {
                    "code": "internal_gate_host_compose_marker_missing",
                    "detail": f"compose.yaml does not include {marker}.",
                }
            )

    if "Caddyfile.example" in file_text:
        for marker in _missing_markers(file_text["Caddyfile.example"], CADDY_MARKERS):
            findings.append(
                {
                    "code": "internal_gate_host_caddy_marker_missing",
                    "detail": f"Caddyfile.example does not include {marker}.",
                }
            )

    if ".env.example" in file_text:
        for marker in _missing_markers(file_text[".env.example"], ENV_MARKERS):
            findings.append(
                {
                    "code": "internal_gate_host_env_marker_missing",
                    "detail": f".env.example does not include {marker}.",
                }
            )

    checked_text = "\n".join(file_text.values())
    for marker in FORBIDDEN_MARKERS:
        if marker in checked_text:
            findings.append(
                {
                    "code": "internal_gate_host_forbidden_secret_marker",
                    "detail": f"Checked-in bundle includes forbidden marker {marker}.",
                }
            )

    status = "metadata_ready" if not findings else "blocked"
    return {
        "schema_version": "1",
        "program_id": "GPP-2ae",
        "status": status,
        "bundle_dir": str(bundle_dir),
        "required_files": list(REQUIRED_FILES),
        "services": [
            "caddy",
            "live-adapter-gate-policy",
            "ao-release-gate",
        ],
        "operator_owned_platform_infrastructure": True,
        "end_user_self_host_required": False,
        "uses_repo_owned_container_packages": True,
        "uses_internal_vault_secret_ids": True,
        "secret_value_readback": False,
        "public_https_hosting_evidence": False,
        "github_webhook_configured": False,
        "github_callback_post": False,
        "github_check_run_post": False,
        "branch_protection_cutover": False,
        "protected_workflow_dispatch": False,
        "live_adapter_execution": False,
        "support_widening": False,
        "production_platform_claim": False,
        "findings": findings,
    }


def _render_text(payload: dict[str, object]) -> str:
    lines = [
        "Internal Gate Host Bootstrap Attestation",
        f"status: {payload['status']}",
        f"bundle_dir: {payload['bundle_dir']}",
        f"operator_owned_platform_infrastructure: {str(payload['operator_owned_platform_infrastructure']).lower()}",
        f"end_user_self_host_required: {str(payload['end_user_self_host_required']).lower()}",
        f"secret_value_readback: {str(payload['secret_value_readback']).lower()}",
        f"github_callback_post: {str(payload['github_callback_post']).lower()}",
        f"github_check_run_post: {str(payload['github_check_run_post']).lower()}",
        f"live_adapter_execution: {str(payload['live_adapter_execution']).lower()}",
        f"support_widening: {str(payload['support_widening']).lower()}",
        f"production_platform_claim: {str(payload['production_platform_claim']).lower()}",
    ]
    findings = payload.get("findings", [])
    if findings:
        lines.append("findings:")
        for finding in findings:
            if isinstance(finding, dict):
                lines.append(f"- {finding.get('code')}: {finding.get('detail')}")
    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle-dir", type=Path, default=DEFAULT_BUNDLE_DIR)
    parser.add_argument("--artifact-path", type=Path, default=None)
    parser.add_argument("--output", choices=("json", "text"), default="json")
    parser.add_argument("--fail-on-blocked", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    bundle_dir = args.bundle_dir
    if not bundle_dir.is_absolute():
        bundle_dir = _repo_root() / bundle_dir
    payload = build_attestation(bundle_dir)
    rendered = json.dumps(payload, indent=2, sort_keys=True)
    if args.artifact_path is not None:
        args.artifact_path.write_text(rendered + "\n", encoding="utf-8")
    if args.output == "text":
        print(_render_text(payload))
    else:
        print(rendered)
    if args.fail_on_blocked and payload["status"] != "metadata_ready":
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
