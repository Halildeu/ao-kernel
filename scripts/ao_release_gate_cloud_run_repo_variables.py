#!/usr/bin/env python3
"""Set non-secret Cloud Run deploy repository variables for ao-release-gate."""

from __future__ import annotations

import argparse
import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, NoReturn

DEFAULT_REPOSITORY = "Halildeu/ao-kernel"
REQUIRED_REPOSITORY_VARIABLES: tuple[str, ...] = (
    "GCP_PROJECT_ID",
    "GCP_WORKLOAD_IDENTITY_PROVIDER",
    "GCP_SERVICE_ACCOUNT",
    "GCP_CLOUD_RUN_REGION",
    "GCP_ARTIFACT_REGISTRY_LOCATION",
    "GCP_ARTIFACT_REGISTRY_REPOSITORY",
    "RELEASE_GATE_SERVICE_NAME",
    "AO_RELEASE_GATE_GITHUB_APP_ID",
    "AO_RELEASE_GATE_WEBHOOK_SECRET_NAME",
    "AO_RELEASE_GATE_GITHUB_APP_PRIVATE_KEY_SECRET_NAME",
)
OPTIONAL_REPOSITORY_VARIABLES: tuple[str, ...] = (
    "AO_RELEASE_GATE_WEBHOOK_SECRET_VERSION",
    "AO_RELEASE_GATE_GITHUB_APP_PRIVATE_KEY_SECRET_VERSION",
)
ALLOWED_REPOSITORY_VARIABLES = REQUIRED_REPOSITORY_VARIABLES + OPTIONAL_REPOSITORY_VARIABLES
DENIED_VARIABLE_NAMES = frozenset(
    {
        "AO_CLAUDE_CODE_CLI_AUTH",
        "AO_RELEASE_GATE_WEBHOOK_SECRET",
        "AO_GITHUB_APP_ID",
        "AO_GITHUB_APP_PRIVATE_KEY_PEM",
        "AO_GITHUB_APP_PRIVATE_KEY_PATH",
    }
)
DENIED_VALUE_MARKERS = (
    "-----BEGIN ",
    "github_pat_",
    "ghp_",
    "gho_",
    "ghu_",
    "ghs_",
    "glpat-",
    "xoxb-",
    "xoxp-",
    "sk-ant-",
    "sk-",
)


@dataclass(frozen=True)
class RepositoryVariableOperation:
    """A validated GitHub repository variable write operation."""

    name: str
    value: str


class ConfigError(ValueError):
    """Raised when the local variable config is unsafe or incomplete."""


RunGh = Callable[..., subprocess.CompletedProcess[str]]


def _fail(message: str) -> NoReturn:
    raise ConfigError(message)


def empty_template() -> dict[str, str]:
    return {name: "" for name in ALLOWED_REPOSITORY_VARIABLES}


