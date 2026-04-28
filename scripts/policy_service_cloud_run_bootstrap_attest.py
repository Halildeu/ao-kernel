#!/usr/bin/env python3
"""Emit metadata-only policy service Cloud Run deploy bootstrap attestation."""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path
from typing import Literal, TypedDict

ARTIFACT_KIND = "policy_service_cloud_run_bootstrap_attestation"
ARTIFACT_NAME = "policy-service-cloud-run-bootstrap-attestation.v1.json"
PROGRAM_ID = "GPP-2ab"
SERVICE_ID = "ao-kernel-live-adapter-gate-policy-service"

REQUIRED_REPOSITORY_VARIABLES: tuple[str, ...] = (
    "GCP_PROJECT_ID",
    "GCP_WORKLOAD_IDENTITY_PROVIDER",
    "GCP_SERVICE_ACCOUNT",
    "GCP_CLOUD_RUN_REGION",
    "GCP_ARTIFACT_REGISTRY_LOCATION",
    "GCP_ARTIFACT_REGISTRY_REPOSITORY",
    "POLICY_SERVICE_NAME",
    "AO_GITHUB_APP_ID",
    "AO_POLICY_SERVICE_WEBHOOK_SECRET_NAME",
    "AO_GITHUB_APP_PRIVATE_KEY_SECRET_NAME",
)

OPTIONAL_REPOSITORY_VARIABLES: tuple[str, ...] = (
    "AO_POLICY_SERVICE_WEBHOOK_SECRET_VERSION",
    "AO_GITHUB_APP_PRIVATE_KEY_SECRET_VERSION",
)


class VariableStatus(TypedDict):
    """Sanitized repository variable metadata."""

    name: str
    present: bool
    updated_at: str | None


class BootstrapCheck(TypedDict):
    """One attestation check row."""

    id: str
    status: Literal["pass", "blocked"]
    detail: str


class BootstrapAttestation(TypedDict):
    """Policy service Cloud Run bootstrap attestation artifact."""

    schema_version: str
    artifact_kind: str
    program_id: str
    service_id: str
    overall_status: Literal["metadata_ready", "blocked"]
    finding_code: str | None
    reason: str
    required_repository_variables: list[VariableStatus]
    optional_repository_variables: list[VariableStatus]
    missing_repository_variables: list[str]
    checks: list[BootstrapCheck]
    github_repository_variable_metadata_checked: bool
    cloud_oidc_bootstrap_attested: bool
    cloud_run_deploy_executed: bool
    secret_value_readback: bool
    github_callback_post: bool
    live_adapter_execution: bool
    support_widening: bool
    production_platform_claim: bool


def _variable_index(variable_payload: object) -> dict[str, str | None]:
    """Return variable name -> updatedAt without preserving values."""

    if not isinstance(variable_payload, list):
        raise ValueError("repository variable payload must be a JSON list")
    variables: dict[str, str | None] = {}
    for item in variable_payload:
        if not isinstance(item, dict):
            continue
        name = item.get("name")
        if not isinstance(name, str) or not name:
            continue
        updated_at = item.get("updatedAt")
        variables[name] = updated_at if isinstance(updated_at, str) else None
    return variables


def _statuses(names: tuple[str, ...], variables: dict[str, str | None]) -> list[VariableStatus]:
    return [{"name": name, "present": name in variables, "updated_at": variables.get(name)} for name in names]


def _check(check_id: str, *, ok: bool, detail: str) -> BootstrapCheck:
    return {"id": check_id, "status": "pass" if ok else "blocked", "detail": detail}


