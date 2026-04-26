#!/usr/bin/env python3
"""Emit metadata-only protected live-adapter prerequisite attestation."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from ao_kernel.live_adapter_gate import (  # noqa: E402
    ATTESTATION_ARTIFACT,
    PROTECTED_ENVIRONMENT_NAME,
    REQUIRED_DEPLOYMENT_PROTECTION_APP_SLUG,
    REQUIRED_SECRET_ID,
    build_live_adapter_gate_attestation,
    render_live_adapter_gate_attestation_text,
    write_live_adapter_gate_attestation,
)


def _load_json_file(path: Path | None) -> object | None:
    """Load a JSON fixture if ``path`` is provided."""

    if path is None:
        return None
    payload: object = json.loads(path.read_text(encoding="utf-8"))
    return payload


def _run_json(command: list[str], *, allow_failure: bool = False) -> object:
    """Run a command that emits JSON and return the decoded payload."""

    completed = subprocess.run(command, check=not allow_failure, capture_output=True, text=True)
    if completed.returncode != 0 and allow_failure:
        return {
            "custom_deployment_protection_rules": [],
            "collection_error": completed.stderr.strip() or str(completed.returncode),
        }
    return json.loads(completed.stdout or "null")


def _collect_live_payloads(repo: str, environment: str) -> tuple[object, object, object, object, object]:
    """Collect GitHub metadata without reading secret values."""

    environment_payload = _run_json(
        [
            "gh",
            "api",
            f"repos/{repo}/environments/{environment}",
        ]
    )
    branch_policy_payload = _run_json(
        [
            "gh",
            "api",
            f"repos/{repo}/environments/{environment}/deployment-branch-policies",
        ]
    )
    secret_payload = _run_json(
        [
            "gh",
            "secret",
            "list",
            "--env",
            environment,
            "--repo",
            repo,
            "--json",
            "name,updatedAt",
        ]
    )
    collaborator_payload = _run_json(
        [
            "gh",
            "api",
            f"repos/{repo}/collaborators?per_page=100",
        ]
    )
    deployment_protection_payload = _run_json(
        [
            "gh",
            "api",
            f"repos/{repo}/environments/{environment}/deployment_protection_rules",
        ],
        allow_failure=True,
    )
    return (
        environment_payload,
        branch_policy_payload,
        secret_payload,
        collaborator_payload,
        deployment_protection_payload,
    )


def build_parser() -> argparse.ArgumentParser:
    """Build the CLI parser."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", default="Halildeu/ao-kernel", help="GitHub repository owner/name.")
    parser.add_argument("--environment", default=PROTECTED_ENVIRONMENT_NAME, help="Protected environment name.")
    parser.add_argument("--secret-id", default=REQUIRED_SECRET_ID, help="Required environment secret handle.")
    parser.add_argument(
        "--deployment-protection-app-slug",
        default=REQUIRED_DEPLOYMENT_PROTECTION_APP_SLUG,
        help="Required GitHub App deployment protection slug.",
    )
    parser.add_argument("--actor-login", default="", help="Current triggering actor login for non-self checks.")
    parser.add_argument(
        "--equivalent-release-gate-approved",
        action="store_true",
        help=(
            "Record a historical equivalent release gate flag; it does not satisfy "
            "the selected GitHub App deployment protection gate."
        ),
    )
    parser.add_argument(
        "--artifact-path",
        type=Path,
        default=Path(ATTESTATION_ARTIFACT),
        help="Path for the metadata-only attestation artifact.",
    )
    parser.add_argument("--output", choices=("json", "text"), default="json", help="Stdout render mode.")
    parser.add_argument(
        "--fail-on-blocked",
        action="store_true",
        help="Return exit code 1 when prerequisites are blocked.",
    )
    parser.add_argument("--environment-json", type=Path, default=None, help="Fixture JSON for environment metadata.")
    parser.add_argument(
        "--branch-policies-json",
        type=Path,
        default=None,
        help="Fixture JSON for deployment branch policy metadata.",
    )
    parser.add_argument("--secrets-json", type=Path, default=None, help="Fixture JSON for secret names.")
    parser.add_argument("--collaborators-json", type=Path, default=None, help="Fixture JSON for collaborators.")
    parser.add_argument(
        "--deployment-protection-json",
        type=Path,
        default=None,
        help="Fixture JSON for deployment protection rules.",
    )
    return parser


def _fixture_payloads(args: argparse.Namespace) -> tuple[object, object, object, object, object] | None:
    """Return fixture payloads when all fixture inputs are provided."""

    core_paths = (args.environment_json, args.branch_policies_json, args.secrets_json, args.collaborators_json)
    if all(path is None for path in core_paths):
        if args.deployment_protection_json is not None:
            raise SystemExit("deployment protection fixture requires the core fixture inputs")
        return None
    if any(path is None for path in core_paths):
        raise SystemExit("all core fixture inputs must be provided together")
    return (
        _load_json_file(args.environment_json),
        _load_json_file(args.branch_policies_json),
        _load_json_file(args.secrets_json),
        _load_json_file(args.collaborators_json),
        _load_json_file(args.deployment_protection_json) if args.deployment_protection_json else {},
    )


def main(argv: list[str] | None = None) -> int:
    """CLI entrypoint."""

    parser = build_parser()
    args = parser.parse_args(argv)
    payloads = _fixture_payloads(args)
    if payloads is None:
        payloads = _collect_live_payloads(args.repo, args.environment)

    (
        environment_payload,
        branch_policy_payload,
        secret_payload,
        collaborator_payload,
        deployment_protection_payload,
    ) = payloads
    artifact = build_live_adapter_gate_attestation(
        environment_payload=environment_payload,
        branch_policy_payload=branch_policy_payload,
        secret_payload=secret_payload,
        collaborator_payload=collaborator_payload,
        deployment_protection_payload=deployment_protection_payload,
        environment_name=args.environment,
        required_secret_id=args.secret_id,
        required_deployment_protection_app_slug=args.deployment_protection_app_slug,
        actor_login=args.actor_login,
        equivalent_release_gate_approved=args.equivalent_release_gate_approved,
    )
    write_live_adapter_gate_attestation(args.artifact_path, artifact)

    if args.output == "json":
        print(json.dumps(artifact, indent=2, sort_keys=True))
    else:
        print(render_live_adapter_gate_attestation_text(artifact))

    if args.fail_on_blocked and artifact["overall_status"] != "ready":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