def write_template(path: Path, *, force: bool = False) -> None:
    if path.exists() and not force:
        _fail(f"refusing to overwrite existing template: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(empty_template(), indent=2, sort_keys=False) + "\n", encoding="utf-8")


def load_config(path: Path) -> dict[str, str]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        _fail("configuration must be a JSON object of repository variable names to values")

    config: dict[str, str] = {}
    for key, value in payload.items():
        if not isinstance(key, str) or not key:
            _fail("all repository variable names must be non-empty strings")
        if not isinstance(value, str):
            _fail(f"repository variable {key} must have a string value")
        config[key] = value
    return config


def _looks_like_secret_value(value: str) -> bool:
    stripped = value.strip()
    return any(marker in stripped for marker in DENIED_VALUE_MARKERS)


def build_operations(config: dict[str, str]) -> list[RepositoryVariableOperation]:
    unknown = sorted(set(config) - set(ALLOWED_REPOSITORY_VARIABLES) - DENIED_VARIABLE_NAMES)
    denied = sorted(set(config) & DENIED_VARIABLE_NAMES)
    missing_required = [name for name in REQUIRED_REPOSITORY_VARIABLES if not config.get(name, "").strip()]
    suspicious_values = [name for name, value in config.items() if value and _looks_like_secret_value(value)]

    errors: list[str] = []
    if unknown:
        errors.append(f"unknown repository variables: {', '.join(unknown)}")
    if denied:
        errors.append(f"secret/runtime credential names are not repository variables: {', '.join(denied)}")
    if missing_required:
        errors.append(f"missing required repository variables: {', '.join(missing_required)}")
    if suspicious_values:
        errors.append(
            "values look like credential material and must be stored in the cloud secret manager instead: "
            + ", ".join(sorted(suspicious_values))
        )
    if errors:
        _fail("\n".join(errors))

    operations: list[RepositoryVariableOperation] = []
    for name in ALLOWED_REPOSITORY_VARIABLES:
        value = config.get(name, "").strip()
        if value:
            operations.append(RepositoryVariableOperation(name=name, value=value))
    return operations


def apply_operations(
    operations: list[RepositoryVariableOperation],
    *,
    repo: str,
    runner: RunGh = subprocess.run,
) -> None:
    for operation in operations:
        runner(
            ["gh", "variable", "set", operation.name, "--repo", repo],
            check=True,
            capture_output=True,
            input=operation.value,
            text=True,
        )


def render_summary(operations: list[RepositoryVariableOperation], *, repo: str, dry_run: bool) -> dict[str, Any]:
    return {
        "repo": repo,
        "mode": "dry_run" if dry_run else "applied",
        "variable_count": len(operations),
        "variables": [operation.name for operation in operations],
        "secret_value_readback": False,
        "cloud_run_deploy_executed": False,
        "check_run_post": False,
        "real_pr_evidence": False,
        "branch_protection_cutover": False,
        "merge_authority_enabled": False,
        "live_adapter_execution": False,
        "support_widening": False,
        "production_platform_claim": False,
    }


def render_text(summary: dict[str, Any]) -> str:
    lines = [
        "AO Release Gate Cloud Run Repository Variables",
        f"repo: {summary['repo']}",
        f"mode: {summary['mode']}",
        f"variable_count: {summary['variable_count']}",
        f"secret_value_readback: {str(summary['secret_value_readback']).lower()}",
        f"cloud_run_deploy_executed: {str(summary['cloud_run_deploy_executed']).lower()}",
        f"check_run_post: {str(summary['check_run_post']).lower()}",
        f"real_pr_evidence: {str(summary['real_pr_evidence']).lower()}",
        f"branch_protection_cutover: {str(summary['branch_protection_cutover']).lower()}",
        f"merge_authority_enabled: {str(summary['merge_authority_enabled']).lower()}",
        f"live_adapter_execution: {str(summary['live_adapter_execution']).lower()}",
        f"support_widening: {str(summary['support_widening']).lower()}",
        f"production_platform_claim: {str(summary['production_platform_claim']).lower()}",
        "",
        "Variables:",
    ]
    lines.extend(f"- {name}" for name in summary["variables"])
    return "\n".join(lines) + "\n"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", default=DEFAULT_REPOSITORY, help="GitHub repository owner/name.")
    parser.add_argument(
        "--config-json",
        type=Path,
        default=None,
        help="JSON object containing non-secret repository variable values.",
    )
    parser.add_argument(
        "--write-template",
        type=Path,
        default=None,
        help="Write an empty JSON config template containing required and optional variable names.",
    )
    parser.add_argument(
        "--force-template-overwrite",
        action="store_true",
        help="Allow --write-template to overwrite an existing file.",
    )
    parser.add_argument("--dry-run", action="store_true", help="Validate and print variable names without writing.")
    parser.add_argument("--output", choices=("json", "text"), default="text", help="Stdout render mode.")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        if args.write_template is not None:
            write_template(args.write_template, force=args.force_template_overwrite)
            print(f"Wrote repository variable template: {args.write_template}")
            if args.config_json is None:
                return 0

        if args.config_json is None:
            parser.error("--config-json is required unless --write-template is used")

        operations = build_operations(load_config(args.config_json))
        if not args.dry_run:
            apply_operations(operations, repo=args.repo)

        summary = render_summary(operations, repo=args.repo, dry_run=args.dry_run)
        if args.output == "json":
            print(json.dumps(summary, indent=2, sort_keys=True))
        else:
            print(render_text(summary), end="")
    except ConfigError as exc:
        parser.exit(2, f"error: {exc}\n")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