def build_policy_service_cloud_run_bootstrap_attestation(variable_payload: object) -> BootstrapAttestation:
    """Build a metadata-only deploy bootstrap attestation.

    This intentionally validates repository variable handles only. It does not
    prove Google Cloud Workload Identity, Artifact Registry, Secret Manager, or
    Cloud Run are configured correctly.
    """

    variables = _variable_index(variable_payload)
    missing = [name for name in REQUIRED_REPOSITORY_VARIABLES if name not in variables]
    metadata_ready = not missing
    checks = [
        _check(
            "required_repository_variables",
            ok=metadata_ready,
            detail=(
                "All required repository variable handles are present."
                if metadata_ready
                else f"Missing required repository variable handles: {', '.join(missing)}."
            ),
        ),
        _check(
            "secret_value_readback",
            ok=True,
            detail="Only repository variable names and update timestamps were inspected.",
        ),
        _check(
            "cloud_bootstrap_scope",
            ok=True,
            detail="Google Cloud OIDC, Artifact Registry, Secret Manager, and Cloud Run were not contacted.",
        ),
        _check(
            "runtime_side_effects",
            ok=True,
            detail="No deploy, GitHub callback post, protected workflow dispatch, or live adapter execution was performed.",
        ),
    ]
    return {
        "schema_version": "1",
        "artifact_kind": ARTIFACT_KIND,
        "program_id": PROGRAM_ID,
        "service_id": SERVICE_ID,
        "overall_status": "metadata_ready" if metadata_ready else "blocked",
        "finding_code": None if metadata_ready else "policy_cloud_run_bootstrap_missing_repository_variables",
        "reason": (
            "Required GitHub repository variable handles are present; Google Cloud bootstrap remains unproven."
            if metadata_ready
            else "Required GitHub repository variable handles are missing; do not dispatch deployment."
        ),
        "required_repository_variables": _statuses(REQUIRED_REPOSITORY_VARIABLES, variables),
        "optional_repository_variables": _statuses(OPTIONAL_REPOSITORY_VARIABLES, variables),
        "missing_repository_variables": missing,
        "checks": checks,
        "github_repository_variable_metadata_checked": True,
        "cloud_oidc_bootstrap_attested": False,
        "cloud_run_deploy_executed": False,
        "secret_value_readback": False,
        "github_callback_post": False,
        "live_adapter_execution": False,
        "support_widening": False,
        "production_platform_claim": False,
    }


def write_attestation(path: Path, attestation: BootstrapAttestation) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(attestation, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def render_attestation_text(attestation: BootstrapAttestation) -> str:
    missing = attestation["missing_repository_variables"]
    lines = [
        "Policy Service Cloud Run Bootstrap Attestation",
        f"overall_status: {attestation['overall_status']}",
        f"finding_code: {attestation['finding_code'] or '<none>'}",
        f"reason: {attestation['reason']}",
        f"missing_repository_variables: {', '.join(missing) if missing else '<none>'}",
        f"cloud_oidc_bootstrap_attested: {str(attestation['cloud_oidc_bootstrap_attested']).lower()}",
        f"cloud_run_deploy_executed: {str(attestation['cloud_run_deploy_executed']).lower()}",
        f"secret_value_readback: {str(attestation['secret_value_readback']).lower()}",
        f"github_callback_post: {str(attestation['github_callback_post']).lower()}",
        f"live_adapter_execution: {str(attestation['live_adapter_execution']).lower()}",
        f"support_widening: {str(attestation['support_widening']).lower()}",
        f"production_platform_claim: {str(attestation['production_platform_claim']).lower()}",
        "",
        "Required repository variables:",
    ]
    for item in attestation["required_repository_variables"]:
        status = "present" if item["present"] else "missing"
        lines.append(f"- {item['name']}: {status}")
    lines.append("")
    lines.append("Checks:")
    for check in attestation["checks"]:
        lines.append(f"- {check['id']}: {check['status']} - {check['detail']}")
    return "\n".join(lines) + "\n"


def _load_json(path: Path | None) -> object | None:
    if path is None:
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _collect_repository_variables(repo: str) -> object:
    completed = subprocess.run(
        ["gh", "variable", "list", "--repo", repo, "--json", "name,updatedAt"],
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(completed.stdout or "[]")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", default="Halildeu/ao-kernel", help="GitHub repository owner/name.")
    parser.add_argument("--variables-json", type=Path, default=None, help="Fixture JSON from gh variable list.")
    parser.add_argument(
        "--artifact-path",
        type=Path,
        default=Path(ARTIFACT_NAME),
        help="Path for the metadata-only bootstrap attestation artifact.",
    )
    parser.add_argument("--output", choices=("json", "text"), default="json", help="Stdout render mode.")
    parser.add_argument("--fail-on-blocked", action="store_true", help="Return exit code 1 when metadata is blocked.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    variable_payload = _load_json(args.variables_json)
    if variable_payload is None:
        variable_payload = _collect_repository_variables(args.repo)

    attestation = build_policy_service_cloud_run_bootstrap_attestation(variable_payload)
    write_attestation(args.artifact_path, attestation)

    if args.output == "json":
        print(json.dumps(attestation, indent=2, sort_keys=True))
    else:
        print(render_attestation_text(attestation), end="")

    if args.fail_on_blocked and attestation["overall_status"] != "metadata_ready":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
