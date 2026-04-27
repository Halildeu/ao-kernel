#!/usr/bin/env python3
"""Build a protected live-adapter policy service callback artifact locally."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from ao_kernel.live_adapter_gate_policy_service import (  # noqa: E402
    GITHUB_DEPLOYMENT_PROTECTION_EVENT,
    POLICY_SERVICE_ARTIFACT,
    build_live_adapter_gate_policy_service_result,
    github_webhook_signature,
    render_live_adapter_gate_policy_service_text,
    write_live_adapter_gate_policy_service_result,
)


def build_parser() -> argparse.ArgumentParser:
    """Build the CLI parser."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--payload",
        type=Path,
        required=True,
        help="Path to a deployment_protection_rule webhook or enriched policy payload JSON.",
    )
    parser.add_argument(
        "--artifact-path",
        type=Path,
        default=Path(POLICY_SERVICE_ARTIFACT),
        help="Path for the service callback artifact.",
    )
    parser.add_argument("--output", choices=("json", "text"), default="json", help="Stdout render mode.")
    parser.add_argument("--event", default=GITHUB_DEPLOYMENT_PROTECTION_EVENT, help="X-GitHub-Event header value.")
    parser.add_argument("--delivery-id", default="local-fixture", help="X-GitHub-Delivery header value.")
    parser.add_argument("--signature", default=None, help="X-Hub-Signature-256 header value.")
    parser.add_argument(
        "--webhook-secret-env",
        default=None,
        help="Environment variable that contains the webhook secret for signature verification.",
    )
    parser.add_argument(
        "--sign-fixture-with-secret-env",
        default=None,
        help="Environment variable used to sign the local fixture before verification.",
    )
    parser.add_argument(
        "--allow-unsigned-fixture",
        action="store_true",
        help="Skip signature verification for local fixture evaluation only.",
    )
    parser.add_argument(
        "--fail-on-blocked",
        action="store_true",
        help="Return exit code 1 when the service result is blocked.",
    )
    return parser


def _env_secret(name: str | None) -> str | None:
    """Return an environment secret by name without printing it."""

    if name is None:
        return None
    value = os.environ.get(name)
    if not value:
        raise SystemExit(f"environment variable {name} is not set")
    return value


def main(argv: list[str] | None = None) -> int:
    """CLI entrypoint."""

    parser = build_parser()
    args = parser.parse_args(argv)
    body = args.payload.read_bytes()
    webhook_secret = _env_secret(args.webhook_secret_env)
    signature = args.signature
    signing_secret = _env_secret(args.sign_fixture_with_secret_env)
    if signing_secret is not None:
        signature = github_webhook_signature(signing_secret, body)
        if webhook_secret is None:
            webhook_secret = signing_secret

    require_signature = not args.allow_unsigned_fixture
    headers = {
        "X-GitHub-Event": args.event,
        "X-GitHub-Delivery": args.delivery_id,
    }
    if signature is not None:
        headers["X-Hub-Signature-256"] = signature

    result = build_live_adapter_gate_policy_service_result(
        body,
        headers,
        webhook_secret=webhook_secret,
        require_signature=require_signature,
    )
    write_live_adapter_gate_policy_service_result(args.artifact_path, result)

    if args.output == "json":
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        print(render_live_adapter_gate_policy_service_text(result))

    if args.fail_on_blocked and result["status"] == "blocked":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
